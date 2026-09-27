-- LLM triage fallback (app/nlp/triage.py). Additive only.

-- Verdict, reason, model and prompt version for reports the classifier
-- couldn't place. NULL = triage never ran (classifier was confident).
ALTER TABLE reports ADD COLUMN IF NOT EXISTS triage jsonb;

-- A report triaged as spam gets its own issue, held off every board and
-- never joined by real reports, until staff release it. Nothing is deleted.
ALTER TABLE issues ADD COLUMN IF NOT EXISTS held_as_spam boolean NOT NULL DEFAULT false;
