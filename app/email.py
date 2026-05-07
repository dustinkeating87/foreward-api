import os
import httpx
import logging
from typing import Optional

log = logging.getLogger(__name__)


def send_dynamic_template(
    *,
    to: str,
    template_id: str,
    dynamic_data: dict,
    from_email: str = "hello@goodlie.golf",
    from_name: str = "Good Lie",
) -> bool:
    """
    Sends a SendGrid Dynamic Template email.

    Returns True on 2xx, False on failure. Does not raise - failures
    must never break callers (same contract as existing alarm emails).
    """
    sg_key = os.environ.get("SENDGRID_API_KEY", "")
    if not sg_key:
        log.warning("send_dynamic_template: SENDGRID_API_KEY not set, skipping to=%s", to)
        return False
    if not template_id:
        log.warning("send_dynamic_template: template_id is empty, skipping to=%s", to)
        return False
    try:
        r = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {sg_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": {"email": from_email, "name": from_name},
                "personalizations": [{
                    "to": [{"email": to}],
                    "dynamic_template_data": dynamic_data,
                }],
                "template_id": template_id,
            },
            timeout=15,
        )
        r.raise_for_status()
        return True
    except Exception as exc:
        log.error("send_dynamic_template: failed to=%s template=%s — %s", to, template_id, exc)
        return False


def send_email(to: str, subject: str, body: str, from_addr: str = "hello@goodlie.golf") -> None:
    sg_key = os.environ.get("SENDGRID_API_KEY", "")
    if not sg_key:
        log.warning("send_email: SENDGRID_API_KEY not set, skipping email to %s", to)
        return
    r = httpx.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {sg_key}", "Content-Type": "application/json"},
        json={
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": from_addr, "name": "Good Lie"},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        },
        timeout=15,
    )
    r.raise_for_status()


def send_balance_alarm_email(balance: float, threshold: float) -> None:
    send_email(
        os.environ.get("ALARM_EMAIL_TO", "hello@goodlie.golf"),
        "[Good Lie] 2Captcha balance low",
        (
            f"2Captcha balance has dropped below ${threshold:.2f}.\n\n"
            f"Current balance: ${balance:.2f}\n\n"
            "Top up at https://2captcha.com/pay to avoid GTG scraper failures."
        ),
        from_addr=os.environ.get("ALARM_EMAIL_FROM", "hello@goodlie.golf"),
    )


def send_balance_recovery_email(balance: float, threshold: float) -> None:
    send_email(
        os.environ.get("ALARM_EMAIL_TO", "hello@goodlie.golf"),
        "[Good Lie] 2Captcha balance recovered",
        (
            f"2Captcha balance is back above ${threshold:.2f}.\n\n"
            f"Current balance: ${balance:.2f}"
        ),
        from_addr=os.environ.get("ALARM_EMAIL_FROM", "hello@goodlie.golf"),
    )


def send_heartbeat_alarm_email(seconds_stale: int, threshold_seconds: int) -> None:
    send_email(
        os.environ.get("ALARM_EMAIL_TO", "hello@goodlie.golf"),
        "[Good Lie] Worker heartbeat stale",
        (
            f"No heartbeat from the scraper worker for {seconds_stale}s "
            f"(threshold: {threshold_seconds}s).\n\n"
            "Check Railway worker logs. The worker may be crashed or hung."
        ),
        from_addr=os.environ.get("ALARM_EMAIL_FROM", "hello@goodlie.golf"),
    )


def send_heartbeat_recovery_email(was_stale_seconds: int, threshold_seconds: int) -> None:
    send_email(
        os.environ.get("ALARM_EMAIL_TO", "hello@goodlie.golf"),
        "[Good Lie] Worker heartbeat recovered",
        f"Scraper worker heartbeat has recovered.\n\nThreshold: {threshold_seconds}s.",
        from_addr=os.environ.get("ALARM_EMAIL_FROM", "hello@goodlie.golf"),
    )


def send_free_tier_expiry_email(to: str, alert_id: str, renewals_used: int, renewal_link: str) -> None:
    # Signature frozen: Block 4 replaces body with SendGrid template call, not this signature.
    renewals_remaining = 2 - renewals_used
    plural = "s" if renewals_remaining != 1 else ""
    send_email(
        to,
        "Good Lie Golf — no tee times opened up in your window",
        (
            f"Unfortunately no tee times opened up matching your alert during the 14-day window.\n\n"
            f"You have {renewals_remaining} renewal{plural} remaining.\n\n"
            f"Renew your alert (one click): {renewal_link}\n\n"
            "You can also edit your criteria before renewing by visiting goodlie.golf."
        ),
    )


def send_final_expiry_email(to: str, discount_code: Optional[str]) -> None:
    # Signature frozen: Block 4 replaces body with SendGrid template call, not this signature.
    coupon_section = (
        f"\n\nAs a thank-you for trying Good Lie Golf, here's 50% off your first month: {discount_code}\n"
        "This code expires in 7 days. Redeem at goodlie.golf/billing."
        if discount_code
        else ""
    )
    send_email(
        to,
        "Good Lie Golf — your free alert period has ended",
        (
            "Your free alert has run through all 3 polling windows (42 days) without a match.\n\n"
            "Subscribe to Good Lie Golf for unlimited real-time alerts at $9.99/mo.\n"
            "Visit goodlie.golf to get started."
            f"{coupon_section}"
        ),
    )
