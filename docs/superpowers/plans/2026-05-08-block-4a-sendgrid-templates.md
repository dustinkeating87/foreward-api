# Free-Tier Block 4a -- SendGrid Dynamic Templates for expiry emails

**Status:** plan
**Date:** 2026-05-08
**ClickUp:** `86ahazbr4` (scoped down -- Stripe coupon work deferred to Block 4b, see comment on ticket)
**Master:** `86ahavm5n` (Pricing redesign)

## Goal

Replace the plaintext free-tier expiry emails (shipped in Block 3) with SendGrid Dynamic Templates. The three templates already exist in SendGrid (created via API, IDs below). This block wires them into `free_tier_expiry_loop`.

## Out of scope (deferred to Block 4b)

- Stripe coupon generation
- Coupon codes embedded in email templates
- Frontend Checkout flow accepting coupon param

## Prereq state (already done before this block)

- Three Dynamic Templates created in SendGrid (Handlebars variables `{{first_name}}` and `{{course_name}}`, hardcoded CTAs to `https://goodlie.golf/subscribe`):
  - Expiry 1 (First Window): `d-f53c968e8bb645a0ba98844549b2d2f1`
  - Expiry 2 (Last Renewal): `d-bfbc0e264a2e4092ab236e6c594f7611`
  - Expiry 3 (Final): `d-af240773d6ec40899f6c20ae9c685dcf`
- SendGrid sender identity `hello@goodlie.golf` already authenticated (per ARCHITECTURE.md)
- `SENDGRID_API_KEY` already on Railway `web` service env vars

## Files to edit

1. **`foreward-api/app/email.py`** -- add `send_dynamic_template()` helper alongside existing `send_alarm_email()` / `send_recovery_email()`. Posts to `/v3/mail/send` with `template_id` + `dynamic_template_data` payload instead of inline `subject`/`content`.

2. **`foreward-api/app/free_tier_expiry_loop.py`** (or wherever the loop currently lives -- verify path) -- at the three transition points where plaintext emails currently fire, swap to `send_dynamic_template()` with the right template_id and data dict.

3. **`foreward-api/app/config.py`** (or wherever Settings lives) -- add three template ID config fields, sourced from env vars.

## Env vars to add (Railway `web` service)

```
SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_1=d-f53c968e8bb645a0ba98844549b2d2f1
SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_2=d-bfbc0e264a2e4092ab236e6c594f7611
SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_3=d-af240773d6ec40899f6c20ae9c685dcf
```

(Railway env var step -- Dustin sets these manually after code lands.)

## Implementation notes

### `send_dynamic_template()` signature

```python
def send_dynamic_template(
    *,
    to: str,
    template_id: str,
    dynamic_data: dict,
    from_email: str = "hello@goodlie.golf",
    from_name: str = "Good Lie",
) -> bool:
    """
    Sends a SendGrid Dynamic Template email.

    Returns True on 2xx, False on failure. Does not raise -- failures
    must NEVER break callers (same contract as existing alarm emails).
    """
```

### Payload structure (SendGrid `/v3/mail/send`)

```json
{
  "from": {"email": "hello@goodlie.golf", "name": "Good Lie"},
  "personalizations": [{
    "to": [{"email": "<user>"}],
    "dynamic_template_data": {
      "first_name": "...",
      "course_name": "..."
    }
  }],
  "template_id": "d-..."
}
```

Critical: when `template_id` is set, do NOT include `subject` or `content` blocks. SendGrid uses what's defined in the template version.

### Where to wire it in `free_tier_expiry_loop`

The loop currently sends plaintext emails at three transitions (per Block 3 entry in ARCHITECTURE.md):

1. **First expiry** -- alert moves from `expiry_state=NULL` -> `expiry_state='expired_pending_renewal'`, `renewals_used=0`. Send Expiry 1.
2. **Second expiry** -- alert moves to `expiry_state='expired_pending_renewal'`, `renewals_used=1`. Send Expiry 2.
3. **Final expiry** -- alert moves to `expiry_state='final_expired'`, `final_expired_at` set. Send Expiry 3.

For each of these, swap the existing `send_*` call for:

```python
send_dynamic_template(
    to=user_profile["notify_email"] or user_profile["email"],
    template_id=settings.sendgrid_template_free_tier_expiry_N,
    dynamic_data={
        "first_name": user_profile.get("first_name", "there"),  # fallback if no first name
        "course_name": alert_courses_to_display_name(alert["courses"]),  # see fallback note
    },
)
```

### `first_name` source -- open question

`user_profiles` table has no `first_name` column (per ARCHITECTURE.md schema). Options:

1. Use a fallback like `"there"` always (Hey there,)
2. Pull from Supabase auth.users metadata if it's set during signup
3. Add a `first_name` column (out of scope for this block)

**Decision:** option 1 for this block. Email salutation becomes "Hey there," when no name is known. Logged as known limitation; addressing properly is a future block.

### `course_name` source

`alert_profiles.courses` is a `text[]` array of course slugs. The email needs a human-readable name. Two cases:

- Single course in array: render the human name for that slug
- Multiple courses: render `"X, Y, and Z"` or just count: `"{n} courses"`

For this block: if single course, use its display name; if multiple, render `"{n} courses you're watching"`. Slug->name mapping already exists somewhere in the codebase (used by SMS notifications); reuse that, don't duplicate.

If the helper doesn't exist or is hard to find: Claude Code surfaces this as a blocker before implementing. Don't invent a new mapping.

### Failure handling

- SendGrid 4xx/5xx must be logged but NOT raised. The expiry loop continues processing other alerts.
- If `template_id` env var is unset (Railway env var setup pending), log and skip -- don't crash. This is important because env vars get added AFTER code deploys.

### Tests

- Unit test for `send_dynamic_template()` -- mock httpx, verify payload shape (template_id present, no subject/content fields, dynamic_template_data dict structure)
- Unit test for course_name rendering: single course slug -> "Lakeview", multi -> "3 courses you're watching"
- No integration test against real SendGrid (don't burn API quota in CI)

## Acceptance criteria

- AC1: Plaintext free-tier expiry email code paths replaced with `send_dynamic_template()` calls
- AC2: All three template IDs sourced from env vars, not hardcoded
- AC3: When `SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_*` env var is unset, code logs warning and skips email send (does not crash the expiry loop)
- AC4: `dynamic_data` dict contains `first_name` (with fallback) and `course_name` keys
- AC5: SendGrid API failures don't break the expiry loop (try/except wrapping)
- AC6: Unit tests pass for `send_dynamic_template()` payload shape and course_name rendering
- AC7: Existing alarm/recovery emails (silent-failure alerts) unchanged -- they keep using inline content, not templates

## Verification (manual, after deploy)

1. Set `SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_*` env vars on Railway (three IDs)
2. Wait for Railway redeploy
3. Manually trigger a free-tier expiry transition via SQL:

```sql
-- Pick a test alert, set polling_expires_at to past so the loop transitions it
UPDATE alert_profiles
SET polling_expires_at = now() - interval '1 minute',
    is_free_tier = true,
    expiry_state = NULL
WHERE id = '<test-alert-id>';
```

4. Wait up to 5 min for `free_tier_expiry_loop` to pick it up (loop runs every 5 min per ARCHITECTURE.md)
5. Verify email arrives in test inbox with HTML formatting and correct dynamic data
6. Repeat for transition 2 and 3 by adjusting `expiry_state` and `renewals_used`

## Rollback

`FREE_TIER_ENABLED=false` already kills all free-tier paths in production. Block 4a is dormant code in prod until Block 9 cutover. If something's wrong: revert the commit, redeploy. No data state to clean up.

## Branding fix worth doing in same commit

`from_name="Good Lie"` (per Dustin's call). Replaces any prior `"Tee Sniper"` or `"FOREward"` strings in email send paths. Grep for stragglers while we're in `app/email.py`.

## ClickUp

- Closes `86ahazbr4` (scoped to 4a; coupon work moved to a new Block 4b ticket to be filed at session close)
