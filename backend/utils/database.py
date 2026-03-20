import sqlite3

DB_PATH = "orders.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    # ── Orders — now includes username to scope per user ─────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id      TEXT PRIMARY KEY,
            username      TEXT,
            customer_name TEXT,
            items         TEXT,
            total_amount  REAL,
            status        TEXT,
            created_at    TEXT,
            notes         TEXT
        )
    """)

    # ── Hotel bookings — now includes username ────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hotel_bookings (
            booking_id        TEXT PRIMARY KEY,
            username          TEXT,
            hotel_name        TEXT,
            hotel_address     TEXT,
            check_in          TEXT,
            check_out         TEXT,
            guests            INTEGER,
            rooms             INTEGER,
            room_type         TEXT,
            total_nights      INTEGER,
            estimated_price   REAL,
            status            TEXT,
            created_at        TEXT,
            notes             TEXT
        )
    """)

    # ── INPUT ROLE 2 — Long-term Memory ──────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            session_id  TEXT PRIMARY KEY,
            preferences TEXT NOT NULL DEFAULT '{}'
        )
    """)

    # ── INPUT ROLE 5 — Dialogue / Interaction State ───────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dialogue_state (
            session_id TEXT PRIMARY KEY,
            state      TEXT NOT NULL DEFAULT '{}'
        )
    """)

    # ── AUTH — User accounts ──────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            email         TEXT,
            password_hash TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Migration: add username column to existing tables if missing ──────────
    # Safe to run every time — ignored if column already exists
    for migration in [
        "ALTER TABLE orders ADD COLUMN username TEXT",
        "ALTER TABLE hotel_bookings ADD COLUMN username TEXT",
    ]:
        try:
            conn.execute(migration)
        except Exception:
            pass  # column already exists — skip

    conn.commit()
    conn.close()