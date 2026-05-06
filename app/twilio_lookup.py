import os
import logging
import httpx
from app.util.phone import hash_phone

log = logging.getLogger(__name__)

BLOCKED_TYPES = {"nonFixedVoip", "personal"}
BLOCKED_CARRIERS = {"google voice", "textnow", "hushed", "sideline", "pinger"}

# In-memory cache: phone_hash -> True (blocked) | False (allowed)
# Lost on redeploy, which is fine — a cache miss just costs $0.005
_lookup_cache: dict[str, bool] = {}


class LookupBlocked(Exception):
    pass


def check_phone(e164: str) -> None:
    """
    Raises LookupBlocked if the phone is VoIP or a known disposable carrier.
    Raises httpx.HTTPError on Twilio API failure (caller should handle).
    Caches result by phone hash to avoid double-billing on resend.
    """
    phone_hash = hash_phone(e164)
    if phone_hash in _lookup_cache:
        if _lookup_cache[phone_hash]:
            raise LookupBlocked("VoIP or disposable number not permitted")
        return

    sid = os.environ.get("TWILIO_SID", "")
    token = os.environ.get("TWILIO_TOKEN", "")
    if not (sid and token):
        log.warning("twilio_lookup: TWILIO_SID/TWILIO_TOKEN not set — skipping lookup")
        _lookup_cache[phone_hash] = False
        return

    r = httpx.get(
        f"https://lookups.twilio.com/v2/PhoneNumbers/{e164}",
        params={"Fields": "line_type_intelligence"},
        auth=(sid, token),
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()

    lti = data.get("line_type_intelligence") or {}
    line_type = lti.get("type", "")
    carrier = (lti.get("carrier_name") or "").lower()

    blocked = (
        line_type in BLOCKED_TYPES
        or any(name in carrier for name in BLOCKED_CARRIERS)
    )
    _lookup_cache[phone_hash] = blocked
    log.info(
        "twilio_lookup: phone_hash=%s type=%s carrier=%s blocked=%s",
        phone_hash[:8], line_type, carrier, blocked,
    )
    if blocked:
        raise LookupBlocked("VoIP or disposable number not permitted")
