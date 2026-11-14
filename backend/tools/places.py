"""Find agriculture-related places near a caller-provided location."""
import asyncio
import json
import logging
from typing import Literal

import aiohttp
from livekit.agents import ToolError, function_tool

from app.core.config import get_settings
from app.services.agent_steps import send_step

GEOCODING_URL = "https://api.geoapify.com/v1/geocode/search"
PLACES_URL = "https://api.geoapify.com/v2/places"
CATEGORIES = {
    "farm_supply": "commercial.agrarian",
    "garden": "commercial.garden",
    "agriculture_office": "office.government.agriculture",
}


async def _get(client, url, params):
    async with client.get(url, params=params) as response:
        response.raise_for_status()
        return await response.json()


@function_tool
async def search_farming_places(
    location: str,
    kind: Literal["farm_supply", "garden", "agriculture_office"],
    name: str | None = None,
) -> str:
    """Find nearby farming-related places; listings do not confirm products or stock.

    Args:
        location: Caller-provided city, village, postcode, or address, preferably with region.
        kind: farm_supply for fertilizer, pesticide, seed or farm shops; garden for nurseries; agriculture_office for government agriculture offices.
        name: Optional exact business name to search for, not a product or category.
    """
    location = " ".join(location.split())
    name = " ".join(name.split()) if name else None
    if not 2 <= len(location) <= 200 or name and len(name) > 100 or kind not in CATEGORIES:
        raise ToolError("Provide a location, a supported place type, and an optional short business name.")
    api_key = get_settings().geoapify_api_key
    if not api_key or not api_key.get_secret_value().strip():
        raise ToolError("Farming place search is unavailable. Ask the user to try later.")
    await send_step("places_search_started", {})
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=12),
            headers={"x-api-key": api_key.get_secret_value()},
        ) as client:
            geocoded = await _get(client, GEOCODING_URL, {"text": location, "limit": 1, "format": "json"})
            if not isinstance(geocoded, dict) or not isinstance(geocoded.get("results"), list):
                raise ValueError("Invalid geocoding response")
            matches = geocoded["results"]
            if not matches:
                raise ToolError("Location not found. Ask for a clearer city, region, or postcode.")
            point = matches[0]
            if not isinstance(point, dict):
                raise ValueError("Invalid geocoding result")
            lat, lon = float(point["lat"]), float(point["lon"])
            if not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError("Invalid geocoding coordinates")
            params = {"categories": CATEGORIES[kind], "filter": f"circle:{lon},{lat},10000",
                      "bias": f"proximity:{lon},{lat}", "limit": 5}
            if name:
                params["name"] = name
            data = await _get(client, PLACES_URL, params)
            if not isinstance(data, dict) or not isinstance(data.get("features"), list):
                raise ValueError("Invalid places response")
    except ToolError:
        await send_step("places_search_failed", {})
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, TypeError, ValueError) as error:
        logging.getLogger(__name__).warning("Place search failed: %s", type(error).__name__)
        await send_step("places_search_failed", {})
        raise ToolError("Farming place search is unavailable. Do not invent listings; ask the user to try later.") from None
    results = []
    for feature in data["features"]:
        properties = feature.get("properties", {}) if isinstance(feature, dict) else {}
        if not isinstance(properties, dict) or not properties.get("name"):
            continue
        contact = properties.get("contact") if isinstance(properties.get("contact"), dict) else {}
        results.append({"name": properties["name"], "address": properties.get("formatted"),
                        "phone": contact.get("phone"), "distance_m": properties.get("distance")})
    await send_step("places_search_completed", {"matches": len(results)})
    return json.dumps({"source": "Geoapify", "searched_near": point.get("formatted", location),
                       "radius_km": 10, "places": results,
                       "note": "Listings may be incomplete or outdated. Product availability and stock are unverified; distances are from the resolved search location, not necessarily the caller."}, ensure_ascii=False)
