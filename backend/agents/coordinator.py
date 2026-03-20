import re
from backend.utils.llm import chat_completion_fast

COORDINATOR_SYSTEM_PROMPT = """You are a coordinator agent for a smart assistant system.
Analyze the user's message and decide which specialist agent should handle it.

Available specialist agents:
1. "product_search"   - browse/search products, check prices in store catalog
2. "order_booking"    - book/place an order for products in the store catalog
3. "order_status"     - check status of a specific existing order by order ID
4. "order_history"    - show all orders, order history, list my orders
5. "order_cancel"     - cancel an order or booking
6. "hotel_search"     - find/search/show hotels nearby or in a city
7. "hotel_booking"    - book a hotel room, reserve a room at a hotel
8. "food_search"      - find/search nearby restaurants
9. "food_order"       - order food from a restaurant for delivery
10. "greeting"        - general greeting, thanks, small talk
11. "clarification"   - intent is unclear

CRITICAL RULES:
- If message contains "book" + a food item (rice, biryani, pizza, burger, dosa, idly etc.) → food_order
- If message contains "order" + a food item → food_order
- If message contains "units of" or "plate of" or "portions of" → food_order
- If message contains "hotel" AND ("search"/"find"/"show"/"near"/"nearby") → hotel_search
- If message contains "hotel" AND ("book"/"reserve"/"room"/"stay"/"night") → hotel_booking
- NEVER route food item orders to hotel_booking or order_booking
- NEVER route hotel searches to food_search

Respond with ONLY the agent name, nothing else.

Examples:
- "book 4 units of fried rice" → food_order
- "order 2 biryani" → food_order
- "2 plates of dosa" → food_order
- "Search hotels near me" → hotel_search
- "Find hotels in Chennai" → hotel_search
- "Book a room at this hotel" → hotel_booking
- "Book 2 nights at the hotel" → hotel_booking
- "Find restaurants nearby" → food_search
- "Show restaurants near me" → food_search
- "Book 2 Choco" → order_booking
- "What products do you have?" → product_search
- "Check my order ORD-123" → order_status
- "Show my order history" → order_history
- "Cancel my order" → order_cancel
- "Cancel the booking" → order_cancel
- "Hello" → greeting
"""

VALID_AGENTS = [
    "product_search", "order_booking", "order_status", "order_history",
    "order_cancel", "hotel_search", "hotel_booking", "food_search",
    "food_order", "greeting", "clarification"
]

FOOD_ITEMS = [
    "rice", "biryani", "pizza", "burger", "dosa", "idly", "idli", "vada",
    "noodles", "pasta", "roti", "naan", "curry", "chicken", "mutton", "fish",
    "paneer", "sandwich", "wrap", "salad", "soup", "chai", "tea", "coffee",
    "juice", "pepsi", "coke", "water", "dessert", "cake", "icecream",
    "fried rice", "chowmein", "parotta", "appam", "uttapam", "upma",
    "pongal", "sambar", "rasam", "dal", "chutney", "snack", "starter",
    "meals", "thali", "combo", "roll", "kebab", "tikka", "wings"
]

CONFIRM_WORDS = {
    "yes", "yeah", "yep", "ok", "okay", "sure", "confirm", "proceed",
    "go ahead", "do it", "book it", "order it", "yes proceed", "yes confirm",
    "yes cancel", "cancel it", "place order", "place it", "yes please",
    "yes correct", "correct"
}

CANCEL_KEYWORDS = [
    "cancel", "cancellation", "delete order", "remove order",
    "don't want", "dont want", "stop order"
]


def _has_pending_cancel(conversation_history: list) -> bool:
    """Check if the last assistant message was asking to confirm a cancellation."""
    for msg in reversed(conversation_history[-6:]):
        if msg.get("role") == "assistant":
            content = msg.get("content", "").lower()
            if any(kw in content for kw in [
                "cancel", "cancellation", "would you like to cancel",
                "confirm", "is this the one", "reply yes to confirm",
                "you'd like to cancel", "cancel this order", "cancel this booking"
            ]):
                return True
            # If last assistant message was NOT about cancellation, stop looking
            break
    return False


def _has_pending_food_order(conversation_history: list) -> bool:
    """Check if the last assistant message was about a food order in progress."""
    for msg in reversed(conversation_history[-6:]):
        if msg.get("role") == "assistant":
            c = msg.get("content", "").lower()
            if any(kw in c for kw in [
                "what would you like to order", "tell me the items",
                "restaurant selected", "order from", "which items",
                "would you like to proceed with the order",
                "would you like to make any changes",
                "order summary", "total:", "proceed with the order",
                "place the order", "confirm your order",
            ]):
                return True
            break
    return False


def _has_pending_hotel_booking(conversation_history: list) -> bool:
    """Check if the last assistant message was collecting hotel booking details."""
    for msg in reversed(conversation_history[-6:]):
        if msg.get("role") == "assistant":
            content = msg.get("content", "").lower()
            if any(kw in content for kw in [
                "check-in", "check-out", "number of guests", "room type",
                "hotel selected", "book a room", "nights"
            ]):
                return True
            break
    return False


def _keyword_route(message: str) -> str | None:
    msg = message.lower().strip()

    # ── Food order — check BEFORE hotel/product booking ──────────────────────
    is_food = any(food in msg for food in FOOD_ITEMS)

    food_order_patterns = [
        r'\d+\s+units?\s+of',
        r'\d+\s+plates?\s+of',
        r'\d+\s+portions?\s+of',
        r'order\s+\d+',
        r'\d+\s+\w+\s+and\s+\d+',
    ]
    if is_food and any(re.search(p, msg) for p in food_order_patterns):
        return "food_order"

    if is_food and any(t in msg for t in ["book ", "order ", "get me ", "i want ", "add "]):
        if not any(t in msg for t in ["room", "hotel room", "night", "check in", "check-in", "suite", "deluxe"]):
            return "food_order"

    # ── Cancel keywords — explicit cancel always wins ─────────────────────────
    if any(kw in msg for kw in CANCEL_KEYWORDS):
        return "order_cancel"

    # ── Hotel ─────────────────────────────────────────────────────────────────
    hotel_search_triggers = ["search hotel", "find hotel", "show hotel", "hotels near",
                             "hotel near", "hotels around", "hotels in ", "hotel in ",
                             "look for hotel", "search for hotel", "nearby hotel"]
    if any(t in msg for t in hotel_search_triggers):
        return "hotel_search"

    hotel_book_triggers = ["book a room", "book room", "reserve a room", "reserve room",
                           "book a hotel", "book hotel", "hotel booking", "book a suite",
                           "book a deluxe", "book a standard", "nights at", "night at",
                           "stay at", "check in", "check-in"]
    if any(t in msg for t in hotel_book_triggers):
        return "hotel_booking"

    # ── Food search ───────────────────────────────────────────────────────────
    food_search_triggers = ["find restaurant", "search restaurant", "restaurants near",
                            "restaurant near", "restaurants around", "restaurants in ",
                            "show restaurant", "food near", "food nearby", "eat near",
                            "where to eat", "places to eat", "nearby restaurant"]
    if any(t in msg for t in food_search_triggers):
        return "food_search"

    # ── Orders ────────────────────────────────────────────────────────────────
    history_triggers = ["my orders", "order history", "show orders", "list orders",
                        "all my orders", "past orders", "previous orders",
                        "show bookings", "my bookings", "booking history",
                        "get the history", "get history", "show history",
                        "view history", "my history", "show my history",
                        "get my history", "show all", "list all"]
    if any(t in msg for t in history_triggers):
        return "order_history"

    status_triggers = ["check my order", "track my order", "where is my order",
                       "order status", "check order status", "track order",
                       "whats my order", "what's my order", "order update",
                       "check the order", "status of my order"]
    if any(t in msg for t in status_triggers):
        return "order_status"

    if re.search(r'ORD-[A-Z0-9]{4,}', message.upper()):
        return "order_status"

    return None


def route_message(message: str, conversation_history: list) -> str:
    # 1. Hard keyword routing first
    hard_route = _keyword_route(message)
    if hard_route:
        return hard_route

    msg_lower = message.lower().strip()
    is_confirm = msg_lower in CONFIRM_WORDS or any(msg_lower.startswith(w) for w in CONFIRM_WORDS)

    if is_confirm and conversation_history:
        # PRIORITY 1: pending cancellation → always go to order_cancel
        if _has_pending_cancel(conversation_history):
            return "order_cancel"

        # PRIORITY 2: pending food order → go to food_order
        if _has_pending_food_order(conversation_history):
            return "food_order"

        # PRIORITY 3: pending hotel booking → go to hotel_booking
        if _has_pending_hotel_booking(conversation_history):
            return "hotel_booking"

    # 2. LLM fallback
    history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
    messages = history + [{"role": "user", "content": message}]
    agent = chat_completion_fast(messages, COORDINATOR_SYSTEM_PROMPT, temperature=0.0)
    agent = agent.strip().lower().replace('"', '').replace("'", "").split()[0]

    return agent if agent in VALID_AGENTS else "clarification"