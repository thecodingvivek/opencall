# Agent tools

Tools available to the voice agent live in this folder. `AGENT_TOOLS` in
`__init__.py` registers them with LiveKit's `Agent`.

## Weather: `get_weather`

The assistant can check current weather, daily forecasts, hourly periods, and
historical weather using Open-Meteo. No API key is required for this local setup.
The public endpoint is for non-commercial use; see the provider's
[usage terms](https://open-meteo.com/en/terms).

The LLM chooses when to call the tool and supplies three arguments:

| Argument | Default | Meaning |
| --- | --- | --- |
| `location` | Required | City, optionally followed by region and country, e.g. `Hyderabad, India`. |
| `start` | `now` | Local date/time or a supported relative expression. |
| `end` | Omitted | Inclusive end of the requested range. Without an end, request one day/hour, or current weather for `now`. |

Accepted time formats:

- `now`, `today`, `tomorrow`, `yesterday`.
- `2026-10-29` for a complete local day.
- `2026-10-29T15:00` for a local hour. ISO UTC offsets are also accepted.
- `+3h`, `+7d`, `-7d` relative to the location's current time/date.

Examples:

```python
await get_weather("Hyderabad, India")                           # Current conditions
await get_weather("Hyderabad, India", "tomorrow")               # Tomorrow's daily weather
await get_weather("Hyderabad, India", "now", "+3h")             # Hourly estimates over the next three hours
await get_weather("Hyderabad, India", "today", "+6d")           # Seven days, inclusive
await get_weather("Paris, France", "2024-07-10T15:00")           # A historical local hour
await get_weather("London, GB", "2024-01-01", "2024-12-31")      # Historical year summary
```

## Behavior and limits

The tool geocodes the city, resolves its timezone, and returns the resolved place
name so the assistant can state which location it checked. A supplied region or
country must match. If no match exists, the assistant asks for a clearer location.

- Current weather is a model estimate from the forecast API.
- Date-only requests return daily minimum/maximum temperature, precipitation,
  maximum wind speed and conditions.
- Requests containing times return hourly estimates with temperature, humidity,
  precipitation, wind and conditions. Minutes use the preceding whole-hour
  timestamp; this is not an exact minute-by-minute forecast. Hourly precipitation
  is the amount over the preceding hour.
- Temperatures are Celsius, precipitation millimeters, and wind kilometers/hour.
- Forecasts cover today through 15 days after today in the location's timezone.
- Historical dates start at January 1, 1940. Older periods use the archive's
  reanalysis data; the most recent five days use the forecast endpoint's recent
  model data. A range crossing that boundary is split and combined.
- Each lookup accepts up to 366 days. Longer requests must be narrowed or split
  into separate lookups. Weather outside the forecast horizon is not invented.
- Up to 14 daily or 24 hourly records are included. Longer periods return an
  aggregate summary and a note asking for a narrower range for individual values.
- Missing values stay missing. `partial_data` and precipitation sample counts
  help distinguish incomplete coverage from zero rain.
- Network calls have timeouts, and the whole tool execution is limited to 20
  seconds. Provider errors become safe `ToolError` messages for the agent.

Only weather query parameters go to Open-Meteo. The tool does not create
database tables or save weather results in the phonebook.

## Phoenix

Open `http://localhost:6006`, select `opencall`, and open a session trace.
An executed weather lookup appears as **`tool.get_weather`**, with span kind
**TOOL** and attribute `tool.name=get_weather`. Errors are marked on this span.

Tool arguments and output text are hidden by default. Set
`PHOENIX_CAPTURE_CONTENT=true` and restart the worker to inspect them. Tool span
names, kinds, latency, and error status remain visible without content capture.

Provider references: [forecast API](https://open-meteo.com/en/docs),
[historical API](https://open-meteo.com/en/docs/historical-weather-api),
[geocoding API](https://open-meteo.com/en/docs/geocoding-api).
