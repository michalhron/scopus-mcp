"""Generate the logo, icons and figures in docs/assets/.

    uv run --with fonttools python docs/assets/make_assets.py [--fonts DIR]

Text is converted to outlines, so the SVGs look the same on GitHub, PyPI and
in any viewer, with no web fonts. The fonts (IBM Plex Sans, IBM Plex Mono,
Source Serif 4; all SIL Open Font License) are read from --fonts, or
downloaded once into docs/assets/.fonts/ (git-ignored).

Palette: the app icon's navy, amber and sky on a dark blueprint ground.
"""
import argparse
import math
import re
import urllib.request
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

OUT = Path(__file__).resolve().parent

# ---------------------------------------------------------------- palette
BG = "#0D1B2A"      # ground
PANEL = "#132A40"   # cards
EDGE = "#24425F"    # card outlines, axes
GRID = "#14273A"    # blueprint grid
NAVY = "#1F3A5F"    # the app icon's tile
AMBER = "#F2B134"   # main path, the one accent
SKY = "#9FC3E6"     # links, secondary marks
WHITE = "#FFFFFF"
INK = "#E8EEF4"     # body text on dark
SUB = "#B4C6D8"     # secondary text
MUTED = "#7189A3"   # captions, axes
RUST = "#D9694A"    # flags and problems only

PLEX = "https://raw.githubusercontent.com/IBM/plex/v6.4.0"
FONT_FILES = {
    'serif': ("SourceSerif4-Bold.otf",
              "https://raw.githubusercontent.com/adobe-fonts/source-serif/release/OTF/SourceSerif4-Bold.otf"),
    'serif-sb': ("SourceSerif4-Semibold.otf",
                 "https://raw.githubusercontent.com/adobe-fonts/source-serif/release/OTF/SourceSerif4-Semibold.otf"),
    'sans': ("IBMPlexSans-Regular.otf", f"{PLEX}/IBM-Plex-Sans/fonts/complete/otf/IBMPlexSans-Regular.otf"),
    'sans-sb': ("IBMPlexSans-SemiBold.otf", f"{PLEX}/IBM-Plex-Sans/fonts/complete/otf/IBMPlexSans-SemiBold.otf"),
    'mono': ("IBMPlexMono-Regular.otf", f"{PLEX}/IBM-Plex-Mono/fonts/complete/otf/IBMPlexMono-Regular.otf"),
    'mono-md': ("IBMPlexMono-Medium.otf", f"{PLEX}/IBM-Plex-Mono/fonts/complete/otf/IBMPlexMono-Medium.otf"),
}
FONTS = {}


class Font:
    def __init__(self, key, path):
        self.key = key
        tt = TTFont(path)
        self.glyphs = tt.getGlyphSet()
        self.cmap = tt.getBestCmap()
        self.upm = tt['head'].unitsPerEm
        self.hmtx = tt['hmtx']

    def name(self, ch):
        return self.cmap.get(ord(ch)) or self.cmap.get(ord('?'))

    def advance(self, ch):
        return self.hmtx[self.name(ch)][0]

    def width(self, s, size, spacing=0):
        return sum(self.advance(c) for c in s) * size / self.upm + spacing * max(len(s) - 1, 0)

    def outline(self, gname):
        pen = SVGPathPen(self.glyphs)
        self.glyphs[gname].draw(pen)
        return pen.getCommands()


def load_fonts(font_dir: Path):
    font_dir.mkdir(parents=True, exist_ok=True)
    for key, (fname, url) in FONT_FILES.items():
        path = font_dir / fname
        if not path.exists():
            print(f"downloading {fname}")
            urllib.request.urlretrieve(url, path)
        FONTS[key] = Font(key, path)


# ---------------------------------------------------------------- document
class Doc:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.body, self.defs, self.glyphs = [], [], {}

    def add(self, *parts):
        self.body.extend(parts)
        return self

    def text(self, x, y, s, size, font='sans', fill=INK, anchor='start', spacing=0.0, opacity=None):
        f = FONTS[font]
        w = f.width(s, size, spacing)
        x0 = x - (w if anchor == 'end' else w / 2 if anchor == 'middle' else 0)
        k = size / f.upm
        uses, pen_x = [], 0.0
        for ch in s:
            g = f.name(ch)
            if ch != ' ':
                gid = re.sub(r'[^A-Za-z0-9_-]', '_', f"{f.key}-{g}")
                if gid not in self.glyphs:
                    self.glyphs[gid] = f.outline(g)
                uses.append(f'<use href="#{gid}" x="{pen_x:.0f}"/>')
            pen_x += f.advance(ch) + spacing / k
        op = f' opacity="{opacity}"' if opacity is not None else ""
        self.body.append(f'<g fill="{fill}"{op} transform="translate({x0:.1f} {y:.1f}) scale({k:.5f} {-k:.5f})">'
                         + "".join(uses) + "</g>")
        return w

    def svg(self):
        glyphs = "".join(f'<path id="{gid}" d="{d}"/>' for gid, d in self.glyphs.items())
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" '
                f'height="{self.h}" role="img" aria-label="{self.title}"><title>{self.title}</title>'
                f'<defs>{glyphs}{"".join(self.defs)}</defs>{"".join(self.body)}</svg>\n')

    def save(self, name):
        (OUT / name).write_text(self.svg(), encoding='utf-8')
        print(f"wrote {name}")


# ---------------------------------------------------------------- primitives
def circle(x, y, r, fill=WHITE, stroke=None, sw=0, opacity=None):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}"{s}{op}/>'


def line(x1, y1, x2, y2, color=SKY, w=3, dash=None, opacity=None, cap="round"):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" '
            f'stroke-width="{w}" stroke-linecap="{cap}"{d}{op}/>')


def trimmed(x1, y1, x2, y2, gap1, gap2):
    """The segment between two circles, shortened by a gap at each end."""
    a = math.atan2(y2 - y1, x2 - x1)
    return (x1 + gap1 * math.cos(a), y1 + gap1 * math.sin(a), x2 - gap2 * math.cos(a), y2 - gap2 * math.sin(a))


def arrow(x1, y1, x2, y2, color=SKY, w=3, head=None, dash=None):
    head = head or 4 * w
    a = math.atan2(y2 - y1, x2 - x1)
    bx, by = x2 - head * math.cos(a), y2 - head * math.sin(a)
    hw = head * 0.6
    p1 = (bx + hw * math.sin(a), by - hw * math.cos(a))
    p2 = (bx - hw * math.sin(a), by + hw * math.cos(a))
    return (line(x1, y1, bx, by, color, w, dash, cap="butt")
            + f'<path d="M{x2:.1f} {y2:.1f}L{p1[0]:.1f} {p1[1]:.1f}L{p2[0]:.1f} {p2[1]:.1f}z" fill="{color}"/>')


def rect(x, y, w, h, fill=PANEL, stroke=EDGE, sw=1.5, rx=10, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{s}{d}/>'


def frame(doc, grid=True):
    """Dark rounded ground with a blueprint grid and crop marks."""
    w, h = doc.w, doc.h
    doc.defs.append(f'<clipPath id="frame"><rect width="{w}" height="{h}" rx="16"/></clipPath>')
    doc.defs.append(f'<pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">'
                    f'<path d="M24 0H0V24" fill="none" stroke="{GRID}" stroke-width="1"/></pattern>')
    doc.add(f'<rect width="{w}" height="{h}" rx="16" fill="{BG}"/>')
    if grid:
        doc.add(f'<rect width="{w}" height="{h}" fill="url(#grid)" clip-path="url(#frame)"/>')
    m, L = 14, 18
    for cx, cy, sx, sy in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
        doc.add(f'<path d="M{cx} {cy + sy * L}V{cy}H{cx + sx * L}" fill="none" stroke="{EDGE}" stroke-width="2"/>')


def kicker(doc, x, y, s, color=SKY):
    doc.add(f'<rect x="{x}" y="{y - 11}" width="11" height="11" fill="{AMBER}"/>')
    doc.text(x + 22, y, s, 14, font='mono-md', fill=color, spacing=2.2)


# ---------------------------------------------------------------- logo (the app icon, redrawn)
LOGO_NODES = {'a': (155, 142, 23, AMBER), 'b': (357, 133, 23, WHITE), 'c': (257, 257, 31, AMBER),
              'd': (133, 357, 23, WHITE), 'e': (378, 357, 23, AMBER), 'f': (257, 420, 23, AMBER)}
LOGO_EDGES = [('a', 'b', SKY, 11), ('b', 'c', SKY, 11), ('c', 'd', SKY, 11), ('d', 'f', SKY, 11),
              ('a', 'c', AMBER, 15), ('c', 'e', AMBER, 15), ('e', 'f', AMBER, 15)]


def logo_body():
    out = f'<rect x="20" y="20" width="472" height="472" rx="104" fill="{NAVY}"/>'
    for u, v, color, w in LOGO_EDGES:
        x1, y1, r1, _ = LOGO_NODES[u]
        x2, y2, r2, _ = LOGO_NODES[v]
        out += line(*trimmed(x1, y1, x2, y2, r1 + 9, r2 + 9), color=color, w=w, cap="butt")
    for x, y, r, fill in LOGO_NODES.values():
        out += circle(x, y, r, fill)
    return out


def logo_at(x, y, size):
    return f'<g transform="translate({x} {y}) scale({size / 512:.5f})">{logo_body()}</g>'


# ---------------------------------------------------------------- icons (96 x 96 glyphs on the icon's navy tile)
def bar(x, y, w, h=6, fill=WHITE):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{fill}"/>'


def poly(points, color, w, fill="none", closed=False):
    d = "M" + "L".join(f"{x} {y}" for x, y in points) + ("z" if closed else "")
    return (f'<path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{w}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


GLYPHS = {
    # lens over a list of records, one record matched
    'search': bar(16, 22, 40) + bar(16, 36, 30) + bar(16, 50, 20, fill=AMBER) + bar(16, 64, 24)
    + circle(60, 54, 15, fill="none", stroke=SKY, sw=6) + line(71, 65, 82, 76, color=SKY, w=8),
    # references behind a paper, citing papers ahead of it
    'citations': line(*trimmed(18, 26, 48, 48, 7, 10), color=WHITE, w=4) + line(*trimmed(18, 70, 48, 48, 7, 10), color=WHITE, w=4)
    + arrow(*trimmed(48, 48, 80, 26, 10, 7), color=SKY, w=4, head=11) + arrow(*trimmed(48, 48, 80, 70, 10, 7), color=SKY, w=4, head=11)
    + circle(18, 26, 7) + circle(18, 70, 7) + circle(48, 48, 10, AMBER),
    # a citation network with its main path
    'networks': '<g transform="translate(-1 -1) scale(0.1914)">'
    + "".join(line(*trimmed(*LOGO_NODES[u][:2], *LOGO_NODES[v][:2], LOGO_NODES[u][2] + 9, LOGO_NODES[v][2] + 9),
                   color=c, w=w, cap="butt") for u, v, c, w in LOGO_EDGES)
    + "".join(circle(x, y, r, fill) for x, y, r, fill in LOGO_NODES.values()) + '</g>',
    # the citing sentence behind a citation edge
    'audit': rect(20, 12, 56, 34, fill="none", stroke=SKY, sw=4, rx=8) + poly([(40, 46), (46, 56), (52, 46)], SKY, 4)
    + bar(30, 22, 36, 5) + bar(30, 33, 24, 5, fill=AMBER)
    + line(*trimmed(18, 74, 78, 74, 8, 8), color=AMBER, w=5, cap="butt") + circle(18, 74, 7) + circle(78, 74, 7),
    # publications per year, quartiles
    'bibliometrics': bar(16, 56, 12, 22, SKY) + bar(34, 42, 12, 36, SKY) + bar(52, 48, 12, 30, SKY)
    + bar(70, 22, 12, 56, AMBER) + line(12, 82, 86, 82, color=WHITE, w=4),
    # a pulse: is the connection alive, what does it allow
    'diagnostics': poly([(10, 52), (28, 52), (36, 32), (50, 72), (60, 42), (68, 52), (78, 52)], WHITE, 5)
    + circle(84, 52, 6, AMBER),
    # a page, one term found in the body
    'fulltext': poly([(24, 12), (60, 12), (74, 26), (74, 84), (24, 84)], WHITE, 4.5, closed=True)
    + poly([(60, 12), (60, 26), (74, 26)], WHITE, 4.5)
    + bar(33, 36, 32, 5, SKY) + bar(33, 48, 14, 5, SKY) + bar(50, 47, 16, 7, AMBER) + bar(33, 60, 32, 5, SKY)
    + bar(33, 72, 22, 5, SKY),
    # two sources feed the same analysis
    'sources': "".join(f'<ellipse cx="{x}" cy="18" rx="15" ry="5" fill="none" stroke="{c}" stroke-width="4"/>'
                       f'<path d="M{x - 15} 18V40a15 5 0 0 0 30 0V18" fill="none" stroke="{c}" stroke-width="4"/>'
                       for x, c in ((26, WHITE), (70, SKY)))
    + line(*trimmed(26, 48, 48, 76, 4, 11), color=WHITE, w=4) + line(*trimmed(70, 48, 48, 76, 4, 11), color=SKY, w=4)
    + circle(48, 76, 10, AMBER),
    # what your access allows, and what it does not
    'access': poly([(14, 26), (20, 32), (30, 20)], SKY, 5) + bar(40, 23, 42)
    + poly([(14, 50), (20, 56), (30, 44)], SKY, 5) + bar(40, 47, 34)
    + line(16, 66, 28, 78, color=RUST, w=5) + line(28, 66, 16, 78, color=RUST, w=5) + bar(40, 69, 26, fill=SKY),
    # tests pass
    'tested': poly([(48, 10), (80, 22), (80, 46), (48, 86), (16, 46), (16, 22)], WHITE, 5, closed=True)
    + poly([(34, 46), (45, 57), (64, 36)], AMBER, 7),
    # the skill draws the map
    'skill': "".join(f'<path d="M{x} {y + sy * 14}V{y}H{x + sx * 14}" fill="none" stroke="{WHITE}" stroke-width="4"/>'
                     for x, y, sx, sy in ((12, 12, 1, 1), (84, 12, -1, 1), (12, 84, 1, -1), (84, 84, -1, -1)))
    + poly([(26, 64), (42, 38), (58, 56), (72, 30)], AMBER, 5) + circle(26, 64, 6, AMBER) + circle(42, 38, 6, AMBER)
    + circle(58, 56, 6, AMBER) + circle(72, 30, 6, AMBER) + circle(30, 30, 5, SKY) + circle(70, 68, 5, SKY),
}

FAMILIES = [  # icon, short name, two-line description, tools (from scripts/gen_tools_doc.py)
    ('search', 'Search', ('records, authors,', 'full text'),
     ['search_scopus', 'search_all', 'search_fulltext', 'get_abstract_details', 'resolve_identifier',
      'search_authors', 'get_author_profile', 'get_fulltext']),
    ('citations', 'Citations', ('references and', 'citing papers'), ['get_references', 'get_citing_papers']),
    ('networks', 'Networks', ('coupling, lineage,', 'main paths, fronts'),
     ['bibliographic_coupling', 'co_citation', 'citation_lineage', 'citation_network', 'historiograph', 'rpys',
      'research_fronts']),
    ('audit', 'Audit', ('citers, contexts,', 'coverage, retractions'),
     ['resolve_citers', 'citation_context', 'path_transmission', 'coding_agreement', 'index_coverage',
      'check_retractions']),
    ('bibliometrics', 'Bibliometrics', ('counts, journals,', 'themes, BibTeX'),
     ['publication_counts', 'topic_landscape', 'thematic_evolution', 'get_journal_metrics', 'find_journals',
      'get_bibtex', 'import_records']),
    ('diagnostics', 'Diagnostics', ('access, quota,', 'background jobs'),
     ['diagnose_connection', 'get_quota_status', 'get_server_info', 'job_status', 'job_result']),
]
OPENALEX = {'search_all', 'search_authors', 'get_references', 'get_citing_papers', 'bibliographic_coupling',
            'co_citation', 'citation_lineage', 'citation_network', 'historiograph', 'rpys', 'research_fronts',
            'resolve_citers', 'publication_counts', 'thematic_evolution', 'get_journal_metrics'}


def tile(name):
    return f'<rect width="96" height="96" rx="22" fill="{NAVY}"/>' + GLYPHS[name]


def icon_at(name, x, y, size):
    return f'<g transform="translate({x} {y}) scale({size / 96:.5f})">{tile(name)}</g>'


def make_icons():
    for name in GLYPHS:
        doc = Doc(96, 96, name)
        doc.add(tile(name))
        doc.save(f"icon-{name}.svg")
    doc = Doc(512, 512, "Scopus Plus MCP")
    doc.add(logo_body())
    doc.save("logo.svg")


# ---------------------------------------------------------------- banner
def make_banner():
    doc = Doc(1200, 400, "Scopus Plus MCP")
    frame(doc)
    doc.add(logo_at(56, 52, 104))
    doc.text(178, 96, "MCP SERVER", 14, font='mono-md', fill=SKY, spacing=2.4)
    doc.text(178, 124, "Scopus  +  OpenAlex", 14, font='mono', fill=MUTED, spacing=1.2)
    doc.text(60, 236, "Scopus Plus MCP", 66, font='serif', fill=WHITE)
    doc.text(62, 284, "Search, full text, citation networks, journal quality", 23, fill=SUB)
    doc.text(62, 316, "and bibliometrics, for Claude and other AI assistants.", 23, fill=SUB)
    w = doc.text(62, 362, "$ ", 16, font='mono-md', fill=AMBER)
    doc.text(62 + w, 362, "uvx scopus-plus-mcp", 16, font='mono', fill=INK)

    # right: a citation network on a time axis, its main path in amber
    px, py, pw, ph = 690, 44, 466, 312
    doc.add(rect(px, py, pw, ph, fill=PANEL, stroke=EDGE, rx=12))
    doc.text(px + 20, py + 30, "FIG. 1", 12, font='mono-md', fill=MUTED, spacing=1.6)
    doc.text(px + 82, py + 30, "citation_network  ·  main path (SPC)", 12, font='mono', fill=SUB)

    def X(year):
        return px + 40 + (year - 1995) * (pw - 76) / 30

    nodes = {'A': (1997, 175), 'B': (1999, 255), 'C': (2002, 115), 'D': (2004, 205), 'E': (2006, 270),
             'F': (2008, 150), 'G': (2010, 235), 'H': (2012, 100), 'I': (2014, 190), 'J': (2016, 262),
             'K': (2018, 128), 'L': (2019, 215), 'M': (2021, 165), 'N': (2023, 245), 'O': (2024, 112),
             'P': (2001, 290)}
    nodes = {k: (X(yr), py + 70 + (y - 100) * 0.85) for k, (yr, y) in nodes.items()}
    edges = ['AC', 'AD', 'AB', 'BE', 'BD', 'CF', 'DF', 'DG', 'EG', 'EJ', 'FH', 'FI', 'GI', 'GJ', 'HK', 'IK',
             'IL', 'JL', 'KM', 'LM', 'LN', 'MO', 'MN', 'PE', 'CH']
    path = ['A', 'D', 'F', 'I', 'L', 'M', 'O']
    on_path = {a + b for a, b in zip(path, path[1:])}
    for e in edges:
        if e not in on_path:
            (x1, y1), (x2, y2) = nodes[e[0]], nodes[e[1]]
            doc.add(line(*trimmed(x1, y1, x2, y2, 8, 8), color=SKY, w=2, opacity=0.55))
    for a, b in zip(path, path[1:]):
        (x1, y1), (x2, y2) = nodes[a], nodes[b]
        doc.add(line(*trimmed(x1, y1, x2, y2, 10, 10), color=AMBER, w=4.5, cap="butt"))
    for k, (x, y) in nodes.items():
        if k == 'A':
            doc.add(circle(x, y, 13, fill="none", stroke=AMBER, sw=2), circle(x, y, 8, AMBER))
        elif k in path:
            doc.add(circle(x, y, 7, AMBER))
        else:
            doc.add(circle(x, y, 5.5, WHITE))
    ax = py + ph - 34
    doc.add(line(px + 30, ax, px + pw - 26, ax, color=EDGE, w=1.5))
    for yr in range(1995, 2026, 5):
        doc.add(line(X(yr), ax, X(yr), ax + 6, color=EDGE, w=1.5))
        doc.text(X(yr), ax + 22, str(yr), 11, font='mono', fill=MUTED, anchor='middle')
    sx, sy = nodes['A']
    doc.text(sx, sy - 22, "seed", 12, font='mono', fill=MUTED, anchor='middle')
    doc.save("banner.svg")


# ---------------------------------------------------------------- tool map
def make_tool_map():
    doc = Doc(1200, 690, "35 tools in six families")
    frame(doc)
    kicker(doc, 40, 62, "35 TOOLS  ·  6 FAMILIES")
    doc.text(40, 114, "From a query to a verified, measured map of a field.", 34, font='serif', fill=WHITE)
    cw, ch, gx, gy, x0, y0 = 362, 236, 17, 20, 40, 150
    for i, (ic, name, desc, tools) in enumerate(FAMILIES):
        x, y = x0 + (i % 3) * (cw + gx), y0 + (i // 3) * (ch + gy)
        doc.add(rect(x, y, cw, ch, rx=12))
        doc.add(icon_at(ic, x + 20, y + 22, 56))
        doc.text(x + 20, y + 112, name, 19, font='serif-sb', fill=WHITE)
        doc.text(x + 20, y + 138, desc[0], 13, fill=MUTED)
        doc.text(x + 20, y + 156, desc[1], 13, fill=MUTED)
        doc.add(line(x + 158, y + 22, x + 158, y + ch - 22, color=EDGE, w=1.5))
        for j, t in enumerate(tools):
            ty = y + 40 + j * 24.5
            if t in OPENALEX:
                doc.add(f'<rect x="{x + 170}" y="{ty - 8}" width="7" height="7" fill="{SKY}" '
                        f'transform="rotate(45 {x + 173.5} {ty - 4.5})"/>')
            doc.text(x + 186, ty, t, 12.5, font='mono', fill=INK if t in OPENALEX else SUB)
    ly = y0 + 2 * ch + gy + 34
    doc.add(f'<rect x="43" y="{ly - 9}" width="8" height="8" fill="{SKY}" transform="rotate(45 47 {ly - 5})"/>')
    w = doc.text(62, ly, 'source="openalex"', 13, font='mono', fill=INK)
    doc.text(62 + w + 8, ly, "also runs on OpenAlex, with no Scopus subscription", 13, fill=MUTED)
    doc.save("tools.svg")


# ---------------------------------------------------------------- how it works
def make_flow():
    doc = Doc(1200, 560, "How it works")
    frame(doc)
    kicker(doc, 48, 62, "HOW IT WORKS")
    doc.text(48, 114, "You ask in plain words. The server calls the APIs and writes the files.", 32,
             font='serif', fill=WHITE)

    # you
    doc.add(rect(48, 160, 236, 250, rx=12))
    doc.text(70, 192, "YOU ASK", 12, font='mono-md', fill=MUTED, spacing=1.8)
    doc.add(rect(68, 210, 196, 66, fill=NAVY, stroke=None, rx=10),
            poly([(96, 276), (104, 290), (114, 276)], NAVY, 1, fill=NAVY))
    doc.text(86, 238, "Map the research front", 14, fill=INK)
    doc.text(86, 258, "around these six papers.", 14, fill=INK)
    for i, client in enumerate(["Claude Desktop", "Claude Code", "Cursor", "any MCP client"]):
        doc.add(circle(76, 318 + i * 24 - 4, 3, SKY))
        doc.text(88, 318 + i * 24, client, 13, font='mono', fill=SUB)

    # the server
    sx, sw_ = 330, 476
    doc.add(rect(sx, 160, sw_, 250, rx=12, stroke=AMBER, sw=2))
    doc.add(logo_at(sx + 22, 178, 34))
    doc.text(sx + 66, 201, "scopus-plus-mcp", 17, font='mono-md', fill=WHITE)
    for i, (ic, name, _, tools) in enumerate(FAMILIES):
        cx, cy = sx + 24 + (i % 3) * 150, 236 + (i // 3) * 82
        doc.add(icon_at(ic, cx, cy, 40))
        doc.text(cx + 50, cy + 18, name, 14, font='sans-sb', fill=INK)
        doc.text(cx + 50, cy + 36, f"{len(tools)} tools", 12, font='mono', fill=MUTED)
    doc.text(sx + 24, 394, "cache  ·  background jobs  ·  quota checks", 12, font='mono', fill=MUTED)
    doc.add(arrow(290, 285, 324, 285, color=SKY, w=3))

    # the sources
    rx_ = 862
    doc.add(rect(rx_, 160, 290, 250, rx=12))
    doc.text(rx_ + 22, 192, "IT CALLS", 12, font='mono-md', fill=MUTED, spacing=1.8)
    sources = [("Scopus, ScienceDirect", "your Elsevier key"), ("OpenAlex", "open, no subscription"),
               ("Crossref", "reference counts, retractions"), ("Semantic Scholar", "citing sentences, intent"),
               ("Open-access copies", "arXiv, Europe PMC, Unpaywall, CORE")]
    for i, (name, note) in enumerate(sources):
        y = 226 + i * 38
        doc.add(circle(rx_ + 28, y - 5, 5, AMBER if i == 0 else SKY))
        doc.text(rx_ + 44, y, name, 14, font='sans-sb', fill=INK)
        doc.text(rx_ + 44, y + 16, note, 11.5, font='mono', fill=MUTED)
    for y in (230, 285, 340):
        doc.add(arrow(sx + sw_ + 6, 285, rx_ - 8, y, color=SKY, w=2.5, head=10))

    # the files
    doc.add(arrow(sx + sw_ / 2, 414, sx + sw_ / 2, 446, color=AMBER, w=3))
    doc.add(rect(48, 452, 1104, 66, fill=PANEL, stroke=EDGE, rx=12, dash="6 5"))
    doc.text(70, 491, "WRITTEN TO DISK", 12, font='mono-md', fill=MUTED, spacing=1.8)
    x = 230
    for chip in ["JSON", "CSV", "GraphML", "Pajek .net .clu", "PNG", "HTML graph", "BibTeX .bib"]:
        w = FONTS['mono'].width(chip, 13) + 26
        doc.add(rect(x, 470, w, 30, fill=NAVY, stroke=None, rx=15))
        doc.text(x + 13, 490, chip, 13, font='mono', fill=INK)
        x += w + 12
    doc.text(x + 8, 490, "for Pajek, VOSviewer, Gephi, Zotero", 13, fill=MUTED)
    doc.save("flow.svg")


# ---------------------------------------------------------------- main path analysis
MP_NODES = [(24, 100), (70, 46), (70, 154), (122, 98), (166, 40), (168, 162), (208, 100), (244, 52), (244, 152)]
MP_EDGES = [(0, 1), (0, 2), (0, 3), (1, 3), (1, 4), (2, 3), (2, 5), (3, 4), (3, 6), (3, 5), (4, 7), (5, 8),
            (6, 7), (6, 8), (4, 6)]


def spc(nodes, edges):
    """Search path count per edge: source-to-sink paths through it (Hummon & Doreian 1989)."""
    n = len(nodes)
    out = {i: [v for u, v in edges if u == i] for i in range(n)}
    inn = {i: [u for u, v in edges if v == i] for i in range(n)}
    order = sorted(range(n), key=lambda i: nodes[i][0])  # x is time: a topological order here
    fwd, back = {}, {}
    for i in order:
        fwd[i] = 1 if not inn[i] else sum(fwd[u] for u in inn[i])
    for i in reversed(order):
        back[i] = 1 if not out[i] else sum(back[v] for v in out[i])
    weights = {(u, v): fwd[u] * back[v] for u, v in edges}
    path, cur = [0], 0
    while out[cur]:  # local (greedy) main path from the source
        cur = max(out[cur], key=lambda v: weights[(cur, v)])
        path.append(cur)
    return weights, path


def make_main_path():
    doc = Doc(1200, 466, "Main path analysis")
    frame(doc)
    kicker(doc, 48, 62, "MAIN PATH ANALYSIS  ·  citation_network")
    doc.text(48, 114, "From a set of papers to the path that carries the most citation flow.", 32,
             font='serif', fill=WHITE)
    weights, path = spc(MP_NODES, MP_EDGES)
    top = max(weights.values())
    on_path = set(zip(path, path[1:]))
    steps = [("01", "Corpus", ("ids, a query, or Scopus and", "Web of Science exports")),
             ("02", "Citation network", ("each reference list, kept where", "it points inside the set")),
             ("03", "SPC weights", ("source-to-sink paths through", "each edge (also SPLC, SPNP)")),
             ("04", "Main path", ("the heaviest route; key routes", "add the next strongest"))]
    pw, gap = 264, 16
    for i, (num, name, cap) in enumerate(steps):
        px, py = 48 + i * (pw + gap), 146
        doc.add(rect(px, py, pw, 230, rx=12, stroke=AMBER if i == 3 else EDGE, sw=2 if i == 3 else 1.5))
        doc.text(px + 18, py + 28, num, 12, font='mono-md', fill=AMBER, spacing=1)
        doc.text(px + 44, py + 28, name, 15, font='sans-sb', fill=INK)
        gx, gy = px + 2, py + 46
        if i >= 1:
            for (u, v) in MP_EDGES:
                (x1, y1), (x2, y2) = MP_NODES[u], MP_NODES[v]
                seg = trimmed(gx + x1, gy + y1, gx + x2, gy + y2, 9, 10)
                if i == 1:
                    doc.add(arrow(*seg, color=SKY, w=2, head=8))
                elif i == 2:
                    doc.add(line(*seg, color=SKY, w=1.5 + 5.5 * weights[(u, v)] / top, opacity=0.85))
                elif (u, v) in on_path:
                    doc.add(arrow(*seg, color=AMBER, w=4, head=11))
                else:
                    doc.add(line(*seg, color=SKY, w=1.5, opacity=0.35))
            if i == 2:
                for (u, v), wgt in weights.items():
                    (x1, y1), (x2, y2) = MP_NODES[u], MP_NODES[v]
                    mx, my = gx + (x1 + x2) / 2, gy + (y1 + y2) / 2
                    lw = FONTS['mono'].width(str(wgt), 10) + 8
                    doc.add(rect(mx - lw / 2, my - 8, lw, 15, fill=BG, stroke=None, rx=4))
                    doc.text(mx, my + 3.5, str(wgt), 10, font='mono', fill=WHITE, anchor='middle')
        for k, (x, y) in enumerate(MP_NODES):
            fill = AMBER if (i == 3 and k in path) else WHITE
            doc.add(circle(gx + x, gy + y, 6.5 if fill == AMBER else 5.5, fill,
                           opacity=0.5 if (i == 3 and k not in path) else None))
        doc.text(px + 18, py + 262, cap[0], 13, fill=SUB)
        doc.text(px + 18, py + 280, cap[1], 13, fill=SUB)
        if i < 3:
            doc.add(arrow(px + pw + 2, py + 115, px + pw + gap - 2, py + 115, color=MUTED, w=2, head=7))
    doc.save("main-path.svg")


# ---------------------------------------------------------------- transmission audit
def make_transmission():
    doc = Doc(1200, 470, "Transmission audit of a main path")
    frame(doc)
    kicker(doc, 48, 62, "TRANSMISSION AUDIT  ·  path_transmission")
    doc.text(48, 114, "Does each citation on the main path carry the idea forward?", 32, font='serif', fill=WHITE)
    xs, y = [110, 340, 570, 800, 1030], 268
    labels = [("substantive", SKY, None), ("construct-shifted", AMBER, None), ("hollow", RUST, "8 7"),
              ("unresolved", MUTED, "2 7")]
    for (x1, x2), (lab, color, dash) in zip(zip(xs, xs[1:]), labels):
        doc.add(arrow(*trimmed(x1, y, x2, y, 16, 18), color=color, w=4, dash=dash, head=13))
        mx = (x1 + x2) / 2
        # the citing sentence behind the edge
        doc.add(rect(mx - 62, 162, 124, 50, fill=PANEL, stroke=EDGE, rx=8),
                poly([(mx - 8, 212), (mx, 222), (mx + 8, 212)], EDGE, 1.5, fill=PANEL))
        if lab == "unresolved":
            doc.text(mx, 193, "no sentence found", 11, font='mono', fill=MUTED, anchor='middle')
        else:
            doc.add(bar(mx - 46, 176, 92, 5, SUB), bar(mx - 46, 188, 60 if lab != "hollow" else 48, 5, SUB))
            if lab == "substantive":
                doc.add(bar(mx + 18, 187, 28, 7, AMBER))
            if lab == "hollow":
                doc.text(mx + 28, 194, "[3-7]", 11, font='mono', fill=RUST, anchor='middle')
        cw = FONTS['mono'].width(lab, 12) + 24
        doc.add(rect(mx - cw / 2, y + 22, cw, 26, fill=BG, stroke=color, sw=1.5, rx=13))
        doc.text(mx, y + 40, lab, 12, font='mono', fill=color if color != MUTED else SUB, anchor='middle')
    for i, x in enumerate(xs):
        doc.add(circle(x, y, 13, AMBER))
        doc.text(x, y - 26, f"P{i + 1}", 12, font='mono-md', fill=MUTED, anchor='middle')
    # coding sheet -> two coders -> agreement
    by = 372
    doc.add(rect(48, by, 1104, 64, fill=PANEL, stroke=EDGE, rx=12, dash="6 5"))
    steps = [("coding sheet .csv", "draft label + evidence per edge"), ("coder 1, coder 2", "label each edge blind"),
             ("coding_agreement", "Cohen's kappa, confusion matrix")]
    for i, (a, b) in enumerate(steps):
        x = 76 + i * 372
        doc.text(x, by + 28, a, 14, font='mono-md', fill=INK)
        doc.text(x, by + 48, b, 12.5, fill=MUTED)
        if i < 2:
            doc.add(arrow(x + 300, by + 32, x + 344, by + 32, color=SKY, w=2.5, head=9))
    doc.save("transmission.svg")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fonts', type=Path, default=OUT / '.fonts')
    args = ap.parse_args()
    load_fonts(args.fonts)
    make_icons()
    make_banner()
    make_tool_map()
    make_flow()
    make_main_path()
    make_transmission()


if __name__ == '__main__':
    main()
