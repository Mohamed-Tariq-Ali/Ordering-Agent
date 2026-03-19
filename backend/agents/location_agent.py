from backend.utils.llm import chat_completion
from backend.utils.maps import reverse_geocode

LOCATION_SYSTEM_PROMPT = """You are a friendly location assistant.
The user has just shared their GPS coordinates and you have their address.
Acknowledge their location warmly and let them know what you can help with:
- Search for nearby restaurants and order food for delivery
- Search for hotels nearby
- Track delivery to their location

Be brief, friendly, and helpful.
"""


async def handle_location(lat: float, lng: float, conversation_history: list) -> dict:
    """Process user's location and return address + friendly message."""
    address = await reverse_geocode(lat, lng)
    if not address:
        address = f"coordinates ({lat:.4f}, {lng:.4f})"

    messages = conversation_history[-4:] + [{
        "role": "user",
        "content": f"My location is: {address} (lat: {lat}, lng: {lng})"
    }]
    reply = chat_completion(messages, LOCATION_SYSTEM_PROMPT, temperature=0.5)

    return {
        "reply": reply,
        "lat": lat,
        "lng": lng,
        "address": address
    }
