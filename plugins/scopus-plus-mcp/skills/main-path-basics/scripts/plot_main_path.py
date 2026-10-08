#!/usr/bin/env python3
"""plot_main_path.py: draw the main path by year, optionally in topic lanes, with a band of highlighted papers.

Usage:
  python3 plot_main_path.py --corpus network.json --result main_path_result.json --out map.png \
      [--lanes lanes.json] [--highlight "\\bAI\\b|machine learning" --highlight-label "AI papers"] [--title "..."]

lanes.json (optional), written by you after reading the papers on the path:
  {"order": ["Lane name 1", "Lane name 2"], "assign": {"<paper id>": "Lane name 1", ...}}
Papers without a lane go to the first lane.
"""
import argparse, json, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

BLUE, PALE, TEXT, MUTED, GOLD = "#1E64C8", "#F3F6FA", "#1E293B", "#64748B", "#9A8C3E"

ap = argparse.ArgumentParser()
ap.add_argument("--corpus", required=True); ap.add_argument("--result", required=True); ap.add_argument("--out", default="map.png")
ap.add_argument("--lanes"); ap.add_argument("--highlight"); ap.add_argument("--highlight-label", default="Highlighted papers")
ap.add_argument("--title", default="Main path"); ap.add_argument("--font", default="DejaVu Sans")
a = ap.parse_args()
plt.rcParams["font.family"] = a.font

d = json.load(open(a.corpus, encoding="utf-8")); res = json.load(open(a.result, encoding="utf-8"))
papers = {str(p.get("id") or p.get("scopus_id")): p for p in (d.get("nodes") or d.get("records"))}
yr = lambda i: int(float(papers[i].get("year") or 0))
path, labels = res["main_path"], res["main_path_labels"]
lanes = {"order": ["Main path"], "assign": {}}
if a.lanes: lanes = json.load(open(a.lanes, encoding="utf-8"))
order = list(lanes["order"]) + (["__hl"] if a.highlight else [])
lane_y = {name: len(order) - 1 - i for i, name in enumerate(order)}
ly = lambda i: lane_y.get(lanes["assign"].get(i, lanes["order"][0]), lane_y[lanes["order"][0]])

fig, ax = plt.subplots(figsize=(12, 1.6 + 1.4 * len(order)), dpi=200)
y0, y1 = min(map(yr, papers)), max(map(yr, papers))
for name, y in lane_y.items():
    ax.axhspan(y - 0.5, y + 0.5, color=PALE if y % 2 else "white", lw=0, zorder=0)
    ax.text(y0 - 0.5, y + 0.38, (a.highlight_label if name == "__hl" else name).upper(), fontsize=9, fontweight="bold",
            color=GOLD if name == "__hl" else MUTED, va="top")
seen = {}
pos = {}
for i in path:
    k = (yr(i), ly(i)); seen[k] = seen.get(k, 0) + 1
    pos[i] = (yr(i) + 0.4 * (seen[k] - 1), ly(i) - 0.05)
for u, v in zip(path, path[1:]):
    ax.add_patch(FancyArrowPatch(pos[u], pos[v], arrowstyle="-|>", mutation_scale=12, shrinkA=6, shrinkB=6,
                                 connectionstyle="arc3,rad=0.1", color=BLUE, lw=2.4, zorder=2))
for n, (i, lab) in enumerate(zip(path, labels)):
    ax.scatter(*pos[i], s=70, color=BLUE, edgecolor="white", zorder=3)
    dy = [10, -12, 26, -28][n % 4]
    ax.annotate(lab, pos[i], xytext=(0, dy), textcoords="offset points", ha="center",
                va="bottom" if dy > 0 else "top", fontsize=8.5, fontweight="bold", color=TEXT)
if a.highlight:
    rx = re.compile(a.highlight, re.I); hl = [i for i, p in papers.items() if rx.search(p.get("title") or "")]
    for j, i in enumerate(hl):
        ax.scatter(yr(i) + ((j * 37) % 100) / 100 * 0.8 - 0.4, lane_y["__hl"] - 0.25 + ((j * 53) % 100) / 100 * 0.4,
                   s=18, facecolor="white", edgecolor=MUTED, lw=0.8, zorder=3)
    print(f"{len(hl)} highlighted papers, {len(set(hl) & set(path))} on the main path")
ax.set_xlim(y0 - 0.7, y1 + 1.5); ax.set_ylim(-0.5, len(order) - 0.5); ax.set_yticks([])
for s in ("left", "right", "top"): ax.spines[s].set_visible(False)
ax.set_title(a.title, loc="left", fontsize=14, fontweight="bold", color=TEXT)
fig.text(0.01, 0.01, f"Main path by search path count through {len(papers)} papers.", fontsize=8, color=MUTED)
fig.tight_layout(); fig.savefig(a.out, facecolor="white"); print("wrote", a.out)
