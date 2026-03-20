from fastapi import APIRouter, Cookie
from typing import Optional
from backend.models.schemas import ChatRequest, ChatResponse
from backend.agents.coordinator import route_message
from backend.agents.product_search_agent import handle_product_search
from backend.agents.order_booking_agent import handle_order_booking
from backend.agents.order_status_agent import (
    handle_order_status, handle_order_cancel, handle_order_history
)
from backend.agents.greeting_agent import handle_greeting
from backend.agents.location_agent import handle_location
from backend.agents.hotel_search_agent import handle_hotel_search
from backend.agents.hotel_booking_agent import handle_hotel_booking, get_all_hotel_bookings
from backend.agents.food_delivery_agent import handle_food_search, handle_food_order
from backend.utils.maps import get_maps_embed_url
from backend.utils.llm import chat_completion
from backend.utils.order_store import get_all_orders

# ── 6 Input Roles ─────────────────────────────────────────────────────────────
from backend.utils.context_prefetch import (          # Role 1 — Context
    prefetch_context, format_context_for_prompt
)
from backend.utils.memory import (                    # Role 2 — Memory
    get_short_term_memory,
    load_user_preferences, save_user_preferences,
    extract_preferences_from_message,
    format_preferences_for_prompt,
)
from backend.utils.runtime_context import (           # Role 3 — Environment
    build_runtime_context, format_runtime_for_prompt
)
from backend.utils.policy import (                    # Role 4 — System Instructions
    content_filter, get_agent_policy
)
from backend.utils.dialogue_state import (            # Role 5 — Interaction State
    load_dialogue_state, save_dialogue_state,
    clear_dialogue_state, format_dialogue_state_for_prompt
)
from backend.utils.auth import decode_token
from backend.utils.agent_bus import (                 # Role 6 — Agent-to-Agent
    send_message, receive_messages, clear_messages,
    delegation_message, result_message,
    format_agent_messages_for_prompt,
)
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api", tags=["chat"])

FALLBACK_SYSTEM = """You are a helpful smart assistant. You can help with:
- Browsing and ordering products
- Finding nearby restaurants and ordering food for delivery
- Searching for hotels nearby and booking hotel rooms
- Tracking and cancelling orders
- Showing order history and hotel booking history
Suggest what you can do for the user.
"""

# Flows that use multi-step slot-filling (Role 5)
SLOT_FILLING_AGENTS = {"hotel_booking", "food_order", "order_booking"}

# Agents that benefit from pre-fetched DB context (Role 1)
CONTEXT_AGENTS = {"order_cancel", "order_status", "order_history", "order_booking"}

# Keywords that mean the user wants date-filtered history (not full history)
DATE_KEYWORDS = ["yesterday", "today", "last week", "this week", "last month", "this month"]


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, auth_token: Optional[str] = Cookie(default=None)):
    message             = request.message.strip()
    history             = request.conversation_history
    session_id          = request.session_id
    user_location       = request.location
    selected_restaurant = request.selected_restaurant
    selected_hotel      = request.selected_hotel

    # Extract username from JWT cookie — server-authoritative, never trust client
    username = None
    if auth_token:
        payload  = decode_token(auth_token)
        username = payload.get("sub") if payload else None

    # ── ROLE 4: Content filter (pre-routing gate) ─────────────────────────────
    blocked, block_reply = content_filter(message)
    if blocked:
        return ChatResponse(
            reply=block_reply,
            session_id=session_id,
            agent_used="policy_filter",
        )

    # ── ROLE 3: Build runtime context ─────────────────────────────────────────
    runtime_ctx   = build_runtime_context(session_id, user_location)
    runtime_block = format_runtime_for_prompt(runtime_ctx)

    # ── ROLE 2: Load long-term memory + update preferences ───────────────────
    prefs         = load_user_preferences(session_id)
    pref_updates  = extract_preferences_from_message(message, prefs)
    if pref_updates:
        save_user_preferences(session_id, pref_updates)
        prefs.update(pref_updates)
    memory_block  = format_preferences_for_prompt(prefs)

    # ── ROLE 2: Short-term memory (trimmed history) ───────────────────────────
    short_term    = get_short_term_memory(history, max_turns=6)

    # ── Route message ─────────────────────────────────────────────────────────
    agent_name = route_message(message, short_term)

    # ── ROLE 1: Pre-fetch context if this agent needs DB data ─────────────────
    context_block = ""
    db_context    = {}
    if agent_name in CONTEXT_AGENTS:
        db_context    = prefetch_context(message, session_id, username=username)
        context_block = format_context_for_prompt(db_context)

    # ── ROLE 5: Load dialogue state ───────────────────────────────────────────
    dialogue_state      = load_dialogue_state(session_id)
    dialogue_state_block = format_dialogue_state_for_prompt(dialogue_state)

    # ── ROLE 6: Send delegation message from coordinator to specialist ────────
    delegation = delegation_message(
        from_agent="coordinator",
        to_agent=agent_name,
        task=message,
        session_id=session_id,
        extra={"runtime": runtime_ctx.get("date"), "location": user_location},
    )
    send_message(delegation)

    # Retrieve any pending agent messages for this specialist
    pending_msgs    = receive_messages(session_id, to_agent=agent_name)
    agent_msg_block = format_agent_messages_for_prompt(pending_msgs)
    clear_messages(session_id)  # consume after formatting

    # ── ROLE 4: Per-agent policy fragment ─────────────────────────────────────
    agent_policy = get_agent_policy(agent_name)

    # ── Helper: build kwargs for chat_completion ──────────────────────────────
    def llm_kwargs() -> dict:
        return dict(
            context_block  = context_block,
            memory_block   = memory_block,
            runtime_block  = runtime_block + "\n" + dialogue_state_block,
            agent_msg_block= agent_msg_block,
        )

    # ── Dispatch ──────────────────────────────────────────────────────────────
    reply               = ""
    order_data          = None
    orders_list         = None
    hotel_bookings_list = None
    hotels              = None
    restaurants         = None
    location_data       = None
    map_embed_url       = None
    hotel_booking       = None

    if agent_name == "product_search":
        reply = handle_product_search(message, short_term)

    elif agent_name == "order_booking":
        reply, order_data = handle_order_booking(message, short_term, username=username)
        if order_data:                           # flow completed — clear state
            clear_dialogue_state(session_id)

    elif agent_name == "order_status":
        reply = handle_order_status(message, short_term)

    elif agent_name == "order_history":
        msg_lower = message.lower()
        has_date_filter = any(kw in msg_lower for kw in DATE_KEYWORDS)

        if has_date_filter and db_context:
            # DATE-FILTERED: use pre-fetched context, ask LLM to narrate it
            filtered_orders   = db_context.get("recent_orders", [])
            filtered_bookings = db_context.get("recent_bookings", [])
            date_filter       = db_context.get("date_filter", {})
            start = date_filter.get("start", "")
            end   = date_filter.get("end", "")

            orders_list         = filtered_orders
            hotel_bookings_list = filtered_bookings

            # Build a plain summary for the LLM to narrate
            summary_lines = [f"Date filter: {start} to {end}"]
            if filtered_orders:
                summary_lines.append(f"Orders ({len(filtered_orders)} found):")
                for o in filtered_orders:
                    summary_lines.append(
                        f"  - {o['order_id']} | {o['status']} | ₹{o['total_amount']} | {o['created_at'][:10]}"
                    )
            else:
                summary_lines.append("Orders: none found for this period.")
            if filtered_bookings:
                summary_lines.append(f"Hotel Bookings ({len(filtered_bookings)} found):")
                for b in filtered_bookings:
                    summary_lines.append(
                        f"  - {b['booking_id']} | {b['hotel_name']} | {b['check_in']} → {b['check_out']} | {b['status']}"
                    )
            else:
                summary_lines.append("Hotel Bookings: none found for this period.")

            HISTORY_SYSTEM = (
                "You are a helpful order assistant. The user asked for order history "
                "for a specific date range. Present ONLY the records listed below — "
                "do not add, invent, or omit any. Be concise and friendly."
            )
            llm_messages = [{"role": "user", "content": "\n".join(summary_lines)}]
            reply = chat_completion(llm_messages, HISTORY_SYSTEM, temperature=0.3)

        else:
            # NO DATE FILTER: return full history as before
            reply, records      = handle_order_history(username=username)
            orders_list         = records.get("orders", [])
            hotel_bookings_list = records.get("bookings", [])

    elif agent_name == "order_cancel":
        reply, cancelled_order_id, cancelled_booking_id = handle_order_cancel(
            message, short_term, username=username
        )
        if cancelled_order_id or cancelled_booking_id:
            # Re-fetch AFTER cancel so the history panel reflects updated status
            import time; time.sleep(0.05)   # tiny yield to ensure commit flushes
            orders_list         = [o.model_dump() for o in get_all_orders(username=username)]
            hotel_bookings_list = [b.model_dump() for b in get_all_hotel_bookings(username=username)]
            historyPanel_open   = True   # signal frontend to open history panel

    elif agent_name == "hotel_search":
        reply, hotels = await handle_hotel_search(message, short_term, user_location)
        if user_location:
            map_embed_url = get_maps_embed_url(
                user_location["lat"], user_location["lng"], zoom=14
            )

    elif agent_name == "hotel_booking":
        reply, hotel_booking = await handle_hotel_booking(
            message, short_term, selected_hotel, username=username
        )
        if hotel_booking:
            clear_dialogue_state(session_id)
        else:
            # Still collecting slots — persist progress (Role 5)
            save_dialogue_state(session_id, {
                "active_flow": "hotel_booking",
                "step"       : "in_progress",
                "slots"      : {"hotel": selected_hotel.get("name") if selected_hotel else None},
            })

    elif agent_name == "food_search":
        reply, restaurants = await handle_food_search(message, short_term, user_location)
        if user_location:
            map_embed_url = get_maps_embed_url(
                user_location["lat"], user_location["lng"], zoom=15
            )

    elif agent_name == "food_order":
        reply, order_data = await handle_food_order(
            message, short_term, user_location, selected_restaurant, username=username
        )
        if order_data:
            clear_dialogue_state(session_id)

    elif agent_name == "greeting":
        reply = handle_greeting(message, short_term)

    else:
        messages_for_llm = short_term + [{"role": "user", "content": message}]
        reply = chat_completion(
            messages_for_llm,
            FALLBACK_SYSTEM + "\n" + agent_policy,
            temperature=0.5,
            **llm_kwargs(),
        )

    # ── ROLE 6: Send result message back to coordinator ───────────────────────
    send_message(result_message(
        from_agent=agent_name,
        to_agent="coordinator",
        result={"reply_length": len(reply), "agent": agent_name},
        session_id=session_id,
        success=bool(reply),
    ))

    # ── Debug payload (shows what was injected — remove in production) ────────
    input_roles_debug = {
        "role_1_context_injected"  : bool(context_block),
        "role_2_memory_prefs"      : prefs,
        "role_3_runtime_date"      : runtime_ctx.get("date"),
        "role_4_policy_agent"      : agent_name,
        "role_5_dialogue_state"    : dialogue_state,
        "role_6_agent_msgs_count"  : len(pending_msgs),
    }

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        order=order_data,
        agent_used=agent_name,
        hotels=hotels if hotels else None,
        restaurants=restaurants if restaurants else None,
        location=location_data,
        map_embed_url=map_embed_url,
        orders_list=orders_list,
        hotel_booking=hotel_booking,
        hotel_bookings_list=hotel_bookings_list,
        input_roles_debug=input_roles_debug,
    )


@router.post("/location", response_model=dict)
async def update_location(lat: float, lng: float, session_id: str):
    result = await handle_location(lat, lng, [])
    return result


@router.post("/env", response_model=dict)
async def get_env():
    """
    Called by the frontend on startup.
    Returns any public config the client needs.
    Extend this dict as needed — never expose secret keys here.
    """
    return {"status": "ok"}


@router.get("/memory/{session_id}", response_model=dict)
async def get_memory(session_id: str):
    """
    Called by the frontend to load persisted user preferences / short-term memory.
    Returns the stored preference dict for the given session.
    """
    prefs = load_user_preferences(session_id)
    return {"session_id": session_id, "preferences": prefs}


@router.get("/orders", response_model=list)
async def get_orders(auth_token: Optional[str] = Cookie(default=None)):
    username = None
    if auth_token:
        payload  = decode_token(auth_token)
        username = payload.get("sub") if payload else None
    return [o.model_dump() for o in get_all_orders(username=username)]


@router.get("/hotel-bookings", response_model=list)
async def get_hotel_bookings_endpoint(auth_token: Optional[str] = Cookie(default=None)):
    username = None
    if auth_token:
        payload  = decode_token(auth_token)
        username = payload.get("sub") if payload else None
    return [b.model_dump() for b in get_all_hotel_bookings(username=username)]


@router.get("/health")
async def health():
    return {"status": "ok", "message": "Multi-Agent System running"}