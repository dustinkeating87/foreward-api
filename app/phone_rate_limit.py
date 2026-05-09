import logging
from datetime import datetime, timezone
from fastapi import HTTPException, Request

log = logging.getLogger(__name__)

MAX_SENDS_PER_PHONE_PER_DAY = 3


def check_phone_rate_limit(request: Request, phone_hash: str) -> None:
    """
    Enforces MAX_SENDS_PER_PHONE_PER_DAY verification sends per phone per calendar day (UTC).
    State lives on app.state.phone_rate_limit (dict). Raises 429 if exceeded.
    Key is phone_hash (SHA-256 hex), not raw E.164 — avoids leaking numbers into diagnostics.
    Call this after check_ip_rate_limit, before any Twilio call.
    """
    today = datetime.now(timezone.utc).date()
    store: dict = request.app.state.phone_rate_limit

    entry = store.get(phone_hash)
    if entry and entry["window_date"] == today:
        if entry["count"] >= MAX_SENDS_PER_PHONE_PER_DAY:
            log.warning("phone_rate_limit: blocked phone_hash=%s — %d sends today", phone_hash[:8], entry["count"])
            raise HTTPException(
                status_code=429,
                detail="This phone number has reached today's verification limit. Please try again tomorrow or contact support.",
            )
        entry["count"] += 1
    else:
        store[phone_hash] = {"count": 1, "window_date": today}

    log.info("phone_rate_limit: phone_hash=%s count=%d date=%s", phone_hash[:8], store[phone_hash]["count"], today)
