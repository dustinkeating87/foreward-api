ALTER TABLE scraper_health
  ADD COLUMN IF NOT EXISTS captcha_balance_alarmed boolean,
  ADD COLUMN IF NOT EXISTS last_captcha_balance_check_at timestamptz,
  ADD COLUMN IF NOT EXISTS last_captcha_balance_usd numeric(10,4);
NOTIFY pgrst, 'reload schema';
