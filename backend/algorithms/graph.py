"""Graph model: nodes = locations, edges = travel legs."""

import math
from typing import List, Dict, Any, Tuple


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


class TravelGraph:
    def __init__(self, city_speed_kmph: float = 28.0, cost_per_km: float = 15.0, k_neighbors: int = 4):
        self.city_speed_kmph = city_speed_kmph
        self.cost_per_km = cost_per_km
        self.k_neighbors = k_neighbors
        self.nodes: List[Dict[str, Any]] = []
        # edges[i][j] = {"distance_km", "time_minutes", "cost"} (complete graph, for TSP)
        self.edges: List[List[Dict[str, float]]] = []
        # adj[i] = list of j indices connected by a travel link (sparse, road-like)
        self.adj: List[List[int]] = []

    def add_nodes(self, locations: List[Dict[str, Any]]):
        self.nodes = locations
        n = len(locations)
        self.edges = [[{} for _ in range(n)] for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                d = haversine_km(
                    locations[i]["lat"], locations[i]["lng"],
                    locations[j]["lat"], locations[j]["lng"],
                )
                t = d / self.city_speed_kmph * 60.0
                self.edges[i][j] = {
                    "distance_km": round(d, 2),
                    "time_minutes": round(t, 1),
                    "cost": round(d * self.cost_per_km, 0),
                }
        # Sparse adjacency: each node connects to its k nearest neighbours.
        # Mirrors road networks (no teleporting) and makes Dijkstra hop chains.
        k = min(self.k_neighbors, max(1, n - 1))
        self.adj = []
        for i in range(n):
            order = sorted((j for j in range(n) if j != i), key=lambda j: self.edges[i][j]["distance_km"])
            self.adj.append(order[:k])

    def edge(self, i: int, j: int) -> Dict[str, float]:
        return self.edges[i][j]

    def time_weight(self, i: int, j: int) -> float:
        return self.edges[i][j]["time_minutes"]
