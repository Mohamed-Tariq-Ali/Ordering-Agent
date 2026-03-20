"""
INPUT ROLE 5 — Interaction State (Dialogue Control)

Tracks slot-filling state across turns within a session:
  - which slots are collected vs. still missing
  - which step of a multi-step workflow is active
  - last agent used (for continuity)

Persisted in SQLite so it survives across requests in the same session.

Example state for hotel booking:
  {
    "active_flow"  : "hotel_booking",
    "step"         : "awaiting_dates",
    "slots": {
      "hotel_name"  : "The Park Chennai",   ← confirmed
      "check_in"    : null,                  ← waiting
      "check_out"   : null,                  ← waiting
      "guests"      : 2,                     ← confirmed
      "room_type"   : null                   ← waiting
    }
  }
"""

import json
from backend.utils.database import get_connection


# ─── Load / Save ──────────────────────────────────────────────────────────────

def load_dialogue_state(session_id: str) -> dict:
    """Retrieve the current dialogue state for this session."""
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT state FROM dialogue_state WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row["state"])
    except Exception:
        pass
    return {}


def save_dialogue_state(session_id: str, state: dict) -> None:
    """Persist updated dialogue state for this session."""
    try:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO dialogue_state (session_id, state)
            VALUES (?, ?)
            ON CONFLICT(session_id) DO UPDATE SET state = excluded.state
            """,
            (session_id, json.dumps(state))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def clear_dialogue_state(session_id: str) -> None:
    """Reset dialogue state — call when a flow completes or is cancelled."""
    save_dialogue_state(session_id, {})


# ─── State helpers ────────────────────────────────────────────────────────────

def start_flow(session_id: str, flow_name: str, initial_slots: dict | None = None) -> dict:
    """Begin a new multi-step flow, optionally pre-filling known slots."""
    state = {
        "active_flow": flow_name,
        "step"       : "started",
        "slots"      : initial_slots or {},
    }
    save_dialogue_state(session_id, state)
    return state


def update_slots(session_id: str, slot_updates: dict, next_step: str | None = None) -> dict:
    """Merge new slot values into the current state and optionally advance the step."""
    state = load_dialogue_state(session_id)
    if "slots" not in state:
        state["slots"] = {}
    state["slots"].update(slot_updates)
    if next_step:
        state["step"] = next_step
    save_dialogue_state(session_id, state)
    return state


def get_missing_slots(session_id: str, required_slots: list[str]) -> list[str]:
    """Return which required slots are still None/missing for the active flow."""
    state = load_dialogue_state(session_id)
    slots = state.get("slots", {})
    return [s for s in required_slots if not slots.get(s)]


# ─── Prompt injection ─────────────────────────────────────────────────────────

def format_dialogue_state_for_prompt(state: dict) -> str:
    """
    Render the current dialogue state as a compact prompt block
    so the agent knows exactly where it is in a multi-step flow.
    """
    if not state or not state.get("active_flow"):
        return ""

    slots = state.get("slots", {})
    confirmed = {k: v for k, v in slots.items() if v is not None}
    waiting    = [k for k, v in slots.items() if v is None]

    lines = [
        "=== DIALOGUE STATE (current workflow progress) ===",
        f"  • Active Flow : {state['active_flow']}",
        f"  • Current Step: {state.get('step', 'unknown')}",
    ]
    if confirmed:
        lines.append("  • Confirmed Slots:")
        for k, v in confirmed.items():
            lines.append(f"      ✓ {k}: {v}")
    if waiting:
        lines.append("  • Still Needed:")
        for k in waiting:
            lines.append(f"      ? {k}: <waiting>")
    lines.append("=== END DIALOGUE STATE ===\n")
    return "\n".join(lines)