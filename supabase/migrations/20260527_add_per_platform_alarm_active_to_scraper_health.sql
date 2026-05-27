-- Migration: 20260527_add_per_platform_alarm_active_to_scraper_health
-- Adds per_platform_alarm_active jsonb to scraper_health for CAS-guarded
-- per-platform alarm state. Stores {"gtg": bool, "golfnow": bool, ...}.
-- Default empty object so the row is unaffected and new platforms are falsy.

ALTER TABLE scraper_health
  ADD COLUMN IF NOT EXISTS per_platform_alarm_active jsonb DEFAULT '{}'::jsonb;

NOTIFY pgrst, 'reload schema';
