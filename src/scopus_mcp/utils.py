import csv
import json
import logging
import math
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

logger = logging.getLogger(__name__)

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
# Citation-network graph helpers
# ---------------------------------------------------------------------------

EDGE_CSV_COLUMNS = ['source', 'target', 'weight', 'cosine']


def _make_node_label(meta: Dict[str, Any], node_id: str = '') -> str:
    """Derive a short readable label for a graph node.

    Priority: 'Surname YYYY' (from ce:indexed-name + year) → title[:40] → node_id.
    """
    creator = (meta.get('creator') or '').strip()
    year = (meta.get('year') or '').strip()
    if creator:
        # ce:indexed-name is 'Surname I.' — first token is the surname
        surname = creator.split()[0].rstrip('.,')
        return f'{surname} {year}' if year else surname
    title = (meta.get('title') or '').strip()
    if title:
        return title[:40]
    return node_id or str(meta.get('id', ''))


def compute_pairwise_edges(
    seed_sets: Dict[str, Set[str]],
    min_shared: int = 2,
) -> List[Dict[str, Any]]:
    """Compute pairwise overlap between seed sets; return a weighted edge list.

    Args:
        seed_sets: mapping of seed_id → set of reference or citing-paper IDs.
                   Seeds with empty sets are silently skipped.
        min_shared: minimum shared items required for an edge to be emitted.

    Returns:
        List of {'source', 'target', 'weight' (int), 'cosine' (float)},
        sorted by weight descending. Each unordered pair (a, b) appears once.
    """
    seeds = [s for s, refs in seed_sets.items() if refs]
    edges = []
    for i in range(len(seeds)):
        for j in range(i + 1, len(seeds)):
            a, b = seeds[i], seeds[j]
            set_a, set_b = seed_sets[a], seed_sets[b]
            shared = len(set_a & set_b)
            if shared < min_shared:
                continue
            denom = math.sqrt(len(set_a) * len(set_b))
            cosine = round(shared / denom, 6) if denom > 0 else 0.0
            edges.append({'source': a, 'target': b, 'weight': shared, 'cosine': cosine})
    edges.sort(key=lambda e: e['weight'], reverse=True)
    return edges


def write_graph_to_disk(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    slug: str,
) -> Dict[str, str]:
    """Write graph data to GraphML + CSV edge list + PNG; return their absolute paths.

    Node dicts: {id, label, title, creator, year, venue} — all except id may be None.
    Edge dicts: {source, target, weight, cosine}

    GraphML carries explicit <key> declarations (label, title, creator, year, venue)
    so it opens cleanly in Gephi and VOSviewer. PNG is rendered via render_graph_png
    alongside the other files; render failures are non-fatal (png_path=None in result).
    Output directory follows the SCOPUS_MCP_OUTPUT_DIR convention.
    """
    out = _output_dir()
    ts = datetime.now().strftime('%Y%m%dT%H%M%S')
    base = f'scopus-{_query_slug(slug)}-{ts}'

    graphml_path = out / f'{base}.graphml'
    csv_path = out / f'{base}-edges.csv'

    # ---- GraphML ----
    root = ET.Element('graphml', {
        'xmlns': 'http://graphml.graphdrawing.org/graphml',
        'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'xsi:schemaLocation': (
            'http://graphml.graphdrawing.org/graphml '
            'http://graphml.graphdrawing.org/graphml/graphml.xsd'
        ),
    })
    for kid, fname, ffor, ftype in [
        ('d_label',   'label',   'node', 'string'),
        ('d_title',   'title',   'node', 'string'),
        ('d_creator', 'creator', 'node', 'string'),
        ('d_year',    'year',    'node', 'string'),
        ('d_venue',   'venue',   'node', 'string'),
        ('d_weight',  'weight',  'edge', 'double'),
        ('d_cosine',  'cosine',  'edge', 'double'),
    ]:
        ET.SubElement(root, 'key', {
            'id': kid, 'for': ffor,
            'attr.name': fname, 'attr.type': ftype,
        })
    graph_el = ET.SubElement(root, 'graph', {'id': 'G', 'edgedefault': 'undirected'})
    for node in nodes:
        n_el = ET.SubElement(graph_el, 'node', {'id': str(node['id'])})
        for key_id, field in [
            ('d_label', 'label'), ('d_title', 'title'), ('d_creator', 'creator'),
            ('d_year', 'year'), ('d_venue', 'venue'),
        ]:
            val = node.get(field)
            if val is not None:
                d = ET.SubElement(n_el, 'data', {'key': key_id})
                d.text = str(val)
    for idx, edge in enumerate(edges):
        e_el = ET.SubElement(graph_el, 'edge', {
            'id': f'e{idx}',
            'source': str(edge['source']),
            'target': str(edge['target']),
        })
        dw = ET.SubElement(e_el, 'data', {'key': 'd_weight'})
        dw.text = str(edge['weight'])
        dc = ET.SubElement(e_el, 'data', {'key': 'd_cosine'})
        dc.text = str(edge['cosine'])

    tree = ET.ElementTree(root)
    ET.indent(tree, space='  ')
    with graphml_path.open('wb') as f:
        tree.write(f, encoding='utf-8', xml_declaration=True)

    # ---- CSV edge list ----
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=EDGE_CSV_COLUMNS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(edges)

    # ---- PNG (non-fatal) ----
    png_path = None
    try:
        png_path = render_graph_png(nodes, edges, base)
    except Exception as exc:
        logger.warning(f'write_graph_to_disk: render_graph_png non-fatal error: {exc}')

    return {
        'graphml_path': str(graphml_path),
        'csv_path': str(csv_path),
        'png_path': png_path,
    }


def render_graph_png(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    base_filename: str,
) -> Optional[str]:
    """Render the graph to PNG via networkx + matplotlib (Agg backend).

    Returns the absolute path to the PNG, or None if the graph is empty or
    rendering fails for any reason. Never raises — errors are logged and
    the caller continues with GraphML/CSV as the primary artifacts.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import networkx as nx

        out = _output_dir()
        png_path = out / f'{base_filename}.png'

        G = nx.Graph()
        for node in nodes:
            G.add_node(str(node['id']), label=node.get('label', str(node['id'])))
        for edge in edges:
            G.add_edge(
                str(edge['source']), str(edge['target']),
                weight=float(edge.get('weight', 1)),
            )

        if len(G.nodes) == 0:
            return None

        fig, ax = plt.subplots(figsize=(12, 8))
        pos = nx.spring_layout(G, seed=42, k=2.0 / math.sqrt(max(len(G.nodes), 1)))

        degrees = dict(G.degree())
        node_sizes = [max(200, 150 * degrees.get(n, 1)) for n in G.nodes]

        weights = [G[u][v].get('weight', 1) for u, v in G.edges]
        max_w = max(weights) if weights else 1
        edge_widths = [0.5 + 3.5 * w / max_w for w in weights]

        nx.draw_networkx_nodes(G, pos, node_size=node_sizes, ax=ax, alpha=0.85)
        nx.draw_networkx_edges(G, pos, width=edge_widths, ax=ax, alpha=0.5)
        nx.draw_networkx_labels(
            G, pos,
            labels={n: G.nodes[n]['label'] for n in G.nodes},
            ax=ax, font_size=7,
        )

        ax.set_axis_off()
        plt.tight_layout()
        plt.savefig(str(png_path), dpi=150, bbox_inches='tight')
        plt.close(fig)

        return str(png_path)
    except Exception as exc:
        logger.warning(f'render_graph_png failed (non-fatal): {exc}')
        return None


def write_lineage_to_disk(records: List[Dict[str, Any]], seed_id: str) -> str:
    """Write citation lineage corpus to JSON; return absolute path.

    Each record: {scopus_id, doi, title, year, venue, generation, parents, cited_by_count}.
    Output directory follows the SCOPUS_MCP_OUTPUT_DIR convention.
    """
    out = _output_dir()
    ts = datetime.now().strftime('%Y%m%dT%H%M%S')
    slug = _query_slug(f'lineage-{seed_id}')
    json_path = out / f'scopus-{slug}-{ts}.json'
    json_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return str(json_path)


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

    The REF view returns each reference as a flat object with top-level keys:
    'title', 'sourcetitle', 'scopus-id', 'ce:doi', 'prism:coverDate',
    'author-list', '@id'.  Unresolved or partially matched references may omit
    some fields; the parser degrades gracefully to None for missing values.
    Authors are deduplicated by @auid to collapse multi-affiliation duplicates.
    """
    root = data.get('abstracts-retrieval-response') or data.get('abstract-retrieval-response')
    if not root:
        return []

    ref_block = root.get('references')
    if not isinstance(ref_block, dict):
        return []
    refs = ref_block.get('reference')
    if refs is None:
        return []
    if isinstance(refs, dict):
        refs = [refs]
    if not isinstance(refs, list):
        return []

    cleaned: List[Dict[str, Any]] = []
    for r in refs:
        if not isinstance(r, dict):
            continue

        # Year from ISO cover date (e.g. "1996-01-01" → "1996")
        cover = r.get('prism:coverDate') or ''
        year = cover[:4] if cover else None

        # Authors — deduplicate by @auid to collapse multi-affiliation entries
        raw_authors = r.get('author-list', {})
        if isinstance(raw_authors, dict):
            raw_authors = raw_authors.get('author', [])
        if isinstance(raw_authors, dict):
            raw_authors = [raw_authors]
        seen_auids: set = set()
        authors: List[str] = []
        for a in (raw_authors or []):
            if not isinstance(a, dict):
                continue
            auid = a.get('@auid')
            if auid and auid in seen_auids:
                continue
            if auid:
                seen_auids.add(auid)
            name = a.get('ce:indexed-name') or a.get('ce:surname')
            if name:
                authors.append(name)

        cleaned.append({
            'position': r.get('@id'),
            'title': r.get('title'),
            'authors': authors,
            'source': r.get('sourcetitle'),
            'year': year or None,
            'scopus_id': r.get('scopus-id'),
            'doi': r.get('ce:doi'),
            'fulltext': None,
        })

    if limit is not None:
        return cleaned[:limit]
    return cleaned
