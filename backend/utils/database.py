import sqlite3

DB_PATH = "orders.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id      TEXT PRIMARY KEY,
            customer_name TEXT,
            items         TEXT,
            total_amount  REAL,
            status        TEXT,
            created_at    TEXT,
            notes         TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hotel_bookings (
            booking_id        TEXT PRIMARY KEY,
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
    conn.commit()
    conn.close()