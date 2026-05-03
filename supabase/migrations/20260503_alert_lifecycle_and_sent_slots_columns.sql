-- Migration: 20260503_alert_lifecycle_and_sent_slots_columns
-- Author: Dustin
-- Date applied: 2026-05-03
--
-- Batched schema hardening pass. Combines:
--   1. alert_profiles lifecycle (one-shot fired alerts via status column)
--   2. sent_slots.user_id (closes ClickUp 86ah69xbh — column did not exist)
--   3. sent_slots activity-ticker columns (course_name, tee_time, players, taken_at)
--   4. sent_slots.scanned_at (closes ClickUp 86ah7at4x — "Available as of {time}" SMS)
--
-- All columns nullable. No data loss risk. Backfills are conservative.
-- Wrapped in a transaction so partial failure rolls everything back.

BEGIN;

-- ============================================================================
-- 1. alert_profiles lifecycle
-- ============================================================================
ALTER TABLE public.alert_profiles
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'fired', 'expired', 'paused'));

UPDATE public.alert_profiles
SET status = 'expired'
WHERE date_to < CURRENT_DATE
  AND status = 'active';

UPDATE public.alert_profiles
SET status = 'paused'
WHERE active = false
  AND status = 'active';

CREATE INDEX IF NOT EXISTS alert_profiles_status_active_idx
  ON public.alert_profiles (status)
  WHERE status = 'active';

-- ============================================================================
-- 2. sent_slots.user_id
-- ============================================================================
ALTER TABLE public.sent_slots
  ADD COLUMN IF NOT EXISTS user_id uuid;

UPDATE public.sent_slots ss
SET user_id = ap.user_id
FROM public.alert_profiles ap
WHERE ss.alert_id = ap.id::text
  AND ss.user_id IS NULL;

CREATE INDEX IF NOT EXISTS sent_slots_user_id_idx
  ON public.sent_slots (user_id);

-- ============================================================================
-- 3. sent_slots activity-ticker columns
-- ============================================================================
ALTER TABLE public.sent_slots
  ADD COLUMN IF NOT EXISTS course_name text,
  ADD COLUMN IF NOT EXISTS tee_time    timestamptz,
  ADD COLUMN IF NOT EXISTS players     int,
  ADD COLUMN IF NOT EXISTS taken_at    timestamptz;

CREATE INDEX IF NOT EXISTS sent_slots_activity_idx
  ON public.sent_slots (created_at DESC)
  WHERE course_name IS NOT NULL;

-- ============================================================================
-- 4. sent_slots.scanned_at
-- ============================================================================
ALTER TABLE public.sent_slots
  ADD COLUMN IF NOT EXISTS scanned_at timestamptz;

COMMIT;
