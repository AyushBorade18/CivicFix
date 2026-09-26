-- Auth foundation: CivicFix users, their ward/department scope, and report
-- ownership. Additive only - no existing row is changed or removed. Existing
-- synthetic reports keep reporter_user_id = NULL (they predate accounts).
-- Idempotent, so re-running it on an already-migrated database is a no-op.

CREATE TABLE IF NOT EXISTS users (
  id               bigserial PRIMARY KEY,
  -- The identity provider's subject ("sub" claim). The only thing a token
  -- is trusted for; role and scope always come from this database.
  external_auth_id text NOT NULL UNIQUE,
  email            text,
  display_name     text,
  role             text NOT NULL DEFAULT 'citizen'
                   CHECK (role IN ('citizen', 'ward_officer', 'department_officer', 'system_admin')),
  is_active        boolean NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_wards (
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  ward_id int    NOT NULL REFERENCES wards(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, ward_id)
);

-- Department names are the values of app.core.routing.AGENCY_MAP (the only
-- department concept the system has); app/users.py validates against it.
CREATE TABLE IF NOT EXISTS user_departments (
  user_id    bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  department text   NOT NULL,
  PRIMARY KEY (user_id, department)
);

ALTER TABLE reports ADD COLUMN IF NOT EXISTS reporter_user_id bigint REFERENCES users(id);
CREATE INDEX IF NOT EXISTS reports_reporter_user_id_idx ON reports (reporter_user_id);
