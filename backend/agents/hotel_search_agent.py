from backend.utils.llm import chat_completion
from backend.utils.maps import search_nearby_hotels, get_directions_url, geocode_address

HOTEL_SEARCH_SYSTEM_PROMPT = """You are a helpful hotel search agent.
Present ONLY the hotels listed below. Do NOT invent any hotels.
For each hotel show whatever info is available — skip fields that are N/A.
End by offering directions or more info.

Hotels found near {address}:
{hotels}
"""

NO_RESULTS_PROMPT = """You are a helpful hotel search agent.
OpenStreetMap has limited hotel data for this area: {address}
Tell the user honestly that our map database has limited data for this area.
Then tell them you've prepared search links for them to find hotels.
Be helpful and warm. Do NOT make up any hotel names.
"""

NO_LOCATION_PROMPT = """You are a hotel search assistant.
The user wants to search for hotels but hasn't shared their location yet.
Ask them to click the 📍 location button or type a city/area like "hotels in Guindy".
"""


def _build_google_hotel_url(area: str) -> str:
    query = area.replace(" ", "+").replace(",", "")
    return f"https://www.google.com/search?q=hotels+in+{query}"


def _build_makemytrip_url(area: str) -> str:
    city = area.split(",")[0].strip().replace(" ", "-").lower()
    return f"https://www.makemytrip.com/hotels/{city}-hotels.html"


def _build_booking_url(area: str) -> str:
    query = area.split(",")[0].strip().replace(" ", "+").lower()
    return f"https://www.booking.com/search.html?ss={query}"


async def handle_hotel_search(message: str, conversation_history: list,
                               user_location: dict | None) -> tuple[str, list]:

    # Step 1: Check if user mentioned a specific city/area
    search_location = None
    search_address = ""
    raw_area = ""

    location_keywords = ["in ", "near ", "around ", "at ", "for "]
    message_lower = message.lower()
    for kw in location_keywords:
        if kw in message_lower:
            idx = message_lower.index(kw) + len(kw)
            candidate = message[idx:].strip().rstrip("?.,!")
            if candidate and len(candidate) > 2:
                raw_area = candidate
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
            reply = chat_completion(messages, NO_LOCATION_PROMPT, temperature=0.4)
            return reply, []
        search_location = user_location
        search_address = user_location.get("address", "your location")
        raw_area = search_address.split(",")[0].strip()

    lat = search_location["lat"]
    lng = search_location["lng"]

    # Step 3: Fetch hotels from OSM
    hotels = await search_nearby_hotels(lat, lng, radius=5000)

    # Step 4: If OSM returns nothing — give dynamic booking links
    if not hotels:
        # Use full formatted address for context — fully dynamic, no hardcoded city
        context = search_address if search_address else raw_area
        area_label = raw_area if raw_area else search_address.split(",")[0].strip()

        google_url     = _build_google_hotel_url(context)
        makemytrip_url = _build_makemytrip_url(context)
        booking_url    = _build_booking_url(context)

        reply = (
            f"Our map database has limited hotel data for **{area_label}**. "
            f"Here are direct links to find hotels there:\n\n"
            f"🔍 [Search on Google]({google_url})\n"
            f"🏨 [MakeMyTrip]({makemytrip_url})\n"
            f"🌐 [Booking.com]({booking_url})\n\n"
            f"Would you like me to search a nearby area instead? "
            f"Try **Anna Nagar**, **T Nagar**, or **Nungambakkam**."
        )
        return reply, []

    # Step 5: Enrich addresses for hotels showing "Nearby"
    origin_lat = user_location["lat"] if user_location else lat
    origin_lng = user_location["lng"] if user_location else lng

    for hotel in hotels:
        hotel["directions_url"] = get_directions_url(
            origin_lat, origin_lng, hotel["lat"], hotel["lng"]
        )
        hotel["google_search_url"] = (
            f"https://www.google.com/search?q="
            f"{hotel['name'].replace(' ', '+')}+hotel"
        )
        if not hotel["address"] or hotel["address"] == "Nearby":
            from backend.utils.maps import reverse_geocode
            addr = await reverse_geocode(hotel["lat"], hotel["lng"])
            if addr:
                parts = addr.split(",")
                hotel["address"] = ", ".join(parts[:3]).strip()

    # Step 6: Build text from real data only
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

    history = conversation_history[-4:]
    messages = history + [{"role": "user", "content": message}]
    system = HOTEL_SEARCH_SYSTEM_PROMPT.format(
        hotels=hotels_text,
        address=search_address
    )
    reply = chat_completion(messages, system, temperature=0.3)
    return reply, hotels