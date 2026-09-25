"""PMC-published hospitals and schools (L08 open-data bundle) -> sensitive_sites.

Distinct from OSM (app/ingest/osm_sensitive_sites.py), not a duplicate of it:
OSM's "hospital" points here are crowd-sourced (sampled names include things
like "SKINN AND HAIR CLINIC"); these are PMC's own published facility
register, split by Government/Private. Only categories that map onto an
EXISTING weighted `kind` in app/core/priority.py's SITE_WEIGHTS are loaded -
private clinics and dispensaries are real L08 sheets but have no weight of
their own, and giving them hospital-tier weight would misrepresent them, so
they're left out rather than guessed at (priority.py's weights are a
hard-rule constant, not something an ingest script should quietly nudge).
The larger "List of Schools in the PMC Area" sheet has no coordinates (only
phone/UDISE/email) and would need new geocoding to use - out of scope, see
data/eval/README.md's "no new lookups" rule.

Source: PMC's L08 open-data bundle (not redistributed by PMC as a stable
API - a snapshot audited into this repo). Duplicates across sources (e.g. a
hospital both OSM and L08 know about) are harmless: app/core/priority.py's
exposure term takes the max site weight in range, never a count.

Run: python -m app.ingest.l08_sensitive_sites
"""
import csv
import re

from app.db import get_connection
from app.ingest.osm_sensitive_sites import deduplicate_sites, insert_sites_in_wards

HOSPITAL_FILES = {
    "l08_gov_hospital": "data/l08/government_hospitals.csv",
    "l08_private_hospital": "data/l08/private_hospitals.csv",
}
SCHOOL_FILE = "data/l08/pmc_schools.csv"
_LOCATION_RE = re.compile(r"\(?\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\)?")


def _read_csv(path: str) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.reader(f))


def parse_hospital_rows(rows: list[list[str]], source_prefix: str) -> list[dict]:
    """Government/Private Hospitals sheets: City Name, Ward No, Ward Name,
    Name of healthcare facility, Type of facility, Latitude, Longitude."""
    header = [h.strip() for h in rows[0]]
    name_col = header.index("Name of healthcare facility")
    lat_col, lon_col = header.index("Latitude"), header.index("Longitude")
    sites = []
    for i, row in enumerate(rows[1:]):
        try:
            lat, lon = float(row[lat_col]), float(row[lon_col])
        except (ValueError, IndexError):
            continue
        sites.append({
            "source_id": f"{source_prefix}:{i}",
            "category": "hospital",
            "name": row[name_col].strip() or None,
            "lat": lat,
            "lon": lon,
        })
    return sites


def parse_school_rows(rows: list[list[str]]) -> list[dict]:
    """PMC Schools sheet: Sr No, Facility Type/Category, Name of Facility,
    Address, "Location(lat,long)" (one combined "(lat, lon)" column),
    Prabhag Name, Ward Name. Ends with ragged footer/note rows - skipped by
    requiring both a numeric Sr No and a parseable location."""
    header = [h.strip() for h in rows[0]]
    sr_col = header.index("Sr No")
    name_col = header.index("Name of Facility")
    loc_col = header.index("Location(lat,long)")
    sites = []
    for row in rows[1:]:
        if len(row) <= max(sr_col, name_col, loc_col) or not row[sr_col].strip().isdigit():
            continue
        match = _LOCATION_RE.search(row[loc_col])
        if match is None:
            continue
        sites.append({
            "source_id": f"l08_pmc_school:{row[sr_col].strip()}",
            "category": "school",
            "name": row[name_col].strip() or None,
            "lat": float(match.group(1)),
            "lon": float(match.group(2)),
        })
    return sites


def load_l08_sensitive_sites(conn=None) -> int:
    sites = []
    for prefix, path in HOSPITAL_FILES.items():
        sites += parse_hospital_rows(_read_csv(path), source_prefix=prefix)
    sites += parse_school_rows(_read_csv(SCHOOL_FILE))

    deduped = deduplicate_sites(sites)
    owns_conn = conn is None
    conn = conn or get_connection()
    try:
        inserted = insert_sites_in_wards(deduped, conn)
        if owns_conn:
            conn.commit()
        print(f"{len(sites)} L08 facility rows -> {len(deduped)} deduped -> {inserted} inside PMC wards")
        return inserted
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    load_l08_sensitive_sites()
