# Good Lie Golf — Architecture & Decision Log

**Last verified:** 2026-05-07 (Block 4a: SendGrid Dynamic Templates for free-tier expiry emails)
**Maintained by:** Claude sessions, in collaboration with Dustin
**Read this file at the start of any Good Lie Golf work.** It is the source of truth for how the app is built. ClickUp space `Good Lie Golf` (id `901313780791`) is the source of truth for *open work*. Both must be checked. If you make architectural decisions or learn schema details during a session, update this file before ending the session.

Raw scavenged data lives in `./scavenge-raw/` next to this file. Re-run scavenge if anything below feels stale.

---

## Product

**Good Lie Golf** — tee-time alert service for GTA-area golf courses. Users sign up, configure preferred courses + day/date/time windows + player count + holes, and receive SMS notifications when matching tee times open up. The product is the *alert*, not the *booking*. Booking is left to the user.

**Positioning:** the ethical, golfer-friendly alternative to private auto-booking bots.

**Pricing:** Free-tier first. New users get one free alert on signup with no credit card; paywall presented after the alert fires. Paid tier: $9.99 CAD/month. There is no 7-day trial.
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
| trial_end | timestamptz | YES | — | 7-day free trial expiry |
| phone_verified | boolean | NO | false | Set true on successful 6-digit verification at free-tier signup |
| free_tier_used_at | timestamptz | YES | — | Block 1 (2026-05-07) — set when user first uses free tier; lifetime once-only |
| final_expired_at | timestamptz | YES | — | Block 1 — user-level free-tier final expiry timestamp |
| phone_hash | text | YES | — | Block 2 — SHA-256 hexdigest of E.164 phone (no salt); used for uniqueness check |

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
| is_free_tier | boolean | YES | false | Block 1 (2026-05-07) — true if alert was created under free-tier rules |
| polling_expires_at | timestamptz | YES | — | Block 1 — 14-day polling window for free-tier alerts; NULL for paid |
| renewals_used | integer | YES | 0 | Block 1 — count of free-tier renewals used (0 or 1) |
| expiry_state | text | YES | — | Block 1 — NULL / expired_pending_renewal / final_expired |
| final_expired_at | timestamptz | YES | — | Block 1 — set when alert hits final expiry on free tier |

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
│   └── routers/
│       ├── admin.py            ← /admin/dashboard, /admin/scraper-health, /scraper-heartbeat (now with alarm logic)
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
├── chronogolf_scraper.py       ← excluded from ALERTING_PLATFORMS — no GTA courses
├── ezlinks_scraper.py          ← RETIRED Apr 27, 2026
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
| **GolfNow** | active | no | none | `golfnow_scraper.py` (covers Lakeview, BraeBen, Eagles Nest, Royal Woodbine, Pickering Glen, Winchester, Angus Glen N, Remington Valley, Remington Upper, Flemingdon Park) |
| **Golf The 6ix (GTG)** | active | yes (Cloudflare Turnstile via 2Captcha) | account login (`GTG_EMAIL`/`GTG_PASSWORD`); singular `GTG_ACCOUNT` on worker, plural `GTG_ACCOUNTS` on api — migration in progress | inline in `tee_sniper.py` |
| **EZLinks** | retired 2026-04-27 | — | — | `ezlinks_scraper.py` (kept as dead code) |
| **Chronogolf** | tracked but excluded from ALERTING_PLATFORMS | — | — | `chronogolf_scraper.py` |

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
- **Known limitation:** alarms fire on chronogolf too even though it's excluded from ALERTING_PLATFORMS. Tracked as ClickUp `86ah8btux`.

### Frontend page map (Lovable / `foreward` repo)

| Route | Purpose |
|---|---|
| `/` | Landing — pitch, pricing, "Never miss a tee time" tagline. Activity ticker. Region-group pill listing 13 GTA courses |
| `/signup`, `/login` | Auth flows |
| `/dashboard` | `status='active'` alerts only (filter via `?status=active`) |
| `/alerts/new`, `/alerts/{id}/edit` | Alert criteria CRUD |
| `/alerts/history` | `status='fired'` and `status='expired'` alerts; status badges; "Try again" / "Edit dates" buttons |
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

**No automated paging beyond email.** Email-on-silent-failure is the only auto-alert. Worker healthcheck endpoint planned (ClickUp `86ah8bq8w`).

### Failure modes (umbrella view)

| Failure | What happens | How it's detected | How it recovers |
|---|---|---|---|
| GolfNow Cloudflare/proxy block | GolfNow API returns errors or empty results for ALL courses (not short-circuit) | `consecutive_zero_polls.golfnow` increments on actual failure → **email at 10 polls**. (Distinct from intentional short-circuit where no alerts target GolfNow courses — that resets to 0 per `bc527e3`.) | Webshare proxy rotation / wait it out / contact GolfNow if persistent |
| 2Captcha balance exhausted | GTG captcha solves fail; GTG returns 0 slots | Same signature: streak increments → **email at 10 polls**. (Direct balance check is queued, ClickUp `86ah8bq89`) | Top up account |
| GTG account banned/throttled | GTG scrape fails or returns empty | Same signature as captcha failure | Rotate to backup account |
| Worker crashes | Polling stops entirely | Heartbeat goes stale (no auto-detect; planned: `86ah8bq8w`) | Railway auto-restart per `railway.json` |
| Worker stuck-but-running | Process alive, polls don't complete | Currently undetected. Will be caught by planned `/healthz` endpoint (`86ah8bq8w`) | Manual restart until healthcheck ships |
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
Trial:      Set on signup (user_profiles.trial_end = now() + 7d), not on subscription start
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

| Metric | Value | Notes |
|---|---|---|
| Auth users | 21 | (was 33 in morning; 14 orphans deleted, 2 new signups today) |
| `user_profiles` rows | 21 | Now matches auth.users — orphan gap closed |
| `alert_profiles` total | 16 | (was 17; one orphan deleted with its owner) |
| `alert_profiles` `status='active'` | 2 | |
| `alert_profiles` `status='fired'` | **7** | **Up from 0 this morning — alert lifecycle code firing in production** |
| `alert_profiles` `status='expired'` | 7 | |
| `alert_profiles` `status='paused'` | 0 | |
| `sent_slots` total | 122 | (was 126; 4 orphan rows deleted) |
| `sent_slots` with `user_id` | 61 | |
| `sent_slots` orphan (`user_id IS NULL`) | 61 | Pre-launch test alerts; harmless. Optional cleanup deferred. |
| Stripe-subscribed users | 2 | |
| Stripe-customer-only (abandoned) | 2 | |
| `invite_codes` total | 60 | |
| 2Captcha balance | $18.72 | ~18 days runway at current burn ($1/day). Top up before $10. |

---

## API surface (foreward-api endpoints)

```
Auth
  POST   /auth/signup
  POST   /auth/signup-free-tier         ← FREE_TIER_ENABLED gate; consumes verification_token, creates auth user with tier=free
  POST   /auth/login
  GET    /auth/me
  POST   /auth/send-verification-code   ← FREE_TIER_ENABLED gate; Twilio Lookup + IP rate limit + phone dedupe + SMS send
  POST   /auth/verify-phone             ← FREE_TIER_ENABLED gate; validates OTP, returns verification_token (consumed by /auth/signup-free-tier)
  POST   /auth/resend-verification-code ← FREE_TIER_ENABLED gate; 60s cooldown, max 3 resends per code

Alerts (user-facing)
  POST   /alerts
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
- 17 service env vars: `GTG_EMAIL`, `GTG_PASSWORD`, `CAPTCHA_API_KEY`, `ALERTS_API_URL`, `ALERTS_API_KEY`, `GTG_ACCOUNT`, `POLL_INTERVAL_SECONDS`, `PROXY_URL`, `PROXY_URLS`, `SENDGRID_API_KEY`, `SMTP_*`, `TWILIO_*`

### Railway: `spirited-youthfulness` (web/API)
- Project ID: `7c8fa4ed-d992-4f5d-a78b-907ed5fd4e44`
- Service: `web` (id `0aa1761e-7bd3-4d72-9877-0968a14f5974`)
- Public URL: `https://web-production-b24db.up.railway.app`
- 24 service env vars (added 2026-05-03: `ALARM_THRESHOLD_POLLS=10`, `ALARM_EMAIL_TO=hello@goodlie.golf`, `ALARM_EMAIL_FROM=hello@goodlie.golf`; added 2026-05-07: `SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_1`, `SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_2`, `SENDGRID_TEMPLATE_FREE_TIER_EXPIRY_3`)

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
| Chronogolf module excluded from ALERTING_PLATFORMS | (prior) | No active alerts in GTA |
| One-shot alerts (status='fired' after fire) | 2026-05-03 | Avoid spamming users with repeated SMS for same alert. User-initiated re-fire via "Try again." |
| Multi-match folds to one SMS | 2026-05-03 | If a poll detects multiple matching slots for one alert, all fold into one summary SMS. |
| Auto-expiry per-poll, no cron | 2026-05-03 | Scraper calls `POST /scraper/expire-alerts` at top of each poll. Matches "intentionally simple." |
| "Try again" semantics: re-activate only | 2026-05-03 | Does not clear sent_slots rows. Future *new* matches will fire; previously-sent slots won't re-fire. |
| Scraper writes status via API, not direct DB | 2026-05-03 | Centralizes business logic. Trades one network hop per poll for testability + future audit. |
| **Backup retention 28 days** | **2026-05-03** | **Sufficient given quarterly test cadence; minimizes Drive bloat.** |
| **Silent-failure alerts: API-side, transition-only** | **2026-05-03** | **No state column needed. Implicit comparison of prev/new. Failures swallowed — never break heartbeat.** |
| **DB password is alphanumeric only** | **2026-05-03** | **Avoids URL-encoding issues across shells, scripts, and connection-string parsers.** |

---

## Known issues / things to watch

1. ~~Lakeview Cloudflare 403~~ ✗ **withdrawn 2026-05-03 PM.** Earlier doc claimed Lakeview had its own scraper with a Cloudflare 403 issue. Runtime evidence (worker logs, scraper_health jsonb) shows no `[lakeview]` platform tag and no separate Lakeview scraper running. Lakeview is a *course* on the GolfNow platform. Possibly vestigial code in `tee_sniper.py` from an earlier architecture; needs verification (see #18 below).
2. ~~`sent_slots` missing `user_id`~~ ✓ closed 2026-05-03 (column added).
3. ~~`auth.users` ↔ `user_profiles` gap~~ ✓ closed 2026-05-03 afternoon (14 orphans deleted).
4. ~~Migration system not in use~~ ✓ closed 2026-05-03 (in use, 2 files committed).
5. ~~No Supabase backups configured~~ ✓ closed 2026-05-03 afternoon (weekly local pg_dump → Google Drive).
6. **No worker healthcheck endpoint** — Railway can't auto-detect stuck-but-running worker. Spec ready (ClickUp `86ah8bq8w`).
7. **`GTG_ACCOUNT` (singular) on worker vs `GTG_ACCOUNTS` (plural) on API** — multi-account migration half-done.
8. ~~README in `foreward-api` still says "Tee Sniper API"~~ ✓ closed 2026-05-08. README was already updated; tracking entry retroactively closed.
9. **2Captcha balance has no auto-monitoring** — silent failure mode if balance hits zero. Spec ready (ClickUp `86ah8bq89`). Current balance $18.72 (~18 days).
10. **Meta ad account trust issues** affecting parent operator's brands.
11. **Scraper writes status via API endpoints, not direct Supabase.** If alerts get stuck in `active` despite firing, check API logs first.
12. **61 orphan rows in `sent_slots`** (`user_id IS NULL`) from pre-launch test alerts. Harmless. Optional cleanup deferred.
13. **Silent-failure alerts fire for chronogolf** even though it's excluded from ALERTING_PLATFORMS. Tracked as ClickUp `86ah8btux`.
14. **Backups not yet end-to-end tested.** First quarterly restore test due 2026-08-03 (ClickUp `86ah8bnjk`). Until then, treat backups as unverified.
15. **GitHub PAT lacks `workflow` scope** — workflow file edits must use GitHub web UI until PAT is updated.
16. **Railway "Wait for CI" toggle off** on both services. CI is advisory until enabled. Both workflows passing reliably as of 2026-05-03.
17. ~~GolfNow returning 0 slots persistently~~ ✓ **resolved 2026-05-03 PM, verified in production.** Was a false alarm. Root cause: the alert-driven filtering optimization (scrapers only fetch courses with at least one active user alert) makes platforms return 0 slots when no active alerts target their courses. The `consecutive_zero_polls` counter didn't distinguish "scraped → got 0" from "didn't scrape". Fundamentally incompatible with natural alert lifecycle churn. **Fix shipped (commit `bc527e3`):** `poll_golfnow_tee_times` and `poll_chronogolf_tee_times` return `None` instead of `[]` when short-circuiting; two call sites in `tee_sniper.py` detect `None` and reset the counter to 0 instead of incrementing. Real failures (HTTP 403, timeouts, exceptions inside `fetch_one`, captcha exhaustion) still return a list (possibly `[]`) and increment normally. Verified post-deploy: GolfNow 0/0, Chronogolf 0/0, dashboard Healthy. **Lesson learned:** the silent-failure alert system did its job — it surfaced a real measurement problem, just not the one we initially thought. The morning's 11:57 AM "test" alarm was likely also a false positive on the same root cause.

18. **Admin dashboard hardcodes platform cards** as `[GTG, GolfNow, EZLinks, Chronogolf]`. EZLinks is retired but still rendered. Should be data-driven from `scraper_health.slots_last_poll` jsonb keys instead. Cosmetic — fix in Lovable when convenient.

20. **ARCHITECTURE.md was lost from local filesystem on 2026-05-06 and recovered from Cowork project knowledge (2026-05-03 baseline). Recent updates between 2026-05-03 and 2026-05-06 (2Captcha balance auto-alert, ClickUp/doc reconciliation, By-request picker confirmation, alert form defaults patches) need to be re-derived from closed ClickUp tickets — tracked in ticket 86ahb0m91.**

19. **Possible vestigial Lakeview code in `tee_sniper.py`.** Earlier versions of this doc described an inline Lakeview scraper with cookie refresh / Cloudflare 403 handling. No `[lakeview]` log lines fire at runtime, so the code (if it exists) isn't called from the main poll loop. Next session: `grep -ri lakeview ~/foreward-scraper/`. If dead code, delete. If reachable but unwired, decide whether to revive (Lakeview-direct gives richer data than GolfNow proxy) or consolidate on GolfNow path.

21. **Local Python 3.9.6 vs Railway Python 3.11 — `fromisoformat` drift.** Python 3.9's `datetime.fromisoformat` rejects timestamps with non-6-digit fractional seconds (e.g. 5-digit microseconds). Supabase/PostgREST can return any precision. Railway runs 3.11 (full ISO 8601 support) so prod is unaffected, but local runs can crash. The fix pattern is `_parse_iso()` in `app/routers/phone_verification.py` (added Block 2): normalize fractional seconds to 6 digits with a regex before calling `fromisoformat`. Three out-of-scope call sites still use the raw pattern: `heartbeat_monitor.py:30`, `routers/auth.py:93`, `routers/admin.py:147` — tracked in ClickUp `86ahbacxw`.

22. **Supabase SQL editor shows "0 rows" for UPDATE without RETURNING.** The editor reports "0 rows" for any DML statement that doesn't include a `RETURNING` clause, regardless of how many rows were actually affected. Always append `RETURNING id` (or similar) when row count matters during a test or migration verify.

23. **Free-tier first_name fallback is hardcoded to "there"** in expiry email templates. `user_profiles` has no first_name column. Acceptable for launch since most users won't notice "Hey there," in a transactional email. Worth fixing once free-tier flows have real user data.

24. **`COURSE_DISPLAY_NAMES` dict in `app/util/courses.py` is hardcoded** and won't reflect upstream renames automatically. Scraper fetches canonical names from external APIs at runtime (`sent_slots.course_name`); the dict is for email/SMS copy where no `sent_slots` row exists yet. Reconcile against scraper's runtime names ~quarterly.

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

**Marketing & Launch**
- 🟠 `86ah69yrf` — Instagram content kit for `@playgoodlie`
- 🔵 `86ah69ytx` — OG image upgrade
- ⚪ `86ah69yw6` — Meta reclaim attempt for `@goodliegolf`
- ⚪ `86ah8ag8y` — Enable Stripe abandoned-checkout recovery emails
- 🔵 `86ahc027p` — Bug: /auth/signup-free-tier returns identical 401 for three distinct failure modes (subtask of master `86ahavm5n`)
- 🔵 `86ahc02dc` — Bug: /auth/send-verification-code has no phone-ownership check (subtask of master `86ahavm5n`)

🔴 urgent · 🟠 high · 🔵 normal · ⚪ low

---

## Decision log

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

**Python 3.9 / Railway 3.11 patch:** `app/routers/phone_verification.py` has a `_parse_iso()` helper (added this session) that normalizes fractional seconds to 6 digits before calling `fromisoformat`. Applies at the three Supabase timestamp reads (lines 156, 202, 216). Required because Python 3.9 `fromisoformat` rejects non-6-digit microseconds and Supabase/PostgREST can return any precision. Railway runs Python 3.11 — prod unaffected. Three out-of-scope call sites (`heartbeat_monitor.py:30`, `routers/auth.py:93`, `routers/admin.py:147`) remain unpatched; tracked in ClickUp `86ahbacxw`.

ClickUp `86ahaza0k` closed.

### 2026-05-06 (Block 1 — free-tier schema foundation)

Migration `20260506_add_free_tier_columns.sql` applied to prod via Supabase SQL Editor, committed to `foreward-api/supabase/migrations/`. Adds 5 columns to `alert_profiles` (`is_free_tier`, `polling_expires_at`, `renewals_used`, `final_expired_at`, `expiry_state` with CHECK constraint) and 4 columns to `user_profiles` (`phone_verified`, `phone_hash`, `free_tier_used_at`, `final_expired_at`). Two partial indexes: `ix_user_profiles_phone_hash_free_tier` (unique on `phone_hash WHERE free_tier_used_at IS NOT NULL`) and `ix_alert_profiles_polling_expires_at_free_tier` (btree on `polling_expires_at WHERE is_free_tier = true AND expiry_state IS NULL`). `FREE_TIER_ENABLED=false` added to Railway `web` service — all free-tier branches gated on this flag; no behavior change in production until Block 9 flips it to true. No existing paid alerts affected (all new columns null/default). ClickUp `86ahaz9e0` closed. ARCHITECTURE.md moved into `foreward-api/docs/` and committed — previously unversioned and stored in Cowork only. Doc drift from 2026-05-03→2026-05-06 (2Captcha balance auto-alert, ClickUp/doc reconciliation, By-request picker confirmation, alert form defaults patches) tracked in ticket 86ahb0m91.

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
