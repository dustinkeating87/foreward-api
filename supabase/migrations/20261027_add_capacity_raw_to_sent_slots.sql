-- Migration: 20261027_add_capacity_raw_to_sent_slots
-- Adds sent_slots.capacity_raw (text, nullable).
-- GolfNow fires store the raw playerRule value(s) the capacity match was decided on,
-- comma-joined (e.g. "TwoThreeFour" or "One,OneToFour"). Other platforms leave it NULL.
-- Lets a fire be audited after the fact (ClickUp wdpu2yqvk7).

ALTER TABLE sent_slots
  ADD COLUMN IF NOT EXISTS capacity_raw text;

NOTIFY pgrst, 'reload schema';
