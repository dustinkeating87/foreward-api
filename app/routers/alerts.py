import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query

from app.config import settings
from app.database import supabase_admin
from app.dependencies import get_current_user, get_current_user_with_profile
from app.schemas import AlertProfileCreate, AlertProfileUpdate

router = APIRouter(tags=["alerts"])
log = logging.getLogger(__name__)

ALERT_LIMIT = 10


def _is_paid(profile: dict) -> bool:
    return bool(profile.get("is_active") or profile.get("is_beta"))


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
    if not settings.free_tier_enabled:
        raise HTTPException(status_code=403, detail="Active subscription required")

    if profile.get("final_expired_at"):
        # Phone permanently ineligible for free tier
        raise HTTPException(status_code=402, detail="Payment required to create alerts")

    if profile.get("free_tier_used_at"):
        # Already consumed their one free alert
        raise HTTPException(status_code=402, detail="Payment required to create additional alerts")

    # Free-tier requires exactly one course
    if len(body.courses) != 1:
        raise HTTPException(status_code=400, detail="Free-tier alerts must target exactly one course.")

    course_key = body.courses[0]

    # Course must be actively polled by at least one paid alert
    polled = (
        supabase_admin.table("alert_profiles")
        .select("id", count="exact")
        .eq("status", "active")
        .eq("is_free_tier", False)
        .contains("courses", [course_key])
        .limit(1)
        .execute()
    )
    if not (polled.count and polled.count > 0):
        raise HTTPException(
            status_code=400,
            detail="This course isn't currently being monitored. Try one of the available courses.",
        )

    now = datetime.now(timezone.utc)
    polling_expires_at = (now + timedelta(days=14)).isoformat()

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
        "polling_expires_at": polling_expires_at,
        "renewals_used": 0,
    }

    result = supabase_admin.table("alert_profiles").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create alert")

    # Mark free-tier as consumed on the user profile. Set once, never cleared.
    supabase_admin.table("user_profiles").update({
        "free_tier_used_at": now.isoformat(),
    }).eq("id", user_id).execute()

    log.info(
        "free_tier_create: alert=%s user=%s expires=%s",
        result.data[0]["id"],
        user_id[:8],
        polling_expires_at,
    )
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
    paid = _is_paid(ctx["profile"])

    existing = (
        supabase_admin.table("alert_profiles")
        .select("id, is_free_tier, status")
        .eq("id", alert_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Free-tier paywall: editing a fired alert requires subscription
    if (
        settings.free_tier_enabled
        and existing.data.get("is_free_tier")
        and existing.data.get("status") == "fired"
        and not paid
    ):
        raise HTTPException(status_code=402, detail="Subscribe to edit and retry alerts")

    updates = body.model_dump(exclude_none=True, exclude={"course"})
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
    paid = _is_paid(ctx["profile"])

    existing = (
        supabase_admin.table("alert_profiles")
        .select("id, date_to, is_free_tier")
        .eq("id", alert_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    if existing.data["date_to"] < date.today().isoformat():
        raise HTTPException(status_code=400, detail="Alert end date has passed — edit dates before retrying")

    # Free-tier paywall: retry requires a subscription
    if settings.free_tier_enabled and existing.data.get("is_free_tier") and not paid:
        raise HTTPException(status_code=402, detail="Subscribe to retry alerts")

    supabase_admin.table("alert_profiles").update({"status": "active"}).eq("id", alert_id).eq("user_id", user_id).execute()
    return {"id": alert_id, "status": "active"}


@router.post("/alerts/{alert_id}/renew")
def renew_alert(alert_id: str, ctx=Depends(get_current_user_with_profile)):
    if not settings.free_tier_enabled:
        raise HTTPException(status_code=503, detail="Free tier is not yet available.")

    user_id = str(ctx["user"].id)

    existing = (
        supabase_admin.table("alert_profiles")
        .select("id, is_free_tier, renewals_used, expiry_state")
        .eq("id", alert_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert = existing.data

    if not alert.get("is_free_tier"):
        raise HTTPException(status_code=400, detail="Renewal is not applicable to this alert")

    renewals_used = alert.get("renewals_used") or 0
    if renewals_used >= 2:
        raise HTTPException(status_code=402, detail="Maximum renewals reached. Subscribe to continue.")

    if alert.get("expiry_state") != "expired_pending_renewal":
        raise HTTPException(status_code=400, detail="Alert is not pending renewal")

    now = datetime.now(timezone.utc)
    new_expires = (now + timedelta(days=14)).isoformat()
    new_renewals_used = renewals_used + 1

    supabase_admin.table("alert_profiles").update({
        "renewals_used": new_renewals_used,
        "polling_expires_at": new_expires,
        "expiry_state": None,
        "status": "active",
    }).eq("id", alert_id).execute()

    log.info(
        "free_tier_renew: alert=%s renewals_used=%d expires=%s",
        alert_id,
        new_renewals_used,
        new_expires,
    )
    return {
        "id": alert_id,
        "status": "active",
        "polling_expires_at": new_expires,
        "renewals_used": new_renewals_used,
    }
