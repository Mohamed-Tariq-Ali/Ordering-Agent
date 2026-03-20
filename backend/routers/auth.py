from fastapi import APIRouter, HTTPException, Response, Cookie
from pydantic import BaseModel
from typing import Optional
from backend.utils.database import get_connection, init_db
from backend.utils.auth import hash_password, verify_password, create_token, decode_token

router = APIRouter(prefix="/auth", tags=["auth"])

init_db()


# ── Schemas ───────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    success: bool
    message: str
    username: Optional[str] = None


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_user(username: str) -> dict | None:
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(username: str, email: str, hashed_pw: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (username, email, hashed_pw)
    )
    conn.commit()
    conn.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=AuthResponse)
async def signup(body: SignupRequest, response: Response):
    if len(body.username) < 3:
        raise HTTPException(400, "Username must be at least 3 characters.")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")
    if get_user(body.username):
        raise HTTPException(400, "Username already taken.")

    create_user(body.username, body.email, hash_password(body.password))
    token = create_token({"sub": body.username})
    response.set_cookie(
        key="auth_token", value=token,
        httponly=True, max_age=86400, samesite="lax"
    )
    return AuthResponse(success=True, message="Account created!", username=body.username)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, response: Response):
    user = get_user(body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid username or password.")

    token = create_token({"sub": body.username})
    response.set_cookie(
        key="auth_token", value=token,
        httponly=True, max_age=86400, samesite="lax"
    )
    return AuthResponse(success=True, message="Welcome back!", username=body.username)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("auth_token")
    return {"success": True}


@router.get("/me", response_model=AuthResponse)
async def me(auth_token: Optional[str] = Cookie(default=None)):
    if not auth_token:
        raise HTTPException(401, "Not authenticated.")
    payload = decode_token(auth_token)
    if not payload:
        raise HTTPException(401, "Session expired.")
    return AuthResponse(success=True, message="ok", username=payload.get("sub"))