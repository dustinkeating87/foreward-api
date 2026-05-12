from fastapi import APIRouter, HTTPException, Request, Depends, Query
from typing import Optional
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


@router.get("/admin/users")
def admin_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    current_user=Depends(require_admin),
):
    try:
        users_result = supabase_admin.table("user_profiles").select(
            "id, email, created_at, is_active, is_beta, stripe_customer_id, "
            "stripe_subscription_id, trial_end, notify_phone, phone_verified, "
            "notify_updated_at, free_tier_used_at, free_tier_grace_retry_used_at"
        ).order("created_at", desc=True).execute()

        alerts_result = supabase_admin.table("alert_profiles").select(
            "id, user_id, status, updated_at"
        ).execute()

        sms_result = supabase_admin.table("sent_slots").select(
            "user_id"
        ).not_.is_("user_id", None).execute()
    except Exception as exc:
        log.error("admin_users query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch users")

    alerts_by_user: dict = {}
    for a in alerts_result.data or []:
        uid = a["user_id"]
        alerts_by_user.setdefault(uid, []).append(a)

    sms_by_user: dict = {}
    for row in sms_result.data or []:
        uid = row.get("user_id")
        if uid:
            sms_by_user[uid] = sms_by_user.get(uid, 0) + 1

    now_str = datetime.now(timezone.utc).isoformat()

    def _badge(u: dict) -> str:
        if u.get("is_active") and u.get("stripe_subscription_id"):
            return "Paying"
        if u.get("is_beta") and u.get("is_active"):
            return "Beta"
        if (u.get("trial_end") and u["trial_end"] > now_str
                and not u.get("stripe_subscription_id")
                and not u.get("free_tier_used_at")):
            return "Trial"
        if u.get("free_tier_grace_retry_used_at") and not u.get("is_active"):
            return "Expired"
        if u.get("free_tier_used_at") and not u.get("is_active"):
            return "Free"
        if (u.get("stripe_customer_id") and not u.get("stripe_subscription_id")
                and not u.get("is_active")):
            return "Churned"
        return "Signed up"

    status_filter = {s.strip() for s in status.split(",")} if status else None
    search_lower = search.lower() if search else None

    users = []
    for u in users_result.data or []:
        badge = _badge(u)
        if status_filter and badge not in status_filter:
            continue
        if search_lower and search_lower not in (u.get("email") or "").lower():
            continue

        uid = u["id"]
        user_alerts = alerts_by_user.get(uid, [])
        alerts_active = sum(1 for a in user_alerts if a.get("status") == "active")
        alerts_fired = sum(1 for a in user_alerts if a.get("status") == "fired")
        alerts_expired = sum(1 for a in user_alerts if a.get("status") == "expired")
        alerts_paused = sum(1 for a in user_alerts if a.get("status") == "paused")

        ts_candidates = [t for t in ([u.get("notify_updated_at")]
                         + [a.get("updated_at") for a in user_alerts]) if t]
        last_activity_at = max(ts_candidates) if ts_candidates else None

        phone = u.get("notify_phone") or ""
        notify_phone_last4 = phone[-4:] if len(phone) >= 4 else (phone or None)

        users.append({
            "id": uid,
            "email": u.get("email"),
            "created_at": u.get("created_at"),
            "status": badge,
            "notify_phone_last4": notify_phone_last4 or None,
            "phone_verified": u.get("phone_verified", False),
            "alerts_active": alerts_active,
            "alerts_fired": alerts_fired,
            "alerts_expired": alerts_expired,
            "alerts_paused": alerts_paused,
            "sms_sent_total": sms_by_user.get(uid, 0),
            "last_activity_at": last_activity_at,
            "stripe_customer_id": u.get("stripe_customer_id"),
            "is_beta": u.get("is_beta", False),
            "is_active": u.get("is_active", False),
            "trial_end": u.get("trial_end"),
            "free_tier_used_at": u.get("free_tier_used_at"),
        })

    return {
        "total": len(users),
        "limit": limit,
        "offset": offset,
        "users": users[offset:offset + limit],
    }


@router.get("/admin/alerts")
def admin_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
    tier: Optional[str] = Query(default=None),
    course: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    current_user=Depends(require_admin),
):
    try:
        query = supabase_admin.table("alert_profiles").select(
            "id, user_id, status, is_free_tier, courses, date_from, date_to, "
            "time_from, time_to, players, holes, created_at, updated_at"
        ).order("updated_at", desc=True)

        if status:
            statuses = [s.strip() for s in status.split(",")]
            query = query.eq("status", statuses[0]) if len(statuses) == 1 else query.in_("status", statuses)
        if tier == "free":
            query = query.eq("is_free_tier", True)
        elif tier == "paid":
            query = query.eq("is_free_tier", False)
        if user_id:
            query = query.eq("user_id", user_id)

        alerts_result = query.execute()

        user_ids = list({a["user_id"] for a in (alerts_result.data or []) if a.get("user_id")})
        emails_by_uid: dict = {}
        if user_ids:
            emails_result = supabase_admin.table("user_profiles").select(
                "id, email"
            ).in_("id", user_ids).execute()
            emails_by_uid = {r["id"]: r.get("email") for r in (emails_result.data or [])}
    except Exception as exc:
        log.error("admin_alerts query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch alerts")

    search_lower = search.lower() if search else None
    alerts = []
    for a in alerts_result.data or []:
        email = emails_by_uid.get(a.get("user_id"))
        if course and course not in (a.get("courses") or []):
            continue
        if search_lower and search_lower not in (email or "").lower():
            continue
        alerts.append({
            "id": a["id"],
            "user_id": a.get("user_id"),
            "user_email": email,
            "status": a.get("status"),
            "is_free_tier": a.get("is_free_tier", False),
            "courses": a.get("courses") or [],
            "date_from": a.get("date_from"),
            "date_to": a.get("date_to"),
            "time_from": a.get("time_from"),
            "time_to": a.get("time_to"),
            "players": a.get("players"),
            "holes": a.get("holes"),
            "created_at": a.get("created_at"),
            "updated_at": a.get("updated_at"),
        })

    return {
        "total": len(alerts),
        "limit": limit,
        "offset": offset,
        "alerts": alerts[offset:offset + limit],
    }


@router.get("/admin/recent-fires")
def admin_recent_fires(
    limit: int = Query(default=50, ge=1, le=200),
    since: Optional[str] = Query(default=None),
    current_user=Depends(require_admin),
):
    now = datetime.now(timezone.utc)
    if since:
        try:
            _parse_iso(since)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid 'since' datetime format")
        since_str = since
    else:
        since_str = (now - timedelta(days=7)).isoformat()

    try:
        fires_result = supabase_admin.table("sent_slots").select(
            "id, alert_id, user_id, course_name, tee_time, players, scanned_at, created_at, taken_at"
        ).gte("created_at", since_str).order("created_at", desc=True).limit(limit).execute()

        user_ids = list({r["user_id"] for r in (fires_result.data or []) if r.get("user_id")})
        emails_by_uid: dict = {}
        if user_ids:
            emails_result = supabase_admin.table("user_profiles").select(
                "id, email"
            ).in_("id", user_ids).execute()
            emails_by_uid = {r["id"]: r.get("email") for r in (emails_result.data or [])}
    except Exception as exc:
        log.error("admin_recent_fires query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch recent fires")

    fires = [
        {
            "id": row["id"],
            "alert_id": row.get("alert_id"),
            "user_id": row.get("user_id"),
            "user_email": emails_by_uid.get(row.get("user_id")),
            "course_name": row.get("course_name"),
            "tee_time": row.get("tee_time"),
            "players": row.get("players"),
            "scanned_at": row.get("scanned_at"),
            "created_at": row.get("created_at"),
            "taken_at": row.get("taken_at"),
        }
        for row in fires_result.data or []
    ]
    return {"fires": fires}


@router.get("/admin/course-demand")
def admin_course_demand(current_user=Depends(require_admin)):
    now = datetime.now(timezone.utc)
    cutoff_30d = (now - timedelta(days=30)).isoformat()

    try:
        active_result = supabase_admin.table("alert_profiles").select(
            "courses, user_id"
        ).eq("status", "active").execute()

        fires_result = supabase_admin.table("sent_slots").select(
            "course_name"
        ).gte("created_at", cutoff_30d).not_.is_("course_name", None).execute()
    except Exception as exc:
        log.error("admin_course_demand query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch course demand")

    course_alerts: dict = {}
    course_users: dict = {}
    for row in active_result.data or []:
        uid = row.get("user_id")
        for key in (row.get("courses") or []):
            course_alerts[key] = course_alerts.get(key, 0) + 1
            if uid:
                course_users.setdefault(key, set()).add(uid)

    # sent_slots.course_name is the scraper display name; keyed lowercase for best-effort match
    fires_30d: dict = {}
    for row in fires_result.data or []:
        name = (row.get("course_name") or "").lower()
        if name:
            fires_30d[name] = fires_30d.get(name, 0) + 1

    courses = sorted(
        [
            {
                "course_key": key,
                "course_name": key,  # no mapping table — raw key returned; see closeout note
                "active_alerts": course_alerts[key],
                "fired_alerts_30d": fires_30d.get(key.lower(), 0),
                "unique_users": len(course_users.get(key, set())),
            }
            for key in course_alerts
        ],
        key=lambda x: -x["active_alerts"],
    )
    return {"courses": courses}


@router.get("/admin/course-requests")
def admin_course_requests(current_user=Depends(require_admin)):
    try:
        result = supabase_admin.table("course_requests").select(
            "course_name, email, user_email, created_at"
        ).execute()
    except Exception as exc:
        log.error("admin_course_requests query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch course requests")

    groups: dict = {}
    for row in result.data or []:
        raw_name = row.get("course_name") or ""
        key = raw_name.lower()
        if key not in groups:
            groups[key] = {"canonical_name": raw_name, "created_ats": [], "emails": set()}
        groups[key]["created_ats"].append(row.get("created_at"))
        email = row.get("user_email") or row.get("email")
        if email:
            groups[key]["emails"].add(email)

    requests = []
    for g in groups.values():
        timestamps = sorted(t for t in g["created_ats"] if t)
        requests.append({
            "course_name": g["canonical_name"],
            "request_count": len(g["created_ats"]),
            "first_requested_at": timestamps[0] if timestamps else None,
            "last_requested_at": timestamps[-1] if timestamps else None,
            "requester_emails": sorted(g["emails"])[:10],
        })

    requests.sort(key=lambda x: x["last_requested_at"] or "", reverse=True)
    requests.sort(key=lambda x: x["request_count"], reverse=True)
    return {"requests": requests}
