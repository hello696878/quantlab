"""
Lineage graph rules: cycle detection and bounded traversal.

Scale assumption: a local single-user SQLite registry (hundreds of versions,
not millions), so plain BFS over the edge table is appropriate.  Traversal is
bounded by depth AND node count, and reports truncation honestly.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Set, Tuple

from app.dataset_registry import store

DEFAULT_MAX_DEPTH = 6
MAX_MAX_DEPTH = 12
DEFAULT_NODE_LIMIT = 60
MAX_NODE_LIMIT = 200
# Absolute safety bound on visited edges during any walk.
_EDGE_VISIT_CAP = 10_000


class LineageError(ValueError):
    """Raised on lineage rule violations (self-edge, cycle, missing version)."""


def would_create_cycle(parent_version_id: int, child_version_id: int) -> bool:
    """True when adding parent→child would create a cycle.

    A cycle exists iff ``parent`` is already reachable FROM ``child`` by
    following child edges (i.e. child is an ancestor of parent).  BFS downward
    from ``child`` with a visited set and an absolute edge cap.
    """
    if parent_version_id == child_version_id:
        return True
    seen: Set[int] = {child_version_id}
    queue: deque[int] = deque([child_version_id])
    visited_edges = 0
    while queue:
        current = queue.popleft()
        for edge in store.edges_by_parent(current):
            visited_edges += 1
            if visited_edges > _EDGE_VISIT_CAP:
                # Fail safe: refuse rather than risk an unbounded walk.
                raise LineageError("lineage graph too large to validate safely")
            nxt = edge["child_version_id"]
            if nxt == parent_version_id:
                return True
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return False


def _neighbours(version_id: int, direction: str) -> List[Tuple[int, Dict[str, Any]]]:
    if direction == "up":
        return [(e["parent_version_id"], e) for e in store.edges_by_child(version_id)]
    return [(e["child_version_id"], e) for e in store.edges_by_parent(version_id)]


def bounded_neighborhood(
    root_version_id: int,
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    node_limit: int = DEFAULT_NODE_LIMIT,
) -> Dict[str, Any]:
    """Collect ancestors + descendants of *root* within depth/node bounds.

    Returns ``{"node_ids": {id: (depth, direction)}, "edges": [...],
    "truncated": bool}``.  ``direction`` is ``"self" | "ancestor" |
    "descendant"``; nodes reachable both ways keep their first assignment.
    Invalidated versions stay visible (they are still lineage facts).
    """
    max_depth = max(1, min(int(max_depth), MAX_MAX_DEPTH))
    node_limit = max(1, min(int(node_limit), MAX_NODE_LIMIT))

    node_ids: Dict[int, Tuple[int, str]] = {root_version_id: (0, "self")}
    edges: Dict[int, Dict[str, Any]] = {}
    truncated = False

    for direction, label in (("up", "ancestor"), ("down", "descendant")):
        queue: deque[Tuple[int, int]] = deque([(root_version_id, 0)])
        seen: Set[int] = {root_version_id}
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                # There may be more beyond the horizon — check cheaply.
                if _neighbours(current, direction):
                    truncated = True
                continue
            for neighbour_id, edge in _neighbours(current, direction):
                edges[edge["id"]] = edge
                if neighbour_id in seen:
                    continue
                seen.add(neighbour_id)
                if len(node_ids) >= node_limit:
                    truncated = True
                    continue
                if neighbour_id not in node_ids:
                    node_ids[neighbour_id] = (depth + 1, label)
                queue.append((neighbour_id, depth + 1))

    # Keep only edges whose two endpoints made it into the bounded node set.
    kept_edges = [
        e for e in edges.values()
        if e["parent_version_id"] in node_ids and e["child_version_id"] in node_ids
    ]
    kept_edges.sort(key=lambda e: e["id"])
    return {"node_ids": node_ids, "edges": kept_edges, "truncated": truncated}


__all__ = [
    "DEFAULT_MAX_DEPTH",
    "MAX_MAX_DEPTH",
    "DEFAULT_NODE_LIMIT",
    "MAX_NODE_LIMIT",
    "LineageError",
    "would_create_cycle",
    "bounded_neighborhood",
]
