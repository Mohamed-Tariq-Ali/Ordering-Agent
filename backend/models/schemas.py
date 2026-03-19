from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class Message(BaseModel):
    role: str
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total_price: float


class Order(BaseModel):
    order_id: str = Field(default_factory=lambda: f"ORD-{str(uuid.uuid4())[:8].upper()}")
    customer_name: Optional[str] = None
    items: List[OrderItem] = []
    total_amount: float = 0.0
    status: str = "pending"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    notes: Optional[str] = None


class HotelBooking(BaseModel):
    booking_id: str = Field(default_factory=lambda: f"BKG-{str(uuid.uuid4())[:8].upper()}")
    hotel_name: str
    hotel_address: Optional[str] = None
    check_in: str
    check_out: str
    guests: int = 1
    rooms: int = 1
    room_type: str = "Standard"
    total_nights: int = 1
    estimated_price: Optional[float] = None
    status: str = "confirmed"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    notes: Optional[str] = None


class LocationData(BaseModel):
    lat: float
    lng: float
    address: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    session_id: str
    conversation_history: List[dict] = []
    location: Optional[dict] = None
    selected_restaurant: Optional[dict] = None
    selected_hotel: Optional[dict] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    order: Optional[dict] = None
    agent_used: str = ""
    hotels: Optional[List[dict]] = None
    restaurants: Optional[List[dict]] = None
    location: Optional[dict] = None
    map_embed_url: Optional[str] = None
    orders_list: Optional[List[dict]] = None
    hotel_booking: Optional[dict] = None
    hotel_bookings_list: Optional[List[dict]] = None
    