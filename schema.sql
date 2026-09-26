-- WardSentry schema. Source of truth: ARCHITECTURE.md section 4.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

DO $$ BEGIN
  CREATE TYPE civic_category AS ENUM (
    'pothole_road', 'drainage_sewage', 'water_supply', 'streetlight',
    'garbage_waste', 'footpath', 'traffic_signage', 'other'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE severity_band AS ENUM ('cosmetic', 'moderate', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS wards (
  id     serial PRIMARY KEY,
  name   text NOT NULL,
  geom   geometry(MultiPolygon,4326),
  population int,
  area_sqkm  real
);

CREATE TABLE IF NOT EXISTS issues (
  id              bigserial PRIMARY KEY,
  category        civic_category NOT NULL,
  geom            geometry(Point,4326),
  ward_id         int REFERENCES wards(id),
  first_reported  timestamptz,
  last_reported   timestamptz,
  report_count    int NOT NULL DEFAULT 0,
  status          text NOT NULL DEFAULT 'open',
  closed_at       timestamptz,
  recurrence_count int NOT NULL DEFAULT 0,
  priority_score  real,
  priority_breakdown jsonb,
  embedding       vector(384),
  routed_agency   text,        -- deterministic category -> agency lookup, see app/core/routing.py
  routed_at       timestamptz
);

CREATE TABLE IF NOT EXISTS reports (
  id              bigserial PRIMARY KEY,
  raw_text        text NOT NULL,
  photo_url       text,
  reported_at     timestamptz NOT NULL,
  category        civic_category,
  category_conf   real,
  severity        severity_band,
  location_phrase text,
  geom            geometry(Point,4326),
  geom_confidence real,
  ward_id         int REFERENCES wards(id),
  embedding       vector(384),
  issue_id        bigint REFERENCES issues(id),
  is_synthetic    boolean NOT NULL DEFAULT false,
  language        text,  -- ISO 639-1 code from langdetect, NULL if undetectable; never assumed "en"
  translated_text text,  -- English translation used for classify/severity/location when language != "en"
  photo_severity_score real,       -- see app/nlp/photo_severity.py
  photo_severity_band  severity_band,
  photo_checks    jsonb            -- authenticity signals + encryption status, see app/nlp/photo_validate.py
);

-- One row per uploaded photo, written at upload time (before any report
-- exists), so the signals read from the original bytes survive the strip.
CREATE TABLE IF NOT EXISTS photo_uploads (
  filename     text PRIMARY KEY,
  uploaded_at  timestamptz NOT NULL DEFAULT now(),
  checks       jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS works (
  id              bigserial PRIMARY KEY,
  work_name       text NOT NULL,
  description     text,
  cost            numeric,
  status          text,
  sanctioned_on   date,
  completed_on    date,
  agency          text,
  constituency    text,
  category        civic_category,
  geom            geometry(Point,4326),
  ward_id         int REFERENCES wards(id),
  geom_confidence real,             -- 1.0 geocoded landmark; 0.5 ward-level (reviewed
                                    -- ward centroid or gazetteer locality); NULL no geom
  source_record_id text,            -- MPLADS workId
  embedding       vector(384)
);

CREATE TABLE IF NOT EXISTS matches (
  id              bigserial PRIMARY KEY,
  issue_id        bigint NOT NULL REFERENCES issues(id),
  work_id         bigint NOT NULL REFERENCES works(id),
  semantic_score  real NOT NULL,
  distance_m      real,             -- NULL when the match relies on ward-level
                                     -- spatial compatibility, not a real distance
  days_since_completion int,
  combined_score  real NOT NULL,
  match_reason    text NOT NULL,
  created_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS signals (
  id              bigserial PRIMARY KEY,
  issue_id        bigint REFERENCES issues(id),
  match_id        bigint REFERENCES matches(id),
  rule_name       text NOT NULL,
  explanation     text NOT NULL,
  source_record_ids jsonb NOT NULL,
  created_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feedback (
  id                 bigserial PRIMARY KEY,
  issue_id           bigint NOT NULL REFERENCES issues(id),
  resolved_confirmed boolean NOT NULL,
  comment            text,
  submitted_at       timestamptz NOT NULL DEFAULT now(),
  is_synthetic       boolean NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS sensitive_sites (
  id        bigserial PRIMARY KEY,
  name      text,
  kind      text NOT NULL,
  geom      geometry(Point,4326),
  source_id text UNIQUE  -- e.g. "node/123456" - preserves the OSM identifier
);

CREATE INDEX IF NOT EXISTS reports_geom_idx ON reports USING GIST (geom);
CREATE INDEX IF NOT EXISTS issues_geom_idx  ON issues  USING GIST (geom);
CREATE INDEX IF NOT EXISTS works_geom_idx   ON works   USING GIST (geom);
CREATE INDEX IF NOT EXISTS sensitive_sites_geom_idx ON sensitive_sites USING GIST (geom);
CREATE INDEX IF NOT EXISTS reports_embedding_idx ON reports USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS works_embedding_idx   ON works   USING ivfflat (embedding vector_cosine_ops);

-- Columns added after the first release; lets re-running this file migrate an existing database.
ALTER TABLE reports ADD COLUMN IF NOT EXISTS photo_checks jsonb;
