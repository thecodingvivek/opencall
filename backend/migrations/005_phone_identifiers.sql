-- Replace legacy placeholders while preserving real numbers and existing numeric IDs.
DO $$
DECLARE account_id uuid;
BEGIN
  FOR account_id IN SELECT id FROM opencall.users
      WHERE generated_phone_identifier LIKE 'placeholder-%' LOOP
    LOOP
      BEGIN
        UPDATE opencall.users
        SET generated_phone_identifier = (1000000000 + floor(random() * 9000000000))::bigint::text,
            updated_at = now()
        WHERE id = account_id AND generated_phone_identifier LIKE 'placeholder-%';
        EXIT;
      EXCEPTION WHEN unique_violation THEN
        NULL;
      END;
    END LOOP;
  END LOOP;
END $$;
