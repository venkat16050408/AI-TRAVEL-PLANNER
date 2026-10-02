"""Unit tests for the DAA algorithms. Run: python tests/test_algorithms.py"""
import sys, os, random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from algorithms.knapsack import knapsack_select
from algorithms.graph import TravelGraph, haversine_km
from algorithms.tsp import nearest_neighbour, two_opt, optimize_route, route_cost
from algorithms.dijkstra import dijkstra, shortest_path


def make_places(n=8):
    return [
        {"name": f"p{i}", "cost": 500 * (i + 1), "duration_minutes": 60,
         "value": 10 - i if i < 6 else 3, "lat": 17.4 + i * 0.01, "lng": 78.4 + i * 0.01}
        for i in range(n)
    ]


def test_knapsack():
    places = make_places()
    sel = knapsack_select(places, budget=1500, time_slots=10)  # 1500 INR / 10 slots
    cost = sum(p["cost"] for p in sel)
    time_ = sum(p["duration_minutes"] for p in sel)
    assert cost <= 1500, f"over budget: {cost}"
    assert time_ <= 10 * 30, f"over time: {time_}"
    # picks high-value cheap items first
    assert sel, "selected nothing"
    print(f"knapsack OK: {len(sel)} places, cost {cost}<=1500, time {time_}<=300")


def test_knapsack_no_cheat():
    places = make_places()
    # tiny budget must select zero or only affordable items
    sel = knapsack_select(places, budget=100, time_slots=5)
    assert sum(p["cost"] for p in sel) <= 100
    print(f"knapsack tiny budget OK: {len(sel)} selected")


def test_graph():
    g = TravelGraph()
    g.add_nodes([
        {"name": "a", "lat": 0.0, "lng": 0.0},
        {"name": "b", "lat": 0.0, "lng": 1.0},
        {"name": "c", "lat": 1.0, "lng": 1.0},
    ])
    e = g.edge(0, 1)
    assert e["distance_km"] > 100 and e["time_minutes"] > 0 and e["cost"] >= 0
    assert haversine_km(0, 0, 0, 1) > 100
    print(f"graph OK: edge a->b = {e}")


def test_tsp():
    random.seed(7)
    pts = [{"name": f"n{i}", "lat": 17.3 + random.random() * 0.1,
            "lng": 78.4 + random.random() * 0.1} for i in range(12)]
    g = TravelGraph()
    g.add_nodes(pts)
    nn = nearest_neighbour(g, 0)
    assert sorted(nn) == list(range(12)) and nn[0] == 0, "NN invalid"
    improved = two_opt(g, nn)
    assert sorted(improved) == list(range(12)) and improved[0] == 0, "2-opt invalid"
    c_nn, c_opt = route_cost(g, nn), route_cost(g, improved)
    assert c_opt <= c_nn + 1e-9, f"2-opt worsened route {c_opt} > {c_nn}"
    print(f"tsp OK: NN={c_nn:.2f} km, 2-opt={c_opt:.2f} km (<= NN)")


def test_dijkstra():
    g = TravelGraph()
    g.add_nodes([{"name": x, "lat": 17.3, "lng": 78.4 + i * 0.05} for i, x in enumerate("ABCD")])
    dist, prev = dijkstra(g, 0)
    assert dist[0] == 0 and all(d < float("inf") for d in dist)
    path = shortest_path(g, 0, 3)
    assert path[0] == 0 and path[-1] == 3 and len(path) >= 2, f"bad path {path}"
    # consecutive hops must be actual graph links
    for i in range(len(path) - 1):
        assert path[i + 1] in g.adj[path[i]], f"hop {path[i]}->{path[i+1]} not in graph"
    # shortest path time equals accumulated edge times along path
    total = sum(g.time_weight(path[i], path[i + 1]) for i in range(len(path) - 1))
    assert abs(total - dist[3]) < 1e-6, f"{total} != {dist[3]}"

    # Sparse graph case: only nearest-neighbour links, so Dijkstra must chain hops
    import random
    random.seed(3)
    pts = [{"name": f"n{i}", "lat": 17.3 + random.random() * 0.2,
            "lng": 78.4 + random.random() * 0.2} for i in range(15)]
    g2 = TravelGraph(k_neighbors=2)
    g2.add_nodes(pts)
    d2, _ = dijkstra(g2, 0)
    p2 = shortest_path(g2, 0, 14)
    assert p2 and p2[0] == 0 and p2[-1] == 14, f"sparse path {p2}"
    t2 = sum(g2.time_weight(p2[i], p2[i + 1]) for i in range(len(p2) - 1))
    assert abs(t2 - d2[14]) < 1e-6
    print(f"dijkstra OK: dense 0->3 {dist[3]:.1f} min via {path}; sparse 0->14 {t2:.1f} min via {len(p2)} hops")


if __name__ == "__main__":
    test_knapsack()
    test_knapsack_no_cheat()
    test_graph()
    test_tsp()
    test_dijkstra()
    print("ALL ALGORITHM TESTS PASSED")
