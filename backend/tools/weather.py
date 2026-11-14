"""Current, forecast and historical weather from Open-Meteo."""
import asyncio
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import json
import logging
import re
from zoneinfo import ZoneInfo

import aiohttp
from livekit.agents import ToolError, function_tool

from app.services.agent_steps import send_step

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
EARLIEST_DATE = date(1940, 1, 1)
MAX_DAYS = 366
HOURLY = "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m"
DAILY = "temperature_2m_min,temperature_2m_max,precipitation_sum,weather_code,wind_speed_10m_max"
WMO = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Freezing fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle", 56: "Light freezing drizzle",
    57: "Dense freezing drizzle", 61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain", 71: "Light snow", 73: "Moderate snow",
    75: "Heavy snow", 77: "Snow grains", 80: "Light rain showers", 81: "Moderate rain showers",
    82: "Heavy rain showers", 85: "Light snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with light hail", 99: "Thunderstorm with heavy hail",
}


def _now(zone: ZoneInfo) -> datetime:
    return datetime.now(zone)


async def _get(client, url: str, params: dict) -> dict:
    async with client.get(url, params=params) as response:
        response.raise_for_status()
        data = await response.json()
        if not isinstance(data, dict) or data.get("error"):
            raise ToolError("Weather provider could not serve that location or period. Try a narrower request.")
        return data


async def _location(client, location: str) -> dict:
    parts = [part.strip() for part in location.split(",") if part.strip()]
    if not parts or len(location) > 200:
        raise ToolError("Provide a city, optionally followed by its country, such as Hyderabad, India.")
    data = await _get(client, GEOCODING_URL, {"name": parts[0], "count": 10, "language": "en", "format": "json"})
    results = data.get("results") or []
    if len(parts) > 1:
        results = [result for result in results if all(
            (hint.casefold() == result.get("country_code", "").casefold() if len(hint) == 2 else
             hint.casefold() in " ".join(str(result.get(key, "")) for key in
                ("name", "admin1", "admin2", "country", "country_code")).casefold())
            for hint in parts[1:])]
    if not results:
        raise ToolError("Location not found. Ask for the city and country, then try again.")
    return results[0]


def _parse(value: str, now: datetime) -> tuple[datetime, bool]:
    value = value.strip()
    relative = value.lower()
    if relative == "now":
        return now, True
    offsets = {"today": 0, "tomorrow": 1, "yesterday": -1}
    if relative in offsets:
        return datetime.combine(now.date() + timedelta(days=offsets[relative]), time.min, now.tzinfo), False
    match = re.fullmatch(r"([+-])(\d{1,4})([hd])", relative)
    if match:
        amount = int(match[2]) * (1 if match[1] == "+" else -1)
        if match[3] == "d":
            return datetime.combine(now.date() + timedelta(days=amount), time.min, now.tzinfo), False
        return datetime.fromtimestamp(now.timestamp() + amount * 3600, now.tzinfo), True
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return datetime.combine(date.fromisoformat(value), time.min, now.tzinfo), False
        if "T" not in value:
            raise ValueError("Expected ISO time")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=now.tzinfo)
            if parsed.astimezone(timezone.utc).astimezone(now.tzinfo).replace(tzinfo=None) != parsed.replace(tzinfo=None):
                raise ValueError("Nonexistent local time")
        return parsed.astimezone(now.tzinfo), True
    except (ValueError, OverflowError):
        raise ToolError("Use a valid local ISO date/time, now, today, tomorrow, yesterday, or offsets like +3h and +7d.") from None


def _window(start: str, end: str | None, now: datetime) -> tuple[datetime, datetime, bool]:
    begin, start_has_time = _parse(start, now)
    finish, end_has_time = _parse(end, now) if end else (begin, start_has_time)
    if not end_has_time:
        finish = datetime.combine(finish.date(), time.max, now.tzinfo)
    if finish.timestamp() < begin.timestamp():
        raise ToolError("The end must be at or after the start.")
    if begin.date() < EARLIEST_DATE:
        raise ToolError("Historical weather is available from 1940-01-01 onward.")
    latest = now.date() + timedelta(days=15)
    if finish.date() > latest:
        raise ToolError(f"Forecasts currently extend only through {latest.isoformat()} in this location. Do not guess later weather.")
    if (finish.date() - begin.date()).days + 1 > MAX_DAYS:
        raise ToolError("Request at most 366 days at a time. Ask the user to narrow a longer period.")
    return begin, finish, start_has_time or end_has_time


def _value(block: dict, field: str, index: int):
    values = block.get(field) or []
    return values[index] if index < len(values) else None


def _records(data: dict, begin: datetime, finish: datetime, hourly: bool) -> list[dict]:
    block = data.get("hourly" if hourly else "daily") or {}
    records = []
    for index, stamp in enumerate(block.get("time", [])):
        if hourly:
            local = datetime.fromtimestamp(stamp, begin.tzinfo)
            first_hour = begin.replace(minute=0, second=0, microsecond=0)
            if not first_hour.timestamp() <= local.timestamp() <= finish.timestamp():
                continue
            record = {"time": local.isoformat(timespec="minutes"),
                "temperature_c": _value(block, "temperature_2m", index),
                "humidity_percent": _value(block, "relative_humidity_2m", index),
                "precipitation_mm": _value(block, "precipitation", index),
                "wind_kmh": _value(block, "wind_speed_10m", index)}
        else:
            if not begin.date().isoformat() <= stamp <= finish.date().isoformat():
                continue
            record = {"date": stamp, "min_c": _value(block, "temperature_2m_min", index),
                "max_c": _value(block, "temperature_2m_max", index),
                "precipitation_mm": _value(block, "precipitation_sum", index),
                "wind_kmh": _value(block, "wind_speed_10m_max", index)}
        code = _value(block, "weather_code", index)
        record["conditions"] = WMO.get(code, f"Weather code {code}") if code is not None else None
        if any(value is not None for key, value in record.items() if key not in {"time", "date"}):
            records.append(record)
    return records


def _summary(records: list[dict], hourly: bool) -> dict:
    def values(key):
        return [row[key] for row in records if isinstance(row.get(key), (int, float))]
    lows, highs = values("temperature_c" if hourly else "min_c"), values("temperature_c" if hourly else "max_c")
    rain, wind = values("precipitation_mm"), values("wind_kmh")
    return {"min_c": min(lows) if lows else None, "max_c": max(highs) if highs else None,
            "precipitation_mm": round(sum(rain), 2) if rain else None,
            "precipitation_data_points": len(rain), "max_wind_kmh": max(wind) if wind else None,
            "common_conditions": [condition for condition, _ in Counter(
                row["conditions"] for row in records if row["conditions"]).most_common(3)]}


async def weather_data(location: str, start: str = "now", end: str | None = None) -> dict:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as client:
        city = await _location(client, location)
        zone = ZoneInfo(city.get("timezone", "UTC"))
        now = _now(zone)
        base = {"latitude": city["latitude"], "longitude": city["longitude"], "timezone": str(zone),
                "temperature_unit": "celsius", "wind_speed_unit": "kmh", "precipitation_unit": "mm"}
        result = {"source": "Open-Meteo", "attribution_url": "https://open-meteo.com/",
                  "location": ", ".join(filter(None, [city["name"], city.get("admin1"), city.get("country")])),
                  "timezone": str(zone), "retrieved_at": now.isoformat(timespec="minutes")}
        if start.strip().lower() == "now" and end is None:
            data = await _get(client, FORECAST_URL, {**base, "current": HOURLY})
            current = data.get("current") or {}
            if current.get("temperature_2m") is None:
                raise ToolError("Current weather is unavailable for this location. Try today's daily weather instead.")
            result.update(resolution="current", data_kind="current_model_estimate", current={
                "time": current.get("time"), "temperature_c": current["temperature_2m"],
                "humidity_percent": current.get("relative_humidity_2m"), "precipitation_mm": current.get("precipitation"),
                "wind_kmh": current.get("wind_speed_10m"), "conditions": WMO.get(current.get("weather_code"))})
            return result
        begin, finish, hourly = _window(start, end, now)
        cutoff = now.date() - timedelta(days=5)
        requests, sources = [], []
        for url, first, last, label in [
            (ARCHIVE_URL, begin.date(), min(finish.date(), cutoff), "historical_reanalysis"),
            (FORECAST_URL, max(begin.date(), cutoff + timedelta(days=1)), finish.date(), "recent_or_forecast_model"),
        ]:
            if first > last:
                continue
            params = {**base, "start_date": first.isoformat(), "end_date": last.isoformat(),
                      "hourly" if hourly else "daily": HOURLY if hourly else DAILY}
            if hourly:
                params["timeformat"] = "unixtime"
            requests.append(_get(client, url, params))
            sources.append(label)
        responses = await asyncio.gather(*requests)
        records = [row for data in responses for row in _records(data, begin, finish, hourly)]
        if not records:
            raise ToolError("Weather data is unavailable for that period. Try different dates; do not infer missing weather.")
        expected = (int((finish.timestamp() - begin.replace(minute=0, second=0, microsecond=0).timestamp()) // 3600) + 1
                    if hourly else (finish.date() - begin.date()).days + 1)
        limit = 24 if hourly else 14
        result.update(resolution="hourly" if hourly else "daily", data_kinds=sources,
            start=begin.isoformat(timespec="minutes"), end=finish.isoformat(timespec="minutes"),
            data_points=len(records), requested_data_points=expected, partial_data=len(records) < expected,
            summary=_summary(records, hourly), details_omitted=len(records) > limit)
        if hourly:
            result["note"] = "Hourly estimates; minute-specific requests use that hour. Precipitation covers the preceding hour."
        if len(records) <= limit:
            result["details"] = records
        else:
            result["note"] = result.get("note", "") + " Period summarized to limit response size; narrow the range for individual values."
        return result


@function_tool
async def get_weather(location: str, start: str = "now", end: str | None = None) -> str:
    """Get weather for a city; all dates and times are local to that city.

    Args:
        location: City, optionally with region or country.
        start: now, today, tomorrow, yesterday, ISO date/time, or relative +3h/+7d/-7d.
        end: Optional inclusive end in the same format. Omit for current weather or one day/hour.

    Time requests use hourly estimates; dates use daily data. History starts in 1940;
    forecasts reach 15 days ahead; maximum range is 366 days. Long ranges are summarized.
    """
    await send_step("weather_started", {"location": location})
    try:
        async with asyncio.timeout(20):
            data = await weather_data(location, start, end)
        await send_step("weather_completed", {"location": data.get("location", location)})
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    except ToolError:
        await send_step("weather_failed", {})
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError) as error:
        logging.getLogger(__name__).warning("Weather provider unavailable: %s", type(error).__name__)
        await send_step("weather_failed", {})
        raise ToolError("The weather service is temporarily unavailable. Please try again shortly.") from None
    except (ValueError, KeyError, TypeError, OverflowError) as error:
        logging.getLogger(__name__).warning("Weather provider response invalid: %s", type(error).__name__)
        await send_step("weather_failed", {})
        raise ToolError("The weather service returned incomplete data. Ask for a clearer location or time and try again.") from None
