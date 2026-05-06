import logging
from datetime import date, timezone, datetime
from fastapi import HTTPException, Request

log = logging.getLogger(__name__)

MAX_ATTEMPTS_PER_DAY = 3


def check_ip_rate_limit(request: Request) -> None:
    """
    Enforces MAX_ATTEMPTS_PER_DAY signup attempts per IP per calendar day (UTC).
    State lives on app.state.ip_rate_limit (dict). Raises 429 if exceeded.
    Call this from the send-verification-code endpoint before any Twilio call.
    """
    ip = request.client.host if request.client else "unknown"
    today = datetime.now(timezone.utc).date()
    store: dict = request.app.state.ip_rate_limit

    entry = store.get(ip)
    if entry and entry["window_date"] == today:
        if entry["count"] >= MAX_ATTEMPTS_PER_DAY:
            log.warning("ip_rate_limit: blocked %s — %d attempts today", ip, entry["count"])
            raise HTTPException(
                status_code=429,
                detail="Too many verification requests from this IP. Try again tomorrow.",
            )
        entry["count"] += 1
    else:
        store[ip] = {"count": 1, "window_date": today}

    log.info("ip_rate_limit: %s count=%d date=%s", ip, store[ip]["count"], today)
