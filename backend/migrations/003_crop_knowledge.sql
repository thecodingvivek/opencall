CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;
CREATE TABLE IF NOT EXISTS opencall.crop_knowledge (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  crop text NOT NULL,
  problem text NOT NULL,
  symptoms text NOT NULL,
  cause text NOT NULL DEFAULT '',
  fertilizer text NOT NULL DEFAULT '',
  treatment text NOT NULL DEFAULT '',
  dosage text NOT NULL DEFAULT '',
  safety_note text NOT NULL DEFAULT '',
  region text[] NOT NULL DEFAULT ARRAY['all']::text[],
  source_url text NOT NULL,
  knowledge_key text NOT NULL UNIQUE,
  embedding extensions.vector(384) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (cardinality(region) > 0)
);
CREATE INDEX IF NOT EXISTS crop_knowledge_embedding_hnsw_idx
  ON opencall.crop_knowledge USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS crop_knowledge_crop_idx ON opencall.crop_knowledge (lower(crop));
REVOKE ALL ON opencall.crop_knowledge FROM PUBLIC, anon, authenticated;
ALTER TABLE opencall.crop_knowledge ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION opencall.search_crop_knowledge(
  query_embedding extensions.vector(384),
  requested_crop text DEFAULT NULL,
  requested_region text DEFAULT NULL,
  result_limit integer DEFAULT 5
)
RETURNS TABLE (
  id bigint, crop text, problem text, symptoms text, cause text,
  fertilizer text, treatment text, dosage text, safety_note text,
  region text[], source_url text, similarity real
)
LANGUAGE sql STABLE SECURITY INVOKER
SET search_path = ''
AS $$
  SELECT k.id, k.crop, k.problem, k.symptoms, k.cause, k.fertilizer,
         k.treatment, k.dosage, k.safety_note, k.region, k.source_url,
         (1 - (k.embedding OPERATOR(extensions.<=>) query_embedding))::real AS similarity
  FROM opencall.crop_knowledge AS k
  WHERE (requested_crop IS NULL OR lower(k.crop) = lower(requested_crop))
    AND (requested_region IS NULL OR 'all' = ANY(k.region)
         OR EXISTS (SELECT 1 FROM unnest(k.region) AS r WHERE lower(r) = lower(requested_region)))
  ORDER BY k.embedding OPERATOR(extensions.<=>) query_embedding
  LIMIT LEAST(GREATEST(result_limit, 1), 8)
$$;
REVOKE ALL ON FUNCTION opencall.search_crop_knowledge(extensions.vector, text, text, integer) FROM PUBLIC, anon, authenticated;
