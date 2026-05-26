-- Add paywall_email_sent_at to user_profiles
-- Tracks whether the "That course just isn't into you" conversion email has been sent.
-- NULL = not yet sent; non-NULL = sent at this timestamp (send once per user, ever).

ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS paywall_email_sent_at timestamptz;

COMMENT ON COLUMN user_profiles.paywall_email_sent_at IS
  'Set when the paywall conversion email is sent after free + grace retry are exhausted. NULL = not yet sent.';
