"""Pune gazetteer from OpenStreetMap -> data/gazetteer/pune_gazetteer_osm.csv.

Place names (suburbs, neighbourhoods, localities, villages, named junctions,
named major roads) with a point and, for areal places, the PMC 2022 ward the
point falls in. Marathi/Hindi names come from OSM's name:mr / name:hi tags.

Honesty rules:
- One row per lowercased name. A name found at points more than
  AMBIGUOUS_KM apart is kept but marked kind=ambiguous, and must not be
  used to place anything.
- Roads span many wards, so a road's point is the median of its segment
  centres and its ward is left empty.
- Coordinates are OSM's, not verified on the ground.

Run: python -m scripts.build_gazetteer   (Overpass response cached in data/cache/)
"""
import csv
import json
import math
import statistics
import urllib.parse
import urllib.request
from pathlib import Path

from app.db import get_connection

BBOX = "18.40,73.72,18.65,74.02"  # covers PMC plus fringe; ward join decides "in PMC"
CACHE = Path("data/cache/overpass_gazetteer.json")
OUTPUT = Path("data/gazetteer/pune_gazetteer_osm.csv")
AMBIGUOUS_KM = 1.5
COLUMNS = ["name_en", "name_marathi", "name_hindi", "romanized_variants", "kind",
           "lat", "lon", "ward_2022_id", "ward_2022_name", "coord_source", "notes"]
# Higher rank wins when one name is tagged as several kinds at the same spot.
KIND_RANK = {"suburb": 6, "quarter": 5, "neighbourhood": 4, "locality": 3,
             "village": 2, "hamlet": 2, "junction": 1, "road": 0}

QUERY = f"""[out:json][timeout:120];(
node["place"~"^(suburb|neighbourhood|quarter|locality|village|hamlet)$"]["name"]({BBOX});
way["place"~"^(suburb|neighbourhood|quarter)$"]["name"]({BBOX});
relation["place"~"^(suburb|neighbourhood|quarter)$"]["name"]({BBOX});
relation["boundary"~"^(local_authority|administrative)$"]["admin_level"!~"^[1-8]$"]["name"]({BBOX});
way["highway"~"^(primary|secondary|tertiary|trunk)$"]["name"]({BBOX});
node["junction"]["name"]({BBOX}););out center tags;"""


def fetch_elements() -> list[dict]:
    if not CACHE.exists():
        request = urllib.request.Request(
            "https://overpass-api.de/api/interpreter",
            data=urllib.parse.urlencode({"data": QUERY}).encode(),
            headers={"User-Agent": "WardSentry-hackathon-prototype/0.1"},
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            CACHE.write_bytes(response.read())
    return json.loads(CACHE.read_text())["elements"]


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _kind(tags: dict) -> str:
    if "highway" in tags:
        return "road"
    if "boundary" in tags:
        return "locality"
    return tags.get("place") or "junction"


def build_rows(elements: list[dict]) -> list[dict]:
    """Groups OSM elements by lowercased name into one gazetteer row each."""
    groups: dict[str, list[dict]] = {}
    for el in elements:
        name = el["tags"]["name"].strip()
        point = (el["lat"], el["lon"]) if "lat" in el else (el["center"]["lat"], el["center"]["lon"])
        groups.setdefault(name.lower(), []).append({"name": name, "tags": el["tags"],
                                                    "kind": _kind(el["tags"]), "point": point,
                                                    "osm": f"{el['type']}/{el['id']}"})
    rows = []
    for items in groups.values():
        best = max(items, key=lambda i: KIND_RANK[i["kind"]])
        if best["kind"] == "road":
            roads = [i["point"] for i in items if i["kind"] == "road"]
            point = (statistics.median(p[0] for p in roads), statistics.median(p[1] for p in roads))
            kind, notes = "road", f"{len(roads)} OSM segments; point is median of segment centres"
        else:
            point, kind, notes = best["point"], best["kind"], best["osm"]
            areal = [i["point"] for i in items if i["kind"] != "road"]
            spread = max(_km(point, p) for p in areal)
            if spread > AMBIGUOUS_KM:
                kind, notes = "ambiguous", f"same name at points {spread:.1f} km apart; do not use to locate"
        tags = best["tags"]
        rows.append({"name_en": tags.get("name:en") or best["name"],
                     "name_marathi": tags.get("name:mr", ""), "name_hindi": tags.get("name:hi", ""),
                     "romanized_variants": best["name"] if tags.get("name:en") else "",
                     "kind": kind, "lat": round(point[0], 6), "lon": round(point[1], 6),
                     "coord_source": "osm_overpass", "notes": notes})
    return rows


def attach_wards(rows: list[dict]) -> None:
    """Areal places and junctions get the PMC 2022 ward their point is in."""
    with get_connection() as conn, conn.cursor() as cur:
        for row in rows:
            row["ward_2022_id"] = row["ward_2022_name"] = ""
            if row["kind"] in ("road", "ambiguous"):
                continue
            cur.execute("SELECT id, name FROM wards WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
                        (row["lon"], row["lat"]))
            hit = cur.fetchone()
            if hit:
                row["ward_2022_id"], row["ward_2022_name"] = hit


def main() -> None:
    rows = build_rows(fetch_elements())
    attach_wards(rows)
    rows.sort(key=lambda r: (-KIND_RANK.get(r["kind"], -1), r["name_en"].lower()))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    kinds: dict[str, int] = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    in_pmc = sum(1 for r in rows if r["ward_2022_id"])
    print(f"{len(rows)} names -> {OUTPUT}  kinds={kinds}  inside a PMC ward={in_pmc}  "
          f"with Marathi={sum(1 for r in rows if r['name_marathi'])}")


if __name__ == "__main__":
    main()
