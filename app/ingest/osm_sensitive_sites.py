import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

from app.db import get_connection

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "WardSentry-hackathon-prototype/0.1 (civic complaint triage, local dev)"
DEFAULT_CACHE_PATH = "data/cache/osm_sensitive_sites.json"
DEDUPE_RADIUS_M = 30

# ARCHITECTURE.md 3: schools, hospitals, markets, water bodies, bus stops.
_CATEGORY_FILTERS = {
    "school": [('amenity', 'school')],
    "hospital": [('amenity', 'hospital')],
    "market": [('amenity', 'marketplace')],
    "water_body": [('natural', 'water')],
    "bus_stop": [('highway', 'bus_stop')],
}


def _build_category_query(category: str, bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"
    lines = ["[out:json][timeout:90];", "("]
    for key, value in _CATEGORY_FILTERS[category]:
        lines.append(f'  node["{key}"="{value}"]({bbox_str});')
        lines.append(f'  way["{key}"="{value}"]({bbox_str});')
    lines.append(");")
    lines.append("out center;")
    return "\n".join(lines)


def _fetch_category_elements(category: str, bbox: tuple[float, float, float, float]) -> list[dict]:
    query = _build_category_query(category, bbox)
    data = urllib.parse.urlencode({"data": query}).encode()
    request = urllib.request.Request(OVERPASS_URL, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read())["elements"]


def _classify_osm_tags(tags: dict) -> str | None:
    for category, filters in _CATEGORY_FILTERS.items():
        for key, value in filters:
            if tags.get(key) == value:
                return category
    return None


def _element_point(element: dict) -> tuple[float, float] | tuple[None, None]:
    if element.get("type") == "node":
        return element.get("lat"), element.get("lon")
    center = element.get("center")
    if center:
        return center.get("lat"), center.get("lon")
    return None, None


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_osm_elements(
    bbox: tuple[float, float, float, float],
    cache_path: str = DEFAULT_CACHE_PATH,
    force_refresh: bool = False,
) -> list[dict]:
    """Queries Overpass for the 5 sensitive-site categories within bbox, one
    smaller request per category rather than one combined query - the
    combined query 504'd against the shared public instance, while a single
    category resolved in ~2.5s. Caches the merged raw response so repeated
    runs and offline dev don't need network access.

    Partial failure is real and handled per-category: if some categories
    fail and others succeed, the successful ones are still cached and
    returned - callers can see which categories are missing/incomplete
    rather than losing everything to one bad request. Only when EVERY
    category fails does this fall back to a stale cache, or finally an
    empty list (never fabricates a substitute).
    """
    cache_file = Path(cache_path)
    if not force_refresh and cache_file.exists():
        return json.loads(cache_file.read_text())["elements"]

    seen_keys = set()
    all_elements = []
    failed_categories = []
    for i, category in enumerate(_CATEGORY_FILTERS):
        if i > 0:
            time.sleep(1)  # courtesy pause between requests to the shared public instance
        try:
            elements = _fetch_category_elements(category, bbox)
        except Exception as e:
            print(f"Overpass request for category '{category}' failed: {e}")
            failed_categories.append(category)
            continue
        for element in elements:
            key = (element.get("type"), element.get("id"))
            if key not in seen_keys:
                seen_keys.add(key)
                all_elements.append(element)

    if len(failed_categories) == len(_CATEGORY_FILTERS):
        if cache_file.exists():
            print(f"All Overpass requests failed; falling back to cached data at {cache_path}")
            return json.loads(cache_file.read_text())["elements"]
        print(f"All Overpass requests failed and no cache exists at {cache_path}; loading zero sites")
        return []

    if failed_categories:
        print(f"Overpass requests failed for categories {failed_categories} - results incomplete for those")

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"elements": all_elements, "failed_categories": failed_categories}))
    return all_elements


def normalize_elements(elements: list[dict]) -> list[dict]:
    sites = []
    for element in elements:
        category = _classify_osm_tags(element.get("tags", {}))
        if category is None:
            continue
        lat, lon = _element_point(element)
        if lat is None or lon is None:
            continue
        sites.append({
            "source_id": f"{element['type']}/{element['id']}",
            "category": category,
            "name": element.get("tags", {}).get("name"),
            "lat": lat,
            "lon": lon,
        })
    return sites


def deduplicate_sites(sites: list[dict], radius_m: float = DEDUPE_RADIUS_M) -> list[dict]:
    """Collapses near-duplicate OSM objects (e.g. a school mapped as both a
    node and a building outline) of the SAME category within radius_m of
    each other into one representative site. Different categories at the
    same point, and same-category sites further apart, are never merged.
    """
    by_category: dict[str, list[dict]] = {}
    for site in sites:
        by_category.setdefault(site["category"], []).append(site)

    deduped = []
    for group in by_category.values():
        kept: list[dict] = []
        for site in group:
            match = next(
                (k for k in kept if _haversine_m(site["lat"], site["lon"], k["lat"], k["lon"]) <= radius_m),
                None,
            )
            if match is None:
                kept.append(dict(site))
            elif not match.get("name") and site.get("name"):
                match["name"] = site["name"]
        deduped.extend(kept)
    return deduped


def _fetch_ward_bbox(conn) -> tuple[float, float, float, float]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ST_YMin(ST_Extent(geom)), ST_XMin(ST_Extent(geom)), "
            "ST_YMax(ST_Extent(geom)), ST_XMax(ST_Extent(geom)) FROM wards"
        )
        return cur.fetchone()


def load_sensitive_sites(
    bbox: tuple[float, float, float, float] | None = None,
    conn=None,
    cache_path: str = DEFAULT_CACHE_PATH,
    force_refresh: bool = False,
) -> int:
    """Loads OSM sensitive sites for the exposure calc. Scope is enforced by
    ward containment, not the query bbox: the bbox is only a superset net
    (Overpass has no simple way to filter by 58 real ward polygons at once),
    and every candidate is checked against the actual PMC ward polygons
    afterward - a site outside all 58 wards is discarded, never silently
    kept under a broader "Pune district" scope.
    """
    owns_conn = conn is None
    conn = conn or get_connection()
    try:
        if bbox is None:
            bbox = _fetch_ward_bbox(conn)

        elements = fetch_osm_elements(bbox, cache_path=cache_path, force_refresh=force_refresh)
        return insert_sites_in_wards(deduplicate_sites(normalize_elements(elements)), conn)
    finally:
        if owns_conn:
            conn.close()


def insert_sites_in_wards(sites: list[dict], conn=None) -> int:
    """Upserts sites (keyed by source_id) that fall inside a PMC ward polygon;
    a site outside all 58 wards is out of scope and discarded. Shared by
    every sensitive-site source (OSM, PMC bus stops).
    """
    owns_conn = conn is None
    conn = conn or get_connection()
    try:
        inserted = 0
        with conn.cursor() as cur:
            for site in sites:
                cur.execute(
                    "SELECT 1 FROM wards WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
                    (site["lon"], site["lat"]),
                )
                if cur.fetchone() is None:
                    continue  # outside all PMC wards - out of scope, discard

                cur.execute(
                    """
                    INSERT INTO sensitive_sites (name, kind, geom, source_id)
                    VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
                    ON CONFLICT (source_id) DO UPDATE SET
                        name = EXCLUDED.name, kind = EXCLUDED.kind, geom = EXCLUDED.geom
                    """,
                    (site.get("name"), site["category"], site["lon"], site["lat"], site["source_id"]),
                )
                inserted += 1
        conn.commit()
        return inserted
    finally:
        if owns_conn:
            conn.close()
