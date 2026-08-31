-- Migration: 20260831_add_proxy_auth_failed_to_scraper_health
-- Adds proxy_auth_failed boolean to scraper_health.
-- Set to true when any scraper detects a 407 Proxy Auth Required response;
-- cleared on the next successful proxied request. The /scraper-heartbeat
-- handler fires one ops email on the false→true transition.

ALTER TABLE scraper_health
  ADD COLUMN IF NOT EXISTS proxy_auth_failed boolean DEFAULT false;

NOTIFY pgrst, 'reload schema';
