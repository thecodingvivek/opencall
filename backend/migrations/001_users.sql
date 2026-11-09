CREATE SCHEMA IF NOT EXISTS opencall;
CREATE TABLE IF NOT EXISTS opencall.users (
  id uuid PRIMARY KEY,
  firebase_uid text NOT NULL UNIQUE,
  display_name text,
  email text,
  phone_number text,
  phone_verified boolean NOT NULL DEFAULT false,
  generated_phone_identifier text UNIQUE,
  phonebook text NOT NULL DEFAULT '' CHECK (char_length(phonebook) <= 800),
  phonebook_revision bigint NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (phone_number IS NULL OR generated_phone_identifier IS NULL)
);
REVOKE ALL ON SCHEMA opencall FROM PUBLIC, anon, authenticated;
REVOKE ALL ON opencall.users FROM PUBLIC, anon, authenticated;
ALTER TABLE opencall.users ENABLE ROW LEVEL SECURITY;
