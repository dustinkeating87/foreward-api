-- Block 2: verification codes for free-tier phone verification
-- Applied via Supabase SQL Editor. Commit file after applying.

CREATE TABLE IF NOT EXISTS phone_verification_codes (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_hash          text        NOT NULL,
    code                text        NOT NULL,
    verification_token  text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    expires_at          timestamptz NOT NULL,
    token_expires_at    timestamptz,
    resend_count        int         NOT NULL DEFAULT 0,
    last_resend_at      timestamptz,
    used                boolean     NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS ix_pvc_phone_hash ON phone_verification_codes (phone_hash);

-- RLS: service role only (API uses supabase_admin / service key for all reads/writes)
ALTER TABLE phone_verification_codes ENABLE ROW LEVEL SECURITY;
