#!/usr/bin/env python3
"""main_path.py: search path count, global main path and key routes for a citation network.

Input: the corpus JSON written by the Scopus MCP server's citation_network tool
  {"nodes": [{"id", "title", "creator", "year", "venue", ...}], "edges": [{"citing", "cited"}, ...]}
or a minimal file {"records": [{"id", "year", ...}], "edges": [[cited, citing], ...]}.

Knowledge flows from the cited (older) paper to the citing (newer) paper.
Search path count of a link u -> v = (paths from any source to u) x (paths from v to any sink)
(Batagelj 2003). The global main path is the source-to-sink chain with the largest
summed weight (Hummon and Doreian 1989; Liu and Lu 2012). Key routes start from the
k heaviest links and extend them forward and backward along the heaviest neighbours
(Liu and Lu 2012).

Usage:
  python3 main_path.py --corpus network.json --k 10 --out result.json
  python3 main_path.py --selftest
"""
import argparse, csv, json, sys
from collections import defaultdict, deque


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    papers = d.get("nodes") or d.get("records")
    papers = [dict(p, id=str(p.get("id") or p.get("scopus_id"))) for p in papers]
    links = []
    for e in d["edges"]:
        if isinstance(e, dict):
            links.append((str(e["cited"]), str(e["citing"])))
        else:
            links.append((str(e[0]), str(e[1])))
    return papers, links


def as_dag(papers, links):
    """Keep links inside the set that do not run backward in time. Same-year links stay,
    and any cycle among them is broken by dropping the link that closes it."""
    year = {p["id"]: int(float(p.get("year") or 0)) for p in papers}
    inside = sorted({(u, v) for u, v in links if u in year and v in year and u != v})
    keep = [(u, v) for u, v in inside if year[u] <= year[v]]
    backward = len(inside) - len(keep)
    out = defaultdict(list)
    for u, v in keep: out[u].append(v)
    state, cyc = {}, set()
    for root in sorted(year, key=lambda n: (year[n], n)):
        if root in state: continue
        stack = [(root, iter(out[root]))]; state[root] = 1
        while stack:
            n, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[n] = 2; stack.pop()
            elif state.get(nxt) == 1:
                cyc.add((n, nxt))
            elif nxt not in state:
                state[nxt] = 1; stack.append((nxt, iter(out[nxt])))
    dag = [e for e in keep if e not in cyc]
    indeg = defaultdict(int); out = defaultdict(list)
    for u, v in dag: out[u].append(v); indeg[v] += 1
    q = deque(sorted((n for n in year if indeg[n] == 0), key=lambda n: (year[n], n))); order = []
    while q:
        n = q.popleft(); order.append(n)
        for v in out[n]:
            indeg[v] -= 1
            if indeg[v] == 0: q.append(v)
    return order, dag, {"backward_in_time": backward, "cycle_breaks": len(cyc)}


def search_path_count(order, links):
    out, inn = defaultdict(list), defaultdict(list)
    for u, v in links:
        out[u].append(v); inn[v].append(u)
    fwd = {n: 1 if not inn[n] else 0 for n in order}
    for n in order:
        for v in out[n]: fwd[v] += fwd[n]
    bwd = {n: 1 if not out[n] else 0 for n in order}
    for n in reversed(order):
        for u in inn[n]: bwd[u] += bwd[n]
    return {(u, v): fwd[u] * bwd[v] for u, v in links}, out, inn


def global_main_path(order, w, out, inn):
    best, nxt = {n: 0 for n in order}, {n: None for n in order}
    for n in reversed(order):
        for v in out[n]:
            if w[(n, v)] + best[v] > best[n]:
                best[n], nxt[n] = w[(n, v)] + best[v], v
    sources = [n for n in order if not inn[n] and out[n]]
    if not sources: return [], 0
    cur = max(sources, key=lambda s: best[s]); total = best[cur]; path = []
    while cur is not None:
        path.append(cur); cur = nxt[cur]
    return path, total


def key_routes(w, out, inn, k):
    routes = []
    for (u, v), _ in sorted(w.items(), key=lambda kv: -kv[1])[:k]:
        chain = [u, v]
        while out[chain[-1]]:
            chain.append(max(out[chain[-1]], key=lambda x: w[(chain[-1], x)]))
        while inn[chain[0]]:
            chain.insert(0, max(inn[chain[0]], key=lambda x: w[(x, chain[0])]))
        routes.append(chain)
    return routes


def label(p):
    a = (p.get("creator") or p.get("first_author") or "?").split()[0].rstrip(",")
    return f"{a} {int(float(p.get('year') or 0))}"


def run(papers, links, k):
    order, dag, dropped = as_dag(papers, links)
    w, out, inn = search_path_count(order, dag)
    path, total = global_main_path(order, w, out, inn)
    routes = key_routes(w, out, inn, k)
    byid = {p["id"]: p for p in papers}
    backbone = sorted({n for r in routes for n in r} | set(path), key=lambda n: (int(float(byid[n].get("year") or 0)), n))
    return {
        "main_path": path, "main_path_labels": [label(byid[n]) for n in path], "main_path_weight": total,
        "key_routes": routes, "backbone": backbone,
        "links": [{"cited": u, "citing": v, "spc": x} for (u, v), x in sorted(w.items(), key=lambda kv: -kv[1])],
        "stats": {"papers": len(papers), "links_inside": len(dag), "dropped": dropped,
                  "sources": sum(1 for n in order if not inn[n] and out[n]),
                  "sinks": sum(1 for n in order if inn[n] and not out[n]),
                  "isolated": sum(1 for n in order if not inn[n] and not out[n])},
    }


def selftest():
    # Liang et al. (2016) Fig. 1 substructure: V1 -> V4 carries three source-sink paths,
    # and the global main path from V1 is V1-V4-V7-V8-V9.
    papers = [{"id": n, "year": y} for n, y in [("V1", 1), ("V4", 2), ("V5", 3), ("V7", 3), ("V8", 4), ("V9", 5)]]
    links = [("V1", "V4"), ("V4", "V5"), ("V4", "V7"), ("V4", "V8"), ("V7", "V8"), ("V8", "V9")]
    order, dag, _ = as_dag(papers, links)
    w, out, inn = search_path_count(order, dag)
    assert w[("V1", "V4")] == 3, w
    path, _ = global_main_path(order, w, out, inn)
    assert path == ["V1", "V4", "V7", "V8", "V9"], path
    print("self-test passed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus"); ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--out", default="main_path_result.json"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest: selftest(); sys.exit(0)
    if not a.corpus: ap.error("--corpus is required")
    papers, links = load(a.corpus)
    res = run(papers, links, a.k)
    json.dump(res, open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    with open(a.out.rsplit(".", 1)[0] + "_links.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f); wr.writerow(["cited", "citing", "spc"])
        for l in res["links"]: wr.writerow([l["cited"], l["citing"], l["spc"]])
    print(json.dumps(res["stats"])); print("main path:", " -> ".join(res["main_path_labels"]))
