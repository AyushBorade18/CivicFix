-- Location-verified evidence: in-app camera photos with the device's own
-- location reading, for citizens (before) and field workers (after).
-- Evidence is a verification signal for human review, never proof, and its
-- absence never marks a report false. Additive only; existing rows untouched.

-- Field workers capture resolution evidence for issues assigned to them.
-- Not a staff role: they see assigned issues only, never the priority queue.
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
  CHECK (role IN ('citizen', 'ward_officer', 'department_officer', 'system_admin', 'field_worker'));

-- Work assignment is recorded beside the existing status (open/closed/
-- reopened) rather than as new status values, because the matcher,
-- recurrence check and public filters all key off those three.
ALTER TABLE issues ADD COLUMN IF NOT EXISTS assigned_worker_id bigint REFERENCES users(id);
ALTER TABLE issues ADD COLUMN IF NOT EXISTS assigned_at timestamptz;
-- Fixed when the issue is closed, so a later policy change doesn't move an
-- open window. NULL for issues closed before this migration (no window).
ALTER TABLE issues ADD COLUMN IF NOT EXISTS reverification_due_at timestamptz;

-- Fixed at report time for the same reason. NULL on pre-existing reports.
ALTER TABLE reports ADD COLUMN IF NOT EXISTS evidence_due_at timestamptz;

CREATE TABLE IF NOT EXISTS evidence (
  id                   bigserial PRIMARY KEY,
  issue_id             bigint NOT NULL REFERENCES issues(id),
  report_id            bigint REFERENCES reports(id),   -- set for citizen evidence
  submitted_by         bigint NOT NULL REFERENCES users(id),
  actor_type           text NOT NULL CHECK (actor_type IN ('citizen', 'worker')),
  evidence_type        text NOT NULL CHECK (evidence_type IN ('initial_report', 'resolution')),
  capture_method       text NOT NULL DEFAULT 'camera' CHECK (capture_method = 'camera'),
  -- Private file under data/evidence/, served only through an authorized
  -- endpoint - never a public URL.
  file_key             text NOT NULL,
  mime_type            text NOT NULL,
  byte_size            int  NOT NULL,
  sha256               text NOT NULL,
  -- Device-reported location and its reported accuracy radius.
  geom                 geometry(Point,4326) NOT NULL,
  accuracy_m           real NOT NULL CHECK (accuracy_m >= 0),
  -- Client clock: a signal, not a source of truth.
  captured_at          timestamptz,
  location_captured_at timestamptz,
  -- Server clock.
  submitted_at         timestamptz NOT NULL DEFAULT now(),
  -- Metres to the issue's location as it stood at submission; NULL if the
  -- issue had no location.
  distance_from_issue_m real,
  review_status        text NOT NULL DEFAULT 'pending_review'
                       CHECK (review_status IN ('pending_review', 'verified', 'review_required')),
  reviewed_by          bigint REFERENCES users(id),
  reviewed_at          timestamptz,
  review_note          text,
  -- Generated on the device per capture, so a retried upload after a
  -- network drop returns the first row instead of creating a duplicate.
  client_submission_id uuid NOT NULL UNIQUE,
  user_agent           text
);
CREATE INDEX IF NOT EXISTS evidence_issue_id_idx  ON evidence (issue_id);
CREATE INDEX IF NOT EXISTS evidence_report_id_idx ON evidence (report_id);
-- One initial photo per report; a retake happens on the device before upload.
CREATE UNIQUE INDEX IF NOT EXISTS evidence_one_initial_per_report
  ON evidence (report_id) WHERE evidence_type = 'initial_report';

-- The no-photo path: staff confirm a report through another channel.
CREATE TABLE IF NOT EXISTS alternative_verifications (
  id            bigserial PRIMARY KEY,
  report_id     bigint NOT NULL REFERENCES reports(id),
  channel       text NOT NULL CHECK (channel IN ('phone', 'whatsapp', 'in_person', 'other')),
  status        text NOT NULL DEFAULT 'initiated'
                CHECK (status IN ('initiated', 'confirmed', 'not_confirmed', 'unreachable')),
  initiated_by  bigint NOT NULL REFERENCES users(id),
  initiated_at  timestamptz NOT NULL DEFAULT now(),
  completed_by  bigint REFERENCES users(id),
  completed_at  timestamptz,
  notes         text
);
CREATE INDEX IF NOT EXISTS alternative_verifications_report_id_idx ON alternative_verifications (report_id);
