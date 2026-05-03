-- Enable RLS on sent_slots to address Supabase Security Advisor error
-- All legitimate access uses service_role which bypasses RLS:
--   - Scraper writes via /scraper/sent (POST) and reads via /scraper/sent/{alert_id}/{slot_key} (GET)
--   - Admin dashboard reads in /admin/stats and /admin/dashboard
--   - User-facing /alerts/history reads with application-level user_id filter
-- This policy denies direct client access from anon and authenticated roles,
-- which is correct because no legitimate path uses those clients for this table.

ALTER TABLE public.sent_slots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "No direct client access to sent_slots"
ON public.sent_slots
FOR ALL
TO anon, authenticated
USING (false);
