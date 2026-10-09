# Bibliometrics and bibliography

<img src="assets/icon-bibliometrics.svg" width="64" height="64" align="right" alt="">

These tools measure a topic and its venues: how much is published and when,
where and at what prestige, which themes it holds and how they change, and
which journals clear a quality bar. They also produce the BibTeX for whatever
you found.

## How much, and when

`publication_counts` counts publications per year for a query. On Scopus it
sends one request per year, so `from_year` and `to_year` are required (at
most 60 years). On OpenAlex one request covers all years. The two sources
count differently. Compare trends within one source, and do not compare
totals across sources.

## Where, and at what prestige

`topic_landscape` runs a Scopus query and reports papers per broad subject
area, and then, per subject category, how many papers appear in Q1, Q2, Q3
and Q4 journals of that category, with the main journals. A journal can be
Q1 in one category and Q3 in another, so each paper counts in every category
of its journal.

Quartiles count journal papers only by default. Proceedings series such as
IFAC-PapersOnLine also carry CiteScore ranks, and they are reported
separately with book series. Large topics are analysed on a sample of up to
2,000 papers, the most recent by default or the most cited
(`sample="cited"`) to see where influential work appears. The reply states
the coverage.

## Which journals clear the bar

`find_journals` lists the journals in one or more Scopus subject categories
at or above a CiteScore percentile within the category. 75 is Q1 and 90 is
the top 10%. Categories are ASJC names or codes, such as Information Systems
(1710) or Management Information Systems (1404). The reply gives each
journal's rank, percentile, quartile and CiteScore, a CSV, and a ready
`SRCID(...)` fragment to paste into a `search_all` query.

`get_journal_metrics` returns SJR, SNIP, CiteScore and CiteScore Tracker with
their years, plus subject areas, for up to 200 journals by ISSN or Scopus
source ID. With `source="openalex"` it returns OpenAlex's own measures
(2-year mean citedness, h-index, i10-index) and needs no subscription.
Journals that are not found are listed in the reply.

## Themes over time

`thematic_evolution` follows the method of Cobo et al. (2011), as in
bibliometrix's thematic map. For each period it clusters co-occurring
keywords and places each cluster in the strategic diagram by Callon
centrality and density: motor, basic, niche, or emerging and declining
themes. Between periods it reports which themes continue, split, merge,
appear or vanish.

With `construct_terms` it follows one construct through the periods: the
theme that holds it, where that theme sits, and the keywords around it. That
shows whether the construct stays central, drifts, or dissolves into another
theme. Set periods with `cut_years` or let `n_periods` split the corpus
evenly. The tool writes JSON, CSV and a PNG of the strategic diagrams.

## Bibliography

`get_bibtex` writes BibTeX for up to 200 papers by DOI, Scopus ID or
OpenAlex ID. Entries come from the publisher's metadata, errors included, so
check author names. Papers without a DOI, such as many AIS conference papers,
get a minimal entry built from Scopus or OpenAlex metadata, marked with a
note.

Parameters for every tool: [tool reference](tools.md#bibliometrics-and-bibliography).
