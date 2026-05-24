# Good Lie Golf — SYSTEM

**This file is the stable map of how Good Lie is built — repos, routing rules, locked decisions, and the chronological decision log.**

**This file is NOT a snapshot of current state.** Schema, env vars, runtime state, and open work all live elsewhere (see "Live sources" below). If you want to know what's true right now, query the source — do not trust this file for stateful facts.

**Maintained by:** Claude Code, automatically, by draining the ClickUp "SYSTEM.md updates queued" list (id `901327295790`) at session start. Dustin does not edit this file.

---

## Product

Good Lie Golf — tee-time alert service for GTA-area golf courses. Users configure preferred courses + day/date/time windows + player count + holes, and receive SMS notifications when matching tee times open up. The product is the *alert*, not the *booking*.

Domain: https://goodlie.golf · Instagram: @playgoodlie · Pricing: $9.99 CAD/mo

### Brand pivot history
1. Tee Sniper (original — scraper module still named `tee_sniper.py`)
2. FOREward / FOREward Tee Times (Lovable project name; GitHub repo names: `foreward`, `foreward-api`, `foreward-scraper`)
3. Good Lie Golf (current)

"Snipe" is internal-only — never user-facing. Always "alert," "match," or "opening."

---

## Stack at a glance

| Layer | Platform | Repo | Where edits happen |
|---|---|---|---|
| Frontend | Lovable → `goodlie.golf` | `dustinkeating87/foreward` | Lovable AI prompts |
| Backend API | Railway `spirited-youthfulness` / web | `dustinkeating87/foreward-api` (FastAPI) | Claude Code |
| Scraper | Railway `resourceful-delight` / worker (EU West) | `dustinkeating87/foreward-scraper` (Python) | Claude Code |
| Database | Supabase `offtdltmvjfizkoeywei` (Ohio, t4g.nano) | Migrations in `foreward-api/supabase/migrations/` | SQL editor + Claude Code |
| SMS | Twilio | called from `foreward-scraper` | — |
| Email | SendGrid (primary), SMTP (fallback) | both services | — |
| Billing | Stripe ($9.99 CAD/mo, 7-day trial) | `foreward-api/app/routers/billing.py` | — |
| Captcha | 2Captcha (GTG Turnstile) | `foreward-scraper` | — |
| Proxies | Webshare (20-IP rotation) | `foreward-scraper` | — |
| CI | GitHub Actions parse-check on push | both backend repos | GitHub web UI |
| Backups | Local pg_dump → Google Drive (weekly Sun 10 AM via launchd) | `foreward-api/scripts/backup/` | local Mac |
| Task tracking | ClickUp space `Good Lie Golf` (id `901313780791`) | — | ClickUp connector |

---

## Routing rule for any change

- **Schema change** → numbered SQL file in `foreward-api/supabase/migrations/`, applied via Supabase SQL Editor, committed
- **API endpoint, billing, auth, admin, ops alerting** → `foreward-api` via Claude Code
- **Scraping, polling, SMS sending, alert dedupe** → `foreward-scraper` via Claude Code
- **Frontend page, signup flow, dashboard, ticker UI** → Lovable prompts written by Claude in chat, pasted by Dustin
- **Verification / planning / content / brand work** → Cowork (chat)
- **CI workflow files** (`.github/workflows/*`) → GitHub web UI if local PAT lacks `workflow` scope

Backend changes do NOT belong in Lovable. Lovable holds only the frontend and one edge function (`course-request`).

---

## Live sources — query these for current state

| What you want to know | How to find out |
|---|---|
| Current schema (any table) | `SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_schema='public' AND table_name='<name>'` in Supabase SQL Editor |
| Migration history | `ls foreward-api/supabase/migrations/` |
| Open work | ClickUp space `901313780791`, filter by list (Backend & Infra `901327040517`, Frontend & UX `901327040524`, Scrapers & Data `901327040519`, Marketing & Launch `901327040532`) |
| Queued doc updates | ClickUp list `901327295790` ("SYSTEM.md updates queued") |
| Current Railway env vars | Railway dashboard → service → Variables, OR `railway variables` CLI on the relevant service |
| Current `FREE_TIER_ENABLED` value | `railway variables --service web` in `foreward-api` |
| Current 2Captcha balance | `scraper_health` table OR 2Captcha dashboard |
| What the scraper is doing right now | Railway logs for `resourceful-delight` worker OR `scraper_health.slots_last_poll` jsonb |
| Auth users count, alert counts, sent_slots counts | live SQL on Supabase — never trust a number written in this doc |
| Current API surface | source: `foreward-api/app/routers/` |
| Current scraper booking platforms | source: `foreward-scraper/tee_sniper.py` ALERTING_PLATFORMS constant |
| What a specific endpoint does | source: the relevant router file |
| Stripe subscription state | Stripe dashboard OR `SELECT stripe_customer_id, stripe_subscription_id, is_active FROM user_profiles` |

**Rule: if a fact about current state is needed, query a live source. Do not infer from this file.**

---

## How it works (conceptual — rarely changes)

### Request lifecycle: signup through first SMS

1. User visits goodlie.golf → Lovable serves React/TS app
2. POST /auth/signup → foreward-api → Supabase auth.users → `handle_new_user` trigger fires → row in `user_profiles` with `trial_end = now()+7d`
3. POST /auth/login → JWT issued
4. POST /alerts → INSERT `alert_profiles` (status='active')
5. Worker polls every 60s: expire stale alerts, load active alerts, scrape enabled platforms, fold matches into one SMS per alert, mark alert `status='fired'`, dedupe via `sent_slots` unique index
6. User receives SMS within ~60-90s of slot becoming available
7. User books on the course's own platform — Good Lie does not book
8. User clicks "Try again" on /alerts/history → POST /alerts/{id}/retry → status='active' again, eligible to fire on new slots only

### Data flow

### Auth model

Current: service role + app-level filtering. Target: anon Supabase client + user JWT + RLS. RLS already enabled on every public table; `sent_slots` is deny-all for anon/authenticated, service role bypasses. Migration to JWT+RLS is in flight, tracked in ClickUp.

### Stripe lifecycle

Trial set on signup (`user_profiles.trial_end = now()+7d`), not on subscription start. Checkout via `/create-checkout-session`. Webhook at `/webhooks/stripe` handles `customer.subscription.{created,updated,deleted}` and `invoice.payment_failed`. Pricing: single `STRIPE_PRICE_ID` at $9.99 CAD/month.

### Failure modes umbrella

| Failure | Detection | Recovery |
|---|---|---|
| GolfNow Cloudflare/proxy block | `consecutive_zero_polls.golfnow` ≥ threshold → email | proxy rotation / wait / contact GolfNow |
| 2Captcha balance exhausted | same signature as above | top up |
| GTG account banned/throttled | same signature | rotate to backup account |
| Worker crash | heartbeat stale (no auto-detect yet) | Railway auto-restart |
| API down during a fire | repeated SMS to same user | manual SQL UPDATE if it happens |
| Stripe webhook drops | manual reconciliation | Stripe retries ~3 days |
| Supabase outage / data loss | everything stops / RESTORE.md | up to 7 days RPO |

The system is intentionally simple — no queues, no replicas, no failovers. Acceptable trade at current scale; flag for revisit when paying customers cross ~50 or alert volume crosses ~500/day.

---

## Locked product decisions

Append-only table. Each row is a decision that future sessions should not re-litigate.

| Decision | Date | Rationale |
|---|---|---|
| No auto-booking, ever | 2026-04-30 | Ethical stance + credit-card trust risk + bot-protection arms race. Forum-validated. |
| No priority list / preferred-time ranking | 2026-04-30 | Doesn't fit alert model — we alert on a range, not a specific time |
| No per-course release schedule as user-config | 2026-04-30 | App-config, not user-config |
| No multi-channel notifications (push/email) yet | 2026-04-30 | SMS is enough for MVP |
| No playing partners as first-class objects | 2026-04-30 | Not relevant for alerts-only tool |
| "Snipe" is internal-only — never user-facing | 2026-04-30 | Inherited from Tee Sniper branding |
| EZLinks platform retired | 2026-04-27 | Coverage moved to GolfNow |
| Chronogolf excluded from ALERTING_PLATFORMS | (prior) | No active alerts in GTA |
| One-shot alerts (status='fired' after fire) | 2026-05-03 | Avoid spamming users |
| Multi-match folds to one SMS | 2026-05-03 | Multiple matching slots in one poll = one summary SMS |
| Auto-expiry per-poll, no cron | 2026-05-03 | Scraper calls /scraper/expire-alerts top-of-poll |
| "Try again" re-activates only, does not clear sent_slots | 2026-05-03 | Future new matches fire; previously-sent slots don't re-fire |
| Scraper writes status via API, not direct DB | 2026-05-03 | Centralizes business logic |
| Backup retention 28 days | 2026-05-03 | Quarterly test cadence |
| Silent-failure alerts: API-side, transition-only | 2026-05-03 | No state column; implicit prev/new comparison |
| DB password is alphanumeric only | 2026-05-03 | Avoids URL-encoding issues |
| `is_free_tier` is per-alert, not per-user | 2026-05-07 | User can hold paid and free-tier alerts simultaneously |
| Free-tier `free_tier_used_at` on `user_profiles` is lifetime once-only | 2026-05-07 | One free-tier alert per user, ever |
| Two expiry mechanisms (60s scraper sweep + 5min in-process loop) acceptable | 2026-05-07 | Loop wins on state because it updates after; benign race |
| **ARCHITECTURE.md format retired; replaced by SYSTEM.md + queued updates** | **2026-05-21** | **Doc drift was eating sessions. New rule: stateful facts come from live sources, narrative comes from this file, updates are queued in ClickUp and drained by Claude Code automatically.** |

---

## Decision log

Append-only. Chronological. Most recent at top.

Updates to this section happen via the ClickUp queue (list `901327295790`), drained by Claude Code at session start. Do not edit by hand.

Bar for an entry: **something actioned changed in the world.** Code shipped, config flipped, schema migrated, bug filed, locked-in commitment made. Pure deliberation does not get logged.

### 2026-05-23 (s2) — GTG: cf_clearance lasts ~1yr; manual-clearance + cookie-reuse is lead path

Continuation of GTG PAT investigation (ClickUp 86ahnnyda full record, 86ahnpnt4 full record). GTG cold-start login blocked at Cloudflare PAT device attestation; multiple approaches confirmed-closed (PAT-passing via Chromium, token injection, window.turnstile reach-in, postMessage forge, DOM side channels — see 86ahnnyda, do not re-attempt). This session pivoted to cookie reuse as the lead path.

Key findings from direct DevTools observation:
- Manual real Safari passes the Cloudflare/Turnstile wall trivially (auto-pass, no interaction).
- Manual Chrome ALSO currently holds a logged-in GTG session — contradicts the prior "Chrome always gets 401" framing; flagged unresolved (may have logged in during a working window or session predates May redeploy).
- Automated Safari (safaridriver) did NOT pass in 2 attempts, but BOTH runs were inconclusive due to probe timing bugs (script checked for the Turnstile iframe before the Angular SPA rendered it). Do NOT record "automated Safari fails" as fact.
- cf_clearance cookie expires 2027-05-21 — ~ONE YEAR. Overturns the prior "GTG sessions expire fast" assumption. Once a human clears Turnstile, the Cloudflare gate stays open ~1yr on that browser/IP/UA.
- No app auth token in localStorage (only app state/prefs). GTG login lives in an HttpOnly cookie or IndexedDB/Session storage — not yet located.

Revised lead hypothesis: worker's production failure = missing cf_clearance (the /pat/ 401 is the Cloudflare gate, not the app login). Hand the worker a valid cf_clearance → it may pass the gate → then log in with GTG creds it already has. Cost ~$0, re-paste ~1x/year. Critical untested risk: cf_clearance is IP+UA-bound; cookie minted on Dustin's home IP may be rejected from worker's proxy/datacenter egress. Next action: test cf_clearance transfer in foreward-scraper.

Paid options ruled out at current user count: cloud-Mac ($60–150/mo) and managed unblockers ($30–130/mo) exceed <$15/mo ceiling. GTG is non-negotiable for the product (5 flagship courses). Manual touch tolerance: a few min every few days.

Tooling lesson: Claude Code introduced a Py3.10+ syntax regression mid-session (tuple|None syntax on Python 3.9). Fixed via `from __future__ import annotations`. Code to smoke-test imports before handback going forward.

### 2026-05-21 — Process gap filed: stateful work done outside chat sessions is invisible

Filed ClickUp 86ahmctj5. 80+ courses were added to the scraper across multiple sessions between late April and May 21 without generating a chat session or decision-log entry. Result: Claude confidently cited "22 courses" while the actual number was ~106. Problem: the session-start protocol has no mechanism to surface deltas from work done outside chat. Options: (a) live Supabase query for course count at session start when marketing/coverage claims are involved; (b) "what's happened since last chat" delta step surfacing commits, new courses, env vars; (c) other. Not fixing today — to be addressed in a planning session when there's bandwidth for process work.

### 2026-05-21 — foreward CLAUDE.md pointer: needs update to SYSTEM.md (deferred)

The foreward (Lovable frontend) repo's CLAUDE.md referenced the stale `~/Documents/Claude/Projects/Good Lie Golf/ARCHITECTURE.md` path. Intent (queued as 86ahma82e): update foreward/CLAUDE.md to point to the canonical SYSTEM.md GitHub raw URL. At drain time (2026-05-24) no CLAUDE.md was found in foreward-frontend/ — the edit was never done and the file doesn't exist. To resolve: create a CLAUDE.md in the foreward-frontend repo pointing to the SYSTEM.md raw URL. Lesson: cross-repo doc pointers are a hidden drift surface; always use GitHub raw URLs, not local filesystem paths.

### 2026-05-21 — SYSTEM.md surgery: ARCHITECTURE.md format retired

Replaced ARCHITECTURE.md (~600 lines, accumulated 18 days of state-drift across multiple sessions) with this SYSTEM.md (~250 lines). Removed: full schema dump, per-service env var lists, "live state" snapshots, API surface enumeration, "outstanding ClickUp tasks" snapshot, "known issues" list. Kept: brand history, stack table, routing rule, conceptual data flow, failure modes umbrella, locked product decisions, decision log.

New mechanism: ClickUp list "SYSTEM.md updates queued" (id `901327295790`) inside Good Lie space. Chat sessions write decision-log entries as new tasks in that list. Claude Code, at session start in any Good Lie repo, drains the queue into this file, commits, pushes, closes the tickets. Dustin does not edit this file. System-prompt working rules updated to match.

Lesson: a markdown file trying to mirror stateful systems will always drift. Stateful facts belong in queries against live sources. Markdown is for narrative and locked-in decisions.

### 2026-05-07 — Block 3: free-tier alert lifecycle (verified)

Block 3 implementation complete and verified in production. 7 commits (b108f76..13d2bde) on foreward-api/main, 21 new tests passing (29 total). Verification script scripts/verify_block_3.py (gitignored) confirmed AC1 (paid no-regression) and AC7 (expiry sweep) PASS against deployed Railway API. Plan doc: foreward-api/docs/superpowers/plans/2026-05-07-block-3-free-tier-alert-lifecycle.md. Master ticket 86ahavm5n. Block 3 ticket 86ahazaza.

Schema documentation drift caught and corrected. Block 1 (earlier session) added columns to alert_profiles and user_profiles but did not update the doc. Lesson: every Block must end with a doc update before close.

Key architectural decisions:
- is_free_tier is per-ALERT (alert_profiles), not per-user. A user can hold paid and free-tier alerts simultaneously. free_tier_used_at on user_profiles is the lifetime once-only flag.
- Two expiry mechanisms run independently:
  - Scraper-driven POST /scraper/expire-alerts (60s cadence, date-based, sets status='expired')
  - In-process free_tier_expiry_loop (5min cadence, polling-window based, transitions expiry_state, sends emails, generates Stripe coupons)
  - These can race on overlapping rows. Loop wins on state because it updates after. Benign.
- Railway sleepApplication: false confirmed via Railway API for spirited-youthfulness web service. In-process loop is safe.
- free_tier_expiry_loop updates BOTH status='expired' AND expiry_state='expired_pending_renewal' on first transition (verified 2026-05-07).
- New endpoint GET /courses/available-for-free-tier returns {courses, count, available} (NOT bare []) gated behind FREE_TIER_ENABLED env var.
- FREE_TIER_ENABLED kill switch: rejects free-tier paths everywhere, not just /courses.
- Free tier lifecycle: 14-day initial polling window, up to 2 renewals via Stripe coupon (3 polling windows total, 42 days max alert lifetime), then final_expired.

Bugs identified during verification (filed as ClickUp tickets under master 86ahavm5n): 86ahbkw2n (renewals copy mismatch), 86ahbkw5h (dashboard toggle reads legacy active column), 86ahbkwf6 (Lovable signup wall blocking free tier), 86ahbkwka (course names vs slugs), 86ahbkx68 (pre-launch checklist).

### 2026-05-06 — Block 2: phone verification endpoints

Three new endpoints added to foreward-api under /auth/: send-verification-code, verify-phone, resend-verification-code. All gated by FREE_TIER_ENABLED=false — return 503 in production until Block 9 flips the flag.

New files: app/util/phone.py (SHA-256 hashing, E.164 validation), app/twilio_lookup.py (Twilio Lookup v2 wrapper with in-memory cache), app/ip_rate_limit.py (midnight-UTC IP counter on app.state), app/routers/phone_verification.py (3 endpoints). New unit tests in tests/test_phone_util.py (8 tests, all passing).

New DB table: phone_verification_codes — migration file committed.

Verification token design: on successful verify-phone, a URL-safe UUID token is stored on the phone_verification_codes row and returned to the client. Block 5 (Lovable signup flow) will submit this token to prove phone was verified before account creation.

AC verification results: AC1 (503 guard, prod), AC2 (happy path), AC3 (IP rate limit), AC5 fast-path (resend cooldown), AC6 (single-use + expiry) all PASS. AC4 (phone uniqueness) and AC5 max-3 cap deferred to code-review-only. AC5 spec gap: first resend has no cooldown — last_resend_at is NULL on row creation, so the 60s check is bypassed on the first resend. Cooldown only applies resend→resend. Flagged for Block 5 fix.

Python 3.9 / Railway 3.11 patch: app/routers/phone_verification.py has a _parse_iso() helper (added this session) that normalizes fractional seconds to 6 digits before calling fromisoformat. Required because Python 3.9 fromisoformat rejects non-6-digit microseconds and Supabase/PostgREST can return any precision. Railway runs Python 3.11 — prod unaffected. Three out-of-scope call sites (heartbeat_monitor.py:30, routers/auth.py:93, routers/admin.py:147) remain unpatched; tracked in ClickUp 86ahbacxw.

### 2026-05-06 — Block 1: free-tier schema foundation

Migration 20260506_add_free_tier_columns.sql applied to prod via Supabase SQL Editor, committed to foreward-api/supabase/migrations/. Adds 5 columns to alert_profiles (is_free_tier, polling_expires_at, renewals_used, final_expired_at, expiry_state with CHECK constraint) and 4 columns to user_profiles (phone_verified, phone_hash, free_tier_used_at, final_expired_at). Two partial indexes: ix_user_profiles_phone_hash_free_tier (unique on phone_hash WHERE free_tier_used_at IS NOT NULL) and ix_alert_profiles_polling_expires_at_free_tier (btree on polling_expires_at WHERE is_free_tier = true AND expiry_state IS NULL).

FREE_TIER_ENABLED=false added to Railway web service — all free-tier branches gated on this flag; no behavior change in production until Block 9 flips it to true. No existing paid alerts affected (all new columns null/default).

ARCHITECTURE.md moved into foreward-api/docs/ and committed — previously unversioned and stored in Cowork only.

### 2026-05-03 (afternoon) — backups, alerts, CI, cleanup session

Backups: Set up weekly Postgres backups via local Mac pg_dump driver + launchd schedule + Google Drive sync. Restore runbook committed at foreward-api/scripts/backup/RESTORE.md. Quarterly test reminder logged (ClickUp 86ah8bnjk). DB password reset to alphanumeric (avoids URL-encoding issues).

Orphan auth.users cleanup: Deleted 14 orphan auth.users (test/dev accounts from launch testing) plus their dependents. Discovered along the way that 4 FK constraints exist between public and auth.users (alert_profiles CASCADE, course_requests SET NULL, user_profiles CASCADE, invite_codes NO ACTION) — previous version of the doc claimed there were none.

CI parse-check on both repos: Added GitHub Actions workflow to foreward-api and foreward-scraper. Each runs pip install then python -m compileall on the source tree. Committed via GitHub web UI because local PAT lacks workflow scope.

Silent-failure email alerts (commit 337c048, closes ClickUp 86ah8bnxv): New module app/email.py — thin httpx wrapper around SendGrid /v3/mail/send. /scraper-heartbeat reads prev consecutive_zero_polls BEFORE upserting, compares per-platform, fires alarm email when prev < threshold AND new >= threshold, recovery email when prev >= threshold AND new == 0. New env vars on Railway web: ALARM_THRESHOLD_POLLS=10, ALARM_EMAIL_TO=hello@goodlie.golf, ALARM_EMAIL_FROM=hello@goodlie.golf. Email failures wrapped in try/except — never break the heartbeat. First real-world catch (PM): GolfNow went silent for 101 polls. Detection works.

GolfNow false-alarm investigation (late afternoon): Admin dashboard showed GolfNow alarming (101 zero polls). Root cause: alert-driven filtering optimization (scrapers only fetch courses with matching active alerts) makes platforms return 0 slots when no active alerts target their courses. The consecutive_zero_polls counter didn't distinguish "scraped → got 0" from "didn't scrape". Fix shipped (commit bc527e3): poll_golfnow_tee_times and poll_chronogolf_tee_times return None instead of [] when short-circuiting; two call sites in tee_sniper.py detect None and reset the counter to 0 instead of incrementing. Real failures (HTTP 403, timeouts, exceptions inside fetch_one, captcha exhaustion) still return a list (possibly []) and increment normally. Verified post-deploy: GolfNow 0/0, Chronogolf 0/0, dashboard Healthy.

Meta-lesson: the silent-failure alert infrastructure worked correctly — it surfaced a real measurement bug. But "first time it fired" being a false positive is a credibility hit. Tightening the signal before it cries wolf again.

Pattern worth preserving: the fix uses None as a sentinel return value (vs []) from poll_*_tee_times to distinguish three states — "no work this poll" (None), "scraped, found nothing" ([]), "scraped, found slots" (non-empty list). This three-state distinction at the data-flow level is cleaner than burying the same logic in conditionals at each call site.

Doc-drift correction — Lakeview is not a separate platform. Dustin asked why Lakeview was missing from the admin dashboard. Investigation of scraper_health jsonb and worker logs confirmed Lakeview is a course on GolfNow (course key lakeview, ID 8409), not a separate platform. The architecture doc's "Booking platforms" table claimed otherwise. Meta-lesson: documentation error carried forward across multiple sessions because no one had verified against runtime behavior.

Inbox lookup gotcha: silent-failure alerts go to hello@goodlie.golf (Google Workspace, accessed via mail.google.com/mail/u/4). Personal inbox at mail/u/0 does NOT receive these. When investigating ops alerts, navigate to mail/u/4 explicitly.

### 2026-05-03 (morning) — alert lifecycle hardening session

Migration 20260503_alert_lifecycle_and_sent_slots_columns.sql shipped. Applied to prod via Supabase SQL Editor at ~9:25 AM, committed as 73920c3 on foreward-api/main. First properly-committed batched migration; establishes migrations discipline.

Schema changes:
- alert_profiles.status (text, default 'active', CHECK in active|fired|expired|paused)
- sent_slots.user_id (uuid) — backfilled 65/126 rows; 61 orphans
- sent_slots.course_name, tee_time, players, taken_at, scanned_at
- Indexes: alert_profiles_status_active_idx (partial), sent_slots_user_id_idx, sent_slots_activity_idx (partial)

Track 3 close-out: 20260429_enable_rls_sent_slots.sql finally committed (fb13669). RLS verified live (Advisor zero issues).

API changes (commits e20436f, c70af92):
- GET /alerts accepts ?status=, defaults to status=active
- GET /alerts/history includes status field per row
- POST /alerts/{id}/retry — sets status='active'
- GET /activity — public, 30s cache, 20 most recent ticker rows
- POST /scraper/expire-alerts — bulk-marks expired (called by scraper top-of-poll)
- POST /scraper/fire-alert — marks fired + invalidates alert cache

Scraper changes (commit c916e1c): top of poll calls POST /scraper/expire-alerts; active alerts filter status='active'; one-shot firing per alert per poll; slot inserts populate user_id, course_name, tee_time, players, scanned_at; SMS body multi-slot variant + single-slot variant; mark_taken_slots_api() runs per-platform AFTER productive polls only.

Lovable phase: dashboard filter, History tab redesign with badges + "Try again" button, homepage activity ticker, region-group pill collapsing 13 GTA courses. Shipped.

Stripe insight: investigated 4-customers-but-2-subscriptions discrepancy. Root cause: 2 abandoned Checkout sessions. Logged ClickUp 86ah8ag8y to enable Stripe's automated recovery emails.

### 2026-04-30 — Activity ticker session + product decision lock-in

Activity ticker (#1 of 3 website improvements) — superseded by 2026-05-03 implementation. Take-detection mechanism: piggyback on the existing 60s worker poll. Implemented 2026-05-03.

Created the original architecture doc as the canonical source of truth (later retired 2026-05-21). Full scavenge completed. Locked product decisions (auto-booking, priority list, per-course config, multi-channel, playing partners).

### 2026-04-29 — RLS migration applied to sent_slots

Deny-all to anon/authenticated; service role bypasses.

### 2026-04-27 — EZLinks retired

EZLinks retired as a scraping platform. Coverage moved to GolfNow.

### 2026-04-26 — Scraper health dashboard feature complete

### 2026-04-25 — @playgoodlie Instagram handle secured

---

## How this file gets updated

You don't update it. Claude Code does, automatically.

If a chat session produces an actioned decision worth logging, the chat session creates a task in ClickUp list `901327295790` with the markdown block as the task description. The next Claude Code session in any Good Lie repo, at session start, drains that queue: pulls each task, appends its markdown to the decision log, commits, pushes, closes the task.

If you find yourself wanting to edit this file by hand, stop. Either:
- The change is an actioned decision → tell Claude to queue it, or paste into a Claude Code session
- The change is current-state info → it doesn't belong in this file; query the live source

The only valid manual edit to this file is fixing a typo or formatting bug in something already committed. Even then, prefer routing through Claude Code.
