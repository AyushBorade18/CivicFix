"""LO4: build the NON-PRODUCTION normalized public-works master dataset.

    python -m scripts.lo4.build_public_works_master

Reads only files (never the database, never the network):
  - data/mplads/MPLADS_cleaned.csv          MPLADS works (only source with work records)
  - data/cache/geocode_cache.json           existing Nominatim results; no new lookups
  - data/wards/pune-2022-wards.geojson      PMC 2022 prabhag polygons

Writes data/eval/public_works_master.csv. Does not touch the `works` table.

Sources checked and deliberately contributing ZERO rows (see data/eval/README.md):
  - PMC Open Data (~/Downloads/PMC.zip): ward-level indicators, river water
    quality, PMPML bus stops - no project/work records.
  - ~/Downloads/MPLADS.csv (older export): 38 Pune rows, all rural, all
    "Unsanctioned", generic "NA - <category>" text, no work id.
  - MahaTenders: no data in the repo yet. No placeholder rows are created.

Rules this script follows:
  - ward_id is ONLY set from a geocoded point falling inside a PMC 2022
    polygon. A "Ward No. N" in MPLADS text is never mapped to ward_id: the
    text mixes PMC old/new schemes, PCMC wards and village wards.
  - Coordinates only come from the existing geocode cache, and only for a
    landmark phrase that isn't a known-junk query. All are unverified.
  - Nothing missing is filled in; missing stays empty.
"""
import csv
import json
import re
import sys
from pathlib import Path

from shapely.geometry import Point, shape

from app.ingest.category import map_work_category
from app.ingest.location import _WARD_PATTERN, extract_landmark_phrase

MPLADS_CSV = Path("data/mplads/MPLADS_cleaned.csv")
GEOCODE_CACHE = Path("data/cache/geocode_cache.json")
WARDS_GEOJSON = Path("data/wards/pune-2022-wards.geojson")
OUTPUT_CSV = Path("data/eval/public_works_master.csv")

COLUMNS = [
    # the normalized schema requested for LO4
    "work_id", "source", "source_record_id", "work_name", "work_description",
    "work_category", "authority", "location_text", "ward_id", "latitude",
    "longitude", "status", "start_date", "completion_date", "cost",
    "source_url", "location_confidence",
    # provenance / review columns - why each value above is what it is
    "recommended_date", "cost_basis", "category_method", "location_method",
    "ward_number_in_text", "ward_mapping_status", "jurisdiction_hint",
    "pmc_locality_hint", "quality_flags", "matching_usability",
]

# Landmark phrases the regex extracted that are not places. Their cached
# geocode results are coordinates for the wrong thing entirely.
JUNK_LANDMARKS = {
    "survey no", "office at", "park", "shri", "pcmc", "post", "the village",
    "gram panchayat", "village", "taluka", "ward no", "ward number",
}

PCMC_CUES = ("pimpri", "chinchwad", "pcmc", "nigdi", "talwade", "chikhali",
             "thergaon", "kalewadi", "landewadi", "more vasti", "rupinagar")
RURAL_CUES = ("taluka", " tal.", " tal ", "gram panchayat", "grampanchayat",
              "at post", "village", "dist.", "district pune", "distict")
# Positive text evidence that a work is inside PMC limits. Words taken from
# the 58 PMC 2022 ward names (data/wards/ward-attributes.csv), plus a few
# well-known PMC localities/spellings that appear in MPLADS text but not in
# ward names. Place names only - used as a hint column, never as ward_id,
# because one locality (e.g. Kothrud) spans several wards.
PMC_LOCALITIES = (
    "dhanori", "vishrantwadi", "tingrenagar", "lohegaon", "lohgaon", "vimannagar",
    "kharadi", "wagholi", "vadgaon sheri", "ramwadi", "kalyaninagar", "yerwada",
    "yerawada", "shivajinagar", "sangamwadi", "bopodi", "aundh", "balewadi", "baner",
    "mahalunge", "pashan", "bawdhan", "bavdhan", "gokhalenagar", "erandwane",
    "erandvana", "shaniwar peth", "navi peth", "kasba peth", "rasta peth",
    "koregaon park", "mundhwa", "manjari", "hadapsar", "magarpatta", "wanwadi",
    "wanowrie", "bhavani peth", "ghorpade peth", "ghorpadi", "kelewadi", "kothrud",
    "warje", "karvenagar", "dattawadi", "padmavati", "market yard", "bibvewadi",
    "bibwewadi", "kondhva", "kondhwa", "fursungi", "yewalewadi", "balajinagar",
    "sahakarnagar", "taljai", "vadgaon bk", "manikbaug", "nanded city", "khadakwasla",
    "narhe", "dhayari", "ambegaon", "dhankawadi", "bharati vidyapeeth",
    "sukhsagarnagar", "sukhsagar nagar", "katraj", "ganesh peth", "ganeshpeth",
    "senapati bapat", "sb road", "sinhagad road", "swargate", "deccan", "sutardara",
    "kishkindhanagar", "shastrinagar", "shashtrinagar", "hanumannagar", "ganj peth",
)
NON_INFRA_CUES = ("laptop", "computer", "printer", "ambulance", "vehicle",
                  "furniture", "books", "equipment", "projector", "camera")
PLACEHOLDER_DESCRIPTIONS = {"as per attechment", "as per attachment", "na", "-"}


def _is_pune(row: dict) -> bool:
    # Same filter as app/ingest/mplads.py, so the row set matches `works`.
    return "pune" in (row.get("ida") or "").lower() or "pune" in (row.get("constituency") or "").lower()


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def _work_name(description: str, limit: int = 80) -> str:
    # MPLADS has no title field; same derivation as app/ingest/mplads.py.
    if len(description) <= limit:
        return description
    return description[:limit].rstrip() + "…"


def _pmc_localities(lowered: str) -> list[str]:
    return [loc for loc in PMC_LOCALITIES if re.search(rf"\b{re.escape(loc)}\b", lowered)]


def _jurisdiction_hint(lowered: str, inside_pmc: bool, localities: list[str]) -> str:
    if any(cue in lowered for cue in PCMC_CUES):
        return "pcmc_text"
    if any(cue in lowered for cue in RURAL_CUES):
        return "rural_district_text"
    if inside_pmc:
        return "pmc_geocoded"
    if localities:
        return "pmc_locality_text"
    return "unknown"


def _ward_mapping_status(lowered: str, ward_text: str | None, jurisdiction: str) -> str:
    if ward_text is None:
        return "no_ward_in_text"
    if jurisdiction == "pcmc_text":
        return "pcmc_ward_not_pmc"
    if "old ward" in lowered or "new ward" in lowered:
        return "mixed_old_new_scheme_stated"
    if jurisdiction == "rural_district_text":
        return "village_or_rural_ward"
    return "unverified_scheme"


def _quality_flags(row: dict, description: str, lowered: str) -> list[str]:
    flags = []
    if not description:
        flags.append("missing_description")
    elif lowered in PLACEHOLDER_DESCRIPTIONS or len(description) < 15:
        flags.append("placeholder_or_too_short")
    if any(cue in lowered for cue in NON_INFRA_CUES):
        flags.append("non_infrastructure_hint")
    rec, done = row.get("recommendationDate") or "", row.get("completedDate") or ""
    if rec and done and done < rec:
        flags.append("completed_before_recommended")
    if row.get("status") == "completed" and not done:
        flags.append("completed_without_date")
    return flags


def _matching_usability(status: str, category: str, flags: list[str], jurisdiction: str) -> str:
    """A triage tier for LO4 candidate generation, not a label.

    candidate:*      completed, civic category, positive PMC evidence
    review:*         could be a candidate once a human checks one thing
    negative_only:*  real PMC-area work usable as a hard negative
    exclude:*        should not enter the LO4 pair set at all
    """
    if "missing_description" in flags or "placeholder_or_too_short" in flags:
        return "exclude:bad_description"
    if jurisdiction == "pcmc_text":
        return "exclude:outside_pmc_pcmc"
    if jurisdiction == "rural_district_text":
        return "exclude:outside_pmc_rural"
    if jurisdiction == "unknown":
        return "exclude:jurisdiction_unknown"
    # From here on there is positive PMC evidence (geocode or locality text).
    if category == "other":
        if status == "completed" and "other_but_mentions_civic_infra" in flags:
            return "review:category_mapper_miss"
        return "negative_only:non_civic_category"
    if status != "completed":
        return "negative_only:not_completed"
    if jurisdiction == "pmc_geocoded":
        return "candidate:geocoded_unverified"
    return "candidate:locality_text_only"


def build() -> list[dict]:
    csv.field_size_limit(sys.maxsize)
    geocode_cache = json.loads(GEOCODE_CACHE.read_text())
    wards = [
        (f["properties"]["wardnum"], shape(f["geometry"]))
        for f in json.loads(WARDS_GEOJSON.read_text())["features"]
    ]

    with MPLADS_CSV.open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if _is_pune(r)]

    out = []
    for row in rows:
        description = _clean(row.get("workDescription"))
        lowered = description.lower()

        ward_match = _WARD_PATTERN.search(description)
        ward_text = ward_match.group(0) if ward_match else None
        landmark = extract_landmark_phrase(description)
        junk_landmark = bool(landmark) and landmark.lower() in JUNK_LANDMARKS
        if junk_landmark:
            landmark = None

        lat = lon = ward_id = None
        location_method = "junk_landmark_ignored" if junk_landmark else "none"
        if landmark:
            cached = geocode_cache.get(f"{landmark}, Pune, Maharashtra, India")
            if cached:
                lat, lon = cached
                location_method = "geocode_cache_landmark"
                point = Point(lon, lat)
                for wardnum, polygon in wards:
                    if polygon.contains(point):
                        ward_id = wardnum
                        break
            else:
                location_method = "landmark_text_not_geocoded"

        # A cached geocode that lands inside PMC while the text itself says
        # PCMC or a rural taluka is a wrong geocode (e.g. "Indian Colony ...
        # in PCMC" resolving into PMC ward 11). Keep the raw coordinates for
        # review, but never derive a ward from them.
        geocode_conflict = ward_id is not None and (
            any(cue in lowered for cue in PCMC_CUES) or any(cue in lowered for cue in RURAL_CUES)
        )
        if geocode_conflict:
            ward_id = None

        inside_pmc = ward_id is not None
        localities = _pmc_localities(lowered)
        jurisdiction = _jurisdiction_hint(lowered, inside_pmc, localities)
        ward_status = _ward_mapping_status(lowered, ward_text, jurisdiction)

        if geocode_conflict:
            location_confidence = "geocode_conflicts_with_text"
        elif lat is not None and inside_pmc:
            location_confidence = "geocoded_unverified_inside_pmc"
        elif lat is not None:
            location_confidence = "geocoded_unverified_outside_pmc"
        elif landmark or ward_text:
            location_confidence = "text_only"
        else:
            location_confidence = "none"

        category = map_work_category(description)
        flags = _quality_flags(row, description, lowered)
        if geocode_conflict:
            flags.append("geocode_conflicts_with_text")
        if category == "other" and any(w in lowered for w in ("road", "drain", "footpath", "paving", "light")):
            flags.append("other_but_mentions_civic_infra")
        location_text = "; ".join(p for p in (landmark, ward_text) if p)

        final_amount, recommended_amount = row.get("finalAmount"), row.get("recommendedAmount")
        cost, cost_basis = (final_amount, "finalAmount") if final_amount else (
            (recommended_amount, "recommendedAmount") if recommended_amount else ("", "none"))

        out.append({
            "work_id": f"MPLADS-{row['workId']}",
            "source": "MPLADS",
            "source_record_id": row["workId"],
            "work_name": _work_name(description),
            "work_description": description,
            "work_category": category,
            "authority": row.get("ida") or "",
            "location_text": location_text,
            "ward_id": ward_id if ward_id is not None else "",
            "latitude": lat if lat is not None else "",
            "longitude": lon if lon is not None else "",
            "status": row.get("status") or "",
            "start_date": "",  # MPLADS has no start date; recommendationDate is not one
            "completion_date": row.get("completedDate") or "",
            "cost": cost,
            "source_url": "",  # not present in the export; not invented
            "location_confidence": location_confidence,
            "recommended_date": row.get("recommendationDate") or "",
            "cost_basis": cost_basis,
            "category_method": "keyword_v1(app/ingest/category.py)",
            "location_method": location_method,
            "ward_number_in_text": ward_text or "",
            "ward_mapping_status": ward_status,
            "jurisdiction_hint": jurisdiction,
            "quality_flags": "|".join(flags),
            "pmc_locality_hint": "|".join(localities),
            "matching_usability": _matching_usability(
                row.get("status") or "", category, flags, jurisdiction,
            ),
        })
    return out


def main() -> None:
    records = build()
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(records)
    print(f"wrote {len(records)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
