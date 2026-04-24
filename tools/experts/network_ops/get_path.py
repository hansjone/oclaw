from __future__ import annotations

from collections import deque
from typing import Any

from oclaw.tools.base import ToolSpec


def _default_edges() -> list[tuple[str, str]]:
    return [
        ("R1", "R2"),
        ("R2", "R3"),
        ("R3", "R4"),
        ("R2", "R5"),
        ("R5", "R4"),
        ("R1", "SW1"),
        ("SW1", "FW1"),
        ("FW1", "R3"),
    ]


def _build_adj(edges: list[tuple[str, str]]) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = {}
    for a, b in edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    return adj


def _bfs_path(adj: dict[str, set[str]], src: str, dst: str) -> list[str] | None:
    if src == dst:
        return [src]
    q: deque[str] = deque([src])
    prev: dict[str, str | None] = {src: None}
    while q:
        cur = q.popleft()
        for nxt in sorted(adj.get(cur, set())):
            if nxt in prev:
                continue
            prev[nxt] = cur
            if nxt == dst:
                q.clear()
                break
            q.append(nxt)
    if dst not in prev:
        return None
    path: list[str] = []
    cur2: str | None = dst
    while cur2 is not None:
        path.append(cur2)
        cur2 = prev[cur2]
    path.reverse()
    return path


def get_path_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        src = str(args.get("src"))
        dst = str(args.get("dst"))
        raw_edges = args.get("topology_edges")

        edges: list[tuple[str, str]]
        if raw_edges is None:
            edges = _default_edges()
        else:
            edges = []
            for item in raw_edges:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    return {"ok": False, "error": "topology_edges must be an array of pairs; each item must contain two node names."}
                edges.append((str(item[0]), str(item[1])))

        adj = _build_adj(edges)
        path = _bfs_path(adj, src, dst)
        if not path:
            return {"ok": False, "src": src, "dst": dst, "error": "No reachable path in the given topology."}
        return {"ok": True, "src": src, "dst": dst, "hops": path, "hop_count": len(path) - 1}

    return ToolSpec(
        name="get_path",
        description="Compute the shortest path from src to dst (BFS) over an undirected topology. Optional topology_edges overrides the built-in demo graph.",
        parameters={
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "Source node name."},
                "dst": {"type": "string", "description": "Destination node name."},
                "topology_edges": {
                    "type": "array",
                    "description": 'Optional edge list, e.g. [["R1","R2"],["R2","R3"]].',
                    "items": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 2},
                },
            },
            "required": ["src", "dst"],
            "additionalProperties": False,
        },
        handler=handler,
    )


__all__ = ["get_path_tool"]
