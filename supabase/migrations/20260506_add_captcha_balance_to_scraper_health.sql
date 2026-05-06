ALTER TABLE scraper_health
  ADD COLUMN IF NOT EXISTS captcha_balance numeric(10,2);
