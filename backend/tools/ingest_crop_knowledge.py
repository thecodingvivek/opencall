"""Idempotently embed and upsert reviewed crop guidance into Supabase Postgres."""
import json
from pathlib import Path

from fastembed import TextEmbedding

from app.core.postgres import get_pool
from tools.crop_knowledge import MODEL_NAME

SEED = Path(__file__).resolve().parents[1] / "data" / "crop_knowledge_seed.json"
FIELDS = ("crop", "problem", "symptoms", "cause", "fertilizer", "treatment", "dosage", "safety_note")


def passage(row: dict) -> str:
    return "\n".join(f"{field}: {row[field]}" for field in FIELDS) + "\nregion: " + ", ".join(row["region"])


def vector_literal(values) -> str:
    values = [float(value) for value in values]
    if len(values) != 384 or any(not (-1e4 < value < 1e4) for value in values):
        raise ValueError("Unexpected embedding dimensions or values")
    return "[" + ",".join(format(value, ".8g") for value in values) + "]"


def ingest() -> int:
    rows = json.loads(SEED.read_text())
    model = TextEmbedding(model_name=MODEL_NAME)
    vectors = list(model.embed([passage(row) for row in rows]))
    with get_pool().connection() as conn:
        with conn.transaction():
            conn.execute("DELETE FROM opencall.crop_knowledge WHERE knowledge_key LIKE 'seed-v1:%'")
            for row, vector in zip(rows, vectors, strict=True):
                conn.execute("""
                    INSERT INTO opencall.crop_knowledge
                      (crop, problem, symptoms, cause, fertilizer, treatment, dosage,
                       safety_note, region, source_url, knowledge_key, embedding)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::extensions.vector(384))
                    ON CONFLICT (knowledge_key) DO UPDATE SET
                      crop=EXCLUDED.crop, problem=EXCLUDED.problem, symptoms=EXCLUDED.symptoms,
                      cause=EXCLUDED.cause, fertilizer=EXCLUDED.fertilizer,
                      treatment=EXCLUDED.treatment, dosage=EXCLUDED.dosage,
                      safety_note=EXCLUDED.safety_note, region=EXCLUDED.region,
                      source_url=EXCLUDED.source_url, embedding=EXCLUDED.embedding
                """, (*(row[field] for field in FIELDS), row["region"], row["source_url"],
                      "seed-v1:" + row["knowledge_key"], vector_literal(vector)))
    return len(rows)


if __name__ == "__main__":
    print(f"Upserted {ingest()} sourced crop knowledge records using {MODEL_NAME}.")
