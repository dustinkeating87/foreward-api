# Good Lie — Free Tier (Product Spec)

**Status:** Canonical. This document defines the free tier. Any code, schema, plan doc, or marketing copy that contradicts this document is wrong and must be brought into alignment.

**Last reviewed:** 2026-05-09 (Dustin)

**Reading rule for future Claude sessions:** any work that touches free-tier signup, free-tier alert lifecycle, the `is_free_tier` column, the `free_tier_used_at` column, or any code path gated on `FREE_TIER_ENABLED` must read this document at session start. If the work appears to require behavior not described here, stop and surface the gap to Dustin before writing code.

---

## Why the free tier exists

We were losing prospective users at the credit-card-required-to-trial gate. The free tier's job is to remove that gate and replace it with a tangible product moment — an SMS arriving with a real tee time on a real course the user actually wants. The conversion lever is the user's own experience of the product working, not feature limitations or expiring trials.

The free tier is a guaranteed-successful demonstration of the product. It is a marketing cost, not a product tier.

---

## What the user gets

A new visitor signs up with a phone number and an email. Phone is verified via SMS code. Both phone and email are permanently locked to that account — neither can be reused for another free-tier signup, ever.

After signup, the user lands on the dashboard and is prompted to set up their one free alert. They configure it exactly the way a paid user would: any course in the system, any date range, time range, players, holes. There are no restrictions on what they can choose. No paid-coverage gating. No course list filtering. No system-side course count limit beyond what already applies to paid users.

The system then watches for a matching tee time and fires the alert exactly the way it fires a paid alert. The user receives one SMS and one email when a match is found.

After the alert fires, the user is done. They cannot retry, edit, or create a second free alert. The dashboard shows the fired alert and a prominent subscribe CTA. The only path forward is a paid subscription.

---

## The one exception: non-firing expiry

If the user's alert hits `date_to` without ever firing — meaning the date range passed and no matching slot ever opened up — they get exactly one chance to reset the alert with a new date range. This is the only case in which a free-tier user gets a second alert configuration.

It exists because the free tier's promise is "guaranteed successful demonstration," and an unsuccessful expiry breaks that promise.

The grace retry is per-user, lifetime. Once used — whether the retry fires or expires again — the user has no more free-tier capacity. They subscribe or they leave.

---

## What does not exist in the free tier

Listed explicitly so future blocks do not reintroduce these:

- **No fixed polling window.** Free alerts run on the same expiry rules as paid alerts: alive until `date_to` passes.
- **No renewal ladder.** No "2 free renewals." No "3 polling windows." No periodic free-tier-specific extensions.
- **No Stripe coupons.** No 100%-off checkouts. No discount codes generated as a free-tier mechanic.
- **No paid-coverage gate on courses.** The user can pick any course in the system. We pay the marginal scrape cost. This is the price of demonstrating a working product.
- **No "permanently expired" state with custom emails and discount codes.** The user simply runs out of free-tier capacity after firing or after using their grace retry.
- **No card-on-file at signup.** Stripe is not invoked anywhere in the signup or alert-creation flow. Stripe checkout only appears post-fire, on the subscribe CTA.
- **No nag emails.** A user who signs up and never sets an alert is left alone.

---

## Future-proofing: how to evaluate proposed changes

If anyone — Claude or otherwise — proposes adding limitations, restrictions, or new mechanics to the free tier in future, the question to ask is:

> Does this make the demo less compelling, or does it add friction between the user and a working SMS in their hand?

If the answer is yes, the proposed change does not belong in the free tier. The free tier is the demo. It is allowed to cost us money. It is not allowed to be a worse product than the paid tier.

The places where new free-tier mechanics tend to creep in are:

- "Operational" reasoning (margin cost, scrape budget, captcha credits) — these concerns belong in paid-tier capacity planning, not free-tier UX
- "Anti-abuse" reasoning beyond the existing phone+email locks — additional anti-abuse should be invisible to legitimate users
- "Conversion funnel" mechanics (drip emails, expiring discounts, urgency timers) — the conversion lever is the SMS the user already received. Don't dilute it.

Before adding anything to the free tier, the proposer must show in writing how the addition fits the "one guaranteed successful demonstration, then convert" model.

---

## Authoritative references

This document is the authoritative product spec. The following derive from it:

- `ARCHITECTURE.md` — must include a "Free Tier (product spec)" section that links to this doc and does not contradict it
- Any plan doc in `docs/superpowers/plans/` that touches free-tier code — must cite this doc and operate within its bounds
- ClickUp tickets in space "Good Lie Golf" related to the free tier — must reference this doc

If any of those derivative documents disagree with this one, this one wins.
