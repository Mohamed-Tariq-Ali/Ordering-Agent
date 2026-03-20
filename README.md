# 🤖 Multi-Agent Ordering System

A fully conversational multi-agent system for ordering products, booking food delivery, searching & booking hotels — powered by Groq (LLaMA 3), FastAPI, and OpenStreetMap (free, no card required).

---

## 🏗️ Multi-Agent Architecture

```
User Message
     │
     ▼
┌──────────────────────┐
│   Coordinator Agent  │  ← Keyword + context-aware routing, LLM fallback
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
| Coordinator | Keyword hard-routing first, context-aware confirmation routing, LLM fallback |
| Product Search | Browse catalog, check prices |
| Order Booking | Place product orders, confirm, save to DB |
| Order Status | Look up existing orders by ID |
| Order Cancel | Cancel orders or hotel bookings — handles "last order", numbered lists, yes/confirm flow |
| Hotel Search | Find real hotels via OpenStreetMap + booking links |
| Hotel Booking | Book a hotel room conversationally, saves to DB |
| Food Search | Find real nearby restaurants via OpenStreetMap + OSRM for ETA |
| Food Order | Place food delivery order, recovers restaurant from history if lost |
| Greeting | Small talk, onboarding, help |

---

## 📁 Project Structure

```
order-booking-agent/
├── main.py                              # FastAPI app entry point
├── requirements.txt
├── .env.example                         # Copy to .env, add your keys
├── orders.db                            # SQLite database (auto-created)
│
├── backend/
│   ├── agents/
│   │   ├── coordinator.py               # Routes messages — keyword + context + LLM
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
│   │   ├── chat.py                      # All API endpoints
│   │   └── auth.py                      # /auth/signup, /auth/login, /auth/logout, /auth/me
│   │
│   └── utils/
│       ├── llm.py                       # Groq client — dual model, auto-fallback, token trimming
│       ├── maps.py                      # OpenStreetMap + OSRM API calls
│       ├── catalog.py                   # Product catalog
│       ├── database.py                  # SQLite setup + auto-migration
│       ├── order_store.py               # Order CRUD operations
│       ├── auth.py                      # JWT + bcrypt password hashing
│       ├── context_prefetch.py          # Role 1 — DB pre-fetch with date filtering
│       ├── memory.py                    # Role 2 — Short + long-term memory
│       ├── runtime_context.py           # Role 3 — Datetime/timezone injection
│       ├── policy.py                    # Role 4 — Guardrails + content filter
│       ├── dialogue_state.py            # Role 5 — Slot-filling state
│       └── agent_bus.py                 # Role 6 — Agent-to-agent message bus
│
└── frontend/
    ├── templates/
    │   ├── index.html                   # Main chat UI with logout button
    │   └── auth.html                    # Login / signup page
    └── static/
        ├── css/style.css                # Dark theme
        └── js/app.js                    # Chat logic, location, cards, logout
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

New packages added for authentication:
```bash
pip install passlib[bcrypt]==1.7.4 python-jose[cryptography]==3.3.0 bcrypt==4.0.1
```

### 4. Set up environment variables
```bash
# Mac/Linux
cp .env.example .env

# Windows
copy .env.example .env
```

Open `.env` and fill in:
```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
SECRET_KEY=any-long-random-string-here
```

- Get a free Groq API key at: https://console.groq.com
- `SECRET_KEY` can be any long random string — used to sign JWT tokens

### 5. Run the server
```bash
uvicorn main:app --reload --port 8000
```

### 6. Open the app
```
http://localhost:8000
```

You'll be redirected to the login page. Create an account and sign in.

---

## 🔐 Authentication

| Feature | Detail |
|---|---|
| Signup | Username + optional email + password (min 6 chars) |
| Login | JWT token stored as httponly cookie (24hr expiry) |
| Logout | Button in topbar — clears cookie, redirects to login |
| Per-user data | All orders and bookings are scoped to logged-in user |
| Security | Passwords hashed with bcrypt, token verified server-side on every request |

- `/` redirects to `/login` if not authenticated
- `/login` redirects to `/` if already logged in
- Username is extracted from JWT cookie server-side — never trusted from client

---

## 🔑 API Keys Required

| Key | Required | Get it from |
|---|---|---|
| `GROQ_API_KEY` | ✅ Yes | https://console.groq.com (free) |
| `SECRET_KEY` | ✅ Yes | Any random string you choose |
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
"Book 4 units of fried rice"           ← also works
"yes proceed"                           ← confirms order
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
"Get the history"
"Cancel my order"                       ← bot asks which one if multiple
"Cancel my last order"                  ← finds most recent, asks confirmation
"Cancel my last hotel booking"          ← finds most recent booking
"Cancel my hotel booking"
"Cancel BKG-XXXXXXXX"                   ← direct cancel by ID
"yes confirm"                           ← confirms cancellation
```

---

## 🗺️ Location Features
- Click 📍 **Share My Location** in the sidebar — uses browser GPS
- Or mention any area: `"restaurants in T Nagar"`
- Map embed shows automatically after hotel/restaurant search
- Distance and ETA calculated via OSRM routing engine

---

## 📡 API Endpoints

| Method | URL | Description |
|---|---|---|
| GET | `/` | Chat UI (requires auth) |
| GET | `/login` | Login/signup page |
| POST | `/auth/signup` | Create account |
| POST | `/auth/login` | Sign in, sets cookie |
| POST | `/auth/logout` | Sign out, clears cookie |
| GET | `/auth/me` | Get current user info |
| POST | `/api/chat` | Send message, get agent reply |
| POST | `/api/location` | Submit GPS coordinates |
| POST | `/api/env` | Send client environment info |
| GET | `/api/memory/{session_id}` | Get session memory/preferences |
| GET | `/api/orders` | List orders for logged-in user |
| GET | `/api/hotel-bookings` | List bookings for logged-in user |
| GET | `/api/health` | Health check |

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
  "map_embed_url": null,
  "input_roles_debug": {}
}
```

---

## 🗄️ Database

Uses SQLite — built into Python, zero setup needed.

| Table | Stores |
|---|---|
| `users` | Usernames, hashed passwords, emails |
| `orders` | Product orders + food delivery orders (scoped by username) |
| `hotel_bookings` | Hotel room bookings (scoped by username) |
| `user_preferences` | Long-term memory per session |
| `dialogue_state` | Slot-filling state per session |

Database file: `orders.db` in project root. Open with **DB Browser for SQLite** to inspect.

**What persists across restarts:**
- ✅ All orders and hotel bookings
- ✅ User accounts
- ✅ Long-term preferences

**What resets on page refresh:**
- ❌ Conversation history (browser memory)
- ❌ GPS location (re-share each session)

---

## ⚡ 6 Input Roles (Context Injection)

Every LLM call is enriched with 6 layers of context:

| Role | File | What it does |
|---|---|---|
| Role 1 — Context | `context_prefetch.py` | Pre-fetches DB records before agent runs; supports date filters ("yesterday", "last week") |
| Role 2 — Memory | `memory.py` | Short-term (last 6 turns) + long-term (cuisine/room preferences) injected into every prompt |
| Role 3 — Runtime | `runtime_context.py` | Current date, time, timezone (Asia/Kolkata), GPS location injected automatically |
| Role 4 — Policy | `policy.py` | Global guardrails prepended to every LLM call; per-agent policy fragments; jailbreak filter |
| Role 5 — Dialogue | `dialogue_state.py` | Slot-filling progress (hotel booking steps, food order steps) persisted in SQLite |
| Role 6 — Agent Bus | `agent_bus.py` | Coordinator sends delegation message to specialist; specialist sends result back |

---

## 🧠 Smart Coordinator Routing

The coordinator uses a 3-layer routing strategy to avoid LLM hallucination:

```
1. Keyword hard-routing   — instant, no LLM needed
   e.g. "book 4 units of fried rice" → food_order
        "search hotels near me"      → hotel_search
        "cancel my last order"       → order_cancel

2. Context-aware routing  — checks last bot message
   e.g. "yes confirm" after cancel prompt  → order_cancel
        "yes proceed" after order summary  → food_order
        "yes" after hotel booking prompt   → hotel_booking

3. LLM fallback           — only when 1 and 2 don't match
   Uses llama-3.1-8b-instant (fast model, 500k TPD)
```

---

## 🔒 Cancel Flow

```
User: "Cancel my last order"
          │
          ▼
    order_cancel agent:
    ├── Sorts active orders by created_at DESC
    ├── Shows most recent with full details + timestamp
    └── Asks: "Is this the one? Reply yes to confirm."

User: "yes confirm"
          │
          ▼
    Coordinator: _has_pending_cancel() → True → order_cancel
          │
          ▼
    Finds ORD-XXXXXX in history → cancels in DB → shows ❌ in history
```

---

## 🚀 Token Optimization (Groq Free Tier)

Two models used to stay within the 100k TPD free limit:

| Model | Used for | TPD limit |
|---|---|---|
| `llama-3.1-8b-instant` | Coordinator routing (needs one word back) | 500k |
| `llama-3.3-70b-versatile` | All agent responses (needs quality) | 100k |

Other savings:
- History trimmed to last 6 turns per request
- System prompts capped at 2500 chars
- `max_tokens` reduced from 1024 → 512
- Auto-fallback to 8b model if 70b hits rate limit

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| LLM | Groq API — LLaMA 3.3 70B + LLaMA 3.1 8B |
| Auth | JWT (python-jose) + bcrypt (passlib) |
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

**Add or change products**
Edit `backend/utils/catalog.py` — update the `PRODUCT_CATALOG` dict.

**Change the LLM model**
In `backend/utils/llm.py`:
```python
FAST_MODEL  = "llama-3.1-8b-instant"      # coordinator routing
SMART_MODEL = "llama-3.3-70b-versatile"   # agent responses
```

**Change search radius**
In `backend/utils/maps.py`:
```python
radius=3000   # restaurants — metres
radius=5000   # hotels — metres
```

---

## 📝 License

MIT License — free to use, modify, and distribute.