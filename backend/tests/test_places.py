import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from livekit.agents import ToolError
from pydantic import SecretStr

from tools.places import GEOCODING_URL, PLACES_URL, search_farming_places


class PlacesTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings = Mock(geoapify_api_key=SecretStr('test-key'))
        self.get = AsyncMock(side_effect=[
            {'results': [{'lat': 16.75, 'lon': 81.68, 'formatted': 'Tanuku, AP, India'}]},
            {'features': [
                {'properties': {'name': 'Farm store', 'formatted': 'Tanuku',
                                'contact': {'phone': '123'}, 'distance': 350}},
                {'properties': {'formatted': 'Unnamed place'}},
            ]},
        ])
        for patcher in (patch('tools.places.get_settings', return_value=self.settings),
                        patch('tools.places._get', self.get),
                        patch('tools.places.send_step', new_callable=AsyncMock)):
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_nearby_search_uses_coordinates_and_preserves_listing_limits(self):
        result = json.loads(await search_farming_places('Tanuku, Andhra Pradesh', 'farm_supply'))
        self.assertEqual(result['searched_near'], 'Tanuku, AP, India')
        self.assertEqual(result['source'], 'Geoapify')
        self.assertEqual(result['places'], [{'name': 'Farm store', 'address': 'Tanuku',
                                            'phone': '123', 'distance_m': 350}])
        self.assertIn('stock are unverified', result['note'])
        self.assertEqual(self.get.await_args_list[0].args[1], GEOCODING_URL)
        self.assertEqual(self.get.await_args_list[1].args[1], PLACES_URL)
        params = self.get.await_args_list[1].args[2]
        self.assertEqual(params['categories'], 'commercial.agrarian')
        self.assertEqual(params['filter'], 'circle:81.68,16.75,10000')
        self.assertEqual(params['limit'], 5)
        self.assertNotIn('apiKey', params)

    async def test_name_filter_and_no_results(self):
        self.get.side_effect = [{'results': [{'lat': 1, 'lon': 2}]}, {'features': []}]
        result = json.loads(await search_farming_places('Some town', 'garden', 'Green Gardens'))
        self.assertEqual(result['places'], [])
        self.assertEqual(self.get.await_args_list[1].args[2]['name'], 'Green Gardens')
        self.assertEqual(self.get.await_args_list[1].args[2]['categories'], 'commercial.garden')

    async def test_missing_key_or_location_does_not_call_provider(self):
        self.settings.geoapify_api_key = None
        with self.assertRaises(ToolError):
            await search_farming_places('Tanuku', 'farm_supply')
        with self.assertRaises(ToolError):
            await search_farming_places('', 'farm_supply')
        self.get.assert_not_awaited()

    async def test_unknown_location_and_provider_timeout(self):
        self.get.side_effect = [{'results': []}]
        with self.assertRaisesRegex(ToolError, 'Location not found'):
            await search_farming_places('Unknown place', 'agriculture_office')
        self.get.side_effect = asyncio.TimeoutError()
        with self.assertRaisesRegex(ToolError, 'unavailable'):
            await search_farming_places('Tanuku', 'farm_supply')

    async def test_malformed_provider_response_does_not_claim_no_places(self):
        self.get.side_effect = [{'results': [{'lat': 1, 'lon': 2}]}, {}]
        with self.assertRaisesRegex(ToolError, 'unavailable'):
            await search_farming_places('Tanuku', 'farm_supply')
