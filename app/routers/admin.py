from fastapi import APIRouter, HTTPException, Request, Depends
from app.database import supabase_admin
from app.dependencies import get_current_user
from app.config import settings
from app.email import send_email
from app.captcha_balance import maybe_check_and_alert
from app.util.dates import _parse_iso
from collections import Counter
from datetime import datetime, timezone, timedelta
import httpx
import logging
import os

router = APIRouter(tags=["admin"])
log = logging.getLogger(__name__)

ADMIN_EMAILS = ["dustinkeating87@gmail.com"]
ALERTING_PLATFORMS = ["gtg", "golfnow", "chronogolf"]
ZERO_STREAK_THRESHOLD = 10
PLATFORM_GUIDANCE = {
    "lakeview": "The Lakeview cookie has likely expired. Log in to the scraper dashboard and refresh the session cookie.",
    "gtg": "Check 2captcha balance and account health. Low credits or a banned account will cause silent failures.",
    "golfnow": "Check worker logs and proxy health. GolfNow scraper may be blocked or the proxy pool exhausted.",
}
DEFAULT_GUIDANCE = "Check Railway worker logs for errors or restart the worker."


def require_admin(current_user=Depends(get_current_user)):
    if current_user.email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/admin/stats")
def admin_stats(current_user=Depends(require_admin)):
    users = supabase_admin.table("user_profiles").select("id, email, is_active, is_beta, created_at, stripe_subscription_id").execute()
    alerts = supabase_admin.table("alert_profiles").select("id, user_id, active, courses").execute()
    sent = supabase_admin.table("sent_slots").select("id, created_at").execute()

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
    poll_number = body.get("poll_count") or body.get("poll", 0)

    threshold = int(os.environ.get("ALARM_THRESHOLD_POLLS", "10"))
    alarm_to = os.environ.get("ALARM_EMAIL_TO", "hello@goodlie.golf")
    alarm_from = os.environ.get("ALARM_EMAIL_FROM", "hello@goodlie.golf")

    prev_result = supabase_admin.table("scraper_health").select("*").eq("id", 1).maybe_single().execute()
    prev_data = prev_result.data or {}
    prev_streaks: dict = prev_data.get("consecutive_zero_polls") or {}

    upsert_data = {
        "id": 1,
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        "last_poll": poll_number,
    }

    if "slots_per_platform" in body:
        upsert_data["slots_last_poll"] = body["slots_per_platform"]
    if "consecutive_zero_polls" in body:
        upsert_data["consecutive_zero_polls"] = body["consecutive_zero_polls"]
    if body.get("is_productive"):
        upsert_data["last_productive_poll"] = datetime.now(timezone.utc).isoformat()
    if "captcha_balance" in body:
        try:
            cb = body["captcha_balance"]
            upsert_data["captcha_balance"] = float(cb) if cb is not None else None
        except (ValueError, TypeError) as exc:
            log.warning("invalid captcha_balance in heartbeat: %s", exc)

    supabase_admin.table("scraper_health").upsert(upsert_data).execute()

    new_streaks: dict = body.get("consecutive_zero_polls") or {}
    last_productive = prev_data.get("last_productive_poll")
    admin_url = "https://goodlie.golf/admin"

    all_platforms = set(prev_streaks.keys()) | set(new_streaks.keys())
    for platform in all_platforms:
        prev_count = int(prev_streaks.get(platform) or 0)
        new_count = int(new_streaks.get(platform) or 0)
        try:
            if prev_count < threshold and new_count >= threshold:
                guidance = PLATFORM_GUIDANCE.get(platform, DEFAULT_GUIDANCE)
                subject = f"[Good Lie] {platform.upper()} silent for {new_count} polls (about {new_count} min)"
                lines = [
                    f"Platform: {platform}",
                    f"Consecutive zero-slot polls: {new_count}",
                ]
                if last_productive:
                    lines.append(f"Last productive poll: {last_productive}")
                lines += [
                    "",
                    guidance,
                    "",
                    f"Admin dashboard: {admin_url}",
                ]
                send_email(alarm_to, subject, "\n".join(lines), from_addr=alarm_from)
                log.info("alarm email sent for platform=%s streak=%d", platform, new_count)
            elif prev_count >= threshold and new_count == 0:
                subject = f"[Good Lie] {platform.upper()} recovered"
                body_text = f"{platform} is producing slots again."
                send_email(alarm_to, subject, body_text, from_addr=alarm_from)
                log.info("recovery email sent for platform=%s", platform)
        except Exception as exc:
            log.error("heartbeat email failed for platform=%s: %s", platform, exc)

    try:
        await maybe_check_and_alert(supabase_admin)
    except Exception as exc:
        log.error("maybe_check_and_alert raised unexpectedly: %s", exc)

    return {"ok": True}


def _compute_health(health: dict) -> dict:
    last_heartbeat = health.get("last_heartbeat")
    if last_heartbeat:
        # Python 3.9 compat: see app/util/dates.py
        last_dt = _parse_iso(last_heartbeat)
        minutes_ago = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
        is_healthy = minutes_ago < 5
    else:
        minutes_ago = None
        is_healthy = False

    consecutive = health.get("consecutive_zero_polls") or {}
    platform_alarms = [
        p for p in ALERTING_PLATFORMS
        if (consecutive.get(p) or 0) >= ZERO_STREAK_THRESHOLD
    ]

    return {
        "is_healthy": is_healthy,
        "last_heartbeat": last_heartbeat,
        "last_poll": health.get("last_poll"),
        "minutes_ago": round(minutes_ago, 1) if minutes_ago is not None else None,
        "slots_last_poll": health.get("slots_last_poll"),
        "consecutive_zero_polls": health.get("consecutive_zero_polls"),
        "last_productive_poll": health.get("last_productive_poll"),
        "platform_alarms": platform_alarms,
    }


@router.get("/admin/scraper-health")
def scraper_health(current_user=Depends(require_admin)):
    result = supabase_admin.table("scraper_health").select("*").eq("id", 1).maybe_single().execute()
    return _compute_health(result.data or {})


@router.get("/admin/dashboard")
def admin_dashboard(current_user=Depends(require_admin)):
    health_result = supabase_admin.table("scraper_health").select("*").eq("id", 1).maybe_single().execute()
    health = _compute_health(health_result.data or {})

    now = datetime.now(timezone.utc)
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    cutoff_7d = (now - timedelta(days=7)).isoformat()
    cutoff_30d = (now - timedelta(days=30)).isoformat()

    sent_24h = supabase_admin.table("sent_slots").select("id").gte("created_at", cutoff_24h).execute()
    sent_7d = supabase_admin.table("sent_slots").select("id").gte("created_at", cutoff_7d).execute()

    users = supabase_admin.table("user_profiles").select("id, is_active, is_beta").execute()
    alerts = supabase_admin.table("alert_profiles").select("id, active").execute()

    try:
        slots_raw = supabase_admin.table("sent_slots").select("created_at").gte("created_at", cutoff_30d).limit(5000).execute()
        day_counts = Counter(row["created_at"][:10] for row in (slots_raw.data or []))
        alert_volume_30d = [
            {"date": (now - timedelta(days=i)).strftime("%Y-%m-%d"),
             "count": day_counts.get((now - timedelta(days=i)).strftime("%Y-%m-%d"), 0)}
            for i in range(29, -1, -1)
        ]
    except Exception as exc:
        log.error("alert_volume_30d query failed: %s", exc)
        alert_volume_30d = []

    try:
        active_alerts_raw = supabase_admin.table("alert_profiles").select("courses").eq("active", True).execute()
        course_counts = Counter()
        for row in (active_alerts_raw.data or []):
            for course in (row.get("courses") or []):
                course_counts[course] += 1
        course_coverage = [
            {"course_name": name, "alert_count": count, "platform": "unknown"}
            for name, count in course_counts.most_common(25)
        ]
    except Exception as exc:
        log.error("course_coverage query failed: %s", exc)
        course_coverage = []

    # TODO: add stripe_subscription_status to user_profiles (synced via Stripe webhook) for
    # precise paying/trial/churned counts. Currently inferring from trial_end and stripe_subscription_id.
    try:
        users_full = supabase_admin.table("user_profiles").select(
            "id, is_active, is_beta, stripe_subscription_id, trial_end"
        ).execute()
        users_data = users_full.data or []
        now_str = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        trial_users = sum(
            1 for u in users_data
            if u.get("is_active") and (u.get("trial_end") or "") > now_str
        )
        paying_users = sum(
            1 for u in users_data
            if u.get("is_active")
            and u.get("stripe_subscription_id")
            and (not u.get("trial_end") or u["trial_end"] <= now_str)
        )
        churned_users = sum(
            1 for u in users_data
            if not u.get("is_active") and u.get("stripe_subscription_id")
        )
        user_funnel = {
            "total_users": len(users_data),
            "active_users": sum(1 for u in users_data if u.get("is_active")),
            "beta_users": sum(1 for u in users_data if u.get("is_beta")),
            "paying_users": paying_users,
            "trial_users": trial_users,
            "churned_users": churned_users,
        }
    except Exception as exc:
        log.error("user_funnel query failed: %s", exc)
        user_funnel = None

    return {
        "health": health,
        "activity": {
            "notifications_24h": len(sent_24h.data or []),
            "notifications_7d": len(sent_7d.data or []),
        },
        "system": {
            "total_users": len(users.data or []),
            "active_subscribers": len([u for u in (users.data or []) if u.get("is_active") and not u.get("is_beta")]),
            "beta_users": len([u for u in (users.data or []) if u.get("is_beta")]),
            "total_alerts": len(alerts.data or []),
            "active_alerts": len([a for a in (alerts.data or []) if a.get("active")]),
        },
        "alert_volume_30d": alert_volume_30d,
        "course_coverage": course_coverage,
        "user_funnel": user_funnel,
    }
