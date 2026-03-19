import sqlite3
import json
import os
from datetime import datetime

DB_PATH = "orders.db"  # saved in your project root folder


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist — runs on startup."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id    TEXT PRIMARY KEY,
            customer_name TEXT,
            items       TEXT,
            total_amount REAL,
            status      TEXT,
            created_at  TEXT,
            notes       TEXT
        )
    """)
    conn.commit()
    conn.close()