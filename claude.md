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

## Claude Code permission policy

The `.claude/settings.json` at the repo root encodes two tiers of operations.

**Routine ops — auto-run without prompting:** reading any file (Read tool), editing or creating files with common source extensions (`.py`, `.md`, `.json`, `.sql`, `.txt`, `.sh`, `.toml`, `.yaml`, `.yml`, `.cfg`, `.ini`), running the test suite (`pytest`, `python -m pytest`, `python -m compileall`), and git operations that only affect the local repo (`git add`, `git commit`, `git status`, `git diff`, `git log`, `git show`, `git branch`, `git fetch`). Also routine read-only shell ops (`cat`, `ls`, `find`, `grep`).

**Irreversible ops — always force a prompt, never auto-approved:** destructive SQL (any DROP, TRUNCATE, or DELETE/UPDATE without a WHERE clause) via the Supabase MCP tool (`mcp__claude_ai_Supabase__execute_sql`) or psql; force-push (`git push --force`, `git push -f`, `git push --force-with-lease`); any write to secrets or environment variable files (`.env`, `.env.*`) or Railway variable mutations (`railway variables set`); any SQL or Supabase client code touching `auth.users`; any edit to billing or Stripe code (`billing.py`, direct Stripe API calls). These are kept out of the allow list so Claude Code always pauses for human review before proceeding.

**Standing rule for dangerous-set prompts:** when a prompt fires for one of the above operations, Dustin does not answer it himself directly. He pastes the full prompt text into Claude chat and asks for a plain-English explanation of exactly what the operation will do and what the blast radius is. Only after that explanation does he answer yes or no in the terminal. The point of this rule is to prevent any operation in the dangerous set from being approved under time pressure or without full situational awareness.

**Known mechanical gaps (prose-only protection):** the settings.json cannot inspect the content of SQL strings passed to Supabase MCP tools, so it cannot distinguish a safe SELECT from a destructive DROP — all `execute_sql` calls will prompt, not just dangerous ones. Python edits to `billing.py` or any file that makes Stripe API calls are auto-approved by the `Edit(*.py)` rule because Claude Code cannot inspect what the code change does; Stripe protection relies entirely on this prose and human review. Similarly, Python-level calls to the Supabase client that touch `auth.users` (e.g., `supabase_admin.table("users")`) cannot be mechanically detected — they look like ordinary `.py` edits. Files without standard extensions (`Dockerfile`, `Procfile`) will prompt by default since they don't match any allow pattern, which is intentional.
