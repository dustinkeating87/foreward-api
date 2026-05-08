# Block 5a Debug State — 2026-05-07

## Status: Bug fixed, production re-verified partially. AC1 happy path pending tomorrow.

---

## Bug found and fixed

**Commit:** `fad2887` — "fix: signup-free-tier 401 on valid token — used flag has dual semantics"
**Pushed:** main, 2026-05-07

**Root cause:** `phone_verification_codes.used` is set to `True` by `verify_phone` when
it issues the verification_token (marks OTP consumed, prevents OTP reuse). `signup_free_tier`
was also checking `used=True` as a guard against token replay — but since `used` is
always `True` for any legitimately issued token, this made the happy path unreachable.
Every real call returned 401.

**Fix:**
- Removed `if row.get("used"): raise 401` from `signup_free_tier` (auth.py:69-70)
- Replaced post-signup `phone_verification_codes.update({"used": True})` with
  `phone_verification_codes.update({"token_expires_at": NOW()})` — immediately
  expires the token after use instead of re-setting a field that's already True
- `signup_free_tier` no longer selects `used` from the DB (removed from `.select()`)

**Tests:** 11 passing (was 10 — added `test_regression_verify_phone_used_flag_does_not_block_signup`,
removed `test_ac2_used_token_returns_401` which was testing the buggy behavior)

---

## Production verification

### Confirmed passing (2026-05-07 session):

- **Bogus token → 401**: verified post-deploy via curl. Behavior unchanged.
- **No user created**: confirmed via auth.users query — 0 users in last 3h before fix.
- **Token state**: the `ed812333` row (`used=True`, `phone_hash=1c690f9c...`) was
  correctly identified as a victim of the bug, not user error.

### Pending (resume tomorrow):

- **AC1 happy path**: the `+16475155754` verification_token expired at 15:31 EDT
  before the fix was deployed and verified. Dustin's wife is unavailable tonight.

**To resume AC1 tomorrow:**
1. Flip `FREE_TIER_ENABLED=true` in Railway
2. Call `POST /auth/send-verification-code` with `{"phone": "+16475155754"}`
3. Enter the SMS code via `POST /auth/verify-phone`
4. Use the returned `verification_token` in `POST /auth/signup-free-tier` with real
   email/password/phone_e164
5. Expect 201 with `{"access_token": ..., "user": {"tier": "free"}}`
6. Confirm user exists in Supabase auth.users and user_profiles has `free_tier_used_at` set
7. Confirm token row has `token_expires_at` set to the past (immediate expiry after signup)
8. Flip `FREE_TIER_ENABLED=false` after verification

---

## All other Block 5a ACs (status before this session's changes)

| AC | Description | Status |
|----|-------------|--------|
| AC0 | Kill switch → 503 | PASS (unit test) |
| AC1 | Happy path end-to-end | **PENDING** (see above) |
| AC2 | Expired token → 401 | PASS (unit test) |
| AC3 | Phone mismatch → 401 | PASS (unit test) |
| AC4 | Phone already claimed → 409 | PASS (unit test) |
| AC5 | Email already exists → 409 | PASS (unit test) |
| AC6 | Compensating delete on mid-flow failure → 500 | PASS (unit test) |
| AC7 | Bogus token → 401 (not 500) | PASS (unit+prod) |

---

## FREE_TIER_ENABLED state

Set to `false` in Railway after bogus-token post-deploy verification.
Must be set to `true` before resuming AC1 tomorrow. Reset to `false` after.

---

## Related files

- Plan doc: `docs/superpowers/plans/2026-05-07-block-5a-free-tier-signup-api.md`
- Fix commit: `fad2887`
- Phone verification router: `app/routers/phone_verification.py`
- Auth router (fixed): `app/routers/auth.py`
- Tests: `tests/test_signup_free_tier.py`
- Architecture note: `docs/ARCHITECTURE.md` (phone_verification_codes Known Issues + decision log)

---

## 2026-05-08 closeout

AC1 verified PASS by data inspection (no fresh re-run needed). The 22:19:07 UTC signup of dustinkeating87+freetier1@gmail.com on +16475155754 — captured the night this debug doc was written — turned out to be a successful happy-path run. All fields land where the spec requires:
- auth.users exists with email_confirmed_at and last_sign_in_at
- user_profiles.phone_verified=true, free_tier_used_at set, Stripe fields NULL, is_active=false
- phone_verification_codes.token_expires_at set to ~signup time (token immediately invalidated)
- 0 alert_profiles for the user (correct — Block 5b ships alert creation)

Block 5a closed. See ARCHITECTURE.md decision log entry dated 2026-05-08 for full retro.
