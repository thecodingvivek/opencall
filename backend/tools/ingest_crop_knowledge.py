"""Idempotently upsert reviewed crop guidance without an embedding model.

Apply migration 006 before inserting new records into an existing database.
"""
import json
from pathlib import Path

from app.core.postgres import get_pool

SEED = Path(__file__).resolve().parents[1] / "data" / "crop_knowledge_seed.json"
FIELDS = ("crop", "problem", "symptoms", "cause", "fertilizer", "treatment", "dosage", "safety_note")


def ingest() -> int:
    rows = json.loads(SEED.read_text())
    with get_pool().connection() as conn:
        with conn.transaction():
            for row in rows:
                conn.execute("""
                    INSERT INTO opencall.crop_knowledge
                      (crop, problem, symptoms, cause, fertilizer, treatment, dosage,
                       safety_note, region, source_url, knowledge_key)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (knowledge_key) DO UPDATE SET
                      crop=EXCLUDED.crop, problem=EXCLUDED.problem, symptoms=EXCLUDED.symptoms,
                      cause=EXCLUDED.cause, fertilizer=EXCLUDED.fertilizer,
                      treatment=EXCLUDED.treatment, dosage=EXCLUDED.dosage,
                      safety_note=EXCLUDED.safety_note, region=EXCLUDED.region,
                      source_url=EXCLUDED.source_url
                """, (*(row[field] for field in FIELDS), row["region"], row["source_url"],
                      "seed-v1:" + row["knowledge_key"]))
    return len(rows)


if __name__ == "__main__":
    print(f"Upserted {ingest()} sourced crop knowledge records.")
