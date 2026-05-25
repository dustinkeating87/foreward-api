# Good Lie Golf — SYSTEM (repo mirror)

**ClickUp doc is the source of truth: https://app.clickup.com/90131142261/docs/2ky3r5kn-713**

**If this file disagrees with the ClickUp doc, the ClickUp doc wins.** This mirror exists for in-repo convenience only. Do not edit it by hand — queue updates in ClickUp list `901327295790` and let Claude Code drain them.

---

## Anti-rot rule

Never freeze volatile state as prose here. Schema, pricing, env vars, course lists, deploy config, and live metrics belong in live sources (see Pointers below), not in this file. Write pointers, not snapshots.

---

## Product

Good Lie Golf — tee-time alert service for GTA-area golf courses. Users configure courses + date/time windows + player count + holes, and receive SMS notifications when matching tee times open. The product is the *alert*, not the *booking*.

**Domain:** https://goodlie.golf · **Instagram:** @playgoodlie

### Brand pivot history
1. Tee Sniper (original — scraper module still named `tee_sniper.py`)
2. FOREward / FOREward Tee Times (Lovable project name; GitHub repos: `foreward`, `foreward-api`, `foreward-scraper`)
3. Good Lie Golf (current)

**Naming rule:** "Snipe" is internal-only — never user-facing. Always "alert," "match," or "opening."

### Product model (as of 2026-05-25)

Free tier is LIVE (`FREE_TIER_ENABLED=true` in Railway web service).

**Unsubscribed path:** ONE free alert (`is_free_tier=true` on the alert row). Grace retry: if that alert expires without ever firing an SMS, user gets one additional free alert. After that → 402 Payment Required.

**Paid path:** $9.99 CAD/month Stripe subscription. Up to 10 active alerts. Verify current trial details in `billing.py` and Stripe dashboard.

---

## Stack at a glance

| Layer | Platform | Repo | Where edits happen |
|---|---|---|---|
| Frontend | Lovable → goodlie.golf | `dustinkeating87/foreward` | Lovable AI prompts |
| Backend API | Railway `spirited-youthfulness` / web | `dustinkeating87/foreward-api` (FastAPI) | Claude Code |
| Scraper | Railway `resourceful-delight` / worker (EU West) | `dustinkeating87/foreward-scraper` (Python) | Claude Code |
| Database | Supabase `offtdltmvjfizkoeywei` (Ohio) | Migrations in `foreward-api/supabase/migrations/` | SQL editor + Claude Code |
| SMS | Twilio | foreward-scraper | — |
| Email | SendGrid (primary), SMTP (fallback) | both services | — |
| Billing | Stripe | `foreward-api/app/routers/billing.py` | — |
| Captcha | 2Captcha (GTG Turnstile only) | `foreward-scraper/tee_sniper.py` | — |
| Proxies | Webshare (rotation pool) | `foreward-scraper` | — |
| CI | GitHub Actions parse-check on push | both backend repos | GitHub web UI |
| Backups | Local pg_dump → Google Drive (weekly Sun 10 AM via launchd) | `foreward-api/scripts/backup/` | local Mac |
| Task tracking | ClickUp space `Good Lie Golf` (id `901313780791`) | — | ClickUp connector |

---

## Routing rule for any change

- **Schema change** → numbered SQL file in `foreward-api/supabase/migrations/`, applied via Supabase SQL Editor, committed
- **API endpoint, billing, auth, admin, ops alerting** → `foreward-api` via Claude Code
- **Scraping, polling, SMS sending, alert dedup** → `foreward-scraper` via Claude Code
- **Frontend page, signup flow, dashboard UI** → Lovable prompts written by Claude in chat, pasted by Dustin
- **CI workflow files** → GitHub web UI (local PAT lacks `workflow` scope)

Backend changes do NOT belong in Lovable. Lovable holds only the frontend and one edge function (`course-request`).

---

## Polling cadence

- Base poll loop: **30 seconds** (configurable via `POLL_INTERVAL_SECONDS`)
- GTG loop: **900 seconds / 15 minutes** (configurable via `GTG_POLL_INTERVAL_SECONDS`)
- GolfNow and Chronogolf run at the 30s base tick (pure httpx, no captcha cost)
- GTG runs its own decoupled timer to control 2captcha spend

---

## GTG architecture invariant — DO NOT REINTRODUCE LOGIN

**GTG tee-time data is fully public.** No login, no session, no cookies. Confirmed live 2026-05-24 and in production 2026-05-25 (105 slots, zero auth).

**Implementation:** direct `httpx` GET to `gateway.golfthe6ix.com/Booking/Teetimes` with `CaptchaTokenV3` header (Turnstile token, solved by 2captcha, `action=Booking_Teetimes`). YYZ proxy on gateway calls. One fresh solve per date per poll.

**Do NOT reintroduce login/session/PAT/Playwright.** The "GTG needs login" assumption from April 2026 was wrong and cost weeks. See ClickUp canonical doc for full debugging guidance.

---

## Live sources — query these for current state

| What you want to know | How to find out |
|---|---|
| Current schema | `SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='<name>'` in Supabase SQL Editor |
| Migration history | `ls foreward-api/supabase/migrations/` |
| Open work | ClickUp space `901313780791` |
| Queued doc updates | ClickUp list `901327295790` |
| Railway env vars | `railway variables --service web` (API) or `--service worker` (scraper) |
| FREE_TIER_ENABLED status | `railway variables --service web` in foreward-api |
| 2captcha balance | `scraper_health` table OR 2captcha dashboard |
| Stripe pricing / subscription state | Stripe dashboard OR `SELECT stripe_customer_id, is_active FROM user_profiles` |
| What the scraper is doing | Railway logs for `resourceful-delight` OR `scraper_health.slots_last_poll` jsonb |

**Rule: if a fact about current state is needed, query a live source. Do not infer from this file.**

---

## Failure modes

| Failure | Detection | Recovery |
|---|---|---|
| GTG sitekey rotation | `[gtg] SITEKEY FALLBACK` WARN in logs | Fix live scrape or update hardcoded fallback |
| 2captcha balance exhausted | `scraper_health.captcha_balance` alarm | Top up at 2captcha.com |
| GolfNow/Chronogolf block | consecutive_zero_polls (see note) | Proxy rotation / wait |
| Worker crash | Heartbeat stale | Railway auto-restart |
| API down during fire | Repeated SMS | Manual SQL UPDATE |
| Stripe webhook drops | Manual reconciliation | Stripe retries ~3 days |

**KNOWN-BROKEN: `consecutive_zero_polls`** false-alarms when no active alerts target a platform (alert-driven filtering skips the platform entirely, which resets the counter as if healthy). Full fix in ClickUp ticket 86ahnu41e.

---

## Locked product decisions

| Decision | Date | Rationale |
|---|---|---|
| No auto-booking, ever | 2026-04-30 | Ethical stance + credit-card trust risk |
| No priority list / preferred-time ranking | 2026-04-30 | Doesn't fit alert model |
| "Snipe" is internal-only | 2026-04-30 | Never user-facing |
| EZLinks platform retired | 2026-04-27 | Coverage moved to GolfNow |
| Chronogolf excluded from ALERTING_PLATFORMS | (prior) | No active GTA alerts |
| One-shot alerts (status='fired' after fire) | 2026-05-03 | Avoid spamming users |
| Multi-match folds to one SMS | 2026-05-03 | Multiple slots in one poll = one summary SMS |
| Scraper writes status via API, not direct DB | 2026-05-03 | Centralizes business logic |
| `is_free_tier` is per-alert, not per-user | 2026-05-07 | User can hold paid and free-tier alerts simultaneously |
| `free_tier_used_at` is lifetime once-only | 2026-05-07 | One free-tier opportunity per user, ever |
| GTG data is public — no login needed, ever | 2026-05-24 | Confirmed live |
| GTG uses direct httpx GET + 2captcha CaptchaTokenV3 | 2026-05-25 | Confirmed in production |
| ClickUp doc is source of truth; repo SYSTEM.md is mirror | 2026-05-25 | Prevents doc drift |

---

## Decision log

Append-only. Most recent at top. Updated automatically by Claude Code draining ClickUp list `901327295790`.

### 2026-05-25 — GTG rebuild live; session code retired; docs made canonical

GTG rebuild confirmed in production (105 slots, 3 2captcha solves, ~$0.01 per poll, 15-min cadence). `scripts/mint_gtg_session.py` deleted. SESSION_DIR dead (Railway volume can be detached). Sitekey scrape fixed: JS bundle fetches now go direct (no proxy) — CDN was 502ing the datacenter proxy on static assets. ClickUp doc created as canonical source of truth; SYSTEM.md files rewritten as mirrors; ARCHITECTURE.md in scraper repo stubbed.

### 2026-05-25 — GTG token-reuse confirmed non-reusable; poll interval locked at 900s

Probe (max 6 requests) confirmed each `/Booking/Teetimes` request requires a fresh 2captcha solve. Token reuse returns 400/`400002002`. GTG_POLL_INTERVAL=900 chosen over 600 to hold under $15/mo budget at ≥3 active alert dates; tunable via env var.

### 2026-05-24 — GTG: data is public; proxy IP not burned; Patchright fingerprint was blocker

Live logged-out browser testing confirmed GTG tee-time data is fully public (no login). YYZ proxy IP passes Turnstile fine with a real browser. Patchright automation fingerprint was the actual blocker, not the IP.

### 2026-05-23 — GTG: cf_clearance lasts ~1yr; manual-clearance path explored (now moot)

cf_clearance cookie expiry confirmed ~1 year. Session pivot to cookie-reuse as lead path — superseded by the direct-GET + 2captcha approach confirmed 2026-05-24.

### 2026-05-21 — ARCHITECTURE.md retired; SYSTEM.md format established

Doc drift was causing multi-session knowledge loss. Replaced architecture doc with SYSTEM.md (narrative + pointers, no frozen state). ClickUp queue list created for automated updates.

### 2026-05-09 — Free-tier lifecycle simplified

Migration `20260509_simplify_free_tier.sql` dropped renewal-cycle model (polling_expires_at, renewals_used, expiry_state, final_expired_at). Live model: one free alert + grace retry → pay. Blocks 5-7 spec renewal endpoints that no longer exist.

### 2026-05-07 — Block 3: free-tier alert lifecycle implemented and verified

7 commits, 21 new tests passing. Subsequently simplified 2026-05-09.

### 2026-05-06 — Block 2: phone verification; Block 1: free-tier schema

Phone verification endpoints (send/verify/resend). `phone_verification_codes` table. Free-tier columns added to user_profiles and alert_profiles.

### 2026-05-03 — Alert lifecycle, backups, CI, silent-failure monitoring

Full alert lifecycle, sent_slots schema, scraper expire/fire endpoints, activity ticker, backups, CI. Silent-failure monitoring via consecutive_zero_polls (later identified as false-alarm prone when no alerts target a platform).

### 2026-04-27 — EZLinks retired

Coverage moved to GolfNow.
