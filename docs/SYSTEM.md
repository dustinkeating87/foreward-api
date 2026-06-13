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

### 2026-06-13 — Tee-on NS HRM go-live: 5 courses onboarded, LOST extended flow shipped

Code shipped: foreward-scraper commit `6cb9972`, foreward-api commit `2b36d72`.

NS launched as HRM region. 5 courses wired into TEEON_COURSES (active=True) and courses.py, poll loop integrated in tee_sniper.py: TLAB (Brunello, already live), AIRL (Airlane), FOHO (Fox Hollow), ILGC (Indian Lake), LOST (Lost Creek). GLAR (Glen Arbour) set active=False — routes to ATL publicly but club offers no public tee times. ForeUP (Granite Springs) and Chronogolf NS deferred.

New flow ss_ext shipped for LOST: Steps 1-6 identical to ss; Step 7a GET WebBookingSearchSteps?FromTrailSearch=true&CourseGroupID={gid}&Date={date}; Step 7b GET WebBookingAllTimesLanding with empty CourseCode (CourseCode=, server resolves from session). Lesson: `CourseCode={code}` returns 622-byte session timeout for LOST; empty string returns full tee sheet. ComboLanding routing pre-check is unreliable for HRM courses (all return HTTP 404).

Live verification (all PASS, Jun 14 2026-06-13): TLAB 42 slots 4 AM 18H; AIRL 26 slots 1 AM 18H; FOHO 72 slots 3 AM 18H; ILGC 6 slots 0 AM 18H (AM sold out — high scarcity); LOST 92 slots 15 AM 18H first=6:39am.

courses.py: airlane-golf-club, fox-hollow-golf-club-ns, indian-lake-golf-course, lost-creek-golf-club added as platform=teeon.

Next step: course-picker frontend (Lovable) — NS courses are monitored but not selectable until picker ships.

### 2026-06-12 — Tee-on adopted as new platform; full fold-in committed, ForeUP deferred

Tee-on platform recon complete (output: `foreward-scraper/recon/tee_on_platform.md`, commit c199142). Decision: build Tee-on as a new scraping platform and fold in every course it opens up — both NS Tee-on courses (Brunello, Glen Arbour) and the ~8 net-new Ontario courses (Toronto-area + Hamilton). Rationale: this is a platform bet, not an NS-only bet. The Ontario/Hamilton unlock justifies the build independent of the Nova Scotia launch decision, so the integration is not NS-contingent.

Difficulty Class B: plain httpx, no Playwright, no captcha / no 2captcha spend. Two page-path variants exist and each course routes to one via a direct endpoint test: `AllTimesLanding` (simple, GET → JSESSIONID → POST `Date=YYYY-MM-DD` → parse HTML; Brunello's path) and `SearchSteps` (multi-step + Altcha proof-of-work, a ~5ms SHA-256 solve done in-process with stdlib — no vendor cost, no new dependency; Glen Arbour's path). No new external dependencies and no per-poll cost; cheaper to operate than GTG.

NS coverage via Tee-on is the two marquee HRM anchors only — Brunello and Glen Arbour. The other NS targets (Northumberland Links, Granite Springs, Hartlen Point) are on other platforms; Granite Springs is ForeUP. Full HRM coverage via a ForeUP integration is deferred — not a launch blocker, since Brunello + Glen Arbour are the most-wanted HRM weekend courses.

Build sequence (Claude Code): (1) AllTimesLanding path + routing test across all targets + ship all easy-path courses; (2) SearchSteps/Altcha path + remaining courses; (3) wire to ALERTING_PLATFORMS + polling cadence + live verification + course-picker frontend (Lovable prompt). Live state — which courses are live and ALERTING_PLATFORMS membership — is read from source per the Pointers table, not frozen here.

### 2026-06-12 — Tee-on platform recon complete; Class B; 2/5 NS targets; ~8 Ontario net-new

Recon output: `foreward-scraper/recon/tee_on_platform.md` (commit c199142 on `foreward-scraper` main).

Platform: Tee-on (`www.tee-on.com`). Difficulty: Class B — plain httpx, no Playwright, no datacenter IP block on Webshare YYZ proxy (confirmed).

Two booking flows exist (course-level config):
- **WebBookingAllTimesLanding** (Brunello confirmed): GET for JSESSIONID → POST with `Date=YYYY-MM-DD` body param. Server-rendered HTML. No CAPTCHA. Proven working this session.
- **WebBookingSearchSteps** (Glen Arbour + all other confirmed NS/ON courses): Same session flow, but requires Altcha SHA-256 proof-of-work challenge solve before POST. Altcha is pure PoW (no fingerprinting) — automatable with ~20 lines of Python, no 2captcha spend. Difficulty 10, maxnumber 100,000.

NS coverage (5 scarce HRM targets): 2 of 5 on Tee-on — Brunello (TLAB/10789, AllTimesLanding) and Glen Arbour (GLAR/10127, SearchSteps). Granite Springs (ForeUP), Hartlen Point (phone only), Northumberland Links (Chronogolf) are not on Tee-on. 14 NS Tee-on courses total (6 in HRM).

Ontario/GTA net-new: ~8 courses Tee-on would unlock that aren't in current courses.py: 3 Toronto-area (Oakville Executive OEGC/10621, Pheasant Run PHEA/10087, Turtle Creek TUCR/10136) + 5 Hamilton-area. All on SearchSteps+Altcha.

Brunello scarcity confirmed on live Tee-on data: Jun 14 Saturday showed only 5 × 18-hole AM slots before noon (7:00, 7:10, 7:30, 8:10, 9:40). Booking window opens 7 days out at 6:30 AM local.

### 2026-06-12 — Geographic expansion un-shelved; Nova Scotia chosen as first out-of-region market; Vancouver rejected, Montreal deferred

Out-of-GTA expansion is the next growth push, reversing the prior "geographic expansion shelved until activation/conversion improve" stance. Justified by sustainable monthly burn (~$100/mo per Dustin) and the fact that adding courses on already-scraped platforms (GolfNow, Chronogolf) is low-effort. Decision driver: Toronto's slow uptake is understood as a category/audience problem (easy-to-clone service, hostile enthusiast community, GTG/city-course wedge muzzled by the City of Toronto takedown request) rather than something more Toronto reach fixes.

**Market scan findings (durable):**

- **Vancouver — rejected.** Not whitespace. Incumbent alert services already operate there: Tee Time Buddy (near-identical freemium model — free single alert, paid SMS/multi-course — across Metro Vancouver) and Snag Your Tee (9 Metro Vancouver public courses incl. Langara/Fraserview/McCleery). Entering means fighting incumbents on their home turf with no local channel presence.
- **Calgary — wedge undercut.** The City of Calgary golf app has a native standby/notify feature on municipal courses, so the acute-pain wedge is self-served. Private Chronogolf courses remain addressable but milder pain.
- **Montreal — deferred, not rejected.** Deeply covered by Chronogolf (its home market); no dedicated alert competitor found. Deferred because: (1) French market — Bill 96 (OQLF enforcement incentive/complaint-based for businesses with no Quebec establishment; practical risk low; fr-CA toggle resolves cheaply); (2) Lightspeed/Chronogolf home turf raises native-feature risk. Dustin is willing to run English ads there and add French later if NS proves the model.

**Chosen path: Nova Scotia first.** English, no alert competitor found, documented acute weekend scarcity (The Links at Brunello reviews: ~3 weeks out, first weekend availability often 4pm+). Small but clean market — the purest test of "does owning uncontested whitespace convert better than being one of three in Toronto." Start Halifax metro, expand province-wide (demand is HRM-weighted — Cape Breton resort courses like Cabot/Highlands Links/Bell Bay/Fox Harb'r are tourist-demand, not weekend-cancellation demand).

**Strategic positioning candidate:** be the only national Canadian tee-time alert service — every competitor found (Tee Time Buddy, Snag Your Tee, Brio) is single-city. "Tee-time alerts anywhere in Canada, one app" is a story the hyperlocal players structurally can't tell.

**Category caveat (lesson for future sessions):** tee-time alerting is easy to clone (multiple independent services across US/Canada) and booking platforms are absorbing it natively (Calgary standby, Vancouver waitlist, Gallus "Standby" integrates with tee sheets). The demand/willingness-to-pay question follows the product to every market; changing cities relocates it, doesn't solve it.

### 2026-06-11 — Founder funnel shipped and verified e2e; trial removed; full email price sweep

The 30-day Stripe trial was removed entirely (`billing.py`); confirmed no trial exists at the price or in checkout code. The founding-member offer went live: FOUNDINGYEAR coupon ($5 CAD off, repeating 12 months, **uncapped** — "first 100" is marketing, not Stripe-enforced), auto-applied at checkout behind `FOUNDER_COUPON_ID` on spirited-youthfulness. Verified on real invoice and subscription data (not page copy): checkout shows $4.99, charges $4.99, and the coupon attaches to the subscription for a 365-day recurring discount. **Top-level session `discounts` is the correct field for subscription-mode Checkout; `subscription_data.discounts` is silently ignored — do not "fix" this again.** One real founding member (cnolfi24) converted during the session, correctly on $4.99 for the year.

The paywall conversion email was wired to a grace-retry branch that 0 users hit, so it had never fired despite 12 users consuming their free alert. Built a daily sweep (`/scraper/send-paywall-emails`, gated on `FREE_TIER_ENABLED`, `PAYWALL_EMAIL_DRY_RUN` flag, stamps `paywall_email_sent_at` on success only, auth-email fallback chain). Sent live: 11/11 delivered. A 24h `FIRE_DELAY_HOURS` gate correctly holds a just-fired user back to the next sweep.

Price sweep: every outbound email and the recurring charge were audited — not just the checkout page and the in-focus email. Stale $9.99 copy was corrected in `send_paywall_email`, `send_free_tier_fired_email` (scraper, tee_sniper.py), and the welcome email's hardcoded amount. Subscribe page and Account-inactive flow copy updated to $4.99 via Lovable (Account founder-link deferred on Lovable credits).

Two process lessons: (1) A price change must be verified on the recurring invoice and swept across every email surface — verifying the checkout page and the in-focus email is insufficient; this session shipped two emails still on $9.99 after the initial "copy fix." (2) A diagnosis hypothesis is not fact until tested: a recurring-billing "bug" was escalated and a fix deployed that was itself the breakage (zero-discount sessions), caught and reverted within the same window (49ad500 to 0a5192a, no real users affected). Hold the systematic-debugging line — confirm before fixing.

_Doc amendment:_ the 2026-06-10 entry and locked-decisions row stating the cap is "honored via Stripe max_redemptions=100" are superseded — the coupon is uncapped; closing the offer is a manual unset of `FOUNDER_COUPON_ID`.

### 2026-06-11 — Test account created for founder checkout walk; cleanup required

Test account `dustinkeating87+test@gmail.com` (Supabase ID `860cfc42-9bd1-466e-b26d-cb243a382e19`) created 2026-06-11 to walk the $4.99 FOUNDINGYEAR founder checkout flow. Set up in paywall state (`free_tier_used_at` stamped, `is_active=false`, phone_verified manually bypassed). Cleanup required: cancel Stripe subscription + refund if payment completed, delete Stripe customer, delete auth user in Supabase dashboard (user_profiles cascades on auth delete). Steps tracked in ClickUp task wdpu2y8vbk.

### 2026-06-11 — Conversion path audit: billing.py amount fixed; two Lovable gaps flagged

`send_paid_signup_email` in `_handle_checkout_completed` was hardcoded to `amount_cad=9.99`. Fixed to read `session.get("amount_total") / 100` — the actual post-discount Stripe amount — so founding members paying $4.99 get correct copy in the internal alert email. Fallback: 999 cents if `amount_total` absent. Committed a51d880.

Two gaps flagged for Lovable action (pending Dustin approval):
(1) Subscribe.tsx copy stuck at $9.99 — button label `:135`, default body `:105`, and Meta Pixel value `:49` all show $9.99 while the actual checkout charges $4.99 via FOUNDINGYEAR coupon. Copy mismatch creates friction for emailed users who were promised $4.99. Fix: Lovable prompt to update those strings.
(2) Logged-out visitors hitting `/subscribe` (email CTA): `ProtectedRoute` redirects to `/auth?mode=signin` with no `returnTo` param; after sign-in `PublicOnly` sends them to `/dashboard`, purchase intent lost. Fix: pass `redirect=/subscribe` in `ProtectedRoute` redirect, read it after login in Auth.tsx. Both files are Lovable-owned.

Logged-in non-active users (exact state of the 11 emailed users) correctly land on `/subscribe` with the working checkout button. Active-user redirect (`is_active && !sessionId`) is correctly scoped.

### 2026-06-11 — First live paywall sweep sent; PAYWALL_EMAIL_DRY_RUN flipped false

First live conversion sweep executed 2026-06-11 13:43:56 UTC. `PAYWALL_EMAIL_DRY_RUN` flipped to `false` on Railway `spirited-youthfulness`. Sweep sent 11 emails (all qualifying users: `free_tier_used_at IS NOT NULL`, `paywall_email_sent_at IS NULL`, not active, not beta, fired >24h ago). All 11 delivered via SendGrid confirmed via activity API (status=delivered, 13:43:58–13:44:11 UTC). Recipients: brandon.kofman@gmail.com, cnolfi24@gmail.com, ecrsqvxs@sharklasers.com, jaygall@hotmail.com, jalild@me.com, jon.banack@gmail.com, matt.mamalyga@gmail.com, mkwarner@rogers.com, owen43@me.com, rsantoo@rogers.com, willtblanco@gmail.com. All 11 `user_profiles.paywall_email_sent_at` rows stamped at 2026-06-11 13:43:56.770319 UTC. User df3c1003 (fired today, <24h) correctly excluded and unstamped — will qualify on next sweep. No failures; no rows stamped without a confirmed send.

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
