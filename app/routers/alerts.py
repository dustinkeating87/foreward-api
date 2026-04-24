from fastapi import APIRouter, HTTPException, Depends
from app.schemas import AlertProfileCreate, AlertProfileUpdate
from app.database import supabase_admin
from app.dependencies import get_current_subscribed_user, get_current_user

router = APIRouter(tags=["alerts"])


ALERT_LIMIT = 10

@router.post("/alerts", status_code=201)
def create_alert(body: AlertProfileCreate, ctx=Depends(get_current_subscribed_user)):
    user_id = str(ctx["user"].id)

    # Enforce per-user alert limit
    count_result = supabase_admin.table("alert_profiles").select("id", count="exact").eq("user_id", user_id).execute()
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


@router.get("/alerts")
def list_alerts(ctx=Depends(get_current_subscribed_user)):
    from datetime import date
    user_id = str(ctx["user"].id)
    today = date.today().isoformat()
    # Only return non-expired alerts (date_to >= today)
    result = supabase_admin.table("alert_profiles").select("*").eq("user_id", user_id).gte("date_to", today).order("created_at", desc=True).execute()
    return result.data or []


@router.put("/alerts/{alert_id}")
def update_alert(alert_id: str, body: AlertProfileUpdate, ctx=Depends(get_current_subscribed_user)):
    user_id = str(ctx["user"].id)

    # Verify ownership
    existing = supabase_admin.table("alert_profiles").select("id").eq("id", alert_id).eq("user_id", user_id).maybe_single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    updates = body.model_dump(exclude_none=True, exclude={"course"})
    if "date_from" in updates:
        updates["date_from"] = updates["date_from"].isoformat()
    if "date_to" in updates:
        updates["date_to"] = updates["date_to"].isoformat()

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = supabase_admin.table("alert_profiles").update(updates).eq("id", alert_id).eq("user_id", user_id).execute()
    return result.data[0]


@router.delete("/alerts/{alert_id}", status_code=204)
def delete_alert(alert_id: str, ctx=Depends(get_current_subscribed_user)):
    user_id = str(ctx["user"].id)

    existing = supabase_admin.table("alert_profiles").select("id").eq("id", alert_id).eq("user_id", user_id).maybe_single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    supabase_admin.table("alert_profiles").delete().eq("id", alert_id).eq("user_id", user_id).execute()


@router.get("/alerts/history")
def get_alert_history(current_user=Depends(get_current_user)):
    result = supabase_admin.table("sent_slots").select("*").eq("user_id", str(current_user.id)).order("notified_at", desc=True).limit(100).execute()
    return result.data or []
