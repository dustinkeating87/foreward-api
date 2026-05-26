-- Migration: 20260526_add_sitekey_fallback_to_scraper_health
-- Adds sitekey_fallback_active boolean to scraper_health for GTG sitekey alarm debounce.
-- The API's /scraper-heartbeat handler reads prev state from this column and fires a
-- SendGrid email only on False->True and True->False transitions (same pattern as
-- captcha_balance_alarmed). Applies once; DEFAULT false so existing row is unaffected.

ALTER TABLE scraper_health
  ADD COLUMN IF NOT EXISTS sitekey_fallback_active boolean DEFAULT false;

NOTIFY pgrst, 'reload schema';
