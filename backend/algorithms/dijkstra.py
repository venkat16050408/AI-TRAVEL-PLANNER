"""Dijkstra shortest paths over the sparse travel graph."""

import heapq
from typing import List, Tuple
from .graph import TravelGraph


def dijkstra(graph: TravelGraph, source: int) -> Tuple[List[float], List[int]]:
    """Shortest travel time from source to every node (cost = edge time_minutes)."""
    n = len(graph.nodes)
    dist = [float("inf")] * n
    prev = [-1] * n
    if n == 0:
        return dist, prev
    dist[source] = 0.0
    pq = [(0.0, source)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v in graph.adj[u]:
            w = graph.time_weight(u, v)
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return dist, prev


def shortest_path(graph: TravelGraph, source: int, target: int) -> List[int]:
    """Hop chain of the shortest-time route between two nodes."""
    _, prev = dijkstra(graph, source)
    path = []
    cur = target
    while cur != -1:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    if path and path[0] == source:
        return path
    return []  # unreachable in the sparse graph
