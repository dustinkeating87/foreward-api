# Good Lie Backups — How to Restore

## Where backups live
`~/Library/CloudStorage/GoogleDrive-hello@goodlie.golf/My Drive/Good Lie Backups/`

Each file: `goodlie_YYYYMMDD_HHMMSS.sql.gz`. New backup every Sunday at 10 AM. Files older than 28 days auto-pruned.

## Health check
Should show `OK <date>`. If `FAIL`, see `~/Library/Logs/goodlie-backup.log`.

## Restore procedure

1. **Pick a backup** — most recent file from before the corruption.
2. **Decompress:** `gunzip -k goodlie_YYYYMMDD_HHMMSS.sql.gz`
3. **Decide:** restore to existing project (faster, destroys current data) OR fresh project (safer, preserves the broken project for forensics).
4. **Run:** `psql "<CONNECTION-STRING>" < goodlie_YYYYMMDD_HHMMSS.sql`
5. **Verify counts:**
```sql
SELECT count(*) FROM auth.users;
SELECT count(*) FROM public.user_profiles;
SELECT count(*) FROM public.alert_profiles;
SELECT count(*) FROM public.sent_slots;
SELECT status, count(*) FROM public.alert_profiles GROUP BY status;
```
Compare against ARCHITECTURE.md "Live state" section.

6. **Re-point services** (only if restored to fresh project) — update `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY` on Railway `spirited-youthfulness/web` and `resourceful-delight/worker`. Get new values from Supabase → Project Settings → API. Also update `~/.goodlie-backup-env`.

## Caveats

- **Stripe state** — `stripe_customer_id`/`stripe_subscription_id` are restored, but Stripe is the source of truth. Reconcile via Stripe Dashboard after restore.
- **Auth users** — `auth.users` is restored, but `auth.identities`, `auth.sessions`, `auth.refresh_tokens` aren't. Users will be logged out; they sign in normally with existing credentials. If issues, send password reset emails via Supabase Dashboard → Authentication → Users.
- **Application code** — this backup is data only. Code lives in GitHub (`dustinkeating/foreward-api`, `dustinkeating/foreward-scraper`, `dustinkeating/foreward`).
- **Schema migrations** — `foreward-api/supabase/migrations/` is the source of truth. After restore, verify any newer migrations have been re-applied.

## Test quarterly
Untested backups aren't backups. Once a quarter: create a temp Supabase project (free tier), restore the latest backup, verify counts, delete the temp project.
