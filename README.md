# 🤖 Multi-Agent Ordering System

A fully conversational multi-agent system for ordering products, booking food delivery, searching & booking hotels — powered by **Groq (LLaMA 3)**, **FastAPI**, and **OpenStreetMap** (free, no card required).

---

## 🏗️ Multi-Agent Architecture

```
User Message
     │
     ▼
┌──────────────────────┐
│   Coordinator Agent  │  ← Understands intent, routes to specialist
└──────────┬───────────┘
           │
     ┌─────┴──────────────────────────────────────────┐
     │                                                 │
     ▼                                                 ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Product Search │   │  Order Booking  │   │  Order Status   │
│     Agent       │   │     Agent       │   │     Agent       │
└─────────────────┘   └─────────────────┘   └─────────────────┘
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Hotel Search   │   │  Hotel Booking  │   │  Food Search    │
│     Agent       │   │     Agent       │   │     Agent       │
└─────────────────┘   └─────────────────┘   └─────────────────┘
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Food Order     │   │  Order Cancel   │   │    Greeting     │
│     Agent       │   │     Agent       │   │     Agent       │
└─────────────────┘   └─────────────────┘   └─────────────────┘
```

### Agents
| Agent | Responsibility |
|---|---|
| **Coordinator** | Routes user message to the right specialist agent |
| **Product Search** | Browse catalog, check prices |
| **Order Booking** | Place product orders, confirm, save to DB |
| **Order Status** | Look up existing orders by ID |
| **Order Cancel** | Cancel orders or hotel bookings — handles multiple active items intelligently |
| **Hotel Search** | Find real hotels via OpenStreetMap, fallback to Google/MakeMyTrip/Booking.com links |
| **Hotel Booking** | Book a hotel room conversationally, saves to DB |
| **Food Search** | Find real nearby restaurants via OpenStreetMap + OSRM for ETA |
| **Food Order** | Place food delivery order from selected restaurant |
| **Greeting** | Small talk, onboarding, help |

---

## 📁 Project Structure

```
order-booking-agent/
├── main.py                              # FastAPI app entry point
├── requirements.txt
├── .env.example                         # Copy to .env, add your Groq key
├── orders.db                            # SQLite database (auto-created)
│
├── backend/
│   ├── agents/
│   │   ├── coordinator.py               # Routes messages to specialist agents
│   │   ├── order_booking_agent.py       # Places and confirms product orders
│   │   ├── order_status_agent.py        # Tracks, cancels orders & bookings
│   │   ├── hotel_search_agent.py        # Finds hotels via OSM + booking links
│   │   ├── hotel_booking_agent.py       # Books hotel rooms conversationally
│   │   ├── food_delivery_agent.py       # Finds restaurants + places food orders
│   │   ├── location_agent.py            # Handles GPS reverse geocoding
│   │   ├── product_search_agent.py      # Product catalog search
│   │   └── greeting_agent.py            # Small talk handler
│   │
│   ├── models/
│   │   └── schemas.py                   # Pydantic models (Order, HotelBooking, etc.)
│   │
│   ├── routers/
│   │   └── chat.py                      # All API endpoints
│   │
│   └── utils/
│       ├── llm.py                       # Groq LLaMA 3 client wrapper
│       ├── maps.py                      # OpenStreetMap + OSRM API calls
│       ├── catalog.py                   # Product catalog
│       ├── database.py                  # SQLite setup
│       └── order_store.py               # Order CRUD operations
│
└── frontend/
    ├── templates/
    │   └── index.html                   # Chat UI
    └── static/
        ├── css/style.css                # Dark theme
        └── js/app.js                    # Chat logic, location, cards
```

---

## 🚀 Setup & Run

### 1. Clone the repository
```bash
git clone https://github.com/Mohamed-Tariq-Ali/Ordering-Agent.git
cd Ordering-Agent
```

### 2. Create virtual environment
```bash
python -m venv venv

# Mac/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
# Mac/Linux
cp .env.example .env

# Windows
copy .env.example .env
```

Open `.env` and add your Groq API key:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
```
> Get a **free** Groq API key at: https://console.groq.com

### 5. Run the server
```bash
uvicorn main:app --reload --port 8000
```

### 6. Open the app
```
http://localhost:8000
```

---

## 🔑 API Keys Required

| Key | Required | Get it from |
|---|---|---|
| `GROQ_API_KEY` | ✅ Yes | https://console.groq.com (free) |
| Google Maps | ❌ No | Uses free OpenStreetMap instead |

---

## 💬 Example Conversations

### Product Ordering
```
"Book 2 units of Choco"
"I want 3 cookies and 1 juice"
"What products do you have?"
"How much does chips cost?"
```

### Food Delivery
```
"Find restaurants near me"              ← uses GPS
"Find restaurants in Guindy"            ← uses area name
"Find pizza places nearby"              ← cuisine filter
"Order 1 Biryani and 2 Pepsi"          ← after selecting restaurant
```

### Hotel Search & Booking
```
"Search hotels in Anna Nagar"
"Search hotels near me"
"Book a room"                           ← after selecting hotel
"Book a Standard room for 2 nights from tomorrow for 2 guests"
"Book a Deluxe room, check in 25th March, check out 27th March"
```

### Order & Booking Management
```
"Show my order ORD-ABC12345"
"Show my order history"
"Cancel my order"                       ← bot asks which one if multiple
"Cancel my hotel booking"               ← cancels hotel booking specifically
"Cancel BKG-XXXXXXXX"                   ← direct cancel by ID
```

---

## 🗺️ Location Features

- Click **📍 Share My Location** in the sidebar — uses browser GPS
- Or mention any area in your message: `"restaurants in T Nagar"`
- Map embed shows automatically after hotel/restaurant search
- Distance and ETA calculated via OSRM routing engine

---

## 📡 API Endpoints

| Method | URL | Description |
|---|---|---|
| `GET` | `/` | Chat UI |
| `POST` | `/api/chat` | Send message, get agent reply |
| `POST` | `/api/location` | Submit GPS coordinates |
| `GET` | `/api/orders` | List all orders |
| `GET` | `/api/hotel-bookings` | List all hotel bookings |
| `GET` | `/api/health` | Health check |

### POST /api/chat — Request
```json
{
  "message": "Book 2 units of Choco",
  "session_id": "sess_abc123",
  "conversation_history": [],
  "location": { "lat": 13.08, "lng": 80.27, "address": "Chennai" },
  "selected_restaurant": null,
  "selected_hotel": null
}
```

### POST /api/chat — Response
```json
{
  "reply": "Your order has been confirmed!",
  "session_id": "sess_abc123",
  "agent_used": "order_booking",
  "order": { "order_id": "ORD-ABC12345", "status": "confirmed" },
  "hotel_booking": null,
  "restaurants": null,
  "hotels": null,
  "orders_list": null,
  "hotel_bookings_list": null,
  "map_embed_url": null
}
```

---

## 🗄️ Database

Uses **SQLite** — built into Python, zero setup needed.

| Table | Stores |
|---|---|
| `orders` | Product orders + food delivery orders |
| `hotel_bookings` | Hotel room bookings |

Database file: `orders.db` in project root.
Open with [DB Browser for SQLite](https://sqlitebrowser.org) to inspect data directly.

**What persists across restarts:**
- ✅ All orders
- ✅ All hotel bookings

**What resets on page refresh:**
- ❌ Conversation history (browser memory)
- ❌ GPS location (re-share each session)

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| LLM | Groq API — LLaMA 3.3 70B Versatile |
| Geocoding | Nominatim (OpenStreetMap) |
| Places Search | Overpass API (OpenStreetMap) |
| Routing / ETA | OSRM (Open Source Routing Machine) |
| Map Display | OpenStreetMap embed |
| Database | SQLite (built-in Python) |
| Frontend | Vanilla HTML + CSS + JS |
| Templating | Jinja2 |
| Data Models | Pydantic v2 |

---

## 🔧 Customization

### Add or change products
Edit `backend/utils/catalog.py` — update the `PRODUCT_CATALOG` dict.

### Change the LLM model
In `backend/utils/llm.py`, change the `model` field:
```python
model="llama-3.3-70b-versatile"   # default — best quality
model="llama-3.1-8b-instant"      # faster, lighter
model="mixtral-8x7b-32768"        # large context window
```

### Switch to a real database
Replace `backend/utils/order_store.py` and `backend/agents/hotel_booking_agent.py`
with SQLAlchemy or any ORM of your choice.

### Change search radius
In `backend/utils/maps.py`:
```python
radius=3000   # restaurants — metres
radius=5000   # hotels — metres
```

---

## 🧪 Cancel Logic — Multi-Agent BTS Flow

```
User: "Cancel my order"
          │
          ▼
    Coordinator → order_cancel
          │
          ▼
    Cancel Agent checks DB:
    ├── 0 active items     → "Nothing active to cancel"
    ├── 1 order only       → Cancels it directly ✅
    ├── 1 booking only     → Cancels it directly ✅
    ├── user says "hotel"  → Only shows hotel bookings
    ├── user says "food"   → Only shows food/product orders
    └── multiple + unclear → Lists everything, asks which one

User: "Cancel the hotel"
          │
          ▼
    Cancel Agent → finds active hotel booking → cancels ✅
    History panel auto-refreshes
```

---

## 📝 License

MIT License — free to use, modify, and distribute.