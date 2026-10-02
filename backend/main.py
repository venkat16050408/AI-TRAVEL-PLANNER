import math
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from algorithms.knapsack import knapsack_select
from algorithms.graph import TravelGraph, haversine_km
from algorithms.tsp import optimize_route, nearest_neighbour, two_opt, route_cost
from algorithms.dijkstra import dijkstra, shortest_path
import locations

app = FastAPI(title="AI Travel Planner")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc: RequestValidationError):
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"] if p != "body")
        if err["type"] in ("greater_than", "greater_than_equal") and "budget" in loc:
            msg = "Budget must be greater than zero."
        elif "days" in loc:
            msg = "Number of days must be between 1 and 14."
        elif "travelers" in loc:
            msg = "Number of travelers must be between 1 and 20."
        elif "destination" in loc or "origin" in loc:
            msg = f"{loc.capitalize()} is required."
        else:
            msg = f"Invalid value for {loc or 'request'}."
        return JSONResponse(status_code=400, content={"detail": msg})
    return JSONResponse(status_code=400, content={"detail": "Invalid request."})


class PlanRequest(BaseModel):
    destination: str = Field(..., min_length=1)
    origin: str = Field(..., min_length=1)
    days: int = Field(..., ge=1, le=14)
    travelers: int = Field(..., ge=1, le=20)
    budget: float = Field(..., gt=0)
    interests: List[str] = []


DAILY_MINUTES = 9 * 60  # usable sightseeing time per day


def build_itinerary(route: List[Dict[str, Any]], legs: List[Dict[str, Any]], days: int):
    """Distribute the optimized route across exactly `days` days."""
    total_needed = sum(
        (legs[i]["time_minutes"] if i < len(legs) else 0) + stop["duration_minutes"]
        for i, stop in enumerate(route)
    )
    # Balanced daily capacity: never exceed the real daily limit, but spread the
    # route evenly so later days aren't left empty.
    target = min(DAILY_MINUTES, math.ceil(total_needed / days)) if days > 0 else DAILY_MINUTES
    buckets: List[List[Dict[str, Any]]] = [[] for _ in range(days)]
    day_used = [0] * days
    day_idx = 0
    n = len(route)
    for i, stop in enumerate(route):
        leg = legs[i] if i < len(legs) else None
        travel = leg["time_minutes"] if leg else 0
        visit = stop["duration_minutes"]
        # Always keep at least one stop available for each remaining day.
        remaining_days = days - day_idx - 1
        must_leave = remaining_days  # stops we must reserve
        while day_idx < days - 1 and buckets[day_idx]:
            too_long = day_used[day_idx] + travel + visit > DAILY_MINUTES
            balanced = day_used[day_idx] >= target and (n - i) > must_leave
            if too_long or balanced:
                day_idx += 1
            else:
                break
        buckets[day_idx].append({**stop, "leg": leg})
        day_used[day_idx] += travel + visit
    return buckets


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/plan")
def plan(req: PlanRequest):
    dest_info, candidates, err = locations.fetch_candidates(req.destination, req.interests)
    if err:
        raise HTTPException(status_code=400, detail=err)
    if len(candidates) < 2:
        raise HTTPException(status_code=400, detail=f"Only {len(candidates)} valid place(s) found in \"{req.destination}\". Try a nearby larger area or different interests.")

    origin_info = locations.geocode(req.origin, near=req.destination)
    origin_note = None
    if not origin_info:
        # Fall back to the destination city centre, but say so explicitly.
        origin_info = locations.geocode(req.destination)
        if not origin_info:
            raise HTTPException(status_code=400, detail=f"Could not find the origin/hotel \"{req.origin}\" or \"{req.destination}\" on the map. Try a landmark, neighbourhood or street name.")
        origin_note = f"Origin \"{req.origin}\" wasn't found on the map, so routing starts from {req.destination} city centre."
    origin_info = {"name": req.origin, "lat": origin_info["lat"], "lng": origin_info["lng"]}

    # --- Dynamic programming: budget per traveler-group & total visitable time ---
    total_time_budget = req.days * DAILY_MINUTES
    selected = knapsack_select(candidates, req.budget, max(1, total_time_budget // 30))
    budget_note = None
    if not selected:
        # Budget too tight for any stop: fall back to the best-valued picks and say so.
        selected = sorted(candidates, key=lambda p: -p["value"])[: max(2, req.days)]
        fallback_cost = sum(p["cost"] for p in selected)
        budget_note = (f"Your budget (₹{req.budget:,.0f}) was too small for every candidate "
                       f"(cheapest ~₹{min(p['cost'] for p in candidates):,.0f}). "
                       f"The plan below uses the best-value stops anyway (~₹{fallback_cost:,.0f}); "
                       f"expect to go over budget.")
    # cap places to something sensible
    selected = selected[: max(6, req.days * 4)]

    # --- Graph ---
    all_nodes = [origin_info] + selected
    graph = TravelGraph()
    graph.add_nodes(all_nodes)

    # --- TSP from origin (index 0) ---
    nn_route = nearest_neighbour(graph, start=0)
    opt_route = optimize_route(graph, start=0)  # NN + 2-opt

    # --- Dijkstra shortest paths from the origin (used for leg travel) ---
    dist_time, _ = dijkstra(graph, 0)

    route_places = []
    legs = []
    prev = 0
    for k, idx in enumerate(opt_route[1:]):
        leg_edge = graph.edge(prev, idx)
        # Dijkstra path through the sparse travel graph (nearest-neighbour links)
        path = shortest_path(graph, prev, idx)
        if len(path) >= 2:
            km = sum(graph.edge(path[i], path[i + 1])["distance_km"] for i in range(len(path) - 1))
            mins = sum(graph.edge(path[i], path[i + 1])["time_minutes"] for i in range(len(path) - 1))
            hop_names = [all_nodes[p]["name"] for p in path]
        else:
            km = leg_edge["distance_km"]
            mins = leg_edge["time_minutes"]
            hop_names = [all_nodes[prev]["name"], all_nodes[idx]["name"]]
        leg = {
            "from": all_nodes[prev]["name"],
            "to": all_nodes[idx]["name"],
            "distance_km": round(km, 2),
            "time_minutes": round(mins, 1),
            "cost": round(km * 15, 0),
            "dijkstra_path": hop_names,
            "dijkstra_time_minutes": round(dist_time[idx], 1) if dist_time[idx] != float("inf") else None,
        }
        route_places.append({**all_nodes[idx], "leg": leg})
        legs.append(leg)
        prev = idx

    # Photos for selected places only (Google Places → Wikimedia Commons → None).
    locations.attach_photos(route_places, req.destination)

    itinerary_buckets = build_itinerary(route_places, legs, req.days)
    itinerary = []
    daily_spend = []
    for d, bucket in enumerate(itinerary_buckets, start=1):
        stops = []
        day_total = 0.0
        for s in bucket:
            leg = s.get("leg")
            transport = leg["cost"] if leg else 0
            stop_total = s["entry_cost"] + s["food_cost"] + transport
            day_total += stop_total
            stops.append({
                "name": s["name"],
                "category": s["category"],
                "description": s["description"],
                "duration_minutes": s["duration_minutes"],
                "cost": s["cost"],
                "entry_cost": s["entry_cost"],
                "entry_price_label": s["entry_price_label"],
                "food_cost": s["food_cost"],
                "food_price_label": s["food_price_label"],
                "transport_cost": round(transport, 0),
                "transport_price_label": "Estimated",
                "stop_total": round(stop_total, 0),
                "photo_url": s.get("photo_url"),
                "lat": s["lat"],
                "lng": s["lng"],
                "distance_from_previous_km": leg["distance_km"] if leg else 0,
                "travel_time_from_previous_minutes": leg["time_minutes"] if leg else 0,
            })
        itinerary.append({"day": d, "stops": stops})
        daily_spend.append({"day": d, "amount": round(day_total, 0)})

    total_distance = sum(l["distance_km"] for l in legs)
    total_travel = sum(l["time_minutes"] for l in legs)
    total_visit = sum(s["duration_minutes"] for s in route_places)
    # Real total = entry + food per stop + actual transport legs.
    total_cost = sum(s["entry_cost"] + s["food_cost"] for s in route_places) + sum(l["cost"] for l in legs)
    remaining_budget = req.budget - total_cost

    nn_cost = route_cost(graph, nn_route)
    opt_cost = route_cost(graph, opt_route)

    warning = None
    empty_days = sum(1 for b in itinerary_buckets if not b)
    if empty_days:
        warning = f"Only {len(route_places)} places fit the constraints, so {empty_days} day(s) may have fewer or no stops. Try a larger budget or more travel time."
    if budget_note:
        warning = f"{warning} {budget_note}" if warning else budget_note
    if total_cost > req.budget:
        over = f"Estimated total (₹{total_cost:,.0f}) exceeds your budget (₹{req.budget:,.0f}) by ₹{total_cost - req.budget:,.0f}, mostly from travel costs between stops."
        warning = f"{warning} {over}" if warning else over

    return {
        "destination": req.destination,
        "origin": origin_info,
        "origin_note": origin_note,
        "destination_center": dest_info,
        "candidates": candidates,
        "selected_places": [{k: v for k, v in p.items()} for p in selected],
        "optimized_route": [all_nodes[i]["name"] for i in opt_route],
        "days": req.days,
        "itinerary": itinerary,
        "total_distance_km": round(total_distance, 2),
        "total_travel_time_minutes": round(total_travel, 1),
        "total_visit_minutes": round(total_visit, 1),
        "total_cost": round(total_cost, 0),
        "budget": req.budget,
        "total_estimated_cost": round(total_cost, 0),
        "remaining_budget": round(remaining_budget, 0),
        "over_budget": total_cost > req.budget,
        "daily_spend": daily_spend,
        "warning": warning,
        "algorithm_summary": {
            "candidates_found": len(candidates),
            "selected_by_dp": len(selected),
            "nn_route_distance_km": round(nn_cost, 2),
            "two_opt_route_distance_km": round(opt_cost, 2),
            "dijkstra_used": True,
        },
    }
