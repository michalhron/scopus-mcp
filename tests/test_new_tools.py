"""Tests for the identifier helpers and new response cleaners.

These cover pure parsing/normalization logic and need no network or API key.
"""
from scopus_mcp.utils import (
    to_scopus_id,
    to_eid,
    detect_id_type,
    clean_identifiers,
    clean_references,
)


def test_to_scopus_id_strips_prefixes():
    assert to_scopus_id("0031512927") == "0031512927"
    assert to_scopus_id("SCOPUS_ID:0031512927") == "0031512927"
    assert to_scopus_id("2-s2.0-0031512927") == "0031512927"


def test_to_eid_builds_and_preserves():
    assert to_eid("0031512927") == "2-s2.0-0031512927"
    assert to_eid("SCOPUS_ID:0031512927") == "2-s2.0-0031512927"
    assert to_eid("2-s2.0-0031512927") == "2-s2.0-0031512927"


def test_detect_id_type():
    assert detect_id_type("2-s2.0-0031512927") == "eid"
    assert detect_id_type("10.1287/isre.8.4.458") == "doi"
    assert detect_id_type("0031512927") == "scopus_id"
    assert detect_id_type("SCOPUS_ID:0031512927") == "scopus_id"


def test_clean_identifiers_extracts_crossrefs():
    raw = {
        "abstracts-retrieval-response": {
            "coredata": {
                "dc:identifier": "SCOPUS_ID:0031512927",
                "eid": "2-s2.0-0031512927",
                "prism:doi": "10.1287/isre.8.4.458",
                "dc:title": "The organizing vision in information systems innovation",
                "prism:publicationName": "Information Systems Research",
                "citedby-count": "1234",
            }
        }
    }
    out = clean_identifiers(raw)
    assert out["scopus_id"] == "0031512927"
    assert out["eid"] == "2-s2.0-0031512927"
    assert out["doi"] == "10.1287/isre.8.4.458"
    assert out["cited_by_count"] == "1234"


def test_clean_identifiers_synthesizes_eid_when_absent():
    raw = {"abstracts-retrieval-response": {"coredata": {"dc:identifier": "SCOPUS_ID:55555"}}}
    assert clean_identifiers(raw)["eid"] == "2-s2.0-55555"


def test_clean_identifiers_empty_on_garbage():
    assert clean_identifiers({}) == {}
    assert clean_identifiers({"nope": 1}) == {}


def test_clean_references_parses_ref_view():
    raw = {
        "abstracts-retrieval-response": {
            "references": {
                "reference": [
                    {
                        "@id": "1",
                        "ref-fulltext": "Daft R.L., Weick K.E., ...",
                        "ref-info": {
                            "ref-title": {"ref-titletext": "Toward a model of organizations"},
                            "ref-sourcetitle": "Academy of Management Review",
                            "ref-publicationyear": {"@first": "1984"},
                            "ref-authors": {"author": [{"ce:indexed-name": "Daft R.L."}]},
                            "refd-itemidlist": {
                                "itemid": [
                                    {"@idtype": "SGR", "$": "0021488089"},
                                    {"@idtype": "DOI", "$": "10.2307/258441"},
                                ]
                            },
                        },
                    }
                ]
            }
        }
    }
    refs = clean_references(raw)
    assert len(refs) == 1
    r = refs[0]
    assert r["position"] == "1"
    assert r["title"] == "Toward a model of organizations"
    assert r["year"] == "1984"
    assert r["scopus_id"] == "0021488089"
    assert r["doi"] == "10.2307/258441"
    assert r["authors"] == ["Daft R.L."]


def test_clean_references_handles_single_dict_and_limit():
    raw = {
        "abstracts-retrieval-response": {
            "references": {
                "reference": {
                    "@id": "1",
                    "ref-info": {"ref-title": {"ref-titletext": "Solo ref"}},
                }
            }
        }
    }
    refs = clean_references(raw)
    assert len(refs) == 1 and refs[0]["title"] == "Solo ref"


def test_clean_references_empty_on_garbage():
    assert clean_references({}) == []
    assert clean_references({"abstracts-retrieval-response": {}}) == []
