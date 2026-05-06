-- Block 1: Free-tier schema columns and indexes
-- Ticket: 86ahaz9e0
-- Applied: 2026-05-06 via Supabase SQL Editor

-- alert_profiles: free-tier tracking columns
ALTER TABLE alert_profiles ADD COLUMN IF NOT EXISTS is_free_tier boolean NOT NULL DEFAULT false;
ALTER TABLE alert_profiles ADD COLUMN IF NOT EXISTS polling_expires_at timestamptz;
ALTER TABLE alert_profiles ADD COLUMN IF NOT EXISTS renewals_used integer NOT NULL DEFAULT 0;
ALTER TABLE alert_profiles ADD COLUMN IF NOT EXISTS final_expired_at timestamptz;
ALTER TABLE alert_profiles ADD COLUMN IF NOT EXISTS expiry_state text;

-- expiry_state CHECK constraint (idempotent via DO block)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'alert_profiles_expiry_state_check'
      AND conrelid = 'public.alert_profiles'::regclass
  ) THEN
    ALTER TABLE alert_profiles
    ADD CONSTRAINT alert_profiles_expiry_state_check
    CHECK (expiry_state IS NULL OR expiry_state IN ('expired_pending_renewal', 'final_expired'));
  END IF;
END $$;

-- user_profiles: free-tier tracking columns
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS phone_verified boolean NOT NULL DEFAULT false;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS phone_hash text;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS free_tier_used_at timestamptz;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS final_expired_at timestamptz;

-- Indexes
CREATE UNIQUE INDEX IF NOT EXISTS ix_user_profiles_phone_hash_free_tier
  ON user_profiles (phone_hash)
  WHERE free_tier_used_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_alert_profiles_polling_expires_at_free_tier
  ON alert_profiles (polling_expires_at)
  WHERE is_free_tier = true AND expiry_state IS NULL;
