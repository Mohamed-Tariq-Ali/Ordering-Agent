import json
"""
INPUT ROLE 1 — Context (External Knowledge)
Pre-fetches relevant data from DB before the agent runs and injects it into the prompt.
Eliminates hallucination by grounding the LLM in real data.
Supports date-aware filtering: "yesterday", "today", "last week", etc.
"""

from backend.utils.database import get_connection
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

DEFAULT_TZ = "Asia/Kolkata"


# ─── Date range resolver ──────────────────────────────────────────────────────

def _resolve_date_filter(message: str) -> tuple[str | None, str | None]:
    """
    Parse temporal keywords from the message and return (start_date, end_date)
    as ISO date strings (YYYY-MM-DD), or (None, None) if no filter needed.
    """
    tz  = ZoneInfo(DEFAULT_TZ)
    now = datetime.now(tz)
    msg = message.lower()

    if "yesterday" in msg:
        d = (now - timedelta(days=1)).date()
        return str(d), str(d)

    if "today" in msg or "right now" in msg:
        d = now.date()
        return str(d), str(d)

    if "last week" in msg or "past week" in msg:
        end   = (now - timedelta(days=1)).date()
        start = (now - timedelta(days=7)).date()
        return str(start), str(end)

    if "this week" in msg:
        start = (now - timedelta(days=now.weekday())).date()
        end   = now.date()
        return str(start), str(end)

    if "last month" in msg or "past month" in msg:
        end   = (now - timedelta(days=1)).date()
        start = (now - timedelta(days=30)).date()
        return str(start), str(end)

    if "this month" in msg:
        start = now.replace(day=1).date()
        end   = now.date()
        return str(start), str(end)

    return None, None   # no temporal filter — fetch recent


def prefetch_context(message: str, session_id: str, username: str = None) -> dict:
    """
    Inspect the user message, resolve any date filter, and pre-fetch
    relevant DB records scoped to the logged-in user.
    """
    context   = {}
    msg_lower = message.lower()

    needs_orders = any(k in msg_lower for k in [
        "order", "cancel", "status", "history", "last order",
        "my order", "purchased", "bought", "yesterday", "today",
        "last week", "this week", "last month", "this month"
    ])
    needs_bookings = any(k in msg_lower for k in [
        "hotel", "booking", "reservation", "room", "stay",
        "check-in", "check-out", "cancel", "yesterday", "today",
        "last week", "this week", "last month", "this month"
    ])

    start_date, end_date = _resolve_date_filter(message)

    if needs_orders:
        context["recent_orders"] = _fetch_orders(start_date, end_date, username=username)
        context["date_filter"]   = {"start": start_date, "end": end_date}

    if needs_bookings:
        context["recent_bookings"] = _fetch_bookings(start_date, end_date, username=username)

    return context


def _fetch_orders(start_date: str | None, end_date: str | None, limit: int = 20, username: str = None) -> list[dict]:
    """Fetch orders scoped to username with optional date filter."""
    try:
        conn = get_connection()
        if start_date and end_date:
            rows = conn.execute(
                """
                SELECT order_id, customer_name, items, total_amount, status, created_at
                FROM orders
                WHERE date(created_at) BETWEEN ? AND ?
                AND (username = ? OR (? IS NULL AND username IS NULL))
                ORDER BY created_at DESC LIMIT ?
                """,
                (start_date, end_date, username, username, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT order_id, customer_name, items, total_amount, status, created_at
                FROM orders
                WHERE (username = ? OR (? IS NULL AND username IS NULL))
                ORDER BY created_at DESC LIMIT ?
                """,
                (username, username, limit)
            ).fetchall()
        conn.close()
        result = []
        for row in rows:
            r = dict(row)
            # items is stored as JSON string in SQLite — parse it back to a list
            if isinstance(r.get("items"), str):
                try:
                    r["items"] = json.loads(r["items"])
                except Exception:
                    r["items"] = []
            result.append(r)
        return result
    except Exception:
        return []


def _fetch_bookings(start_date: str | None, end_date: str | None, limit: int = 20, username: str = None) -> list[dict]:
    """Fetch hotel bookings scoped to username with optional date filter."""
    try:
        conn = get_connection()
        if start_date and end_date:
            rows = conn.execute(
                """
                SELECT booking_id, hotel_name, check_in, check_out,
                       room_type, status, created_at
                FROM hotel_bookings
                WHERE date(created_at) BETWEEN ? AND ?
                AND (username = ? OR (? IS NULL AND username IS NULL))
                ORDER BY created_at DESC LIMIT ?
                """,
                (start_date, end_date, username, username, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT booking_id, hotel_name, check_in, check_out,
                       room_type, status, created_at
                FROM hotel_bookings
                WHERE (username = ? OR (? IS NULL AND username IS NULL))
                ORDER BY created_at DESC LIMIT ?
                """,
                (username, username, limit)
            ).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception:
        return []


def format_context_for_prompt(context: dict) -> str:
    """
    Convert the pre-fetched context dict into a clean string
    ready to be prepended to any system prompt.
    """
    if not context:
        return ""

    date_filter = context.get("date_filter", {})
    start       = date_filter.get("start")
    end         = date_filter.get("end")
    date_label  = f" (filtered: {start} → {end})" if start else " (recent)"

    lines = [f"=== PRE-FETCHED CONTEXT — real DB data{date_label} ==="]

    orders = context.get("recent_orders", [])
    if orders:
        lines.append(f"\nOrders{date_label} [{len(orders)} found]:")
        for o in orders:
            lines.append(
                f"  • {o['order_id']} | {o['status']} | "
                f"₹{o['total_amount']} | {o['created_at'][:10]}"
            )
    else:
        if start:
            lines.append(f"\nOrders: none found between {start} and {end}.")

    bookings = context.get("recent_bookings", [])
    if bookings:
        lines.append(f"\nHotel Bookings{date_label} [{len(bookings)} found]:")
        for b in bookings:
            lines.append(
                f"  • {b['booking_id']} | {b['hotel_name']} | "
                f"{b['check_in']} → {b['check_out']} | {b['status']}"
            )
    else:
        if start and context.get("recent_bookings") is not None:
            lines.append(f"\nHotel Bookings: none found between {start} and {end}.")

    lines.append("=== END CONTEXT — do not fabricate any IDs or amounts ===\n")
    return "\n".join(lines)