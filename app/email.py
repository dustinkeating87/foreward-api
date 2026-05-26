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


def send_free_tier_signup_email(user_email: str, course_name: str, alert_id: str) -> None:
    from datetime import datetime, timezone
    now_utc_iso = datetime.now(timezone.utc).isoformat()
    to = os.environ.get("SIGNUP_NOTIFY_TO") or os.environ.get("ALARM_EMAIL_TO")
    if not to:
        log.warning("send_free_tier_signup_email: no recipient configured (SIGNUP_NOTIFY_TO/ALARM_EMAIL_TO), skipping")
        return
    sg_key = os.environ.get("SENDGRID_API_KEY", "")
    if not sg_key:
        log.warning("send_free_tier_signup_email: SENDGRID_API_KEY not set, skipping")
        return
    from_addr = os.environ.get("ALARM_EMAIL_FROM", "hello@goodlie.golf")
    html = (
        f"<h2>New free-tier signup</h2>"
        f"<p><strong>Email:</strong> {user_email}</p>"
        f"<p><strong>First alert course:</strong> {course_name}</p>"
        f"<p><strong>Alert ID:</strong> {alert_id}</p>"
        f"<p><strong>Time:</strong> {now_utc_iso}</p>"
    )
    try:
        r = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {sg_key}", "Content-Type": "application/json"},
            json={
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": from_addr, "name": "Good Lie"},
                "subject": f"New free-tier signup: {user_email}",
                "content": [{"type": "text/html", "value": html}],
            },
            timeout=15,
        )
        r.raise_for_status()
    except Exception as exc:
        log.error("send_free_tier_signup_email: failed user=%s — %s", user_email, exc)


def send_paid_signup_email(user_email: str, stripe_subscription_id: str, amount_cad: float) -> None:
    from datetime import datetime, timezone
    now_utc_iso = datetime.now(timezone.utc).isoformat()
    to = os.environ.get("SIGNUP_NOTIFY_TO") or os.environ.get("ALARM_EMAIL_TO")
    if not to:
        log.warning("send_paid_signup_email: no recipient configured (SIGNUP_NOTIFY_TO/ALARM_EMAIL_TO), skipping")
        return
    sg_key = os.environ.get("SENDGRID_API_KEY", "")
    if not sg_key:
        log.warning("send_paid_signup_email: SENDGRID_API_KEY not set, skipping")
        return
    from_addr = os.environ.get("ALARM_EMAIL_FROM", "hello@goodlie.golf")
    html = (
        f"<h2>New paid subscriber</h2>"
        f"<p><strong>Email:</strong> {user_email}</p>"
        f"<p><strong>Subscription ID:</strong> {stripe_subscription_id}</p>"
        f"<p><strong>Amount:</strong> ${amount_cad:.2f} CAD/month</p>"
        f"<p><strong>Time:</strong> {now_utc_iso}</p>"
    )
    try:
        r = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {sg_key}", "Content-Type": "application/json"},
            json={
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": from_addr, "name": "Good Lie"},
                "subject": f"New paid subscriber: {user_email}",
                "content": [{"type": "text/html", "value": html}],
            },
            timeout=15,
        )
        r.raise_for_status()
    except Exception as exc:
        log.error("send_paid_signup_email: failed user=%s — %s", user_email, exc)


def send_free_tier_non_firing_expiry_email(to: str, alert_id: str, retry_link: str, course_name: str = "the course") -> None:
    """Sent when a free-tier alert hits date_to without ever firing."""
    send_email(
        to,
        "That course played hard to get",
        (
            f"{course_name} wasn't ready to compromise. {course_name} showed you nothing for the entire window, not one slot. "
            f"We mean this: it's not you, it's the course. To make it up to you, here's a fresh alert on the house. "
            f"Keep chasing this one, or point it at a few others and play the field a little.\n\n"
            f"Set up another free alert: {retry_link}"
        ),
    )
