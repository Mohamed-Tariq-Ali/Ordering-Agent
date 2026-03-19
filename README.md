# 🤖 Order Booking Multi-Agent System

A conversational multi-agent order booking system powered by **Groq (LLaMA 3)** with a **FastAPI** backend and a clean chat UI.

---

## 🏗️ Architecture

```
User Message
     │
     ▼
┌─────────────────────┐
│  Coordinator Agent  │  ← Routes to the right specialist
└─────────┬───────────┘
          │
    ┌─────┴──────┐
    │  Routes to │
    ▼            ▼
┌──────────┐  ┌───────────────┐  ┌───────────────┐  ┌──────────────┐  ┌──────────┐
│ Product  │  │ Order Booking │  │ Order Status  │  │ Order Cancel │  │ Greeting │
│  Search  │  │    Agent      │  │    Agent      │  │    Agent     │  │  Agent   │
└──────────┘  └───────────────┘  └───────────────┘  └──────────────┘  └──────────┘
```

**Agents:**
- **Coordinator** — Understands the user's intent and routes to the correct specialist
- **Product Search Agent** — Handles product browsing, price checks, catalog queries
- **Order Booking Agent** — Extracts order details, validates against catalog, creates & saves order
- **Order Status Agent** — Looks up existing orders by Order ID
- **Order Cancel Agent** — Cancels orders conversationally
- **Greeting Agent** — Handles small talk and onboarding

---

## 📁 Project Structure

```
order-booking-agent/
├── main.py                          # FastAPI app entry point
├── requirements.txt
├── .env.example                     # Copy to .env and fill in your key
│
├── backend/
│   ├── agents/
│   │   ├── coordinator.py           # Routes messages to specialist agents
│   │   ├── order_booking_agent.py   # Places and confirms orders
│   │   ├── order_status_agent.py    # Tracks & cancels orders
│   │   ├── product_search_agent.py  # Product catalog search
│   │   └── greeting_agent.py        # Small talk handler
│   │
│   ├── models/
│   │   └── schemas.py               # Pydantic models (Order, OrderItem, etc.)
│   │
│   ├── routers/
│   │   └── chat.py                  # POST /api/chat endpoint
│   │
│   └── utils/
│       ├── llm.py                   # Groq client wrapper
│       ├── catalog.py               # Product catalog + search
│       └── order_store.py           # In-memory order storage
│
└── frontend/
    ├── templates/
    │   └── index.html               # Jinja2 HTML template
    └── static/
        ├── css/style.css            # Dark theme chat UI
        └── js/app.js                # Chat logic & API calls
```

---

## 🚀 Setup & Run

### 1. Clone / extract the project
```bash
cd order-booking-agent
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up your environment variables
```bash
cp .env.example .env
```
Open `.env` and paste your **Groq API key**:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
```
> Get a free Groq API key at: https://console.groq.com

### 5. Run the server
```bash
uvicorn main:app --reload --port 8000
```

### 6. Open the app
Visit: **http://localhost:8000**

---

## 💬 Example Conversations

| You say | Agent handles it |
|---|---|
| `"Book 2 units of Choco"` | order_booking |
| `"I want 3 cookies and 1 juice"` | order_booking |
| `"What products do you have?"` | product_search |
| `"How much does chips cost?"` | product_search |
| `"Show me my order ORD-ABC12345"` | order_status |
| `"Cancel order ORD-ABC12345"` | order_cancel |
| `"Hello!"` | greeting |

---

## 🔧 Customization

### Add / change products
Edit `backend/utils/catalog.py` — the `PRODUCT_CATALOG` dict.

### Use a real database
Replace functions in `backend/utils/order_store.py` with your DB calls (SQLAlchemy, MongoDB, etc.)

### Change the LLM model
In `backend/utils/llm.py`, change the `model` parameter:
- `llama3-70b-8192` (default, best quality)
- `llama3-8b-8192` (faster, lighter)
- `mixtral-8x7b-32768` (large context)

---

## 📡 API Endpoints

| Method | URL | Description |
|---|---|---|
| `GET` | `/` | Chat UI |
| `POST` | `/api/chat` | Send a message, get agent reply |
| `GET` | `/api/health` | Health check |

### POST /api/chat
**Request:**
```json
{
  "message": "Book 2 units of Choco",
  "session_id": "sess_abc123",
  "conversation_history": []
}
```
**Response:**
```json
{
  "reply": "Your order has been confirmed! ...",
  "session_id": "sess_abc123",
  "order": { "order_id": "ORD-ABC12345", ... },
  "agent_used": "order_booking"
}
```

---

## 🛠️ Tech Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI + Uvicorn |
| LLM | Groq API (LLaMA 3 70B) |
| Frontend | Vanilla HTML/CSS/JS |
| Templating | Jinja2 |
| Data models | Pydantic v2 |
| Storage | In-memory (swap with any DB) |
