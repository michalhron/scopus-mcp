import logging
import asyncio
import httpx
from typing import Optional, Dict, Any
from urllib.parse import urljoin

from .config import get_api_key, get_cache_config
from .cache import CacheManager
from .utils import to_scopus_id, to_eid

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://api.elsevier.com/"

class ScopusClient:
    """
    Async client for interacting with the Elsevier Scopus API.
    Handles authentication, caching, rate limiting, and retries.
    """
    def __init__(self):
        self.api_key = get_api_key()
        self.cache_config = get_cache_config()
        self.headers = {
            'X-ELS-APIKey': self.api_key,
            'Accept': 'application/json',
            'User-Agent': 'ScopusMCP/0.1.0'
        }
        # Initialize CacheManager with default expiration
        self.cache = CacheManager(expiration_seconds=self.cache_config['default'])
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=30.0,
            follow_redirects=True
        )
        self.quota_info = {} # Store latest quota headers

    async def close(self):
        """Closes the underlying HTTP client."""
        await self.client.aclose()

    async def get_quota_status(self) -> Dict[str, Any]:
        """Returns the latest known quota status."""
        return self.quota_info

    async def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, use_cache: bool = True, ttl: Optional[int] = None) -> Dict[str, Any]:
        """
        Internal method to handle API requests with caching, rate limiting, and retries.
        """
        url = urljoin(BASE_URL, endpoint)
        
        # Check cache (Synchronous cache access is fast enough)
        if use_cache and method.upper() == 'GET':
            cached = self.cache.get(url, params)
            if cached:
                logger.debug(f"Cache hit for {url}")
                return cached

        retries = 3
        backoff = 1

        while retries > 0:
            try:
                response = await self.client.request(method, url, params=params)
                
                # Update Quota Info from Headers
                self._update_quota_info(response.headers)
                
                # Handle Rate Limiting
                if response.status_code == 429:
                    reset_time = int(response.headers.get('X-RateLimit-Reset', asyncio.get_event_loop().time() + 60))
                    # Calculate wait time, ensure at least 1 second
                    # Note: asyncio time vs epoch time. X-RateLimit-Reset is usually epoch.
                    import time
                    current_time = time.time()
                    sleep_time = max(reset_time - current_time, 1)
                    
                    logger.warning(f"Rate limit exceeded. Sleeping for {sleep_time:.2f} seconds.")
                    await asyncio.sleep(sleep_time)
                    continue

                response.raise_for_status()
                data = response.json()

                # Save to cache if GET
                if use_cache and method.upper() == 'GET':
                    self.cache.set(url, data, params, ttl=ttl)

                return data

            except httpx.HTTPStatusError as e:
                # Update quota info even on error if headers exist
                if e.response:
                    self._update_quota_info(e.response.headers)
                    
                status = e.response.status_code
                if status in [500, 502, 503, 504]:
                    logger.warning(f"Server error {status}. Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                    retries -= 1
                    backoff *= 2
                elif status == 401:
                     logger.error("Authentication failed. Check your API key.")
                     raise Exception("Authentication failed: Invalid API Key") from e
                elif status == 404:
                    logger.info(f"Resource not found: {url}")
                    return {} 
                else:
                    # Surface the response body and the query so malformed-syntax
                    # 400s (bad REF()/field syntax) are distinguishable from
                    # entitlement 403s without guesswork.
                    body = ''
                    try:
                        body = e.response.text[:500]
                    except Exception:
                        pass
                    q = params.get('query') if params else None
                    raise Exception(
                        f"Scopus API error {status} for {url} "
                        f"(query={q!r}): {body}"
                    ) from e
            except httpx.RequestError as e:
                logger.warning(f"Request failed: {e}. Retrying...")
                await asyncio.sleep(backoff)
                retries -= 1
                backoff *= 2
            except ValueError:
                logger.error("Failed to parse JSON response")
                raise Exception("Invalid JSON response from Scopus API")

        raise Exception(f"Max retries exceeded for {url}")

    def _update_quota_info(self, headers: httpx.Headers):
        """Updates internal quota state from response headers."""
        self.quota_info = {
            'limit': headers.get('X-RateLimit-Limit', 'unknown'),
            'remaining': headers.get('X-RateLimit-Remaining', 'unknown'),
            'reset': headers.get('X-RateLimit-Reset', 'unknown'),
            'status': 'OK'
        }

    async def search_scopus(self, query: str, count: int = 25, start: int = 0, sort: str = 'coverDate') -> Dict[str, Any]:
        """
        Searches Scopus API.
        Endpoint: content/search/scopus
        """
        params = {
            'query': query,
            'count': count,
            'start': start,
            'sort': sort,
            'view': 'STANDARD'
        }
        return await self._request('GET', 'content/search/scopus', params, ttl=self.cache_config['search'])

    async def get_abstract(self, scopus_id: str) -> Dict[str, Any]:
        """
        Retrieves abstract details.
        Endpoint: content/abstract/scopus_id/{id}
        """
        clean_id = scopus_id.replace('SCOPUS_ID:', '')
        return await self._request('GET', f'content/abstract/scopus_id/{clean_id}', ttl=self.cache_config['abstract'])

    async def get_author(self, author_id: str) -> Dict[str, Any]:
        """
        Retrieves author profile.
        Endpoint: content/author/author_id/{id}
        """
        clean_id = author_id.replace('AUTHOR_ID:', '')
        return await self._request('GET', f'content/author/author_id/{clean_id}', ttl=self.cache_config['author'])

    async def get_abstract_by(self, value: str, id_type: str = 'scopus_id') -> Dict[str, Any]:
        """
        Retrieves an abstract record by any supported identifier type.
        Endpoint: content/abstract/{id_type}/{value}

        id_type is one of: 'scopus_id', 'eid', 'doi', 'pii'.
        Used by resolve_identifier to cross-reference IDs (Scopus ID / EID / DOI).
        """
        id_type = (id_type or 'scopus_id').lower()
        if id_type == 'scopus_id':
            endpoint = f"content/abstract/scopus_id/{to_scopus_id(value)}"
        elif id_type == 'eid':
            endpoint = f"content/abstract/eid/{str(value).strip()}"
        elif id_type == 'doi':
            endpoint = f"content/abstract/doi/{str(value).strip()}"
        elif id_type == 'pii':
            endpoint = f"content/abstract/pii/{str(value).strip()}"
        else:
            raise ValueError(f"Unsupported id_type: {id_type}")
        return await self._request('GET', endpoint, ttl=self.cache_config['abstract'])

    async def get_references(self, scopus_id: str) -> Dict[str, Any]:
        """
        Retrieves the cited-reference list (backward citations) for a document
        via the Abstract Retrieval REF view.
        Endpoint: content/abstract/scopus_id/{id}?view=REF

        Note: the REF view requires an entitled (subscriber) key; an
        unentitled key returns 403, surfaced as an error by _request.
        Deeper paging of long reference lists uses the 'startref' parameter.
        """
        params = {'view': 'REF'}
        return await self._request(
            'GET',
            f"content/abstract/scopus_id/{to_scopus_id(scopus_id)}",
            params,
            ttl=self.cache_config['abstract'],
        )

    async def search_all(self, query: str, max_results: int = 200, sort: str = 'coverDate') -> Dict[str, Any]:
        """
        Pages through a Scopus search and returns aggregated results up to max_results.

        Uses start-based paging (page size 200, ceiling 5,000) when max_results <= 5,000.
        Switches to cursor=* deep paging when max_results > 5,000 — the two modes are
        mutually exclusive per Scopus API rules.  Deduplicates across pages by dc:identifier.
        """
        # 25 is the max count per page for non-institutional API keys.
        # Institutional keys support up to 200, but 25 is safe for all tiers.
        PAGE_SIZE = 25
        CURSOR_CEILING = 5000

        all_entries: list = []
        seen_ids: set = set()
        total_available: int = 0
        note: Optional[str] = None

        use_cursor = max_results > CURSOR_CEILING

        if use_cursor:
            cursor: str = '*'
            while len(all_entries) < max_results:
                batch = min(PAGE_SIZE, max_results - len(all_entries))
                params: Dict[str, Any] = {
                    'query': query,
                    'count': batch,
                    'cursor': cursor,
                    'sort': sort,
                    'view': 'STANDARD',
                }
                data = await self._request(
                    'GET', 'content/search/scopus', params,
                    use_cache=True, ttl=self.cache_config['search'],
                )
                sr = data.get('search-results', {})
                if not total_available:
                    try:
                        total_available = int(sr.get('opensearch:totalResults', 0))
                    except (ValueError, TypeError):
                        pass
                entries = sr.get('entry', [])
                if not entries:
                    break
                for e in entries:
                    uid = e.get('dc:identifier') or e.get('eid') or ''
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        all_entries.append(e)
                next_cursor = sr.get('cursor', {}).get('@next')
                if not next_cursor:
                    break
                if len(entries) < batch:
                    break  # API returned fewer than requested — results exhausted
                cursor = next_cursor
        else:
            start = 0
            while len(all_entries) < max_results and start < CURSOR_CEILING:
                batch = min(PAGE_SIZE, max_results - len(all_entries), CURSOR_CEILING - start)
                data = await self.search_scopus(query, count=batch, start=start, sort=sort)
                sr = data.get('search-results', {})
                if not total_available:
                    try:
                        total_available = int(sr.get('opensearch:totalResults', 0))
                    except (ValueError, TypeError):
                        pass
                entries = sr.get('entry', [])
                if not entries:
                    break
                added = 0
                for e in entries:
                    uid = e.get('dc:identifier') or e.get('eid') or ''
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        all_entries.append(e)
                        added += 1
                start += len(entries)
                if len(entries) < batch or added == 0:
                    break  # Exhausted or only duplicates returned

        fetched = len(all_entries)
        truncated = bool(total_available and fetched < total_available)
        if truncated:
            note = (
                f"Result set capped: fetched {fetched} of {total_available} total "
                f"(max_results={max_results})."
            )

        return {
            'search-results': {'entry': all_entries},
            '_meta': {
                'total_fetched': fetched,
                'total_available': total_available,
                'truncated': truncated,
                'note': note,
            },
        }

    async def get_citing_papers(self, scopus_id: str, count: int = 25, start: int = 0, sort: str = 'coverDate') -> Dict[str, Any]:
        """
        Retrieves forward citations via a Search API REF() query.
        Builds REF(2-s2.0-<id>) using the centralized EID normalization,
        which the Search API accepts (the bare-id REFEID(<id>) form 400s).
        """
        query = f"REF({to_eid(scopus_id)})"
        return await self.search_scopus(query, count=count, start=start, sort=sort)
