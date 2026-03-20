from fastapi import FastAPI, Cookie, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional
from backend.routers.chat import router as chat_router
from backend.routers.auth import router as auth_router
from backend.utils.auth import decode_token

app = FastAPI(
    title="Order Booking Multi-Agent",
    description="A conversational multi-agent system for order booking powered by Groq",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

app.include_router(chat_router)
app.include_router(auth_router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, auth_token: Optional[str] = Cookie(default=None)):
    # Guard: redirect to login if not authenticated
    if not auth_token or not decode_token(auth_token):
        return RedirectResponse(url="/login", status_code=302)
    payload  = decode_token(auth_token)
    username = payload.get("sub", "User")
    return templates.TemplateResponse("index.html", {"request": request, "username": username})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, auth_token: Optional[str] = Cookie(default=None)):
    # Already logged in → go straight to chat
    if auth_token and decode_token(auth_token):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("auth.html", {"request": request})