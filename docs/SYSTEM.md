# Good Lie Golf — SYSTEM (repo mirror)

**ClickUp doc is the source of truth: https://app.clickup.com/90131142261/docs/2ky3r5kn-713**

**If this file disagrees with the ClickUp doc, the ClickUp doc wins.** This mirror exists for in-repo convenience only. Do not edit it by hand — queue updates in ClickUp list `901327295790` and let Claude Code drain them.

---

## Anti-rot rule

Never freeze volatile state as prose here. Schema, pricing, env vars, course lists, deploy config, and live metrics belong in live sources (see Pointers below), not in this file. Write pointers, not snapshots.

---

## Reading rule: ticket status is not ship state

ClickUp ticket status answers only "is there open work." It is never evidence of whether a feature exists, is enabled, or matches current behavior. A "to do" ticket does not mean a feature is unbuilt; a "complete" ticket does not mean live behavior matches its spec.

Whether something is built, shipped, enabled, or has-sent is answered in order by: (1) the decision log in this doc; (2) the live source named in the Pointers table (Railway vars, Supabase, repo source, SendGrid). Never from ticket status, never from injected chat memory alone.

**Session-start enforcement.** Make no claims about system state until this doc's body has been read live this session. If the read fails, retry and use ClickUp search as fallback before reasoning; injected memory is not a substitute (recency bias). When answering any is-it-built / is-it-on / how-many / has-it-sent question, state the live source checked so a stale assumption is catchable on sight.

---

## Product

Good Lie Golf — tee-time alert service for GTA-area golf courses. Users configure courses + date/time windows + player count + holes, and receive SMS notifications when matching tee times open. The product is the *alert*, not the *booking*.

**Domain:** https://goodlie.golf · **Instagram:** @playgoodlie

### Brand pivot history
1. Tee Sniper (original — scraper module still named `tee_sniper.py`)
2. FOREward / FOREward Tee Times (Lovable project name; GitHub repos: `foreward`, `foreward-api`, `foreward-scraper`)
3. Good Lie Golf (current)

**Naming rule:** "Snipe" is internal-only — never user-facing. Always "alert," "match," or "opening."

### Product model (as of 2026-05-27)

Free tier is LIVE (`FREE_TIER_ENABLED=true` in Railway web service).

**Unsubscribed path:** ONE free alert (`is_free_tier=true` on the alert row). Grace retry: if that alert expires without ever firing an SMS, user gets one additional free alert. After that → 402 Payment Required. `free_tier_used_at` is stamped at first confirmed delivery, not at creation.

**Paid path:** $9.99 CAD/month Stripe subscription. `billing.py` updated to `trial_period_days: 30` on 2026-05-26 — verify Stripe dashboard price config matches before treating as confirmed. Up to 10 active alerts.

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
| CI | GitHub Actions on push | both backend repos | GitHub web UI |
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

**Implementation:** direct `httpx` GET to `gateway.golfthe6ix.com/Booking/Teetimes` with `CaptchaTokenV3` header (Turnstile token, solved by 2captcha, `action=Booking_Teetimes`). YYZ proxy on gateway calls. One fresh solve per date per poll. Sitekey: scraped live from `GET https://gateway.golfthe6ix.com/App/GlobalTenantSettings` (JSON field `CloudflareRecaptchaSiteKey`); hardcoded fallback only as last resort with loud WARN.

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
| Canonical course registry (slug ↔ display ↔ platform) | `foreward-api/app/util/courses.py` (API side); COURSES lists in each scraper file (scraper side) |

**Rule: if a fact about current state is needed, query a live source. Do not infer from this file.**

---

## Failure modes

| Failure | Detection | Recovery |
|---|---|---|
| GTG sitekey rotation | `[gtg] SITEKEY FALLBACK` WARN in logs; `sitekey_fallback_active` alarm email within ~2.5h | Scrape self-heals via GlobalTenantSettings; alarm clears automatically |
| 2captcha balance exhausted | `scraper_health.captcha_balance` alarm | Top up at 2captcha.com |
| GolfNow/Chronogolf block | `consecutive_zero_polls` HTTP-failure counter | Proxy rotation / wait |
| Worker crash | Heartbeat stale | Railway auto-restart |
| API down during fire | Repeated SMS | Manual SQL UPDATE |
| Stripe webhook drops | Manual reconciliation | Stripe retries ~3 days |

~~KNOWN-DRIFT: `alert_profiles.courses` mix of slugs and display names~~ **Resolved 2026-05-28.** All rows are now slug format; strict write-time validation (422) blocks new display-name entries. Backfill script committed as artifact (`foreward-api/scripts/backfill_course_slugs.py`).

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
| `free_tier_used_at` stamped at first confirmed delivery | 2026-05-07 / updated 2026-05-27 | Prevents premature consumption |
| GTG data is public — no login needed, ever | 2026-05-24 | Confirmed live |
| GTG uses direct httpx GET + 2captcha CaptchaTokenV3 | 2026-05-25 | Confirmed in production |
| ClickUp doc is source of truth; repo SYSTEM.md is mirror | 2026-05-25 | Prevents doc drift |
| auth.users email is delivery floor; fallback chain: notify_email → auth email | 2026-05-27 | Auth email is guaranteed non-null |
| fire_alert refuses to set status='fired' on empty slots | 2026-05-27 | Prevents silent no-delivery fires |
| DB reads from chat OK; live-state writes go through API endpoints | 2026-05-27 | Prevents bypassing business-logic guards |
| slug is canonical for `alert_profiles.courses`; enforced at API write-time since 2026-05-28; CI guards scraper registry sync | 2026-05-27 (locked) / 2026-05-28 (enforced) | Format drift broke matching 3+ times; structural fix complete |
| Founding 100 offer: first 100 subscribers get founding rate for first year, then roll to list price; "first 100" is marketing copy, not Stripe enforcement; closing the offer = unset FOUNDER_COUPON_ID | 2026-06-10 / amended 2026-06-11 | FOUNDINGYEAR coupon is uncapped (max_redemptions=null); urgency via unknown-remaining scarcity, no visible counter, no deadline |
| No Stripe trial; subscriptions charge from day 1 | 2026-06-11 | Trial was redundant with the founding $4.99 rate and the free-tier alert; free alert is now the only free entry |

---

## Decision log

Append-only. Most recent at top. Updated automatically by Claude Code draining ClickUp list `901327295790`.

### 2026-06-11 — Paywall email updated with founding offer copy; FOUNDER_COUPON_ID set; checkout confirmed $4.99; 12 vs 11 delta explained

Paywall conversion email (`send_paywall_email`) updated with founding-offer copy. Subject: "That one was on the house." Good/bad-news structure kept; bad-news block now pitches $4.99/mo founding rate ("The first 100 members lock in at $4.99 a month for their first year, then $9.99. Applies automatically at checkout, no code needed. Up to 10 alerts at once, across every course we watch. Cancel anytime. The count is not posted."). Old $9.99-only language retired. Committed 96dfcd2, pushed main.

`FOUNDER_COUPON_ID` set to `FOUNDINGYEAR` (uppercase) on Railway `spirited-youthfulness`. Note: coupon exists in Stripe as `FOUNDINGYEAR` (uppercase) — initially set to lowercase `foundingyear` (wrong; Stripe IDs are case-sensitive), immediately corrected. Coupon params confirmed live: amount_off=$5.00 CAD, duration=repeating, duration_in_months=12, valid=true. `max_redemptions=None` (uncapped; see 2026-06-11 entry below for rationale).

Checkout test confirmed via live Stripe API: price_1TPOe5F1e15xxqfqUgs0dbNE + FOUNDINGYEAR coupon → amount_total=499 cents ($4.99 CAD), amount_discount=500 cents, amount_subtotal=999 cents. No trial (`subscription_data=None`). Checkout pipeline is live-ready.

12 vs 11 recipient delta explained: bare SQL (no delay gate) returned 12 candidates; conversion sweep dry-run returned 11. Missing user: `df3c1003-dc1d-46ba-ab58-71375c81b3f6`, `free_tier_used_at=2026-06-11 10:16 UTC` (< 24 hours ago). Excluded by `FIRE_DELAY_HOURS=24` cutoff in `conversion_sweep.py` — by design. No NULL `is_active` issue, no missing email fallback. `PAYWALL_EMAIL_DRY_RUN` remains `true`; live send awaits Dustin approval after checkout test.

### 2026-06-11 — Trial removed; FOUNDINGYEAR coupon confirmed; paywall sweep endpoint wired

**AMENDED 2026-06-10 entry:** FOUNDINGYEAR coupon has `max_redemptions=None` (uncapped). "First 100" is marketing copy, not Stripe enforcement. Closing the offer is a manual decision: unset `FOUNDER_COUPON_ID` on Railway `spirited-youthfulness`.

Stripe trial removed from checkout. `subscription_data: {trial_period_days: 30}` deleted from `billing.py`. Stripe Price `price_1TPOe5F1e15xxqfqUgs0dbNE` confirmed via live API to have `recurring.trial_period_days=null` — no dashboard-level trial exists; code removal is sufficient. Subscriptions charge from day 1. Tickets 86ahpqy0m and 86ahqck8e both closed as superseded. Unifying funnel story: free alert fires → conversion email pitches $4.99 founding rate → checkout charges $4.99/mo via FOUNDINGYEAR coupon → rolls to $9.99 after 12 months. No free month anywhere.

Paywall conversion sweep endpoint: `POST /scraper/send-paywall-emails` added to `app/main.py` (API-key auth, same as other `/scraper/*` endpoints). Calls `run_conversion_sweep(dry_run=settings.paywall_email_dry_run)`. New `PAYWALL_EMAIL_DRY_RUN` env var (Railway `spirited-youthfulness`), default `true` — kill switch; set to `false` to enable live sends. Scraper (`tee_sniper.py`) calls endpoint once per UTC day via `send_paywall_emails_daily()` with date-gate. `conversion_sweep.py` (from prior session) provides query logic and `auth.users` email fallback.

### 2026-06-10 — Founding-member offer + FOUNDER_COUPON_ID auto-applied at checkout

*(Amended 2026-06-11: coupon is uncapped — see 2026-06-11 entry above)*

First 100 subscribers get a founding rate for their first year, then roll to list price ($9.99/mo CAD). List price unchanged — market scan confirmed mid-band and not the conversion blocker. Duration is one year, NOT lifetime. "First 100" is marketing scarcity; Stripe max_redemptions=null (uncapped). No visible counter, no deadline.

Backend: new `FOUNDER_COUPON_ID` env var on Railway `spirited-youthfulness`. If set and non-empty, `billing.py:create_checkout_session` adds `discounts:[{coupon: FOUNDER_COUPON_ID}]` to the Stripe checkout session. Kill switch: unset/empty = full-price checkout. Defensive fallback: if Stripe rejects the coupon for any reason, session is retried without the discount so checkout never fails. `allow_promotion_codes` is NOT set (auto-applied coupon; a promo code field would confuse users and Stripe rejects `discounts` + `allow_promotion_codes` together). Changes: `app/config.py` (new `founder_coupon_id` field), `app/routers/billing.py` (`create_checkout_session` refactored to `session_params` dict + conditional discount + retry).

Offer placement: FIRST ALERT FREE (hero) → FOUNDING 100 / $4.99 first year → $9.99 / cancel anytime. Not burned into hero image. Reinforce on landing page (Lovable).

Parked: season pass (Apr–Oct) priced to playable months, revisited once there are subscribers to retain.

### 2026-06-07 — Reading rule: ticket status is not ship state

New rule added after a chat session incorrectly concluded that free-tier lifecycle emails were unbuilt by reading ClickUp ticket status, when the decision log already recorded them as shipped on 2026-05-26. Root cause: tickets are never updated after work ships; only the decision log and live sources are authoritative.

Rule: ticket status answers only "is there open work." Whether something is built, shipped, enabled, or has-sent is determined by (1) this decision log, then (2) the live source (Railway vars, Supabase, repo source, SendGrid). Never from ticket status; never from injected chat memory alone. Session-start enforcement: state the live source checked for every live-state assertion.

### 2026-06-03 — Good Lie native app (Capacitor) reaches verified Phase 1

App is wrapped in Capacitor as a native shell over the live web app, in a new private repo `goodlie-app` (separate from foreward by design — Lovable owns foreward and would clobber native folders). Spike resolved GO: email/password Supabase auth survives the Android WebView and lands on the alerts dashboard. Phase plan: P1 wrap setup (done), P2 native push (FCM/APNs + device-token table + scraper notify path; `device_tokens` migration staged, not applied), P3 payments (RevenueCat/IAP to the `is_active` gate), P4 store builds (Android any OS; iOS needs macOS+Xcode, available). Paid gates deferred. Stable truth + pointers only.

### 2026-05-28 — Canonical slug registry; write-time validation; GTG slot enrichment; CI key-parity

Course-identifier format drift fixed structurally (ticket 86ahk5w6n). **Slug is canonical everywhere.** Canonical registry = `foreward-api/app/util/courses.py`. A Supabase courses table (A2) was rejected: scraper per-platform operational config (platform IDs, GTG abbreviations) is irreducible and can't collapse into a shared table — a table adds infra without removing the drift surface. The anti-recurrence mechanism is the CI key-parity check.

**Part A:** `util/courses.py` extended with 6 GTG courses (dentonia-park, don-valley, humber-valley, maple-acres, scarlett-woods, tam-o-shanter); display names marked advisory (GTG gateway is authoritative at runtime). `GET /courses` switched from frozen `docs/courses.json` (generated by deleted `scripts/refresh_state.py`) to `util.courses.all_courses()` — 152 courses. CI check added to foreward-scraper (`scripts/check_course_keys.py` + `check-course-keys` job in `ci.yml`): clones foreward-api, fails build if any scraper `course_key` is absent from `util/courses.py`.

**Part B:** `_validate_courses()` in `alerts.py` rejects unknown slugs with 422 at alert create and update. Strict slug-only at the API boundary.

**Part C:** `scripts/backfill_course_slugs.py` — idempotent dry-run-by-default; reverse map derived from `util/courses.py` at runtime (no hardcoded literals). All active alert rows were already slugs when strict mode was enabled. owen43@me.com's alert was the one live casualty — hotfixed display-name→slug during the chat session. Script committed as documented artifact.

**Part D (scraper):** `GTG_COURSE_ID_MAP` added to `tee_sniper.py` mapping gateway abbreviations (DP/DV/HV/MA/SW/TS) to slugs. `poll_gtg_date` replaces slot `CourseID` with slug before matching. MA (Maple Acres) added to request params (was previously omitted). `slot_matches_profile` restructured: direct slug equality check runs first; tolerant `_normalize_course` fallback retained for backwards compat but emits WARNING when it fires — making future drift visible in logs.

Commits: foreward-api `e797925` (A+B+C), foreward-scraper `aeee8fc` (CI check), `aa8c7e6` (D).

**KNOWN-DRIFT resolved:** all `alert_profiles.courses` rows are now slug format.

### 2026-05-27 — GTG zero-fire fixed; no-delivery defect trio; re-arm endpoint; CC permission policy; slug canonical

GTG fired zero alerts since ~May 13–14. Root cause: `_normalize_course()` stripped apostrophes but not hyphens; alert slug "humber-valley" never matched scraped CourseName "Humber Valley". Fix: strip ALL non-alphanumerics. Commit d8198b7, verified live (rsantoo's alert fired).

Course-identifier format drift named as recurring bug class. **LOCKED: slug is canonical.** Structural fix tracked in 86ahk5w6n.

No-delivery defect trio: (A) email fallback to auth.users.email (delivery floor, commit 71bc614); (B) fire_alert refuses status='fired' on empty slots (scraper bc7a3c3, api afe7ff3); (C) free_tier_used_at stamped at delivery not creation (commit 350d44d).

Internal POST /scraper/rearm-alert: API-key auth, no subscription gate. Commit 05ddb73.

Claude Code permission policy in both repos: silent-allow routine ops; force-prompt irreversibles. Python edits to billing.py/auth.py rely on prose-only protection — Dustin must review diffs for those files.

### 2026-05-26 (pm-2) — Admin dashboard honest-health; auth+signup fixes; date validation; CI fixed

Admin honest-health: `_platform_status(streak, threshold)` as single source of truth. Frontend (Admin.tsx) now renders backend verdict — was computing health against hardcoded thresholds, could show green while platform was dead. Commit 9911d70.

Auth 15-min logout fixed (Lovable): `refresh()` now clears only on 401, not transient 502/503.

**Signup redirect fixed (Lovable) — 100% of organic signups were being redirected to sign-in.** Fix: call `refresh()` before navigating from signup. Dominant activation leak.

Server-side alert date validation (schemas.py): rejects bad date ranges, inverted windows, malformed HH:MM. 8 tests.

CI: deleted broken "Refresh STATE.md" workflow. Scraper CI now runs pytest on Python 3.11 against real module (all scraper tests were unguarded since May 3).

Still open (Stripe, Dustin-action): confirm trial=30 days in Stripe dashboard; disable auto "trial ending soon" email.

### 2026-05-26 (pm) — GTG sitekey scrape truly fixed (GlobalTenantSettings); idle-nudge email

Sitekey root cause: key was **never** in HTML or JS bundles. All prior extraction paths (including the May 25 "direct bundle fetch" fix) looked in the wrong place. Key served by `GET https://gateway.golfthe6ix.com/App/GlobalTenantSettings` (field `CloudflareRecaptchaSiteKey`). **Supersedes May 25 "sitekey fixed" entry.** Commit f0b667f. Confirmed live: `sitekey_fallback_active` → false.

Idle-nudge email (app/idle_nudge.py): daily loop, targets organic free users with 0 alerts, 4+ days since signup. First run sent to 7 users.

### 2026-05-26 — Three-state zero-poll counter; sitekey fallback alarm; free→paid emails

Three-state zero-poll counter: throttle path no longer resets GTG counter (was root cause of May 14–21 silent outage, not aggregate-masking as previously attributed). GTG treats zero-slot response as failure; GolfNow/Chronogolf treat only HTTP failure. **KNOWN-BROKEN for consecutive_zero_polls removed — fixed.**

sitekey_fallback_active alarm: scraper reports flag → API transitions/emails on entry. Future rotation alarms within ~2.5h. Migration `20260526_add_sitekey_fallback_to_scraper_health.sql`.

Free→paid emails: success/upgrade email on free-tier alert fire (gated: is_free_tier AND NOT user_is_paid); expiry email rewritten. `/export-alerts` now returns `is_free_tier` and `user_is_paid`.

### 2026-05-25 — GTG rebuild live; session code retired; docs made canonical

GTG rebuild confirmed in production (105 slots, 3 2captcha solves, ~$0.01/poll). `mint_gtg_session.py` deleted. Sitekey scrape attempted via direct bundle fetch — later found to be the wrong extraction path entirely (see 2026-05-26 pm). ClickUp doc created as canonical source of truth; SYSTEM.md files rewritten as mirrors; ARCHITECTURE.md stubbed.

### 2026-05-25 — GTG token-reuse confirmed non-reusable; poll interval locked at 900s

Each `/Booking/Teetimes` request requires a fresh 2captcha solve. GTG_POLL_INTERVAL=900 chosen to hold under $15/mo budget.

### 2026-05-24 — GTG: data is public; proxy IP not burned; Patchright fingerprint was blocker

Live logged-out browser testing confirmed GTG tee-time data is fully public (no login). YYZ proxy IP passes Turnstile fine with a real browser. Patchright automation fingerprint was the actual blocker, not the IP.

### 2026-05-23 — GTG: cf_clearance lasts ~1yr; manual-clearance path explored (now moot)

cf_clearance cookie expiry confirmed ~1 year. Session pivot to cookie-reuse as lead path — superseded by the direct-GET + 2captcha approach.

### 2026-05-21 — ARCHITECTURE.md retired; SYSTEM.md format established

Doc drift was causing multi-session knowledge loss. Replaced architecture doc with SYSTEM.md (narrative + pointers, no frozen state). ClickUp queue list created for automated updates.

### 2026-05-09 — Free-tier lifecycle simplified

Migration `20260509_simplify_free_tier.sql` dropped renewal-cycle model. Live model: one free alert + grace retry → pay.

### 2026-05-07 — Block 3: free-tier alert lifecycle implemented and verified

7 commits, 21 new tests passing. Subsequently simplified 2026-05-09.

### 2026-05-06 — Block 2: phone verification; Block 1: free-tier schema

Phone verification endpoints (send/verify/resend). `phone_verification_codes` table.

### 2026-05-03 — Alert lifecycle, backups, CI, silent-failure monitoring

Full alert lifecycle, sent_slots schema, scraper expire/fire endpoints, activity ticker, backups, CI. Silent-failure monitoring via consecutive_zero_polls (two-state; superseded by three-state counter 2026-05-26).

### 2026-04-27 — EZLinks retired

Coverage moved to GolfNow.
