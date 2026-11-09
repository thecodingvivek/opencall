"""Multilingual semantic retrieval for sourced crop-health guidance."""
from functools import lru_cache
import asyncio
import logging

from fastembed import TextEmbedding
from livekit.agents import ToolError, function_tool

from app.core.postgres import get_pool
from app.services.agent_steps import send_step

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    return TextEmbedding(model_name=MODEL_NAME)


def _embed(query: str) -> list[float]:
    return list(next(_model().embed([query])))


@function_tool
async def search_crop_knowledge(query: str, crop: str | None = None, region: str | None = None) -> str:
    """Find sourced crop disease, pest, and nutrient guidance by symptoms or question.

    Args:
        query: Crop problem, observed symptoms, or farming question in the farmer's own words.
        crop: Optional crop name, such as tomato, chilli, rice, or wheat.
        region: Optional Indian state or region to prefer local guidance.
    """
    query = " ".join(query.split())
    crop = " ".join(crop.split()) if crop else None
    region = " ".join(region.split()) if region else None
    if not 3 <= len(query) <= 1000 or crop and len(crop) > 80 or region and len(region) > 100:
        raise ToolError("Give a crop-health question up to 1000 characters and shorter optional crop and region names.")
    await send_step("crop_search_started", {"crop": crop})
    try:
        embedding = await asyncio.to_thread(_embed, query)
        with get_pool().connection() as conn:
            rows = conn.execute("""
                SELECT * FROM opencall.search_crop_knowledge(
                  %s::extensions.vector(384), %s, %s, 5
                ) WHERE similarity >= 0.35
            """, (embedding, crop, region)).fetchall()
    except Exception as error:
        logging.getLogger(__name__).warning("Crop knowledge search failed: %s", type(error).__name__)
        await send_step("crop_search_failed", {})
        raise ToolError("Crop guidance search is unavailable. Do not guess a diagnosis or treatment.") from None
    await send_step("crop_search_completed", {"matches": len(rows)})
    if not rows:
        raise ToolError("No sufficiently similar sourced crop guidance was found. Ask for more symptoms or recommend a local KVK/agricultural officer.")
    return "\n\n".join(
        f"Crop: {row['crop']}\nProblem: {row['problem']}\nSymptoms: {row['symptoms']}\nCause: {row['cause']}\n"
        f"Fertilizer: {row['fertilizer']}\nTreatment: {row['treatment']}\nDosage: {row['dosage']}\n"
        f"Safety: {row['safety_note']}\nRegion: {', '.join(row['region'])}\nSource: {row['source_url']}"
        for row in rows
    )
