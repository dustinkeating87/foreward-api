# Block 3: Free-Tier Alert Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the complete free-tier alert lifecycle — creation gating, 14-day polling window, 2-renewal cap, async expiry sweep with email triggers and Stripe coupon generation, paywall gates on retry/edit — all behind `FREE_TIER_ENABLED=false` with zero prod behavior change.

**Architecture:** New behavior lives entirely in `foreward-api`. The expiry sweep is an asyncio background task (`free_tier_expiry_loop`) mirroring `heartbeat_monitor_loop` — placed in the API (not the scraper) because Stripe SDK and `app/email.py` are API-only dependencies. A shared `app/util/dates.py` module is introduced for `_parse_iso`, which also closes `86ahbacxw` (3 existing sites patched in the same task). Email stubs (plain-text, stable signatures) are added now so the sweep is end-to-end testable; Block 4 swaps internals without touching call sites. No new DB migration — Block 1 already added all required columns.

**Tech Stack:** FastAPI, supabase-py (service role), stripe-python, `app/email.py` (SendGrid via httpx), asyncio background tasks, Python 3.9.6 local / 3.11 Railway.

---

## ✅ Ambiguities — All Approved

| # | Decision | Status |
|---|----------|--------|
| 1 | **Expiry sweep in API, not scraper** — Stripe SDK and `app/email.py` are API-only. Scraper would need both added as dependencies. | ✅ Approved |
| 2 | **Task 1 closes 86ahbacxw** — `app/util/dates.py` created here; all 4 fromisoformat sites migrated in same commit. | ✅ Approved |
| 3 | **Email stubs in Block 3** — plain-text bodies, stable signatures. Block 4 swaps internals only. | ✅ Approved |
| 4 | **Zero-active-paid-alerts scenario** — empty course list is correct behavior; pre-launch checklist ticket filed (see below). | ✅ Approved |
| 5 | **Gate existing `PUT /alerts/{id}`, no `PATCH` alias** | ✅ Approved |

**Additions incorporated:**

- **Railway autoscale:** Task 0 verifies `sleep on idle` is OFF before any code changes. If ON, the 5-min asyncio background task is unreliable and we'd need an external Railway Cron instead.
- **Python 3.9 compat comments:** `# Python 3.9 compat: see app/util/dates.py` added at each of the 4 migration sites (above the `_parse_iso(...)` call, or on the import line for `phone_verification.py`).
- **Stable email signatures:** documented below in Design Decisions. Block 4 never touches call sites.
- **Empty-courses response:** `{courses: [], count: 0, available: false}` — frontend can render a meaningful empty state. Pre-launch checklist ticket filed: verify N≥2 courses with active paid alerts before Block 9.
- **`PUT` confirmed, no `PATCH`.**

---

## Design Decisions (Pinned)

### 1. `is_free_tier` × `is_paid` × alert caps

| User state | `_is_paid()` | Alert cap | Free-tier path? |
|---|---|---|---|
| `is_active=true` (paid) | `True` | 10-alert cap | No — paid path always |
| `is_beta=true` | `True` | 10-alert cap | No — paid path always |
| Neither, `free_tier_used_at IS NULL` | `False` | 1 alert (enforced via `free_tier_used_at`) | Yes, when flag on |
| Neither, `free_tier_used_at IS NOT NULL`, `final_expired_at IS NULL` | `False` | 0 (already used) → 402 | Blocked |
| Neither, `final_expired_at IS NOT NULL` | `False` | 0 (permanently blocked) → 402 | Permanently blocked |

Key points:
- The **10-alert cap** is only checked in the paid branch of `create_alert`. Free-tier users never hit it.
- `is_free_tier` is a column on `alert_profiles` (marks which alerts were created under free tier) — it has no effect on which cap applies to future alerts.
- If a free-tier user later subscribes (`is_active=true`), their next alert goes through the **paid path** and counts toward the 10-alert cap. Their old `is_free_tier=true` alert also counts toward that cap (it's included in the `status='active'` count query).
- The expiry sweep **skips alerts for users who are now paid** — no point expiring a paying customer's alert or sending them "no times opened up" emails.

### 2. Rollback symmetry: `FREE_TIER_ENABLED=false`

Every free-tier path returns a non-2xx response when the flag is off. Verified at each endpoint:

| Endpoint | Flag off → response |
|---|---|
| `POST /auth/send-verification-code` | 503 (existing `_require_free_tier()`) |
| `POST /auth/verify-phone` | 503 (existing) |
| `POST /auth/resend-verification-code` | 503 (existing) |
| `GET /courses/available-for-free-tier` | 503 (Task 5) |
| `POST /alerts/{id}/renew` | 503 (Task 6) |
| `POST /alerts` for non-paid user | 403 (`_require_subscription_or_free_tier` + unpaid branch check) |
| `GET /alerts` for non-paid user | 403 |
| `PUT /alerts/{id}` for non-paid user | 403 |
| `DELETE /alerts/{id}` for non-paid user | 403 |
| `POST /alerts/{id}/retry` for non-paid user | 403 |
| Expiry sweep | Runs but is a no-op (no free-tier alerts can be created when flag is off; if any exist from testing, they will still be processed — this is correct) |

The sweep itself does **not** check `FREE_TIER_ENABLED`. It processes whatever `is_free_tier=true` alerts exist. In prod with the flag off, none exist.

### 3. Integration tests: none in Block 3

**Decision:** no FastAPI TestClient or DB-mock integration tests in this block.

**Rationale:** the project has no existing TestClient harness. Introducing one requires mocking `supabase_admin` across all modules — a non-trivial setup that belongs in a separate test-infrastructure block if ever warranted. All pure business logic is unit-tested in Task 9. The AC table serves as the integration test spec, verified manually via curl against local uvicorn. Railway logs are the production integration check post-deploy.

### 4. Email signature contract (stable through Block 4)

These signatures are frozen. Block 4 replaces only the function bodies (swap plain-text for SendGrid template calls). Call sites in `free_tier_expiry.py` never change.

```python
send_free_tier_expiry_email(to: str, alert_id: str, renewals_used: int, renewal_link: str) -> None
send_final_expiry_email(to: str, discount_code: str | None) -> None
```

---

## File Map

```
Create:
  app/util/dates.py                 ← _parse_iso() shared helper (closes 86ahbacxw)
  app/stripe_coupons.py             ← create_one_time_coupon(user_id, coupon_id) → str
  app/free_tier_expiry.py           ← async expiry sweep: check_free_tier_expiry() + loop
  app/routers/courses.py            ← GET /courses/available-for-free-tier
  tests/test_free_tier_logic.py     ← unit tests for _parse_iso + business-logic helpers

Modify:
  app/config.py                     ← add stripe_free_tier_coupon_id: str = ""
                                       add frontend_url: str = "http://localhost:3000"
  app/email.py                      ← add send_free_tier_expiry_email(), send_final_expiry_email()
  app/dependencies.py               ← add get_current_user_with_profile() (no subscription gate)
  app/routers/alerts.py             ← free-tier gating on create/PUT/retry; new /renew endpoint;
                                       switch list/delete to get_current_user_with_profile
  app/routers/phone_verification.py ← replace local _parse_iso with import (86ahbacxw)
  app/heartbeat_monitor.py          ← replace raw fromisoformat with _parse_iso (86ahbacxw)
  app/routers/auth.py               ← replace raw fromisoformat with _parse_iso (86ahbacxw)
  app/routers/admin.py              ← replace raw fromisoformat with _parse_iso (86ahbacxw)
  app/main.py                       ← register courses router; start free_tier_expiry_loop task
```

---

## Acceptance Criteria

| AC | Description | How to verify |
|----|-------------|---------------|
| AC0 | Railway `web` service has `sleep on idle` OFF | Task 0 — check Railway dashboard before any code |
| AC1 | Flag off → zero behavior change for paid users | Run paid flow with `FREE_TIER_ENABLED=false`; all endpoints behave as before |
| AC2 | Flag on → first free alert creation succeeds | `POST /alerts` with free-tier JWT; alert has `is_free_tier=true`, `polling_expires_at` set 14 days out, `user_profiles.free_tier_used_at` set |
| AC3 | Second alert from same user returns 402 | `POST /alerts` second time with same JWT; confirm 402 |
| AC4 | Course polled check blocks unmonitored course | Request alert for course not in any active non-free-tier alert; confirm 400 |
| AC5 | `/renew` transitions `expired_pending_renewal → active` | Manually set `expiry_state='expired_pending_renewal'` in SQL Editor, call `POST /alerts/{id}/renew`; confirm `status=active`, `polling_expires_at` extended, `renewals_used` incremented |
| AC6 | Renewal blocked after 2 renewals | Set `renewals_used=2`, call renew; confirm 402 |
| AC7 | Expiry sweep: `renewals_used < 2` → `expired_pending_renewal` | Set `polling_expires_at` to past in SQL Editor, wait up to 5 min; confirm `expiry_state='expired_pending_renewal'`, `status='expired'`, renewal email logged |
| AC8 | Expiry sweep: `renewals_used=2` → `final_expired` on both rows | Set `renewals_used=2`, `polling_expires_at` to past; confirm `alert_profiles.expiry_state='final_expired'` AND `user_profiles.final_expired_at` set; Stripe promo code visible in test dashboard |
| AC9 | Sweep skips paid users | Set `is_active=true` on user, set alert `polling_expires_at` to past; confirm sweep logs skip, alert NOT transitioned |
| AC10 | Retry gate: free-tier + not paid → 402 | `POST /alerts/{id}/retry` as free-tier user with flag on; confirm 402 |
| AC11 | Edit gate: free-tier + fired + not paid → 402 | Set alert `is_free_tier=true, status=fired`; `PUT /alerts/{id}`; confirm 402 |
| AC12 | Courses endpoint returns `{courses, count, available}` | `GET /courses/available-for-free-tier`; confirm shape; confirm empty state when no active paid alerts |
| AC13 | All unit tests pass | `pytest tests/ -v` — all pass |

---

## Task 0: Pre-Implementation Railway Verification

**Do this before touching any code.**

- [ ] **Step 1: Verify Railway `web` service sleep setting**

Open Railway dashboard → project `spirited-youthfulness` → service `web` → Settings.

Look for "Sleep" or "Idle" setting. **Confirm it is OFF.**

If it is ON: the `free_tier_expiry_loop` asyncio task will be killed when the service idles between requests. In that case, **do not implement the asyncio background task approach**. Instead, use a Railway Cron Job (separate service, calls a new `POST /internal/run-free-tier-expiry` endpoint secured by API key). Flag this to Dustin before proceeding — it changes Tasks 7 and 8 substantially.

The scraper heartbeat fires every 60s, so in normal operation the service stays alive. But verify explicitly before assuming.

- [ ] **Step 2: Confirm `STRIPE_FREE_TIER_COUPON_ID` strategy**

This env var will point to a Stripe Coupon ID (e.g. `FREE50`) configured in Stripe test mode. Block 4 sets up the coupon. For Block 3, the var defaults to `""` (empty string) — the sweep logs a warning and skips coupon generation, but still sends the final expiry email. This is intentional: Block 3 is fully functional without Block 4 being done.

No action needed — just confirm understanding.

---

## Task 1: Create `app/util/dates.py` and migrate all 4 fromisoformat sites

**Files:**
- Create: `app/util/dates.py`
- Modify: `app/routers/phone_verification.py`
- Modify: `app/heartbeat_monitor.py` (line 30)
- Modify: `app/routers/auth.py` (line 93)
- Modify: `app/routers/admin.py` (line 147)

**Closes:** ClickUp `86ahbacxw`

- [ ] **Step 1: Confirm the sites before touching anything**

```bash
cd ~/foreward-api && source .venv/bin/activate
grep -n "fromisoformat" app/heartbeat_monitor.py app/routers/auth.py app/routers/admin.py app/routers/phone_verification.py
```

Expected (4 lines):
```
app/heartbeat_monitor.py:30:        last_dt = datetime.fromisoformat(last_hb.replace("Z", "+00:00"))
app/routers/auth.py:93:        last_updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
app/routers/admin.py:147:        last_dt = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
app/routers/phone_verification.py:65:    ts = ts.replace("Z", "+00:00")
```

If there are additional sites (Block 5 may have introduced more), patch those too.

- [ ] **Step 2: Create `app/util/dates.py`**

```python
import re
from datetime import datetime


def _parse_iso(ts: str) -> datetime:
    # Python 3.9 fromisoformat rejects fractional seconds unless exactly 0, 3, or 6 digits.
    # Supabase/PostgREST returns any precision. Normalize to 6 digits before parsing.
    ts = ts.replace("Z", "+00:00")
    ts = re.sub(r"\.(\d+)(?=[+-])", lambda m: "." + m.group(1).ljust(6, "0")[:6], ts)
    return datetime.fromisoformat(ts)
```

- [ ] **Step 3: Update `app/routers/phone_verification.py`**

Change the imports block — remove `import re`, add the dates import with compat comment:

```python
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

# Python 3.9 compat: see app/util/dates.py
from app.util.dates import _parse_iso
```

Delete the local `_parse_iso` function definition (the entire block from `def _parse_iso(ts: str) -> datetime:` through its closing line, currently lines 65–70).

- [ ] **Step 4: Update `app/heartbeat_monitor.py` line 30**

Add to imports at the top:
```python
from app.util.dates import _parse_iso
```

Change line 30 from:
```python
        last_dt = datetime.fromisoformat(last_hb.replace("Z", "+00:00"))
```
to:
```python
        # Python 3.9 compat: see app/util/dates.py
        last_dt = _parse_iso(last_hb)
```

- [ ] **Step 5: Update `app/routers/auth.py` line 93**

Add to imports at the top:
```python
from app.util.dates import _parse_iso
```

Change line 93 from:
```python
        last_updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
```
to:
```python
        # Python 3.9 compat: see app/util/dates.py
        last_updated_dt = _parse_iso(last_updated)
```

- [ ] **Step 6: Update `app/routers/admin.py` line 147**

Add to imports at the top:
```python
from app.util.dates import _parse_iso
```

Change line 147 from:
```python
        last_dt = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
```
to:
```python
        # Python 3.9 compat: see app/util/dates.py
        last_dt = _parse_iso(last_heartbeat)
```

- [ ] **Step 7: Verify clean compile**

```bash
python -m compileall app/
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add app/util/dates.py app/routers/phone_verification.py app/heartbeat_monitor.py app/routers/auth.py app/routers/admin.py
git commit -m "$(cat <<'EOF'
refactor: lift _parse_iso to app/util/dates, patch all 4 fromisoformat sites

Closes ClickUp 86ahbacxw. Python 3.9 fromisoformat rejects non-6-digit
fractional seconds; Supabase can return any precision. Shared helper now
normalizes before parsing at all call sites.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `app/config.py` and `app/stripe_coupons.py`

**Files:**
- Modify: `app/config.py`
- Create: `app/stripe_coupons.py`

- [ ] **Step 1: Update `app/config.py`**

Full file after changes:
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_price_id: str
    export_api_key: str = ""
    base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    success_url: str = "http://localhost:3000/success"
    cancel_url: str = "http://localhost:3000/cancel"
    free_tier_enabled: bool = False
    stripe_free_tier_coupon_id: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
```

Two new fields:
- `frontend_url` — used in expiry emails for the renewal link (points to Lovable frontend, not API). Set `FRONTEND_URL=https://goodlie.golf` in Railway `web` env.
- `stripe_free_tier_coupon_id` — Stripe Coupon ID for the 50%-off code (Block 4 configures the coupon, Block 4 sets this env var). Defaults to `""` — sweep skips coupon generation when unset.

- [ ] **Step 2: Create `app/stripe_coupons.py`**

```python
import time
import logging
import stripe
from app.config import settings

log = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key


def create_one_time_coupon(user_id: str, coupon_id: str) -> str:
    """
    Generate a single-use Stripe PromotionCode tied to coupon_id.
    coupon_id is the underlying Stripe Coupon ID (e.g. "FREE50PCT"),
    configured once in the Stripe dashboard in Block 4.
    Returns the human-readable promo code string (e.g. "ABCD1234").
    """
    expires_at = int(time.time()) + 7 * 24 * 3600  # 7 days from now
    promo = stripe.PromotionCode.create(
        coupon=coupon_id,
        max_redemptions=1,
        expires_at=expires_at,
        metadata={"supabase_user_id": user_id},
    )
    log.info("stripe_coupon: created promo_code=%s for user=%s", promo.code, user_id[:8])
    return promo.code
```

- [ ] **Step 3: Verify parse**

```bash
python -m compileall app/config.py app/stripe_coupons.py
```

- [ ] **Step 4: Commit**

```bash
git add app/config.py app/stripe_coupons.py
git commit -m "$(cat <<'EOF'
feat: add frontend_url + stripe_free_tier_coupon_id settings, stripe_coupons module

frontend_url drives renewal links in expiry emails (points to goodlie.golf).
stripe_free_tier_coupon_id is set by Block 4; defaults to empty so Block 3
sweep runs without Stripe coupon generation.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `app/email.py` — add expiry email stubs

**Files:**
- Modify: `app/email.py`

**Signature contract (frozen through Block 4):**
```python
send_free_tier_expiry_email(to: str, alert_id: str, renewals_used: int, renewal_link: str) -> None
send_final_expiry_email(to: str, discount_code: str | None) -> None
```
Block 4 replaces the function bodies only. The call sites in `free_tier_expiry.py` are never touched.

- [ ] **Step 1: Append two functions to `app/email.py`**

```python
def send_free_tier_expiry_email(to: str, alert_id: str, renewals_used: int, renewal_link: str) -> None:
    # Signature frozen: Block 4 replaces body with SendGrid template call, not this signature.
    renewals_remaining = 2 - renewals_used
    plural = "s" if renewals_remaining != 1 else ""
    send_email(
        to,
        "Good Lie Golf — no tee times opened up in your window",
        (
            f"Unfortunately no tee times opened up matching your alert during the 14-day window.\n\n"
            f"You have {renewals_remaining} renewal{plural} remaining.\n\n"
            f"Renew your alert (one click): {renewal_link}\n\n"
            "You can also edit your criteria before renewing by visiting goodlie.golf."
        ),
    )


def send_final_expiry_email(to: str, discount_code: str | None) -> None:
    # Signature frozen: Block 4 replaces body with SendGrid template call, not this signature.
    coupon_section = (
        f"\n\nAs a thank-you for trying Good Lie Golf, here's 50% off your first month: {discount_code}\n"
        "This code expires in 7 days. Redeem at goodlie.golf/billing."
        if discount_code
        else ""
    )
    send_email(
        to,
        "Good Lie Golf — your free alert period has ended",
        (
            "Your free alert has run through all 3 polling windows (42 days) without a match.\n\n"
            "Subscribe to Good Lie Golf for unlimited real-time alerts at $9.99/mo.\n"
            "Visit goodlie.golf to get started."
            f"{coupon_section}"
        ),
    )
```

- [ ] **Step 2: Verify parse**

```bash
python -m compileall app/email.py
```

- [ ] **Step 3: Commit**

```bash
git add app/email.py
git commit -m "$(cat <<'EOF'
feat: add free-tier expiry email stubs with frozen signatures

send_free_tier_expiry_email() and send_final_expiry_email() added to
app/email.py. Plain-text bodies. Block 4 replaces bodies only — call sites
in free_tier_expiry.py are stable.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `app/dependencies.py` — add `get_current_user_with_profile`

**Files:**
- Modify: `app/dependencies.py`

`get_current_user_with_profile` = auth + profile fetch, no subscription gate. Used by alert endpoints that handle paid vs. free-tier branching internally.

- [ ] **Step 1: Full `app/dependencies.py` after change**

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import supabase, supabase_admin

security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        response = supabase.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not response.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return response.user


def get_current_subscribed_user(user=Depends(get_current_user)):
    result = supabase_admin.table("user_profiles").select("*").eq("id", str(user.id)).maybe_single().execute()
    profile = result.data
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    if not profile.get("is_beta") and not profile.get("is_active"):
        raise HTTPException(status_code=403, detail="Active subscription required")
    return {"user": user, "profile": profile}


def get_current_user_with_profile(user=Depends(get_current_user)):
    """Authenticated user + profile, no subscription gate. Handlers using this
    perform their own paid-vs-free-tier branching and replicate the subscription
    gate internally when FREE_TIER_ENABLED=false."""
    result = supabase_admin.table("user_profiles").select("*").eq("id", str(user.id)).maybe_single().execute()
    profile = result.data
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    return {"user": user, "profile": profile}
```

- [ ] **Step 2: Verify parse**

```bash
python -m compileall app/dependencies.py
```

- [ ] **Step 3: Commit**

```bash
git add app/dependencies.py
git commit -m "$(cat <<'EOF'
feat: add get_current_user_with_profile dependency (no subscription gate)

Alert endpoints switch to this dependency and enforce the subscription
check internally, allowing free-tier branching when FREE_TIER_ENABLED=true.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `app/routers/courses.py` — available courses endpoint

**Files:**
- Create: `app/routers/courses.py`

Returns course keys from active, non-free-tier alert profiles. Cached 60s. 503 when flag off.

**Empty-state response contract:** always returns `{courses, count, available}` — never a bare list. Frontend branches on `available` for the empty-state render.

- [ ] **Step 1: Create `app/routers/courses.py`**

```python
import time
import logging
from fastapi import APIRouter, HTTPException
from app.database import supabase_admin
from app.config import settings

router = APIRouter(tags=["courses"])
log = logging.getLogger(__name__)

_courses_cache: dict = {"data": None, "ts": 0.0}
_CACHE_TTL = 60.0


def _require_free_tier() -> None:
    if not settings.free_tier_enabled:
        raise HTTPException(status_code=503, detail="Free tier is not yet available.")


@router.get("/courses/available-for-free-tier")
def available_free_tier_courses():
    _require_free_tier()

    now = time.monotonic()
    if _courses_cache["data"] is not None and now - _courses_cache["ts"] < _CACHE_TTL:
        return _courses_cache["data"]

    result = supabase_admin.table("alert_profiles") \
        .select("courses") \
        .eq("status", "active") \
        .eq("is_free_tier", False) \
        .execute()

    course_set: set[str] = set()
    for row in result.data or []:
        for course in (row.get("courses") or []):
            course_set.add(course)

    data = {
        "courses": sorted(course_set),
        "count": len(course_set),
        "available": len(course_set) > 0,
    }
    _courses_cache["data"] = data
    _courses_cache["ts"] = now
    log.debug("available_free_tier_courses: %d courses cached", len(course_set))
    return data
```

- [ ] **Step 2: Verify parse**

```bash
python -m compileall app/routers/courses.py
```

- [ ] **Step 3: Commit**

```bash
git add app/routers/courses.py
git commit -m "$(cat <<'EOF'
feat: add GET /courses/available-for-free-tier endpoint

Returns {courses, count, available} — stable empty-state payload.
Courses drawn from active non-free-tier alert_profiles. 60s in-process cache.
503 when FREE_TIER_ENABLED=false.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `app/routers/alerts.py` — free-tier gating

**Files:**
- Modify: `app/routers/alerts.py`

Changes per function:

| Function | Old dependency | New dependency | Changes |
|---|---|---|---|
| `create_alert` | `get_current_subscribed_user` | `get_current_user_with_profile` | full free-tier creation logic |
| `list_alerts` | `get_current_subscribed_user` | `get_current_user_with_profile` | gate replicated internally |
| `update_alert` (PUT) | `get_current_subscribed_user` | `get_current_user_with_profile` | paywall on fired free-tier |
| `delete_alert` | `get_current_subscribed_user` | `get_current_user_with_profile` | gate replicated internally |
| `retry_alert` | `get_current_subscribed_user` | `get_current_user_with_profile` | paywall: free-tier + not paid → 402 |
| `renew_alert` | — (new) | `get_current_user_with_profile` | new endpoint |
| `get_alert_history` | `get_current_user` | `get_current_user` | no change |

`_require_subscription_or_free_tier(profile)`: replicates the `get_current_subscribed_user` gate when `FREE_TIER_ENABLED=false`. When the flag is on, it passes through (free-tier users allowed). Ensures rollback symmetry.

- [ ] **Step 1: Full new `app/routers/alerts.py`**

```python
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
```

- [ ] **Step 2: Verify parse**

```bash
python -m compileall app/routers/alerts.py
```

- [ ] **Step 3: Smoke-test paid path (flag off)**

```bash
FREE_TIER_ENABLED=false uvicorn app.main:app --reload
# Log in as a paid/beta user; call GET /alerts — confirm 200, no regressions
# Call POST /alerts as that user — confirm alert created normally
```

- [ ] **Step 4: Commit**

```bash
git add app/routers/alerts.py
git commit -m "$(cat <<'EOF'
feat: add free-tier gating to alert endpoints and POST /alerts/{id}/renew

- create_alert: free-tier path — one-per-phone, polled-course check,
  sets is_free_tier + polling_expires_at, marks free_tier_used_at on profile.
  Paid path unchanged (10-alert cap still enforced there only).
- list/delete: accessible to free-tier users when FREE_TIER_ENABLED=true
- update_alert (PUT): gate fired free-tier edits behind 402
- retry_alert: gate free-tier retry behind 402
- renew_alert: new endpoint — transitions expired_pending_renewal → active

_require_subscription_or_free_tier() ensures 403 for non-paid users when
FREE_TIER_ENABLED=false (rollback symmetry).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `app/free_tier_expiry.py` — async expiry sweep

**Files:**
- Create: `app/free_tier_expiry.py`

Runs every 5 minutes. Queries `alert_profiles` for free-tier active alerts where `polling_expires_at < now` and `expiry_state IS NULL`. For each:

1. **Skip** if the user is now paid (converted to subscription after creating the free alert)
2. **`renewals_used < 2`** → `expired_pending_renewal`, send renewal email
3. **`renewals_used == 2`** → `final_expired` on alert + `user_profiles`, generate Stripe promo code (if configured), send final email

**Critical Python note:** lambdas in a loop capture variables by reference. All `asyncio.to_thread` lambdas use default-argument binding (`lambda aid=alert_id: ...`) to capture the current loop value by value.

- [ ] **Step 1: Create `app/free_tier_expiry.py`**

```python
import asyncio
import logging
from datetime import datetime, timezone

from app.config import settings
from app.database import supabase_admin
from app.email import send_final_expiry_email, send_free_tier_expiry_email
from app.stripe_coupons import create_one_time_coupon
from app.util.dates import _parse_iso

log = logging.getLogger(__name__)


async def check_free_tier_expiry() -> None:
    try:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        result = await asyncio.to_thread(
            lambda: supabase_admin.table("alert_profiles")
            .select("id, user_id, renewals_used, polling_expires_at")
            .eq("is_free_tier", True)
            .eq("status", "active")
            .is_("expiry_state", "null")
            .lt("polling_expires_at", now_iso)
            .execute()
        )

        alerts = result.data or []
        if not alerts:
            return

        log.info("free_tier_expiry: %d alert(s) to process", len(alerts))

        for alert in alerts:
            alert_id = alert["id"]
            user_id = alert["user_id"]
            renewals_used = alert.get("renewals_used") or 0

            # Skip if user has since subscribed — don't expire a paying customer's alert
            profile_check = await asyncio.to_thread(
                lambda uid=user_id: supabase_admin.table("user_profiles")
                .select("is_active, is_beta")
                .eq("id", uid)
                .maybe_single()
                .execute()
            )
            p = profile_check.data or {}
            if p.get("is_active") or p.get("is_beta"):
                log.info("free_tier_expiry: skip alert=%s — user converted to paid", alert_id)
                continue

            if renewals_used < 2:
                await _transition_pending_renewal(alert_id, user_id, renewals_used, now_iso)
            else:
                await _transition_final_expired(alert_id, user_id, now_iso)

    except Exception:
        log.exception("check_free_tier_expiry error")


async def _transition_pending_renewal(
    alert_id: str, user_id: str, renewals_used: int, now_iso: str
) -> None:
    try:
        await asyncio.to_thread(
            lambda aid=alert_id: supabase_admin.table("alert_profiles")
            .update({"expiry_state": "expired_pending_renewal", "status": "expired"})
            .eq("id", aid)
            .execute()
        )

        profile_result = await asyncio.to_thread(
            lambda uid=user_id: supabase_admin.table("user_profiles")
            .select("notify_email, email")
            .eq("id", uid)
            .maybe_single()
            .execute()
        )
        profile = profile_result.data or {}
        to_email = profile.get("notify_email") or profile.get("email")

        if to_email:
            renewal_link = f"{settings.frontend_url}/alerts/{alert_id}/renew"
            try:
                await asyncio.to_thread(
                    lambda e=to_email, aid=alert_id, r=renewals_used, lnk=renewal_link:
                        send_free_tier_expiry_email(e, aid, r, lnk)
                )
            except Exception as exc:
                log.error("free_tier_expiry: renewal email failed alert=%s — %s", alert_id, exc)

        log.info(
            "free_tier_expiry: alert=%s → expired_pending_renewal renewals_used=%d",
            alert_id,
            renewals_used,
        )
    except Exception:
        log.exception("free_tier_expiry: _transition_pending_renewal failed alert=%s", alert_id)


async def _transition_final_expired(alert_id: str, user_id: str, now_iso: str) -> None:
    try:
        await asyncio.to_thread(
            lambda aid=alert_id, ts=now_iso: supabase_admin.table("alert_profiles")
            .update({"expiry_state": "final_expired", "final_expired_at": ts, "status": "expired"})
            .eq("id", aid)
            .execute()
        )

        await asyncio.to_thread(
            lambda uid=user_id, ts=now_iso: supabase_admin.table("user_profiles")
            .update({"final_expired_at": ts})
            .eq("id", uid)
            .execute()
        )

        # Generate Stripe promo code — skipped if STRIPE_FREE_TIER_COUPON_ID not configured (Block 4 sets it)
        discount_code: str | None = None
        coupon_id = settings.stripe_free_tier_coupon_id
        if coupon_id:
            try:
                discount_code = await asyncio.to_thread(
                    lambda uid=user_id, cid=coupon_id: create_one_time_coupon(uid, cid)
                )
            except Exception as exc:
                log.error("free_tier_expiry: stripe coupon failed alert=%s — %s", alert_id, exc)
        else:
            log.info("free_tier_expiry: STRIPE_FREE_TIER_COUPON_ID not set — skipping coupon for alert=%s", alert_id)

        profile_result = await asyncio.to_thread(
            lambda uid=user_id: supabase_admin.table("user_profiles")
            .select("notify_email, email")
            .eq("id", uid)
            .maybe_single()
            .execute()
        )
        profile = profile_result.data or {}
        to_email = profile.get("notify_email") or profile.get("email")

        if to_email:
            try:
                await asyncio.to_thread(
                    lambda e=to_email, d=discount_code: send_final_expiry_email(e, d)
                )
            except Exception as exc:
                log.error("free_tier_expiry: final email failed alert=%s — %s", alert_id, exc)

        log.info(
            "free_tier_expiry: alert=%s user=%s → final_expired coupon=%s",
            alert_id,
            user_id[:8],
            discount_code,
        )
    except Exception:
        log.exception("free_tier_expiry: _transition_final_expired failed alert=%s", alert_id)


async def free_tier_expiry_loop() -> None:
    while True:
        try:
            await asyncio.sleep(300)  # 5 minutes — sleep first, then check
            await check_free_tier_expiry()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("free_tier_expiry_loop iteration failed")
```

- [ ] **Step 2: Verify parse**

```bash
python -m compileall app/free_tier_expiry.py
```

- [ ] **Step 3: Commit**

```bash
git add app/free_tier_expiry.py
git commit -m "$(cat <<'EOF'
feat: add free-tier expiry sweep (async background task, 5-min interval)

check_free_tier_expiry() processes active free-tier alerts with expired
polling windows:
- Skips alerts for users who have since subscribed (paid-user skip)
- renewals_used < 2 → expired_pending_renewal + renewal email
- renewals_used == 2 → final_expired on alert + user_profiles + Stripe
  promo code (if STRIPE_FREE_TIER_COUPON_ID set) + final email

Lambda default-arg binding used throughout to avoid loop-capture gotcha.
No-op when FREE_TIER_ENABLED=false (no free-tier alerts exist in prod).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `app/main.py` — wire courses router and expiry loop

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Update router imports line**

Change:
```python
from app.routers import auth, alerts, billing, invites, admin, course_requests, activity, phone_verification
```
to:
```python
from app.routers import auth, alerts, billing, invites, admin, course_requests, activity, phone_verification, courses
```

- [ ] **Step 2: Add expiry loop import**

After the heartbeat import line:
```python
from app.heartbeat_monitor import heartbeat_monitor_loop
```
add:
```python
from app.free_tier_expiry import free_tier_expiry_loop
```

- [ ] **Step 3: Update the lifespan context manager**

Change from:
```python
@asynccontextmanager
async def lifespan(app):
    app.state.ip_rate_limit = {}
    task = asyncio.create_task(heartbeat_monitor_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
```

To:
```python
@asynccontextmanager
async def lifespan(app):
    app.state.ip_rate_limit = {}
    heartbeat_task = asyncio.create_task(heartbeat_monitor_loop())
    expiry_task = asyncio.create_task(free_tier_expiry_loop())
    try:
        yield
    finally:
        heartbeat_task.cancel()
        expiry_task.cancel()
        for t in (heartbeat_task, expiry_task):
            try:
                await t
            except asyncio.CancelledError:
                pass
```

- [ ] **Step 4: Register the courses router**

After `app.include_router(phone_verification.router)` add:
```python
app.include_router(courses.router)
```

- [ ] **Step 5: Verify parse and startup**

```bash
python -m compileall app/main.py
uvicorn app.main:app --reload
```

Expected: server starts cleanly. Both background tasks start silently (they sleep 60s and 300s respectively before first check).

- [ ] **Step 6: Commit**

```bash
git add app/main.py
git commit -m "$(cat <<'EOF'
feat: register courses router and start free_tier_expiry_loop in lifespan

Wires up GET /courses/available-for-free-tier and the 5-minute free-tier
expiry sweep as a background asyncio task alongside the heartbeat monitor.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Tests

**Files:**
- Create: `tests/test_free_tier_logic.py`

Pure-function unit tests only. No DB, no HTTP, no mocking. Follows the same pattern as `tests/test_phone_util.py`. All business-logic helpers are defined locally in the test file so they're testable without importing the full FastAPI app.

- [ ] **Step 1: Write `tests/test_free_tier_logic.py`**

```python
from datetime import datetime, timezone, timedelta
import pytest

from app.util.dates import _parse_iso


# ── _parse_iso ─────────────────────────────────────────────────────────────────

def test_parse_iso_standard_6_digit():
    result = _parse_iso("2026-05-07T00:55:46.123456+00:00")
    assert result == datetime(2026, 5, 7, 0, 55, 46, 123456, tzinfo=timezone.utc)


def test_parse_iso_5_digit_pads_to_6():
    # Python 3.9 raises ValueError on this without the helper
    result = _parse_iso("2026-05-07T00:55:46.20461+00:00")
    assert result.microsecond == 204610


def test_parse_iso_3_digit_pads_to_6():
    result = _parse_iso("2026-05-07T00:55:46.123+00:00")
    assert result.microsecond == 123000


def test_parse_iso_no_fractional():
    result = _parse_iso("2026-05-07T00:55:46+00:00")
    assert result.second == 46
    assert result.microsecond == 0


def test_parse_iso_z_suffix():
    result = _parse_iso("2026-05-07T00:55:46.123456Z")
    assert result.utcoffset().total_seconds() == 0


def test_parse_iso_negative_offset():
    result = _parse_iso("2026-05-07T00:55:46.123456-05:00")
    assert result.utcoffset().total_seconds() == -5 * 3600


# ── Free-tier user classification (mirrors logic in create_alert) ──────────────
# Defined here as a pure helper so the test doesn't import the FastAPI app.

def _classify_free_tier_user(profile: dict, free_tier_enabled: bool) -> str:
    is_paid = bool(profile.get("is_active") or profile.get("is_beta"))
    if is_paid:
        return "paid"
    if not free_tier_enabled:
        return "flag_off"
    if profile.get("final_expired_at"):
        return "blocked"
    if profile.get("free_tier_used_at"):
        return "already_used"
    return "eligible"


def test_classify_is_active_paid():
    assert _classify_free_tier_user({"is_active": True}, True) == "paid"


def test_classify_is_beta_paid():
    assert _classify_free_tier_user({"is_beta": True}, True) == "paid"


def test_classify_paid_flag_off_still_paid():
    # Paid users are never affected by the flag
    assert _classify_free_tier_user({"is_active": True}, False) == "paid"


def test_classify_flag_off_unpaid():
    assert _classify_free_tier_user({}, False) == "flag_off"


def test_classify_permanently_blocked():
    profile = {"final_expired_at": "2026-04-01T00:00:00+00:00"}
    assert _classify_free_tier_user(profile, True) == "blocked"


def test_classify_already_used():
    profile = {"free_tier_used_at": "2026-04-01T00:00:00+00:00"}
    assert _classify_free_tier_user(profile, True) == "already_used"


def test_classify_eligible_new_user():
    assert _classify_free_tier_user({}, True) == "eligible"


# ── Expiry transition classification (mirrors logic in check_free_tier_expiry) ──

def _classify_expiry_action(alert: dict, now: datetime) -> str | None:
    if not alert.get("is_free_tier"):
        return None
    if alert.get("status") != "active":
        return None
    if alert.get("expiry_state") is not None:
        return None
    expires_at_str = alert.get("polling_expires_at")
    if not expires_at_str:
        return None
    if now <= _parse_iso(expires_at_str):
        return None
    renewals_used = alert.get("renewals_used") or 0
    return "pending_renewal" if renewals_used < 2 else "final_expired"


def test_expiry_not_free_tier():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": False, "status": "active", "expiry_state": None,
             "polling_expires_at": (now - timedelta(hours=1)).isoformat(), "renewals_used": 0}
    assert _classify_expiry_action(alert, now) is None


def test_expiry_not_yet_expired():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": True, "status": "active", "expiry_state": None,
             "polling_expires_at": (now + timedelta(days=1)).isoformat(), "renewals_used": 0}
    assert _classify_expiry_action(alert, now) is None


def test_expiry_already_has_state():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": True, "status": "active", "expiry_state": "expired_pending_renewal",
             "polling_expires_at": (now - timedelta(hours=1)).isoformat(), "renewals_used": 0}
    assert _classify_expiry_action(alert, now) is None


def test_expiry_not_active():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": True, "status": "expired", "expiry_state": None,
             "polling_expires_at": (now - timedelta(hours=1)).isoformat(), "renewals_used": 0}
    assert _classify_expiry_action(alert, now) is None


def test_expiry_first_window_pending_renewal():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": True, "status": "active", "expiry_state": None,
             "polling_expires_at": (now - timedelta(hours=1)).isoformat(), "renewals_used": 0}
    assert _classify_expiry_action(alert, now) == "pending_renewal"


def test_expiry_after_first_renewal_still_pending():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": True, "status": "active", "expiry_state": None,
             "polling_expires_at": (now - timedelta(hours=1)).isoformat(), "renewals_used": 1}
    assert _classify_expiry_action(alert, now) == "pending_renewal"


def test_expiry_after_two_renewals_final():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": True, "status": "active", "expiry_state": None,
             "polling_expires_at": (now - timedelta(hours=1)).isoformat(), "renewals_used": 2}
    assert _classify_expiry_action(alert, now) == "final_expired"


def test_expiry_5_digit_microsecond_timestamp():
    # Regression: ensure expiry works even when Supabase returns 5-digit microseconds
    now = datetime.now(timezone.utc)
    past = "2026-04-01T00:55:46.20461+00:00"  # 5-digit microseconds
    alert = {"is_free_tier": True, "status": "active", "expiry_state": None,
             "polling_expires_at": past, "renewals_used": 0}
    assert _classify_expiry_action(alert, now) == "pending_renewal"
```

- [ ] **Step 2: Run all tests**

```bash
cd ~/foreward-api && source .venv/bin/activate
pytest tests/ -v
```

Expected: all pass. New count: 21 new tests (6 `_parse_iso` + 7 classification + 8 expiry).

- [ ] **Step 3: Commit**

```bash
git add tests/test_free_tier_logic.py
git commit -m "$(cat <<'EOF'
test: 21 unit tests for _parse_iso, free-tier user classification, expiry logic

Covers: timestamp parsing edge cases (5-digit microseconds, Z suffix,
negative offset), user classification (paid/beta/blocked/already_used/
eligible/flag_off), expiry transition classification (pending/final/no-op),
and a regression test for 5-digit microsecond timestamps in expiry checks.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## End-to-End Verification Sequence (local, flag on)

After all tasks complete. Add `FREE_TIER_ENABLED=true` and `FRONTEND_URL=http://localhost:3000` to `.env` temporarily.

```bash
cd ~/foreward-api && source .venv/bin/activate
uvicorn app.main:app --reload

# AC12: courses endpoint shape
curl http://localhost:8000/courses/available-for-free-tier
# Expected: {"courses": [...], "count": N, "available": true/false}

# AC1: paid user unchanged (use existing paid JWT)
curl -H "Authorization: Bearer $PAID_JWT" http://localhost:8000/alerts
# Expected: 200

# AC3: second free-tier alert → 402
# (requires a free-tier user JWT — either create one via Block 5 flow or
#  manually insert a user_profiles row with phone_hash set + free_tier_used_at IS NULL)

# AC5/AC7: expiry sweep test
# In Supabase SQL Editor:
#   UPDATE alert_profiles SET polling_expires_at = NOW() - INTERVAL '1 hour'
#   WHERE is_free_tier = true AND status = 'active' AND expiry_state IS NULL;
# Wait up to 5 min, then check:
#   SELECT id, status, expiry_state, renewals_used FROM alert_profiles WHERE is_free_tier = true;
# Expected: expiry_state = 'expired_pending_renewal', status = 'expired'
# Check uvicorn logs for: free_tier_expiry: alert=... → expired_pending_renewal

# AC9: paid-user skip
# Set is_active = true on the user, then repeat the polling_expires_at update above.
# Check logs: free_tier_expiry: skip alert=... — user converted to paid
# Alert should NOT transition.
```

---

## Notes for Future Blocks

- **Block 4** (`86ahazbr4`): configure the 50%-off Stripe Coupon in Stripe test dashboard, set `STRIPE_FREE_TIER_COUPON_ID` in Railway env, and update `send_free_tier_expiry_email` / `send_final_expiry_email` bodies in `app/email.py` — call sites in `free_tier_expiry.py` unchanged.
- **Block 5** (`86ahazcce`): Lovable signup flow will call `GET /courses/available-for-free-tier` (branch on `available` field) and `POST /alerts` as a free-tier user. `GET /alerts` is now accessible to free-tier users.
- **Block 9 pre-launch**: run the pre-launch checklist ticket (filed this session) to verify N≥2 courses actively polled before flipping `FREE_TIER_ENABLED=true`. Also set `FRONTEND_URL=https://goodlie.golf` in Railway `web` env.
- **AC4, AC5 (Block 2 deferred)**: phone uniqueness runtime verify and max-3 resend cap runtime verify remain deferred to Block 5.
- **86ahbacxw**: closed by Task 1 of this block.
