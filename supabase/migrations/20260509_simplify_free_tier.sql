-- Block 6: Simplify free tier per docs/PRODUCT_FREE_TIER.md
-- Removes Block 3 lifecycle machinery columns. Adds grace-retry tracking.
-- Apply via Supabase SQL Editor after Block 6 code is deployed.

ALTER TABLE alert_profiles DROP COLUMN IF EXISTS polling_expires_at;
ALTER TABLE alert_profiles DROP COLUMN IF EXISTS renewals_used;
ALTER TABLE alert_profiles DROP COLUMN IF EXISTS expiry_state;
ALTER TABLE alert_profiles DROP COLUMN IF EXISTS final_expired_at;
ALTER TABLE user_profiles DROP COLUMN IF EXISTS final_expired_at;

DROP INDEX IF EXISTS ix_alert_profiles_polling_expires_at_free_tier;

ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS free_tier_grace_retry_used_at timestamptz;

COMMENT ON COLUMN user_profiles.free_tier_grace_retry_used_at IS
  'Set when a free-tier user uses their one non-firing-expiry grace retry. NULL = grace available.';
