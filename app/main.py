import os
import time
import smtplib
from email.mime.text import MIMEText
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.routers import auth, alerts, billing, invites, admin, course_requests
from app.database import supabase, supabase_admin
from app.config import settings
import httpx

app = FastAPI(title="Tee Sniper API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(alerts.router)
app.include_router(billing.router)
app.include_router(invites.router)
app.include_router(admin.router)
app.include_router(course_requests.router)

# ── In-memory heartbeat store ──────────────────────────────────────────────────
_heartbeat: dict = {"timestamp": None, "poll_count": None}


def _require_api_key(x_api_key: Optional[str]):
    if not settings.export_api_key or x_api_key != settings.export_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    result: dict = {"status": "ok"}
    if _heartbeat["timestamp"] is not None:
        result["last_heartbeat"] = _heartbeat["timestamp"]
        result["seconds_ago"] = int(time.time() - _heartbeat["timestamp"])
        result["poll_count"] = _heartbeat["poll_count"]
    return result


# ── Scraper heartbeat ──────────────────────────────────────────────────────────

class HeartbeatBody(BaseModel):
    timestamp: float
    poll_count: int


@app.post("/scraper-heartbeat", status_code=200)
def scraper_heartbeat(body: HeartbeatBody, x_api_key: Optional[str] = Header(default=None)):
    _require_api_key(x_api_key)
    _heartbeat["timestamp"] = body.timestamp
    _heartbeat["poll_count"] = body.poll_count
    return {"received": True}


# ── Test notification ──────────────────────────────────────────────────────────

@app.get("/test-notification")
def test_notification(
    email: Optional[str] = Query(default=None),
    phone: Optional[str] = Query(default=None),
    x_api_key: Optional[str] = Header(default=None),
):
    _require_api_key(x_api_key)

    if not email and not phone:
        raise HTTPException(status_code=400, detail="Provide at least one of: email, phone")

    results = {}
    subject = "Tee Sniper — test notification"
    body = "This is a test notification from Tee Sniper. Your alerts are working."

    if email:
        sg_key = os.environ.get("SENDGRID_API_KEY", "")
        if sg_key:
            try:
                r = httpx.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={"Authorization": f"Bearer {sg_key}", "Content-Type": "application/json"},
                    json={
                        "personalizations": [{"to": [{"email": email}]}],
                        "from": {"email": "hello@goodlie.golf"},
                        "subject": subject,
                        "content": [{"type": "text/plain", "value": body}],
                    },
                    timeout=15,
                )
                r.raise_for_status()
                results["email"] = f"sent to {email} via SendGrid"
            except Exception as exc:
                results["email"] = f"failed — {exc}"
        else:
            smtp_host = os.environ.get("SMTP_HOST", "")
            if not smtp_host:
                results["email"] = "skipped — SENDGRID_API_KEY and SMTP_HOST not set"
            else:
                try:
                    port = int(os.environ.get("SMTP_PORT", "587"))
                    user = os.environ.get("SMTP_USER", "")
                    pw   = os.environ.get("SMTP_PASS", "")
                    msg  = MIMEText(body)
                    msg["Subject"] = subject
                    msg["From"]    = user
                    msg["To"]      = email
                    with smtplib.SMTP(smtp_host, port, timeout=15) as s:
                        s.ehlo(); s.starttls()
                        if user and pw:
                            s.login(user, pw)
                        s.sendmail(user, [email], msg.as_string())
                    results["email"] = f"sent to {email} via SMTP"
                except Exception as exc:
                    results["email"] = f"failed — {exc}"

    if phone:
        sid   = os.environ.get("TWILIO_SID", "")
        token = os.environ.get("TWILIO_TOKEN", "")
        frm   = os.environ.get("TWILIO_FROM", "")
        if not (sid and token and frm):
            results["sms"] = "skipped — TWILIO_SID / TWILIO_TOKEN / TWILIO_FROM not set"
        else:
            try:
                r = httpx.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                    auth=(sid, token),
                    data={"From": frm, "To": phone, "Body": f"{subject}\n{body}"},
                    timeout=15,
                )
                r.raise_for_status()
                results["sms"] = f"sent to {phone}"
            except Exception as exc:
                results["sms"] = f"failed — {exc}"

    return results


# ── Export alerts ──────────────────────────────────────────────────────────────

@app.get("/export-alerts")
def export_alerts(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
):
    if x_api_key:
        if not settings.export_api_key or x_api_key != settings.export_api_key:
            raise HTTPException(status_code=403, detail="Invalid API key")
    elif authorization:
        token = authorization.removeprefix("Bearer ").strip()
        try:
            response = supabase.auth.get_user(token)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")

    alerts_result = supabase_admin.table("alert_profiles").select("*").eq("active", True).execute()

    # Build a map of user_id -> contact info from user_profiles
    user_ids = list({row["user_id"] for row in alerts_result.data or [] if row.get("user_id")})
    profiles_map = {}
    if user_ids:
        profiles_result = supabase_admin.table("user_profiles").select("id, notify_email, notify_phone").in_("id", user_ids).execute()
        for p in profiles_result.data or []:
            profiles_map[p["id"]] = p

    export = []
    for row in alerts_result.data or []:
        profile = profiles_map.get(row.get("user_id"), {})
        # Use user profile contact info; fall back to alert-level fields for backwards compat
        email = profile.get("notify_email") or row.get("notify_email") or ""
        phone = profile.get("notify_phone") or row.get("notify_phone") or ""
        export.append({
            "id": row["id"],
            "email": email,
            "phone": phone,
            "courses": row.get("courses") or [],
            "date_from": row["date_from"],
            "date_to": row["date_to"],
            "time_from": row["time_from"],
            "time_to": row["time_to"],
            "players": row["players"],
            "holes": row["holes"],
        })

    return export


# ── Sent slots dedup (persistent across redeploys) ────────────────────────────

class SentSlotBody(BaseModel):
    alert_id: str
    slot_key: str


@app.post("/scraper/sent", status_code=201)
def mark_sent_slot(body: SentSlotBody, x_api_key: Optional[str] = Header(default=None)):
    _require_api_key(x_api_key)
    try:
        supabase_admin.table("sent_slots").insert({
            "alert_id": body.alert_id,
            "slot_key": body.slot_key,
        }).execute()
    except Exception:
        # Unique constraint violation = already marked, that's fine
        pass
    return {"ok": True}


@app.get("/scraper/sent/{alert_id}/{slot_key}")
def is_sent_slot(alert_id: str, slot_key: str, x_api_key: Optional[str] = Header(default=None)):
    _require_api_key(x_api_key)
    result = supabase_admin.table("sent_slots").select("id").eq("alert_id", alert_id).eq("slot_key", slot_key).execute()
    return {"sent": len(result.data) > 0 if result.data else False}
