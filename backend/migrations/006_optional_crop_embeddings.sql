-- Keep existing vectors untouched while allowing new text-only crop records.
ALTER TABLE opencall.crop_knowledge ALTER COLUMN embedding DROP NOT NULL;
