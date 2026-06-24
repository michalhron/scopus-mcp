import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# ---------------------------------------------------------------------------
# Output-file helpers (reusable by any tool that returns large result sets)
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    'scopus_id', 'title', 'creator', 'publication_name',
    'cover_date', 'doi', 'cited_by_count', 'aggregation_type', 'url',
]

# Inline-vs-file threshold: result sets larger than this are written to disk.
SEARCH_ALL_INLINE_THRESHOLD = 50


def _output_dir() -> Path:
    """Resolve the directory for large result dumps.

    Order: SCOPUS_MCP_OUTPUT_DIR env var → ~/scopus-mcp-output.
    Creates the directory (and parents) if absent.
    """
    d = os.environ.get('SCOPUS_MCP_OUTPUT_DIR')
    path = Path(d).expanduser() if d else Path.home() / 'scopus-mcp-output'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _query_slug(query: str) -> str:
    """Derive a short, filesystem-safe slug from a Scopus query string."""
    slug = re.sub(r'[^\w\s-]', '', query.lower())
    slug = re.sub(r'[\s_-]+', '-', slug).strip('-')
    return slug[:50] or 'query'


def write_results_to_disk(records: List[Dict[str, Any]], query: str) -> Dict[str, str]:
    """Write cleaned records to JSON and CSV files; return their absolute paths.

    Output directory: SCOPUS_MCP_OUTPUT_DIR if set, else ~/scopus-mcp-output.
    CSV columns: scopus_id, title, creator, publication_name, cover_date,
                 doi, cited_by_count, aggregation_type, url.
    """
    out = _output_dir()
    ts = datetime.now().strftime('%Y%m%dT%H%M%S')
    base = f'scopus-{_query_slug(query)}-{ts}'

    json_path = out / f'{base}.json'
    csv_path = out / f'{base}.csv'

    json_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)

    return {'json_path': str(json_path), 'csv_path': str(csv_path)}


def should_write_to_disk(
    records: List[Dict[str, Any]],
    threshold: int = SEARCH_ALL_INLINE_THRESHOLD,
) -> bool:
    """Return True when the result count exceeds the inline-return threshold."""
    return len(records) > threshold


# ---------------------------------------------------------------------------
# Search result cleaner
# ---------------------------------------------------------------------------

def clean_search_results(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extracts and normalizes search results from the Scopus Search API response.

    Args:
        data: The raw JSON response from Scopus API.

    Returns:
        A list of simplified dictionaries containing key article metadata.
        Returns [] when there are zero results or when the API returns an
        error-sentinel entry (no dc:identifier, carries an 'error' key).
    """
    if not data or 'search-results' not in data:
        return []

    sr = data['search-results']

    # Scopus signals an empty result set with totalResults "0".
    if str(sr.get('opensearch:totalResults', '')).strip() == '0':
        return []

    entries = sr.get('entry', [])
    cleaned_entries = []

    for entry in entries:
        # Skip error-sentinel entries: they carry an 'error' key and no real ID.
        if entry.get('error') and not entry.get('dc:identifier'):
            continue
        cleaned = {
            'scopus_id': entry.get('dc:identifier', '').replace('SCOPUS_ID:', ''),
            'title': entry.get('dc:title'),
            'creator': entry.get('dc:creator'),
            'publication_name': entry.get('prism:publicationName'),
            'cover_date': entry.get('prism:coverDate'),
            'doi': entry.get('prism:doi'),
            'cited_by_count': entry.get('citedby-count'),
            'aggregation_type': entry.get('prism:aggregationType'),
            'url': next((link['@href'] for link in entry.get('link', []) if link.get('@ref') == 'scopus'), None)
        }
        cleaned_entries.append(cleaned)

    return cleaned_entries

def clean_abstract_details(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts relevant details from the Scopus Abstract Retrieval API response.

    Args:
        data: The raw JSON response from Scopus API.

    Returns:
        A simplified dictionary containing abstract details.
    """
    # The API key can be singular or plural depending on endpoint version/context,
    # though usually 'abstracts-retrieval-response'.
    root = data.get('abstracts-retrieval-response') or data.get('abstract-retrieval-response')
    
    if not root:
        return {}

    coredata = root.get('coredata', {})
    authors_data = root.get('authors', {}).get('author', [])
    
    # Normalize authors to a list even if single author (API inconsistency)
    if isinstance(authors_data, dict):
        authors_data = [authors_data]
        
    authors = []
    for auth in authors_data:
        authors.append({
            'auth_id': auth.get('@auid'),
            'name': auth.get('ce:indexed-name'),
            'surname': auth.get('ce:surname'),
            'initials': auth.get('ce:initials')
        })

    return {
        'scopus_id': coredata.get('dc:identifier', '').replace('SCOPUS_ID:', ''),
        'doi': coredata.get('prism:doi'),
        'title': coredata.get('dc:title'),
        'description': coredata.get('dc:description'), # This is the abstract text
        'publication_name': coredata.get('prism:publicationName'),
        'cover_date': coredata.get('prism:coverDate'),
        'cited_by_count': coredata.get('citedby-count'),
        'authors': authors,
        'url': next((link['@href'] for link in coredata.get('link', []) if link.get('@ref') == 'scopus'), None)
    }

def clean_author_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts details from the Scopus Author Retrieval API response.

    Args:
        data: The raw JSON response from Scopus API.

    Returns:
        A simplified dictionary containing author profile information.
    """
    if not data or 'author-retrieval-response' not in data:
        return {}
    
    root = data['author-retrieval-response']
    core = root.get('coredata', {})
    profile = root.get('author-profile', {})
    
    name_variant = profile.get('preferred-name', {})
    
    return {
        'author_id': core.get('dc:identifier', '').replace('AUTHOR_ID:', ''),
        'orcid': core.get('orcid'),
        'document_count': core.get('document-count'),
        'cited_by_count': core.get('cited-by-count'),
        'citation_count': core.get('citation-count'),
        'name': {
            'surname': name_variant.get('surname'),
            'given_name': name_variant.get('given-name'),
            'initials': name_variant.get('initials')
        },
        'current_affiliation': _extract_affiliation(profile),
        'url': next((link['@href'] for link in core.get('link', []) if link.get('@ref') == 'scopus-author'), None)
    }

def _extract_affiliation(profile: Dict[str, Any]) -> Optional[str]:
    """Helper to extract current affiliation name."""
    affil = profile.get('affiliation-current', {}).get('affiliation', {})
    # Sometimes it's a list if multiple affiliations
    if isinstance(affil, list):
        affil = affil[0] if affil else {}
        
    return affil.get('ip-doc', {}).get('afdispname')


# ---------------------------------------------------------------------------
# Identifier normalization helpers
# ---------------------------------------------------------------------------
# Scopus exposes the same document under several identifiers. The Search API's
# REF() field expects the EID form (2-s2.0-<id>), while the Abstract Retrieval
# endpoints key on the bare Scopus ID. Centralizing the conversion here keeps
# every tool consistent and prevents the REFEID/REF class of bug.

def to_scopus_id(value: str) -> str:
    """Return the bare numeric Scopus ID, stripping a SCOPUS_ID: prefix or
    2-s2.0- EID prefix if present."""
    clean = str(value).strip().replace('SCOPUS_ID:', '')
    if clean.lower().startswith('2-s2.0-'):
        clean = clean[len('2-s2.0-'):]
    return clean


def to_eid(value: str) -> str:
    """Return the EID form (2-s2.0-<id>) used by the Search API's REF() field."""
    return f'2-s2.0-{to_scopus_id(value)}'


def detect_id_type(value: str) -> str:
    """Best-effort detection of an identifier's type.

    Returns one of: 'eid', 'doi', 'pii', 'scopus_id'. Callers may override.
    """
    v = str(value).strip()
    if v.lower().startswith('2-s2.0-'):
        return 'eid'
    if v.startswith('10.') or '/' in v:
        return 'doi'
    bare = v.replace('SCOPUS_ID:', '')
    if bare.isdigit():
        return 'scopus_id'
    # PII is 17 chars, alphanumeric, often starting with S or B. Loose heuristic.
    if bare and bare[0] in ('S', 'B') and bare.replace('-', '').isalnum():
        return 'pii'
    return 'scopus_id'


def clean_identifiers(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the cross-reference identifier set from an Abstract Retrieval
    response. This is the join layer for cross-linking with OpenAlex/Crossref,
    which key on DOI."""
    root = data.get('abstracts-retrieval-response') or data.get('abstract-retrieval-response')
    if not root:
        return {}

    core = root.get('coredata', {})
    sid = core.get('dc:identifier', '').replace('SCOPUS_ID:', '')
    eid = core.get('eid') or (f'2-s2.0-{sid}' if sid else None)

    return {
        'scopus_id': sid or None,
        'eid': eid,
        'doi': core.get('prism:doi'),
        'pii': core.get('pii'),
        'pubmed_id': core.get('pubmed-id'),
        'title': core.get('dc:title'),
        'publication_name': core.get('prism:publicationName'),
        'cover_date': core.get('prism:coverDate'),
        'cited_by_count': core.get('citedby-count'),
    }


def clean_references(data: Dict[str, Any], limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Extract the cited-reference list (backward citations) from an Abstract
    Retrieval REF-view response.

    The REF view's shape varies across records, so this digs through the two
    common locations and degrades gracefully to whatever fields are present.
    """
    root = data.get('abstracts-retrieval-response') or data.get('abstract-retrieval-response')
    if not root:
        return []

    refs = None
    if isinstance(root.get('references'), dict):
        refs = root['references'].get('reference')
    if refs is None:
        # Fallback: references nested in the bibrecord tail
        try:
            refs = root['item']['bibrecord']['tail']['bibliography']['reference']
        except (KeyError, TypeError):
            refs = None
    if refs is None:
        return []
    if isinstance(refs, dict):
        refs = [refs]

    cleaned: List[Dict[str, Any]] = []
    for r in refs:
        info = r.get('ref-info', r) if isinstance(r, dict) else {}

        title = None
        rt = info.get('ref-title')
        if isinstance(rt, dict):
            title = rt.get('ref-titletext')

        year = None
        pub = info.get('ref-publicationyear')
        if isinstance(pub, dict):
            year = pub.get('@first')

        scopus_id = None
        doi = None
        idlist = info.get('refd-itemidlist', {})
        items = idlist.get('itemid') if isinstance(idlist, dict) else None
        if isinstance(items, dict):
            items = [items]
        for it in (items or []):
            idtype = (it.get('@idtype') or '').upper()
            val = it.get('$') or it.get('#text') or it.get('value')
            if idtype in ('SGR', 'SCP', 'SCOPUS'):
                scopus_id = val
            elif idtype == 'DOI':
                doi = val

        authors: List[str] = []
        ra = info.get('ref-authors', {})
        alist = ra.get('author') if isinstance(ra, dict) else None
        if isinstance(alist, dict):
            alist = [alist]
        for a in (alist or []):
            if isinstance(a, dict):
                authors.append(a.get('ce:indexed-name') or a.get('ce:surname'))

        cleaned.append({
            'position': r.get('@id') if isinstance(r, dict) else None,
            'title': title,
            'authors': [x for x in authors if x],
            'source': info.get('ref-sourcetitle'),
            'year': year,
            'scopus_id': scopus_id,
            'doi': doi,
            'fulltext': info.get('ref-fulltext'),
        })

    if limit is not None:
        return cleaned[:limit]
    return cleaned
