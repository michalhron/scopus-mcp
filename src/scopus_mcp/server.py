import asyncio
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from .client import ScopusClient
from .utils import (
    clean_search_results,
    clean_abstract_details,
    clean_author_profile,
    clean_identifiers,
    clean_references,
    detect_id_type,
    to_scopus_id,
    to_eid,
    write_results_to_disk,
    should_write_to_disk,
    compute_pairwise_edges,
    write_graph_to_disk,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scopus-mcp")

# Initialize Server
server = Server("scopus-mcp")
client = ScopusClient()

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_scopus",
            description="Search for documents in Scopus using a query string.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The Scopus search query (e.g., 'TITLE(AI) AND PUBYEAR > 2020')."
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of results to return (default 5, max 25).",
                        "default": 5,
                        "maximum": 25
                    },
                    "sort": {
                        "type": "string",
                        "description": "Sort order (e.g., 'coverDate', 'relevancy').",
                        "default": "coverDate"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_abstract_details",
            description="Retrieve full details for a specific document by Scopus ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "scopus_id": {
                        "type": "string",
                        "description": "The Scopus ID of the document."
                    }
                },
                "required": ["scopus_id"]
            }
        ),
        types.Tool(
            name="get_author_profile",
            description="Retrieve an author's profile by Author ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "author_id": {
                        "type": "string",
                        "description": "The Scopus Author ID."
                    }
                },
                "required": ["author_id"]
            }
        ),
        types.Tool(
            name="get_citing_papers",
            description="Retrieve a list of papers that have cited the specified document (Forward Citations).",
            inputSchema={
                "type": "object",
                "properties": {
                    "scopus_id": {
                        "type": "string",
                        "description": "The Scopus ID of the document to find citations for."
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of results to return (default 5, max 25).",
                        "default": 5,
                        "maximum": 25
                    },
                    "sort": {
                        "type": "string",
                        "description": "Sort order (e.g., 'coverDate', 'relevancy').",
                        "default": "coverDate"
                    }
                },
                "required": ["scopus_id"]
            }
        ),
        types.Tool(
            name="get_quota_status",
            description="Get the current API quota status (remaining/limit). Note: Values are updated only after making a request.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="resolve_identifier",
            description=(
                "Resolve any document identifier (Scopus ID, EID, DOI, or PII) to "
                "the full cross-reference set (scopus_id, eid, doi, pii, title). "
                "Use this to obtain a DOI for cross-linking with OpenAlex/Crossref, "
                "or to normalize an ID before calling other tools."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "The identifier value (e.g. '0031512927', '2-s2.0-0031512927', or a DOI)."
                    },
                    "id_type": {
                        "type": "string",
                        "description": "Optional override of the identifier type.",
                        "enum": ["scopus_id", "eid", "doi", "pii"]
                    }
                },
                "required": ["identifier"]
            }
        ),
        types.Tool(
            name="search_all",
            description=(
                "Search Scopus and automatically page through results, returning up to "
                "max_results entries in a single call. Uses STANDARD view (200 results/page). "
                "For max_results > 5,000 the tool switches to cursor-based deep paging. "
                "Large max_results values consume significant API quota and may require "
                "many requests — use conservatively."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The Scopus search query (e.g., 'TITLE(AI) AND PUBYEAR > 2020')."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum total results to fetch across all pages (default 200). Large values consume quota.",
                        "default": 200
                    },
                    "sort": {
                        "type": "string",
                        "description": "Sort order (e.g., 'coverDate', 'relevancy').",
                        "default": "coverDate"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="bibliographic_coupling",
            description=(
                "Build a bibliographic-coupling graph for a set of seed papers. "
                "Two seeds are coupled when they share cited references; edge weight = "
                "count of shared references, cosine = Salton index. "
                "Maps the current research front. Requires an entitled (subscriber) key "
                "for REF-view access. Output: GraphML + CSV edge list written to disk."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "seed_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of Scopus IDs (bare numeric or SCOPUS_ID: prefixed)."
                    },
                    "min_shared": {
                        "type": "integer",
                        "description": "Minimum shared references for an edge to be emitted (default 2).",
                        "default": 2
                    }
                },
                "required": ["seed_ids"]
            }
        ),
        types.Tool(
            name="co_citation",
            description=(
                "Build a co-citation graph for a set of seed papers. "
                "Two seeds are co-cited when a later paper cites both; edge weight = "
                "count of co-citing papers, cosine = Salton index. "
                "Maps the intellectual base of a field. "
                "max_citing_per_seed bounds the API quota used per seed. "
                "Output: GraphML + CSV edge list written to disk."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "seed_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of Scopus IDs (bare numeric or SCOPUS_ID: prefixed)."
                    },
                    "min_shared": {
                        "type": "integer",
                        "description": "Minimum co-citing papers for an edge to be emitted (default 2).",
                        "default": 2
                    },
                    "max_citing_per_seed": {
                        "type": "integer",
                        "description": "Cap on citing papers fetched per seed (default 500). Limits quota usage.",
                        "default": 500
                    }
                },
                "required": ["seed_ids"]
            }
        ),
        types.Tool(
            name="get_references",
            description=(
                "Retrieve the cited-reference list of a document (Backward Citations) "
                "via the Abstract Retrieval REF view. Complements get_citing_papers, "
                "which returns forward citations. Requires an entitled (subscriber) key."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "scopus_id": {
                        "type": "string",
                        "description": "The Scopus ID (or EID) of the document whose references to retrieve."
                    },
                    "count": {
                        "type": "integer",
                        "description": "Maximum number of references to return (default 25).",
                        "default": 25
                    }
                },
                "required": ["scopus_id"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if not arguments:
        arguments = {}

    try:
        if name == "search_scopus":
            query = arguments.get("query")
            count = arguments.get("count", 5)
            sort = arguments.get("sort", "coverDate")
            
            if not query:
                raise ValueError("Query is required")

            # Await the async client method
            raw_data = await client.search_scopus(query, count=count, sort=sort)
            results = clean_search_results(raw_data)
            
            return [types.TextContent(type="text", text=str(results))]

        elif name == "get_abstract_details":
            scopus_id = arguments.get("scopus_id")
            if not scopus_id:
                raise ValueError("scopus_id is required")
                
            raw_data = await client.get_abstract(scopus_id)
            details = clean_abstract_details(raw_data)
            
            return [types.TextContent(type="text", text=str(details))]

        elif name == "get_author_profile":
            author_id = arguments.get("author_id")
            if not author_id:
                raise ValueError("author_id is required")
                
            raw_data = await client.get_author(author_id)
            profile = clean_author_profile(raw_data)
            
            return [types.TextContent(type="text", text=str(profile))]

        elif name == "get_citing_papers":
            scopus_id = arguments.get("scopus_id")
            count = arguments.get("count", 5)
            sort = arguments.get("sort", "coverDate")

            if not scopus_id:
                raise ValueError("scopus_id is required")

            # Forward citations via centralized REF(2-s2.0-<id>) construction.
            raw_data = await client.get_citing_papers(scopus_id, count=count, sort=sort)
            results = clean_search_results(raw_data)

            return [types.TextContent(type="text", text=str(results))]

        elif name == "resolve_identifier":
            identifier = arguments.get("identifier")
            if not identifier:
                raise ValueError("identifier is required")

            id_type = arguments.get("id_type") or detect_id_type(identifier)
            raw_data = await client.get_abstract_by(identifier, id_type=id_type)
            ids = clean_identifiers(raw_data)
            if not ids:
                return [types.TextContent(
                    type="text",
                    text=f"No record found for {identifier!r} (resolved as id_type={id_type})."
                )]
            return [types.TextContent(type="text", text=str(ids))]

        elif name == "get_references":
            scopus_id = arguments.get("scopus_id")
            count = arguments.get("count", 25)
            if not scopus_id:
                raise ValueError("scopus_id is required")

            raw_data = await client.get_references(scopus_id)
            references = clean_references(raw_data, limit=count)
            if not references:
                return [types.TextContent(
                    type="text",
                    text=("No references returned. The document may have no indexed "
                          "references, or your API key may lack REF-view entitlement.")
                )]
            return [types.TextContent(type="text", text=str(references))]

        elif name == "search_all":
            query = arguments.get("query")
            max_results = arguments.get("max_results", 200)
            sort = arguments.get("sort", "coverDate")

            if not query:
                raise ValueError("query is required")

            raw_data = await client.search_all(query, max_results=max_results, sort=sort)
            results = clean_search_results(raw_data)
            meta = raw_data.get('_meta', {})

            if should_write_to_disk(results):
                paths = write_results_to_disk(results, query)
                sample = results[:10]
                text = (
                    f"Fetched {meta.get('total_fetched', len(results))} records "
                    f"(total available: {meta.get('total_available', 'unknown')}, "
                    f"truncated: {meta.get('truncated', False)}).\n"
                    f"Full results written to disk:\n"
                    f"  JSON: {paths['json_path']}\n"
                    f"  CSV:  {paths['csv_path']}\n\n"
                    f"First 10 records:\n{sample}"
                )
            else:
                text = str(results)

            if meta.get('note'):
                text += f"\n\nNote: {meta['note']}"

            return [types.TextContent(type="text", text=text)]

        elif name == "bibliographic_coupling":
            seed_ids_raw = arguments.get("seed_ids", [])
            min_shared = int(arguments.get("min_shared", 2))

            if not seed_ids_raw:
                raise ValueError("seed_ids is required and must be non-empty")

            seed_sets: dict = {}
            seed_meta: dict = {}
            skipped: list = []

            for raw_id in seed_ids_raw:
                sid = to_scopus_id(str(raw_id))
                try:
                    raw = await client.get_references(sid)
                    refs = clean_references(raw)
                    ref_keys: set = set()
                    for r in refs:
                        key = r.get('scopus_id') or r.get('doi')
                        if key and key != sid:
                            ref_keys.add(key)
                    if not ref_keys:
                        skipped.append(sid)
                        logger.info(f"bibliographic_coupling: {sid} has no usable refs, skipping")
                        continue
                    seed_sets[sid] = ref_keys
                    # REF view response carries the seed's own coredata — no extra call needed
                    details = clean_abstract_details(raw)
                    authors = details.get('authors') or []
                    seed_meta[sid] = {
                        'title': details.get('title') or sid,
                        'creator': authors[0].get('name') if authors else None,
                        'year': (details.get('cover_date') or '')[:4] or None,
                        'venue': details.get('publication_name'),
                    }
                except Exception as exc:
                    logger.warning(f"bibliographic_coupling: error for {sid}: {exc}")
                    skipped.append(sid)

            edges = compute_pairwise_edges(seed_sets, min_shared=min_shared)
            nodes = [
                {
                    'id': sid,
                    'label': seed_meta.get(sid, {}).get('title', sid),
                    'year': seed_meta.get(sid, {}).get('year'),
                    'venue': seed_meta.get(sid, {}).get('venue'),
                }
                for sid in seed_sets
            ]
            paths = write_graph_to_disk(nodes, edges, f'bibcoupling-{len(seed_ids_raw)}seeds')

            top10 = edges[:10]
            top10_lines = [
                f"  {seed_meta.get(e['source'], {}).get('title', e['source'])!r} → "
                f"{seed_meta.get(e['target'], {}).get('title', e['target'])!r}: "
                f"weight={e['weight']}, cosine={e['cosine']:.4f}"
                for e in top10
            ]
            text = (
                f"Bibliographic coupling: {len(seed_sets)}/{len(seed_ids_raw)} seeds processed, "
                f"{len(edges)} edges emitted (min_shared={min_shared}).\n"
                f"Graph files:\n"
                f"  GraphML: {paths['graphml_path']}\n"
                f"  CSV:     {paths['csv_path']}\n\n"
                f"Top {len(top10)} edges by weight:\n"
                + ('\n'.join(top10_lines) if top10_lines else '  (none)')
            )
            if skipped:
                text += f"\n\nSkipped (no usable references or API error): {skipped}"
            return [types.TextContent(type="text", text=text)]

        elif name == "co_citation":
            seed_ids_raw = arguments.get("seed_ids", [])
            min_shared = int(arguments.get("min_shared", 2))
            max_citing = int(arguments.get("max_citing_per_seed", 500))

            if not seed_ids_raw:
                raise ValueError("seed_ids is required and must be non-empty")

            seed_sets = {}
            seed_meta = {}
            skipped = []

            for raw_id in seed_ids_raw:
                sid = to_scopus_id(str(raw_id))
                # Fetch seed metadata (one abstract call per seed)
                try:
                    raw_meta = await client.get_abstract(sid)
                    details = clean_abstract_details(raw_meta)
                    authors = details.get('authors') or []
                    seed_meta[sid] = {
                        'title': details.get('title') or sid,
                        'creator': authors[0].get('name') if authors else None,
                        'year': (details.get('cover_date') or '')[:4] or None,
                        'venue': details.get('publication_name'),
                    }
                except Exception as exc:
                    logger.warning(f"co_citation: metadata fetch failed for {sid}: {exc}")
                    seed_meta[sid] = {'title': sid, 'creator': None, 'year': None, 'venue': None}

                # Fetch citing papers via search_all with REF() query
                try:
                    raw_citers = await client.search_all(
                        f"REF({to_eid(sid)})", max_results=max_citing
                    )
                    citers = clean_search_results(raw_citers)
                    citer_ids: set = set()
                    for c in citers:
                        cid = c.get('scopus_id')
                        if cid and cid != sid:
                            citer_ids.add(cid)
                    if not citer_ids:
                        skipped.append(sid)
                        logger.info(f"co_citation: {sid} has no citing papers, skipping")
                        continue
                    seed_sets[sid] = citer_ids
                except Exception as exc:
                    logger.warning(f"co_citation: citing fetch failed for {sid}: {exc}")
                    skipped.append(sid)

            edges = compute_pairwise_edges(seed_sets, min_shared=min_shared)
            nodes = [
                {
                    'id': sid,
                    'label': seed_meta.get(sid, {}).get('title', sid),
                    'year': seed_meta.get(sid, {}).get('year'),
                    'venue': seed_meta.get(sid, {}).get('venue'),
                }
                for sid in seed_sets
            ]
            paths = write_graph_to_disk(nodes, edges, f'cocitation-{len(seed_ids_raw)}seeds')

            top10 = edges[:10]
            top10_lines = [
                f"  {seed_meta.get(e['source'], {}).get('title', e['source'])!r} → "
                f"{seed_meta.get(e['target'], {}).get('title', e['target'])!r}: "
                f"weight={e['weight']}, cosine={e['cosine']:.4f}"
                for e in top10
            ]
            text = (
                f"Co-citation: {len(seed_sets)}/{len(seed_ids_raw)} seeds processed, "
                f"{len(edges)} edges emitted (min_shared={min_shared}, "
                f"max_citing_per_seed={max_citing}).\n"
                f"Graph files:\n"
                f"  GraphML: {paths['graphml_path']}\n"
                f"  CSV:     {paths['csv_path']}\n\n"
                f"Top {len(top10)} edges by weight:\n"
                + ('\n'.join(top10_lines) if top10_lines else '  (none)')
            )
            if skipped:
                text += f"\n\nSkipped (no citing papers or API error): {skipped}"
            return [types.TextContent(type="text", text=text)]

        elif name == "get_quota_status":
            quota = await client.get_quota_status()
            if not quota:
                return [types.TextContent(type="text", text="No quota information available yet. Please make a request to initialize.")]
            
            return [types.TextContent(type="text", text=str(quota))]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    return [
        types.Prompt(
            name="research-summary",
            description="Search for papers on a topic and generate a research summary",
            arguments=[
                types.PromptArgument(
                    name="topic",
                    description="The research topic (e.g., 'machine learning healthcare')",
                    required=True
                )
            ]
        ),
        types.Prompt(
            name="author-analysis",
            description="Analyze an author's research impact and recent work",
            arguments=[
                types.PromptArgument(
                    name="author_id",
                    description="The Scopus Author ID",
                    required=True
                )
            ]
        )
    ]

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    if not arguments:
        arguments = {}

    if name == "research-summary":
        topic = arguments.get("topic", "unknown topic")
        return types.GetPromptResult(
            description=f"Research summary for {topic}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Please search specifically for high-cited papers related to '{topic}' published in the last 5 years using the search_scopus tool. Sort by cited references if possible. After retrieving the results, please summarize the key trends and findings in this field."
                    )
                )
            ]
        )

    if name == "author-analysis":
        author_id = arguments.get("author_id", "")
        return types.GetPromptResult(
            description=f"Analysis of author {author_id}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Please call the get_author_profile tool for Author ID '{author_id}'. Based on the returned data, analyze their research impact (citations, h-index if available), identify their main affiliation, and summarize their academic standing."
                    )
                )
            ]
        )

    raise ValueError(f"Unknown prompt: {name}")

async def main():
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    finally:
        # Ensure client is closed on shutdown
        await client.close()

def start():
    """Entry point for the package script."""
    asyncio.run(main())

if __name__ == "__main__":
    start()
