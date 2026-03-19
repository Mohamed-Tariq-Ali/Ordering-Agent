import json
import re
from datetime import datetime, timedelta
from backend.utils.llm import chat_completion
from backend.utils.database import get_connection, init_db
from backend.models.schemas import HotelBooking

init_db()

BOOKING_EXTRACT_PROMPT = """You are extracting hotel booking details from user message.

User message: {message}
Hotel: {hotel_name}

Extract booking details and respond ONLY with valid JSON:
{{
  "check_in": "2024-12-25",
  "check_out": "2024-12-27",
  "guests": 2,
  "rooms": 1,
  "room_type": "Standard",
  "total_nights": 2,
  "estimated_price_per_night": 3000
}}

Rules:
- Dates must be in YYYY-MM-DD format
- If user says "tonight" use today's date: {today}
- If user says "tomorrow" use: {tomorrow}
- If no check-out mentioned, assume 1 night
- If no guests mentioned, assume 1
- If no room type mentioned, use "Standard"
- estimated_price_per_night: realistic Indian hotel price in rupees
  Standard: 2000-4000, Deluxe: 4000-7000, Suite: 7000-15000
"""

BOOKING_CONFIRM_PROMPT = """You are confirming a hotel room booking.
Be warm, professional and excited. Include:
- Booking ID
- Hotel name and address
- Room type
- Check-in and check-out dates
- Number of nights, guests, rooms
- Estimated total price
- That they should contact the hotel to confirm actual availability

Booking details:
{booking_summary}
"""

BOOKING_CLARIFY_PROMPT = """You are a hotel booking assistant.
The user wants to book a hotel room at {hotel_name} but hasn't provided enough details.
Ask them conversationally for:
- Check-in date
- Check-out date (or number of nights)
- Number of guests
- Room type preference (Standard / Deluxe / Suite)

Be friendly and brief.
"""

NO_HOTEL_PROMPT = """You are a hotel booking assistant.
The user wants to book a hotel room but hasn't selected a hotel yet.
Ask them to first search for hotels using "search hotels in [area]"
and then select one from the results.
Be friendly and helpful.
"""


def save_hotel_booking(booking: HotelBooking) -> HotelBooking:
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO hotel_bookings
        (booking_id, hotel_name, hotel_address, check_in, check_out,
         guests, rooms, room_type, total_nights, estimated_price,
         status, created_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        booking.booking_id, booking.hotel_name, booking.hotel_address,
        booking.check_in, booking.check_out, booking.guests, booking.rooms,
        booking.room_type, booking.total_nights, booking.estimated_price,
        booking.status, booking.created_at, booking.notes
    ))
    conn.commit()
    conn.close()
    return booking


def get_all_hotel_bookings() -> list[HotelBooking]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM hotel_bookings ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [_row_to_booking(row) for row in rows]


def get_hotel_booking(booking_id: str) -> HotelBooking | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM hotel_bookings WHERE booking_id = ?", (booking_id,)
    ).fetchone()
    conn.close()
    return _row_to_booking(row) if row else None


def cancel_hotel_booking(booking_id: str) -> HotelBooking | None:
    conn = get_connection()
    conn.execute(
        "UPDATE hotel_bookings SET status = 'cancelled' WHERE booking_id = ?",
        (booking_id,)
    )
    conn.commit()
    conn.close()
    return get_hotel_booking(booking_id)


def _row_to_booking(row) -> HotelBooking:
    return HotelBooking(
        booking_id=row["booking_id"],
        hotel_name=row["hotel_name"],
        hotel_address=row["hotel_address"],
        check_in=row["check_in"],
        check_out=row["check_out"],
        guests=row["guests"],
        rooms=row["rooms"],
        room_type=row["room_type"],
        total_nights=row["total_nights"],
        estimated_price=row["estimated_price"],
        status=row["status"],
        created_at=row["created_at"],
        notes=row["notes"]
    )


async def handle_hotel_booking(message: str, conversation_history: list,
                                selected_hotel: dict | None) -> tuple[str, dict | None]:
    """Book a hotel room conversationally."""

    # Step 1: No hotel selected yet
    if not selected_hotel:
        history = conversation_history[-4:]
        messages = history + [{"role": "user", "content": message}]
        reply = chat_completion(messages, NO_HOTEL_PROMPT, temperature=0.4)
        return reply, None

    hotel_name = selected_hotel.get("name", "the hotel")
    hotel_address = selected_hotel.get("address", "")

    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # Step 2: Extract booking details via LLM
    extract_prompt = BOOKING_EXTRACT_PROMPT.format(
        message=message,
        hotel_name=hotel_name,
        today=today,
        tomorrow=tomorrow
    )
    raw = chat_completion(
        [{"role": "user", "content": message}],
        extract_prompt,
        temperature=0.1
    )

    extracted = None
    try:
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            extracted = json.loads(json_match.group())
    except Exception:
        extracted = None

    # Step 3: Not enough info — ask for details
    if not extracted or not extracted.get("check_in") or not extracted.get("check_out"):
        clarify_prompt = BOOKING_CLARIFY_PROMPT.format(hotel_name=hotel_name)
        history = conversation_history[-4:]
        messages = history + [{"role": "user", "content": message}]
        reply = chat_completion(messages, clarify_prompt, temperature=0.5)
        return reply, None

    # Step 4: Calculate price
    total_nights = int(extracted.get("total_nights", 1))
    price_per_night = float(extracted.get("estimated_price_per_night", 3000))
    rooms = int(extracted.get("rooms", 1))
    total_price = round(total_nights * price_per_night * rooms, 2)

    # Step 5: Create and save booking
    booking = HotelBooking(
        hotel_name=hotel_name,
        hotel_address=hotel_address,
        check_in=extracted["check_in"],
        check_out=extracted["check_out"],
        guests=int(extracted.get("guests", 1)),
        rooms=rooms,
        room_type=extracted.get("room_type", "Standard"),
        total_nights=total_nights,
        estimated_price=total_price,
        status="confirmed",
        notes=f"Booked via OrderBot"
    )
    save_hotel_booking(booking)

    # Step 6: Generate confirmation
    booking_summary = f"""
Booking ID: {booking.booking_id}
Hotel: {hotel_name}
Address: {hotel_address}
Room Type: {booking.room_type}
Check-in: {booking.check_in}
Check-out: {booking.check_out}
Nights: {booking.total_nights}
Guests: {booking.guests}
Rooms: {booking.rooms}
Estimated Total: ₹{total_price}
Status: Confirmed
Note: Please contact the hotel to confirm actual room availability.
"""
    confirm_messages = [{"role": "user", "content": f"Hotel booked:\n{booking_summary}\nGenerate warm confirmation."}]
    reply = chat_completion(confirm_messages, BOOKING_CONFIRM_PROMPT.format(
        booking_summary=booking_summary
    ), temperature=0.6)

    return reply, booking.model_dump()