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

NO_ACTIVE_PROMPT = """You are a helpful cancellation agent.
The user wants to cancel something but they have NO active orders or bookings.
Tell them politely nothing is active to cancel.
"""


def _extract_order_id(text: str) -> str | None:
    match = re.search(r'ORD-[A-Z0-9]{6,10}', text.upper())
    return match.group() if match else None


def _extract_booking_id(text: str) -> str | None:
    match = re.search(r'BKG-[A-Z0-9]{6,10}', text.upper())
    return match.group() if match else None


def _get_active_orders() -> list:
    return [o for o in get_all_orders() if o.status != "cancelled"]


def _get_active_bookings() -> list:
    from backend.agents.hotel_booking_agent import get_all_hotel_bookings
    return [b for b in get_all_hotel_bookings() if b.status != "cancelled"]


def _order_summary(order) -> str:
    items = ", ".join([f"{i.product_name} ×{i.quantity}" for i in order.items])
    order_type = "🍽️ Food" if order.notes and "Delivery from" in (order.notes or "") else "🛍️ Product"
    return f"{order_type} | {order.order_id} | {items} | ₹{order.total_amount}"


def _booking_summary(booking) -> str:
    return (
        f"🏨 Hotel Booking | {booking.booking_id} | "
        f"{booking.hotel_name} | "
        f"{booking.check_in} → {booking.check_out} | "
        f"{booking.total_nights} night(s) | ₹{booking.estimated_price}"
    )


def _is_referring_to_hotel(message: str) -> bool:
    """Check if user is referring to a hotel booking."""
    hotel_keywords = ["hotel", "room", "booking", "stay", "bkg", "check in", "check-in", "reservation"]
    return any(kw in message.lower() for kw in hotel_keywords)


def _is_referring_to_food(message: str) -> bool:
    """Check if user is referring to a food/product order."""
    food_keywords = ["food", "order", "biryani", "pizza", "burger", "choco", "product", "delivery", "ord"]
    return any(kw in message.lower() for kw in food_keywords)


def handle_order_status(message: str, conversation_history: list) -> str:
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

    order = get_order(order_id)
    if not order:
        return f"I couldn't find any order with ID **{order_id}**. Please double-check and try again. 🔍"

    items_text = "\n".join([
        f"  • {item.product_name} × {item.quantity} = ₹{item.total_price}"
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
💰 **Total:** ₹{order.total_amount}
🕐 **Placed at:** {order.created_at[:16].replace('T', ' ')}
""".strip()


def handle_order_cancel(message: str, conversation_history: list) -> tuple[str, str | None, str | None]:
    from backend.agents.hotel_booking_agent import get_all_hotel_bookings, cancel_hotel_booking, get_hotel_booking

    # Step 1: Check if specific IDs mentioned IN THE MESSAGE ONLY (not history)
    order_id   = _extract_order_id(message)
    booking_id = _extract_booking_id(message)

    # Step 2: Direct cancel by order ID from message
    if order_id:
        order = get_order(order_id)
        if not order:
            return f"I couldn't find order **{order_id}**. Please double-check. 🔍", None, None
        if order.status == "cancelled":
            return f"Order **{order_id}** is already cancelled. ❌", None, None
        update_order_status(order_id, "cancelled")
        summary = _order_summary(order)
        reply = chat_completion(
            [{"role": "user", "content": f"Cancelled: {summary}. Confirm warmly."}],
            CANCEL_CONFIRM_PROMPT.format(summary=summary),
            temperature=0.5
        )
        return reply, order_id, None

    # Step 3: Direct cancel by booking ID from message
    if booking_id:
        booking = get_hotel_booking(booking_id)
        if not booking:
            return f"I couldn't find booking **{booking_id}**. Please double-check. 🔍", None, None
        if booking.status == "cancelled":
            return f"Booking **{booking_id}** is already cancelled. ❌", None, None
        cancel_hotel_booking(booking_id)
        summary = _booking_summary(booking)
        reply = chat_completion(
            [{"role": "user", "content": f"Cancelled: {summary}. Confirm warmly."}],
            CANCEL_CONFIRM_PROMPT.format(summary=summary),
            temperature=0.5
        )
        return reply, None, booking_id

    # Step 4: No specific ID — get all active items
    active_orders   = _get_active_orders()
    active_bookings = _get_active_bookings()

    if not active_orders and not active_bookings:
        reply = chat_completion(
            [{"role": "user", "content": message}],
            NO_ACTIVE_PROMPT,
            temperature=0.4
        )
        return reply, None, None

    # Step 5: User clearly mentions hotel — only deal with hotel bookings
    if _is_referring_to_hotel(message) and not _is_referring_to_food(message):
        if len(active_bookings) == 0:
            return "You have no active hotel bookings to cancel. 🏨", None, None
        if len(active_bookings) == 1:
            booking = active_bookings[0]
            cancel_hotel_booking(booking.booking_id)
            summary = _booking_summary(booking)
            reply = chat_completion(
                [{"role": "user", "content": f"Cancelled: {summary}. Confirm warmly."}],
                CANCEL_CONFIRM_PROMPT.format(summary=summary),
                temperature=0.5
            )
            return reply, None, booking.booking_id
        else:
            items_text = "\n".join([
                f"{i+1}. {_booking_summary(b)}"
                for i, b in enumerate(active_bookings)
            ])
            reply = chat_completion(
                [{"role": "user", "content": message}],
                CANCEL_CLARIFY_PROMPT.format(items=items_text),
                temperature=0.4
            )
            return reply, None, None

    # Step 6: User clearly mentions food/order — only deal with orders
    if _is_referring_to_food(message) and not _is_referring_to_hotel(message):
        if len(active_orders) == 0:
            return "You have no active orders to cancel. 📦", None, None
        if len(active_orders) == 1:
            order = active_orders[0]
            update_order_status(order.order_id, "cancelled")
            summary = _order_summary(order)
            reply = chat_completion(
                [{"role": "user", "content": f"Cancelled: {summary}. Confirm warmly."}],
                CANCEL_CONFIRM_PROMPT.format(summary=summary),
                temperature=0.5
            )
            return reply, order.order_id, None
        else:
            items_text = "\n".join([
                f"{i+1}. {_order_summary(o)}"
                for i, o in enumerate(active_orders)
            ])
            reply = chat_completion(
                [{"role": "user", "content": message}],
                CANCEL_CLARIFY_PROMPT.format(items=items_text),
                temperature=0.4
            )
            return reply, None, None

    # Step 7: Completely unclear — show ALL active items
    all_items_text = ""
    if active_orders:
        all_items_text += "**Orders:**\n"
        all_items_text += "\n".join([
            f"{i+1}. {_order_summary(o)}"
            for i, o in enumerate(active_orders)
        ])
    if active_bookings:
        if all_items_text:
            all_items_text += "\n\n"
        all_items_text += "**Hotel Bookings:**\n"
        all_items_text += "\n".join([
            f"{i+1+len(active_orders)}. {_booking_summary(b)}"
            for i, b in enumerate(active_bookings)
        ])

    reply = chat_completion(
        [{"role": "user", "content": message}],
        CANCEL_CLARIFY_PROMPT.format(items=all_items_text),
        temperature=0.4
    )
    return reply, None, None


def handle_order_history() -> tuple[str, dict]:
    """Return all orders AND hotel bookings."""
    from backend.agents.hotel_booking_agent import get_all_hotel_bookings

    orders   = get_all_orders()
    bookings = get_all_hotel_bookings()

    if not orders and not bookings:
        return "You haven't placed any orders or bookings yet. Try ordering something! 🛍️", {"orders": [], "bookings": []}

    lines = []

    if orders:
        lines.append("**🛍️ Orders:**")
        for o in orders:
            status_emoji  = {"confirmed": "✅", "pending": "⏳", "cancelled": "❌"}.get(o.status, "📦")
            order_type    = "🍽️" if o.notes and "Delivery from" in (o.notes or "") else "🛍️"
            items_summary = ", ".join([f"{i.product_name} ×{i.quantity}" for i in o.items])
            lines.append(
                f"{order_type} {status_emoji} **{o.order_id}** — "
                f"{items_summary} — ₹{o.total_amount} — "
                f"{o.created_at[:16].replace('T', ' ')}"
            )

    if bookings:
        lines.append("\n**🏨 Hotel Bookings:**")
        for b in bookings:
            status_emoji = {"confirmed": "✅", "cancelled": "❌"}.get(b.status, "🏨")
            lines.append(
                f"🏨 {status_emoji} **{b.booking_id}** — {b.hotel_name} — "
                f"{b.check_in} → {b.check_out} — "
                f"{b.total_nights} night(s) — ₹{b.estimated_price} — "
                f"{b.created_at[:16].replace('T', ' ')}"
            )

    total = len(orders) + len(bookings)
    reply = f"You have **{total}** record(s):\n\n" + "\n".join(lines)

    return reply, {
        "orders":   [o.model_dump() for o in orders],
        "bookings": [b.model_dump() for b in bookings]
    }