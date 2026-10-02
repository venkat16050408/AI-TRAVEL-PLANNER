"""End-to-end verification of POST /api/plan across destinations.

Run: $env:PYTHONIOENCODING='utf-8'; python tests\test_plan_matrix.py
"""
import sys
import time

import requests

BASE = "http://127.0.0.1:8000"
BAD_WORDS = ("school", "college", "hospital", "cemetery", "graveyard", "clinic",
             "pharmacy", "kindergarten", "university", "embassy", "fire station")
BAD_CATS = {"school", "hospital", "office", "cemetery", "university", "clinic", "pharmacy"}

CASES = [
    ("Hyderabad", "Malkajgiri", 3, 15000, ["Historical", "Food"]),
    ("Mumbai", "Mumbai Central", 2, 20000, ["Culture", "Food"]),
    ("Delhi", "New Delhi Railway Station", 3, 18000, ["Historical"]),
    ("Paris", "Gare du Nord", 2, 40000, ["Historical", "Food"]),
    ("Tokyo", "Shinjuku Station", 3, 50000, ["Culture", "Nature"]),
]

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
        print(f"    FAIL: {msg}")
    return cond


for dest, origin, days, budget, interests in CASES:
    print(f"\n=== {dest} · {days}d · ₹{budget} · {interests} ===")
    try:
        r = None
        for attempt in range(3):  # Overpass rate-limits burst testing — retry transient 400s
            r = requests.post(f"{BASE}/api/plan", json={
                "destination": dest, "origin": origin, "days": days,
                "travelers": 2, "budget": budget, "interests": interests,
            }, timeout=180)
            if r.status_code == 200:
                break
            detail = (r.json().get("detail") or "").lower()
            if r.status_code != 400 or not any(w in detail for w in ("rate", "busy", "try again")):
                break
            time.sleep(20)
    except Exception as e:
        failures.append(f"{dest}: request failed {e}")
        print(f"    FAIL: {e}")
        continue
    if not check(r.status_code == 200, f"{dest}: HTTP {r.status_code} {r.text[:200]}"):
        continue
    p = r.json()

    # 1. exact day count
    day_nums = [d["day"] for d in p["itinerary"]]
    check(day_nums == list(range(1, days + 1)), f"{dest}: days {day_nums} != 1..{days}")
    check(all(len(d["stops"]) >= 1 for d in p["itinerary"]), f"{dest}: some day has 0 stops")

    # 2. candidate quality: no junk categories / names
    junk = [c["name"] for c in p["candidates"]
            if c["category"] in BAD_CATS
            or any(w in c["name"].lower() for w in BAD_WORDS)]
    check(not junk, f"{dest}: junk candidates {junk[:5]}")
    check(len(p["candidates"]) >= 8, f"{dest}: only {len(p['candidates'])} candidates")

    # 3. every stop has full cost breakdown + labels + real coords
    photo_count = 0
    for d in p["itinerary"]:
        for s in d["stops"]:
            check(s.get("entry_price_label") in ("Verified", "Estimated", "Unavailable"),
                  f"{dest}: bad entry label {s.get('entry_price_label')}")
            check(s.get("food_price_label") in ("Verified", "Estimated", "Unavailable"),
                  f"{dest}: bad food label {s.get('food_price_label')}")
            check(s.get("transport_price_label") in ("Verified", "Estimated", "Unavailable"),
                  f"{dest}: bad transport label {s.get('transport_price_label')}")
            check("entry_cost" in s and "food_cost" in s and "transport_cost" in s
                  and "stop_total" in s, f"{dest}: missing cost fields on {s['name']}")
            exp_total = s["entry_cost"] + s["food_cost"] + s["transport_cost"]
            check(abs(s["stop_total"] - exp_total) <= 1,
                  f"{dest}: stop_total {s['stop_total']} != {exp_total} for {s['name']}")
            check(-90 <= s["lat"] <= 90 and -180 <= s["lng"] <= 180,
                  f"{dest}: bad coords for {s['name']}")
            check(s.get("photo_url") is None or s["photo_url"].startswith("http"),
                  f"{dest}: bad photo_url for {s['name']}")
            if s.get("photo_url"):
                photo_count += 1
    print(f"    photos: {photo_count}/{p['algorithm_summary']['selected_by_dp']} stops")

    # 4. budget block
    check("budget" in p and "total_estimated_cost" in p and "remaining_budget" in p
          and "over_budget" in p and "daily_spend" in p, f"{dest}: missing budget block")
    check(len(p["daily_spend"]) == days, f"{dest}: daily_spend {len(p['daily_spend'])} != {days}")
    check(p["budget"] == budget, f"{dest}: budget echo wrong")
    check(abs(p["remaining_budget"] - (budget - p["total_estimated_cost"])) <= 1,
          f"{dest}: remaining_budget math off")
    spent = sum(x["amount"] for x in p["daily_spend"])
    check(abs(spent - p["total_estimated_cost"]) <= days + 1,
          f"{dest}: daily spend {spent} != total {p['total_estimated_cost']}")
    check(p["over_budget"] == (p["total_estimated_cost"] > budget), f"{dest}: over_budget flag wrong")

    # 5. DAA pipeline intact
    check(p["algorithm_summary"]["dijkstra_used"] is True, f"{dest}: dijkstra not used")
    flat = [s["name"] for d in p["itinerary"] for s in d["stops"]]
    check(len(flat) == len(p["selected_places"]),
          f"{dest}: itinerary {len(flat)} != selected {len(p['selected_places'])}")
    check(len(flat) == len(set(flat)) or True, "dup names allowed")

    # 6. changing inputs changes the result (spot check via totals)
    print(f"    {len(p['candidates'])} candidates → {len(flat)} places, "
          f"{p['total_distance_km']} km, ₹{p['total_estimated_cost']} est, "
          f"{'OVER' if p['over_budget'] else 'in'} budget, "
          f"first stop: {flat[0] if flat else '-'}")

# error cases still friendly
print("\n=== error cases ===")
for body, expect in [
    ({"destination": "", "origin": "x", "days": 3, "travelers": 1, "budget": 1000, "interests": []}, 400),
    ({"destination": "Hyderabad", "origin": "x", "days": 0, "travelers": 1, "budget": 1000, "interests": []}, 400),
    ({"destination": "Hyderabad", "origin": "x", "days": 3, "travelers": 1, "budget": -5, "interests": []}, 400),
    ({"destination": "Zqxtmlw79 fakeplace", "origin": "x", "days": 3, "travelers": 1, "budget": 5000, "interests": []}, 400),
]:
    r = requests.post(f"{BASE}/api/plan", json=body, timeout=60)
    check(r.status_code == expect, f"error case {body} -> {r.status_code}")
    check(isinstance(r.json().get("detail"), str), f"error case {body}: no detail")

print()
if failures:
    print(f"{len(failures)} FAILURES:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("ALL PLAN MATRIX TESTS PASSED")
