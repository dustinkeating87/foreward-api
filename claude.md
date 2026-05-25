# Good Lie Golf — API repo (`foreward-api`)

## Source of truth

The canonical system record (architecture, product model, routing rules, locked decisions) lives in the ClickUp doc:

**https://app.clickup.com/90131142261/docs/2ky3r5kn-713**

The repo mirror is `docs/SYSTEM.md` — if it disagrees with ClickUp, ClickUp wins.

## What lives in this repo

- `app/routers/` — FastAPI endpoints (alerts, billing, auth, admin, phone verification, scraper ops)
- `app/email.py` — SendGrid + SMTP wrappers
- `app/config.py` — Settings (reads Railway env vars)
- `supabase/migrations/` — numbered SQL migration files (schema of record)
- `docs/SYSTEM.md` — system mirror + decision log
- `scripts/backup/` — local pg_dump backup setup

## Stack context

- **API service:** Railway `spirited-youthfulness` / web
- **Database:** Supabase `offtdltmvjfizkoeywei` (Ohio)
- **Billing:** Stripe — `billing.py`; pricing in Railway `STRIPE_PRICE_ID` env var
- **Free tier:** `FREE_TIER_ENABLED` env var in Railway; currently `true`

## Schema changes

Always create a numbered SQL file in `supabase/migrations/`, apply via Supabase SQL Editor, then commit the file. Never alter the live schema without committing the migration.

## Naming rule

Never use the word "snipe" in user-facing copy. Use "alert," "match," or "opening."

## Session start checklist

1. Read `docs/SYSTEM.md` for recent system decisions
2. Check ClickUp space `901313780791` for open work
3. Drain ClickUp list `901327295790` if any queued updates exist (read tasks, append to docs/SYSTEM.md AND ClickUp canonical doc, commit, push, close tasks)
