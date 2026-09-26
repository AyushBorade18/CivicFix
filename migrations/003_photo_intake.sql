-- Photo intake checks (app/nlp/photo_validate.py). These were first added to
-- schema.sql only, which never reaches an existing database. Additive only.

ALTER TABLE reports ADD COLUMN IF NOT EXISTS photo_checks jsonb;

-- One row per uploaded photo, written at upload time (before any report
-- exists), so the signals read from the original bytes survive the strip.
CREATE TABLE IF NOT EXISTS photo_uploads (
  filename     text PRIMARY KEY,
  uploaded_at  timestamptz NOT NULL DEFAULT now(),
  checks       jsonb NOT NULL
);
