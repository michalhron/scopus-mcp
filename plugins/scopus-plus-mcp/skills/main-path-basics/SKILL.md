---
name: main-path-basics
description: Map the backbone of a research field with main path analysis. Builds a citation network from a Scopus query through the Scopus MCP server, weighs every link by search path count, extracts the main path and key routes, and draws the path by year. Use when someone wants a citation map, the main path of a literature, the backbone of a field, or a reading list built from citation flow.
---

# Main path basics

Main path analysis finds the chain of papers that carries the most citation flow through a field
(Hummon and Doreian 1989). Each link is weighed by its search path count, the number of chains from
the oldest papers to the newest that run through it (Batagelj 2003). The main path is the chain with
the largest total weight. Key routes add the next-heaviest chains (Liu and Lu 2012).

You need the Scopus Plus MCP server (github.com/michalhron/scopus-plus-mcp) connected. With Scopus,
it needs an API key, and reference lists need institutional access. Without a subscription, pass
`source="openalex"` to `citation_network` and run the same steps on OpenAlex.

## Step 1. Draw the boundary

Ask the user for the topic, the older names the topic went by, and the journals that count.
Write one Scopus query with both: the topic terms in TITLE-ABS-KEY, the journals as SRCID or ISSN.
Journals are one way to slice a field into a set of papers. For IS topics, the Litbaskets baskets
(Wang, Boell and Ciriello 2026) are one option. For any field Scopus indexes, call `find_journals`
with the subject areas the topic touches and a percentile cut-off (`min_percentile=75` keeps the top quarter).
Run `search_scopus` first and report the count. Between 300 and 2,000 papers works well.
Too few and the path is thin. Too many and the reference pull gets slow.

Show the query to the user and get a yes before pulling the network. The boundary decides the result,
so it is the user's call.

## Step 2. Keep the links inside the set

Call `citation_network` with the query, `key_routes=10` and `check_completeness=true`.
The server pulls every reference list and keeps only the citations between papers in the set.
It writes a corpus JSON with `nodes` and `edges`.

Report three things: papers, links inside the set, and papers whose reference lists look short
against Crossref. A paper with a short list can be cited but cannot cite, so it may drop off the path.
Check for reprints and duplicates (the same title twice) and tell the user.

## Step 3 and 4. Weigh the links and follow the heaviest chain

The server returns the main path and key routes. To recompute locally, or on a corpus from elsewhere:

    python3 scripts/main_path.py --corpus network.json --k 10 --out result.json

It drops links that run backward in time, breaks same-year cycles, and writes the main path, key routes,
the backbone and every link weight (also as CSV). Run `--selftest` once to check the install.

## Draw the map

    python3 scripts/plot_main_path.py --corpus network.json --result result.json --out map.png \
        --lanes lanes.json --highlight "\b(AI|machine learning)\b" --highlight-label "AI papers"

Lanes are optional. Read the papers on the path with the user and group them by the question each one
asks. Write the groups to `lanes.json` as `{"order": [...], "assign": {"<id>": "<lane>"}}`.
`--highlight` puts papers whose titles match a pattern in a band at the bottom, so the user can see
whether a new topic reaches the path.

## Read it with care

- The path shows where citations flow. Read the papers before saying what the field believes.
- The newest papers have had little time to be cited. The end of the path is the least settled.
- A different boundary gives a different path. If the user asks, rerun with a narrower or wider
  journal set and compare.
- Title matching for highlights is rough. Say so when reporting counts.

## References

Batagelj, V. (2003). Efficient algorithms for citation network analysis. arXiv:cs/0309023.
Hummon, N. P., and Doreian, P. (1989). Connectivity in a citation network: The development of DNA theory. Social Networks, 11(1), 39-63.
Liu, J. S., and Lu, L. Y. Y. (2012). An integrated approach for main path analysis: Development of the Hirsch index as an example. Journal of the American Society for Information Science and Technology, 63(3), 528-542.
Wang, B., Boell, S. K., and Ciriello, R. F. (2026). LitBaskets: Supporting exploratory literature searches for the information systems research community. Communications of the Association for Information Systems, 58, Article 56.
