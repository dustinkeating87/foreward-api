import asyncio
import logging
import os
import smtplib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.routers import auth, alerts, billing, invites, admin, course_requests, activity, phone_verification, courses
from app.database import supabase, supabase_admin
from app.config import settings
from app.heartbeat_monitor import heartbeat_monitor_loop
from app.idle_nudge import idle_nudge_loop
from app.util.dates import _parse_iso
import httpx

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    app.state.ip_rate_limit = {}
    app.state.phone_rate_limit = {}
    heartbeat_task = asyncio.create_task(heartbeat_monitor_loop())
    nudge_task = asyncio.create_task(idle_nudge_loop())
    try:
        yield
    finally:
        heartbeat_task.cancel()
        nudge_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        try:
            await nudge_task
        except asyncio.CancelledError:
            pass

app = FastAPI(title="Tee Sniper API", version="1.0.0", lifespan=lifespan)

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
app.include_router(activity.router)
app.include_router(phone_verification.router)
app.include_router(courses.router)

def _require_api_key(x_api_key: Optional[str]):
    if not settings.export_api_key or x_api_key != settings.export_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    try:
        row = supabase_admin.table("scraper_health").select(
            "last_heartbeat, last_poll, slots_last_poll"
        ).eq("id", 1).maybe_single().execute()
        data = row.data or {}
    except Exception:
        return {"status": "ok", "scraper": "unavailable"}

    last_heartbeat = data.get("last_heartbeat")
    if last_heartbeat:
        seconds_ago = int((datetime.now(timezone.utc) - _parse_iso(last_heartbeat)).total_seconds())
        scraper_healthy = seconds_ago < 300
    else:
        seconds_ago = None
        scraper_healthy = False

    return {
        "status": "ok",
        "scraper_healthy": scraper_healthy,
        "last_heartbeat": last_heartbeat,
        "seconds_ago": seconds_ago,
        "last_poll_number": data.get("last_poll"),
        "slots_last_poll": data.get("slots_last_poll"),
    }


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

    alerts_result = supabase_admin.table("alert_profiles").select("*").eq("status", "active").execute()

    # Build a map of user_id -> contact info from user_profiles
    user_ids = list({row["user_id"] for row in alerts_result.data or [] if row.get("user_id")})
    profiles_map = {}
    if user_ids:
        profiles_result = supabase_admin.table("user_profiles").select("id, notify_email, notify_phone, is_active").in_("id", user_ids).execute()
        for p in profiles_result.data or []:
            profiles_map[p["id"]] = p

    # Build a map of user_id -> auth email as last-resort fallback when notify_email is unset
    auth_email_map: dict[str, str] = {}
    for uid in user_ids:
        try:
            resp = supabase_admin.auth.admin.get_user_by_id(uid)
            if resp and resp.user and resp.user.email:
                auth_email_map[uid] = resp.user.email
        except Exception:
            pass

    export = []
    for row in alerts_result.data or []:
        uid = row.get("user_id")
        profile = profiles_map.get(uid, {})
        # Resolution order: user_profiles.notify_email → alert notify_email → auth.users.email
        email = (
            profile.get("notify_email")
            or row.get("notify_email")
            or (auth_email_map.get(uid, "") if uid else "")
        )
        phone = profile.get("notify_phone") or row.get("notify_phone") or ""
        export.append({
            "id": row["id"],
            "user_id": uid,
            "status": row.get("status", "active"),
            "email": email,
            "auth_email": auth_email_map.get(uid, "") if uid else "",
            "phone": phone,
            "courses": row.get("courses") or [],
            "date_from": row["date_from"],
            "date_to": row["date_to"],
            "time_from": row["time_from"],
            "time_to": row["time_to"],
            "players": row["players"],
            "holes": row["holes"],
            "is_free_tier": row.get("is_free_tier", False),
            "user_is_paid": bool(profile.get("is_active")),
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


# ── Alert lifecycle ────────────────────────────────────────────────────────────

@app.post("/scraper/send-paywall-emails", status_code=200)
async def send_paywall_emails(x_api_key: Optional[str] = Header(default=None)):
    """Trigger the daily conversion sweep. Dry-run behaviour controlled by PAYWALL_EMAIL_DRY_RUN env var."""
    _require_api_key(x_api_key)
    from app.conversion_sweep import run_conversion_sweep
    await run_conversion_sweep(dry_run=settings.paywall_email_dry_run)
    return {"ok": True, "dry_run": settings.paywall_email_dry_run}


@app.post("/scraper/expire-alerts", status_code=200)
def expire_stale_alerts(x_api_key: Optional[str] = Header(default=None)):
    """Expire alert_profiles where date_to < today and status='active'."""
    _require_api_key(x_api_key)
    from datetime import date
    from app.email import send_free_tier_non_firing_expiry_email
    today = date.today().isoformat()
    result = supabase_admin.table("alert_profiles").update({"status": "expired"}) \
        .lt("date_to", today).eq("status", "active").execute()
    expired = len(result.data) if result.data else 0

    # Non-firing-expiry email for free-tier alerts that never fired
    for alert in result.data or []:
        if not alert.get("is_free_tier"):
            continue
        fired = (
            supabase_admin.table("sent_slots")
            .select("id")
            .eq("alert_id", alert["id"])
            .limit(1)
            .execute()
        )
        if fired.data:
            continue
        user_result = (
            supabase_admin.table("user_profiles")
            .select("notify_email, free_tier_grace_retry_used_at")
            .eq("id", alert["user_id"])
            .maybe_single()
            .execute()
        )
        user = user_result.data or {}
        if user.get("notify_email") and user.get("free_tier_grace_retry_used_at") is None:
            retry_link = f"{settings.frontend_url}/dashboard?retry_free_tier=1"
            course_name = (alert.get("courses") or ["the course"])[0]
            try:
                send_free_tier_non_firing_expiry_email(user["notify_email"], alert["id"], retry_link, course_name)
            except Exception:
                log.error("non_firing_expiry_email: failed alert=%s", alert["id"])

    return {"ok": True, "expired": expired}


class FireAlertSlot(BaseModel):
    slot_key: str
    course_name: Optional[str] = None
    tee_time: Optional[str] = None
    players: Optional[int] = None


class FireAlertBody(BaseModel):
    alert_id: str
    user_id: Optional[str] = None
    scanned_at: Optional[str] = None
    slots: list[FireAlertSlot] = []


@app.post("/scraper/fire-alert", status_code=200)
def fire_alert(body: FireAlertBody, x_api_key: Optional[str] = Header(default=None)):
    """Bulk-insert sent_slots for all matched slots and mark the alert as fired."""
    _require_api_key(x_api_key)

    if not body.slots:
        log.warning("fire_alert called with empty slots for alert %s — refusing to flip status", body.alert_id)
        return {"ok": True, "fired": False, "reason": "no_slots"}

    rows = []
    for slot in body.slots:
        row: dict = {"alert_id": body.alert_id, "slot_key": slot.slot_key}
        if body.user_id:
            row["user_id"] = body.user_id
        if slot.course_name:
            row["course_name"] = slot.course_name
        if slot.tee_time:
            row["tee_time"] = slot.tee_time
        if slot.players is not None:
            row["players"] = slot.players
        if body.scanned_at:
            row["scanned_at"] = body.scanned_at
        rows.append(row)

    slots_attempted = len(rows)
    slots_written = 0
    slots_failed = 0

    try:
        supabase_admin.table("sent_slots").insert(rows).execute()
        slots_written = slots_attempted
    except Exception as bulk_exc:
        log.warning("fire_alert: bulk insert failed for alert %s (%d rows) — trying per-row: %s",
                    body.alert_id, slots_attempted, bulk_exc)
        for row in rows:
            try:
                supabase_admin.table("sent_slots").insert(row).execute()
                slots_written += 1
            except Exception as row_exc:
                slots_failed += 1
                log.error("fire_alert: sent_slots row failed for alert %s slot %s: %s",
                          body.alert_id, row.get("slot_key", "?"), row_exc)

    if slots_failed:
        log.error("fire_alert: %d/%d sent_slots rows failed for alert %s — "
                  "delivery confirmed (SMS/email sent), DB audit trail incomplete",
                  slots_failed, slots_attempted, body.alert_id)

    supabase_admin.table("alert_profiles").update({"status": "fired"}) \
        .eq("id", body.alert_id).execute()

    # Stamp free_tier_used_at at delivery time (not creation) for free-tier alerts
    if body.user_id:
        try:
            alert_row = supabase_admin.table("alert_profiles") \
                .select("is_free_tier") \
                .eq("id", body.alert_id) \
                .maybe_single() \
                .execute()
            if alert_row.data and alert_row.data.get("is_free_tier"):
                supabase_admin.table("user_profiles") \
                    .update({"free_tier_used_at": datetime.now(timezone.utc).isoformat()}) \
                    .eq("id", body.user_id) \
                    .is_("free_tier_used_at", "null") \
                    .execute()
                log.info("fire_alert: stamped free_tier_used_at for user %s", body.user_id[:8])
        except Exception as exc:
            log.warning("fire_alert: failed to stamp free_tier_used_at user=%s: %s", body.user_id, exc)

    return {"ok": True, "fired": True, "slots_written": slots_written, "slots_failed": slots_failed}


class RearmAlertBody(BaseModel):
    alert_id: str
    clear_sent_slots: bool = False


@app.post("/scraper/rearm-alert", status_code=200)
def rearm_alert(body: RearmAlertBody, x_api_key: Optional[str] = Header(default=None)):
    """Re-arm a fired or expired alert back to active. System/admin use only — no subscription gate.

    Guard: only transitions 'fired' or 'expired' → 'active'.
    'active' and 'paused' alerts are returned unchanged.
    clear_sent_slots (default false): when true, deletes sent_slots rows for the alert
    so stale dedup state cannot suppress re-matching. Off by default to preserve the
    delivery audit trail.
    """
    _require_api_key(x_api_key)

    alert_row = (
        supabase_admin.table("alert_profiles")
        .select("id, status")
        .eq("id", body.alert_id)
        .maybe_single()
        .execute()
    )
    if not alert_row.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    current_status = alert_row.data["status"]
    if current_status not in ("fired", "expired"):
        log.info("rearm_alert: alert %s is '%s' — no change", body.alert_id, current_status)
        return {"alert_id": body.alert_id, "status": current_status, "changed": False, "sent_slots_deleted": 0}

    supabase_admin.table("alert_profiles").update({"status": "active"}).eq("id", body.alert_id).execute()
    log.info("rearm_alert: alert %s '%s' → 'active'", body.alert_id, current_status)

    deleted = 0
    if body.clear_sent_slots:
        result = supabase_admin.table("sent_slots").delete().eq("alert_id", body.alert_id).execute()
        deleted = len(result.data) if result.data else 0
        log.info("rearm_alert: deleted %d sent_slots rows for alert %s", deleted, body.alert_id)

    return {"alert_id": body.alert_id, "status": "active", "changed": True, "sent_slots_deleted": deleted}


class MarkTakenBody(BaseModel):
    current_slot_keys: list[str]
    scanned_course_names: list[str]


@app.post("/scraper/mark-taken", status_code=200)
def mark_taken_slots(body: MarkTakenBody, x_api_key: Optional[str] = Header(default=None)):
    """Mark sent_slots as taken when they vanish from a productive platform poll."""
    _require_api_key(x_api_key)

    # Safety: empty lists would match all or nothing incorrectly
    if not body.scanned_course_names or not body.current_slot_keys:
        return {"ok": True, "updated": 0}

    from datetime import datetime, timedelta, timezone as tz
    cutoff = (datetime.now(tz.utc) - timedelta(minutes=30)).isoformat()
    now_str = datetime.now(tz.utc).isoformat()

    try:
        result = supabase_admin.table("sent_slots") \
            .update({"taken_at": now_str}) \
            .is_("taken_at", "null") \
            .in_("course_name", body.scanned_course_names) \
            .not_.in_("slot_key", body.current_slot_keys) \
            .gt("created_at", cutoff) \
            .execute()
        updated = len(result.data) if result.data else 0
        return {"ok": True, "updated": updated}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"mark-taken failed: {exc}")
