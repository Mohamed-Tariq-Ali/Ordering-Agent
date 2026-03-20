"""
INPUT ROLE 3 — Environment / Runtime Context

Automatically injected on every request.
Critical for resolving temporal references like "tomorrow", "last week", "tonight".
Also carries session identity and user permissions tier.

Windows-safe: uses datetime.timezone.utc as fallback if tzdata is not installed.
"""

from datetime import datetime, timezone, timedelta

# Try ZoneInfo with tzdata fallback — safe on Windows
def _get_tz(tz_name: str):
    """Return a timezone object. Falls back to UTC if tzdata not installed."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except Exception:
        pass
    try:
        from backports.zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except Exception:
        pass
    # Final fallback — UTC offset for IST (+5:30)
    if tz_name in ("Asia/Kolkata", "Asia/Calcutta"):
        return timezone(timedelta(hours=5, minutes=30))
    return timezone.utc


DEFAULT_TZ = "Asia/Kolkata"


def build_runtime_context(
    session_id: str,
    user_location: dict | None = None,
    tz_name: str = DEFAULT_TZ,
) -> dict:
    """
    Build a runtime context snapshot for this request.
    Returns a plain dict — format_runtime_for_prompt() converts it to a string.
    """
    tz = _get_tz(tz_name)
    now = datetime.now(tz)

    ctx = {
        "session_id"      : session_id,
        "datetime_iso"    : now.isoformat(),
        "date"            : now.strftime("%A, %d %B %Y"),
        "time"            : now.strftime("%I:%M %p"),
        "timezone"        : tz_name,
        "day_of_week"     : now.strftime("%A"),
        "tomorrow_date"   : (now + timedelta(days=1)).strftime("%d %B %Y"),
        "yesterday_date"  : (now - timedelta(days=1)).strftime("%d %B %Y"),
        "next_week_start" : (now + timedelta(days=(7 - now.weekday()))).strftime("%d %B %Y"),
    }

    if user_location:
        ctx["user_location"] = {
            "lat"    : user_location.get("lat"),
            "lng"    : user_location.get("lng"),
            "address": user_location.get("address", "Unknown"),
        }

    return ctx


def format_runtime_for_prompt(ctx: dict) -> str:
    """
    Render the runtime context as a compact prompt block.
    Always prepended so the LLM never has to guess the date/time.
    """
    loc_line = ""
    if "user_location" in ctx:
        loc = ctx["user_location"]
        loc_line = f"\n  • User Location  : {loc.get('address', 'Unknown')} ({loc.get('lat')}, {loc.get('lng')})"

    return (
        f"=== RUNTIME CONTEXT ===\n"
        f"  • Session ID     : {ctx['session_id']}\n"
        f"  • Current Date   : {ctx['date']}\n"
        f"  • Current Time   : {ctx['time']}  [{ctx['timezone']}]\n"
        f"  • Day            : {ctx['day_of_week']}\n"
        f"  • Tomorrow       : {ctx['tomorrow_date']}\n"
        f"  • Yesterday      : {ctx['yesterday_date']}\n"
        f"  • Next Week Start: {ctx['next_week_start']}"
        f"{loc_line}\n"
        f"=== END RUNTIME ===\n"
    )