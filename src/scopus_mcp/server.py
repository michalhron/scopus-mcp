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
