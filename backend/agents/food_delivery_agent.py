import json
import re
from backend.utils.llm import chat_completion
from backend.utils.maps import (
    search_nearby_restaurants, get_distance_and_eta,
    get_directions_url, geocode_address
)
from backend.utils.order_store import save_order
from backend.models.schemas import Order, OrderItem
import uuid

RESTAURANT_SEARCH_SYSTEM = """You are a friendly food delivery agent.
You have found REAL restaurants from OpenStreetMap near the user.
Present ONLY the restaurants listed below — do NOT invent or add any restaurants not in this list.
If the list is empty, say no restaurants were found.

For each mention: name, cuisine, address, distance and ETA.
Ask what they'd like to order or which restaurant they prefer.

Restaurants found near {address}:
{restaurants}
"""

NO_LOCATION_PROMPT = """You are a food delivery agent.
The user wants to order food but hasn't shared their location yet.
Ask them to click the 📍 location button so you can find real restaurants nearby,
or ask them to mention a specific area or city name.
"""

ORDER_EXTRACT_PROMPT = """You are extracting a food delivery order from user message.
The user picked a restaurant and wants to order food.

Restaurant: {restaurant_name}
User message: {message}

Extract and respond ONLY with valid JSON:
{{
  "items": [
    {{"item_name": "Biryani", "quantity": 2, "estimated_price": 150}},
    {{"item_name": "Pepsi", "quantity": 1, "estimated_price": 40}}
  ],
  "special_instructions": "extra spicy" or null
}}

If nothing specific mentioned, suggest popular items like Biryani, Pizza, Burger.
Use realistic Indian food prices in rupees.
"""

DELIVERY_CONFIRM_SYSTEM = """You are confirming a food delivery order.
Be warm, excited, and give a clear summary including:
- What was ordered and from which restaurant
- Estimated delivery time
- Delivery distance
- Order total (estimated)
- Order ID

Keep it brief and friendly. Use emojis.
"""


def _recover_restaurant_from_history(conversation_history: list) -> dict | None:
    """Scan recent conversation to recover selected restaurant name if lost from frontend state."""
    patterns = [
        r'restaurant selected[:\s*]+([^\n*.<>]+)',
        r'you selected\s+\*{0,2}([^\n*.<>]+?)\*{0,2}[.\n]',
        r'ordering from\s+\*{0,2}([^\n*.<>]+?)\*{0,2}',
        r'order from\s+\*{0,2}([^\n*.<>]+?)\*{0,2}',
        r'great choice.*?you selected\s+\*{0,2}([^\n*.<>]+?)\*{0,2}',
    ]
    for msg in reversed(conversation_history[-12:]):
        content = msg.get("content", "")
        for pattern in patterns:
            m = re.search(pattern, content, re.IGNORECASE)
            if m:
                name = m.group(1).strip().rstrip(".,!?")
                if name:
                    return {"name": name}
    return None


async def handle_food_search(message: str, conversation_history: list,
                              user_location: dict | None) -> tuple[str, list]:
    """Search for nearby restaurants."""

    # Step 1: Check if user mentioned a specific city/area in message
    search_location = None
    search_address = ""

    location_keywords = ["in ", "near ", "around ", "at "]
    message_lower = message.lower()
    for kw in location_keywords:
        if kw in message_lower:
            idx = message_lower.index(kw) + len(kw)
            candidate = message[idx:].strip().rstrip("?.,!")
            if candidate and len(candidate) > 2:
                geocoded = await geocode_address(candidate + ", India")
                if geocoded:
                    search_location = geocoded
                    search_address = geocoded["formatted_address"]
                    break

    # Step 2: Fall back to GPS location
    if not search_location:
        if not user_location:
            history = conversation_history[-4:]
            messages = history + [{"role": "user", "content": message}]
            reply = chat_completion(messages, NO_LOCATION_PROMPT, temperature=0.4)
            return reply, []
        search_location = user_location
        search_address = user_location.get("address", "your location")

    lat = search_location["lat"]
    lng = search_location["lng"]

    # Step 3: Extract cuisine keyword from message if any
    cuisine_keywords = ["pizza", "burger", "biryani", "chinese", "south indian",
                        "north indian", "italian", "fast food", "cafe", "bakery",
                        "seafood", "vegetarian", "vegan", "continental"]
    query = "restaurant"
    for kw in cuisine_keywords:
        if kw in message.lower():
            query = kw
            break

    # Step 4: Fetch real restaurants from OSM
    restaurants = await search_nearby_restaurants(lat, lng, query=query, radius=3000)

    if not restaurants:
        return f"No restaurants found near **{search_address}**. Try a different area or cuisine type. 🍽️", []

    # Step 5: Get distance/ETA from user's actual GPS (or search location)
    origin_lat = user_location["lat"] if user_location else lat
    origin_lng = user_location["lng"] if user_location else lng

    for r in restaurants:
        distance_info = await get_distance_and_eta(origin_lat, origin_lng, r["lat"], r["lng"])
        if distance_info:
            r["distance"] = distance_info["distance"]
            r["eta"] = distance_info["duration"]
        else:
            r["distance"] = "N/A"
            r["eta"] = "N/A"
        r["directions_url"] = get_directions_url(origin_lat, origin_lng, r["lat"], r["lng"])

    # Step 6: Build text from REAL data only and force LLM to use it
    restaurants_text = "\n".join([
        f"{i+1}. {r['name']} | Cuisine: {r.get('cuisine','N/A')} | "
        f"Address: {r['address']} | "
        f"Distance: {r.get('distance','N/A')} | ETA: {r.get('eta','N/A')}"
        for i, r in enumerate(restaurants)
    ])

    strict_system = RESTAURANT_SEARCH_SYSTEM.format(
        restaurants=restaurants_text,
        address=search_address
    ) + "\n\nIMPORTANT: Only mention restaurants listed above. Do NOT invent or add any restaurants."

    history = conversation_history[-4:]
    messages = history + [{"role": "user", "content": message}]
    reply = chat_completion(messages, strict_system, temperature=0.3)

    return reply, restaurants


async def handle_food_order(message: str, conversation_history: list,
                             user_location: dict | None,
                             selected_restaurant: dict | None,
                             username: str | None = None) -> tuple[str, dict | None]:
    """Place a food order from a selected restaurant."""
    if not user_location:
        return "Please share your location first using the 📍 button so I can confirm delivery! 😊", None

    # If selected_restaurant lost from frontend state, recover from conversation history
    if not selected_restaurant:
        selected_restaurant = _recover_restaurant_from_history(conversation_history)
    if not selected_restaurant:
        return "Please tell me which restaurant you'd like to order from first! 🍽️", None

    restaurant_name = selected_restaurant.get("name", "the restaurant")

    # Extract order items via LLM
    extract_prompt = ORDER_EXTRACT_PROMPT.format(
        restaurant_name=restaurant_name,
        message=message
    )
    raw = chat_completion([{"role": "user", "content": message}], extract_prompt, temperature=0.2)

    extracted = None
    try:
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            extracted = json.loads(json_match.group())
    except Exception:
        extracted = None

    if not extracted or not extracted.get("items"):
        return f"What would you like to order from **{restaurant_name}**? Please tell me the items! 🍽️", None

    # Build order items
    order_items = []
    for item in extracted["items"]:
        price = float(item.get("estimated_price", 100))
        qty = int(item.get("quantity", 1))
        order_items.append(OrderItem(
            product_id=f"FOOD-{str(uuid.uuid4())[:6].upper()}",
            product_name=item["item_name"],
            quantity=qty,
            unit_price=price,
            total_price=round(price * qty, 2)
        ))

    total = round(sum(i.total_price for i in order_items), 2)
    delivery_fee = 30.0
    grand_total = round(total + delivery_fee, 2)

    # Get delivery ETA
    eta_info = None
    if user_location and selected_restaurant.get("lat"):
        eta_info = await get_distance_and_eta(
            user_location["lat"], user_location["lng"],
            selected_restaurant["lat"], selected_restaurant["lng"]
        )

    # Save order — scoped to logged-in user
    order = Order(
        customer_name=username,
        items=order_items,
        total_amount=grand_total,
        status="confirmed",
        notes=f"Delivery from {restaurant_name} | {extracted.get('special_instructions', '')}"
    )
    save_order(order, username=username)

    # Generate confirmation message
    items_text = "\n".join([f"  - {i.product_name} x{i.quantity} = Rs.{i.total_price}" for i in order_items])
    summary = f"""
Order ID: {order.order_id}
Restaurant: {restaurant_name}
Items:
{items_text}
Subtotal: Rs.{total}
Delivery fee: Rs.{delivery_fee}
Grand Total: Rs.{grand_total}
Delivery Distance: {eta_info['distance'] if eta_info else 'N/A'}
Estimated Delivery Time: {eta_info['duration'] if eta_info else '30-45 mins'}
Delivery Address: {user_location.get('address', 'Your location')}
"""
    confirm_messages = [{"role": "user", "content": f"Food order placed:\n{summary}\nGenerate a warm confirmation."}]
    reply = chat_completion(confirm_messages, DELIVERY_CONFIRM_SYSTEM, temperature=0.6)

    order_data = order.model_dump()
    order_data["restaurant"] = restaurant_name
    order_data["delivery_address"] = user_location.get("address")
    order_data["eta"] = eta_info["duration"] if eta_info else "30-45 mins"
    order_data["distance"] = eta_info["distance"] if eta_info else "N/A"
    order_data["grand_total"] = grand_total

    return reply, order_data