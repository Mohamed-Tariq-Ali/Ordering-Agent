from backend.utils.llm import chat_completion

COORDINATOR_SYSTEM_PROMPT = """You are a coordinator agent for a smart assistant system.
Analyze the user's message and decide which specialist agent should handle it.

Available specialist agents:
1. "product_search"   - browse/search products, check prices in store catalog
2. "order_booking"    - book/place an order for products in the store catalog
3. "order_status"     - check status of an existing order by order ID
4. "order_history"    - show all orders, order history, list my orders
5. "order_cancel"     - cancel an existing order
6. "hotel_search"     - find/search/show hotels nearby
7. "food_search"      - find/search nearby restaurants, what's nearby to eat
8. "food_order"       - order food from a restaurant for delivery
9. "greeting"         - general greeting, thanks, small talk
10. "clarification"   - intent is unclear

Respond with ONLY the agent name, nothing else.

Examples:
- "Book 2 Choco" → order_booking
- "What products do you have?" → product_search
- "Show me hotels near me" → hotel_search
- "Find restaurants nearby" → food_search
- "I want to order pizza" → food_order
- "Order 1 biryani for delivery" → food_order
- "What restaurants are near me?" → food_search
- "Book a room" → hotel_search
- "Check my order ORD-123" → order_status
- "Show my order history" → order_history
- "List all my orders" → order_history
- "What orders have I placed?" → order_history
- "Cancel my order" → order_cancel
- "Hello" → greeting
"""


def route_message(message: str, conversation_history: list) -> str:
    history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
    messages = history + [{"role": "user", "content": message}]
    agent = chat_completion(messages, COORDINATOR_SYSTEM_PROMPT, temperature=0.1)
    agent = agent.strip().lower().replace('"', '').replace("'", "").split()[0]
    valid = ["product_search", "order_booking", "order_status", "order_history",
             "order_cancel", "hotel_search", "food_search", "food_order",
             "greeting", "clarification"]
    return agent if agent in valid else "clarification"