import os
import httpx
import logging

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


def send_free_tier_non_firing_expiry_email(to: str, alert_id: str, retry_link: str) -> None:
    """Sent when a free-tier alert hits date_to without ever firing.
    The user gets one chance to reset with a new date range — this email surfaces that."""
    send_email(
        to,
        "Your Good Lie alert ran out — try again on us",
        (
            f"Your free Good Lie alert just expired without finding a tee time.\n\n"
            f"That's not the demo we promised. Here's a one-time retry — set a new date range "
            f"and we'll keep watching:\n\n"
            f"{retry_link}\n\n"
            f"This is your last shot on the free tier. After this, you'll need to subscribe "
            f"to keep getting alerts.\n\n"
            f"— Good Lie"
        ),
    )
