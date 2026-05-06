import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import settings
from app.database import supabase_admin
from app.ip_rate_limit import check_ip_rate_limit
from app.twilio_lookup import LookupBlocked, check_phone
from app.util.phone import hash_phone, is_valid_e164
import httpx
import os

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

CODE_TTL_MINUTES = 10
TOKEN_TTL_MINUTES = 30
RESEND_COOLDOWN_SECONDS = 60
MAX_RESENDS = 3


class SendCodeRequest(BaseModel):
    phone: str


class VerifyPhoneRequest(BaseModel):
    phone: str
    code: str


class ResendCodeRequest(BaseModel):
    phone: str


def _require_free_tier():
    if not settings.free_tier_enabled:
        raise HTTPException(status_code=503, detail="Free tier is not yet available.")


def _send_sms(to: str, body: str) -> None:
    sid = os.environ.get("TWILIO_SID", "")
    token = os.environ.get("TWILIO_TOKEN", "")
    frm = os.environ.get("TWILIO_FROM", "")
    if not (sid and token and frm):
        log.error("send_sms: Twilio env vars not set")
        raise HTTPException(status_code=500, detail="SMS service not configured.")
    r = httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        auth=(sid, token),
        data={"From": frm, "To": to, "Body": body},
        timeout=15,
    )
    r.raise_for_status()


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


@router.post("/send-verification-code")
def send_verification_code(body: SendCodeRequest, request: Request):
    _require_free_tier()

    if not is_valid_e164(body.phone):
        raise HTTPException(status_code=422, detail="Phone must be in E.164 format (e.g. +14155551234).")

    check_ip_rate_limit(request)

    phone_hash = hash_phone(body.phone)

    # Twilio Lookup — block VoIP/disposable. Errors swallowed: Lookup outage should not break signup.
    try:
        check_phone(body.phone)
    except LookupBlocked:
        log.info("send_verification_code: lookup blocked phone_hash=%s", phone_hash[:8])
        # Return success to not reveal blocking decision to caller
        return {"success": True}
    except Exception as exc:
        log.warning("send_verification_code: lookup failed (%s) — proceeding", exc)

    # Phone uniqueness: reject if this phone_hash has already consumed a free-tier alert.
    # Return success without sending — do not reveal whether phone is registered (privacy).
    existing = supabase_admin.table("user_profiles") \
        .select("id") \
        .eq("phone_hash", phone_hash) \
        .not_.is_("free_tier_used_at", "null") \
        .limit(1) \
        .execute()
    if existing.data:
        log.info("send_verification_code: phone already used free tier phone_hash=%s", phone_hash[:8])
        return {"success": True}

    code = _generate_code()
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=CODE_TTL_MINUTES)).isoformat()

    # Delete any existing pending code for this phone, then insert fresh
    supabase_admin.table("phone_verification_codes") \
        .delete() \
        .eq("phone_hash", phone_hash) \
        .eq("used", False) \
        .execute()

    supabase_admin.table("phone_verification_codes").insert({
        "phone_hash": phone_hash,
        "code": code,
        "expires_at": expires_at,
    }).execute()

    try:
        _send_sms(body.phone, f"Your Good Lie Golf verification code is: {code}\nExpires in 10 minutes.")
    except Exception as exc:
        log.error("send_verification_code: SMS send failed — %s", exc)
        raise HTTPException(status_code=500, detail="Failed to send SMS. Please try again.")

    log.info("send_verification_code: code sent phone_hash=%s", phone_hash[:8])
    return {"success": True}


@router.post("/verify-phone")
def verify_phone(body: VerifyPhoneRequest, request: Request):
    _require_free_tier()

    if not is_valid_e164(body.phone):
        raise HTTPException(status_code=422, detail="Phone must be in E.164 format.")

    phone_hash = hash_phone(body.phone)
    now = datetime.now(timezone.utc)

    result = supabase_admin.table("phone_verification_codes") \
        .select("id, code, expires_at") \
        .eq("phone_hash", phone_hash) \
        .eq("used", False) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()

    row = (result.data or [None])[0]

    if not row:
        raise HTTPException(status_code=400, detail="Invalid or expired code.")

    expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    if now > expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired code.")

    if row["code"] != body.code:
        raise HTTPException(status_code=400, detail="Invalid or expired code.")

    verification_token = secrets.token_urlsafe(32)
    token_expires_at = (now + timedelta(minutes=TOKEN_TTL_MINUTES)).isoformat()

    supabase_admin.table("phone_verification_codes").update({
        "used": True,
        "verification_token": verification_token,
        "token_expires_at": token_expires_at,
    }).eq("id", row["id"]).execute()

    log.info("verify_phone: phone verified phone_hash=%s", phone_hash[:8])
    return {"verified": True, "verification_token": verification_token}


@router.post("/resend-verification-code")
def resend_verification_code(body: ResendCodeRequest, request: Request):
    _require_free_tier()

    if not is_valid_e164(body.phone):
        raise HTTPException(status_code=422, detail="Phone must be in E.164 format.")

    phone_hash = hash_phone(body.phone)
    now = datetime.now(timezone.utc)

    result = supabase_admin.table("phone_verification_codes") \
        .select("id, resend_count, last_resend_at, expires_at") \
        .eq("phone_hash", phone_hash) \
        .eq("used", False) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()

    row = (result.data or [None])[0]

    if not row:
        raise HTTPException(
            status_code=404,
            detail="No pending verification found. Use send-verification-code first.",
        )

    expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    if now > expires_at:
        raise HTTPException(
            status_code=400,
            detail="Code expired. Use send-verification-code to request a new one.",
        )

    if row["resend_count"] >= MAX_RESENDS:
        raise HTTPException(
            status_code=429,
            detail="Maximum resends reached. Use send-verification-code to request a new one.",
        )

    if row["last_resend_at"]:
        last_resend = datetime.fromisoformat(row["last_resend_at"].replace("Z", "+00:00"))
        elapsed = (now - last_resend).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            wait = int(RESEND_COOLDOWN_SECONDS - elapsed)
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {wait}s before resending.",
            )

    new_code = _generate_code()
    new_expires_at = (now + timedelta(minutes=CODE_TTL_MINUTES)).isoformat()

    supabase_admin.table("phone_verification_codes").update({
        "code": new_code,
        "expires_at": new_expires_at,
        "resend_count": row["resend_count"] + 1,
        "last_resend_at": now.isoformat(),
    }).eq("id", row["id"]).execute()

    try:
        _send_sms(body.phone, f"Your Good Lie Golf verification code is: {new_code}\nExpires in 10 minutes.")
    except Exception as exc:
        log.error("resend_verification_code: SMS send failed — %s", exc)
        raise HTTPException(status_code=500, detail="Failed to send SMS. Please try again.")

    log.info("resend_verification_code: resent phone_hash=%s resend_count=%d", phone_hash[:8], row["resend_count"] + 1)
    return {"success": True}
