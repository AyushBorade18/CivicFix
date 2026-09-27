-- PMC administrative hierarchy for RBAC: 5 zones -> 15 ward offices
-- (kshetriya karyalaya) -> the 58 electoral prabhags already in `wards`.
-- The prabhag -> office mapping is loaded from data/wards/ward_offices.csv
-- (app/ingest/ward_offices.py); `ward_office_verified` stays false until a
-- human confirms each row. Additive and idempotent.

CREATE TABLE IF NOT EXISTS zones (
  id   serial PRIMARY KEY,
  name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS ward_offices (
  id      serial PRIMARY KEY,
  name    text NOT NULL UNIQUE,
  zone_id int  NOT NULL REFERENCES zones(id)
);

ALTER TABLE wards ADD COLUMN IF NOT EXISTS ward_office_id int REFERENCES ward_offices(id);
ALTER TABLE wards ADD COLUMN IF NOT EXISTS ward_office_verified boolean NOT NULL DEFAULT false;

-- Zonal Deputy Commissioner: oversight of every ward office in their zone(s).
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
  CHECK (role IN ('citizen', 'ward_officer', 'zonal_commissioner', 'department_officer',
                  'system_admin', 'field_worker'));

-- A ward officer (Assistant Municipal Commissioner) is scoped to a ward
-- office; user_wards stays for one-off prabhag assignments.
CREATE TABLE IF NOT EXISTS user_ward_offices (
  user_id        bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  ward_office_id int    NOT NULL REFERENCES ward_offices(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, ward_office_id)
);

CREATE TABLE IF NOT EXISTS user_zones (
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  zone_id int    NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, zone_id)
);

-- Who did what: role/scope changes and officer actions on issues.
CREATE TABLE IF NOT EXISTS audit_log (
  id            bigserial PRIMARY KEY,
  actor_user_id bigint REFERENCES users(id) ON DELETE SET NULL,
  action        text NOT NULL,
  target_type   text NOT NULL,
  target_id     text NOT NULL,
  details       jsonb NOT NULL DEFAULT '{}'::jsonb,
  at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_log_at_idx ON audit_log (at DESC);
