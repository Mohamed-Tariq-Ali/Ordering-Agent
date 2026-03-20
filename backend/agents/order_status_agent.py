import re
from backend.utils.llm import chat_completion
from backend.utils.order_store import get_order, update_order_status, get_all_orders
from backend.models.schemas import Order

ORDER_STATUS_SYSTEM_PROMPT = """You are a friendly order status agent.
Tell the user the status of their order clearly and warmly.
If the order is not found, apologize and ask for the correct order ID.
"""

CANCEL_CLARIFY_PROMPT = """You are a helpful cancellation agent.
The user wants to cancel something but has MULTIPLE active orders and/or hotel bookings.
List everything clearly and ask which one they want to cancel.
Be friendly and clear.

Active items:
{items}
"""

CANCEL_CONFIRM_PROMPT = """You are a helpful cancellation agent.
Confirm the cancellation warmly and clearly state what was cancelled.
Cancelled: {summary}
"""

CANCEL_ASK_CONFIRM_PROMPT = """You are a helpful cancellation agent.
The user wants to cancel their most recent item. Show them the details below and ask
them to confirm. Include the order/booking ID, items, amount, and timestamp clearly.

Item to cancel:
{summary}

Ask: "Is this the one you'd like to cancel? Reply yes to confirm."
"""

NO_ACTIVE_PROMPT = """You are a helpful cancellation agent.
The user wants to cancel something but they have NO active orders or bookings.
Tell them politely nothing is active to cancel.
"""

# Words that mean the user is confirming a pending action
CONFIRM_WORDS = {"yes", "yeah", "yep", "yup", "correct", "sure", "ok", "okay",
                 "confirm", "proceed", "go ahead", "do it", "cancel it", "yes correct",
                 "please cancel", "yes please"}

# Keywords that mean "most recent"
LAST_ORDER_KEYWORDS   = ["last order", "latest order", "most recent order",
                         "recent order", "last food order", "latest food order",
                         "last placed order", "previous order"]
LAST_BOOKING_KEYWORDS = ["last booking", "latest booking", "most recent booking",
                         "recent booking", "last hotel", "latest hotel",
                         "last hotel booking", "previous booking"]


def _extract_order_id(text: str) -> str | None:
    match = re.search(r'ORD-[A-Z0-9]{6,10}', text.upper())
    return match.group() if match else None


def _extract_booking_id(text: str) -> str | None:
    match = re.search(r'BKG-[A-Z0-9]{6,10}', text.upper())
    return match.group() if match else None


def _extract_number_choice(text: str) -> int | None:
    match = re.search(r'\b([1-9])\b', text)
    return int(match.group(1)) if match else None


def _is_confirmation(message: str) -> bool:
    msg = message.lower().strip().rstrip("!.,?")
    if msg in CONFIRM_WORDS:
        return True
    for word in CONFIRM_WORDS:
        if msg.startswith(word):
            return True
    return False


def _is_last_order_request(message: str) -> bool:
    msg = message.lower()
    return any(kw in msg for kw in LAST_ORDER_KEYWORDS)


def _is_last_booking_request(message: str) -> bool:
    msg = message.lower()
    return any(kw in msg for kw in LAST_BOOKING_KEYWORDS)


def _get_active_orders(username: str = None) -> list:
    return [o for o in get_all_orders(username=username) if o.status != "cancelled"]


def _get_active_bookings(username: str = None) -> list:
    from backend.agents.hotel_booking_agent import get_all_hotel_bookings
    return [b for b in get_all_hotel_bookings(username=username) if b.status != "cancelled"]


def _get_most_recent_order(username: str = None):
    orders = _get_active_orders(username=username)
    if not orders:
        return None
    return sorted(orders, key=lambda o: o.created_at, reverse=True)[0]


def _get_most_recent_booking(username: str = None):
    bookings = _get_active_bookings(username=username)
    if not bookings:
        return None
    return sorted(bookings, key=lambda b: b.created_at, reverse=True)[0]


def _order_summary(order) -> str:
    items = ", ".join([f"{i.product_name} x{i.quantity}" for i in order.items])
    order_type = "Food" if order.notes and "Delivery from" in (order.notes or "") else "Product"
    timestamp = order.created_at[:16].replace('T', ' ')
    return f"{order_type} Order | {order.order_id} | {items} | Rs.{order.total_amount} | Placed: {timestamp}"


def _booking_summary(booking) -> str:
    timestamp = booking.created_at[:16].replace('T', ' ')
    return (
        f"Hotel Booking | {booking.booking_id} | "
        f"{booking.hotel_name} | "
        f"{booking.check_in} to {booking.check_out} | "
        f"{booking.total_nights} night(s) | Rs.{booking.estimated_price} | Booked: {timestamp}"
    )


def _is_referring_to_hotel(message: str) -> bool:
    hotel_keywords = ["hotel", "room", "booking", "stay", "bkg", "check in", "check-in", "reservation"]
    return any(kw in message.lower() for kw in hotel_keywords)


def _is_referring_to_food(message: str) -> bool:
    food_keywords = ["food", "order", "biryani", "pizza", "burger", "choco", "product", "delivery", "ord"]
    return any(kw in message.lower() for kw in food_keywords)


def _find_pending_cancel_target(conversation_history: list) -> tuple[str | None, str | None]:
    for msg in reversed(conversation_history[-10:]):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        booking_id = _extract_booking_id(content)
        if booking_id:
            return None, booking_id
        order_id = _extract_order_id(content)
        if order_id:
            return order_id, None
    return None, None


def _find_list_cancel_target(conversation_history: list, choice: int, username: str = None):
    active_orders   = _get_active_orders(username=username)
    active_bookings = _get_active_bookings(username=username)

    combined = []
    for o in sorted(active_orders, key=lambda o: o.created_at, reverse=True):
        combined.append(("order", o))
    for b in sorted(active_bookings, key=lambda b: b.created_at, reverse=True):
        combined.append(("booking", b))

    idx = choice - 1
    if 0 <= idx < len(combined):
        kind, item = combined[idx]
        if kind == "order":
            return item, None
        else:
            return None, item
    return None, None


def handle_order_status(message: str, conversation_history: list, username: str = None) -> str:
    order_id = _extract_order_id(message)

    if not order_id:
        for msg in reversed(conversation_history):
            found = _extract_order_id(msg.get("content", ""))
            if found:
                order_id = found
                break

    if not order_id:
        history = conversation_history[-6:]
        messages = history + [{"role": "user", "content": message}]
        return chat_completion(
            messages,
            ORDER_STATUS_SYSTEM_PROMPT + "\nNo order ID found. Ask the user for their Order ID (format: ORD-XXXXXXXX).",
            temperature=0.4
        )

    order = get_order(order_id, username=username)
    if not order:
        return f"I couldn't find any order with ID **{order_id}**. Please double-check and try again."

    items_text = "\n".join([
        f"  - {item.product_name} x {item.quantity} = Rs.{item.total_price}"
        for item in order.items
    ])
    status_emoji = {"confirmed": "✅", "pending": "⏳", "cancelled": "❌"}.get(order.status, "📦")
    order_type = "🍽️ Food Delivery" if order.notes and "Delivery from" in (order.notes or "") else "🛍️ Product Order"

    return f"""
{order_type}
🆔 **Order ID:** {order.order_id}
{status_emoji} **Status:** {order.status.title()}
📦 **Items:**
{items_text}
💰 **Total:** Rs.{order.total_amount}
🕐 **Placed at:** {order.created_at[:16].replace('T', ' ')}
""".strip()


def handle_order_cancel(message: str, conversation_history: list, username: str = None) -> tuple[str, str | None, str | None]:
    from backend.agents.hotel_booking_agent import get_all_hotel_bookings, cancel_hotel_booking, get_hotel_booking

    msg_lower = message.lower().strip()

    # ── STEP 1: Explicit ID in message — cancel immediately ──────────────────
    order_id   = _extract_order_id(message)
    booking_id = _extract_booking_id(message)

    if order_id:
        order = get_order(order_id, username=username)
        if not order:
            return f"I couldn't find order **{order_id}**. Please double-check. 🔍", None, None
        if order.status == "cancelled":
            return f"Order **{order_id}** is already cancelled. ❌", None, None
        update_order_status(order_id, "cancelled", username=username)
        summary = _order_summary(order)
        reply = chat_completion(
            [{"role": "user", "content": f"Cancelled: {summary}. Confirm warmly."}],
            CANCEL_CONFIRM_PROMPT.format(summary=summary),
            temperature=0.5
        )
        return reply, order_id, None

    if booking_id:
        booking = get_hotel_booking(booking_id, username=username)
        if not booking:
            return f"I couldn't find booking **{booking_id}**. Please double-check. 🔍", None, None
        if booking.status == "cancelled":
            return f"Booking **{booking_id}** is already cancelled. ❌", None, None
        cancel_hotel_booking(booking_id, username=username)
        summary = _booking_summary(booking)
        reply = chat_completion(
            [{"role": "user", "content": f"Cancelled: {summary}. Confirm warmly."}],
            CANCEL_CONFIRM_PROMPT.format(summary=summary),
            temperature=0.5
        )
        return reply, None, booking_id

    # ── STEP 2: "cancel my last order / last booking" ─────────────────────────
    if _is_last_order_request(message):
        order = _get_most_recent_order(username=username)
        if not order:
            return "You have no active orders to cancel. 📦", None, None
        summary = _order_summary(order)
        reply = chat_completion(
            [{"role": "user", "content": summary}],
            CANCEL_ASK_CONFIRM_PROMPT.format(summary=summary),
            temperature=0.4
        )
        return reply, None, None

    if _is_last_booking_request(message):
        booking = _get_most_recent_booking(username=username)
        if not booking:
            return "You have no active hotel bookings to cancel. 🏨", None, None
        summary = _booking_summary(booking)
        reply = chat_completion(
            [{"role": "user", "content": summary}],
            CANCEL_ASK_CONFIRM_PROMPT.format(summary=summary),
            temperature=0.4
        )
        return reply, None, None

    # ── STEP 3: User is confirming ("yes", "yes correct") ────────────────────
    if _is_confirmation(message):
        pending_order_id, pending_booking_id = _find_pending_cancel_target(conversation_history)

        if pending_booking_id:
            booking = get_hotel_booking(pending_booking_id, username=username)
            if booking and booking.status != "cancelled":
                cancel_hotel_booking(pending_booking_id, username=username)
                summary = _booking_summary(booking)
                reply = chat_completion(
                    [{"role": "user", "content": f"Cancelled: {summary}. Confirm warmly."}],
                    CANCEL_CONFIRM_PROMPT.format(summary=summary),
                    temperature=0.5
                )
                return reply, None, pending_booking_id

        if pending_order_id:
            order = get_order(pending_order_id, username=username)
            if order and order.status != "cancelled":
                update_order_status(pending_order_id, "cancelled", username=username)
                summary = _order_summary(order)
                reply = chat_completion(
                    [{"role": "user", "content": f"Cancelled: {summary}. Confirm warmly."}],
                    CANCEL_CONFIRM_PROMPT.format(summary=summary),
                    temperature=0.5
                )
                return reply, pending_order_id, None

    # ── STEP 4: Number choice from list ──────────────────────────────────────
    number_choice = _extract_number_choice(msg_lower)
    if number_choice:
        order_obj, booking_obj = _find_list_cancel_target(conversation_history, number_choice, username=username)

        if booking_obj:
            if booking_obj.status == "cancelled":
                return f"Booking **{booking_obj.booking_id}** is already cancelled. ❌", None, None
            cancel_hotel_booking(booking_obj.booking_id, username=username)
            summary = _booking_summary(booking_obj)
            reply = chat_completion(
                [{"role": "user", "content": f"Cancelled: {summary}. Confirm warmly."}],
                CANCEL_CONFIRM_PROMPT.format(summary=summary),
                temperature=0.5
            )
            return reply, None, booking_obj.booking_id

        if order_obj:
            if order_obj.status == "cancelled":
                return f"Order **{order_obj.order_id}** is already cancelled. ❌", None, None
            update_order_status(order_obj.order_id, "cancelled", username=username)
            summary = _order_summary(order_obj)
            reply = chat_completion(
                [{"role": "user", "content": f"Cancelled: {summary}. Confirm warmly."}],
                CANCEL_CONFIRM_PROMPT.format(summary=summary),
                temperature=0.5
            )
            return reply, order_obj.order_id, None

    # ── STEP 5: No match — show the full list sorted by most recent ───────────
    active_orders   = _get_active_orders(username=username)
    active_bookings = _get_active_bookings(username=username)

    if not active_orders and not active_bookings:
        reply = chat_completion(
            [{"role": "user", "content": message}],
            NO_ACTIVE_PROMPT,
            temperature=0.4
        )
        return reply, None, None

    if _is_referring_to_hotel(message) and not _is_referring_to_food(message):
        if len(active_bookings) == 0:
            return "You have no active hotel bookings to cancel. 🏨", None, None
        if len(active_bookings) == 1:
            booking = active_bookings[0]
            summary = _booking_summary(booking)
            reply = chat_completion(
                [{"role": "user", "content": summary}],
                CANCEL_ASK_CONFIRM_PROMPT.format(summary=summary),
                temperature=0.4
            )
            return reply, None, None
        else:
            items_text = "\n".join([f"{i+1}. {_booking_summary(b)}" for i, b in enumerate(
                sorted(active_bookings, key=lambda b: b.created_at, reverse=True)
            )])
            reply = chat_completion(
                [{"role": "user", "content": message}],
                CANCEL_CLARIFY_PROMPT.format(items=items_text),
                temperature=0.4
            )
            return reply, None, None

    if _is_referring_to_food(message) and not _is_referring_to_hotel(message):
        if len(active_orders) == 0:
            return "You have no active orders to cancel. 📦", None, None
        if len(active_orders) == 1:
            order = active_orders[0]
            summary = _order_summary(order)
            reply = chat_completion(
                [{"role": "user", "content": summary}],
                CANCEL_ASK_CONFIRM_PROMPT.format(summary=summary),
                temperature=0.4
            )
            return reply, None, None
        else:
            items_text = "\n".join([f"{i+1}. {_order_summary(o)}" for i, o in enumerate(
                sorted(active_orders, key=lambda o: o.created_at, reverse=True)
            )])
            reply = chat_completion(
                [{"role": "user", "content": message}],
                CANCEL_CLARIFY_PROMPT.format(items=items_text),
                temperature=0.4
            )
            return reply, None, None

    # Mixed — show everything sorted by most recent first
    all_items_text = ""
    active_orders_sorted   = sorted(active_orders,   key=lambda o: o.created_at, reverse=True)
    active_bookings_sorted = sorted(active_bookings, key=lambda b: b.created_at, reverse=True)

    if active_orders_sorted:
        all_items_text += "**Orders (most recent first):**\n"
        all_items_text += "\n".join([f"{i+1}. {_order_summary(o)}" for i, o in enumerate(active_orders_sorted)])
    if active_bookings_sorted:
        if all_items_text:
            all_items_text += "\n\n"
        all_items_text += "**Hotel Bookings (most recent first):**\n"
        all_items_text += "\n".join([
            f"{i+1+len(active_orders_sorted)}. {_booking_summary(b)}"
            for i, b in enumerate(active_bookings_sorted)
        ])

    reply = chat_completion(
        [{"role": "user", "content": message}],
        CANCEL_CLARIFY_PROMPT.format(items=all_items_text),
        temperature=0.4
    )
    return reply, None, None


def handle_order_history(username: str = None) -> tuple[str, dict]:
    """Return all orders AND hotel bookings scoped to the logged-in user."""
    from backend.agents.hotel_booking_agent import get_all_hotel_bookings

    orders   = get_all_orders(username=username)
    bookings = get_all_hotel_bookings(username=username)

    if not orders and not bookings:
        return "You haven't placed any orders or bookings yet. Try ordering something! 🛍️", {"orders": [], "bookings": []}

    lines = []

    if orders:
        lines.append("**🛍️ Orders:**")
        for o in orders:
            status_emoji  = {"confirmed": "✅", "pending": "⏳", "cancelled": "❌"}.get(o.status, "📦")
            order_type    = "🍽️" if o.notes and "Delivery from" in (o.notes or "") else "🛍️"
            items_summary = ", ".join([f"{i.product_name} x{i.quantity}" for i in o.items])
            cancelled_note = " ~~cancelled~~" if o.status == "cancelled" else ""
            lines.append(
                f"{order_type} {status_emoji} **{o.order_id}**{cancelled_note} — "
                f"{items_summary} — Rs.{o.total_amount} — "
                f"{o.created_at[:16].replace('T', ' ')}"
            )

    if bookings:
        lines.append("\n**🏨 Hotel Bookings:**")
        for b in bookings:
            status_emoji = {"confirmed": "✅", "cancelled": "❌"}.get(b.status, "🏨")
            lines.append(
                f"🏨 {status_emoji} **{b.booking_id}** — {b.hotel_name} — "
                f"{b.check_in} to {b.check_out} — "
                f"{b.total_nights} night(s) — Rs.{b.estimated_price} — "
                f"{b.created_at[:16].replace('T', ' ')}"
            )

    total = len(orders) + len(bookings)
    reply = f"You have **{total}** record(s):\n\n" + "\n".join(lines)

    return reply, {
        "orders":   [o.model_dump() for o in orders],
        "bookings": [b.model_dump() for b in bookings]
    }