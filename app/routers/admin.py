from fastapi import APIRouter, HTTPException, Request, Depends
from app.database import supabase_admin
from app.dependencies import get_current_user
from app.config import settings
from datetime import datetime, timezone, timedelta
import httpx

router = APIRouter(tags=["admin"])

ADMIN_EMAILS = ["dustinkeating87@gmail.com"]

def require_admin(current_user=Depends(get_current_user)):
    if current_user.email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/admin/stats")
def admin_stats(current_user=Depends(require_admin)):
    users = supabase_admin.table("user_profiles").select("id, email, is_active, is_beta, created_at, stripe_subscription_id").execute()
    alerts = supabase_admin.table("alert_profiles").select("id, user_id, active, courses").execute()
    sent = supabase_admin.table("sent_slots").select("id, notified_at").execute()

    total_users = len(users.data or [])
    active_subscribers = len([u for u in (users.data or []) if u.get("is_active") and not u.get("is_beta")])
    beta_users = len([u for u in (users.data or []) if u.get("is_beta")])
    total_alerts = len(alerts.data or [])
    active_alerts = len([a for a in (alerts.data or []) if a.get("active")])
    total_notifications = len(sent.data or [])

    return {
        "total_users": total_users,
        "active_subscribers": active_subscribers,
        "beta_users": beta_users,
        "total_alerts": total_alerts,
        "active_alerts": active_alerts,
        "total_notifications_sent": total_notifications,
        "users": users.data or [],
    }


@router.post("/scraper-heartbeat")
async def scraper_heartbeat(request: Request):
    body = await request.json()
    poll_number = body.get("poll", 0)
    supabase_admin.table("scraper_health").upsert({
        "id": 1,
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        "last_poll": poll_number,
    }).execute()
    return {"ok": True}


@router.get("/admin/scraper-health")
def scraper_health(current_user=Depends(require_admin)):
    result = supabase_admin.table("scraper_health").select("*").eq("id", 1).maybe_single().execute()
    health = result.data or {}

    last_heartbeat = health.get("last_heartbeat")
    if last_heartbeat:
        last_dt = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
        minutes_ago = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
        is_healthy = minutes_ago < 5
    else:
        minutes_ago = None
        is_healthy = False

    return {
        "is_healthy": is_healthy,
        "last_heartbeat": last_heartbeat,
        "last_poll": health.get("last_poll"),
        "minutes_ago": round(minutes_ago, 1) if minutes_ago is not None else None,
    }
