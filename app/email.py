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
