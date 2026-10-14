"""Cluster id for one sweep→displacement episode, plus overlapping holds.

Two trades share a cluster when they name the same sweep bar, or when their
holding windows overlap (inclusive). The power floor counts clusters, not trades.
"""

from __future__ import annotations


def _find(parent: list[int], i: int) -> int:
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def _union(parent: list[int], a: int, b: int) -> None:
    ra, rb = _find(parent, a), _find(parent, b)
    if ra != rb:
        parent[rb] = ra


def _span(row: dict) -> tuple[int, int]:
    a = int(row["entry_idx"])
    b = int(row["exit_idx"])
    return (a, b) if a <= b else (b, a)


def assign_clusters(rows: list[dict]) -> list[int]:
    """Return a 0-based cluster id per row, in first-seen order.

    Each row needs `entry_idx` and `exit_idx`. `sweep_idx` may be None.
    """
    n = len(rows)
    parent = list(range(n))
    by_sweep: dict[int, int] = {}
    for i, row in enumerate(rows):
        sweep = row.get("sweep_idx")
        if sweep is None:
            continue
        key = int(sweep)
        if key in by_sweep:
            _union(parent, i, by_sweep[key])
        else:
            by_sweep[key] = i
    spans = [_span(row) for row in rows]
    for i in range(n):
        lo, hi = spans[i]
        for j in range(i + 1, n):
            lo2, hi2 = spans[j]
            if lo <= hi2 and lo2 <= hi:
                _union(parent, i, j)
    order: list[int] = []
    ids: list[int] = []
    for i in range(n):
        root = _find(parent, i)
        if root not in order:
            order.append(root)
        ids.append(order.index(root))
    return ids


def n_clusters(rows: list[dict]) -> int:
    if not rows:
        return 0
    return len(set(assign_clusters(rows)))
