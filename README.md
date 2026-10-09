<!-- mcp-name: io.github.michalhron/scopus-plus-mcp -->

<p align="center"><img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/banner.svg" alt="Scopus Plus MCP: search, full text, citation networks, journal quality and bibliometrics, for Claude and other AI assistants" width="100%"></p>

<p align="center">
<a href="https://github.com/michalhron/scopus-plus-mcp/actions/workflows/test.yml"><img src="https://github.com/michalhron/scopus-plus-mcp/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
<a href="https://pypi.org/project/scopus-plus-mcp/"><img src="https://img.shields.io/pypi/v/scopus-plus-mcp" alt="PyPI"></a>
<img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
<img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT">
</p>

Search the literature, trace who cites whom across generations, map research
fronts and intellectual bases, and pull the counts, metrics and bibliography
you need, from a conversation. It is an [MCP](https://modelcontextprotocol.io)
server, so any MCP client can use it: Claude Desktop, Claude Code, Cursor.

## What you get

<table>
<tr><td width="50%" valign="top"><img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-networks.svg" width="48" height="48" alt="" align="left"><b>Citation networks</b><br>Coupling, co-citation, multi-generation lineages and the network within any paper set, with SPC/SPLC/SPNP main paths, key routes, RPYS and a historiograph. <a href="docs/networks.md">More</a></td><td width="50%" valign="top"><img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-audit.svg" width="48" height="48" alt="" align="left"><b>Audited, not just built</b><br>Citer sets verified across search strategies, reference lists checked against Crossref, and the sentences behind each citation. <a href="docs/audit.md">More</a></td></tr>
<tr><td width="50%" valign="top"><img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-sources.svg" width="48" height="48" alt="" align="left"><b>Two data sources</b><br>Scopus by default. Add <code>source="openalex"</code> to run the same analyses without a Scopus subscription. <a href="docs/data-sources.md">More</a></td><td width="50%" valign="top"><img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-bibliometrics.svg" width="48" height="48" alt="" align="left"><b>Bibliometrics</b><br>Where a topic is published and in which quartile, journals above a percentile cut-off, counts per year, themes over time, BibTeX. <a href="docs/bibliometrics.md">More</a></td></tr>
<tr><td width="50%" valign="top"><img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-fulltext.svg" width="48" height="48" alt="" align="left"><b>Full-text search</b><br>Find Elsevier papers that use a term in their body, and see how often and where each one uses it. <a href="docs/search.md#full-text">More</a></td><td width="50%" valign="top"><img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-access.svg" width="48" height="48" alt="" align="left"><b>Honest about access</b><br>One call tells you which tools your Scopus access supports, and why the rest fail. <a href="docs/access.md">More</a></td></tr>
<tr><td width="50%" valign="top"><img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-skill.svg" width="48" height="48" alt="" align="left"><b>Main-path skill</b><br>Walks Claude from a query to a drawn main path map. Ships with the Claude Code plugin. <a href="plugins/scopus-plus-mcp/skills/main-path/README.md">More</a></td><td width="50%" valign="top"><img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-tested.svg" width="48" height="48" alt="" align="left"><b>Tested</b><br>510 test functions, CI on Linux, macOS and Windows, and a live check of every tool against the real APIs. <a href="docs/development.md">More</a></td></tr>
</table>

How it compares with the other Scopus MCP servers and with bibliometrics
packages (bibliometrix, pybliometrics, VOSviewer, Pajek): [comparison](docs/comparison.md).

## Ask things like

> *Map the research front around these six papers on organizing visions.*
>
> *Trace two generations of work citing Swanson & Ramiller (1997) and show me the main path.*
>
> *Build the citation network of every Basket of Eight paper citing the organizing-vision papers, and show how the main path cites its predecessors.*
>
> *How has publishing on "digital transformation" grown since 2010?*
>
> *Get SJR and CiteScore for the Basket of Eight, and BibTeX for the papers we just found.*

More, with the tools each one triggers: [prompt examples](docs/examples.md).

## How it works

<p align="center"><img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/flow.svg" alt="You ask in your MCP client. scopus-plus-mcp calls Scopus, OpenAlex, Crossref, Semantic Scholar and open-access sources, and writes JSON, CSV, GraphML, Pajek, PNG, HTML and BibTeX files to disk." width="100%"></p>

You ask in plain words and the assistant picks the tools. The server calls
Scopus with your own key, and Crossref, Semantic Scholar and open-access
sources where a tool needs them. Results come back as a summary in the reply,
and the full data goes to files that Pajek, VOSviewer, Gephi or Zotero can
open. Responses are cached, and long jobs run in the background.

## Tools

<p align="center"><img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/tools.svg" alt="35 tools in six families: search, citations, networks, audit, bibliometrics, diagnostics. Fifteen also run on OpenAlex." width="100%"></p>

| | Family | Tools | Guide |
| :-: | --- | --- | --- |
| <img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-search.svg" width="28" height="28" alt=""> | Search and records | `search_scopus` · `search_all` · `search_fulltext` · `get_abstract_details` · `resolve_identifier` · `search_authors` · `get_author_profile` · `get_fulltext` | [search](docs/search.md) |
| <img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-citations.svg" width="28" height="28" alt=""> | Citations | `get_references` · `get_citing_papers` | [search](docs/search.md) |
| <img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-networks.svg" width="28" height="28" alt=""> | Networks | `bibliographic_coupling` · `co_citation` · `citation_lineage` · `citation_network` · `historiograph` · `rpys` · `research_fronts` | [networks](docs/networks.md) |
| <img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-audit.svg" width="28" height="28" alt=""> | Audit | `resolve_citers` · `citation_context` · `path_transmission` · `coding_agreement` · `index_coverage` · `check_retractions` | [audit](docs/audit.md) |
| <img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-bibliometrics.svg" width="28" height="28" alt=""> | Bibliometrics | `publication_counts` · `topic_landscape` · `thematic_evolution` · `get_journal_metrics` · `find_journals` · `get_bibtex` · `import_records` | [bibliometrics](docs/bibliometrics.md) |
| <img src="https://raw.githubusercontent.com/michalhron/scopus-plus-mcp/main/docs/assets/icon-diagnostics.svg" width="28" height="28" alt=""> | Diagnostics and jobs | `diagnose_connection` · `get_quota_status` · `get_server_info` · `job_status` · `job_result` | [access](docs/access.md) |

Every parameter of every tool: [tool reference](docs/tools.md).

## Install

You need an API key from the [Elsevier Developer Portal](https://dev.elsevier.com/)
(register with your institutional email). OpenAlex needs no key.

**Claude Desktop**, one click:
1. Download `scopus-plus-mcp-<version>.mcpb` from the
   [latest release](https://github.com/michalhron/scopus-plus-mcp/releases/latest).
2. Open it (or drag it into *Settings → Extensions*), click **Install**, and
   paste your API key when asked. Claude stores it securely.

**Claude Code**, two commands:

```bash
claude plugin marketplace add michalhron/scopus-plus-mcp
claude plugin install scopus-plus-mcp@michalhron
```

Then make your key available, either in your shell
(`export SCOPUS_API_KEY=...`) or, better, in the
[OS secret store](docs/configuration.md#keep-secrets-out-of-config-files).

**Any other MCP client** (needs [uv](https://docs.astral.sh/uv/)):

```json
{
  "mcpServers": {
    "scopus-plus": {
      "command": "uvx",
      "args": ["scopus-plus-mcp"],
      "env": { "SCOPUS_API_KEY": "YOUR_KEY" }
    }
  }
}
```

Then ask your assistant to run `diagnose_connection`. It checks your key and
tells you which tools your Scopus access supports.

The Claude Code plugin also installs the **main-path** skill, which
walks Claude through a main path analysis from a query to a drawn map. For
Claude Desktop, zip [its folder](plugins/scopus-plus-mcp/skills/main-path)
and upload it as a skill.

## Documentation

Feature guides:

- [Search, records and full text](docs/search.md): finding papers and authors, identifiers, importing exports, full-text search and retrieval.
- [Citation networks and main paths](docs/networks.md): coupling, co-citation, lineages, main path analysis, historiograph, RPYS, research fronts.
- [Audit](docs/audit.md): verified citer sets, reference-list completeness, citation contexts, the transmission audit, retractions.
- [Bibliometrics and bibliography](docs/bibliometrics.md): counts per year, topic landscape, journal cut-offs and metrics, thematic evolution, BibTeX.

Reference and setup:

- [Tool reference](docs/tools.md): every tool and parameter, generated from the code.
- [Data sources](docs/data-sources.md): Scopus vs OpenAlex, when to use which, measured coverage.
- [Configuration](docs/configuration.md): all settings, and keeping keys in the OS secret store.
- [Access and troubleshooting](docs/access.md): off-campus access, tokens, proxies, reading `diagnose_connection`.
- [Comparison](docs/comparison.md): this project vs the other Scopus MCP servers, and vs bibliometrics packages.
- [Prompt examples](docs/examples.md), [development](docs/development.md), [changelog](CHANGELOG.md), [roadmap](ROADMAP.md).

## Origins

Formerly `citation-network-mcp` (and before that `michalhron/scopus-mcp`). This project began as a fork of
[qwe4559999/scopus-mcp](https://github.com/qwe4559999/scopus-mcp) by
[thinktraveller](https://github.com/thinktraveller) and
[qwe4559999](https://github.com/qwe4559999), which provides Scopus search,
abstracts, author profiles and citing papers. Everything since version 0.2
was developed here by [Michal Hron](https://github.com/michalhron). MIT
licensed; see [LICENSE](LICENSE).

Scopus and ScienceDirect are trademarks of Elsevier B.V. This project is
independent and not affiliated with or endorsed by Elsevier; it uses their
public APIs with your own key and subscription.
