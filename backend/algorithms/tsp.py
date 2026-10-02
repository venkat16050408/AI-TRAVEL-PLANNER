"""Nearest Neighbour + 2-opt TSP over the travel graph."""

from typing import List
from .graph import TravelGraph


def nearest_neighbour(graph: TravelGraph, start: int = 0) -> List[int]:
    n = len(graph.nodes)
    if n == 0:
        return []
    visited = [False] * n
    route = [start]
    visited[start] = True
    current = start
    for _ in range(n - 1):
        best, best_d = -1, float("inf")
        for j in range(n):
            if not visited[j]:
                d = graph.edge(current, j)["distance_km"]
                if d < best_d:
                    best, best_d = j, d
        route.append(best)
        visited[best] = True
        current = best
    return route


def route_cost(graph: TravelGraph, route: List[int]) -> float:
    return sum(graph.edge(route[i], route[i + 1])["distance_km"] for i in range(len(route) - 1))


def two_opt(graph: TravelGraph, route: List[int]) -> List[int]:
    """Improve route with 2-opt while keeping the starting node fixed at index 0."""
    if len(route) < 4:
        return route
    best = route[:]
    improved = True
    while improved:
        improved = False
        for i in range(1, len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                if route_cost(graph, candidate) < route_cost(graph, best) - 1e-9:
                    best = candidate
                    improved = True
    return best


def optimize_route(graph: TravelGraph, start: int = 0) -> List[int]:
    nn = nearest_neighbour(graph, start)
    return two_opt(graph, nn)
