-- Applied to production on 2026-05-09 via Supabase MCP.
-- Reason: decouples phone-reuse prevention from free_tier_used_at stamp,
-- enabling the create-first-alert flow per PRODUCT_FREE_TIER.md.

DROP INDEX IF EXISTS ix_user_profiles_phone_hash_free_tier;

CREATE UNIQUE INDEX ix_user_profiles_phone_hash_unique
ON public.user_profiles (phone_hash)
WHERE phone_hash IS NOT NULL;
