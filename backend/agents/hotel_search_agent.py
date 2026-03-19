from backend.utils.llm import chat_completion
from backend.utils.maps import search_nearby_hotels, get_directions_url, geocode_address

HOTEL_SEARCH_SYSTEM_PROMPT = """You are a helpful hotel search agent.
Present ONLY the hotels listed below. Do NOT invent any hotels.
For each hotel show whatever info is available — skip fields that are N/A.
End by offering directions or more info.

Hotels found near {address}:
{hotels}
"""

HOTEL_NO_LOCATION_PROMPT = """You are a hotel search assistant.
The user wants to search for hotels but hasn't shared their location yet.
Ask them to click the 📍 location button or type a city/area name like "hotels in Guindy".
"""

HOTEL_NO_RESULTS_PROMPT = """You are a hotel search assistant.
No hotels were found in OpenStreetMap near: {address}.
Tell the user honestly no results were found and suggest they try a nearby major area.
"""


async def handle_hotel_search(message: str, conversation_history: list,
                               user_location: dict | None) -> tuple[str, list]:

    # Step 1: Check if user mentioned a specific city/area
    search_location = None
    search_address = ""

    location_keywords = ["in ", "near ", "around ", "at ", "for "]
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

    # Step 2: Fall back to GPS
    if not search_location:
        if not user_location:
            history = conversation_history[-4:]
            messages = history + [{"role": "user", "content": message}]
            reply = chat_completion(messages, HOTEL_NO_LOCATION_PROMPT, temperature=0.4)
            return reply, []
        search_location = user_location
        search_address = user_location.get("address", "your location")

    lat = search_location["lat"]
    lng = search_location["lng"]

    # Step 3: Fetch hotels from OSM
    hotels = await search_nearby_hotels(lat, lng, radius=5000)

    if not hotels:
        system = HOTEL_NO_RESULTS_PROMPT.format(address=search_address)
        reply = chat_completion(
            [{"role": "user", "content": message}],
            system, temperature=0.4
        )
        return reply, []

    # Step 4: Enrich each hotel
    origin_lat = user_location["lat"] if user_location else lat
    origin_lng = user_location["lng"] if user_location else lng

    for hotel in hotels:
        # Add directions URL
        hotel["directions_url"] = get_directions_url(
            origin_lat, origin_lng, hotel["lat"], hotel["lng"]
        )

        # Add Google search link so user can look up more info
        hotel["google_search_url"] = (
            f"https://www.google.com/search?q="
            f"{hotel['name'].replace(' ', '+')}+hotel+Chennai"
        )

        # If address is missing, build one from coordinates using reverse geocode
        if not hotel["address"] or hotel["address"] == "Nearby":
            from backend.utils.maps import reverse_geocode
            addr = await reverse_geocode(hotel["lat"], hotel["lng"])
            if addr:
                # Shorten long OSM addresses — take first 2 parts
                parts = addr.split(",")
                hotel["address"] = ", ".join(parts[:3]).strip()
            else:
                hotel["address"] = f"{hotel['lat']:.4f}, {hotel['lng']:.4f}"

    # Step 5: Build clean text — skip N/A fields
    def hotel_line(i, h):
        parts = [f"{i+1}. **{h['name']}**"]
        if h["rating"] and h["rating"] != "N/A":
            parts.append(f"⭐ {h['rating']}")
        if h["price_level"] and h["price_level"] != "N/A":
            parts.append(f"💰 {h['price_level']}")
        if h["type"] and h["type"] != "Hotel":
            parts.append(f"🏨 {h['type']}")
        parts.append(f"📍 {h['address']}")
        if h.get("phone"):
            parts.append(f"📞 {h['phone']}")
        if h.get("website"):
            parts.append(f"🌐 {h['website']}")
        return " | ".join(parts)

    hotels_text = "\n".join([hotel_line(i, h) for i, h in enumerate(hotels)])

    # Step 6: LLM formats the response
    history = conversation_history[-4:]
    messages = history + [{"role": "user", "content": message}]
    system = HOTEL_SEARCH_SYSTEM_PROMPT.format(
        hotels=hotels_text,
        address=search_address
    )
    reply = chat_completion(messages, system, temperature=0.3)

    return reply, hotels