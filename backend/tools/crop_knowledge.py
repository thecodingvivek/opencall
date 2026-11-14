"""Multilingual semantic retrieval for sourced crop-health guidance."""
import asyncio
import logging

from livekit.agents import ToolError, function_tool

from app.core.postgres import get_pool
from app.services.agent_steps import send_step


def _query_crop_knowledge(query: str, crop: str | None, region: str | None):
    with get_pool().connection() as conn:
        return conn.execute("""
            WITH needle AS (SELECT websearch_to_tsquery('english', %s) AS terms),
                 candidates AS (
                   SELECT crop, problem, symptoms, cause, fertilizer, treatment,
                          dosage, safety_note, region, source_url,
                          to_tsvector('english', concat_ws(' ', crop, problem, symptoms, cause)) AS document
                   FROM opencall.crop_knowledge
                   WHERE (%s::text IS NULL OR lower(crop) = lower(%s::text))
                     AND (%s::text IS NULL OR 'all' = ANY(region)
                          OR EXISTS (SELECT 1 FROM unnest(region) AS r WHERE lower(r) = lower(%s::text)))
                 )
            SELECT crop, problem, symptoms, cause, fertilizer, treatment, dosage, safety_note, region, source_url
            FROM candidates CROSS JOIN needle
            WHERE numnode(terms) > 0 AND document @@ terms
            ORDER BY ts_rank(document, terms) DESC
            LIMIT 5
        """, (query, crop, crop, region, region)).fetchall()


@function_tool
async def search_crop_knowledge(query: str, crop: str | None = None, region: str | None = None) -> str:
    """Search sourced crop, pest, disease and fertilizer guidance by text.

    Args:
        query: Crop problem, symptoms, or farming question.
        crop: Optional crop name, e.g. tomato or rice.
        region: Optional Indian state or region.
    """
    query = " ".join(query.split())
    crop = " ".join(crop.split()) if crop else None
    region = " ".join(region.split()) if region else None
    if not 3 <= len(query) <= 1000 or crop and len(crop) > 80 or region and len(region) > 100:
        raise ToolError("Give a crop-health question up to 1000 characters and shorter optional crop and region names.")
    await send_step("crop_search_started", {"crop": crop})
    try:
        rows = await asyncio.to_thread(_query_crop_knowledge, query, crop, region)
    except Exception as error:
        logging.getLogger(__name__).warning("Crop knowledge search failed: %s", type(error).__name__)
        await send_step("crop_search_failed", {})
        raise ToolError("Crop guidance search is unavailable. Do not guess a diagnosis or treatment.") from None
    await send_step("crop_search_completed", {"matches": len(rows)})
    if not rows:
        raise ToolError("No matching sourced crop guidance was found. Ask for more symptoms or recommend a local KVK/agricultural officer.")
    return "\n\n".join(
        f"Crop: {row['crop']}\nProblem: {row['problem']}\nSymptoms: {row['symptoms']}\nCause: {row['cause']}\n"
        f"Fertilizer: {row['fertilizer']}\nTreatment: {row['treatment']}\nDosage: {row['dosage']}\n"
        f"Safety: {row['safety_note']}\nRegion: {', '.join(row['region'])}\nSource: {row['source_url']}"
        for row in rows
    )
