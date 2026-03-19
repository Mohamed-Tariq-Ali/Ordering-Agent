from typing import Dict, List
import re
from backend.utils.llm import chat_completion
from backend.utils.order_store import get_order, update_order_status, get_all_orders

ORDER_STATUS_SYSTEM_PROMPT = """You are a friendly order status agent.
Tell the user the status of their order clearly and warmly.
If the order is not found, apologize and ask for the correct order ID.
"""

ORDER_CANCEL_SYSTEM_PROMPT = """You are a helpful order cancellation agent.
Help the user cancel their order. Be empathetic and clear.
If the order is cancelled, confirm it warmly.
If the order is not found, ask for the correct order ID.
"""


def _extract_order_id(text: str) -> str | None:
    match = re.search(r'ORD-[A-Z0-9]{6,10}', text.upper())
    return match.group() if match else None


def handle_order_status(message: str, conversation_history: list) -> str:
    order_id = _extract_order_id(message)

    if not order_id:
        for msg in reversed(conversation_history):
            found = _extract_order_id(msg.get("content", ""))
            if found:
                order_id = found
                break

    if not order_id:
        history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
        messages = history + [{"role": "user", "content": message}]
        return chat_completion(
            messages,
            ORDER_STATUS_SYSTEM_PROMPT + "\nNo order ID found. Ask the user for their Order ID (format: ORD-XXXXXXXX).",
            temperature=0.4
        )

    order = get_order(order_id)

    if not order:
        return f"I couldn't find any order with ID **{order_id}**. Please double-check the order ID and try again. 🔍"

    items_text = "\n".join([
        f"  • {item.product_name} × {item.quantity} = ₹{item.total_price}"
        for item in order.items
    ])

    status_emoji = {"confirmed": "✅", "pending": "⏳", "cancelled": "❌"}.get(order.status, "📦")

    return f"""
🆔 **Order ID:** {order.order_id}
{status_emoji} **Status:** {order.status.title()}
📦 **Items:**
{items_text}
💰 **Total:** ₹{order.total_amount}
🕐 **Placed at:** {order.created_at[:16].replace('T', ' ')}
""".strip()


def handle_order_cancel(message: str, conversation_history: list) -> str:
    order_id = _extract_order_id(message)

    if not order_id:
        for msg in reversed(conversation_history):
            found = _extract_order_id(msg.get("content", ""))
            if found:
                order_id = found
                break

    if not order_id:
        return "I'd be happy to help cancel your order! Could you please share your **Order ID**? It looks like `ORD-XXXXXXXX`. 😊"

    order = get_order(order_id)

    if not order:
        return f"I couldn't find any order with ID **{order_id}**. Please double-check and try again."

    if order.status == "cancelled":
        return f"Your order **{order_id}** is already cancelled. Is there anything else I can help you with?"

    update_order_status(order_id, "cancelled")
    return f"Your order **{order_id}** has been successfully cancelled. ✅\n\nIf you'd like to place a new order, just let me know! 😊"


def handle_order_history() -> tuple[str, list]:
    """Return all orders as a chat reply + raw list for the UI panel."""
    orders = get_all_orders()

    if not orders:
        return "You haven't placed any orders yet in this session. Try ordering something! 🛍️", []

    lines = []
    for o in orders:
        status_emoji = {"confirmed": "✅", "pending": "⏳", "cancelled": "❌"}.get(o.status, "📦")
        items_summary = ", ".join([f"{i.product_name} ×{i.quantity}" for i in o.items])
        lines.append(
            f"{status_emoji} **{o.order_id}** — {items_summary} — ₹{o.total_amount} — {o.created_at[:16].replace('T', ' ')}"
        )

    reply = f"You have **{len(orders)}** order(s) this session:\n\n" + "\n".join(lines)
    return reply, [o.model_dump() for o in orders]