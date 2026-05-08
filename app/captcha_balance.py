import httpx
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from app.email import send_balance_alarm_email, send_balance_recovery_email
from app.util.dates import _parse_iso

log = logging.getLogger(__name__)


async def check_captcha_balance() -> Optional[float]:
    """Fetch current 2Captcha USD balance. Returns None on API error or missing key."""
    api_key = os.environ.get("CAPTCHA_API_KEY", "")
    if not api_key:
        log.warning("CAPTCHA_API_KEY not set on API service — balance check skipped")
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://2captcha.com/res.php",
                params={"key": api_key, "action": "getbalance"},
            )
        text = r.text.strip()
        if text.startswith("ERROR"):
            log.warning("2Captcha getbalance error: %s", text)
            return None
        return float(text)
    except Exception as exc:
        log.warning("check_captcha_balance failed: %s", exc)
        return None


async def maybe_check_and_alert(supabase) -> None:
    """
    Rate-limited 2Captcha balance check. Called on every /scraper-heartbeat but internally
    gates to at most once per CAPTCHA_BALANCE_CHECK_INTERVAL_MINUTES (default 15).

    Reads/writes scraper_health id=1 for cooldown and alarm state. Sends alarm email on
    threshold crossing; recovery email on recovery above threshold. Swallows all exceptions
    — must never break the heartbeat caller.
    """
    try:
        threshold = float(
            os.environ.get(
                "CAPTCHA_BALANCE_ALARM_THRESHOLD_USD",
                os.environ.get("CAPTCHA_BALANCE_THRESHOLD", "5.0"),
            )
        )
        interval_seconds = int(
            os.environ.get("CAPTCHA_BALANCE_CHECK_INTERVAL_MINUTES", "15")
        ) * 60
        now = datetime.now(timezone.utc)

        result = supabase.table("scraper_health").select(
            "captcha_balance_alarmed, last_captcha_balance_check_at"
        ).eq("id", 1).maybe_single().execute()
        row = result.data or {}

        last_check_raw = row.get("last_captcha_balance_check_at")
        if last_check_raw:
            last_check = _parse_iso(last_check_raw)
            if (now - last_check).total_seconds() < interval_seconds:
                return  # within cooldown window — skip this heartbeat

        balance = await check_captcha_balance()
        if balance is None:
            return  # API error — preserve existing alarm state, no email

        prev_alarmed = row.get("captcha_balance_alarmed")  # bool or None
        now_alarmed = balance < threshold

        supabase.table("scraper_health").update({
            "last_captcha_balance_check_at": now.isoformat(),
            "last_captcha_balance_usd": balance,
            "captcha_balance_alarmed": now_alarmed,
        }).eq("id", 1).execute()

        if prev_alarmed is False and now_alarmed:
            send_balance_alarm_email(balance, threshold)
            log.info("captcha balance alarm: $%.4f < threshold $%.2f", balance, threshold)
        elif prev_alarmed is True and not now_alarmed:
            send_balance_recovery_email(balance, threshold)
            log.info("captcha balance recovery: $%.4f >= threshold $%.2f", balance, threshold)
        elif prev_alarmed is None:
            # First check after migration — set state, no email (no prior state to transition from)
            log.info("captcha balance first check: $%.4f (alarmed=%s, threshold $%.2f)",
                     balance, now_alarmed, threshold)
        else:
            log.info("captcha balance: $%.4f (alarmed=%s, no transition)", balance, now_alarmed)

    except Exception as exc:
        log.error("maybe_check_and_alert failed: %s", exc)
