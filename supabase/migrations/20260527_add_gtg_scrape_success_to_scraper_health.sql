-- Migration: 20260527_add_gtg_scrape_success_to_scraper_health
-- Adds gtg_scrape_success boolean to scraper_health so the heartbeat can record
-- whether the GTG HTTP+captcha scrape itself succeeded (True) or failed (False),
-- independently of slot count. This powers trustworthy GTG failure detection:
-- a successful scrape that returns 0 real slots is healthy, not alarming.

ALTER TABLE scraper_health
  ADD COLUMN IF NOT EXISTS gtg_scrape_success boolean;

NOTIFY pgrst, 'reload schema';
