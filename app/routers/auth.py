from fastapi import APIRouter, HTTPException, Depends
from app.schemas import SignupRequest, LoginRequest, SignupFreeTierRequest
from app.database import supabase, supabase_admin
from app.dependencies import get_current_user
from app.config import settings
from datetime import datetime, timezone, timedelta
from app.util.dates import _parse_iso
from app.util.phone import hash_phone, is_valid_e164

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201)
def signup(body: SignupRequest):
    try:
        response = supabase_admin.auth.admin.create_user({
            "email": body.email,
            "password": body.password,
            "email_confirm": True
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not response.user:
        raise HTTPException(status_code=400, detail="Signup failed")

    try:
        session_response = supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "access_token": session_response.session.access_token,
        "refresh_token": session_response.session.refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(response.user.id),
            "email": response.user.email,
        },
    }


@router.post("/signup-free-tier", status_code=201)
def signup_free_tier(body: SignupFreeTierRequest):
    if not settings.free_tier_enabled:
        raise HTTPException(status_code=503, detail="Free tier is not yet available.")

    if not is_valid_e164(body.phone_e164):
        raise HTTPException(status_code=422, detail="phone_e164 must be a valid E.164 phone number")

    phone_hash = hash_phone(body.phone_e164)

    # Validate verification token
    # Use .limit(1).execute() — maybe_single().execute() returns None (not APIResponse)
    # on 0 rows in postgrest-py 0.18, causing AttributeError on .data access.
    token_rows = (
        supabase_admin.table("phone_verification_codes")
        .select("id, token_expires_at, phone_hash")
        .eq("verification_token", body.verification_token)
        .limit(1)
        .execute()
    ).data or []
    if not token_rows:
        raise HTTPException(status_code=401, detail="Invalid or expired verification token")
    row = token_rows[0]
    # Note: used=True is set by verify_phone to mark the OTP consumed (not the verification_token).
    # Do not gate on used here — check token_expires_at and phone_hash instead.
    # Python 3.9 compat: see app/util/dates.py
    now_utc = datetime.now(timezone.utc)
    expires = _parse_iso(row["token_expires_at"])
    if now_utc > expires:
        raise HTTPException(status_code=401, detail="Invalid or expired verification token")
    if row["phone_hash"] != phone_hash:
        raise HTTPException(status_code=401, detail="Invalid or expired verification token")

    # Phone uniqueness: one free-tier account per phone number (lifetime)
    existing_rows = (
        supabase_admin.table("user_profiles")
        .select("id")
        .eq("phone_hash", phone_hash)
        .not_.is_("free_tier_used_at", "null")
        .limit(1)
        .execute()
    ).data or []
    if existing_rows:
        raise HTTPException(status_code=409, detail="Phone number already associated with a free-tier account")

    # Create auth user
    try:
        create_resp = supabase_admin.auth.admin.create_user({
            "email": body.email,
            "password": body.password,
            "email_confirm": True,
        })
    except Exception as e:
        err = str(e).lower()
        if "already" in err or "exists" in err or "registered" in err:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        raise HTTPException(status_code=400, detail=str(e))

    if not create_resp.user:
        raise HTTPException(status_code=400, detail="Signup failed")

    user_id = str(create_resp.user.id)

    # Sign in to get JWT
    try:
        session_resp = supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
    except Exception as e:
        try:
            supabase_admin.auth.admin.delete_user(user_id)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))

    # Compensating-action wrapper: profile update + mark token used
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        supabase_admin.table("user_profiles").update({
            "phone_verified": True,
            "phone_hash": phone_hash,
            "notify_phone": body.phone_e164,
            "free_tier_used_at": now_iso,
        }).eq("id", user_id).execute()

        supabase_admin.table("phone_verification_codes").update({
            "token_expires_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", row["id"]).execute()
    except Exception:
        try:
            supabase_admin.auth.admin.delete_user(user_id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Account setup failed. Please try again.")

    return {
        "access_token": session_resp.session.access_token,
        "refresh_token": session_resp.session.refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "email": create_resp.user.email,
            "tier": "free",
        },
    }


@router.post("/login")
def login(body: LoginRequest):
    try:
        response = supabase.auth.sign_in_with_password({"email": body.email, "password": body.password})
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    if not response.user or not response.session:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(response.user.id),
            "email": response.user.email,
        },
    }


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    result = supabase_admin.table("user_profiles").select("*").eq("id", str(current_user.id)).maybe_single().execute()
    profile = result.data or {}
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "is_active": profile.get("is_active", False),
        "is_beta": profile.get("is_beta", False),
        "stripe_customer_id": profile.get("stripe_customer_id"),
        "notify_email": profile.get("notify_email"),
        "notify_phone": profile.get("notify_phone"),
        "trial_end": profile.get("trial_end"),
        "notify_updated_at": profile.get("notify_updated_at"),
    }


@router.patch("/me")
def update_me(body: dict, current_user=Depends(get_current_user)):
    allowed = {"notify_email", "notify_phone"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    # Check 24-hour rate limit
    result = supabase_admin.table("user_profiles").select("notify_updated_at").eq("id", str(current_user.id)).maybe_single().execute()
    profile = result.data or {}
    last_updated = profile.get("notify_updated_at")
    if last_updated:
        # Python 3.9 compat: see app/util/dates.py
        last_updated_dt = _parse_iso(last_updated)
        if datetime.now(timezone.utc) - last_updated_dt < timedelta(hours=24):
            raise HTTPException(status_code=429, detail="Notification preferences can only be updated once every 24 hours")

    updates["notify_updated_at"] = datetime.now(timezone.utc).isoformat()
    supabase_admin.table("user_profiles").update(updates).eq("id", str(current_user.id)).execute()
    return {"ok": True}


@router.post("/reset-password")
def reset_password(body: dict):
    email = body.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    try:
        supabase.auth.reset_password_for_email(email, {"redirect_to": "https://goodlie.golf/auth/reset"})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.post("/update-password")
def update_password(body: dict, current_user=Depends(get_current_user)):
    password = body.get("password")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    try:
        supabase_admin.auth.admin.update_user_by_id(str(current_user.id), {"password": password})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}
