"""Location provider using OpenStreetMap (Nominatim + Overpass) + photo lookup.

Real, free, no API key for place data. All coordinates come from OSM — never invented.
Photos come from Google Places (when GOOGLE_PLACES_API_KEY is set) or Wikimedia Commons,
verified against the place name; otherwise None (placeholder is shown).
"""

import os
import re
import time
from typing import List, Dict, Any, Optional, Tuple

import requests

NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
GOOGLE_PLACES_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
HEADERS = {"User-Agent": "AI-Travel-Planner-DAA-Hackathon/1.0"}
RATE_LIMITED = object()  # sentinel: all mirrors answered 429

_CACHE: Dict[Any, Any] = {}
_PHOTO_CACHE: Dict[str, Tuple[Optional[str], float]] = {}  # key → (url, cached_at)

# ---------------------------------------------------------------------------
# Interest → OSM tag queries
# ---------------------------------------------------------------------------
# Order matters: Overpass truncates the tail of the result set, so the big
# landmark queries come first and the very numerous food queries come last.
INTEREST_QUERIES = {
    "Historical": [
        'node["historic"]', 'way["historic"]', 'relation["historic"]',
        'node["tourism"~"^(attraction|castle|palace|monument)$"]',
        'way["tourism"~"^(attraction|castle|palace|monument)$"]',
        'relation["tourism"~"^(attraction|castle|palace|monument)$"]',
    ],
    "Culture": [
        'node["tourism"~"^(museum|gallery|artwork)$"]',
        'way["tourism"~"^(museum|gallery)$"]',
        'node["amenity"~"^(arts_centre|theatre|place_of_worship|museum)$"]',
    ],
    "Nature": [
        'node["leisure"~"^(park|nature_reserve|garden)$"]',
        'way["leisure"~"^(park|nature_reserve|garden)$"]',
        'relation["leisure"~"^(park|nature_reserve)$"]',
        'node["tourism"="viewpoint"]',
        'node["natural"~"^(peak|waterfall|volcano)$"]',
        'node["water"~"^(lake|reservoir)$"]',
        'way["water"~"^(lake|reservoir)$"]',
        'relation["water"~"^(lake|reservoir)$"]',
    ],
    "Adventure": [
        'node["tourism"~"^(theme_park|zoo|aquarium)$"]',
        'node["tourism"="viewpoint"]',
        'node["sport"]',
    ],
    "Shopping": ['node["shop"="mall"]', 'node["amenity"="marketplace"]', 'way["shop"="mall"]'],
    "Food": ['node["amenity"~"^(restaurant|cafe|fast_food)$"]'],
}

# Landmarks cover the whole city; food only needs the near neighbourhood
# (a dense core has hundreds of restaurants within 5 km already).
ATTRACTION_RADIUS = 15000
FOOD_RADIUS = 5000
FOOD_INTERESTS = {"Food"}

# Categories that are always worth showing as tourist candidates.
CORE_CATEGORIES = {"Historical", "Nature", "Culture", "Adventure"}

# Categories only shown when the traveller asked for them.
EXTRA_CATEGORIES = {"Food", "Shopping"}

LODGING_TOURISM = {"hotel", "hostel", "guest_house", "motel", "apartment",
                   "alpine_hut", "camp_site", "caravan_site", "chalet", "motel"}

REJECT_AMENITY = {
    "school", "college", "university", "kindergarten", "hospital", "clinic",
    "doctors", "pharmacy", "fuel", "parking", "toilets", "waste_disposal",
    "recycling", "grave_yard", "fire_station", "police", "courthouse", "embassy",
    "laboratory", "veterinary", "childcare", "blood_donation", "shelter",
    "bench", "drinking_water", "weighbridge", "car_repair", "vehicle_inspection",
    "townhall", "post_office", "bank", "atm", "bureau_de_change", "market_cover",
    "prison", "jail",
}
REJECT_LANDUSE = {"cemetery", "industrial", "residential", "railway", "quarry",
                  "landfill", "brownfield", "military"}
REJECT_LEISURE = {"pitch", "track", "sports_centre", "stadium", "swimming_pool",
                  "fitness_centre", "dog_park", "golf_course"}
REJECT_TOURISM = LODGING_TOURISM | {"information", "hostel", "motel", "artwork_gallery"}

# Building uses that are never a visitor destination on their own. Ignored when
# the element also carries a real attraction tag (heritage station, museum…).
REJECT_BUILDING = {
    "office", "industrial", "hospital", "school", "university", "apartments",
    "residential", "house", "detached", "dormitory", "bungalow", "hut", "garage",
    "shed", "civic", "government", "fire_station", "train_station", "stadium",
    "hotel", "hostel", "warehouse", "farm", "cowshed", "greenhouse", "commercial",
}

# man_made / infrastructure tags that are only interesting with an attraction tag.
REJECT_MAN_MADE = {"power_tower", "pylon", "substation", "transformer",
                   "water_tower", "mast", "storage_tank", "pipe", "pipeline"}

# Never a tourist attraction, whatever it is tagged as.
REJECT_NAME_WORDS = (
    "school", "college", "university", "hospital", "clinic", "pharmacy",
    "cemetery", "graveyard", "crematorium", "embassy", "kindergarten",
    "daycare", "polytechnic", "institute of technology", "jail", "prison",
    "morgue", "fire station", "police station",
)

# historic=* values that are burial sites rather than sights.
REJECT_HISTORIC = {"grave", "graveyard", "cemetery"}

# Generic business names — rejected unless the place has a real popularity signal.
BUSINESS_NAME_WORDS = (
    "graphics", "consultancy", "consultant", "solutions", "enterprises",
    "traders", "trading", "printing", "photocopy", "hardware", "fashions",
    "textiles", "logistics", "distributors", "wholesale", "industries",
    "pvt ltd", "private limited", "dental",
)


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------
def geocode(query: str, near: Optional[str] = None) -> Optional[Dict[str, Any]]:
    queries = []
    if near:
        queries.append(f"{query}, {near}")
    queries.append(query)
    for q in queries:
        for _ in range(2):
            try:
                r = requests.get(
                    NOMINATIM,
                    params={"q": q, "format": "json", "limit": 1},
                    headers=HEADERS,
                    timeout=(4, 8),
                )
                r.raise_for_status()
                data = r.json()
                if data:
                    return {"name": data[0]["display_name"].split(",")[0],
                            "lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
                break  # empty result: try next query variant
            except Exception:
                continue
    return None


# ---------------------------------------------------------------------------
# Overpass
# ---------------------------------------------------------------------------
def _post_overpass(query: str):
    """Try mirrors once each (bounded time).

    Returns the parsed dict, RATE_LIMITED when every mirror said 429, or None.
    """
    saw_rate_limit = False
    deadline = time.time() + 45
    for url in OVERPASS_URLS:
        if time.time() > deadline:
            break
        try:
            r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=(6, 30))
            if r.status_code == 429:
                saw_rate_limit = True
                continue
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                saw_rate_limit = True
            continue
        except Exception:
            continue
    if saw_rate_limit:
        return RATE_LIMITED
    return None


# ---------------------------------------------------------------------------
# Relevance filtering & scoring
# ---------------------------------------------------------------------------
def _relevant(tags: Dict[str, str]) -> bool:
    """Drop schools, hospitals, cemeteries, offices and other non-attractions."""
    amenity = tags.get("amenity", "")
    if amenity in REJECT_AMENITY:
        return False
    if tags.get("landuse") in REJECT_LANDUSE:
        return False
    if tags.get("office") or tags.get("craft"):
        return False
    if tags.get("historic") in REJECT_HISTORIC:
        return False
    if tags.get("highway") in {"bus_stop", "motorway_junction", "rest_area"}:
        return False
    if tags.get("railway") in {"station", "halt", "tram_stop", "subway_entrance"} \
            and "tourism" not in tags and "historic" not in tags:
        return False
    if tags.get("public_transport") and not ({"tourism", "historic"} & set(tags)):
        return False
    if tags.get("tourism") in REJECT_TOURISM:
        return False
    if tags.get("leisure") in REJECT_LEISURE:
        return False

    # An explicit attraction signature overrides the generic building/infra
    # rejections (heritage railway station, museum in a civic building, …).
    has_attraction_signal = bool(
        tags.get("heritage") or tags.get("wikidata") or tags.get("wikipedia")
        or tags.get("tourism") in {"attraction", "museum", "gallery", "castle",
                                   "palace", "monument", "viewpoint", "artwork",
                                   "theme_park", "zoo", "aquarium"}
    )
    if not has_attraction_signal:
        if tags.get("building") in REJECT_BUILDING:
            return False
        if tags.get("man_made") in REJECT_MAN_MADE:
            return False
        if tags.get("government") or tags.get("amenity") == "townhall":
            return False
        # Any other plain building (office/residential block, shop unit…) is only
        # interesting when it hosts something visitable.
        visitable = amenity in {"restaurant", "cafe", "fast_food", "bar", "pub",
                                "theatre", "arts_centre", "museum",
                                "place_of_worship", "library"} \
            or tags.get("shop") in {"mall", "marketplace"} \
            or tags.get("leisure") in {"park", "nature_reserve", "garden"}
        if tags.get("building") and not visitable \
                and "tourism" not in tags and "historic" not in tags:
            return False

    if "tourism" in tags or "historic" in tags:
        return True
    if tags.get("leisure") in {"park", "nature_reserve", "garden", "common"}:
        return True
    if tags.get("natural") in {"peak", "waterfall", "volcano", "volcanic_caldera"}:
        return True
    # Lakes, reservoirs and other named water bodies make fine day-out spots.
    if tags.get("natural") == "water" and tags.get("water") in {"lake", "reservoir"}:
        return True
    if amenity in {"restaurant", "cafe", "fast_food", "bar", "pub",
                   "theatre", "arts_centre", "museum", "place_of_worship", "library"}:
        return True
    if tags.get("shop") in {"mall", "marketplace"}:
        return True
    if tags.get("sport"):
        return True
    return False


def _category_from_tags(tags: Dict[str, str]) -> str:
    if "historic" in tags:
        return "Historical"
    tourism = tags.get("tourism", "")
    if tourism in {"museum", "gallery", "artwork", "artwork_gallery"}:
        return "Culture"
    if tourism in {"theme_park", "zoo", "aquarium"}:
        return "Adventure"
    if tags.get("leisure") in {"park", "nature_reserve", "garden"} \
            or tourism == "viewpoint" or tags.get("natural") in {"peak", "waterfall", "volcano"} \
            or (tags.get("natural") == "water" and tags.get("water") in {"lake", "reservoir"}) \
            or (tags.get("water") in {"lake", "reservoir"} and "tourism" not in tags):
        return "Nature"
    a = tags.get("amenity", "")
    if a in ("restaurant", "cafe", "fast_food", "bar", "pub"):
        return "Food"
    if a in ("arts_centre", "theatre", "museum", "place_of_worship"):
        return "Culture"
    if tags.get("shop") in ("mall", "marketplace"):
        return "Shopping"
    if tags.get("sport"):
        return "Adventure"
    if tourism in ("attraction", "castle", "palace", "monument"):
        return "Historical"
    return "Culture"


def _tourist_score(tags: Dict[str, str], interest_match: bool) -> int:
    """Popularity / tourist relevance, from real OSM signals only."""
    s = 10
    tourism = tags.get("tourism", "")
    if tourism in {"attraction", "museum", "castle", "palace", "monument",
                   "artwork", "viewpoint", "theme_park", "zoo", "aquarium", "gallery"}:
        s += 60
    if "historic" in tags:
        s += 45
    if tags.get("heritage") or tags.get("UNESCO"):
        s += 45
    if tags.get("wikidata") or tags.get("wikipedia"):
        s += 35          # a Wikipedia article is a strong popularity signal
    if tags.get("name:en"):
        s += 12          # internationally known enough to be tagged in English
    if tags.get("leisure") in {"park", "nature_reserve", "garden"}:
        s += 25
    if tags.get("operator:wikidata") or tags.get("subject:wikidata"):
        s += 15
    if tags.get("fee") == "yes" or tags.get("charge"):
        s += 5           # charges money ⇒ somebody maintains it as an attraction
    if interest_match:
        s += 50
    return s


# ---------------------------------------------------------------------------
# Costs
# ---------------------------------------------------------------------------
PRICE_SYMBOL = re.compile(r"(\d+(?:\.\d+))?\s*(₹|Rs\.?|INR)", re.IGNORECASE)


def _entry_cost(tags: Dict[str, str], category: str) -> Tuple[int, str]:
    """Returns (amount, label) — label is Verified / Estimated / Unavailable."""
    charge = tags.get("charge") or tags.get("fee:amount") or ""
    m = PRICE_SYMBOL.search(charge)
    if m and m.group(1):
        return int(float(m.group(1))), "Verified"
    fee = tags.get("fee", "")
    if fee in {"no", "free"}:
        return 0, "Verified"
    if charge:  # a charge exists but in an unknown currency — don't mislabel
        return _estimate_entry(category), "Estimated"
    if fee == "yes":
        return _estimate_entry(category), "Estimated"
    if category in {"Nature"} and "historic" not in tags:
        return 0, "Unavailable"
    return _estimate_entry(category), "Estimated"


def _estimate_entry(category: str) -> int:
    return {"Historical": 150, "Culture": 100, "Adventure": 800,
            "Shopping": 0, "Nature": 0, "Food": 0}.get(category, 100)


def _food_cost(tags: Dict[str, str], category: str) -> Tuple[int, str]:
    if category != "Food":
        return 0, "Unavailable"
    charge = tags.get("charge") or ""
    m = PRICE_SYMBOL.search(charge)
    if m and m.group(1):
        return int(float(m.group(1))), "Verified"
    if tags.get("fee") in {"no", "free"}:
        return 0, "Verified"
    a = tags.get("amenity", "")
    per_head = {"cafe": 250, "fast_food": 200, "bar": 400, "pub": 400,
                "restaurant": 500}.get(a, 450)
    return per_head, "Estimated"


def _visit_defaults(tags: Dict[str, str], category: str) -> int:
    if "historic" in tags:
        return 90
    a = tags.get("amenity", "")
    if a == "restaurant": return 60
    if a == "cafe": return 45
    if a == "fast_food": return 30
    if a in ("bar", "pub"): return 60
    if a == "museum" or tags.get("tourism") == "museum": return 120
    if a == "arts_centre": return 60
    if a == "theatre": return 120
    if a == "place_of_worship": return 45
    if tags.get("leisure") in ("park", "nature_reserve", "garden"): return 60
    if tags.get("tourism") == "viewpoint": return 30
    if tags.get("shop") == "mall": return 90
    if a == "marketplace": return 60
    if tags.get("tourism") == "theme_park": return 180
    return 60


def _describe(tags: Dict[str, str], category: str, destination: str) -> str:
    """Build a factual description from OpenStreetMap tags only — never invented."""
    if tags.get("description"):
        return tags["description"]
    parts = []
    hist = tags.get("historic")
    if hist:
        parts.append(f"OSM-listed historic site ({hist})")
    tourism = tags.get("tourism")
    if tourism:
        parts.append(f"{tourism.replace('_', ' ')} listed on OpenStreetMap")
    amenity = tags.get("amenity")
    cuisine = tags.get("cuisine")
    if amenity in ("restaurant", "cafe", "fast_food", "bar", "pub"):
        parts.append(f"{amenity}" + (f" serving {cuisine.replace(';', ', ')}" if cuisine else ""))
    if tags.get("leisure") in ("park", "nature_reserve", "garden"):
        parts.append("public park")
    if tags.get("shop") == "mall":
        parts.append("shopping mall")
    if amenity == "place_of_worship":
        rel = tags.get("religion", "")
        parts.append(f"{rel + ' ' if rel else ''}place of worship")
    if tags.get("wikidata"):
        parts.append("place with a Wikipedia article")
    if not parts:
        parts.append(f"{category.lower()} place")
    return f"{parts[0].capitalize()} in {destination}, from OpenStreetMap."


# ---------------------------------------------------------------------------
# Candidate discovery
# ---------------------------------------------------------------------------
def fetch_candidates(destination: str, interests: List[str],
                     max_results: int = 40) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Optional[str]]:
    """Returns (destination_info, candidates, error_message)."""
    dest = geocode(destination)
    if not dest:
        return {}, [], f"Could not find the destination \"{destination}\"."

    selected_interests = {i for i in interests if i in INTEREST_QUERIES}
    # Only fetch the bulky extra categories the traveller actually asked for.
    wanted_extras = sorted(i for i in FOOD_INTERESTS | {"Shopping"} if i in selected_interests)
    # One combined query per destination (cached) keeps Overpass happy.
    cache_key = (round(dest["lat"], 3), round(dest["lng"], 3), tuple(wanted_extras))
    cached = _CACHE.get(cache_key)
    if cached is None or time.time() - cached["time"] > 600:
        parts = []
        for interest, qs in INTEREST_QUERIES.items():
            if interest in FOOD_INTERESTS and interest not in selected_interests:
                continue
            if interest == "Shopping" and interest not in selected_interests:
                continue
            radius = FOOD_RADIUS if interest in FOOD_INTERESTS else ATTRACTION_RADIUS
            for q in qs:
                parts.append(f'{q}(around:{radius},{dest["lat"]},{dest["lng"]});')
        # Large cap: dense cities overflow small limits and drop the famous
        # landmarks (Charminar, museums…) out of the response entirely.
        query = f"[out:json][timeout:35];({''.join(parts)});out center tags 3000;"
        elements: List[Dict[str, Any]] = []
        rate_limited = False
        service_down = True
        started = time.time()
        for attempt in range(5):
            if time.time() - started > 60:  # keep total wait bounded
                break
            data = _post_overpass(query)
            if data is RATE_LIMITED:
                rate_limited = True
                service_down = False
                time.sleep(min(4 * (attempt + 1), 12))  # back off and retry
                continue
            if data is not None:
                service_down = False
                if data.get("elements"):
                    elements = data["elements"]
                    break
                remark = str(data.get("remark", ""))
                if any(w in remark.lower() for w in ("rate", "timeout", "too many")):
                    rate_limited = True
                    time.sleep(min(4 * (attempt + 1), 12))
                    continue
                # got JSON but no elements and no rate-limit remark → likely empty area
                break
            # mirror timeouts/errors: brief pause then try all mirrors again
            time.sleep(min(3 * (attempt + 1), 9))
        if not elements:
            if service_down:
                return dest, [], "Location service (OpenStreetMap Overpass) is temporarily busy. Please try again in a moment."
            if rate_limited:
                return dest, [], "OpenStreetMap is rate-limiting requests right now. Please wait a few seconds and try again."
            return dest, [], f"No named places found for \"{destination}\" matching your interests."
        _CACHE[cache_key] = {"time": time.time(), "elements": elements}
        # expire other entries
        for k in [k for k, v in _CACHE.items() if time.time() - v["time"] > 600]:
            _CACHE.pop(k, None)
    else:
        cached["time"] = time.time()
        elements = cached["elements"]

    seen = set()
    all_cands: List[Dict[str, Any]] = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name or name in seen:
            continue
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lng = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lng is None:
            continue
        if not _relevant(tags):
            continue
        low = name.lower()
        if any(w in low for w in REJECT_NAME_WORDS):
            continue  # schools / hospitals / cemeteries etc. even if mis-tagged
        popular = bool(tags.get("wikidata") or tags.get("wikipedia")
                       or tags.get("heritage") or tags.get("UNESCO")
                       or tags.get("tourism") in {"museum", "attraction", "castle",
                                                  "palace", "gallery", "theme_park",
                                                  "zoo", "aquarium"})
        if not popular and any(w in low for w in BUSINESS_NAME_WORDS):
            continue  # irrelevant businesses (offices/shops mis-tagged as POIs)
        seen.add(name)
        category = _category_from_tags(tags)
        interest_match = category in selected_interests
        entry_cost, entry_label = _entry_cost(tags, category)
        food_cost, food_label = _food_cost(tags, category)
        score = _tourist_score(tags, interest_match)
        all_cands.append({
            "name": name,
            "name_en": tags.get("name:en") or "",
            "category": category,
            "lat": lat,
            "lng": lng,
            "duration_minutes": _visit_defaults(tags, category),
            "entry_cost": entry_cost,
            "entry_price_label": entry_label,
            "food_cost": food_cost,
            "food_price_label": food_label,
            "cost": entry_cost + food_cost + 50,  # + local transport reserve (DP input)
            "value": max(1, score),
            "tourist_score": score,
            "interest_match": interest_match,
            "photo_url": None,
            "description": _describe(tags, category, destination),
        })

    if not all_cands:
        return dest, [], f"No named places found for \"{destination}\" matching your interests."

    # Interests + tourist relevance shape the pool: core attractions always,
    # Food/Shopping only when selected; then rank by interest then popularity.
    primary = [c for c in all_cands
               if c["category"] in CORE_CATEGORIES or c["interest_match"]]
    if len(primary) < 15:  # thin city: fall back to every relevant place
        primary = all_cands
    primary.sort(key=lambda c: (not c["interest_match"], -c["tourist_score"], c["name"]))

    candidates: List[Dict[str, Any]] = []
    per_cat: Dict[str, int] = {}
    cap_per_cat = max(8, max_results // 4)
    for c in primary:
        if len(candidates) >= max_results:
            break
        if per_cat.get(c["category"], 0) >= cap_per_cat:
            continue
        per_cat[c["category"]] = per_cat.get(c["category"], 0) + 1
        candidates.append(c)
    for c in primary:  # top up if a category cap left free slots
        if len(candidates) >= max_results:
            break
        if c not in candidates:
            candidates.append(c)
    return dest, candidates, None


# ---------------------------------------------------------------------------
# Photos (Google Places → Wikimedia Commons → None)
# ---------------------------------------------------------------------------
_STOPWORDS = {"the", "of", "and", "in", "at", "a", "an", "de", "la", "le", "el", "der", "die", "das"}


def _name_tokens(name: str) -> set:
    return {t for t in re.split(r"[^0-9A-Za-z]+", name.lower())
            if len(t) > 2 and t not in _STOPWORDS}


def _is_non_latin(text: str) -> bool:
    """True when the name has no Latin-script tokens (e.g. Japanese, Chinese, Arabic)."""
    return not bool(_name_tokens(text)) and bool(text.strip())


def _http_get_json(url: str, params: Dict[str, Any], tries: int = 2) -> Optional[Dict[str, Any]]:
    """GET a JSON endpoint, retrying 429/403 once with a short backoff."""
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=(4, 10))
            if r.status_code in (429, 403):
                time.sleep(1.2 * (i + 1))
                continue
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            time.sleep(0.5)
    return None


def _url_reachable(url: str) -> bool:
    """Confirm the image URL actually serves an image (catch broken/404 links)."""
    try:
        r = requests.head(url, headers=HEADERS, timeout=(3, 8), allow_redirects=True)
        if r.status_code in (403, 405):   # some CDNs reject HEAD — try a tiny GET
            r = requests.get(url, headers=HEADERS, timeout=(3, 10),
                             stream=True, allow_redirects=True)
            r.close()
        ctype = (r.headers.get("Content-Type") or "").lower()
        return r.status_code == 200 and (ctype.startswith("image/") or ctype == "")
    except Exception:
        return False


def _name_matches(candidate: str, names: List[str]) -> bool:
    """True when a candidate label (page title / display name) matches the place."""
    cand_tokens = _name_tokens(candidate.rsplit(".", 1)[0])
    if not cand_tokens:
        return False
    for n in names:
        want = _name_tokens(n)
        if not want:
            if _is_non_latin(n) and n.strip().lower() in candidate.lower():
                return True
            continue
        covered = len(want & cand_tokens) / len(want)
        if covered >= 0.6:
            return True
        # non-Latin source name may appear verbatim in the candidate
        if _is_non_latin(n) and n.strip() and n.strip().lower() in candidate.lower():
            return True
    return False


def _google_places_photo(name: str, city: str, name_en: str = "") -> Optional[str]:
    """Source 1: Google Places photo (only when GOOGLE_PLACES_API_KEY is set)."""
    if not GOOGLE_PLACES_KEY:
        return None
    query_name = name_en or name
    try:
        r = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={
                "X-Goog-Api-Key": GOOGLE_PLACES_KEY,
                "X-Goog-FieldMask": "places.displayName,places.photos",
                "Content-Type": "application/json",
            },
            json={"textQuery": f"{query_name}, {city}", "languageCode": "en"},
            timeout=(5, 12),
        )
        if r.status_code != 200:
            return None
        places = r.json().get("places") or []
        if not places:
            return None
        # confirm the returned display name matches what we asked for
        disp = (places[0].get("displayName") or {}).get("text", "")
        if not _name_matches(disp, [n for n in (name, name_en) if n]):
            return None
        photos = places[0].get("photos") or []
        if not photos:
            return None
        photo_name = photos[0].get("name")
        if not photo_name:
            return None
        url = (f"https://places.googleapis.com/v1/{photo_name}/media"
               f"?maxWidthPx=240&key={GOOGLE_PLACES_KEY}")
        return url if _url_reachable(url) else None
    except Exception:
        return None


def _wikimedia_candidates(query: str) -> List[str]:
    """File titles from a Commons full-text search."""
    data = _http_get_json(COMMONS_API, {
        "action": "query", "format": "json", "list": "search",
        "srsearch": query, "srnamespace": 6, "srlimit": 12,
    })
    if not data:
        return []
    return [s["title"] for s in data.get("query", {}).get("search", [])
            if re.search(r"\.(jpg|jpeg|png|webp)$", s["title"], re.IGNORECASE)]


def _wikimedia_thumb(titles: List[str]) -> Dict[str, str]:
    """title → 240px thumbnail URL for the given Commons file titles."""
    if not titles:
        return {}
    out: Dict[str, str] = {}
    for i in range(0, len(titles), 6):          # keep request sizes modest
        chunk = titles[i:i + 6]
        data = _http_get_json(COMMONS_API, {
            "action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "url", "iiurlwidth": 240, "titles": "|".join(chunk),
        })
        if not data:
            continue
        for page in data.get("query", {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            thumb = info.get("thumburl") or info.get("url")
            if thumb:
                out[page.get("title", "")] = thumb.split("?")[0]
    return out


def _pick_best(names: List[str], thumbs: Dict[str, str]) -> Optional[str]:
    """Tightest title match among the candidate thumbnails — never an unrelated one."""
    best: Optional[Tuple[int, str]] = None
    for title, thumb in thumbs.items():
        if not _name_matches(title, names):
            continue
        title_tokens = _name_tokens(title.rsplit(".", 1)[0])
        extras = min(
            (len(title_tokens - _name_tokens(n)) for n in names
             if _name_tokens(n) and len(_name_tokens(n) & title_tokens) / len(_name_tokens(n)) >= 1.0),
            default=len(title_tokens) + 5,
        )
        if best is None or extras < best[0]:
            best = (extras, thumb)
    return best[1] if best else None


def _wikimedia_photo(name: str, city: str, name_en: str = "",
                     deadline: Optional[float] = None) -> Optional[str]:
    """Source 2: Wikimedia Commons — filename must match the place name."""
    names = [n for n in dict.fromkeys([name_en, name]) if n]
    queries = []
    for n in names:
        queries.append(f"{n} {city}")
    for n in names:
        queries.append(n)
    for n in names:                              # title-scoped search finds exact files
        queries.append(f'intitle:"{n}"')

    seen_titles: List[str] = []
    for q in queries:
        if deadline and time.time() > deadline:
            break
        titles = [t for t in _wikimedia_candidates(q) if t not in seen_titles]
        seen_titles.extend(titles)
        if not titles:
            continue
        url = _pick_best(names, _wikimedia_thumb(titles))
        if url:
            return url
        time.sleep(0.15)  # be polite to Commons
    return None


def _wikipedia_photo(name: str, city: str, name_en: str = "",
                     deadline: Optional[float] = None) -> Optional[str]:
    """Source 3: lead image of the place's own Wikipedia article.

    The article must resolve to a title matching the place name, so the lead
    image is by definition a picture of this exact place.
    """
    names = [n for n in dict.fromkeys([name_en, name]) if n]
    for n in names:
        if deadline and time.time() > deadline:
            return None
        data = _http_get_json("https://en.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "prop": "pageimages",
            "piprop": "thumbnail", "pithumbsize": 240, "redirects": 1,
            "titles": n,
        })
        if not data:
            continue
        for page in data.get("query", {}).get("pages", {}).values():
            title = page.get("title", "")
            thumb = (page.get("thumbnail") or {}).get("source")
            if not thumb or title.startswith("List of"):
                continue
            if _name_matches(title, names):
                return thumb.split("?")[0]
    # Last resort: "<place> <city>" article search, title-verified.
    for n in names:
        if deadline and time.time() > deadline:
            return None
        data = _http_get_json("https://en.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "list": "search",
            "srsearch": f"{n} {city}", "srlimit": 5,
        })
        if not data:
            continue
        hits = [s["title"] for s in data.get("query", {}).get("search", [])
                if _name_matches(s["title"], names)]
        if not hits:
            continue
        data2 = _http_get_json("https://en.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "prop": "pageimages",
            "piprop": "thumbnail", "pithumbsize": 240, "redirects": 1,
            "titles": "|".join(hits[:3]),
        })
        if not data2:
            continue
        for page in data2.get("query", {}).get("pages", {}).values():
            thumb = (page.get("thumbnail") or {}).get("source")
            if thumb and _name_matches(page.get("title", ""), names):
                return thumb.split("?")[0]
    return None


def photo_for(name: str, city: str, name_en: str = "") -> Optional[str]:
    """Resolve a verified photo: Google Places → Wikimedia Commons → Wikipedia.

    Every candidate URL must match the place name and be probed for
    reachability; if nothing reliable exists we return None (neutral fallback).
    Misses are cached briefly so a transient rate-limit can recover quickly.
    """
    key = f"{name}|{name_en}|{city}"
    hit = _PHOTO_CACHE.get(key)
    if hit:
        url, ts = hit
        # hits are worth keeping; misses only for a minute (rate-limit recovery)
        if url or time.time() - ts < 60:
            return url

    deadline = time.time() + 20          # never block a plan response for long
    url = None
    for attempt in range(2):
        url = _google_places_photo(name, city, name_en)
        if not url:
            # Keep a slice of the budget for the Wikipedia fallback.
            wm_deadline = max(time.time() + 5, deadline - 8)
            url = _wikimedia_photo(name, city, name_en, wm_deadline)
            if url and not _url_reachable(url):
                url = None
        if not url:
            url = _wikipedia_photo(name, city, name_en, deadline)
            if url and not _url_reachable(url):
                url = None
        if url or time.time() >= deadline:
            break
        time.sleep(2.0)                   # one retry — Commons throttles bursts
    _PHOTO_CACHE[key] = (url, time.time())
    return url


def attach_photos(places: List[Dict[str, Any]], destination: str) -> None:
    """Attach a verified photo URL to each place (None when nothing reliable)."""
    from concurrent.futures import ThreadPoolExecutor

    todo = [p for p in places if not p.get("photo_url")]
    if not todo:
        return

    def resolve(p: Dict[str, Any]) -> None:
        try:
            p["photo_url"] = photo_for(p["name"], destination, p.get("name_en") or "")
        except Exception:
            p["photo_url"] = None

    with ThreadPoolExecutor(max_workers=3) as pool:   # Commons rate-limits bursts
        list(pool.map(resolve, todo))
