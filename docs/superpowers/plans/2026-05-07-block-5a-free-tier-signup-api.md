===PASTE START===
# Block 5a — Free-tier signup API endpoint

**Date:** 2026-05-07
**Master ticket:** `86ahavm5n` (free-tier launch)
**Block ticket:** `86ahbkwf6` (Lovable signup blocker — pre-launch critical)
**Depends on:** Block 1 (schema), Block 2 (phone verification endpoints), Block 3 (alert lifecycle)
**Blocks:** Block 5b (alert creation logic), Block 5c (Lovable signup page)

---

## Goal

Add `POST /auth/signup-free-tier` endpoint that consumes a `verification_token` from Block 2 and creates a free-tier user with `phone_verified=true`, `phone_hash` set, and `free_tier_used_at=now()`. Gated behind `FREE_TIER_ENABLED` env var (returns 503 when off).

Block 5a does NOT touch `/auth/signup` (paid path), `POST /alerts`, or any frontend. Those are 5b and 5c.

---

## Ambiguities resolved (this session, before writing)

1. **Free vs paid intent at signup** → Single signup page in Lovable; free is the default landing. Upgrade-to-paid CTA visible from dashboard. Resolved 2026-05-07.
2. **API endpoint shape** → New endpoint `/auth/signup-free-tier`. Existing `/auth/signup` left untouched. Resolved 2026-05-07.
3. **Brand voice on "free"** → Body copy uses "free for 14 days" pattern, never bare "free." Hero CTA: "Try one alert, free for 14 days." Resolved 2026-05-07.
4. **Free-tier alert limit** → 1 active alert per free-tier user. Enforced in Block 5b. Resolved 2026-05-07.
5. **Email confirmation behavior** → Match paid signup (`email_confirm: True` on Supabase create_user). Phone is the verification gate; email auto-confirmed. Resolved 2026-05-07.
6. **Refactor vs duplicate auth-user creation** → Duplicate (~20 lines). Zero risk to paid path. Refactor later when justified. Resolved 2026-05-07.

---

## Design decisions pinned

### Validation order (fail-fast)

1. `FREE_TIER_ENABLED` env check → 503 if disabled
2. Pydantic schema validation → 422 on bad input
3. `is_valid_e164(phone_e164)` → 422 if not E.164
4. `hash_phone(phone_e164)` → derive `phone_hash`
5. Lookup `phone_verification_codes` row by `verification_token`:
   - Not found → 401
   - `used = true` → 401
   - `token_expires_at < now()` → 401
   - `phone_hash` mismatch with our derived hash → 401 (catches token-with-wrong-phone)
6. Uniqueness check: `SELECT id FROM user_profiles WHERE phone_hash = $1 AND free_tier_used_at IS NOT NULL` → 409 if exists
7. Supabase `auth.admin.create_user(email, password, email_confirm=True)` → 400 on Supabase failure (most commonly: email already exists)
8. Supabase `auth.sign_in_with_password(email, password)` → 400 on failure (rare; auth was just created)
9. Compensating-action wrapper around steps 10–11:
   10. `UPDATE user_profiles SET phone_verified=true, phone_hash=$1, notify_phone=$2, free_tier_used_at=now() WHERE id=$3`
   11. `UPDATE phone_verification_codes SET used=true WHERE id=$row_id`
   - On any failure in 10–11: `auth.admin.delete_user(user_id)`, return 500. Token stays unused; user can retry.

### Response shape

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "tier": "free"
  }
}
```

`tier: "free"` is a hint for frontend branching; not authoritative. Frontend must rely on `/auth/me` or DB-derived state for anything sensitive.

### Error matrix

| Code | Cause |
|---|---|
| 503 | `FREE_TIER_ENABLED=false` |
| 422 | Pydantic validation OR invalid E.164 phone |
| 401 | Verification token: not found / used / expired / phone mismatch |
| 409 | Phone already claimed free-tier (lifetime) OR email already exists in auth |
| 400 | Supabase auth create_user / sign_in failed for other reason |
| 500 | Mid-flow failure after auth user created (compensating delete attempted) |

### Compensating-action atomicity

Steps 10–11 are NOT a single transaction (Supabase admin SDK doesn't expose multi-statement transactions to us, and we'd need direct Postgres connection to use one). The compensating-action pattern: if 10 or 11 fails, delete the just-created auth user and return 500. The verification_token row stays `used=false`, so the user can call `/auth/signup-free-tier` again with the same token (still within its 30-min `token_expires_at` window).

### File map

**New files:**
- `tests/test_signup_free_tier.py` — unit tests for the new endpoint (8 ACs)

**Modified files:**
- `app/schemas.py` — add `SignupFreeTierRequest` (email, password, phone_e164, verification_token)
- `app/routers/auth.py` — add `signup_free_tier()` endpoint function and route
- `app/dependencies.py` — verify `FREE_TIER_ENABLED` getter exists; add if not
- `docs/ARCHITECTURE.md` — append Block 5a entry to decision log; update API surface section

---

## Tasks

### Task 0 — Pre-checks (no code changes)

0.1. Confirm `FREE_TIER_ENABLED` env var present on Railway `web` service. Expected: `false` (post-Block 3 reset).
0.2. Confirm `phone_verification_codes` table exists in prod. Already verified 2026-05-07 via SQL Editor.
0.3. Confirm Block 2 endpoints respond 503 when flag is false (regression sanity check).
0.4. Confirm `app/util/phone.py` exports `hash_phone` and `is_valid_e164`. Verified 2026-05-07.

### Task 1 — Schema

Add `SignupFreeTierRequest` to `app/schemas.py`:
```python
class SignupFreeTierRequest(BaseModel):
    email: EmailStr
    password: str
    phone_e164: str
    verification_token: str
```

### Task 2 — Endpoint implementation

In `app/routers/auth.py`, add `signup_free_tier()` route handler. Place after existing `/signup` route. Implement validation order from Design Decisions above. Use `supabase_admin` for service-role queries. Use `hash_phone()` and `is_valid_e164()` from `app.util.phone`. Compensating-action pattern: wrap steps 10–11 in try/except; on failure, call `supabase_admin.auth.admin.delete_user(user.id)` and raise HTTPException(500). Return shape includes `"tier": "free"` in user object.

### Task 3 — Tests

Create `tests/test_signup_free_tier.py`. Use unit-test conventions matching Block 2 (`tests/test_phone_util.py`) and Block 3. Mock `supabase_admin` and `supabase` clients per existing test patterns. Eight test cases mapping to AC0–AC7.

### Task 4 — Local verification

Run `pytest tests/`. Expected: all existing tests still pass + 8 new tests pass. Run `python -m compileall app/`.

### Task 5 — Deploy

Direct-to-main commit. `git push origin main`. Wait for Railway deploy. Verify with `curl -sS https://web-production-b24db.up.railway.app/auth/signup-free-tier -X POST -H "Content-Type: application/json" -d '{}'`. Expect 503.

### Task 6 — Production verification (Dustin + Claude do this together in chat)

STOP HERE. Tell Dustin Tasks 0-5 are complete and to come back to chat for Task 6.

### Task 7 — Doc updates (after Task 6 passes)

Append Block 5a entry to `docs/ARCHITECTURE.md` decision log. Update API surface section: add `POST /auth/signup-free-tier` entry under `Auth`. Note that `phone_verification_codes` migration is now applied to prod. Commit and push.

### Task 8 — ClickUp

Add comment to `86ahbkwf6` noting Block 5a complete; Block 5b and Lovable still pending. Do NOT close `86ahbkwf6` — that ticket spans 5a + 5b + Lovable.

---

## Acceptance criteria

- AC0 — Kill switch: `FREE_TIER_ENABLED=false` → 503
- AC1 — Happy path: full signup flow → 201 with JWT, user_profiles populated, token marked used
- AC2 — Used token rejected: 401
- AC3 — Expired token rejected: 401
- AC4 — Phone mismatch rejected: 401
- AC5 — Phone already claimed: 409 (unit test only; not verified in prod)
- AC6 — Email already exists: 409
- AC7 — Compensating delete on failure: auth user deleted, 500 returned (unit test)
- AC8 — Paid /auth/signup unchanged (regression)

---

## Rollback

1. Set `FREE_TIER_ENABLED=false` on Railway. Endpoint returns 503.
2. If code-level bug: `git revert <sha> && git push origin main`. Railway redeploys.
3. If user_profiles bad state: SQL `UPDATE user_profiles SET free_tier_used_at = NULL` for affected users.

No DB migration in this block, no schema rollback.
===PASTE END===
