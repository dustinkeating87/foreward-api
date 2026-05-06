import os
import httpx
import logging

log = logging.getLogger(__name__)


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
