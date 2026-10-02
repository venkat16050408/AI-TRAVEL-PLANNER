# AI Travel Planner — DAA Hackathon

Full-stack trip planner: React + Vite + TypeScript + Tailwind frontend, FastAPI backend,
Google Maps JavaScript API for the map, OpenStreetMap (Nominatim + Overpass) for real place data.

## Pipeline

```
USER INPUT → CANDIDATE LOCATIONS → DYNAMIC PROGRAMMING (2-constraint 0/1 knapsack:
budget + time) → SELECTED LOCATIONS → GRAPH (distance / travel time / travel cost edges)
→ NEAREST NEIGHBOUR → 2-OPT → DIJKSTRA → DAY-WISE ITINERARY → GOOGLE MAP
```

- `backend/algorithms/knapsack.py` — genuine `dp[i][b][t]` knapsack
- `backend/algorithms/graph.py` — weighted graph, haversine distances
- `backend/algorithms/tsp.py` — nearest neighbour + 2-opt
- `backend/algorithms/dijkstra.py` — shortest paths

No place names or coordinates are invented: every candidate comes from OpenStreetMap.
If the location service is down, the API returns a clear error instead of fake data.

## Run

### Backend (port 8000)

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```

### Frontend (port 5173)

```bash
cd frontend
npm install
npm run dev
```

### Google Maps key

```bash
cp .env.example .env          # and frontend/.env.example → frontend/.env
# set VITE_GOOGLE_MAPS_API_KEY=your real key
```

`.env` is git-ignored; never commit keys.

## API

`POST /api/plan`

```json
{ "destination": "Hyderabad", "origin": "Charminar", "days": 3,
  "travelers": 2, "budget": 15000, "interests": ["Historical", "Food"] }
```

Returns `destination, origin, candidates, selected_places, optimized_route, days,
itinerary, total_distance_km, total_travel_time_minutes, total_cost, algorithm_summary`.

## Tests

```bash
python tests/test_algorithms.py   # unit tests for knapsack / NN / 2-opt / Dijkstra
```
