"""
INPUT ROLE 2 — Memory (State)

Short-term  : conversation history slice — already exists in history list,
              this module standardises trimming + formatting.
Long-term   : cross-session user preferences persisted in SQLite,
              retrieved on every request and injected into the prompt.
"""

import json
from backend.utils.database import get_connection


# ─── Short-term memory ────────────────────────────────────────────────────────

def get_short_term_memory(conversation_history: list, max_turns: int = 6) -> list[dict]:
    """
    Return the last N turns of the current session.
    This is what gets injected as prior messages in every chat_completion call.
    """
    return conversation_history[-max_turns:] if len(conversation_history) > max_turns \
        else conversation_history


# ─── Long-term memory ─────────────────────────────────────────────────────────

def load_user_preferences(session_id: str) -> dict:
    """
    Retrieve persisted preferences for this session/user from SQLite.
    Returns an empty dict if no preferences exist yet.
    """
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT preferences FROM user_preferences WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row["preferences"])
    except Exception:
        pass
    return {}


def save_user_preferences(session_id: str, updates: dict) -> None:
    """
    Merge `updates` into the existing preferences for this session and persist.
    Example updates: {"preferred_cuisine": "Indian", "last_location": "Chennai"}
    """
    existing = load_user_preferences(session_id)
    existing.update(updates)
    try:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO user_preferences (session_id, preferences)
            VALUES (?, ?)
            ON CONFLICT(session_id) DO UPDATE SET preferences = excluded.preferences
            """,
            (session_id, json.dumps(existing))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def extract_preferences_from_message(message: str, existing_prefs: dict) -> dict:
    """
    Lightweight heuristic to pull preference signals from the user message
    without an extra LLM call. Extend this list as needed.
    """
    updates = {}
    msg_lower = message.lower()

    cuisine_keywords = {
        "biryani": "Indian", "pizza": "Italian", "burger": "American",
        "sushi": "Japanese", "chinese": "Chinese", "indian": "Indian",
        "north indian": "North Indian", "south indian": "South Indian",
    }
    for keyword, cuisine in cuisine_keywords.items():
        if keyword in msg_lower:
            updates["preferred_cuisine"] = cuisine
            break

    room_keywords = {"deluxe": "Deluxe", "suite": "Suite", "standard": "Standard"}
    for keyword, room_type in room_keywords.items():
        if keyword in msg_lower:
            updates["preferred_room_type"] = room_type
            break

    return updates


def format_preferences_for_prompt(preferences: dict) -> str:
    """
    Format long-term preferences as a compact prompt block.
    """
    if not preferences:
        return ""
    lines = ["=== LONG-TERM USER PREFERENCES (remembered from past sessions) ==="]
    for key, value in preferences.items():
        lines.append(f"  • {key.replace('_', ' ').title()}: {value}")
    lines.append("=== END PREFERENCES ===\n")
    return "\n".join(lines)