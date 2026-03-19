from fastapi import APIRouter
from backend.models.schemas import ChatRequest, ChatResponse
from backend.agents.coordinator import route_message
from backend.agents.product_search_agent import handle_product_search
from backend.agents.order_booking_agent import handle_order_booking
from backend.agents.order_status_agent import handle_order_status, handle_order_cancel, handle_order_history
from backend.agents.greeting_agent import handle_greeting
from backend.agents.location_agent import handle_location
from backend.agents.hotel_search_agent import handle_hotel_search
from backend.agents.food_delivery_agent import handle_food_search, handle_food_order
from backend.utils.maps import get_maps_embed_url
from backend.utils.llm import chat_completion
from backend.utils.order_store import get_all_orders

router = APIRouter(prefix="/api", tags=["chat"])

FALLBACK_SYSTEM = """You are a helpful smart assistant. You can help with:
- Browsing and ordering products
- Finding nearby restaurants and ordering food for delivery
- Searching for hotels nearby
- Tracking and cancelling orders
- Showing order history
Suggest what you can do for the user.
"""


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    message = request.message.strip()
    history = request.conversation_history
    session_id = request.session_id
    user_location = request.location
    selected_restaurant = request.selected_restaurant

    agent_name = route_message(message, history)

    reply = ""
    order_data = None
    orders_list = None
    hotels = None
    restaurants = None
    location_data = None
    map_embed_url = None

    if agent_name == "product_search":
        reply = handle_product_search(message, history)

    elif agent_name == "order_booking":
        reply, order_data = handle_order_booking(message, history)

    elif agent_name == "order_status":
        reply = handle_order_status(message, history)

    elif agent_name == "order_history":
        reply, orders_list = handle_order_history()

    elif agent_name == "order_cancel":
        reply = handle_order_cancel(message, history)

    elif agent_name == "hotel_search":
        reply, hotels = await handle_hotel_search(message, history, user_location)
        if user_location:
            map_embed_url = get_maps_embed_url(user_location["lat"], user_location["lng"], zoom=14)

    elif agent_name == "food_search":
        reply, restaurants = await handle_food_search(message, history, user_location)
        if user_location:
            map_embed_url = get_maps_embed_url(user_location["lat"], user_location["lng"], zoom=15)

    elif agent_name == "food_order":
        reply, order_data = await handle_food_order(message, history, user_location, selected_restaurant)

    elif agent_name == "greeting":
        reply = handle_greeting(message, history)

    else:
        messages = history[-6:] + [{"role": "user", "content": message}]
        reply = chat_completion(messages, FALLBACK_SYSTEM, temperature=0.5)

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        order=order_data,
        agent_used=agent_name,
        hotels=hotels if hotels else None,
        restaurants=restaurants if restaurants else None,
        location=location_data,
        map_embed_url=map_embed_url,
        orders_list=orders_list
    )


@router.post("/location", response_model=dict)
async def update_location(lat: float, lng: float, session_id: str):
    result = await handle_location(lat, lng, [])
    return result


@router.get("/orders", response_model=list)
async def get_orders():
    """Return all orders — used by the sidebar history panel."""
    orders = get_all_orders()
    return [o.model_dump() for o in orders]


@router.get("/health")
async def health():
    return {"status": "ok", "message": "Multi-Agent System running"}