===PASTE START===
# Block 5b — Free-tier alert creation logic

**Date:** 2026-05-07
**Master ticket:** `86ahavm5n` (free-tier launch)
**Block ticket:** `86ahbkwf6` (Lovable signup blocker — pre-launch critical)
**Depends on:** Block 5a (free-tier signup endpoint must be deployed; free-tier users exist)
**Blocks:** Block 5c (Lovable signup page; needs both 5a + 5b deployed before Lovable prompt is pasted)

---

## Goal

Refine `POST /alerts` free-tier path: extract `is_user_free_tier()` classifier, replace the current lifetime `free_tier_used_at` block with a concurrent-alert cap (1 active/fired non-`final_expired` free-tier alert), handle lapsed paid users via the free-tier re-engagement path, and add defense-in-depth 503 when `FREE_TIER_ENABLED=false` for classified free-tier users. Paid path: zero behavior change.

Block 5b does NOT touch `/auth/signup`, `/auth/signup-free-tier`, or any frontend.

---

## Ambiguities resolved (pre-plan, 2026-05-07)

1. **Concurrent vs lifetime cap** — Replace `if profile.get("free_tier_used_at"):` → 402 with a live DB count of `is_free_tier=true` alerts with `status IN ('active', 'fired')` AND `expiry_state != 'final_expired'`. Rationale: once a user's alert hits `final_expired`, they should be upsold, not permanently locked out from free tier — the user-level `final_expired_at` on `user_profiles` is the true lifetime block. Resolved 2026-05-07.

2. **Lapsed paid user path** — A user with `is_active=false, is_beta=false, free_tier_used_at IS NULL` had a subscription that lapsed. Route them through the free-tier creation path (re-engagement). `free_tier_used_at` is set on their first free-tier alert creation, same as a first-time user. Prevents revenue gaming: if they create a free-tier alert then re-subscribe, their `free_tier_used_at` is already set and the cap logic applies as normal. Resolved 2026-05-07.

3. **`is_user_free_tier()` definition** — `free_tier_used_at IS NOT NULL AND NOT is_active`. Identifies users who are currently on the free tier (have created a free-tier alert and are not paid subscribers). Used for: (a) defense-in-depth 503 gate when flag is off, (b) unit tests. NOT used to gate the creation path itself — that remains `not _is_paid()`. Resolved 2026-05-07.

4. **Defense-in-depth 503** — If `FREE_TIER_ENABLED=false` and `is_user_free_tier(profile)` is True, return 503 instead of 403. These users legitimately signed up for free tier; 503 (service temporarily unavailable) is more accurate than 403 (subscription required). New users with no `free_tier_used_at` still get 403 when flag is off (existing behavior unchanged). Resolved 2026-05-07.

5. **`expiry_state` nullability in PostgREST `.neq()`** — `.neq("expiry_state", "final_expired")` in supabase-py on a nullable column keeps rows where `expiry_state IS NULL` or any other non-`final_expired` value, and excludes only rows where `expiry_state = 'final_expired'`. This is the correct behavior for the cap: an alert in `expired_pending_renewal` (still actionable) counts against the cap; an alert in `final_expired` (terminal) does not. Resolved 2026-05-07.

---

## Design decisions (pinned)

### `is_user_free_tier()` classifier

```python
def is_user_free_tier(profile: dict) -> bool:
    """True for active free-tier users and lapsed paid users who later used free tier.
    Used for defense-in-depth 503 gate when FREE_TIER_ENABLED=false."""
    return bool(profile.get("free_tier_used_at") and not profile.get("is_active"))
```

Returns False for:
- Currently paid users (`is_active=True` or `is_beta=True`)
- Brand-new users who have never created a free-tier alert (`free_tier_used_at IS NULL`)
- Lapsed paid users who never used free tier (`free_tier_used_at IS NULL`, not active) — they get 403 when flag is off, not 503

### Concurrent alert cap (replaces lifetime block)

```python
concurrent = (
    supabase_admin.table("alert_profiles")
    .select("id", count="exact")
    .eq("user_id", user_id)
    .eq("is_free_tier", True)
    .in_("status", ["active", "fired"])
    .neq("expiry_state", "final_expired")
    .execute()
)
if (concurrent.count or 0) >= 1:
    raise HTTPException(status_code=402, detail="Payment required to create additional alerts")
```

### Gate order in `POST /alerts` unpaid branch

```
1. _is_paid(profile) → paid path (unchanged)
2. is_user_free_tier(profile) AND NOT free_tier_enabled → 503
3. NOT free_tier_enabled → 403 (new/lapsed user, flag off)
4. final_expired_at on user_profiles → 402 permanent block
5. Concurrent active/fired free-tier alert count ≥ 1 → 402
6. Free-tier creation (is_free_tier=True, polling_expires_at=now()+14d, renewals_used=0, expiry_state=NULL implicit)
```

`free_tier_used_at` is still set on profile after free-tier alert creation (existing behavior preserved).

### File map

**Modified files:**
- `app/routers/alerts.py` — add `is_user_free_tier()`, replace lifetime block with concurrent cap, add defense-in-depth 503
- `tests/test_free_tier_logic.py` — add `is_user_free_tier()` unit tests and a concurrent cap classification helper test

---

## Tasks

### Task 0 — Pre-checks (no code changes)

0.1. Confirm Block 5a is deployed: `curl -sS https://web-production-b24db.up.railway.app/auth/signup-free-tier -X POST -H "Content-Type: application/json" -d '{}'`. Expect 503.
0.2. Confirm `alert_profiles.expiry_state` column exists via `information_schema.columns` (no new migration in this block — Block 1 added it). Run: `SELECT column_name, is_nullable, data_type FROM information_schema.columns WHERE table_name = 'alert_profiles' AND column_name IN ('expiry_state', 'is_free_tier', 'renewals_used', 'polling_expires_at');` in Supabase SQL Editor.
0.3. Re-read current unpaid branch of `create_alert` in `app/routers/alerts.py` line by line before modifying.

### Task 1 — Add `is_user_free_tier()` to alerts.py

Add to `app/routers/alerts.py` alongside `_is_paid()`:

```python
def is_user_free_tier(profile: dict) -> bool:
    """True for active free-tier users and lapsed paid users who later used free tier."""
    return bool(profile.get("free_tier_used_at") and not profile.get("is_active"))
```

### Task 2 — Defense-in-depth 503

In the unpaid branch of `create_alert`, immediately before the existing `if not settings.free_tier_enabled:` → 403 check, add:

```python
if is_user_free_tier(profile) and not settings.free_tier_enabled:
    raise HTTPException(status_code=503, detail="Free tier is not yet available.")
```

Keep the existing 403 check immediately after for users without `free_tier_used_at`.

### Task 3 — Replace lifetime block with concurrent alert cap

Remove:
```python
if profile.get("free_tier_used_at"):
    # Already consumed their one free alert
    raise HTTPException(status_code=402, detail="Payment required to create additional alerts")
```

Replace with:
```python
concurrent = (
    supabase_admin.table("alert_profiles")
    .select("id", count="exact")
    .eq("user_id", user_id)
    .eq("is_free_tier", True)
    .in_("status", ["active", "fired"])
    .neq("expiry_state", "final_expired")
    .execute()
)
if (concurrent.count or 0) >= 1:
    raise HTTPException(status_code=402, detail="Payment required to create additional alerts")
```

### Task 4 — Tests

Add to `tests/test_free_tier_logic.py` under a new `# ── is_user_free_tier ──` section:

```python
def test_is_user_free_tier_true_for_free_tier_user():
    profile = {"free_tier_used_at": "2026-05-01T00:00:00+00:00", "is_active": False}
    assert is_user_free_tier(profile) is True

def test_is_user_free_tier_false_for_paid_user():
    assert is_user_free_tier({"is_active": True, "free_tier_used_at": "2026-05-01T00:00:00+00:00"}) is False

def test_is_user_free_tier_false_for_new_user():
    assert is_user_free_tier({}) is False

def test_is_user_free_tier_false_for_lapsed_paid_no_free_tier_history():
    # Lapsed paid, never used free tier — free_tier_used_at is NULL
    assert is_user_free_tier({"is_active": False}) is False

def test_is_user_free_tier_true_lapsed_paid_with_free_tier_history():
    # Was paid, subscription lapsed, previously had free-tier alert
    profile = {"free_tier_used_at": "2026-04-01T00:00:00+00:00", "is_active": False, "is_beta": False}
    assert is_user_free_tier(profile) is True
```

And a concurrent cap classification helper (matches existing _classify_* pattern):

```python
def _classify_concurrent_cap(alerts: list) -> bool:
    """Returns True (blocked) if there is at least one active/fired non-final-expired free-tier alert."""
    for a in alerts:
        if a.get("is_free_tier") and a.get("status") in ("active", "fired") and a.get("expiry_state") != "final_expired":
            return True
    return False

def test_concurrent_cap_blocks_on_active_alert():
    alerts = [{"is_free_tier": True, "status": "active", "expiry_state": None}]
    assert _classify_concurrent_cap(alerts) is True

def test_concurrent_cap_blocks_on_fired_alert():
    alerts = [{"is_free_tier": True, "status": "fired", "expiry_state": None}]
    assert _classify_concurrent_cap(alerts) is True

def test_concurrent_cap_allows_after_final_expired():
    # final_expired alert should NOT count against the cap
    alerts = [{"is_free_tier": True, "status": "active", "expiry_state": "final_expired"}]
    assert _classify_concurrent_cap(alerts) is False

def test_concurrent_cap_allows_when_no_free_tier_alerts():
    alerts = []
    assert _classify_concurrent_cap(alerts) is False

def test_concurrent_cap_allows_paid_alert_not_counted():
    alerts = [{"is_free_tier": False, "status": "active", "expiry_state": None}]
    assert _classify_concurrent_cap(alerts) is False
```

### Task 5 — Local verification

Run `pytest tests/ -v`. All existing tests + new tests must pass. Run `python -m compileall app/`.

### Task 6 — Deploy

Direct-to-main commit. `git push origin main`. Wait for Railway deploy. Confirm paid alert creation still works (regression check via curl if needed).

### Task 7 — Doc updates (after Task 6)

Append Block 5b entry to `docs/ARCHITECTURE.md` decision log. Commit and push.

### Task 8 — ClickUp

Add comment to `86ahbkwf6` noting Block 5b complete; Lovable (5c) still pending.

---

## Acceptance criteria

| AC | Description | How to verify |
|----|-------------|---------------|
| AC0 | `is_user_free_tier()` — correct in all branches | Unit tests Task 4 |
| AC1 | Free-tier user + flag off → 503 | Unit test; runtime curl if testing with real user |
| AC2 | New/lapsed-no-history user + flag off → 403 | Unit test |
| AC3 | `final_expired_at` set on profile → 402 permanent block | Unit test (existing behavior, preserved) |
| AC4 | 1 active/fired non-final-expired free-tier alert → 402 | Unit test + DB count helper |
| AC5 | Alert with `expiry_state='final_expired'` excluded from cap | Unit test |
| AC6 | Paid path: zero behavior change | `pytest tests/` passes; curl paid create alert if possible |

---

## Rollback

1. `git revert <sha> && git push origin main`. Railway redeploys.
2. No DB migration in this block.
===PASTE END===
