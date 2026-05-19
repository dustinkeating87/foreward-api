# Good Lie Golf — Architecture & Decision Log

**Last verified:** 2026-05-18 (Pricing pivot — free tier replaces 7-day trial)
**Maintained by:** Claude sessions, in collaboration with Dustin
**Read this file at the start of any Good Lie Golf work.** It is the source of truth for how the app is built. ClickUp space `Good Lie Golf` (id `901313780791`) is the source of truth for *open work*. Both must be checked. If you make architectural decisions or learn schema details during a session, update this file before ending the session.

Raw scavenged data lives in `./scavenge-raw/` next to this file. Re-run scavenge if anything below feels stale.

---

## Product

**Good Lie Golf** — tee-time alert service for GTA-area golf courses. Users sign up, configure preferred courses + day/date/time windows + player count + holes, and receive SMS notifications when matching tee times open up. The product is the *alert*, not the *booking*. Booking is left to the user.

**Positioning:** the ethical, golfer-friendly alternative to private auto-booking bots.

**Pricing:** Free tier (one alert per user/phone, lifetime) → $9.99 CAD/mo paid for everything after. No upfront trial, no credit card to start.
**Domain:** https://goodlie.golf
**Instagram:** @playgoodlie (active, secured Apr 25, 2026). @goodliegolf is squatted; reclaim attempt is parallel low-priority.

### Brand pivot history
The product has been renamed twice. References in older code still use earlier names — be alert when reading.

1. **Tee Sniper** (original — `foreward-scraper/tee_sniper.py` is the main scraper module; foreward-api README being updated 2026-05-03)
2. **FOREward / FOREward Tee Times** (Lovable project name; GitHub repo names — `foreward`, `foreward-api`, `foreward-scraper`)
3. **Good Lie Golf** (current — domain, IG handle, marketing)

### Internal terminology
- **"Snipe" / "snipes"** = internal shorthand for an alert event. Inherited from "Tee Sniper" branding.
- **NEVER use "snipe" in user-facing copy.** Always "alert," "match," or "opening." See `.auto-memory/goodliegolf_terminology.md`.

---

## Free Tier (product spec)

The free tier is a guaranteed-successful demonstration of the product. New users sign up with phone+email, verify their phone, and get one free alert that behaves identically to a paid alert. After the alert fires, they receive one SMS + one email and are done — no retry, no second alert, no editing. The only path forward is a paid subscription. If the alert hits `date_to` without ever firing, the user gets exactly one grace retry. Phone and email are permanently locked to the account.

**Implementation notes:**
- `user_profiles.free_tier_used_at` is stamped at **first alert creation** (`alerts.py:99`), not at signup. Signup only writes `phone_verified`, `phone_hash`, and `notify_phone` to `user_profiles`. Any code that stamps `free_tier_used_at` at account-creation time is wrong.
- Phone uniqueness is enforced at signup time via `ix_user_profiles_phone_hash_unique` (unique partial index on `user_profiles(phone_hash) WHERE phone_hash IS NOT NULL`). This index locks a phone to exactly one account from the moment the phone is verified — independent of whether the user has created their free alert yet. The earlier `ix_user_profiles_phone_hash_free_tier` (partial on `WHERE free_tier_used_at IS NOT NULL`) was replaced on 2026-05-09 because it allowed phone reuse before the first alert was created.

Canonical spec: `docs/PRODUCT_FREE_TIER.md`. Any work touching free-tier code paths (`is_free_tier`, `free_tier_used_at`, `FREE_TIER_ENABLED`, signup-free-tier endpoint, alert creation gate) must read that document before making changes.

---

## Stack at a glance

| Layer | Platform | Repo | Where edits happen |
|---|---|---|---|
| **Frontend** | Lovable (project `c3bd43d3-7123-4957-8d39-466b1ada76f6`, name "FOREward Tee Times") → custom domain `goodlie.golf` | `dustinkeating87/foreward` (TypeScript/React, shadcn/ui, Bun) | Lovable AI prompts |
| **Backend API** | Railway project `spirited-youthfulness` → service `web` → `https://web-production-b24db.up.railway.app` | `dustinkeating87/foreward-api` (FastAPI, Python) | Claude Code terminal |
| **Scraper / Worker** | Railway project `resourceful-delight` → service `worker` (EU West, Amsterdam) | `dustinkeating87/foreward-scraper` (Python) | Claude Code terminal |
| **Database** | Supabase project `offtdltmvjfizkoeywei` (Kick Rocks Inc org, us-east-2 Ohio, t4g.nano) | Schema lives in `foreward-api/supabase/migrations/` | SQL editor + Claude Code |
| **SMS** | Twilio | Called from `foreward-scraper` (worker is the SMS sender for user-facing alerts) | Env vars: `TWILIO_SID`, `TWILIO_TOKEN`, `TWILIO_FROM` |
| **Email** | SendGrid (primary), SMTP (fallback) | Both services. **API uses SendGrid for ops alerts as of 2026-05-03.** | Env vars: `SENDGRID_API_KEY`, `SMTP_*` |
| **Billing** | Stripe — $9.99/mo subscription | `foreward-api/app/routers/billing.py` | Env vars: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET` |
| **Captcha solver** | 2Captcha (Turnstile, ~1-2 solves/min, ~$1.45/1000) | Used by GTG scraper only | Env var: `CAPTCHA_API_KEY` |
| **Proxies** | Webshare (20-proxy rotation) | `foreward-scraper` | Env vars: `PROXY_URL` (singular, legacy), `PROXY_URLS` (plural, current) |
| **CI** | GitHub Actions (parse-check on push to main) | Both `foreward-api` and `foreward-scraper` have `.github/workflows/ci.yml` (added 2026-05-03) | GitHub web UI / Claude Code |
| **Backups** | Local pg_dump → Google Drive (weekly Sunday 10 AM via launchd) | `foreward-api/scripts/backup/` | Local Mac via `~/.goodlie-backup-env` config |
| **Task tracking** | ClickUp space `Good Lie Golf` (id `901313780791`) | — | ClickUp connector |

### Routing rule for any change
- **Schema change** → numbered SQL file in `foreward-api/supabase/migrations/`, applied via Supabase SQL editor, then committed
- **API endpoint, billing, auth, admin, ops alerting** → `foreward-api` via Claude Code terminal
- **Scraping, polling, SMS sending, alert dedupe** → `foreward-scraper` via Claude Code terminal
- **Frontend page, signup flow, dashboard, ticker UI** → Lovable prompts
- **Verification / planning / content / forum replies / brand work** → Cowork (this)
- **CI workflow files** (`.github/workflows/*`) → GitHub web UI if local PAT lacks `workflow` scope; otherwise Claude Code

Backend changes do NOT belong in Lovable. Lovable holds only the frontend and one edge function (`course-request`) that submits course requests.


---

## Frontend style guide

**As of 2026-05-08.** This supersedes any earlier brief or design-related instruction in older Lovable prompts, design docs, or memory. Lovable is the live source of truth for what's deployed; this section is the canonical written spec.

### Color palette
No grays. No pure black. No additional colors beyond these six.

- `#FAF7F2` — bone (page background, ambient)
- `#FFFFFF` — white (content section bands, header)
- `#1A1816` — pencil (body text, headlines, secondary borders)
- `#8A9485` — topo sage (mono labels, secondary text, faint line work; use at varying opacities where gray would normally go)
- `#FF4A1F` — flag orange (single accent — primary CTA outline, mono numerals, surgical use only)
- `#2D3B2A` — fairway green (DEPRECATED as button fill; reserved for future inverted sections only — do not use as button fill on new pages)

### Typography
- **Display:** Inter weight 900. Stack: `'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif`. Letter-spacing -0.02em on hero scale, -0.01em smaller. NOT Space Grotesk. NOT New York. NOT a serif.
- **Body & UI:** Inter weights 400-600, same stack as display.
- **Mono:** JetBrains Mono. Stack: `'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace`. Used for eyebrow labels, ticker data, mono numerals, all data-feeling content. Eyebrows uppercase with 0.08em letter-spacing.

### Layout architecture
- Page background is the topo illustration (ambient golf course line drawing) over `#FAF7F2` bone, with a 60% bone overlay for legibility.
- Content sections sit on full-width white (`#FFFFFF`) bands.
- Transparent vertical gaps between bands (96px desktop / 64px mobile) where the topo background shows through.
- Hero section is transparent — sits directly on the topo composition, no white band.
- Header is a white band at top of page. Footer (when built) is a white band.

### Component patterns
- **Primary button:** transparent fill, 1.5px `#FF4A1F` border, `#FF4A1F` text. Hover: fills with orange, text becomes `#FAF7F2`. Padding 14px vertical / 28px horizontal. 4px radius. Min-width 200px.
- **Secondary button:** transparent fill, 1.5px `#1A1816` border, `#1A1816` text. Hover: fills with pencil, text becomes `#FAF7F2`. Same dimensions as primary.
- **Buttons paired side-by-side:** 16px gap, both centered as a unit.
- **Eyebrow labels:** mono, 11px, weight 500, color `#8A9485`, uppercase, 0.08em letter-spacing.
- **Mono numerals (01, 02, 03):** mono, 11px, weight 500, color `#FF4A1F`, uppercase, 0.08em letter-spacing.

### Spacing
- 8px base unit. Use multiples (8, 16, 24, 32, 48, 64, 96, 128).
- Section internal padding: 64px top/bottom desktop, 48px mobile (white bands).
- Container max-width: 1280px.

### Voice and copy
- Informed, dry, confident. Player-side, not country-club.
- Specific over generic, but don't burn in numbers that change ("every course we cover" not "22 courses").
- No exclamation marks. No marketing superlatives. No "snipe" in user-facing copy — always "alert".
- Numbers and data render in mono inline.
- No "7-day free trial" language anywhere — that pricing model is retired.

### Things explicitly out
- No Space Grotesk anywhere.
- No serif fonts (no New York, Georgia, etc.).
- No grays — use `#8A9485` topo at varying opacities.
- No pure black — use `#1A1816`.
- No script fonts.
- No gradients, no box shadows, no dark mode, no borders on content bands.

---

## Frontend signup flow

**As of 2026-05-08.** The free-tier signup page lives at `/auth?mode=signup` on Lovable's `foreward` repo. It REPLACES the previous paid signup flow at the same URL (which redirected to Stripe Checkout). Per the locked pricing model, all new users now enter the product through free-tier signup; paid upgrade happens later, from the dashboard, after a user's free alert fires.

### Layout
Vertical band stack: four full-width white (`#FFFFFF`) horizontal bands stacked vertically, separated by transparent gaps where the topo illustration page background shows through. Bands share equal `min-height` for visual rhythm.

- **Band 1 (Hero):** "Try Good Lie, free" / "No credit card. One alert per phone number." (updated Block 8 — previous copy "Try one alert, free for 14 days" was a Block 3 leftover; 14-day window does not exist in the simplified free-tier model)
- **Band 2 (Step 01):** Phone verification — mobile number + OTP send/verify
- **Band 3 (Step 02):** Account creation — email + password — RENDERED ONLY AFTER phone verification succeeds (not display:none, not rendered at all in the DOM until verify-phone returns 200)
- **Band 4 (Footer):** "Already have an account? Sign in" + fine-print pricing line ("Paid plan ($9.99/mo) unlocks unlimited alerts after your first one fires.")

### Page background
The topo illustration is a page-wide persistent background, NOT confined to band gaps. A 60% opacity bone (`#FAF7F2`) overlay sits on top of the topo for legibility. White content bands occlude the topo where they render; transparent gaps between bands reveal it.

### Form behavior
Step 02 inputs and submit are not rendered until phone verification succeeds. After successful `POST /auth/verify-phone`, Band 3 mounts into the DOM between Band 2 and Band 4, and the page smooth-scrolls down to it.

### API endpoints consumed
- `POST /auth/send-verification-code`
- `POST /auth/verify-phone`
- `POST /auth/resend-verification-code`
- `POST /auth/signup-free-tier`

All four endpoints are gated behind `FREE_TIER_ENABLED` env var on Railway. As of 2026-05-08, `FREE_TIER_ENABLED=false` — meaning the signup page renders but form submissions return 503 with "not available yet" copy. Flag flips at Block 9 cutover.

### Localstorage tokens
Successful signup writes `access_token` and `refresh_token` to localStorage using the same keys as the existing sign-in flow at `/auth?mode=signin`.

### Deferred verification
Block 5b's full gate ladder (503 → 403 → 402 → 402 → 200 on `POST /alerts`) and the full signup loop end-to-end are NOT prod-verified as of 2026-05-08. Verification deferred to real-user walkthrough on a fresh phone (the burnt phone `+16475155754` is not usable). Pre-launch checklist (ClickUp `86ahbkx68`, `86ahbfptb`) tracks this requirement before flipping `FREE_TIER_ENABLED=true`.

---

## Database schema (Supabase project `offtdltmvjfizkoeywei`)

Six tables, all with RLS enabled. Verified live 2026-05-03 (afternoon).

### `user_profiles`
Extends `auth.users` 1:1 via `handle_new_user` trigger.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | NO | — | PK; matches `auth.users.id` |
| email | text | YES | — | denormalized from auth |
| is_active | boolean | YES | false | gate flag |
| is_beta | boolean | YES | false | beta-user flag |
| stripe_customer_id | text | YES | — | Stripe linkage |
| stripe_subscription_id | text | YES | — | Stripe sub linkage |
| created_at | timestamptz | YES | now() | |
| updated_at | timestamptz | YES | now() | |
| notify_email | text | YES | — | preferred notification email (overrides auth email) |
| notify_phone | text | YES | — | E.164 phone |
| notify_updated_at | timestamptz | YES | — | when notification prefs last changed |
| trial_end | timestamptz | YES | — | LEGACY — 7-day trial model retired 2026-05-18. Column kept for existing rows; new signups should not have this set. Pivot to free-alert model. |
| phone_verified | boolean | NO | false | Set true on successful 6-digit verification at free-tier signup |
| free_tier_used_at | timestamptz | YES | — | Block 1 (2026-05-07) — set when user first uses free tier; lifetime once-only |
| phone_hash | text | YES | — | Block 2 — SHA-256 hexdigest of E.164 phone (no salt); used for uniqueness check |
| free_tier_grace_retry_used_at | timestamptz | YES | NULL | Block 6 — set when free-tier user uses their one non-firing-expiry grace retry; NULL = grace available |

**RLS:** `Users can read own profile` — `SELECT` for `public` role where `auth.uid() = id`.

### `alert_profiles`
Per-user saved alert criteria.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | NO | gen_random_uuid() | PK |
| user_id | uuid | NO | — | owner; FK to `auth.users(id)` ON DELETE CASCADE |
| courses | text[] | YES | '{}' | array of course identifiers |
| date_from | date | NO | — | earliest matching tee date |
| date_to | date | NO | — | latest matching tee date |
| time_from | text | NO | — | earliest matching tee time |
| time_to | text | NO | — | latest matching tee time |
| players | int | NO | — | required slot capacity |
| holes | int | NO | — | 9 or 18 |
| notify_email | text | YES | — | per-alert override |
| notify_phone | text | YES | — | per-alert override |
| active | boolean | YES | true | **legacy** — kept for backwards compat; `status` is the truth |
| status | text | NO | 'active' | CHECK in (active, fired, expired, paused) |
| created_at | timestamptz | YES | now() | |
| updated_at | timestamptz | YES | now() | |
**NOTE 2026-05-18:** The 14-day polling window + 2-renewal model these columns supported has been retired. New free-tier model is: one alert per user/phone, runs until first successful fire OR date_to expiry (whichever first). On successful fire → hard paywall for alert #2. On date_to expiry without fire → free re-attempt allowed. `polling_expires_at`, `renewals_used`, `expiry_state`, `final_expired_at` may be vestigial — verify before any code that reads them is touched. `is_free_tier` still used to tag the alert.

| is_free_tier | boolean | YES | false | Block 1 (2026-05-07) — true if alert was created under free-tier rules |

**Status semantics (one-shot model, locked 2026-05-03):**
- `active` — scraper matches against this alert; SMS will fire on next match
- `fired` — alert has fired once; will not fire again until user clicks "Try again"
- `expired` — `date_to` has passed; permanently inactive unless user edits dates
- `paused` — user manually disabled (legacy `active=false` behavior)

**RLS:** `Users can manage own alerts` — `ALL` for `public` role where `auth.uid() = user_id`.
**Index:** `alert_profiles_status_active_idx` partial on `(status)` WHERE `status = 'active'` (hot path for scraper).

### `sent_slots`
Alert event ledger / dedupe table. Each row = "this alert fired on this slot — don't fire again."

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | bigint | NO | nextval | PK |
| alert_id | text | NO | — | references `alert_profiles.id` (text, not uuid — note mismatch; no FK constraint) |
| slot_key | text | NO | — | composite of course + tee_time + players + holes |
| created_at | timestamptz | YES | now() | when the alert was sent |
| user_id | uuid | YES | — | denormalized from alert.user_id; **no FK constraint** |
| course_name | text | YES | — | denormalized for activity ticker |
| tee_time | timestamptz | YES | — | actual tee time of the slot (not insert time) |
| players | int | YES | — | slot capacity |
| taken_at | timestamptz | YES | — | set by scraper when slot disappears from a productive poll |
| scanned_at | timestamptz | YES | — | when scraper detected the slot — used for "Available as of {time}" SMS |

**Indexes:**
- Unique on `(alert_id, slot_key)` for dedupe
- Btree on `created_at DESC` for chronological reads
- `sent_slots_user_id_idx` on `(user_id)`
- `sent_slots_activity_idx` partial on `(created_at DESC)` WHERE `course_name IS NOT NULL`

**RLS:** `No direct client access to sent_slots` — `ALL` for `anon` and `authenticated` roles, `using = false` (deny-all). Service role bypasses.

### `course_requests`
User submissions to add a new course to the platform.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | NO | gen_random_uuid() | |
| course_name | text | NO | — | |
| email | text | YES | — | |
| created_at | timestamptz | YES | now() | |
| user_id | uuid | YES | — | FK to `auth.users(id)` ON DELETE SET NULL |
| user_email | text | YES | — | |

**RLS:** `service_role_modify` (ALL) and `service_role_select` (SELECT) — service role only.
**Edge function:** `course-request` in Lovable (the only Lovable edge function) writes to this table.

### `invite_codes`
Beta gating.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | NO | gen_random_uuid() | |
| code | text | NO | — (unique index) | |
| created_at | timestamptz | YES | now() | |
| used | boolean | YES | false | |
| used_by | uuid | YES | — | FK to `auth.users(id)` **NO ACTION on delete** — see foreign keys section |
| used_at | timestamptz | YES | — | |
| note | text | YES | — | |

**RLS:** enabled, no policies captured (effectively service-role-only via PostgreSQL default).

### `phone_verification_codes`
Short-lived OTP rows for free-tier phone verification (Block 2).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | NO | gen_random_uuid() | PK |
| phone_hash | text | NO | — | SHA-256 of E.164 phone |
| code | text | NO | — | 6-digit OTP (plaintext, short-lived) |
| verification_token | text | YES | — | Set on successful verify; consumed by Block 5 signup |
| created_at | timestamptz | NO | now() | |
| expires_at | timestamptz | NO | — | Code TTL: created_at + 10 min |
| token_expires_at | timestamptz | YES | — | Token TTL: verified_at + 30 min |
| resend_count | int | NO | 0 | Total resends since last send-verification-code |
| last_resend_at | timestamptz | YES | — | Enforces 60s cooldown between resends |
| used | boolean | NO | false | True after OTP verified by `verify_phone` (marks OTP consumed, NOT verification_token spent). `signup_free_tier` must NOT gate on this column — see Known Issues. |

**Index:** `ix_pvc_phone_hash` on `(phone_hash)`.
**RLS:** enabled, service-role only (API uses `supabase_admin` for all reads/writes).

**Known issue — `used` column overload (fixed 2026-05-07, Block 5a):** `verify_phone` sets `used=True` when issuing the verification_token (correct — prevents OTP reuse). `signup_free_tier` originally also checked `used` to guard against token replay — but since `used` is always True for any legitimately issued token, this made the happy path unreachable (always 401). Fixed by removing the `used` check from `signup_free_tier` and expiring the token post-signup via `token_expires_at = NOW()` instead. Any future block that touches this table should treat `used` as "OTP phase done" only, never as "signup phase done."

### `scraper_health`
Single-row health table for the worker.

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | int | NO | — (always 1) |
| last_heartbeat | timestamptz | YES | — |
| last_poll | int | YES | — |
| updated_at | timestamptz | YES | now() |
| slots_last_poll | jsonb | YES | '{}' (per-platform slot count) |
| consecutive_zero_polls | jsonb | YES | '{}' (per-platform alarm tracker) |
| last_productive_poll | timestamptz | YES | — |

Used by `/scraper-heartbeat` (POST from worker) and surfaced via `/admin/scraper-health` (GET) and `/admin/dashboard`.

**As of 2026-05-03 (afternoon):** the `/scraper-heartbeat` handler also reads prev `consecutive_zero_polls` BEFORE upserting and fires email alerts on threshold transitions (see "Silent-failure alerts" below).

**RLS:** enabled, service-role-only.

### Foreign keys (corrected 2026-05-03)

The previous version of this doc claimed "no foreign keys exist anywhere in `public`." That was wrong. Four FKs reference `auth.users`:

| Table | FK column | On delete | Notes |
|---|---|---|---|
| `user_profiles` | `id` | CASCADE | 1:1 extension of auth.users |
| `alert_profiles` | `user_id` | CASCADE | user deletion auto-cleans their alerts |
| `course_requests` | `user_id` | SET NULL | user deletion preserves the request |
| `invite_codes` | `used_by` | NO ACTION (blocks delete) | must be un-used (set to NULL) before deleting auth user |

**`sent_slots.user_id` has no FK** — referential integrity is application-level only there. This was the gap that left 61 orphan sent_slots rows from pre-launch test alerts (harmless, see "Live state" below).

### Triggers / functions
- **`auth.users.on_auth_user_created`** — AFTER INSERT, executes `public.handle_new_user()` which inserts `(id, email)` into `public.user_profiles`. SECURITY DEFINER. Pre-trigger users gap closed 2026-05-03 by deleting 14 orphan auth.users.

### Migrations system
**In use as of 2026-05-03.** Convention: numbered SQL files in `foreward-api/supabase/migrations/`, applied via Supabase SQL Editor, then committed.

Committed migrations:
- `20260429_enable_rls_sent_slots.sql` — commit `fb13669`
- `20260503_alert_lifecycle_and_sent_slots_columns.sql` — commit `73920c3`
- `20260506_add_captcha_balance_to_scraper_health.sql`
- `20260506_add_heartbeat_alarm_state.sql`
- `20260506_add_free_tier_columns.sql` — commit TBD (this session)
- `20260506_add_phone_verification_codes.sql` — Block 2; committed, not yet applied to prod (Dustin applies via SQL Editor)
- `20260508_add_captcha_balance_alarm_state.sql` — applied 2026-05-08, commit `29f0e3a` (3 new columns on `scraper_health` for 2Captcha balance auto-alert)
- `20260509_simplify_free_tier.sql` — Block 6 cleanup, applied 2026-05-09; drops Block 3 lifecycle columns (5 columns from `alert_profiles` and `user_profiles`), drops `ix_alert_profiles_polling_expires_at_free_tier` index, adds `user_profiles.free_tier_grace_retry_used_at`
- `20260509_phone_hash_unique_on_signup.sql` — applied 2026-05-09; drops `ix_user_profiles_phone_hash_free_tier` (partial WHERE `free_tier_used_at IS NOT NULL`), creates `ix_user_profiles_phone_hash_unique` (unique partial WHERE `phone_hash IS NOT NULL`). Decouples phone-reuse prevention from free-tier consumption — phone is now locked at signup, independent of alert creation state.

`supabase_migrations.schema_migrations` table still does not exist; using the directory as the registry rather than the Supabase CLI's tracking system. Acceptable for this scale.

### Extensions
`pg_stat_statements` 1.11, `uuid-ossp` 1.1, `pgcrypto` 1.3, `supabase_vault` 0.3.1.

### Backups
**Weekly via local pg_dump → Google Drive, since 2026-05-03.** See "Backup & restore" section.

### Database password
Reset to alphanumeric-only 2026-05-03 (afternoon) to avoid URL-encoding issues with the local backup script's connection string. Stored in ClickUp `86ah8bnp3` (Credentials & secrets reference). **Application code does NOT use this password** — Railway services authenticate via JWT (`SUPABASE_KEY`/`SUPABASE_SERVICE_KEY`).


---

## Backend code map

### `foreward-api` (FastAPI)

```
foreward-api/
├── .github/
│   └── workflows/
│       └── ci.yml              ← parse-check on push to main (added 2026-05-03)
├── .planning/
│   └── .continue-here.md       ← session-handoff doc
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── email.py                ← NEW 2026-05-03 — SendGrid wrapper for ops alerts
│   ├── main.py
│   ├── schemas.py
│   ├── util/
│   │   ├── courses.py          ← canonical course key → display name mapping; used by /admin/course-demand
│   │   ├── dates.py            ← _parse_iso() — Python 3.9 fromisoformat compat
│   │   └── phone.py            ← SHA-256 phone hashing, E.164 validation
│   └── routers/
│       ├── admin.py            ← /admin/dashboard + 5 new data endpoints (users, alerts, recent-fires, course-demand, course-requests)
│       ├── alerts.py           ← /alerts CRUD, /alerts/history, /alerts/{id}/retry, /activity
│       ├── auth.py             ← /auth/signup, /auth/login, /auth/me
│       ├── billing.py          ← /create-checkout-session, /webhooks/stripe
│       ├── course_requests.py
│       ├── invites.py
│       └── scraper.py          ← /scraper/expire-alerts, /scraper/fire-alert
├── scripts/
│   └── backup/                 ← NEW 2026-05-03
│       ├── backup.sh           ← weekly pg_dump driver (called by launchd)
│       └── RESTORE.md          ← restoration runbook
├── supabase/
│   └── migrations/             ← active 2026-05-03; 2 files committed
├── Procfile
├── README.md
├── railway.json
├── requirements.txt
└── runtime.txt
```

### `foreward-scraper` (Python worker)

```
foreward-scraper/
├── .github/
│   └── workflows/
│       └── ci.yml              ← parse-check on push to main (added 2026-05-03)
├── alerts.json                 ← config/test fixture
├── chronogolf_scraper.py       ← in ALERTING_PLATFORMS; short-circuits when no user alerts target Chronogolf courses
├── ~~ezlinks_scraper.py~~      ← deleted 2026-05-08 (commit 1bad5cf foreward-scraper)
├── golfnow_scraper.py          ← active
├── tee_sniper.py               ← main module; one-shot firing, mark_taken, expire
├── Dockerfile
├── nixpacks.toml
├── Procfile
├── railway.json
├── requirements.txt
└── .gitignore
```

**Polling cadence:** 60 seconds (`POLL_INTERVAL_SECONDS` env).
**Worker writes to:** `sent_slots` (with full denorm cols), `scraper_health` (heartbeat), and `alert_profiles.status` indirectly via API endpoints.
**Worker calls Twilio + SendGrid directly.** SMS sender for user-facing alerts is the worker, not the API.

### Booking platforms

| Platform | Status | Captcha | Auth | Module |
|---|---|---|---|---|
| **GolfNow** | active | no | none | `golfnow_scraper.py` |
| **Golf The 6ix (GTG)** | active | yes (Cloudflare Turnstile via 2Captcha) | account login (`GTG_EMAIL`/`GTG_PASSWORD`); singular `GTG_ACCOUNT` on worker, plural `GTG_ACCOUNTS` on api — migration in progress | inline in `tee_sniper.py` |
| **EZLinks** | retired 2026-04-27 | — | — | `ezlinks_scraper.py` deleted 2026-05-08 (commit `1bad5cf`) |
| **Chronogolf** | active (in ALERTING_PLATFORMS) | — | — | `chronogolf_scraper.py` |

Course inventory and counts: see [STATE.md](./STATE.md) (autogenerated). This section describes platform behavior, not coverage.

**Note (2026-05-03 PM):** Earlier versions of this doc listed Lakeview Golf Course as a separate platform with an inline scraper in `tee_sniper.py` and a Cloudflare 403 known issue. **That was wrong.** Worker logs confirm only three platform tags fire at runtime: `[gtg]`, `[golfnow]`, `[chronogolf]`. Lakeview is a *course* on the GolfNow platform (course key `lakeview`, GolfNow ID 8409). All Lakeview alert emails are sent via the GolfNow scraper. Whether vestigial Lakeview-direct scraping code still exists in `tee_sniper.py` is unverified — needs a `grep -ri lakeview` next session. If found, decide: delete (consolidate on GolfNow) or wire up + add to heartbeat.

### `foreward` (Lovable frontend)

```
foreward/
├── docs/
├── public/
├── src/
├── components.json   ← shadcn/ui config
├── package.json      ← Bun lockfiles + npm lockfile both present
├── index.html
└── tsconfig.json
```

Lovable owns this repo end-to-end. It exposes one edge function: `course-request`. The dashboard, alerts list, alerts history, signup, billing checkout redirect — all consume `foreward-api` over HTTPS.


---

## How it works

### Request lifecycle: signup through first SMS

```
1. User visits goodlie.golf
   → Lovable serves the React/TS app (foreward repo)

2. User submits signup form
   → POST /auth/signup → foreward-api → Supabase auth.users insert
   → on_auth_user_created trigger fires
   → handle_new_user() inserts (id, email) into user_profiles
   → user_profiles.trial_end set to now() + 7 days

3. User confirms email → logs in
   → POST /auth/login → JWT issued

4. User submits alert criteria via dashboard
   → POST /alerts → foreward-api → INSERT alert_profiles (status='active')

5. Background loop: worker polls every 60s
   → Calls POST /scraper/expire-alerts (sweep date_to < today → status='expired')
   → Loads active alerts via /export-alerts (status='active' filter)
   → Scrapes each enabled platform
   → For each alert: collect ALL matching new slots
   → If matches: send ONE SMS summarizing them, insert sent_slots rows,
     POST /scraper/fire-alert {alert_id} → status='fired', cache invalidated
   → Per-platform mark_taken sweep (only if platform was productive this poll)
   → Heartbeat with per-platform stats; API checks for alarm-threshold transitions
     and emails hello@goodlie.golf on silent-failure detection

6. User receives SMS within ~60-90s of slot becoming available

7. User books on the course's own booking platform
   (We don't book — that's the explicit product line.)

8. User wants to be notified again? → "Try again" button on /alerts/history
   → POST /alerts/{id}/retry → status='active' again
```

### Silent-failure alerts (NEW 2026-05-03)

The `/scraper-heartbeat` handler now compares previous and current `consecutive_zero_polls` per platform:

```
On each heartbeat:
  prev_streaks = SELECT consecutive_zero_polls FROM scraper_health WHERE id=1
  new_streaks = payload.consecutive_zero_polls

  for platform, new_streak in new_streaks.items():
    prev_streak = prev_streaks.get(platform, 0)
    if prev_streak < ALARM_THRESHOLD AND new_streak >= ALARM_THRESHOLD:
      send_alarm_email(platform, new_streak)
    elif prev_streak >= ALARM_THRESHOLD AND new_streak == 0:
      send_recovery_email(platform)

  upsert scraper_health (existing logic)
```

- **Threshold:** 10 consecutive zero polls (= ~10 min). Configurable via `ALARM_THRESHOLD_POLLS` env var.
- **Recipient:** `hello@goodlie.golf` (override via `ALARM_EMAIL_TO`).
- **Sender:** SendGrid via `app/email.py`. Failures swallowed and logged — never break the heartbeat.
- **Idempotency:** fires only on transitions, not every poll. No alarm storms.
- **Note (2026-05-19):** Chronogolf is in ALERTING_PLATFORMS. Health alarms fire for it like any other platform. The alert-driven short-circuit means it only runs Playwright polling when a user has an active alert targeting a Chronogolf course; none are configured to date, so it short-circuits in practice.

### Frontend page map (Lovable / `foreward` repo)

| Route | Purpose |
|---|---|
| `/` | Landing — pitch, pricing, "Never miss a tee time" tagline. Activity ticker. Region-group pill listing GTA courses |
| `/auth?mode=signup` | Free-tier signup flow (phone verification → account creation). Rebuilt 2026-05-08, replaces the previous paid Stripe-redirect flow at this same URL. |
| `/auth?mode=signin` | Sign-in flow. Untouched as of 2026-05-08. |
| `/signup` | Orphaned route from a 2026-05-08 Lovable iteration. Currently redirecting / no-op. Cleanup deferred — does not block launch. |
| `/dashboard` | Fetches `status=active,fired,expired` (Block 8 fix-up — active-only fetch left free-tier state CTAs dead). Renders three states for non-paid users: fresh (no `free_tier_used_at`), post-fire subscribe CTA → `/subscribe?from=fired`, expired-without-firing grace-retry CTA → `/alerts/new`. |
| `/alerts/new`, `/alerts/{id}/edit` | Alert criteria CRUD |
| `/alerts/history` | `status='fired'` and `status='expired'` alerts; status badges; "Try again" / "Edit dates" buttons for paid users. Free-tier users on fired alerts see subscribe CTA → `/subscribe?from=fired` instead of "Try again" (Block 8). |
| `/billing` | Stripe Checkout redirect |
| `/admin` | Internal dashboard — needs `noindex` meta tag (queued, ClickUp `86ah69ypk`) |
| `/courses/request` | Submit a missing-course request |

### Data flow diagram

```
                  ┌────────────────┐
        user  ───→│  goodlie.golf  │  (Lovable / foreward repo, React/TS)
                  └────────┬───────┘
                           │  HTTPS
                           ↓
            ┌──────────────────────────────────────────┐
            │  foreward-api  (FastAPI / "web" service) │
            │    /auth/*  /alerts/*  /billing/*        │
            │    /admin/*  /scraper-heartbeat (alarm)  │
            │    /activity (public)                    │
            │    /scraper/expire-alerts                │
            │    /scraper/fire-alert                   │
            └────┬──────────────────┬──────────────────┘
                 │                  │
   service-role  │                  │  JWT (target auth model)
                 ↓                  ↓
            ┌──────────────────────────────────────────┐
            │  Supabase  (offtdltmvjfizkoeywei)        │
            │   user_profiles    alert_profiles+status │
            │   sent_slots+ext   scraper_health        │
            │   invite_codes     course_requests       │
            └────────────┬─────────────────────────────┘
                         ↑
                         │  writes sent_slots, scraper_health
                         │  reads alert_profiles via API
                         │  writes status via API endpoints
            ┌────────────┴────────────┐
            │  foreward-scraper        │
            │  ("worker" service, EU)  │
            └─┬───────┬──────┬───────┘
              │       │      │
              ↓       ↓      ↓
           Twilio  SendGrid  external platforms
           (SMS)   (email)

       (separate, async)
            ┌─────────────────────┐
            │  Local Mac (launchd)│  weekly Sunday 10 AM
            │  pg_dump → gzip     │
            │  → Google Drive     │
            └─────────────────────┘
```

### Deployment flow

| Repo | Trigger | Target | CI gate | Staging |
|---|---|---|---|---|
| `foreward` | Lovable AI bot commits → push to `main` | Lovable hosting → `goodlie.golf` | none | none |
| `foreward-api` | manual `git push` to `main` | Railway `spirited-youthfulness / web` | GitHub Actions parse-check (advisory unless "Wait for CI" toggle is enabled on Railway) | none |
| `foreward-scraper` | manual `git push` to `main` | Railway `resourceful-delight / worker` | GitHub Actions parse-check (advisory unless "Wait for CI" toggle is enabled on Railway) | none |
| Supabase schema | numbered SQL via Supabase SQL Editor → commit file to `foreward-api/supabase/migrations/` | live DB directly | none | none |
| CI workflow files | GitHub web UI (local PAT lacks `workflow` scope) | — | — | — |

**Wait for CI Railway toggle:** off as of 2026-05-03. Workflows run on every push and are passing reliably; toggle is safe to enable at any time. Both repos.

No staging environment. Auto-deploy on push (modulo "Wait for CI" if enabled). Rollback is `git revert HEAD && git push`.

### Observability

| Signal | Where | Refresh |
|---|---|---|
| Scraper heartbeat | `scraper_health` row id=1; `/admin/scraper-health` | every 60s |
| Worker liveness | `GET /healthz` on foreward-scraper (port `$PORT`, default 8080). 200 = healthy (poll completed within 180s). 503 = stale or starting-grace-exceeded. Railway probes this path. | every ~30s (Railway) |
| Per-platform slot counts | `scraper_health.slots_last_poll` (jsonb) | every 60s |
| Per-platform alarm streak | `scraper_health.consecutive_zero_polls` (jsonb) | every 60s |
| Silent-failure alerts | Email to `hello@goodlie.golf` on threshold cross or recovery | per-event |
| Alert volume | `sent_slots`; aggregate via `/admin/dashboard` | real-time |
| Recent activity feed | `GET /activity` (public, 30s cache) | real-time |
| Stripe events | webhook → `/webhooks/stripe`; logs in Railway | per-event |
| Supabase health | Advisor at `dashboard/project/offtdltmvjfizkoeywei/advisors/security` | manual check |
| Railway logs | Railway dashboard → service → Deployments → Logs | live |
| CI status | GitHub Actions tab on each repo | per-push |
| Backup status | `cat ~/.goodlie-backup-status` on local Mac | weekly |

**No automated paging beyond email.** Email-on-silent-failure is the only auto-alert. Worker `/healthz` healthcheck endpoint shipped 2026-05-08 (closes ClickUp `86ah8bq8w`).

### Failure modes (umbrella view)

| Failure | What happens | How it's detected | How it recovers |
|---|---|---|---|
| GolfNow Cloudflare/proxy block | GolfNow API returns errors or empty results for ALL courses (not short-circuit) | `consecutive_zero_polls.golfnow` increments on actual failure → **email at 10 polls**. (Distinct from intentional short-circuit where no alerts target GolfNow courses — that resets to 0 per `bc527e3`.) | Webshare proxy rotation / wait it out / contact GolfNow if persistent |
| 2Captcha balance exhausted | GTG captcha solves fail; GTG returns 0 slots | Direct balance polling every 15 min via `/scraper-heartbeat`. Alarm at <$5 USD. Email via existing alarm infra. Closes ClickUp `86ah8bq89`. Zero-slot streak still fires independently. | Top up at https://2captcha.com/pay |
| GTG account banned/throttled | GTG scrape fails or returns empty | Same signature as captcha failure | Rotate to backup account |
| Worker crashes | Polling stops entirely | Heartbeat goes stale (no auto-detect; planned: `86ah8bq8w`) | Railway auto-restart per `railway.json` |
| Worker stuck-but-running | Process alive, polls don't complete | `/healthz` endpoint on worker returns 503 if last poll completed >180s ago. Railway healthcheck triggers restart on failure. Shipped 2026-05-08. | Railway auto-restart via healthcheck |
| API service down | Frontend errors AND scraper status writes fail | User-visible 5xx; scraper logs API errors | Railway auto-restart |
| API down during a fire | Alert fires SMS, but `/scraper/fire-alert` fails → status stays 'active' → re-fire next poll on dedupe miss | Look for repeated SMS to same user | Manual SQL UPDATE if it happens |
| Stripe webhook drops | Subscription state in `user_profiles` drifts from Stripe | Manual reconciliation only | Stripe auto-retries for ~3 days |
| Supabase outage | Everything stops | All endpoints fail | Wait it out (no replica, no failover) |
| Supabase data loss | Total wipe | n/a | **Restore from local Mac → Google Drive backup** (RESTORE.md). Worst-case data loss = up to 7 days. |
| Bad commit on `main` | Live break (CI advisory only unless "Wait for CI" enabled) | User reports / Dustin checking | `git revert` + push |
| `sent_slots` insert race | Unique constraint violation | Logged; slot treated as already-sent (correct behavior) | Self-healing — the dedupe contract IS the unique index |
| `mark_taken` false-flag | Slots wrongly marked taken on a non-productive platform | UI shows TAKEN incorrectly on ticker | Mitigated by `slots_per_platform[platform] > 0` guard |

The system is **intentionally simple** — no queues, no replicas, no failovers, limited automated paging. Most non-platform failures degrade silently; platform failures now generate email alerts. Acceptable trade at current scale; flag for revisit when paying customers cross ~50 or alert volume crosses ~500/day.

### SMS lifecycle (umbrella)

```
Trigger:    one-shot per alert per poll. First match-set fires; alert moves to status='fired'.
            User clicks "Try again" → status='active' → eligible to fire on NEW slots only.

Body:       Multi-slot:
              "3 openings at Lakeview Sat May 10:
               7:30am, 8:00am, 8:30am (4 players)
               Available as of 9:14am. Book: <link>"
            Single-slot:
              "Lakeview Sat May 10 at 7:30am (4 players)
               Available as of 9:14am. Book: <link>"

Sender:     TWILIO_FROM phone number (worker)
Recipient:  alert_profiles.notify_phone (override) OR user_profiles.notify_phone (default)
Dedupe:     unique (alert_id, slot_key) on sent_slots — race-safe via index
            PLUS: alert.status='fired' after fire — scraper skips fired alerts entirely
Retry:      Twilio handles delivery retries; user-initiated re-fire via "Try again"
Logging:    Twilio's send log; sent_slots ledger with full denorm fields
```

### Auth lifecycle

```
Signup:     POST /auth/signup → Supabase auth → email confirmation
Login:      POST /auth/login → JWT (1h access + refresh) issued by Supabase
API auth:   Bearer JWT in Authorization header → validated in FastAPI dependency
Worker auth: SUPABASE_SERVICE_KEY (bypasses RLS — privileged, no user context)
            PLUS ALERTS_API_KEY for /export-alerts, /scraper/expire-alerts, /scraper/fire-alert
Admin:      /admin/* gated by service role check
Migration:  service-role-with-app-filter → anon-with-JWT-and-RLS (in progress;
            ClickUp 86ah69y22 covers /alerts/history; sent_slots already deny-all-anon)
```

### Stripe lifecycle

```
Trial:      RETIRED 2026-05-18. No upfront trial. Free tier (1 alert) replaces trial as the value-before-payment moment.
Checkout:   POST /create-checkout-session → returns Stripe Checkout URL → user redirected
Success:    Stripe → SUCCESS_URL → user lands back on goodlie.golf
Cancel:     CANCEL_URL same pattern
Webhook:    Stripe → POST /webhooks/stripe → signature verified
Events handled:
  customer.subscription.created → set user_profiles.stripe_subscription_id, is_active=true
  customer.subscription.updated → recompute is_active from status
  customer.subscription.deleted → is_active=false (subscription_id retained)
  invoice.payment_failed       → likely just logged
Pricing:    Single STRIPE_PRICE_ID at $9.99 CAD/month, recurring
Abandoned-checkout:  Stripe Customer object created on checkout-start but no subscription if user
                     bails out. ClickUp 86ah8ag8y covers enabling Stripe's recovery emails.
```

---

## Backup & restore (NEW 2026-05-03)

### Setup
- **Driver:** `~/foreward-api/scripts/backup/backup.sh` (committed)
- **Schedule:** macOS launchd (`~/Library/LaunchAgents/com.goodlie.backup.plist`) — every Sunday 10 AM. Catches up on Mac wake if asleep.
- **Output:** `~/Library/CloudStorage/GoogleDrive-hello@goodlie.golf/My Drive/Good Lie Backups/goodlie_YYYYMMDD_HHMMSS.sql.gz`
- **Schemas dumped:** `public` + `auth`
- **Retention:** 28 days local + Google Drive cloud sync
- **Status check:** `cat ~/.goodlie-backup-status`
- **Logs:** `~/Library/Logs/goodlie-backup.log`

### Config
- `~/.goodlie-backup-env` (chmod 600, NOT in repo) holds `SUPABASE_DB_URL` and `BACKUP_DIR`. Password stored in ClickUp `86ah8bnp3` (Credentials & secrets).

### Restore
- Full procedure: `~/foreward-api/scripts/backup/RESTORE.md` (committed)
- **Quarterly test required:** ClickUp `86ah8bnjk` (recurring task, first due 2026-08-03). Untested backups aren't backups.

### Risk profile
- **Worst-case data loss:** up to 7 days (between weekly runs)
- **Single point of failure:** the Mac. If it dies, last sync survives in Google Drive.
- **Not yet tested end-to-end** (planned for 2026-08-03 first quarterly test)

---

## Live state (Supabase, captured 2026-05-03 afternoon)

> **Stale as of 2026-05-09.** The 2026-05-09 Block 9 session ran a full free-tier walkthrough — test user `dustinkeating87+test2@gmail.com` was created and cleaned up post-walkthrough. Row counts below are the 2026-05-03 baseline; query Supabase directly for current figures before relying on this table. The alert and sent_slots counts have grown as the system has been firing production alerts since 2026-05-03.

| Metric | Value | Notes |
|---|---|---|
| Auth users | 21 | 2026-05-03 baseline — stale |
| `user_profiles` rows | 21 | 2026-05-03 baseline — stale |
| `alert_profiles` total | 16 | 2026-05-03 baseline — stale |
| `alert_profiles` `status='active'` | 2 | stale |
| `alert_profiles` `status='fired'` | **7** | stale — count has grown since 2026-05-03 |
| `alert_profiles` `status='expired'` | 7 | stale |
| `alert_profiles` `status='paused'` | 0 | stale |
| `sent_slots` total | 122 | stale — count has grown since 2026-05-03 |
| `sent_slots` with `user_id` | 61 | stale |
| `sent_slots` orphan (`user_id IS NULL`) | 61 | Pre-launch test alerts; harmless. Optional cleanup deferred. |
| Stripe-subscribed users | 2 | stale |
| Stripe-customer-only (abandoned) | 2 | stale |
| `invite_codes` total | 60 | stale |
| 2Captcha balance | $18.72 | 2026-05-03 baseline — stale; check 2captcha.com for current balance |

---

## API surface (foreward-api endpoints)

```
Auth
  POST   /auth/signup
  POST   /auth/signup-free-tier         ← FREE_TIER_ENABLED gate; consumes verification_token, creates auth user with tier=free
  POST   /auth/login
  GET    /auth/me
  POST   /auth/send-verification-code   ← FREE_TIER_ENABLED gate; Twilio Lookup + IP rate limit + per-phone rate limit (3/24h, Block 7) + phone dedupe + SMS send
  POST   /auth/verify-phone             ← FREE_TIER_ENABLED gate; validates OTP, returns verification_token (consumed by /auth/signup-free-tier)
  POST   /auth/resend-verification-code ← FREE_TIER_ENABLED gate; 60s cooldown, max 3 resends per code

Alerts (user-facing)
  POST   /alerts                     ← non-paid users: one free alert + one grace retry on non-firing expiry (Block 6 simplified flow); 402 otherwise
  GET    /alerts                     ← accepts ?status= (comma-sep); defaults to status=active
  PUT    /alerts/{id}
  DELETE /alerts/{id}
  GET    /alerts/history             ← includes status field per row
  POST   /alerts/{id}/retry          ← sets status='active'; 400 if date_to past, 404 if not owned

Activity (public)
  GET    /activity                   ← 20 most recent ticker rows; 30s cache; no auth

Billing
  POST   /create-checkout-session
  POST   /webhooks/stripe

Export / Scraper internal (ALERTS_API_KEY-gated)
  GET    /export-alerts              ← filters status='active'
  POST   /scraper/expire-alerts      ← bulk-set status='expired' for date_to < today
  POST   /scraper/fire-alert         ← status='fired' for given alert + cache invalidate

Admin
  POST   /scraper-heartbeat          ← worker → API health ping; ALSO checks alarm thresholds and emails on transitions
  GET    /admin/scraper-health
  GET    /admin/dashboard
  GET    /admin/users                ← paginated users; status badges computed server-side; alert counts + SMS totals pre-aggregated; ?limit=&offset=&status=&search=
  GET    /admin/alerts               ← paginated alerts with user_email joined; ?limit=&offset=&status=&tier=free|paid&course=&user_id=&search=
  GET    /admin/recent-fires         ← recent sent_slots rows with user_email; ?limit= (max 200) &since=ISO datetime; default last 7 days
  GET    /admin/course-demand        ← active alerts aggregated by course key; includes fired_alerts_30d and unique_users per course
  GET    /admin/course-requests      ← course_requests aggregated by course name (case-insensitive); includes request_count, requester_emails (capped 10)

Worker (foreward-scraper)
  GET    /healthz                    ← HTTP healthcheck on aiohttp server; reads in-process timestamp; returns starting/healthy/stale
```

---

## Auth model

**Current:** Service role + app-level filtering. The API uses Supabase service role for most reads, then filters by `user_id` in Python.

**Target:** anon Supabase client + user JWT + RLS policies. The DB becomes the source of truth on access.

**RLS state (2026-05-03):** enabled on every public table; deny-all for anon/authenticated on `sent_slots`; service role bypasses.

---

## Infrastructure config

### Railway: `resourceful-delight` (worker)
- Project ID: `789f3187-ccda-4440-bb0b-36a2758c11ce`
- Service: `worker` (id `42260d63-2677-4d6b-90bd-8ea67fc8dacb`)
- Region: EU West (Amsterdam)
- Builder: Dockerfile
- 15 service env vars: `GTG_ACCOUNTS`, `CAPTCHA_API_KEY`, `ALERTS_API_URL`, `ALERTS_API_KEY`, `POLL_INTERVAL_SECONDS`, `PROXY_URL`, `PROXY_URLS`, `SENDGRID_API_KEY`, `SMTP_*`, `TWILIO_*` (removed `GTG_EMAIL`, `GTG_PASSWORD`, `GTG_ACCOUNT` 2026-05-14; renamed `GTG_ACCOUNT` → `GTG_ACCOUNTS`)

### Railway: `spirited-youthfulness` (web/API)
- Project ID: `7c8fa4ed-d992-4f5d-a78b-907ed5fd4e44`
- Service: `web` (id `0aa1761e-7bd3-4d72-9877-0968a14f5974`)
- Public URL: `https://web-production-b24db.up.railway.app`
- 25 service env vars (added 2026-05-03: `ALARM_THRESHOLD_POLLS=10`, `ALARM_EMAIL_TO=hello@goodlie.golf`, `ALARM_EMAIL_FROM=hello@goodlie.golf`; added 2026-05-07: `SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_1`, `SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_2`, `SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_3`; added 2026-05-08: `CAPTCHA_API_KEY` for 2Captcha balance auto-alert)

### Supabase
- Project ID: `offtdltmvjfizkoeywei`
- Hostname: `offtdltmvjfizkoeywei.supabase.co`
- Org: Kick Rocks Inc
- Region: us-east-2 (Ohio)
- Tier: t4g.nano (free)
- Backups: weekly local pg_dump → Google Drive (NEW 2026-05-03)
- Migration system: in use as of 2026-05-03

### Lovable
- Project ID: `c3bd43d3-7123-4957-8d39-466b1ada76f6`
- Custom domain: `https://goodlie.golf/`
- Edge functions: `course-request` (only one)

### ClickUp
- Workspace: `90131142261`
- Space: "Good Lie Golf" — id `901313780791`

### GitHub
- User: `dustinkeating87`
- Repos: `foreward`, `foreward-api`, `foreward-scraper`
- PAT note: current PAT lacks `workflow` scope — workflow files committed via web UI. Update PAT scope when convenient to enable local pushes of `.github/workflows/*` files.

---

## Locked-in product decisions

| Decision | Date | Rationale |
|---|---|---|
| No auto-booking, ever | 2026-04-30 | Ethical/community stance + credit-card trust risk + bot-protection arms race. Forum-validated on torontogolfnuts.com |
| No priority list (preferred-time ranking) | 2026-04-30 | Doesn't fit the alert model — we alert on a range, not a specific time |
| No per-course release schedule as user-config | 2026-04-30 | App-config, not user-config |
| No multi-channel notifications (push/email) for now | 2026-04-30 | SMS is enough for the MVP |
| No playing partners as first-class objects | 2026-04-30 | Not relevant for an alerts-only tool at this stage |
| "Snipe" is internal-only — never user-facing | 2026-04-30 | Inherited from Tee Sniper; brand pivot away from it |
| EZLinks platform retired | 2026-04-27 | Coverage moved to GolfNow |
| Chronogolf always in ALERTING_PLATFORMS | 2026-05-19 | Doc was wrong — code always included it. All three platforms (gtg, golfnow, chronogolf) are in ALERTING_PLATFORMS and polled every 60s. No user-facing alerts have been configured for Chronogolf courses to date, so the alert-driven filtering short-circuits them in practice. They will fire if a user creates an alert targeting one. |
| One-shot alerts (status='fired' after fire) | 2026-05-03 | Avoid spamming users with repeated SMS for same alert. User-initiated re-fire via "Try again." |
| Multi-match folds to one SMS | 2026-05-03 | If a poll detects multiple matching slots for one alert, all fold into one summary SMS. |
| Auto-expiry per-poll, no cron | 2026-05-03 | Scraper calls `POST /scraper/expire-alerts` at top of each poll. Matches "intentionally simple." |
| "Try again" semantics: re-activate only | 2026-05-03 | Does not clear sent_slots rows. Future *new* matches will fire; previously-sent slots won't re-fire. |
| Scraper writes status via API, not direct DB | 2026-05-03 | Centralizes business logic. Trades one network hop per poll for testability + future audit. |
| **Backup retention 28 days** | **2026-05-03** | **Sufficient given quarterly test cadence; minimizes Drive bloat.** |
| **Silent-failure alerts: API-side, transition-only** | **2026-05-03** | **No state column needed. Implicit comparison of prev/new. Failures swallowed — never break heartbeat.** |
| **DB password is alphanumeric only** | **2026-05-03** | **Avoids URL-encoding issues across shells, scripts, and connection-string parsers.** |
| "By request" picker pattern for non-GTA courses | 2026-05-05 | Founder-curated course additions surface in the alert picker's "By request" section only — not on the homepage. Homepage stays GTA-only. Pattern: founder-curated courses graduate to a proper named region at ~5-8 courses. First applied to Sandridge GC (Vero Beach FL, GolfNow platform) — Dunes facility 5223, Lakes facility 6798. |
| **Pricing pivot: free tier replaces trial** | **2026-05-18** | **One free alert per user/phone, lifetime. Runs until first successful fire OR date_to expiry. Successful fire → hard paywall for alert #2. Date_to expiry without fire → free re-attempt. No 7-day credit-card trial. Block 4 (Stripe coupons + renewal emails) retired.** |

---

## Known issues / things to watch

1. ~~Lakeview Cloudflare 403~~ ✗ **withdrawn 2026-05-03 PM.** Earlier doc claimed Lakeview had its own scraper with a Cloudflare 403 issue. Runtime evidence (worker logs, scraper_health jsonb) shows no `[lakeview]` platform tag and no separate Lakeview scraper running. Lakeview is a *course* on the GolfNow platform. Possibly vestigial code in `tee_sniper.py` from an earlier architecture; needs verification (see #18 below).
2. ~~`sent_slots` missing `user_id`~~ ✓ closed 2026-05-03 (column added).
3. ~~`auth.users` ↔ `user_profiles` gap~~ ✓ closed 2026-05-03 afternoon (14 orphans deleted).
4. ~~Migration system not in use~~ ✓ closed 2026-05-03 (in use, 2 files committed).
5. ~~No Supabase backups configured~~ ✓ closed 2026-05-03 afternoon (weekly local pg_dump → Google Drive).
6. ~~No worker healthcheck endpoint — Railway can't auto-detect stuck-but-running worker~~ ✓ closed 2026-05-08 — `/healthz` endpoint shipped on foreward-scraper (commit `b2ea3ad`). aiohttp web server runs as background asyncio task; `mark_poll_completed()` updates in-process timestamp; handler reads timestamp without hitting the DB. Three states: starting (90s grace) / healthy (<180s since last poll) / stale (≥180s, returns 503). Railway healthcheck wired via `railway.json` `deploy.healthcheckPath`. Local testing passed all three states.
7. ~~**`GTG_ACCOUNT` (singular) on worker vs `GTG_ACCOUNTS` (plural) on API** — multi-account migration half-done.~~ ✓ closed 2026-05-14. See decision log.
8. ~~README in `foreward-api` still says "Tee Sniper API"~~ ✓ closed 2026-05-08 — verified rebranded in commit `a6a9730`
9. ~~2Captcha balance has no auto-monitoring — silent failure mode if balance hits zero~~ ✓ closed 2026-05-08 — balance auto-alert shipped on foreward-api (commit `29f0e3a`). Migration `20260508_add_captcha_balance_alarm_state.sql` applied to prod (3 new columns on `scraper_health`). Check fires every 15 min via `/scraper-heartbeat`. Alarm threshold $5 USD (configurable via `CAPTCHA_BALANCE_ALARM_THRESHOLD_USD`). Email alarm + recovery via existing `send_alarm_email` infra. `CAPTCHA_API_KEY` env var added to Railway `web` service. Verified live in prod 2026-05-08 — first check succeeded (balance $16.53, ~26 days runway at current ~$0.43/day burn rate).
10. **Meta ad account trust issues** affecting parent operator's brands.
11. **Scraper writes status via API endpoints, not direct Supabase.** If alerts get stuck in `active` despite firing, check API logs first.
12. **61 orphan rows in `sent_slots`** (`user_id IS NULL`) from pre-launch test alerts. Harmless. Optional cleanup deferred.
13. ~~**Silent-failure alerts fire for chronogolf** even though it's excluded from ALERTING_PLATFORMS.~~ **Resolved 2026-05-19:** Chronogolf was never excluded — the architecture doc was wrong. All three platforms are in ALERTING_PLATFORMS. Silent-failure alarms for Chronogolf are correct and expected behavior.
14. **Backups not yet end-to-end tested.** First quarterly restore test due 2026-08-03 (ClickUp `86ah8bnjk`). Until then, treat backups as unverified.
15. ~~**GitHub PAT lacks `workflow` scope**~~ ✓ **resolved 2026-05-19** — new PAT with `repo` + `workflow` scope in all three local remotes.
16. **Railway "Wait for CI" toggle off** on both services. CI is advisory until enabled. Both workflows passing reliably as of 2026-05-03.
17. ~~GolfNow returning 0 slots persistently~~ ✓ **resolved 2026-05-03 PM (first variant) and 2026-05-12 (second variant), both verified in production.**

   **First variant (2026-05-03):** False alarm. Root cause: alert-driven filtering short-circuit — platforms returned 0 slots when no active alerts targeted their courses. The `consecutive_zero_polls` counter didn't distinguish "scraped → got 0" from "didn't scrape". Fix (`bc527e3`): `poll_golfnow_tee_times` and `poll_chronogolf_tee_times` return `None` when short-circuiting; call sites detect `None` and reset the counter instead of incrementing. Verified post-deploy: GolfNow 0/0, Chronogolf 0/0, dashboard Healthy.

   **Second variant (2026-05-12):** Even after `bc527e3`, HTTP 200 with legitimately empty inventory (no tee times for the searched date/player combination) still returned `[]` from `fetch_one`, indistinguishable from HTTP 403/timeout/exception failures. Worker logs confirmed GolfNow returning HTTP 200 every poll but `consecutive_zero_polls.golfnow` climbing to 95+. Fix (2026-05-12): three-state return contract — `None` (no alert work), `(True, slots)` (request reached the platform — even if empty), `(False, slots)` (request failed). Counter resets on `True`, increments only on `False`. `fetch_one` on GolfNow/Chronogolf returns `(True, [])` on HTTP 200 + empty result, `(False, [])` on non-200/timeout/exception. `poll_tee_times` (GTG) tracks `got_gateway_response` flag — set `True` when the GTG gateway API returns a 200 matching response. Navigation failures (`page.goto` timeout/crash) now caught inside `poll_tee_times` and returned as `(False, [])`, bringing them into the alarm system. All GTG Playwright/Turnstile/search/gateway-timeout failures already returned `[]` and were already incrementing the counter; now correctly typed as `(False, [])`. Extends the silent-failure monitoring established to close known issue #9.

18. ~~Admin dashboard hardcodes platform cards~~ ✓ closed 2026-05-08 — admin platform cards now data-driven from `scraper_health.slots_last_poll` jsonb keys. Currently renders 3 cards (gtg, golfnow, chronogolf). EZLinks no longer surfaces. Verified live on goodlie.golf/admin.

20. **ARCHITECTURE.md was lost from local filesystem on 2026-05-06 and recovered from Cowork project knowledge (2026-05-03 baseline). Recent updates between 2026-05-03 and 2026-05-06 (2Captcha balance auto-alert, ClickUp/doc reconciliation, By-request picker confirmation, alert form defaults patches) need to be re-derived from closed ClickUp tickets — tracked in ticket 86ahb0m91.**

19. ~~Possible vestigial Lakeview code in `tee_sniper.py`~~ ✓ closed 2026-05-08 — audit confirmed the "vestigial Lakeview code" was actually the retired EZLinks platform scraper (`ezlinks_scraper.py`); deleted in commit `1bad5cf` (foreward-scraper). It was never a Lakeview-specific scraper — it was the whole EZLinks platform module which happened to configure Lakeview as one of its courses. The original "inline Lakeview scraper" framing in the doc was misleading. Lakeview is actively and correctly served by `golfnow_scraper.py`.

21. ~~Local Python 3.9.6 vs Railway Python 3.11 — `fromisoformat` drift~~ ✓ closed 2026-05-08 — extracted to `app/util/dates.py` (NOT `datetime_compat.py` as originally proposed); all four call sites now import `_parse_iso`. Commit `582743b`.

22. **Supabase SQL editor shows "0 rows" for UPDATE without RETURNING.** The editor reports "0 rows" for any DML statement that doesn't include a `RETURNING` clause, regardless of how many rows were actually affected. Always append `RETURNING id` (or similar) when row count matters during a test or migration verify.

23. **Free-tier first_name fallback is hardcoded to "there"** in expiry email templates. `user_profiles` has no first_name column. Acceptable for launch since most users won't notice "Hey there," in a transactional email. Worth fixing once free-tier flows have real user data.

24. **`app/util/courses.py` mapping lives in TWO places — scraper and API.** The COURSES dict in `app/util/courses.py` duplicates the `display_name` fields in `GOLFNOW_COURSES` (golfnow_scraper.py) and `CHRONOGOLF_COURSES` (chronogolf_scraper.py). Keeping them in sync is manual discipline. If a scraper display name drifts, `fired_alerts_30d` in `/admin/course-demand` will silently return 0 for that course. Reconcile ~quarterly or whenever a course is added/renamed. Long-term fix: move to a shared Supabase `courses` table. GTG courses are NOT in the dict — their names come from the GTG gateway API at runtime and fall through to the raw key.

26. **Lovable summaries unreliable for verification.** Lovable's response summaries can claim work shipped when it didn't (e.g., 2026-05-08 noindex on `/admin` claimed 'already there, kept' — was actually missing from rendered DOM, required follow-up prompt). Always verify Lovable changes via Inspect → Elements → Cmd+F search in rendered DOM, OR by view-source on rendered page after publish + hard-refresh. Never trust the summary message alone. Lovable's optimism on completion ≠ actual deployment state.

25. ~~Block 5b prod-side AC verification deferred.~~ ✓ closed 2026-05-09 (Block 9 walkthrough) — full end-to-end verified on test account `dustinkeating87+test2@gmail.com`: signup → phone verify → `POST /alerts` 201 → scraper fired SMS + email → second alert correctly 402'd. Three blockers found and fixed during walkthrough; see Block 9 decision log entry. `FREE_TIER_ENABLED=true` on Railway after walkthrough confirmed clean.

27. ~~Free-tier API is aligned with PRODUCT_FREE_TIER.md as of 2026-05-09; Lovable frontend (course picker, dashboard CTA, grace-retry UX) is not yet aligned.~~ ✓ closed 2026-05-09 (Block 8 — frontend aligned with PRODUCT_FREE_TIER.md via five Lovable prompts; see decision log).

28. **Lovable's "Done" status is unreliable — logic can ship dead while Lovable claims the prompt is complete.** Caught in Block 8: Prompt #1 shipped Dashboard CTAs that were unreachable because `getAlerts()` was called without a status filter, returning only active alerts. Lovable's completion claim was accurate at the level of "code was written" but not at the level of "the feature works." Every Lovable prompt requires two independent checks before being marked done: (1) Chrome-connector live render check, and (2) repo-level grep of the post-publish `foreward` source. Neither alone is sufficient.

29. **Regression watch — Lovable may regenerate `App.tsx` route definitions and re-introduce `requireSubscription` on `/dashboard`, `/alerts/new`, `/alerts/history`.** Caught and fixed in Block 9 (commit `2c74354`). If it recurs, free-tier users silently lose access to those three routes (bounced to `/account`). When invoking Lovable on the `foreward` repo for any page work, explicitly instruct it not to modify route definitions in `App.tsx`. After any Lovable session touching `App.tsx`, grep for `requireSubscription` on those three routes before marking done.

30. **`sent_slots.tee_time` was null on the 2026-05-09 free-tier alert fire** (sent_slot id 855, course Dentonia Park). Per schema, this column should be populated by the scraper at insert time — it is used to render "Available as of HH:MM" in the SMS body. Either the scraper isn't writing it for this platform/course, or it's written then nulled. Investigate before launch since a null `tee_time` causes silent SMS body degradation (time context missing from the alert). Check `tee_sniper.py` scanned_at / tee_time write paths.

31. **Orphan SendGrid templates + Railway env vars.** Three SendGrid Dynamic
Templates (`d-f53c968e8bb645a0ba98844549b2d2f1`, `d-bfbc0e264a2e4092ab236e6c594f7611`,
`d-af240773d6ec40899f6c20ae9c685dcf`) and three corresponding Railway env
vars (`SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_1/2/3` on spirited-youthfulness web
service) are dead code paths. No current code reads them; Block 6 deprecated
the renewals mechanic they were meant to drive. Safe to delete post-launch.
Low priority hygiene.

32. **`app/free_tier_expiry_loop.py` was never built.** Block 3 decision log
entry (2026-05-07) and working-rules session header reference this file as
if it exists and runs in production. It has never been in git. Block 6
deprecated the mechanic. Any future session reading the Block 3 entry should
treat the loop as a never-shipped plan. See 2026-05-11 decision log entry
for full explanation.

33. **Design brief drift on typography and wordmark.** good-lie-design-brief.md
§5 mandates New York display serif for hero headline and wordmark; §14.3
leaves wordmark treatment open. Current Lovable implementation uses sans for
both, confirmed acceptable by Dustin 2026-05-11. Brief should be amended
before next design pass to prevent re-litigating.

34. **Transient `ConnectionTerminated` (HTTP/2) on `GET /admin/alerts` at 2026-05-12T20:07:15Z.** Single occurrence, self-recovered, no user impact. Flag if recurrent — may indicate Railway proxy or upstream httpx HTTP/2 framing issue under load.

35. **Block 1–3 schema columns may be partially vestigial after 2026-05-18 pricing pivot.** `polling_expires_at`, `renewals_used`, `expiry_state`, `final_expired_at`, `final_expired_at` on user_profiles — verify which are still meaningful under the new one-alert free-tier model. Touch code paths in `free_tier_expiry_loop.py` carefully. Audit needed before next free-tier code change.

---

## Outstanding ClickUp tasks (snapshot 2026-05-03 afternoon)

ClickUp is the live source of truth — this list is point-in-time.

### Closed today (2026-05-03)
- ✅ `86ah69x38` — Verify RLS migration on `sent_slots`
- ✅ `86ah69xzk` — Commit + push RLS migration file
- ✅ `86ah69xbh` — Audit `user_id` populated on `sent_slots`
- ✅ `86ah7at4x` — Add `scanned_at` to `sent_slots` + SMS body
- ✅ `86ah69y40` — Establish migrations discipline
- ✅ `86ah8bnxv` — Silent-failure email alerts (built, deployed, tested end-to-end)
- ✅ `86ah8btux` — Filter silent-failure alarms by ALERTING_PLATFORMS + runtime short-circuit (commit `bc527e3`, verified in production)

### Open

**Backend & Infra**
- 🟠 `86ah8bq8w` — Worker healthcheck endpoint (`/healthz` on foreward-scraper) — spec ready
- 🔵 `86ah69y22` — Refactor `/alerts/history` to anon + JWT + RLS pattern
- 🔵 `86ah69y6d` — Verify `PROXY_URLS` env var on `resourceful-delight` (worker still has both legacy + plural)
- 🔵 `86ah8d3mf` — **Verify Lakeview code in `tee_sniper.py`.** `grep -ri lakeview ~/foreward-scraper/`. If dead code, delete. If reachable but unwired, decide: revive as Lakeview-direct platform (richer data than GolfNow proxy, but Cloudflare-fragile) OR consolidate on GolfNow path.
- 🔵 `86ah8d3v1` — **Data-drive admin dashboard platform cards** (Lovable). Currently hardcodes `[GTG, GolfNow, EZLinks, Chronogolf]`. Should iterate over `scraper_health.slots_last_poll` keys. Removes the retired-EZLinks-still-shown bug.
- 🔵 `86ahc0b9e` — Free-tier Block 4b: Stripe coupons + email integration (deferred from Block 4 split, post-launch)
- ⚪ `86ah8bnp3` — Credentials & secrets reference (living doc; update as things change)
- ⚪ `86ah8bnjk` — Quarterly DB backup restore test (first due 2026-08-03)
- (no ID yet) — Complete `GTG_ACCOUNTS` plural migration — worker still reads singular

**Scrapers & Data**
- 🔵 `86ah69yf1` — Create 3 more GTG scraper accounts
- 🔵 `86ah8bq89` — 2Captcha balance auto-alert (depends on `86ah8bnxv` infra — now satisfied)
- ⚪ `86ah69zbp` — Set up 2Captcha balance monitoring (superseded by `86ah8bq89`?)

**Frontend & UX** (Lovable)
- 🟠 `86ah69yn2` — Fired-alert UX redesign — Lovable phase shipped 2026-05-03 morning
- 🔵 `86ah7atdw` — Public activity ticker — backend done; Lovable phase shipped 2026-05-03 morning
- ⚪ `86ah69ypk` — Add `noindex` meta tag on `/admin` route — Lovable prompt queued
- 🟠 `86ahc05ry` — Lovable: build `/subscribe` redirect route for email CTAs (depends on Lovable; CTAs in Block 4a templates point here)
- ✅ `86ahbkwf6` — Lovable signup wall — closed by Block 8 (free-tier signup flow shipped; paid signup wall removed at site entry)
- 🔵 `86ahbkx68` — Pre-launch checklist item: flag flip + real-phone E2E walkthrough — **partially obsolete** after Block 6 dropped courses-coverage gate; review and re-scope before closing
- 🔵 `86ahbkwka` — Pre-launch checklist item — **review for obsolescence** after Block 6; may be partially or fully superseded
- 🔵 `86ahazcce`, `86ahazcww`, `86ahazdv1` — Lovable Block 5/6/7 preview-only tickets — **likely superseded** by Block 8 shipping; review for closure
- 🔴 (no ID yet) — `sent_slots.tee_time` null on 2026-05-09 fire (id 855, Dentonia Park) — investigate before launch (see known issue #30)
- 🔵 (no ID yet) — Lovable copy/UX prompt for free-tier: fix "Payment required" static label on Dashboard, add returning-user CTA when `free_tier_used_at` is set but no active alert — shipped 2026-05-09; verify and close

**Marketing & Launch**
- 🟠 `86ah69yrf` — Instagram content kit for `@playgoodlie`
- 🔵 `86ah69ytx` — OG image upgrade
- ⚪ `86ah69yw6` — Meta reclaim attempt for `@goodliegolf`
- ⚪ `86ah8ag8y` — Enable Stripe abandoned-checkout recovery emails
- ✅ `86ahc027p` — Bug: /auth/signup-free-tier returns identical 401 for three distinct failure modes — closed Block 7 (three distinct error strings shipped, commit `a296efc`)
- ✅ `86ahc02dc` — Bug: /auth/send-verification-code has no phone-ownership check — closed Block 7 (per-phone rate limit shipped, commit `a296efc`)

🔴 urgent · 🟠 high · 🔵 normal · ⚪ low

---

## Decision log

### 2026-05-19 (afternoon — wave 1 frontend + course list cleanup)

**Scraper cleanup shipped.** Removed 16 chronogolf duplicates of golfnow entries (commit 2ed75da), 1 test fixture dunnys-divots from golfnow (commit 12a830e), and 19 private/non-bookable chronogolf entries identified via three-signal classification: hardcoded private filter + sent_slots history + live Chronogolf probe. Chronogolf went from 90 to 55, total scraper courses 151 → 115. STATE.md auto-refreshed end-to-end on every push — first proof the cross-repo dispatch chain works as designed.

**Wave 1 frontend picker shipped via Lovable.** Replaced 39-course region pill on /alerts/new with a search-input-plus-flat-alphabetical multi-select pattern. Scales to 200+ courses without redesign. New courses.ts hardcoded in src/lib/ with ~110 entries.

**Wave 1 has structural problems — pending fix tomorrow.** Lovable built its own course list from public sources rather than using the scraper keys. Result: (a) almost every new course has a key that doesn't match the scraper (alerts created via the new picker likely won't fire), (b) Lovable hallucinated courses that don't exist in scraper code (Cardinal Red Course, Hidden Lake East/West, etc.), (c) Lovable re-introduced ~12 private courses we explicitly deleted today (Magna, Beacon Hall, Bayview, Mississaugua, Islington, Markland Wood, Kleinburg, Knollwood, Richmond Hill private, Sleepy Hollow, Stonehenge, Highland Gate, Castlemore, Glen Eagle). STATE.md gap detection surfaced all of this — system worked correctly. Decision: build proper GET /courses API endpoint instead of patching the hardcoded list, so the fix is permanent.

**STATE.md frontend parser updated** for the new courses.ts shape (commit 3326cf7). Pattern now handles non-exported const + new {key, label, region} entry shape. Active-platform gap dropped from 82 (pre-frontend) to 49 (real name mismatches and Lovable-added non-scraper courses). Sanity print added: "Frontend parsed: N courses".

**Token + permissions fixes shipped:**
- New PAT with workflow scope generated for local pushes; all three local git remotes updated
- STATE_UPDATE_TOKEN secret added to foreward-api (was previously only on foreward-scraper and foreward)
- refresh-state.yml workflow grants contents:write so bot can push STATE.md regen commits back to main
- refresh_state.py reads STATE_UPDATE_TOKEN and injects into clone URLs

**ClickUp tasks created:**
- 86ahk5w6n — Build /courses API endpoint to eliminate frontend courses.ts drift (now elevated to next-session priority, not post-launch)

**PENDING — next session, in this exact order:**
1. refresh_state.py also writes courses.json alongside STATE.md (machine-readable canonical list, regions hardcoded in parser)
2. foreward-api exposes GET /courses reading courses.json
3. Lovable replaces hardcoded src/lib/courses.ts with fetch from /courses endpoint at page load
4. Audit existing alert_profiles in Supabase for course keys not in the new canonical list; flag any broken alerts for review

Until #1-3 ship, goodlie.golf /alerts/new shows a picker with wrong keys, hallucinated courses, and re-introduced private clubs. Pre-launch volume is low so user-facing damage is limited, but new signups in the meantime may create alerts that never fire.

**Structural lesson:** Hardcoded course lists drift. The same problem that motivated STATE.md (drift between scraper code and ARCHITECTURE.md) just happened again when Lovable hardcoded the frontend list. The generated-from-source pattern only works if EVERY consumer reads from the same generated artifact. Pending /courses endpoint extends the pattern to the third consumer (the frontend).

---

### 2026-05-19 (Phase 1 + 1.5 — state automation shipped)

STATE.md autogenerated from scraper + frontend + admin.py constants. Triggered by GH Actions on push to any of the three repos (foreward-api, foreward-scraper, foreward). ARCHITECTURE.md no longer hand-maintains course counts or lists — those live in STATE.md. The doc owns rationale and decisions; STATE.md owns facts.

**Doc corrections shipped:** Five stale Chronogolf claims in ARCHITECTURE.md corrected. All three platforms (gtg, golfnow, chronogolf) are in ALERTING_PLATFORMS per code (admin.py line 20). Chronogolf appears dormant only because no user alerts target its courses, not because it's disabled. The "excluded from ALERTING_PLATFORMS" framing was an interpretation, not a code-grounded fact, and had been carried forward across sessions.

**Phase 1.5 improvements:** Active column now driven by parsed ALERTING_PLATFORMS × course-level flag (not always "yes"). Coverage gaps split into "Active-platform gaps" (real, actionable) vs "Dormant / disabled" (informational). Cross-platform duplicates section added — surfaces courses wired under multiple platforms (Angus Glen, Goreway/Parkshore, Pickering Glen, others). Headline counts at top of STATE.md.

**Commits:**
- `a313474` — Phase 1: refresh_state.py + initial STATE.md + cross-repo workflow infrastructure
- `a597004` — Phase 1.5: honest Active column, split gaps, duplicates, ARCHITECTURE.md Chronogolf corrections

**Key finding:** STATE.md headline counts on first honest run: 151 courses scraped, 150 active-platform, 39 exposed on frontend, **109 active-platform gap** — courses the worker is wired to scrape but goodlie.golf doesn't expose. This is now the canonical answer to "courses we have access to but haven't posted."

**Structural lesson:** Hand-typed mirrors of code state drift, regardless of discipline. The end-of-block update rule fired reliably for foreward-api work but silently didn't apply when changes shipped in foreward-scraper or foreward. Phase 1 replaces that pattern: autogenerated sections fenced with AUTOGEN markers, regenerated by script on every push, can't disagree with the code they're parsing. ARCHITECTURE.md becomes write-once-per-decision (rationale) instead of write-on-every-shipped-change (facts).

**Next phases (deferred):** Phase 2 — endpoint autogen (parse foreward-api/app/routers/ for @router. decorators). Phase 3 — schema autogen (pg_dump --schema-only). Phase 4 — changelog auto-append. Phase 5 — frontend parser refinement. To be done as needed, not upfront.

**Closed known issues:**
- #13 (silent-failure alerts fire for chronogolf) — chronogolf IS in ALERTING_PLATFORMS by design; alerts are correct, not a bug
- #15 (GitHub PAT lacks workflow scope) — resolved during this session, new PAT with repo + workflow scope now in use

### 2026-05-18 (Pricing pivot — free tier replaces 7-day trial)

The 7-day free trial gated by credit card is retired. Replaced with a single-alert free tier:

- One free alert per user / per phone, lifetime
- Phone verification still required (Block 2 endpoints intact)
- Runs until successful fire OR date_to expiry
- Successful fire → hard paywall to create alert #2
- Date_to expiry without fire → free re-attempt allowed (no penalty)
- After paywall → $9.99 CAD/month, no further trial

**Why:** Cold paid traffic was converting at 0.24% landing-page-to-signup with the credit-card-upfront trial. Funnel friction was killing ad spend ROI. Free-tier-with-paywall-after-success inverts the trust ask: value first, payment second.

**Retired:**
- 7-day trial model (`user_profiles.trial_end` is now legacy)
- 14-day polling window for free alerts (`polling_expires_at`)
- 2-renewal model (`renewals_used`, `expiry_state`)
- Stripe coupons for renewals (Block 4 dead)
- Renewal email templates (was Block 4a)

**Verification needed (new ticket):**
- Audit Block 1–3 code for references to retired columns. Tear out or leave inert?
- Confirm `is_free_tier` is still the right tag for the new model
- Verify `phone_hash` uniqueness index still does the right thing (one alert per phone)
- Confirm Lovable signup flow can route to free-alert creation (was ticket 86ahbkwf6 — now urgent and reframed)

**Pre-launch checklist replacement:** Old checklist (ticket 86ahbkx68) was 'verify ≥5 paid alerts before flipping FREE_TIER_ENABLED=true'. New checklist: 'verify free-alert path is reachable from Lovable signup, paywall fires on alert #2 attempt, ad traffic lands on free-alert flow not Stripe checkout.'

**Impact on ad campaign:** Ad spend is paused on the new IG-targeted ad set until the free-tier funnel is reachable from goodlie.golf. Current funnel routes all visitors to Stripe checkout, which is the bug that surfaced via Meta pixel conversion data (1 signup from 422 PageViews over 4 days).

### 2026-05-14 (early — GTG auth outage + close-out)

**Outage:** worker exited cleanly at 00:03:10 UTC on GTG initial login failure. Worker stayed dead ~30 min because Railway's ON_FAILURE policy doesn't restart on exit code 0. Active alert (out-of-window dates) was unaffected by the gap.

**Root cause:** env var naming mismatch. Railway worker had `GTG_ACCOUNT` (singular) containing the burner account JSON, but `load_accounts()` reads `GTG_ACCOUNTS` (plural). Primary auth path returned empty, fell through to `GTG_EMAIL` / `GTG_PASSWORD` fallback — which pointed at `dustinkeating87@gmail.com` (not a registered GTG account). Worker attempted login, GTG rejected with "incorrect password," worker exited.

**Why it was invisible until tonight:** the previous worker container had a valid session cookie from whenever it last cold-started successfully. As long as that session held, no re-authentication was needed. Batch 1 deploy triggered a fresh container which had to authenticate cold and exposed the latent bug.

**Fixes shipped tonight (commit hashes follow):**
1. Renamed Railway env var `GTG_ACCOUNT` → `GTG_ACCOUNTS` on `resourceful-delight` worker. Closes known issue #7.
2. Deleted Railway env vars `GTG_EMAIL` and `GTG_PASSWORD` on worker. Misleading fallback removed; if `GTG_ACCOUNTS` is ever unset, worker now fails loudly instead of silently authenticating as wrong identity.
3. Changed worker exit code on GTG login failure from 0 to 1. Railway's `ON_FAILURE` policy now auto-restarts the worker, surfacing the issue via repeat-failure logs rather than silent death.

**Deferred (separate ClickUp tasks):**
- Decouple GTG init from worker startup (architectural change — let GolfNow/Chronogolf polling continue when GTG fails). Today's outage took down all three platforms because GTG init is a startup prerequisite. New task created.
- Create 2-3 backup GTG accounts (ClickUp `86ah69yf1`). Today's outage demonstrates the cost of single-account dependency on a captcha-required platform.

**Meta-lesson:** known issue #7 was documented on 2026-05-03 and deferred for 11 days. It cost ~30 min of worker downtime tonight. Half-done migrations in the "known issues" list should be treated as live risks, not parking lots. Audit the rest of that list for similar shape.

### 2026-05-13 (Batch 1 GTA course expansion — 126 new scraper entries shipped)

**What shipped:** 43 GolfNow + 81 Chronogolf = **126 new scraper entries** added to `golfnow_scraper.py` and `chronogolf_scraper.py` (and to `foreward-api/app/util/courses.py`). All entries are GTA-region only (Batch 1).

**Scraper totals after Batch 1:** GOLFNOW_COURSES: 55 entries. CHRONOGOLF_COURSES: 91 entries. COURSES dict: 146 entries.

**Source:** `foreward-scraper/docs/scrape_targets/ontario_batch1_to_add.json` (133 unique GTA facilities after dedup). Multi-course clubs expand to multiple scraper entries (e.g., Cardinal Golf Complex → 4 courses, Westview → 3).

**Drops and resolutions vs raw batch1 list:**
- 4 GolfNow entries dropped (already scraped via Chronogolf): Lionhead, Lakeridge Links, Silver Lakes — Chronogolf preferred
- 9 GolfNow non-course venues dropped (TopTracer ranges, TopGolf, GolfzonNorth, KStadium, Speedy Golf, Golf Wing, iRange) — slipped through triage keyword heuristic
- 1 GolfNow redundant entry dropped (Westview 27-Holes, covered by 3 Chronogolf courses)
- 2 additional cross-platform duplicates resolved at commit time (St. Andrew's Valley, Angus Glen South) — Chronogolf kept
- 5 Chronogolf clubs skipped entirely: Lebovic, Chedoke, King's Forest, Vic Hadfield (empty `/courses` endpoint), Westview "DO NOT USE" stub

**Chronogolf affiliation_type_id:** 5285 (confirmed visitor default) applied to all new entries. Per-course IDs require DevTools verification for any that return empty.

**Batch 2 (Ontario-near + Ontario-far, ~565 facilities) pending** — deferred until Batch 1 verifies live across a full poll cycle.

### 2026-05-13 (GolfNow SPA discovery — Playwright for Ontario course enumeration)

**Discovery:** GolfNow Ontario city directory pages (`/course-directory/ca/on/<city>`) are 100% client-side rendered (Vue SSR with Angular/Vue hydration). Raw HTML from `requests.get()` contains only the placeholder `~facilityid~` — no real facility IDs are present in the static response. The province index page (`/course-directory/ca/on`) IS static HTML and continues to use `requests`.

**Fix:** `scripts/enumerate_ontario_courses.py` replaces per-city HTTP fetch + regex with a single Playwright Chromium browser: `playwright_stealth` to reduce bot detection, `wait_until="domcontentloaded"` (not `networkidle` — GolfNow's background analytics polling never lets the page reach networkidle), then `wait_for_selector('a[href*="/tee-times/facility/"]', timeout=10s)` to confirm hydration, then `page.evaluate()` JS DOM traversal to extract facility links and names. Browser crash recovery up to 3 restarts; 1.5s sleep between 232 cities.

**Result (2026-05-13 run):** 229 GolfNow + 524 Chronogolf = **753 total Ontario facilities** enumerated. Zero-facility city rate: 49% (114/232 cities) — expected for small towns, well under 80% sanity-guard threshold.

**Why this matters:** These 753 facilities form the candidate pool for the GTA-area scraper. The `flag` field marks known indoor sims, driving ranges, and Shotgun Golf venues for manual review before adding to the active scraper registry.

### 2026-05-12 (consecutive_zero_polls false-alarm fix — tuple-based platform success contract)

**Problem:** `consecutive_zero_polls` incremented on any poll returning 0 slots, regardless of whether the request actually failed. GolfNow returning HTTP 200 + empty inventory (correct scrape, no bookings available for the searched date/players) was indistinguishable from a 403 or timeout — both returned `[]` from `fetch_one`. Counter climbed to 95+ on a healthy GolfNow poll cycle; alarms fired falsely.

**Root cause confirmed across all three platforms:** GolfNow and Chronogolf `fetch_one` returned `[]` for both success-empty and all failure modes. GTG `poll_tee_times` returned `[]` for all failure modes swallowed internally (Turnstile failure, search button failure, gateway timeout) — none of these propagated as exceptions to distinguish them from zero-inventory results.

**Fix — three-state return contract:**
- `None` — no alert work this poll (sentinel, unchanged from `bc527e3`)
- `(True, slots)` — platform was reached and responded, even if empty
- `(False, slots)` — request failed (non-200, timeout, exception, or navigation failure)

Counter rule: reset on `None` (no work) or `True` (reached platform); increment only on `False` (failed).

**Changes shipped:**
- `golfnow_scraper.py` — `fetch_one` returns `(bool, list)`; `poll_golfnow_tee_times` aggregates `had_success = any(ok for ok, _ in results)`, returns `(had_success, all_slots)`.
- `chronogolf_scraper.py` — same pattern. `course not open` early-exit returns `(True, [])` — not a failure.
- `tee_sniper.py` `poll_tee_times` — added `got_gateway_response` flag (set `True` in `on_response` callback when GTG gateway returns HTTP 200). Added `except Exception` to outer try/finally (Option A) — navigation failures now return `(False, [])` instead of propagating. Return type changed to `tuple[bool, list[dict]] | None`.
- `tee_sniper.py` call sites — all three platforms unpack `(success, slots)`; `gtg_count` now uses `len(gtg_slots)` directly instead of subtraction from `raw`. `gtg_slots_only = raw[:gtg_count]` replaced with `gtg_slots`.
- Counter loop — `platform_success` dict; condition changed from `count > 0` to `platform_success[platform]`.

**Secondary effect (GTG):** Turnstile failures, search button failures, and gateway timeouts were previously swallowed inside `poll_tee_times` and returned `[]`, which incremented the counter identically to zero-inventory. Now correctly typed `(False, [])` — alarm system treats them as failures. Navigation failures (previously propagated to loop-restart, bypassing counter entirely) are now caught and return `(False, [])`. This brings all GTG failure modes into the alarm system. Extends the silent-failure monitoring established to close known issue #9 (2Captcha balance auto-alert, 2026-05-08).

### 2026-05-12 (Block 11 — canonical course mapping restored)

Restored `app/util/courses.py` (deleted in Block 6 alongside the expiry loop). The original file was recovered from `git show 64ef4b8 -- app/util/courses.py`. New version has the same 22-course coverage (GolfNow + Chronogolf) but different API shape: `display_name(key)`, `course_platform(key)`, `all_keys()`, `all_courses()`. Display names use en-dashes (–) to match the scraper's `display_name` fields exactly, ensuring `sent_slots.course_name` joins work.

**Root cause of `fired_alerts_30d = 0`:** The Block 10 `/admin/course-demand` endpoint keyed `fired_alerts_30d` by the lowercase course key (e.g. `"lakeview"`) but `sent_slots.course_name` stores the scraper's display name (e.g. `"Lakeview Golf Course"`). These strings never matched. Fix: use `course_display_name(key).lower()` as the lookup key.

**GTG courses:** Not in the mapping. The GTG scraper captures `CourseName` directly from the GTG gateway API at runtime (it doesn't have a static `COURSES` dict like GolfNow/Chronogolf). GTG course names seen in production include "Dentonia Park" (sent_slot id 855, 2026-05-09) and "Humber Valley" (2026-05-08 false-alarm incident). For GTG courses in `/admin/course-demand`, `course_name` returns the raw key and `platform` returns None. `fired_alerts_30d` will match if `sent_slots.course_name.lower()` happens to equal the alert profile key.

**lionhead-masters included despite `active=False`:** Included for completeness in case any alert_profiles rows reference this key. The scraper won't poll it but users may have created alerts against it historically.

Commit: `09e5ced`

### 2026-05-12 (admin dashboard data expansion — 5 new endpoints)

Added five GET endpoints under `/admin/` to support an admin dashboard rebuild (frontend work separate). All use `Depends(require_admin)` (JWT + admin email check) — same auth as existing `/admin/dashboard`. No schema changes; all queries hit existing tables.

**Endpoints added:**

- `GET /admin/users` — paginated user list. Status badge computed server-side from `user_profiles` fields; alert counts pivoted by status; SMS total from `sent_slots`; `last_activity_at = max(notify_updated_at, MAX(alert updated_at))`. Filters: `?status=` (comma-sep badge names), `?search=` (email partial match). Default `limit=50`, max 200.
- `GET /admin/alerts` — paginated alerts with `user_email` joined. Filters: `?status=`, `?tier=free|paid`, `?course=`, `?user_id=`, `?search=`. Sorted `updated_at DESC`.
- `GET /admin/recent-fires` — `sent_slots` rows with `user_email` resolved. `?since=` ISO datetime bound (default: last 7 days). Max 200 rows. No cache (unlike `/activity`).
- `GET /admin/course-demand` — active alerts unnested by course key with 30d fire count and unique active-alert user count. Sorted `active_alerts DESC`.
- `GET /admin/course-requests` — `course_requests` aggregated by `LOWER(course_name)`. Includes `request_count`, `first_requested_at`, `last_requested_at`, `requester_emails` (capped at 10 per course). Sorted `request_count DESC`, then `last_requested_at DESC`.

**Query strategy:** Supabase Python client ORM + Python-side aggregation. No N+1: each endpoint makes 2–3 targeted queries regardless of row count. PostgREST embedded selects were not used — `sent_slots.alert_id` and `sent_slots.user_id` have no FK constraints, and `alert_profiles.user_id → auth.users(id)` (not `public.user_profiles`) makes cross-table embedding unreliable. Pattern matches existing admin.py style.

**Schema deviations from block spec:**
- `user_profiles.final_expired_at` and `alert_profiles.final_expired_at`, `polling_expires_at`, `renewals_used`, `expiry_state` were dropped in Block 6 (2026-05-09) and do not exist in the live DB. Omitted from all responses. The spec's "Expired" status badge (defined as `final_expired_at IS NOT NULL`) was adapted to `free_tier_grace_retry_used_at IS NOT NULL AND NOT is_active` — this captures the same user state (exhausted both free alert and grace retry without converting) using the live schema.

**Course key → display name gap (`/admin/course-demand`):**
~~No `app/util/courses.py` existed at the time of this block.~~ **Resolved in Block 11 (2026-05-12):** `app/util/courses.py` restored with 22 courses (GolfNow + Chronogolf). `/admin/course-demand` now returns proper display names and uses the display name for the `fired_alerts_30d` join. See Block 11 decision log entry.

### 2026-05-11 (launch verification + aesthetic pass + doc corrections)

Pre-ad-launch verification session. No code changes to foreward-api or
foreward-scraper this session. All work was: (a) verification against
production state, (b) ClickUp cleanup, (c) aesthetic pass on Lovable
frontend, (d) doc corrections in this file.

**Launch readiness verified:**
- Incognito sanity pass on goodlie.golf clean end-to-end (homepage, signup
  entry point routing to free-tier flow not Stripe, /dashboard, /alerts/new,
  /alerts/history, /account, /admin)
- Stripe checkout end-to-end conversion path validated via two existing
  paying subscribers (no fresh test transaction needed — webhook → is_active
  flip already exercised in production)
- PROXY_URLS env var on resourceful-delight/worker confirmed present with 20
  proxies. ClickUp 86ah69y6d closeable. Note: legacy singular PROXY_URL also
  still set; cleanup deferred (worker code reads PROXY_URLS, harmless)
- FREE_TIER_ENABLED=true on spirited-youthfulness/web service (set during
  Block 9 walkthrough Saturday); free tier live

**SendGrid renewals templates diagnosis (closes 86ahbkw2n as N/A):**
The original ticket asked to fix "2 renewals remaining" copy in free-tier
expiry templates. Investigation revealed:
- `git log --all --oneline -- app/free_tier_expiry_loop.py` returns no
  history — the file has never been committed to main
- `grep -rn "SENDGRID_TEMPLATE_FREE_TIER_EXPIRY" app/ tests/` returns no
  matches — no current code reads these env vars
- The three SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_1/2/3 env vars on Railway web
  service and their corresponding SendGrid Dynamic Templates are orphans
- Block 6 (Saturday 2026-05-09) removed the entire renewals/coupon mechanic;
  PRODUCT_FREE_TIER.md (canonical) explicitly forbids renewals, polling
  windows, and Stripe coupons
Conclusion: the stale-copy concern resolves itself because no code path
triggers those templates. Closed 86ahbkw2n with this explanation. Filed
post-launch cleanup ticket (low priority) to delete the orphan templates and
env vars.

**`app/free_tier_expiry_loop.py` doc-drift correction:**
The 2026-05-07 Block 3 decision log entry below describes an "in-process
free_tier_expiry_loop (5 min cadence, polling-window based, transitions
expiry_state, sends emails, generates Stripe coupons)" as if it were running
in production. The working-rules session header also references the file
path as a common fetch target. Both descriptions are wrong: the file was
never committed and Block 6 deprecated the entire mechanic it would have
driven. The Block 3 entry below is left in place for historical accuracy
but readers should treat any reference to free_tier_expiry_loop.py as
describing a never-shipped plan, not live code. PRODUCT_FREE_TIER.md is
the authoritative spec for current free-tier behavior.

**Aesthetic pass shipped to Lovable (homepage + /alerts/new):**
Brief-compliance pass against good-lie-design-brief.md §3, §4, §9. Changes:
- Primary CTAs (Get Your Free Alert, Create alert): Fairway (#2D3B2A) fill
  with bone (#F2EDE4) text, per brief §9 primary button spec
- Sign In secondary button: transparent background, --fairway border, --fairway
  text (matches primary color family, contrasts via fill-vs-outline)
- Header bar: Fairway-inverted strip (was previously transparent/bone), bone
  text and nav, matches the Fairway footer added same session — brackets the
  page top and bottom in dark green
- Footer: minimal Fairway-inverted strip with "© 2026 GOOD LIE" in JetBrains
  Mono, --type-mono-s, uppercase, 0.08em tracking (replaces previous "© 2026
  Good Lie" sans line on bone)
- Hero headline "Never miss a tee time.": 78px / weight 700 / line-height 1.05,
  single-line on desktop
- How It Works step titles (Set your alert / We monitor / Notify): 32px /
  weight 700 / line-height 1.2
- Utility chassis topo background removed from /alerts/new, /alerts/history,
  /dashboard, /account, /admin per brief §8.3 ("never in utility chassis")
- /alerts/new form card: --bone background, 1px --pencil at 20% opacity
  border, 4px radius, 32px internal padding (per brief §9 component spec).
  Restored mid-session after Lovable regression removed the card wrapper
- Courses We Monitor section vertical padding matched to How It Works for
  visual rhythm
- "Greater Toronto Area · 13 courses" pill: collapsed by default (no behavior
  change, attempted "bolder" treatment did not land cleanly)
Hero topo illustration NOT modified (per brief §8: Lovable cannot produce
the required precision; real Lakeview topo SVG to be sourced externally,
post-launch).

**Design brief drift (resolve before next design pass):**
- §5 (typography): brief mandates New York display serif for hero headline
  and wordmark. Current implementation uses sans (Inter or similar) for both.
  Decision this session: keep current sans treatment, amend brief.
- §14.3 (wordmark decision): brief left open; this session confirmed sans
  wordmark stays. Brief should be updated to reflect.
Both pending Dustin's brief revision; not blocking launch.

### 2026-05-09 (Block 9 — Free-tier launch walkthrough + three blocker fixes)

End-to-end walkthrough of the free-tier flow against the new product spec from `docs/PRODUCT_FREE_TIER.md`. Walkthrough surfaced three production-blocking bugs, all fixed in this session:

1. **`requireSubscription` route guards on free-tier routes (foreward, commit `2c74354`).** `/dashboard`, `/alerts/new`, and `/alerts/history` all had `requireSubscription` guards in `App.tsx` route definitions. Free-tier users (`is_active=false`, `is_beta=false` by design) were being bounced to `/account`, making the entire free-tier UI unreachable. Fix: removed `requireSubscription` from those three routes; left auth gate intact. `/account` and `/admin` retain their existing protection. Note: this gap was not caught in Block 8 — the AuthProvider routing fix in Block 8 addressed the post-signin redirect target but did not remove the subscription gate at the route definition level. The two layers are separate: AuthProvider controls where a signed-in user navigates; `App.tsx` route guards control whether a route is reachable at all.

2. **Premature `free_tier_used_at` stamp at signup (foreward-api, commit `2f62bf2`).** The `/auth/signup-free-tier` handler was stamping `user_profiles.free_tier_used_at` at account creation. This made the first-free-alert branch in `alerts.py:79` (which requires `free_tier_used_at IS NULL`) unreachable for any signed-up user — every freshly signed-up free-tier user got 402 on `POST /alerts`. Fix: removed the stamp from `auth.py`. The legitimate stamp at `alerts.py:99` (set on first alert insert) is unchanged.

3. **Phone-uniqueness index condition (migration `20260509_phone_hash_unique_on_signup.sql`).** The previous index `ix_user_profiles_phone_hash_free_tier` was partial `WHERE free_tier_used_at IS NOT NULL`, coupling phone-reuse prevention to the free-tier stamp. Removing the signup stamp (fix 2 above) would have opened a phone-reuse window between signup and first-alert creation. Fix: replaced with `ix_user_profiles_phone_hash_unique`, partial `WHERE phone_hash IS NOT NULL`. Phone is now locked to account at signup (when `phone_hash` is written), independent of free-tier state, matching `PRODUCT_FREE_TIER.md`: "phone and email are permanently locked to that account, neither can be reused for another free-tier signup, ever."

Walkthrough verified end-to-end on test account `dustinkeating87+test2@gmail.com` after all three fixes shipped: signup → phone verify → `/dashboard` reachable → `POST /alerts` 201 with `is_free_tier=true` → real scraper match fired SMS + email within minutes → second alert attempt correctly 402'd. Test user cleaned up post-walkthrough.

**Fact established this session:** external `git push` to `dustinkeating87/foreward` main DOES trigger Lovable's deploy pipeline. Previously uncertain. Bundle hash on goodlie.golf changed from `index-B2hBf-Wc.js` (Block 8) to `index-BsxcqL5M.js` (this session) without any Lovable AI activity, confirming Lovable's hosting auto-deploys any push to main regardless of source.

**Pre-launch state at session end:** `FREE_TIER_ENABLED=true` on Railway `web` service. Walkthrough success means the flag can remain enabled for soft launch, contingent on Lovable copy/UX improvements (separate prompt — addresses "Payment required" static label and adds "you've used your alert" CTA on returning-user dashboard).

### 2026-05-09 (Block 8 — Frontend Alignment)

Aligned the Lovable-managed React frontend (`dustinkeating87/foreward`) with the simplified free-tier model documented in `docs/PRODUCT_FREE_TIER.md`. Closes ARCHITECTURE.md known issue #27.

**Audit method:** Live page walk via Claude in Chrome connector (paid/beta paths only — non-paid paths require a free-tier test account, deferred to launch walkthrough); repo-level grep against the cloned foreward repo for deleted-endpoint references, dropped schema columns, and Block 3 lifecycle copy. Audit found that the courses-gate and renewal-ladder mechanics had not bled into the frontend (clean), but Block 3 copy and routing logic had.

**Five Lovable prompts shipped (one with fix-up):**

1. Dashboard post-fire subscribe CTA + grace-retry CTA + free-tier type updates (`api.ts` + `Dashboard.tsx`). Initial ship had a bug — `getAlerts()` called without status filter, returning only active alerts, leaving CTAs dead. Fix-up restored the intended behavior.
2. Subscribe.tsx rewrite — removed all "trial" copy, added `?from=fired` query-param variant for post-fire context.
3. AuthProvider.tsx login routing — simplified to always navigate to `/dashboard`. Free-tier users no longer get bounced to Stripe on login.
4. AlertHistory.tsx — free-tier fired alerts show subscribe CTA instead of "Try again."
5. Signup.tsx hero copy — "Try one alert, free for 14 days" → "Try Good Lie, free."

**Verification approach:** Each prompt verified two ways before being marked done — Chrome-connector live render check (no regression on the founder's beta account) and repo-level grep of the post-publish foreward source. Lovable claiming "Done" is not sufficient; both checks are required.

**Lovable failure mode caught:** Prompt #1 shipped dead because of an incorrect `getAlerts()` call. Repo-level verification caught it; live-render verification alone (which only tested the no-regression beta path) would have missed it. Going forward, every Lovable prompt requires both check types. Documented as known issue #28.

**What remains pre-launch:**
- Real-phone end-to-end walkthrough on `FREE_TIER_ENABLED=true` (gated on a fresh phone + temporary flag flip)
- Copy refinement pass on Lovable-shipped strings (Subscribe headlines, Dashboard CTAs, Signup hero — all currently using Claude-default copy)
- Backend `grace_retry_eligible` boolean exposure (Dashboard currently uses optimistic guess + 402 fallback)
- Pre-launch ticket `86ahbkx68` re-scoping (the "≥5 paid alerts across ≥3 courses" check is partially obsolete now that the courses-gate is gone)

**Canonical spec:** `docs/PRODUCT_FREE_TIER.md`. Anything that contradicts it is wrong.

### 2026-05-09 (Block 7 — Phone-Verification UX Hardening)

Closes ClickUp `86ahc02dc` (wrong-phone OTPs sent to strangers) and `86ahc027p` (generic 401 with no recovery path on signup).

**Per-phone rate limit (`app/phone_rate_limit.py`):** mirrors `app/ip_rate_limit.py` exactly — midnight-UTC reset, counter on `app.state.phone_rate_limit`, key is SHA-256 phone_hash (not raw E.164). Limit: 3 sends per phone per 24-hour window, matching the existing 3-resend cap. Fires after per-IP check, before Twilio Lookup. Raises 429 with actionable message when exceeded.

**Three distinct 401 error strings in `/auth/signup-free-tier`:** replaced the single generic `"Invalid or expired verification token"` with: `"Verification token not recognized."` (token_not_found), `"Verification token has expired. Please request a new code."` (expired), `"This verification code was sent to a different phone number. Please use the same number you entered when requesting the code."` (phone_mismatch). `log.warning(path=...)` diagnostics added alongside each (these were absent from the handler before this block). All three remain HTTP 401.

**Tests:** 3 new tests in `tests/test_signup_free_tier_errors.py` assert the exact detail strings for all three 401 paths. Kept in a separate file from `tests/test_signup_free_tier.py` because the existing file covers status-code contracts and regression guards — adding detail-string asserts there would require touching AC3/AC4 in ways that muddy regression history. New file's scope: "Block 7 error-string contract." 50/50 tests passing.

**Code:** commit `a296efc` on `origin/main`. `FREE_TIER_ENABLED` remains false; no production behavior change.

### 2026-05-09 (Block 6 — Free Tier Cleanup & Realignment)

Ripped out the Block 3 free-tier lifecycle machinery (polling window, renewal ladder, Stripe coupon generation, paid-coverage course gating) and replaced it with the simple model documented in `docs/PRODUCT_FREE_TIER.md`: one alert, one SMS, one email, then convert; one grace retry on non-firing expiry.

**What was undone:** `app/free_tier_expiry.py` (asyncio expiry sweep loop), `app/stripe_coupons.py` (coupon generator), `app/routers/courses.py` (paid-coverage `/courses/available-for-free-tier` gate), `app/util/courses.py`, `tests/test_free_tier_logic.py`, `tests/test_courses_util.py`; startup hook in `main.py` that booted `free_tier_expiry_loop`; `send_free_tier_expiry_email` + `send_final_expiry_email` in `email.py`; `stripe_free_tier_coupon_id` in `config.py`; Block 5b creation gate ladder in `alerts.py` (the expiry_state + renewals_used logic); `/alerts/{id}/renew` endpoint; lifecycle helpers in `dependencies.py`.

**What was kept:** phone verification, signup endpoint (`/auth/signup-free-tier`), `free_tier_used_at` user column, `is_free_tier` alert column.

**What was added:** `user_profiles.free_tier_grace_retry_used_at` column + creation-gate logic in `alerts.py`, `send_free_tier_non_firing_expiry_email` in `email.py`, non-firing-expiry email trigger in `main.py` `expire_stale_alerts`, canonical product spec `docs/PRODUCT_FREE_TIER.md`, salvaged tests `tests/test_dates_util.py` + `tests/test_free_tier_simple.py`.

**Schema:** migration `20260509_simplify_free_tier.sql` applied to prod 2026-05-09. 5 columns dropped from `alert_profiles` (`polling_expires_at`, `renewals_used`, `expiry_state`, `final_expired_at`) and `user_profiles` (`final_expired_at`) — no data loss (verified zero non-null values pre-migration). 1 column added (`user_profiles.free_tier_grace_retry_used_at`). 1 index dropped (`ix_alert_profiles_polling_expires_at_free_tier`).

**Code:** commit `64ef4b8` on `origin/main`. 14 files changed, net −485 lines. 47/47 tests passing.

**Failure-pattern meta-note:** Prior sessions specified a more complex free tier than Dustin wanted. The drift went undetected because plan docs (especially Block 3) led with mechanism — expiry sweeps, renewal ladders, coupon generation, course gating — rather than user experience. Decision tables formatted as "ambiguities resolved" framed product-shape choices as technical decisions, which got rubber-stamped without the user-experience question being asked. Going forward, any work touching the free tier must read `docs/PRODUCT_FREE_TIER.md` at session start and operate within its bounds.

**Out of scope:** Lovable frontend alignment (course picker, dashboard CTA, grace-retry UX) is a separate downstream block. End-to-end walkthrough on a real phone is gated on Lovable being aligned. `FREE_TIER_ENABLED` remains `false` in prod.

**Canonical spec:** `docs/PRODUCT_FREE_TIER.md`.

### 2026-05-08 (late evening — reliability sprint)

After Block 5b ship and Lovable signup rebuild earlier in the session, knocked out a sprint of reliability + cleanup work:

**Test user cleanup:** Deleted test user dustinkeating87+freetier1@gmail.com (UID 87ba8c28-db02-4cd6-8641-6be29dd41f30) via direct Supabase. Cascade cleared associated user_profiles row. The other test user mentioned in the handoff (dustinkeating87+test@gmail.com) was already gone — handoff was stale. +16475155754 phone now unblocked for next-session real-user signup verification.

**Worker /healthz endpoint shipped** (foreward-scraper commits `b2ea3ad` + foreward-api doc commit `62ce236`). Closes known issue #6. aiohttp background task on the scraper, in-process timestamp comparison, three states (starting/healthy/stale). Railway healthcheck wired. All three states tested locally.

**2Captcha balance auto-alert shipped** (foreward-api commit `29f0e3a`, migration applied to prod). Closes known issue #9. 15-min polling cadence via `/scraper-heartbeat`, $5 alarm threshold, durable DB-backed state, transition-only alarm pattern (matches existing silent-failure alerts). Verified live in prod — first check returned $16.53. `CAPTCHA_API_KEY` added to Railway `web` service env vars.

**Lovable batch shipped:** noindex on `/admin` (after one false-claim round), data-driven platform cards on `/admin` (3 cards instead of hardcoded 4 — EZLinks gone), dashboard alert toggle bound to `alert.status === 'active'` instead of legacy `active` column. Closes ClickUp `86ah69ypk`, `86ah8d3v1`, `86ahbkw5h` (latter two via comment-closure; status flipping is on Dustin). Closes known issue #18.

**New known issue #26 (Lovable summaries unreliable):** Lovable claimed noindex was 'already there' on first round when it wasn't. Always verify Lovable changes via rendered-DOM inspection, never trust summary alone. Documented as known issue #26.

Lessons:
1. Direct Supabase access via the connector is a real productivity multiplier vs. having Claude Code do schema work — when the change is small (single migration, single delete), connector is faster and self-verifying.
2. End-of-block doc updates should batch reliability work + cleanup work + Lovable work into one entry rather than spreading across separate commits. This is the cleanest record of "what shipped tonight."
3. Lovable's summary claims now require independent verification, especially for missing-element work like meta tags. View-source or Elements-inspector is the only ground truth.

### 2026-05-08 (2Captcha balance auto-alert shipped)

`app/captcha_balance.py` added to foreward-api. `check_captcha_balance()` hits `2captcha.com/res.php?action=getbalance` directly from the API service. `maybe_check_and_alert(supabase)` is called on every `/scraper-heartbeat` but internally rate-limits to once per 15 min (`CAPTCHA_BALANCE_CHECK_INTERVAL_MINUTES`, default 15). Alarm state is persisted in three new `scraper_health` columns: `captcha_balance_alarmed` (boolean), `last_captcha_balance_check_at` (timestamptz), `last_captcha_balance_usd` (numeric 10,4). Alarm email fires on `False → True` transition; recovery email on `True → False`. First check after migration (`NULL` prev state) sets state without emailing. 2Captcha API error preserves existing state and sends no email. 9 tests added. Migration file: `20260508_add_captcha_balance_alarm_state.sql` — apply manually via Supabase SQL Editor. `CAPTCHA_API_KEY` must be added to Railway `web` service env (currently only on worker). Threshold default lowered from 10.0 (`CAPTCHA_BALANCE_THRESHOLD` in old admin.py constant) to 5.0 (`CAPTCHA_BALANCE_ALARM_THRESHOLD_USD`). Replaces the scraper-reported transition check that was previously in `/scraper-heartbeat` handler — that check was stateless across API restarts and fired only hourly (scraper's balance refresh rate). Closes ClickUp `86ah8bq89` and known issue #9.

### 2026-05-08 (/healthz worker liveness endpoint shipped)

`GET /healthz` added to foreward-scraper (commit `b2ea3ad`). Runs an aiohttp server on `$PORT` (default 8080) as a background asyncio task alongside the main poll loop. The health signal is an in-process `float` timestamp written by `mark_poll_completed()` at the end of each successful poll iteration — no DB reads inside the handler. Response contract: 200 `{"status":"starting"}` within 90s grace period on startup; 200 `{"status":"healthy","seconds_since_last_poll":N}` while fresh; 503 `{"status":"stale",...}` after 180s without a completed poll (3× the 60s poll interval). Railway `healthcheckPath` set to `/healthz` in `railway.json`. Closes ClickUp `86ah8bq8w` and known issue #6.

### 2026-05-08 (evening session — Block 5b ship + Lovable signup rebuild + cleanup)

Frontend free-tier signup flow shipped on `/auth?mode=signup`. Rebuilt from scratch over a single Lovable session: vertical band stack (4 bands), persistent topo page background with 60% bone overlay, center-aligned spine, equal `min-height` bands, orange step numerals as visual accent. Replaces the previous paid Stripe-redirect signup at the same URL — per pricing model A, there is no longer a paid signup path at site entry; paid upgrades happen post-fire from the dashboard. Style guide section above documents the locked design tokens. New "Frontend signup flow" section captures the page structure. The orphaned `/signup` route from an earlier Lovable iteration is currently redirecting/no-op; cleanup deferred (does not block launch).

Block 5b shipped backend-side (commits `a2b519a` for the gate ladder + `is_user_free_tier()` classifier, `6d4d9bd` for the doc). 31 tests passing locally. Prod-side AC verification deliberately deferred to a real-user walkthrough on a fresh phone (added as known issue #25). Same deferred-verification pattern as Block 3.

Cleanup work shipped:
- README rebranded (commit `a6a9730`) — closes known issue #8
- `_parse_iso()` extracted to `app/util/dates.py`, all four call sites import the helper (commit `582743b`) — closes known issue #21
- `ezlinks_scraper.py` deleted (foreward-scraper commit `1bad5cf`, foreward-api doc commit `0adc06f`) — closes known issue #19. The "vestigial Lakeview code" framing in the original issue was misleading; the file was the retired EZLinks platform scraper that happened to scrape Lakeview, not Lakeview-specific code.

Architecture doc gap from 2026-05-04 → 2026-05-06 acknowledged but not back-filled (separate decision log entry above explains).

Open at session end:
- Block 5c (Lovable signup) shipped tonight — sits behind the `FREE_TIER_ENABLED=false` flag with the rest of the free-tier path
- Block 5b prod verification — known issue #25
- Block 4b (Stripe coupons + email integration) still pending, low priority, can land any time

Lessons:
1. Trust nothing about commit state at session start without `git log --oneline -5 origin/main`. Tonight's handoff said tip was `6d952c5` and Block 5b not shipped — both stale. Block 5b had already shipped (`6d4d9bd`).
2. Lovable's "Done" summary is not the same as "deployed to production." Always Publish + hard-refresh `goodlie.golf` before assuming changes are live.
3. State drift between style guides is a real failure mode. The original ARCHITECTURE.md style spec was outdated by ~5 days when this session started; the active May 8 style guide had to be pasted in mid-session. Style guide now lives under version control alongside schema and infrastructure.

### 2026-05-08 (style guide + pricing model captured)

Frontend style guide formalized in ARCHITECTURE.md as a new top-level section ("Frontend style guide"). Supersedes any earlier brief in Cowork memory or older Lovable prompts. Style is what's currently shipped on goodlie.golf and what Block 5c (free-tier signup page) is being built against. Key locked decisions: Inter weight 900 for display (NOT serif, NOT Space Grotesk), six-color palette with `#FF4A1F` flag orange as the single accent, transparent-fill orange-bordered primary buttons (NOT fairway-green-fill), no grays, no pure black, no gradients/shadows/dark-mode.

Pricing model also corrected. The Product section previously said "$9.99 CAD/mo, 7-day free trial." That's wrong — there is no trial. Current model: free-tier first signup (one alert, no credit card), paywall after the alert fires. Paid tier remains $9.99 CAD/mo. Updated in the Product section above.

Lesson: design state was drifting in Lovable while ARCHITECTURE.md still referenced the old brief. Caught when Block 5c prompt was being prepared and the assistant nearly pasted Lovable instructions referencing New York serif and fairway-green button fills. Style guide now lives under version control alongside schema and infrastructure — same drift protections apply.

### 2026-05-07 (Block 5a addendum — signup-free-tier `used` flag bug, FIXED)

Root cause: `phone_verification_codes.used` was set to True by `verify_phone` (correct — marks OTP consumed) then checked by `signup_free_tier` as a proxy for "verification_token already spent." Since every legitimately issued token has `used=True`, the happy path was unreachable — every call returned 401.

Fix (commits on main, 2026-05-07): removed the `used` check from `signup_free_tier`; post-signup invalidation now sets `token_expires_at = NOW()` instead of re-setting `used=True`. Bogus/no-token path (401 on missing row) and expired-token path (401 on token_expires_at) are unaffected. 11 unit tests pass. Bogus-token 401 confirmed against deployed Railway API post-deploy.

AC1 (happy path, real phone) still pending: verification_token for +16475155754 expired before redeploy. Fresh SMS cycle required — resuming tomorrow.

Lesson: a single boolean used to mean two different things across two endpoints. Flag for any future block touching `phone_verification_codes` — see Known Issues note on the table above.

### 2026-05-07 (Block 4a — SendGrid Dynamic Templates for free-tier expiry emails)

Block 4 originally scoped both SendGrid template upgrades AND Stripe 50% coupon generation. Split during planning into:
- Block 4a (this entry): SendGrid Dynamic Templates only — shipped this session
- Block 4b (deferred, ClickUp `86ahc0b9e`): Stripe coupon generation + frontend checkout flow

Rationale: coupons are conversion optimization with no audience pre-launch (FREE_TIER_ENABLED=false). Templates are foundational. Splitting unblocks Block 5 (Lovable signup) faster.

**Implementation (commit c4ea790 + earlier slug-dict commit):**
- Three SendGrid Dynamic Templates created via API on 2026-05-07:
  - Expiry 1 (First Window): `d-f53c968e8bb645a0ba98844549b2d2f1`
  - Expiry 2 (Last Renewal): `d-bfbc0e264a2e4092ab236e6c594f7611`
  - Expiry 3 (Final): `d-af240773d6ec40899f6c20ae9c685dcf`
- Templates use Handlebars `{{first_name}}` and `{{course_name}}`. CTAs hardcoded to `https://goodlie.golf/subscribe` (frontend route TBD, ClickUp `86ahc05ry`).
- New helper `app/email.py::send_dynamic_template()` — non-raising, follows alarm-email failure-handling contract.
- New module `app/util/courses.py` — `COURSE_DISPLAY_NAMES` dict (22 courses across GolfNow + Chronogolf), `slug_to_display_name()`, `courses_to_display_string()`. GTG courses fall through to title-case fallback (no static slug list; names come from API at runtime).
- Three new Railway env vars on `web` service: `SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_1/2/3`.
- Plaintext expiry emails in `free_tier_expiry_loop` swapped for `send_dynamic_template()` calls.
- From-name: `Good Lie <hello@goodlie.golf>` (locked branding decision).
- `first_name` source: hardcoded fallback `"there"` — `user_profiles` has no first_name column. Future block to address properly.
- Plan doc: `foreward-api/docs/superpowers/plans/2026-05-08-block-4a-sendgrid-templates.md`
- 57/57 tests passing pre-push.

**Verified mid-session (pre-implementation):**
- `/auth/signup-free-tier` confirmed working end-to-end. Test user `dustinkeating87+freetier1@gmail.com` (UID `87ba8c28-db02-4cd6-8641-6be29dd41f30`) created via direct API call. `phone_verified=true`, `phone_hash` populated, `free_tier_used_at` set, `is_active=false`, `is_beta=false`, `trial_end=NULL`.

**Verification deferred to next session:**
- Manual expiry-transition trigger + email-arrival check. Tomorrow before content blocks.

**Verification artifacts (cleanup post-launch):**
- Test user `dustinkeating87+freetier1@gmail.com` (UID `87ba8c28-db02-4cd6-8641-6be29dd41f30`) joins existing `+test@gmail.com` test user (UID `76f71a7d-...`) on the post-launch deletion list. Both block fresh signups on the same phone via `phone_hash` uniqueness.

**Bugs identified (filed as subtasks of master `86ahavm5n`):**
- `86ahc027p` — `/auth/signup-free-tier` returns identical 401 detail for three distinct failure modes (token_not_found, expired, phone_mismatch). Server logs already differentiate. Cost ~30 min in this session.
- `86ahc02dc` — `/auth/send-verification-code` has no phone-ownership check; typos send OTPs to strangers.

**Frontend dependency filed:**
- `86ahc05ry` — Lovable: `/subscribe` redirect route. New email CTAs link here; route doesn't exist yet.

**Lessons worth keeping:**
- Splitting tickets at planning time when scope expands beyond a session > half-shipping. Block 4 → 4a + 4b cleanly.
- Stale verification tokens cause same 401 as wrong-phone tokens. Distinct error messages cost nothing and save real debugging time.
- Phase 1 (gather facts) before Phase 2 (form hypothesis) caught the mismatched-phone diagnosis in one DB query rather than another guess-and-check loop.

### 2026-05-08 (Block 5a — free-tier signup endpoint, VERIFIED CLOSED)

POST /auth/signup-free-tier endpoint shipped, fixed, and verified end-to-end. Block 5a master ticket pending closeout (86ahbkwf6 still open — spans 5a+5b+5c). Plan doc: docs/superpowers/plans/2026-05-07-block-5a-free-tier-signup-api.md. Debug-state addendum: docs/superpowers/plans/2026-05-07-block-5a-debug-state.md.

Commit history (foreward-api/main):
- 13bf5b6 — initial endpoint scaffold
- 9c9143f — 500-on-bogus-token fix (AC7)
- fad2887 — used-flag dual-semantics fix (the real bug, root cause below)
- c4ea790 — diagnostic logging revert (clean state)

Root cause of the AC1 401 bug (fad2887): phone_verification_codes.used was being written to True by /auth/verify-phone (correct — marks OTP consumed) AND being read as a token-replay guard in /auth/signup-free-tier. Since used=True for any legitimately issued token, the happy path was unreachable. Fix: stopped reading used in signup_free_tier; replaced post-signup write of used=True with token_expires_at=NOW() so token replay is gated by expiry instead. The verification_token field is intentionally NOT nulled on signup — replay protection is via token_expires_at being set to the past.

AC verification (all PASS as of 2026-05-08):
- AC0 kill switch → 503 — unit test
- AC1 happy path end-to-end — verified by data inspection of dustinkeating87+freetier1@gmail.com signup on 2026-05-07 22:19:07 UTC (auth.users + email_confirmed_at + last_sign_in_at + user_profiles.phone_verified=true + free_tier_used_at set + Stripe fields NULL + is_active=false + token_expires_at set to ~signup time + 0 alert_profiles, matching the spec)
- AC2 expired token → 401 — unit test
- AC3 phone mismatch → 401 — unit test
- AC4 phone already claimed → 409 — unit test
- AC5 email already exists → 409 — unit test
- AC6 compensating delete on mid-flow failure → 500 — unit test
- AC7 bogus token → 401 (not 500) — unit + production curl

Diagnostic-logging detour: commit e4a8a93 added temporary logging during the 401 investigation; reverted in c4ea790 once the dual-semantics root cause was identified. Captured here so the e4a8a93→c4ea790 commit pair has documented intent.

Block 5b (free-tier alert creation, modifies POST /alerts) shipped 2026-05-08. Block 5c (Lovable signup prompt skeleton) plan doc at docs/superpowers/plans/2026-05-07-block-5c-*.md. Pending separate session.

Cleanup deferred:
- The freetier1 test user (UID 87ba8c28-db02-4cd6-8641-6be29dd41f30) and its phone_verification_codes row (id ed812333) should be deleted before launch to free up the +16475155754 phone for real use. Tracked alongside the existing Block 3 cleanup item for dustinkeating87+test@gmail.com.

Bug 86ahbkw2n ("2 renewals remaining" copy mismatch from Block 3 verification) remains open and is now expected to be addressed as part of Block 4b or wherever the user-facing free-tier email copy gets revisited.

### 2026-05-08 (Block 5b — free-tier alert creation logic, SHIPPED)

Concurrent alert cap replaces lifetime `free_tier_used_at` block in `POST /alerts`. Added `is_user_free_tier()` classifier (True when `free_tier_used_at IS NOT NULL AND NOT is_active`). Commit: a2b519a.

Key changes to `app/routers/alerts.py`:
- `is_user_free_tier(profile)` added alongside `_is_paid()`.
- Defense-in-depth 503 (not 403) for existing free-tier users when `FREE_TIER_ENABLED=false`.
- Old `if free_tier_used_at:` → 402 block removed. Replaced with a live DB count of `is_free_tier=true` alerts with `status IN ('active','fired') AND expiry_state != 'final_expired'`; count ≥ 1 → 402.
- `final_expired_at` user-level permanent block preserved at position 4 in gate order.
- Paid path: zero change.

Gate order (unpaid branch): is_user_free_tier+flag_off→503 → flag_off→403 → final_expired_at→402 → concurrent cap≥1→402 → free-tier creation.

10 new unit tests in `tests/test_free_tier_logic.py` (31 total, all passing). Compile clean. Plan doc: `docs/superpowers/plans/2026-05-07-block-5b-free-tier-alert-creation.md`.

No DB migration — all columns (`is_free_tier`, `expiry_state`, `renewals_used`, `polling_expires_at`) were added in Block 1.

### 2026-05-08 (architecture doc gap acknowledged)

ARCHITECTURE.md was lost from local filesystem on 2026-05-06 and recovered from a 2026-05-03 baseline. Updates between 2026-05-03 PM and 2026-05-06 morning (2Captcha balance auto-alert wiring, ClickUp/doc reconciliation work, by-request picker confirmation, alert form defaults patches) were never re-derived back into the doc. ClickUp 86ahb0m91 tracked the recovery work.

Decision: NOT back-filling. The work shipped, the current state is observable in production, and re-deriving 60 hours of history from git + ClickUp doesn't pay for itself. The by-request picker pattern (the only piece that's a reusable decision template rather than a one-off event) is now captured in the locked-in decisions table above. Other items in that window are either already-tracked tickets (2Captcha balance auto-alert is open as 86ah8bq89) or one-time fixes whose current state is the production state. Going forward, the end-of-block ARCHITECTURE.md update rule prevents the same gap.

### 2026-05-07 (Block 3 — free-tier alert lifecycle, VERIFIED)

Block 3 implementation complete and verified in production. 7 commits (b108f76..13d2bde) on foreward-api/main, 21 new tests passing (29 total). Verification script scripts/verify_block_3.py (gitignored) confirmed AC1 (paid no-regression) and AC7 (expiry sweep) PASS against deployed Railway API. Plan doc: foreward-api/docs/superpowers/plans/2026-05-07-block-3-free-tier-alert-lifecycle.md. Master ticket 86ahavm5n. Block 3 ticket 86ahazaza. Closed 86ahbacxw with Task 1.

Schema documentation drift caught and corrected. Block 1 (earlier session) added columns to alert_profiles and user_profiles but did not update this doc. Schema additions logged retroactively above (ARCHITECTURE.md edits A and B in this commit). Lesson: every Block must end with an ARCHITECTURE.md update before close. Adding to session-end checklist.

Key architectural decisions:
- is_free_tier is per-ALERT (alert_profiles), not per-user. A user can hold paid and free-tier alerts simultaneously. free_tier_used_at on user_profiles is the lifetime once-only flag.
- Two expiry mechanisms run independently:
  - Scraper-driven POST /scraper/expire-alerts (60s cadence, date-based, sets status='expired')
  - In-process free_tier_expiry_loop (5min cadence, polling-window based, transitions expiry_state, sends emails, generates Stripe coupons)
  - These can race on overlapping rows. Loop wins on state because it updates after. Benign.
- Railway sleepApplication: false confirmed via Railway API for spirited-youthfulness web service. In-process loop is safe.
- free_tier_expiry_loop updates BOTH status='expired' AND expiry_state='expired_pending_renewal' on first transition (verified 2026-05-07).
- New endpoint GET /courses/available-for-free-tier returns {courses, count, available} (NOT bare []) gated behind FREE_TIER_ENABLED env var. Returns 503 when off, 200 with available=false when on but no qualifying paid alerts. Output format is human-readable course names.
- FREE_TIER_ENABLED kill switch: rejects free-tier paths everywhere, not just /courses. Verified via curl with flag false (503) and true (200). Reset to false post-verification.
- Block 4 (Stripe coupons + email template upgrade) is next.
- Free tier lifecycle: 14-day initial polling window, up to 2 renewals via Stripe coupon (3 polling windows total, 42 days max alert lifetime), then final_expired.

Bugs identified during verification (filed as ClickUp tickets under master 86ahavm5n):
1. 86ahbkw2n — Free-tier expiry email copy says "You have 2 renewals remaining" but renewals_used schema and architectural intent suggest 1 free renewal max. Diagnose before Block 4 ships email template work.
2. 86ahbkw5h — Dashboard alert toggle on goodlie.golf reflects legacy active column, not canonical status. Alerts with status='fired' display as "on." Update toggle binding.
3. 86ahbkwf6 — Lovable signup blocker — pre-launch critical. All new users currently routed to Stripe checkout. Free-tier path is unreachable from production frontend.
4. 86ahbkwka — Courses endpoint returns human-readable names — frontend will need name→slug mapping for rendering.
5. 86ahbkx68 — Pre-launch checklist: verify ≥5 paid alerts across ≥3 courses before flipping FREE_TIER_ENABLED=true. Resolve Bug 3 (signup wall) before launch.

Pre-launch checklist ticket needed: "Verify ≥5 paid alerts across ≥3 courses before flipping FREE_TIER_ENABLED=true in prod. Then resolve Bug 3 (Lovable signup wall) before launch."

Verification artifacts (cleanup):
- Test user dustinkeating87+test@gmail.com UID 76f71a7d-5f4b-4284-92cb-6504ec71f7c3 provisioned with phone_hash set manually via SQL. Should be deleted post-launch to free up phone uniqueness on +16475155754.
- Founder Dentonia alert (id 1a546482-2132-4153-a891-e6f9414e5be8) modified during verification to status='active', date_from=2026-12-01, date_to=2026-12-31. Deleted 2026-05-07 via service role.
- FREE_TIER_ENABLED reset to false in Railway post-verification.

### 2026-05-06 (Block 2 — phone verification endpoints)

Three new endpoints added to `foreward-api` under `/auth/`: `send-verification-code`, `verify-phone`, `resend-verification-code`. All gated by `FREE_TIER_ENABLED=false` — return 503 in production until Block 9 flips the flag.

New files: `app/util/phone.py` (SHA-256 hashing, E.164 validation), `app/twilio_lookup.py` (Twilio Lookup v2 wrapper with in-memory cache), `app/ip_rate_limit.py` (midnight-UTC IP counter on `app.state`), `app/routers/phone_verification.py` (3 endpoints). New unit tests in `tests/test_phone_util.py` (8 tests, all passing).

New DB table: `phone_verification_codes` — migration file committed but Dustin must apply via Supabase SQL Editor before Block 2 endpoints are fully functional.

Verification token design: on successful `verify-phone`, a URL-safe UUID token is stored on the `phone_verification_codes` row and returned to the client. Block 5 (Lovable signup flow) will submit this token to prove phone was verified before account creation.

**AC verification results (2026-05-06):** AC1 (503 guard, prod), AC2 (happy path), AC3 (IP rate limit), AC5 fast-path (resend cooldown), AC6 (single-use + expiry) all PASS. AC4 (phone uniqueness) and AC5 max-3 cap deferred to code-review-only — runtime verification blocked by FK constraint on `user_profiles` (AC4) and 3-min wait (AC5 cap). Full details in ClickUp `86ahaza0k` closeout comment.

**AC5 spec gap:** first resend has no cooldown — `last_resend_at` is NULL on row creation, so the 60s check is bypassed on the first resend. Cooldown only applies resend→resend. Flagged for Block 5 fix.

**Python 3.9 / Railway 3.11 patch:** `_parse_iso()` helper added in Block 2 and centralized in `app/util/dates.py`. Normalizes fractional seconds to 6 digits before calling `fromisoformat`. Required because Python 3.9 rejects non-6-digit microseconds; Supabase/PostgREST returns any precision. Railway runs 3.11 — prod unaffected. All four call sites patched: `phone_verification.py`, `heartbeat_monitor.py`, `routers/auth.py`, `routers/admin.py`. ClickUp `86ahbacxw` closed 2026-05-08.

ClickUp `86ahaza0k` closed.

### 2026-05-06 (Block 1 — free-tier schema foundation)

Migration `20260506_add_free_tier_columns.sql` applied to prod via Supabase SQL Editor, committed to `foreward-api/supabase/migrations/`. Adds 5 columns to `alert_profiles` (`is_free_tier`, `polling_expires_at`, `renewals_used`, `final_expired_at`, `expiry_state` with CHECK constraint) and 4 columns to `user_profiles` (`phone_verified`, `phone_hash`, `free_tier_used_at`, `final_expired_at`). Two partial indexes: `ix_user_profiles_phone_hash_free_tier` (unique on `phone_hash WHERE free_tier_used_at IS NOT NULL` — **superseded 2026-05-09** by `ix_user_profiles_phone_hash_unique` WHERE `phone_hash IS NOT NULL`; see migration `20260509_phone_hash_unique_on_signup.sql`) and `ix_alert_profiles_polling_expires_at_free_tier` (btree on `polling_expires_at WHERE is_free_tier = true AND expiry_state IS NULL` — **dropped 2026-05-09** by `20260509_simplify_free_tier.sql`). `FREE_TIER_ENABLED=false` added to Railway `web` service — all free-tier branches gated on this flag; no behavior change in production until Block 9 flips it to true. No existing paid alerts affected (all new columns null/default). ClickUp `86ahaz9e0` closed. ARCHITECTURE.md moved into `foreward-api/docs/` and committed — previously unversioned and stored in Cowork only. Doc drift from 2026-05-03→2026-05-06 (2Captcha balance auto-alert, ClickUp/doc reconciliation, By-request picker confirmation, alert form defaults patches) tracked in ticket 86ahb0m91.

### 2026-05-03 (afternoon — backups, alerts, CI, cleanup session)

**Backups (closes known issue #5):** Set up weekly Postgres backups via local Mac pg_dump driver + launchd schedule + Google Drive sync. Restore runbook committed at `foreward-api/scripts/backup/RESTORE.md`. Quarterly test reminder logged (ClickUp `86ah8bnjk`). DB password reset to alphanumeric (avoids URL-encoding issues with the connection string).

**Orphan auth.users cleanup (closes known issue #3):** Deleted 14 orphan auth.users (test/dev accounts from launch testing) plus their dependents (4 sent_slots, 1 expired alert_profile, 1 used invite_code un-used). Discovered along the way that 4 FK constraints exist between `public` and `auth.users` (alert_profiles CASCADE, course_requests SET NULL, user_profiles CASCADE, invite_codes NO ACTION) — previous version of this doc claimed there were none. Doc corrected.

**CI parse-check on both repos:** Added GitHub Actions workflow to `foreward-api` and `foreward-scraper`. Each runs `pip install -r requirements.txt` then `python -m compileall` on the source tree. Both passing on first run (~20s each). Committed via GitHub web UI because local PAT lacks `workflow` scope. "Wait for CI" Railway toggle still off — workflows advisory until enabled.

**Silent-failure email alerts (commit `337c048` on foreward-api/main, closes ClickUp `86ah8bnxv`):**
- New module `app/email.py` — thin httpx wrapper around SendGrid `/v3/mail/send`. No new package needed.
- `/scraper-heartbeat` reads prev `consecutive_zero_polls` BEFORE upserting, compares per-platform, fires alarm email when `prev < threshold AND new >= threshold`, recovery email when `prev >= threshold AND new == 0`.
- New env vars on Railway `web` service: `ALARM_THRESHOLD_POLLS=10`, `ALARM_EMAIL_TO=hello@goodlie.golf`, `ALARM_EMAIL_FROM=hello@goodlie.golf`.
- Email failures wrapped in try/except — never break the heartbeat.
- **Tested end-to-end:** set threshold=1, reset `consecutive_zero_polls` to `{}`, next worker poll triggered alarm emails for `golfnow` and `chronogolf`.
- **First real-world catch (PM):** GolfNow went silent for 101 polls. Detection works.
- Threshold reset to 10 post-test.

**ClickUp tasks added:** `86ah8bnp3` (credentials reference), `86ah8bnjk` (quarterly restore test), `86ah8bq89` (2Captcha balance monitor), `86ah8bq8w` (worker healthcheck spec), `86ah8btux` (filter silent-failure alarms by ALERTING_PLATFORMS).

**Live state movement during this session:** auth.users 33 → 21 (14 deleted, 2 new signups). `alert_profiles.status='fired'` 0 → 7 — the lifecycle code shipped this morning is firing alerts in production. `sent_slots` 126 → 122 (4 orphan rows cleaned).

**Late afternoon — GolfNow false-alarm investigation:**

Admin dashboard showed GolfNow alarming (101 zero polls). Investigation revealed it was not a real failure. Worker logs:

```
[golfnow] No courses match active alerts — skipping
```

Both active alerts targeted Humber Valley (GTG only). GolfNow had no work to do, returned 0 slots, counter ticked, crossed threshold, false alarm fired.

This exposed a fundamental incompatibility between the alert-driven filtering optimization (scrapers only fetch courses with matching active alerts) and `consecutive_zero_polls` as a health signal. The morning's "successful" 11:57 AM test alarm was almost certainly also a false positive on the same root cause — by then alerts were already churning to `fired` faster than expected.

ClickUp `86ah8btux` scope expanded from "filter by ALERTING_PLATFORMS" (catches chronogolf only) to "filter by ALERTING_PLATFORMS AND runtime scrape attempt" (catches all short-circuit cases). Priority bumped 🔵 → 🟠. Scraper fix shipped same session.

**Meta-lesson:** the silent-failure alert infrastructure worked correctly — it surfaced a real measurement bug. But "first time it fired" being a false positive is a credibility hit. Tightening the signal before it cries wolf again.

**Pattern worth preserving:** the fix uses `None` as a sentinel return value (vs `[]`) from `poll_*_tee_times` to distinguish three states — "no work this poll" (`None`), "scraped, found nothing" (`[]`), "scraped, found slots" (non-empty list). This three-state distinction at the data-flow level is cleaner than burying the same logic in conditionals at each call site. Future scrapers should follow the same pattern when alert-driven filtering applies.

**Inbox lookup gotcha (worth recording so future Claude sessions don't repeat it):** silent-failure alerts go to `hello@goodlie.golf` (Google Workspace, accessed via `mail.google.com/mail/u/4` in Dustin's Chrome). His personal inbox at `mail/u/0` (`dustinkeating87@gmail.com`) does NOT receive these. Searching the wrong inbox returns "no results" and is misleading. When investigating ops alerts, navigate to `mail/u/4` explicitly.

**Doc-drift correction — Lakeview is not a separate platform.** Dustin asked why Lakeview was missing from the admin dashboard. Investigation of `scraper_health` jsonb (`{"gtg":11,"golfnow":0,"chronogolf":0}` — no lakeview key) and worker logs (only `[gtg]`, `[golfnow]`, `[chronogolf]` tags, zero `[lakeview]` lines) confirmed Lakeview is a *course* on GolfNow (course key `lakeview`, ID 8409), not a separate platform. All Lakeview alerts fire via the GolfNow scraper. The architecture doc's "Booking platforms" table claimed otherwise, including a "Lakeview Cloudflare 403 known issue" that referenced a `consecutive_zero_polls.lakeview` field that has never existed. Doc corrected: Lakeview row removed from platforms table, known issue #1 withdrawn, failure mode reframed as "GolfNow Cloudflare/proxy block". New known issues #18 (dashboard hardcoding) and #19 (verify whether vestigial Lakeview code exists in `tee_sniper.py`) added. **Meta-lesson: Dustin's question revealed a documentation error that had been carried forward across multiple sessions because no one had verified against runtime behavior. The "verify against this file first" instruction in the doc footer needs a complement: also verify the doc against the runtime when something feels off.**

### 2026-05-03 (morning — alert lifecycle hardening session)

Migration `20260503_alert_lifecycle_and_sent_slots_columns.sql` shipped. Applied to prod via Supabase SQL Editor at ~9:25 AM, committed as `73920c3` on `foreward-api/main`. First properly-committed batched migration; establishes migrations discipline.

**Schema changes:**
- `alert_profiles.status` (text, default `'active'`, CHECK in `active|fired|expired|paused`)
- `sent_slots.user_id` (uuid) — backfilled 65/126 rows; 61 orphans
- `sent_slots.course_name`, `tee_time`, `players`, `taken_at`, `scanned_at`
- Indexes: `alert_profiles_status_active_idx` (partial), `sent_slots_user_id_idx`, `sent_slots_activity_idx` (partial)

**Track 3 close-out:** `20260429_enable_rls_sent_slots.sql` finally committed (`fb13669`). RLS verified live (Advisor zero issues).

**API changes** (commits `e20436f`, `c70af92`):
- `GET /alerts` accepts `?status=`, defaults to `status=active`
- `GET /alerts/history` includes `status` field per row
- `POST /alerts/{id}/retry` — sets `status='active'`
- `GET /activity` — public, 30s cache, 20 most recent ticker rows
- `POST /scraper/expire-alerts` — bulk-marks expired (called by scraper top-of-poll)
- `POST /scraper/fire-alert` — marks fired + invalidates alert cache

**Scraper changes** (commit `c916e1c`):
- Top of poll: calls `POST /scraper/expire-alerts`
- Active alerts filter: `status='active'`
- One-shot firing per alert per poll
- Slot inserts populate `user_id`, `course_name`, `tee_time`, `players`, `scanned_at`
- SMS body: multi-slot variant + single-slot variant; both include "Available as of HH:MM"
- `mark_taken_slots_api()` runs per-platform AFTER productive polls only

**Lovable phase:** dashboard filter, History tab redesign with badges + "Try again" button, homepage activity ticker, region-group pill collapsing 13 GTA courses. Shipped.

**Stripe insight:** investigated 4-customers-but-2-subscriptions discrepancy. Root cause: 2 abandoned Checkout sessions. Logged ClickUp `86ah8ag8y` to enable Stripe's automated recovery emails post-Instagram launch.

### 2026-04-30 (later — activity ticker session)
- Activity ticker (#1 of 3 website improvements) — superseded by 2026-05-03 implementation.
- Take-detection mechanism: piggyback on the existing 60s worker poll. **Implemented 2026-05-03.**

### 2026-04-30
- Created this architecture doc as the canonical source of truth.
- Full scavenge completed.
- Locked product decisions (auto-booking, priority list, per-course config, multi-channel, playing partners).

### 2026-04-29
- RLS migration applied to `sent_slots` (deny-all to anon/authenticated; service role bypasses).

### 2026-04-27
- EZLinks retired as a scraping platform. Coverage moved to GolfNow.

### 2026-04-26
- Scraper health dashboard feature complete.

### 2026-04-25
- @playgoodlie Instagram handle secured.

---

## Open questions / TBDs

- Is `BASE_URL` on the API set to `https://goodlie.golf` or the Railway URL?
- What region is the `web` service on Railway? (Worker is EU West Amsterdam.)
- What's the actual schema of `alerts.json` in `foreward-scraper`?
- What's in `foreward-api/docs/superpowers/plans/` and `foreward/docs/`?
- Once worker healthcheck ships (`86ah8bq8w`), can Railway "Wait for CI" be safely combined with the healthcheck for full deploy gating?
- ~~Why is Lakeview not appearing on the admin Scraper Operations dashboard?~~ ✓ resolved 2026-05-03 PM. Lakeview is a course on the GolfNow platform, not a separate scraping platform. Earlier doc was wrong. Dashboard is correct in not showing a Lakeview card; dashboard IS still wrong about showing EZLinks (retired). Tracked as known issue #18. Possible vestigial code is known issue #19.

---

## How to update this file

1. Anything architectural that changes — schema migration shipped, new env var, new endpoint, brand decision, table renamed, FK added, infra change — gets logged here before session end. Don't rely on memory alone.
2. The decision log at the bottom is chronological. Append new entries with dates; don't overwrite.
3. When a TBD gets resolved, replace it inline AND note it in the decision log.
4. Re-run scavenge if anything feels stale: ask Claude to "re-scavenge Good Lie Golf" and it will re-pull Supabase / Railway / Lovable / GitHub / ClickUp.
5. **If past sessions claimed something is documented but isn't visible here, push back. Verify against this file first.**
6. **Course counts and course inventory belong in `STATE.md`, not here.** `ARCHITECTURE.md` owns platform behavior, rationale, and decisions. `STATE.md` owns facts (how many courses, which courses, which are active). Never write course counts inline in this file.
