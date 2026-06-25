"""
Canonical SPC validation — Batagelj (2003) / Wikipedia worked example.

Graph edges (cited → citing):
  A→C, B→C, B→D, C→H, D→F, D→I, F→H, F→I, H→K, I→L, I→M, M→N

Sources: A, B    Sinks: K, L, N

Longest-path-from-source layering used for 'generation' field
(this is the layering that previously triggered the edge-deletion bug):
  A=0, B=0, C=1, D=1, F=2, H=3, I=3, K=4, L=4, M=4, N=5

Expected SPC values from Wikipedia:
  (B,D) = 5   ← primary canonical anchor
  Global main path: B → D → F → I → M → N, sum of edge weights = 15

All 12 edges must be present in the output (guards the Bug-1 regression).
"""

import unittest
from scopus_mcp.utils import compute_main_path

# ---------------------------------------------------------------------------
# Canonical graph construction
# ---------------------------------------------------------------------------

# Edges as (parent, child) — the direction records use for 'parents'
_EDGES = [
    ('A', 'C'), ('B', 'C'), ('B', 'D'),
    ('C', 'H'), ('D', 'F'), ('D', 'I'),
    ('F', 'H'), ('F', 'I'),
    ('H', 'K'), ('I', 'L'), ('I', 'M'),
    ('M', 'N'),
]

# Longest-path generation for each node
_GENERATION = {
    'A': 0, 'B': 0,
    'C': 1, 'D': 1,
    'F': 2,
    'H': 3, 'I': 3,
    'K': 4, 'L': 4, 'M': 4,
    'N': 5,
}


def _build_records():
    """Build records in the server format used by compute_main_path."""
    parents_of = {n: [] for n in _GENERATION}
    for p, c in _EDGES:
        parents_of[c].append(p)

    return [
        {
            'scopus_id': node,
            'generation': gen,
            'parents': parents_of[node],
            'title': node,
        }
        for node, gen in _GENERATION.items()
    ]


_RECORDS = _build_records()


def _run():
    return compute_main_path(_RECORDS)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCanonicalEdgesPresent(unittest.TestCase):
    """Bug 1 regression: no valid edge may be deleted."""

    def test_all_12_edges_present(self):
        result = _run()
        edge_pairs = {(e['source'], e['target']) for e in result['edges']}
        for p, c in _EDGES:
            self.assertIn(
                (p, c), edge_pairs,
                f"Edge ({p},{c}) missing — generation-adjacency guard too strict"
            )

    def test_exactly_12_edges(self):
        result = _run()
        self.assertEqual(len(result['edges']), 12)


class TestCanonicalSPCValues(unittest.TestCase):
    """Bug 2 regression: canonical pseudo-terminal SPC must match Batagelj."""

    def _spc(self, u, v):
        result = _run()
        for e in result['edges']:
            if e['source'] == u and e['target'] == v:
                return e['spc_weight']
        return None

    def test_bd_equals_5(self):
        """Primary canonical anchor: spc(B,D) == 5 (Batagelj 2003 / Wikipedia)."""
        self.assertEqual(self._spc('B', 'D'), 5)

    def test_bc_equals_1(self):
        """spc(B,C) = n_minus[B]*n_plus[C] = 1*1 = 1.
        n_plus[C]=1: C's only outgoing path is C→H→K (one sink)."""
        self.assertEqual(self._spc('B', 'C'), 1)

    def test_ac_equals_1(self):
        """spc(A,C) = n_minus[A]*n_plus[C] = 1*1 = 1."""
        self.assertEqual(self._spc('A', 'C'), 1)

    def test_df_equals_3(self):
        """spc(D,F): n_minus[D]=2 (paths A,B→D via B→D + n_minus contrib),
        n_plus[F]=paths F→{K,L,N} = H→K + I→L + I→M→N = 3. spc=2*3? Let's
        compute: n_minus[D]=n_minus[B]=1 (B is D's only parent). n_plus[F]:
        F→H→K (1) + F→I→L (1) + F→I→M→N (1) = 3. spc(D,F)=1*3=3."""
        self.assertEqual(self._spc('D', 'F'), 3)

    def test_kirchhoff_invariant_node_f(self):
        """Intermediate node F: sum of in-edge SPC weights == sum of out-edge SPC weights.
        In-edges: (D,F). Out-edges: (F,H), (F,I).
        (Kirchhoff / flow conservation property of canonical SPC.)
        """
        result = _run()
        spc = {(e['source'], e['target']): e['spc_weight'] for e in result['edges']}
        in_sum  = spc.get(('D', 'F'), 0)
        out_sum = spc.get(('F', 'H'), 0) + spc.get(('F', 'I'), 0)
        self.assertEqual(in_sum, out_sum,
            f"Kirchhoff violated at F: in={in_sum}, out={out_sum}")

    def test_kirchhoff_invariant_node_i(self):
        """Node I: in-edges (D,I) and (F,I); out-edges (I,L) and (I,M)."""
        result = _run()
        spc = {(e['source'], e['target']): e['spc_weight'] for e in result['edges']}
        in_sum  = spc.get(('D', 'I'), 0) + spc.get(('F', 'I'), 0)
        out_sum = spc.get(('I', 'L'), 0) + spc.get(('I', 'M'), 0)
        self.assertEqual(in_sum, out_sum,
            f"Kirchhoff violated at I: in={in_sum}, out={out_sum}")


class TestGlobalMainPath(unittest.TestCase):
    """Canonical global main path: B→D→F→I→M→N with sum of SPC weights = 15."""

    def test_global_path_equals_canonical(self):
        result = _run()
        self.assertEqual(
            result['global_main_path'],
            ['B', 'D', 'F', 'I', 'M', 'N'],
            f"Global main path mismatch: {result['global_main_path']}"
        )

    def test_global_path_sum_equals_14(self):
        """Sum of SPC edge weights along B→D→F→I→M→N:
        spc(B,D)=5, spc(D,F)=3, spc(F,I)=2, spc(I,M)=2, spc(M,N)=2 → total=14."""
        result = _run()
        spc = {(e['source'], e['target']): e['spc_weight'] for e in result['edges']}
        path = result['global_main_path']
        total = sum(spc.get((path[i], path[i+1]), 0) for i in range(len(path)-1))
        self.assertEqual(total, 14,
            f"Global path weight sum = {total}, expected 14. Path: {path}")

    def test_global_main_path_key_present(self):
        result = _run()
        self.assertIn('global_main_path', result)


class TestSameGenEdgeStillFiltered(unittest.TestCase):
    """v0.7.2 backward-bug invariant: same-generation edges are still excluded."""

    def test_same_gen_edge_not_in_dag(self):
        """Inject a gen-1→gen-1 edge; it must not appear in SPC output."""
        records = [
            {'scopus_id': 'A', 'generation': 0, 'parents': [],            'title': 'A'},
            {'scopus_id': 'B', 'generation': 1, 'parents': ['A'],          'title': 'B'},
            # C has legitimate parent A (gen0) plus injected same-gen parent B (gen1)
            {'scopus_id': 'C', 'generation': 1, 'parents': ['A', 'B'],     'title': 'C'},
            {'scopus_id': 'D', 'generation': 2, 'parents': ['B', 'C'],     'title': 'D'},
        ]
        result = compute_main_path(records)
        edge_pairs = [(e['source'], e['target']) for e in result['edges']]
        self.assertNotIn(('B', 'C'), edge_pairs,
            "Same-generation edge B→C (gen1→gen1) must be filtered")

    def test_multi_gen_spanning_edge_preserved(self):
        """An edge that spans more than 1 generation layer must NOT be removed."""
        # B (gen0) → D (gen2): skips gen1 layer — legitimate in a DAG
        records = [
            {'scopus_id': 'A', 'generation': 0, 'parents': [],       'title': 'A'},
            {'scopus_id': 'B', 'generation': 0, 'parents': [],       'title': 'B'},
            {'scopus_id': 'C', 'generation': 1, 'parents': ['A'],    'title': 'C'},
            {'scopus_id': 'D', 'generation': 2, 'parents': ['B', 'C'], 'title': 'D'},
        ]
        result = compute_main_path(records)
        edge_pairs = [(e['source'], e['target']) for e in result['edges']]
        self.assertIn(('B', 'D'), edge_pairs,
            "Multi-layer-spanning edge B(gen0)→D(gen2) must be preserved")


if __name__ == '__main__':
    unittest.main(verbosity=2)
