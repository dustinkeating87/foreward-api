# Scraper Health Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the scraper heartbeat pipeline to track per-platform slot counts and zero-poll streaks, expose them via updated API endpoints, and add a single-call dashboard endpoint.

**Architecture:** Three sequential commits across two repos. foreward-api/app/routers/admin.py receives all API changes. foreward-scraper/tee_sniper.py adds module-level streak state and enriches the heartbeat payload. Commit 3 is pure verification using live Railway deployments.

**Tech Stack:** FastAPI + supabase-py (API), Python + httpx (scraper), Supabase Postgres (DB), Railway (deploy), curl (verification)

---

## Pre-flight: Verify DB Migration

Before touching any code, confirm the three new columns exist in Supabase.

- [ ] **Step 1: Confirm migration columns**

You need the Supabase service key. Ask the user or run from the API's `.env`:

```bash
curl -s "https://<SUPABASE_PROJECT_REF>.supabase.co/rest/v1/rpc/sql" \
  -H "apikey: <SERVICE_KEY>" \
  -H "Authorization: Bearer <SERVICE_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT column_name FROM information_schema.columns WHERE table_name = '\''scraper_health'\'' ORDER BY ordinal_position"}'
```

Expected: response includes `slots_last_poll`, `consecutive_zero_polls`, `last_productive_poll`.

If any are missing, stop. The migration was not applied. Do not proceed.

---

## Commit 1: foreward-api -- Extend admin.py

**Files:**
- Modify: `foreward-api/app/routers/admin.py` (74 lines -> ~130 lines)

### Task 1: Add constants and fix heartbeat POST

- [ ] **Step 1: Add constants and rewrite scraper_heartbeat**

Replace the existing `scraper_heartbeat` function and add constants directly below the `ADMIN_EMAILS` line. Full replacement for lines 10-51:

```python
ADMIN_EMAILS = ["dustinkeating87@gmail.com"]
ALERTING_PLATFORMS = ["gtg", "golfnow", "ezlinks"]
ZERO_STREAK_THRESHOLD = 10


def require_admin(current_user=Depends(get_current_user)):
    if current_user.email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.post("/scraper-heartbeat")
async def scraper_heartbeat(request: Request):
    body = await request.json()
    poll_number = body.get("poll_count") or body.get("poll", 0)

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

    supabase_admin.table("scraper_health").upsert(upsert_data).execute()
    return {"ok": True}
```

- [ ] **Step 2: Add shared _compute_health helper**

Insert this function immediately before the existing `scraper_health` GET endpoint (after the new POST, before line 54):

```python
def _compute_health(health: dict) -> dict:
    last_heartbeat = health.get("last_heartbeat")
    if last_heartbeat:
        last_dt = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
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
```

- [ ] **Step 3: Replace scraper_health GET to use helper**

Replace the existing `scraper_health` GET function (lines 54-73) with:

```python
@router.get("/admin/scraper-health")
def scraper_health(current_user=Depends(require_admin)):
    result = supabase_admin.table("scraper_health").select("*").eq("id", 1).maybe_single().execute()
    return _compute_health(result.data or {})
```

- [ ] **Step 4: Add dashboard endpoint**

Append to the end of `admin.py`:

```python
@router.get("/admin/dashboard")
def admin_dashboard(current_user=Depends(require_admin)):
    health_result = supabase_admin.table("scraper_health").select("*").eq("id", 1).maybe_single().execute()
    health = _compute_health(health_result.data or {})

    now = datetime.now(timezone.utc)
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    cutoff_7d = (now - timedelta(days=7)).isoformat()

    sent_24h = supabase_admin.table("sent_slots").select("id").gte("notified_at", cutoff_24h).execute()
    sent_7d = supabase_admin.table("sent_slots").select("id").gte("notified_at", cutoff_7d).execute()

    users = supabase_admin.table("user_profiles").select("id, is_active, is_beta").execute()
    alerts = supabase_admin.table("alert_profiles").select("id, active").execute()

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
    }
```

- [ ] **Step 5: Verify final file looks correct**

Run:
```bash
cd ~/foreward-api && python -c "import ast; ast.parse(open('app/routers/admin.py').read()); print('syntax OK')"
```
Expected: `syntax OK`

- [ ] **Step 6: Commit**

```bash
cd ~/foreward-api
git add app/routers/admin.py
git commit -m "feat: extend scraper-heartbeat and add dashboard endpoint

- Accept both poll/poll_count field names in POST body
- Write slots_last_poll, consecutive_zero_polls, last_productive_poll when present
- Extend GET /admin/scraper-health with new fields + platform_alarms
- Add GET /admin/dashboard returning health + 24h/7d activity + system stats
- Add ALERTING_PLATFORMS and ZERO_STREAK_THRESHOLD constants"
```

Record the commit SHA. Hand back to user:
- SHA from `git rev-parse HEAD`
- Curl to run after Railway deploys (user supplies bearer token):
  ```bash
  curl -s -H "Authorization: Bearer <TOKEN>" https://<API_HOST>/admin/scraper-health | jq .
  ```
- Expected: response includes `slots_last_poll`, `consecutive_zero_polls`, `last_productive_poll`, `platform_alarms` keys (all null/empty until commit 2 deploys)

- [ ] **Step 7: Push to main (triggers Railway deploy)**

```bash
cd ~/foreward-api && git push origin main
```

---

## Commit 2: foreward-scraper -- Enrich heartbeat payload

**Files:**
- Modify: `foreward-scraper/tee_sniper.py` (two locations: module-level ~line 32, heartbeat block ~line 1137)

### Task 2: Add streak state and enrich heartbeat

- [ ] **Step 1: Add module-level streak tracker**

After the existing `_proxy_failures: dict[str, int] = {}` line (~line 32), insert:

```python
_consecutive_zero_polls: dict[str, int] = {}
```

- [ ] **Step 2: Enrich the heartbeat payload**

Find the heartbeat block starting at ~line 1137:
```python
            # POST heartbeat to API
            _api_url = os.environ.get("ALERTS_API_URL", "")
```

Replace the entire block through the end of the heartbeat try/except (lines 1137-1153) with:

```python
            # POST heartbeat to API
            _api_url = os.environ.get("ALERTS_API_URL", "")
            _api_key = os.environ.get("ALERTS_API_KEY", "")
            if _api_url and _api_key:
                try:
                    slots_per_platform = {
                        "gtg": gtg_count,
                        "ezlinks": len(ezlinks_slots),
                        "golfnow": len(golfnow_slots),
                        "chronogolf": len(chronogolf_slots),
                    }

                    for platform, count in slots_per_platform.items():
                        if count > 0:
                            _consecutive_zero_polls[platform] = 0
                        else:
                            _consecutive_zero_polls[platform] = _consecutive_zero_polls.get(platform, 0) + 1

                    is_productive = any(v > 0 for v in slots_per_platform.values())

                    from urllib.parse import urlparse, urlunparse
                    _parsed = urlparse(_api_url)
                    _hb_url = urlunparse(_parsed._replace(path="/scraper-heartbeat"))
                    async with httpx.AsyncClient(timeout=5) as _client:
                        await _client.post(
                            _hb_url,
                            json={
                                "timestamp": time.time(),
                                "poll_count": polls_this_session,
                                "slots_per_platform": slots_per_platform,
                                "consecutive_zero_polls": dict(_consecutive_zero_polls),
                                "is_productive": is_productive,
                            },
                            headers={"X-Api-Key": _api_key},
                        )
                    log.info("Heartbeat sent (poll #%d, productive=%s)", polls_this_session, is_productive)
                except Exception as _exc:
                    log.warning("Heartbeat failed: %s", _exc)
```

- [ ] **Step 3: Verify syntax**

```bash
cd ~/foreward-scraper && python -c "import ast; ast.parse(open('tee_sniper.py').read()); print('syntax OK')"
```
Expected: `syntax OK`

- [ ] **Step 4: Commit**

```bash
cd ~/foreward-scraper
git add tee_sniper.py
git commit -m "feat: enrich heartbeat with per-platform slot counts and zero-poll streaks

- Track _consecutive_zero_polls per platform in module-level state
- Send slots_per_platform, consecutive_zero_polls, is_productive in POST payload
- Reset streak to 0 when count > 0, increment when count == 0"
```

Record SHA from `git rev-parse HEAD`.

- [ ] **Step 5: Push to main (triggers Railway deploy)**

```bash
cd ~/foreward-scraper && git push origin main
```

Hand back to user:
- Scraper commit SHA
- Tell user: wait ~2 minutes for Railway to deploy, then run next verification

---

## Commit 3: Verification

This commit is observational only. No code changes.

- [ ] **Step 1: Verify /admin/scraper-health returns new fields**

Ask user to supply bearer token, then run:
```bash
curl -s \
  -H "Authorization: Bearer <TOKEN>" \
  https://<API_HOST>/admin/scraper-health | jq .
```

Expected response shape:
```json
{
  "is_healthy": true,
  "last_heartbeat": "2026-04-26T...",
  "last_poll": 42,
  "minutes_ago": 0.3,
  "slots_last_poll": {"gtg": 12, "ezlinks": 0, "golfnow": 5, "chronogolf": 3},
  "consecutive_zero_polls": {"gtg": 0, "ezlinks": 1, "golfnow": 0, "chronogolf": 0},
  "last_productive_poll": "2026-04-26T...",
  "platform_alarms": []
}
```

`slots_last_poll` and `consecutive_zero_polls` must be non-null objects, not `{}` or `null`. If they are null, commit 2 has not deployed yet -- wait and retry.

- [ ] **Step 2: Verify /admin/dashboard returns expected shape**

```bash
curl -s \
  -H "Authorization: Bearer <TOKEN>" \
  https://<API_HOST>/admin/dashboard | jq .
```

Expected:
```json
{
  "health": { ... same shape as scraper-health ... },
  "activity": {
    "notifications_24h": <integer>,
    "notifications_7d": <integer>
  },
  "system": {
    "total_users": <integer>,
    "active_subscribers": <integer>,
    "beta_users": <integer>,
    "total_alerts": <integer>,
    "active_alerts": <integer>
  }
}
```

- [ ] **Step 3: Confirm Supabase DB directly**

Query via Supabase SQL editor or psql:
```sql
SELECT
  slots_last_poll,
  consecutive_zero_polls,
  last_productive_poll
FROM public.scraper_health
WHERE id = 1;
```

Expected: `slots_last_poll` and `consecutive_zero_polls` are non-empty JSON objects (not `{}` or null). `last_productive_poll` is a timestamp if any platform returned slots since deploy.

- [ ] **Step 4: Report results to user**

Return:
- API commit SHA (foreward-api)
- Scraper commit SHA (foreward-scraper)
- Actual curl output from steps 1 and 2
- Supabase query result from step 3
- Any platform_alarms present and whether they are expected given current streak data
