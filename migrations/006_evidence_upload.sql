-- Evidence photos can now be uploaded from a file as well as captured live.
-- 'upload' rows carry the uploader's device location at upload time, not
-- the place the photo was taken, so reviewers must treat distance checks
-- on them accordingly. Additive and idempotent.
ALTER TABLE evidence DROP CONSTRAINT IF EXISTS evidence_capture_method_check;
ALTER TABLE evidence ADD CONSTRAINT evidence_capture_method_check CHECK (capture_method IN ('camera', 'upload'));
