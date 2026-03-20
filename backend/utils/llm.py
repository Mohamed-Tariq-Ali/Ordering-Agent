import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None

# ── Model config ──────────────────────────────────────────────────────────────
# llama-3.1-8b-instant : 500k TPD on free tier  — used for routing + simple calls
# llama-3.3-70b-versatile: 100k TPD on free tier — used only for rich responses
FAST_MODEL = "llama-3.1-8b-instant"
SMART_MODEL = "llama-3.3-70b-versatile"

# Agents that genuinely need the big model (natural language generation)
SMART_AGENTS = {
    "food_search", "food_order", "hotel_search", "hotel_booking",
    "order_history", "order_cancel", "product_search", "order_booking",
}

# Agents that only need routing/classification — use fast model
FAST_AGENTS = {
    "coordinator", "order_status", "greeting", "clarification", "policy_filter",
}


def get_groq_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in .env file")
        _client = Groq(api_key=api_key)
    return _client


def _trim_messages(messages: list, max_turns: int = 6) -> list:
    """Keep only the most recent N turns to reduce token usage."""
    if len(messages) <= max_turns:
        return messages
    # Always keep the system message if present
    system = [m for m in messages if m["role"] == "system"]
    rest   = [m for m in messages if m["role"] != "system"]
    return system + rest[-max_turns:]


def _trim_system(system_prompt: str, max_chars: int = 2000) -> str:
    """Truncate system prompt if it's excessively long."""
    if len(system_prompt) <= max_chars:
        return system_prompt
    return system_prompt[:max_chars] + "\n[truncated]"


def chat_completion(
    messages       : list,
    system_prompt  : str,
    temperature    : float = 0.3,
    context_block  : str   = "",   # INPUT ROLE 1 — pre-fetched DB context
    memory_block   : str   = "",   # INPUT ROLE 2 — long-term preferences
    runtime_block  : str   = "",   # INPUT ROLE 3 — datetime / session info
    agent_msg_block: str   = "",   # INPUT ROLE 6 — agent-to-agent messages
    use_fast_model : bool  = False, # force fast model for this call
) -> str:
    """
    Call Groq and return the assistant's reply as a string.

    INPUT ROLE 4 (System Instructions / Policies):
      Global guardrails are prepended to EVERY system prompt here so they
      can never be bypassed — even if an agent forgets to include them.
      Per-agent policy fragments are injected by the caller via system_prompt.
    """
    from backend.utils.policy import GLOBAL_GUARDRAILS  # avoid circular import

    # Build enriched system prompt:
    # [guardrails] + [runtime] + [memory] + [context] + [agent msgs] + [agent prompt]
    enriched_system = "\n".join(filter(None, [
        GLOBAL_GUARDRAILS,   # Role 4 — always first, always present
        runtime_block,       # Role 3
        memory_block,        # Role 2
        context_block,       # Role 1
        agent_msg_block,     # Role 6
        system_prompt,       # agent's own instructions (last — highest specificity)
    ]))

    # Trim to reduce token usage
    enriched_system = _trim_system(enriched_system, max_chars=2500)
    trimmed_messages = _trim_messages(messages, max_turns=6)

    # Pick model — fast for routing/simple, smart for rich generation
    model = FAST_MODEL if use_fast_model else SMART_MODEL

    client = get_groq_client()
    full_messages = [{"role": "system", "content": enriched_system}] + trimmed_messages

    try:
        response = client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=512,   # reduced from 1024 — enough for most replies
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        err = str(e)
        # Rate limit hit on smart model — fall back to fast model automatically
        if "rate_limit_exceeded" in err and model == SMART_MODEL:
            try:
                response = client.chat.completions.create(
                    model=FAST_MODEL,
                    messages=full_messages,
                    temperature=temperature,
                    max_tokens=512,
                )
                return response.choices[0].message.content.strip()
            except Exception as e2:
                return f"I'm temporarily unavailable due to rate limits. Please try again in a few minutes. ({str(e2)[:80]})"
        raise


def chat_completion_fast(
    messages      : list,
    system_prompt : str,
    temperature   : float = 0.1,
) -> str:
    """
    Lightweight wrapper for coordinator / routing calls.
    Always uses the fast model, no role blocks injected, minimal tokens.
    """
    from backend.utils.policy import GLOBAL_GUARDRAILS

    system = "\n".join(filter(None, [GLOBAL_GUARDRAILS, system_prompt]))
    system = _trim_system(system, max_chars=1500)
    trimmed = _trim_messages(messages, max_turns=4)

    client = get_groq_client()
    full_messages = [{"role": "system", "content": system}] + trimmed

    try:
        response = client.chat.completions.create(
            model=FAST_MODEL,
            messages=full_messages,
            temperature=temperature,
            max_tokens=50,   # routing only needs one word back
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "clarification"