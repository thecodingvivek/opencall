import asyncio
from datetime import date, datetime, timedelta
import json
import unittest
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import aiohttp
from livekit.agents import ToolError

from tools.weather import ARCHIVE_URL, FORECAST_URL, GEOCODING_URL, _records, _window, get_weather

CITY = {'name': 'Hyderabad', 'admin1': 'Telangana', 'country': 'India',
        'country_code': 'IN', 'latitude': 17.38, 'longitude': 78.48, 'timezone': 'Asia/Kolkata'}
NOW = datetime(2026, 10, 28, 0, 30, tzinfo=ZoneInfo('Asia/Kolkata'))


def daily(params, missing=False):
    begin, end = date.fromisoformat(params['start_date']), date.fromisoformat(params['end_date'])
    times = [(begin + timedelta(days=index)).isoformat() for index in range((end - begin).days + 1)]
    n = len(times)
    return {'daily': {'time': times, 'temperature_2m_min': [None if missing else 20] * n,
                     'temperature_2m_max': [None if missing else 30] * n,
                     'precipitation_sum': [None if missing else 1] * n,
                     'weather_code': [None if missing else 2] * n,
                     'wind_speed_10m_max': [None if missing else 10] * n}}


class WeatherTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.requests = []
        async def request(client, url, params):
            self.requests.append((url, params))
            if url == GEOCODING_URL:
                return {'results': [CITY]}
            if 'current' in params:
                return {'current': {'time': '2026-10-28T00:30', 'temperature_2m': 25,
                                   'weather_code': 0, 'precipitation': 0, 'wind_speed_10m': 5}}
            return daily(params)
        for patcher in [patch('tools.weather._get', side_effect=request),
                        patch('tools.weather._now', return_value=NOW)]:
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_current_weather_resolves_country_and_returns_source_and_units(self):
        result = json.loads(await get_weather('Hyderabad, IN'))
        self.assertEqual(result['timezone'], 'Asia/Kolkata')
        self.assertEqual(result['source'], 'Open-Meteo')
        self.assertEqual(result['current']['temperature_c'], 25)
        self.assertEqual(result['current']['conditions'], 'Clear')
        self.assertEqual(self.requests[-1][1]['temperature_unit'], 'celsius')

    async def test_tomorrow_uses_city_local_date(self):
        result = json.loads(await get_weather('Hyderabad', 'tomorrow'))
        self.assertEqual(result['details'][0]['date'], '2026-10-29')
        self.assertEqual(result['resolution'], 'daily')

    async def test_mixed_history_and_forecast_is_split_without_missing_dates(self):
        result = json.loads(await get_weather('Hyderabad', '2026-10-20', '2026-10-29'))
        self.assertEqual(result['data_points'], 10)
        self.assertFalse(result['partial_data'])
        self.assertEqual(result['summary']['precipitation_mm'], 10)
        self.assertEqual({url for url, _ in self.requests}, {GEOCODING_URL, ARCHIVE_URL, FORECAST_URL})
        archive = next(params for url, params in self.requests if url == ARCHIVE_URL)
        forecast = next(params for url, params in self.requests if url == FORECAST_URL)
        self.assertEqual(archive['end_date'], '2026-10-23')
        self.assertEqual(forecast['start_date'], '2026-10-24')

    async def test_long_period_returns_summary_instead_of_large_tool_output(self):
        result = json.loads(await get_weather('Hyderabad', '2025-01-01', '2025-12-31'))
        self.assertEqual(result['data_points'], 365)
        self.assertTrue(result['details_omitted'])
        self.assertNotIn('details', result)
        self.assertLess(len(json.dumps(result)), 1600)

    async def test_future_dates_and_reversed_or_excessive_ranges_are_rejected(self):
        for start, end in [('2026-11-13', None), ('1939-12-31', None),
                           ('tomorrow', 'yesterday'), ('2024-01-01', '2025-12-31'), ('not-a-date', None)]:
            with self.subTest(start=start, end=end), self.assertRaises(ToolError):
                await get_weather('Hyderabad', start, end)
        self.assertTrue(all(url == GEOCODING_URL for url, _ in self.requests))

    async def test_unknown_location_and_mismatched_country_are_not_guessed(self):
        with patch('tools.weather._get', new=AsyncMock(return_value={'results': []})):
            with self.assertRaises(ToolError):
                await get_weather('unknown city')
        with self.assertRaises(ToolError):
            await get_weather('Hyderabad, US')

    async def test_provider_errors_are_safe_tool_errors(self):
        for error in [aiohttp.ClientConnectionError('private transport detail'), asyncio.TimeoutError()]:
            with patch('tools.weather._get', new=AsyncMock(side_effect=error)):
                with self.assertRaisesRegex(ToolError, 'temporarily unavailable'):
                    await get_weather('Hyderabad')

    async def test_missing_weather_is_not_reported_as_zero(self):
        async def request(client, url, params):
            return {'results': [CITY]} if url == GEOCODING_URL else daily(params, missing=True)
        with patch('tools.weather._get', side_effect=request):
            with self.assertRaisesRegex(ToolError, 'unavailable for that period'):
                await get_weather('Hyderabad', 'tomorrow')

    async def test_hourly_selection_preserves_timezone_and_minutes_use_that_hour(self):
        begin, finish, hourly = _window('2026-10-29T15:30', '2026-10-29T17:10', NOW)
        times = [datetime(2026, 10, 29, hour, tzinfo=NOW.tzinfo).timestamp() for hour in range(14, 19)]
        block = {'hourly': {'time': times, 'temperature_2m': [20, 21, 22, 23, 24], 'weather_code': [0]*5}}
        rows = _records(block, begin, finish, hourly)
        self.assertEqual([row['temperature_c'] for row in rows], [21, 22, 23])
        self.assertTrue(all(row['time'].endswith('+05:30') for row in rows))
        self.assertIsNone(rows[0]['precipitation_mm'])

    async def test_relative_hours_and_dst_offsets(self):
        begin, end, hourly = _window('now', '+3h', NOW)
        self.assertTrue(hourly)
        self.assertEqual(end.timestamp() - begin.timestamp(), 3 * 3600)
        new_york = datetime(2026, 10, 28, tzinfo=ZoneInfo('America/New_York'))
        begin, end, hourly = _window('2026-11-01T01:00-04:00', '2026-11-01T01:00-05:00', new_york)
        rows = _records({'hourly': {'time': [begin.timestamp(), end.timestamp()],
                                    'temperature_2m': [10, 11]}}, begin, end, hourly)
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['time'], rows[1]['time'])
