ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS idle_nudge_sent_at timestamptz DEFAULT NULL;
NOTIFY pgrst, 'reload schema';
