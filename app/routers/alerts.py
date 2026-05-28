import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query

from app.config import settings
from app.database import supabase_admin
from app.dependencies import get_current_user, get_current_user_with_profile
from app.email import send_free_tier_signup_email, send_paywall_email
from app.schemas import AlertProfileCreate, AlertProfileUpdate
from app.util.courses import all_keys as _all_course_keys

router = APIRouter(tags=["alerts"])
log = logging.getLogger(__name__)

ALERT_LIMIT = 10


def _validate_courses(courses: list[str]) -> None:
    """Raise 422 if any slug is not in the canonical registry."""
    if not courses:
        return
    known = set(_all_course_keys())
    bad = [c for c in courses if c not in known]
    if bad:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown course slug(s): {bad}. Use GET /courses for valid slugs.",
        )


def _is_paid(profile: dict) -> bool:
    return bool(profile.get("is_active") or profile.get("is_beta"))


def is_user_free_tier(profile: dict) -> bool:
    """True for active free-tier users and lapsed paid users who later used free tier."""
    return bool(profile.get("free_tier_used_at") and not profile.get("is_active"))


def _require_subscription_or_free_tier(profile: dict) -> None:
    """When FREE_TIER_ENABLED=false, replicates get_current_subscribed_user's gate.
    When the flag is on, passes through — the handler does its own branching."""
    if not _is_paid(profile) and not settings.free_tier_enabled:
        raise HTTPException(status_code=403, detail="Active subscription required")


@router.post("/alerts", status_code=201)
def create_alert(body: AlertProfileCreate, ctx=Depends(get_current_user_with_profile)):
    user_id = str(ctx["user"].id)
    profile = ctx["profile"]
    paid = _is_paid(profile)

    _validate_courses(body.courses)

    if paid:
        # Paid path: enforce per-user alert limit, no free-tier columns set
        count_result = (
            supabase_admin.table("alert_profiles")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("status", "active")
            .execute()
        )
        if (count_result.count or 0) >= ALERT_LIMIT:
            raise HTTPException(status_code=400, detail=f"Alert limit reached ({ALERT_LIMIT} maximum)")

        payload = {
            "user_id": user_id,
            "courses": body.courses,
            "date_from": body.date_from.isoformat(),
            "date_to": body.date_to.isoformat(),
            "time_from": body.time_from,
            "time_to": body.time_to,
            "players": body.players,
            "holes": body.holes,
            "notify_email": body.notify_email,
            "notify_phone": body.notify_phone,
            "active": body.active,
        }
        result = supabase_admin.table("alert_profiles").insert(payload).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create alert")
        return result.data[0]

    # Unpaid path
    if is_user_free_tier(profile) and not settings.free_tier_enabled:
        raise HTTPException(status_code=503, detail="Free tier is not yet available.")

    if not settings.free_tier_enabled:
        raise HTTPException(status_code=403, detail="Active subscription required")

    now = datetime.now(timezone.utc)

    # Gate: check for any existing free-tier alert (replaces free_tier_used_at=null check,
    # since free_tier_used_at is now stamped at delivery, not creation)
    existing_ft = (
        supabase_admin.table("alert_profiles")
        .select("id, status")
        .eq("user_id", user_id)
        .eq("is_free_tier", True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not existing_ft.data:
        # First free alert: no prior free-tier alert exists
        payload = {
            "user_id": user_id,
            "courses": body.courses,
            "date_from": body.date_from.isoformat(),
            "date_to": body.date_to.isoformat(),
            "time_from": body.time_from,
            "time_to": body.time_to,
            "players": body.players,
            "holes": body.holes,
            "notify_email": body.notify_email,
            "notify_phone": body.notify_phone,
            "active": body.active,
            "is_free_tier": True,
        }
        result = supabase_admin.table("alert_profiles").insert(payload).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create alert")
        # NOTE: free_tier_used_at is NOT stamped here — it is stamped only on confirmed delivery
        log.info("free_tier_create: alert=%s user=%s", result.data[0]["id"], user_id[:8])
        send_free_tier_signup_email(
            user_email=ctx["user"].email or "",
            course_name=(body.courses or ["unknown"])[0],
            alert_id=result.data[0]["id"],
        )
        return result.data[0]

    # User has a prior free-tier alert — check grace retry eligibility
    if profile.get("free_tier_grace_retry_used_at") is not None:
        if profile.get("paywall_email_sent_at") is None:
            try:
                to = profile.get("notify_email") or profile.get("email") or ctx["user"].email
                if to:
                    send_paywall_email(to)
                    supabase_admin.table("user_profiles").update({
                        "paywall_email_sent_at": now.isoformat(),
                    }).eq("id", user_id).execute()
            except Exception as _e:
                log.error("paywall email failed user=%s: %s", user_id[:8], _e)
        raise HTTPException(status_code=402, detail="Payment required to create alerts")

    # Reuse the existing_ft query result (already fetched above)
    prior = existing_ft.data[0]

    if prior["status"] != "expired":
        raise HTTPException(status_code=402, detail="Payment required to create alerts")

    fired_check = (
        supabase_admin.table("sent_slots")
        .select("id")
        .eq("alert_id", prior["id"])
        .limit(1)
        .execute()
    )
    if fired_check.data:
        raise HTTPException(status_code=402, detail="Payment required to create alerts")

    # Eligible for grace retry: prior alert expired without ever firing
    payload = {
        "user_id": user_id,
        "courses": body.courses,
        "date_from": body.date_from.isoformat(),
        "date_to": body.date_to.isoformat(),
        "time_from": body.time_from,
        "time_to": body.time_to,
        "players": body.players,
        "holes": body.holes,
        "notify_email": body.notify_email,
        "notify_phone": body.notify_phone,
        "active": body.active,
        "is_free_tier": True,
    }
    result = supabase_admin.table("alert_profiles").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create alert")
    supabase_admin.table("user_profiles").update({
        "free_tier_grace_retry_used_at": now.isoformat(),
    }).eq("id", user_id).execute()
    log.info("free_tier_grace_retry: alert=%s user=%s", result.data[0]["id"], user_id[:8])
    return result.data[0]


@router.get("/alerts")
def list_alerts(
    status: Optional[str] = Query(default=None),
    ctx=Depends(get_current_user_with_profile),
):
    _require_subscription_or_free_tier(ctx["profile"])
    user_id = str(ctx["user"].id)
    statuses = [s.strip() for s in status.split(",") if s.strip()] if status else ["active"]

    query = supabase_admin.table("alert_profiles").select("*").eq("user_id", user_id)
    if len(statuses) == 1:
        query = query.eq("status", statuses[0])
    else:
        query = query.in_("status", statuses)

    result = query.order("created_at", desc=True).execute()
    return result.data or []


@router.put("/alerts/{alert_id}")
def update_alert(alert_id: str, body: AlertProfileUpdate, ctx=Depends(get_current_user_with_profile)):
    _require_subscription_or_free_tier(ctx["profile"])
    user_id = str(ctx["user"].id)

    if settings.free_tier_enabled and not _is_paid(ctx["profile"]):
        raise HTTPException(status_code=402, detail="Subscribe to edit alerts")

    existing = (
        supabase_admin.table("alert_profiles")
        .select("id")
        .eq("id", alert_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    updates = body.model_dump(exclude_none=True, exclude={"course"})
    if "courses" in updates:
        _validate_courses(updates["courses"])
    if "date_from" in updates:
        updates["date_from"] = updates["date_from"].isoformat()
    if "date_to" in updates:
        updates["date_to"] = updates["date_to"].isoformat()

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = (
        supabase_admin.table("alert_profiles")
        .update(updates)
        .eq("id", alert_id)
        .eq("user_id", user_id)
        .execute()
    )
    return result.data[0]


@router.delete("/alerts/{alert_id}", status_code=204)
def delete_alert(alert_id: str, ctx=Depends(get_current_user_with_profile)):
    _require_subscription_or_free_tier(ctx["profile"])
    user_id = str(ctx["user"].id)

    if settings.free_tier_enabled and not _is_paid(ctx["profile"]):
        raise HTTPException(status_code=402, detail="Subscribe to manage alerts")

    existing = (
        supabase_admin.table("alert_profiles")
        .select("id")
        .eq("id", alert_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    supabase_admin.table("alert_profiles").delete().eq("id", alert_id).eq("user_id", user_id).execute()


@router.get("/alerts/history")
def get_alert_history(current_user=Depends(get_current_user)):
    result = (
        supabase_admin.table("sent_slots")
        .select("*, alert_profiles(status)")
        .eq("user_id", str(current_user.id))
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    rows = []
    for row in result.data or []:
        alert_data = row.pop("alert_profiles", None) or {}
        row["status"] = alert_data.get("status")
        rows.append(row)
    return rows


@router.post("/alerts/{alert_id}/retry")
def retry_alert(alert_id: str, ctx=Depends(get_current_user_with_profile)):
    from datetime import date
    _require_subscription_or_free_tier(ctx["profile"])
    user_id = str(ctx["user"].id)

    if settings.free_tier_enabled and not _is_paid(ctx["profile"]):
        raise HTTPException(status_code=402, detail="Subscribe to retry alerts")

    existing = (
        supabase_admin.table("alert_profiles")
        .select("id, date_to")
        .eq("id", alert_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    if existing.data["date_to"] < date.today().isoformat():
        raise HTTPException(status_code=400, detail="Alert end date has passed — edit dates before retrying")

    supabase_admin.table("alert_profiles").update({"status": "active"}).eq("id", alert_id).eq("user_id", user_id).execute()
    return {"id": alert_id, "status": "active"}
