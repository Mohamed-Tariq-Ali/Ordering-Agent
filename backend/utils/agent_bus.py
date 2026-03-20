"""
INPUT ROLE 6 — Agent-to-Agent Messages

Structured handoff payloads passed between agents — not from the user, not from a tool.
Used for:
  - Task delegation  (coordinator → specialist)
  - Status updates   (specialist → coordinator)
  - Error escalation (specialist → coordinator)
  - Sub-agent results fed back to the coordinating agent

Each message is an AgentMessage dataclass.
The bus is in-memory per process (a lightweight dict keyed by session_id).
For multi-process / production use, swap the store for Redis or a DB table.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any
import uuid


# ─── Message schema ───────────────────────────────────────────────────────────

@dataclass
class AgentMessage:
    from_agent  : str                          # e.g. "coordinator"
    to_agent    : str                          # e.g. "order_booking"
    message_type: str                          # "task" | "result" | "error" | "status"
    payload     : dict[str, Any]               # arbitrary structured data
    session_id  : str = ""
    message_id  : str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp   : str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


# ─── In-memory bus ────────────────────────────────────────────────────────────
# Structure: { session_id: [ AgentMessage, ... ] }

_bus: dict[str, list[AgentMessage]] = {}


def send_message(msg: AgentMessage) -> None:
    """Post a message onto the bus for the given session."""
    _bus.setdefault(msg.session_id, []).append(msg)


def receive_messages(session_id: str, to_agent: str | None = None) -> list[AgentMessage]:
    """
    Retrieve all pending messages for a session.
    Optionally filter to messages addressed to a specific agent.
    """
    msgs = _bus.get(session_id, [])
    if to_agent:
        msgs = [m for m in msgs if m.to_agent == to_agent]
    return msgs


def clear_messages(session_id: str) -> None:
    """Clear all messages for a session (call after they've been consumed)."""
    _bus.pop(session_id, None)


# ─── Convenience constructors ─────────────────────────────────────────────────

def delegation_message(
    from_agent: str,
    to_agent: str,
    task: str,
    session_id: str,
    extra: dict | None = None,
) -> AgentMessage:
    """Coordinator delegating a task to a specialist."""
    return AgentMessage(
        from_agent=from_agent,
        to_agent=to_agent,
        message_type="task",
        payload={"task": task, **(extra or {})},
        session_id=session_id,
    )


def result_message(
    from_agent: str,
    to_agent: str,
    result: Any,
    session_id: str,
    success: bool = True,
) -> AgentMessage:
    """Specialist reporting back a result (or failure) to its caller."""
    return AgentMessage(
        from_agent=from_agent,
        to_agent=to_agent,
        message_type="result" if success else "error",
        payload={"result": result, "success": success},
        session_id=session_id,
    )


def error_escalation(
    from_agent: str,
    error: str,
    session_id: str,
    context: dict | None = None,
) -> AgentMessage:
    """Specialist escalating an error back to the coordinator."""
    return AgentMessage(
        from_agent=from_agent,
        to_agent="coordinator",
        message_type="error",
        payload={"error": error, "context": context or {}},
        session_id=session_id,
    )


# ─── Prompt injection ─────────────────────────────────────────────────────────

def format_agent_messages_for_prompt(messages: list[AgentMessage]) -> str:
    """
    Render pending agent-to-agent messages as a prompt block
    so the receiving agent is aware of delegated context.
    """
    if not messages:
        return ""

    lines = ["=== AGENT MESSAGES (from other agents — not from the user) ==="]
    for m in messages:
        lines.append(
            f"  [{m.message_type.upper()}] {m.from_agent} → {m.to_agent} "
            f"| {m.timestamp[:19]}"
        )
        for k, v in m.payload.items():
            lines.append(f"      {k}: {v}")
    lines.append("=== END AGENT MESSAGES ===\n")
    return "\n".join(lines)