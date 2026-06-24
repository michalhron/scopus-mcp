"""Tests for ScopusClient.search_all — no live API calls.

Mocking strategy:
- start-based paging: patch search_scopus on the instance
- cursor-based paging: patch _request on the instance
"""
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from scopus_mcp.client import ScopusClient


def _entry(n: int) -> dict:
    return {'dc:identifier': f'SCOPUS_ID:{n}', 'dc:title': f'Paper {n}'}


def _search_resp(entries: list, total: int = 0, next_cursor: str | None = None) -> dict:
    sr: dict = {
        'entry': entries,
        'opensearch:totalResults': str(total or len(entries)),
    }
    if next_cursor is not None:
        sr['cursor'] = {'@current': 'c0', '@next': next_cursor}
    return {'search-results': sr}


class TestSearchAll(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.config_patcher = patch('scopus_mcp.client.get_api_key', return_value='fake_key')
        self.config_patcher.start()
        self.cache_patcher = patch('scopus_mcp.client.CacheManager')
        MockCache = self.cache_patcher.start()
        MockCache.return_value.get.return_value = None
        self.client = ScopusClient()

    async def asyncTearDown(self):
        self.config_patcher.stop()
        self.cache_patcher.stop()
        await self.client.close()

    # ------------------------------------------------------------------
    # Start-based paging
    # ------------------------------------------------------------------

    async def test_aggregation_across_multiple_pages(self):
        """Two full pages then one partial page are merged into a single list."""
        page1 = [_entry(i) for i in range(200)]
        page2 = [_entry(i) for i in range(200, 400)]
        page3 = [_entry(i) for i in range(400, 450)]

        call_args = []

        async def fake_search(query, count, start, sort):
            call_args.append(start)
            if start == 0:
                return _search_resp(page1, total=450)
            if start == 200:
                return _search_resp(page2, total=450)
            return _search_resp(page3, total=450)

        self.client.search_scopus = fake_search
        result = await self.client.search_all('TITLE(test)', max_results=450)

        entries = result['search-results']['entry']
        self.assertEqual(len(entries), 450)
        self.assertEqual(call_args, [0, 200, 400])
        self.assertFalse(result['_meta']['truncated'])

    async def test_stops_at_max_results(self):
        """Stops paging once max_results entries have been collected."""
        page = [_entry(i) for i in range(200)]

        call_count = 0

        async def fake_search(query, count, start, sort):
            nonlocal call_count
            call_count += 1
            # return a full page regardless of start so paging would be infinite
            # without the max_results guard
            return _search_resp(page[:count], total=5000)

        self.client.search_scopus = fake_search
        result = await self.client.search_all('TITLE(test)', max_results=100)

        self.assertEqual(len(result['search-results']['entry']), 100)
        self.assertEqual(call_count, 1)

    async def test_stops_when_results_exhausted_early(self):
        """Stops cleanly when API returns fewer results than the page size."""
        sparse = [_entry(i) for i in range(30)]

        async def fake_search(query, count, start, sort):
            if start == 0:
                return _search_resp(sparse, total=30)
            # Should never reach here
            raise AssertionError("unexpected second page request")

        self.client.search_scopus = fake_search
        result = await self.client.search_all('TITLE(test)', max_results=200)

        self.assertEqual(len(result['search-results']['entry']), 30)
        self.assertFalse(result['_meta']['truncated'])

    async def test_deduplication_across_pages(self):
        """Duplicate dc:identifier values across pages produce a single entry."""
        # page1 is a full 200-entry batch; page2 includes entry 0 as a dupe
        page1 = [_entry(i) for i in range(200)]
        page2 = [_entry(0)] + [_entry(i) for i in range(200, 208)]  # 9 entries, 1 dupe

        async def fake_search(query, count, start, sort):
            if start == 0:
                return _search_resp(page1[:count], total=209)
            return _search_resp(page2[:count], total=209)

        self.client.search_scopus = fake_search
        result = await self.client.search_all('TITLE(test)', max_results=209)

        ids = [e['dc:identifier'] for e in result['search-results']['entry']]
        self.assertEqual(len(ids), len(set(ids)), "duplicates found")
        self.assertEqual(len(ids), 208)  # 200 unique from page1 + 8 unique from page2

    async def test_truncation_note_when_capped_by_max_results(self):
        """Note is set when max_results < total_available."""
        page = [_entry(i) for i in range(200)]

        async def fake_search(query, count, start, sort):
            return _search_resp(page[:count], total=1000)

        self.client.search_scopus = fake_search
        result = await self.client.search_all('TITLE(test)', max_results=50)

        meta = result['_meta']
        self.assertTrue(meta['truncated'])
        self.assertIn('50', meta['note'])
        self.assertIn('1000', meta['note'])

    # ------------------------------------------------------------------
    # Cursor-based paging (max_results > 5000)
    # ------------------------------------------------------------------

    async def test_cursor_paging_used_when_max_results_exceeds_5000(self):
        """_request is called with cursor=* when max_results > 5000."""
        page = [_entry(i) for i in range(200)]

        request_params = []

        async def fake_request(method, endpoint, params=None, use_cache=True, ttl=None):
            request_params.append(dict(params or {}))
            sr = {
                'entry': page,
                'opensearch:totalResults': '200',
                # No next cursor — single page
            }
            return {'search-results': sr}

        self.client._request = fake_request
        await self.client.search_all('TITLE(test)', max_results=5001)

        self.assertTrue(len(request_params) >= 1)
        first = request_params[0]
        self.assertIn('cursor', first)
        self.assertEqual(first['cursor'], '*')
        self.assertNotIn('start', first)

    async def test_cursor_paging_follows_next_cursor(self):
        """Subsequent cursor pages use the @next cursor from the previous response."""
        page1 = [_entry(i) for i in range(200)]
        page2 = [_entry(i) for i in range(200, 300)]

        call_cursors = []

        async def fake_request(method, endpoint, params=None, use_cache=True, ttl=None):
            c = (params or {}).get('cursor')
            call_cursors.append(c)
            if c == '*':
                sr = {
                    'entry': page1,
                    'opensearch:totalResults': '300',
                    'cursor': {'@current': 'c0', '@next': 'c1'},
                }
            else:
                sr = {
                    'entry': page2,
                    'opensearch:totalResults': '300',
                    # No @next — last page
                }
            return {'search-results': sr}

        self.client._request = fake_request
        result = await self.client.search_all('TITLE(test)', max_results=5001)

        self.assertEqual(call_cursors, ['*', 'c1'])
        self.assertEqual(len(result['search-results']['entry']), 300)

    async def test_cursor_paging_stops_when_exhausted_early(self):
        """Cursor paging stops cleanly when a page is shorter than requested."""
        sparse = [_entry(i) for i in range(50)]

        async def fake_request(method, endpoint, params=None, use_cache=True, ttl=None):
            sr = {
                'entry': sparse,
                'opensearch:totalResults': '50',
                'cursor': {'@current': 'c0', '@next': 'c1'},
            }
            return {'search-results': sr}

        self.client._request = fake_request
        result = await self.client.search_all('TITLE(test)', max_results=5001)

        self.assertEqual(len(result['search-results']['entry']), 50)
