===PASTE START===
# Block 5c — Lovable signup page prompt skeleton

**Date:** 2026-05-07
**Master ticket:** `86ahavm5n` (free-tier launch)
**Block ticket:** `86ahbkwf6` (Lovable signup blocker — pre-launch critical)
**Depends on:** Block 5a deployed + verified, Block 5b deployed + verified, `FREE_TIER_ENABLED=true` flipped on Railway
**Blocks:** Nothing (final block in the signup flow; closes `86ahbkwf6` when Lovable flow works end-to-end)

---

## Goal

Provide a copy-paste Lovable prompt skeleton for the new `/signup` page. Free-tier is the default entry point. Two-step form: phone OTP → email + password. Wired to the Block 5a/5b API. Closes `86ahbkwf6` when the full POST flow works end-to-end in production.

This document contains no API code. All changes are frontend-only (Lovable repo `foreward`).

---

## Pre-paste checklist (Dustin completes ALL of these before pasting the prompt)

- [ ] Block 5a deployed: `curl -sS https://web-production-b24db.up.railway.app/auth/signup-free-tier -X POST -H "Content-Type: application/json" -d '{}'` returns **503** (flag off) or **201** (flag on). Confirm Railway shows the deployment is active.
- [ ] Block 5b deployed: Confirm Railway web service is on a commit after Block 5b Task 6. Paid alert regression passed.
- [ ] `FREE_TIER_ENABLED=true` set in Railway `web` service env vars. (Do NOT flip until 5a + 5b are confirmed deployed.)
- [ ] At least 1 active paid alert exists in `alert_profiles` so `/courses/available-for-free-tier` returns courses. Run: `curl -sS https://web-production-b24db.up.railway.app/courses/available-for-free-tier`. Expect `{"courses": [...], "count": N, "available": true}` with N ≥ 1.
- [ ] Test user `dustinkeating87+test@gmail.com` (UID `76f71a7d-5f4b-4284-92cb-6504ec71f7c3`, phone `+16475155754`) deleted from Supabase auth. This frees up the phone hash for the verified phone number on `+16475155754`. (SQL: `DELETE FROM auth.users WHERE id = '76f71a7d-5f4b-4284-92cb-6504ec71f7c3';` — cascades to `user_profiles`.)
- [ ] `phone_verification_codes` migration applied to prod (Block 2). Confirm via: `SELECT COUNT(*) FROM phone_verification_codes;` in Supabase SQL Editor — any response (including 0) confirms the table exists.
- [ ] `{{API_BASE_URL}}` below is correct: `https://web-production-b24db.up.railway.app`

---

## Lovable prompt

Paste the following block verbatim into the Lovable AI prompt input. Replace `{{API_BASE_URL}}` with `https://web-production-b24db.up.railway.app` before pasting (or leave the placeholder if Lovable supports it).

---

We're adding a new /signup page to Good Lie Golf (goodlie.golf). This is the free-tier signup flow and will be the default entry point for new users.

DESIGN SYSTEM — utility chassis only (NOT the marketing chassis):
- Five-color palette: --fairway #2D5016, --bone #F5F0E8, --pencil #3D3D3D, --topo #8B9E6E, --flag #C8102E
- Typography: "New York" (serif) for display headings, Inter for UI/body, JetBrains Mono for data fields and codes
- No decorative backgrounds, gradients, or brand illustrations on this page — clean utility card only

PAGE: /signup
LAYOUT: Single centered card, max-width 400px. No sidebar, no progress bar. Match the same card style as the existing /login page.

HERO COPY (top of form card):
  Heading: "Try one alert, free for 14 days"
  Sub-heading: "No credit card. One alert per phone number."

FORM — TWO STEPS (render Step 1 first; reveal Step 2 only after phone is verified):

--- STEP 1: Phone verification ---

  Label: "Mobile number"
  Input: type="tel", placeholder="+1 (416) 555-0100"
  Client-side: enforce E.164 format (leading +, digits only, 8–15 digits after +) before allowing submit
  Button: "Send code"

  On button click → POST {{API_BASE_URL}}/auth/send-verification-code
    Request body: { "phone": "<e164 value>" }
    On 200: reveal the OTP input below the phone field (do not clear phone field)
    On 429: inline error below field — "Too many attempts — wait a minute and try again"
    On 503: inline error — "Free-tier signup isn't available yet — check back soon"
    On any other error: inline error — "Couldn't send code. Please try again."

  After successful send, show OTP input:
    Label: "Verification code"
    Input: 6-digit numeric, type="text" inputmode="numeric", maxlength=6, JetBrains Mono font
    Button: "Verify"

  On Verify click → POST {{API_BASE_URL}}/auth/verify-phone
    Request body: { "phone": "<e164>", "code": "<6-digit string>" }
    On 200: store response.verification_token in component state (not localStorage — it's short-lived), advance to Step 2
    On 401: inline error below OTP input — "Incorrect or expired code"
    On any other error: inline error — "Verification failed. Please try again."

  "Resend code" link (shown after first successful send; grayed-out during 60s cooldown):
    On click → POST {{API_BASE_URL}}/auth/resend-verification-code
      Request body: { "phone": "<e164>" }
      On 200: show brief confirmation "New code sent" next to link; reset cooldown timer
      On 429: gray out link, append "(wait 60s)" beside it

--- STEP 2: Account creation (shown only after phone verified) ---

  Label: "Email address"
  Input: type="email"

  Label: "Password"
  Input: type="password"
  Inline requirement shown below field: "At least 8 characters"

  Button: "Create account" (primary action, --fairway background)

  On button click → POST {{API_BASE_URL}}/auth/signup-free-tier
    Request body: { "email": "<email>", "password": "<password>", "phone_e164": "<e164>", "verification_token": "<stored token>" }
    On 201: store response.access_token and response.refresh_token in localStorage using the EXACT same keys as the existing /login page uses. Then redirect to /dashboard.
    On 401: inline error — "Phone verification expired — go back and re-verify your number" (show a "Start over" link that resets to Step 1)
    On 409: check response detail string:
      - Contains "Phone" or "phone" → "This phone number already has a Good Lie account. Sign in instead." (link to /login)
      - Contains "email" or "Email" → "An account with this email already exists. Sign in instead." (link to /login)
      - Anything else → "Account already exists. Sign in instead." (link to /login)
    On 503: inline error — "Free-tier signup isn't available yet"
    On any other error: inline error — "Signup failed. Please try again."

--- BOTTOM OF CARD ---

  "Already have an account? Sign in →" — routes to /login
  "Subscribe instead ($9.99/mo) →" — routes to the existing paid billing/checkout flow (same destination as the existing upgrade CTA on the dashboard)

IMPORTANT CONSTRAINTS — do NOT violate these:
1. Do NOT modify /login, /dashboard, /alerts, or any other existing page.
2. Do NOT add any API endpoints or edge functions. All calls use the three free-tier auth endpoints + signup-free-tier listed above.
3. Do NOT change how paid signup works. If there is an existing /signup that routes to Stripe/billing, leave it untouched.
4. The "Subscribe instead" link must route to exactly where the existing paid upgrade CTA on the dashboard points — do not create a new Stripe session here.
5. localStorage token keys must match exactly what the existing /login page writes — check the login implementation before writing the signup success handler.
6. Do NOT use bare "free" in hero copy. The spec copy above is final: "Try one alert, free for 14 days."

---

## Post-paste verification (Dustin runs this after Lovable renders and deploys)

1. Load `https://goodlie.golf/signup` — confirm hero "Try one alert, free for 14 days" and sub-heading render correctly
2. Enter a real phone number → "Send code" → confirm SMS received
3. Enter OTP → "Verify" → confirm Step 2 reveals (Step 1 inputs remain visible, OTP input hidden or greyed)
4. Enter email + password → "Create account" → confirm redirect to /dashboard
5. In Supabase SQL Editor: `SELECT id, email, phone_verified, free_tier_used_at FROM user_profiles WHERE email = '<the email you used>';` — confirm `phone_verified=true`, `free_tier_used_at IS NOT NULL`
6. From /dashboard: create an alert — confirm it saves successfully
7. In Supabase: `SELECT is_free_tier, polling_expires_at, renewals_used FROM alert_profiles WHERE user_id = '<new user id>';` — confirm `is_free_tier=true`, `polling_expires_at` ~14 days from now, `renewals_used=0`
8. Attempt a second alert from the same account — confirm 402 error surfaced in the UI
9. Click "Subscribe instead" link — confirm it reaches the paid checkout flow
10. Click "Already have an account? Sign in" — confirm /login loads

After all 10 steps pass: close ClickUp `86ahbkwf6`.

---

## Rollback

Set `FREE_TIER_ENABLED=false` on Railway — all free-tier API calls return 503, /signup page still renders but form submissions fail gracefully with "not available yet" copy. No DB changes to roll back (Supabase rows from test signups can be cleaned via SQL Editor if needed).
===PASTE END===
