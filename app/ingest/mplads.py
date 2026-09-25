import csv
from datetime import date


from app.db import get_connection
from app.ingest.category import map_work_category
from app.ingest.geocode import geocode
from app.ingest.location import (
    JUNK_LANDMARKS, extract_landmark_phrase, find_gazetteer_place, is_route_phrase, outside_pmc_text,
)
from app.nlp.embeddings import get_embedding_model as _get_model

def _is_pune_district(row: dict) -> bool:
    return "pune" in (row.get("ida") or "").lower() or "pune" in (row.get("constituency") or "").lower()


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_amount(row: dict) -> float | None:
    for field in ("finalAmount", "recommendedAmount"):
        value = row.get(field)
        if value:
            return float(value)
    return None


def _embedding_literal(vector) -> str:
    return "[" + ",".join(str(float(v)) for v in vector) + "]"


def _work_name(description: str, limit: int = 80) -> str:
    """MPLADS gives no separate title field, only workDescription -- derive a
    short human-readable name from it since `works.work_name` is NOT NULL.
    """
    text = " ".join((description or "").split())
    if len(text) <= limit:
        return text or "(untitled work)"
    return text[:limit].rstrip() + "…"


REVIEW_CSV = "data/eval/mplads_ward_review.csv"
GEOM_CONF_GEOCODED = 1.0  # a named landmark Nominatim resolved: precise
GEOM_CONF_WARD_LEVEL = 0.5  # reviewed ward centroid or gazetteer locality centre


def _reviewed_wards() -> dict[str, int]:
    """MPLADS workId -> PMC 2022 ward, only where a human reviewer assigned
    one (data/eval/mplads_ward_review.csv). A raw "Ward No. N" in MPLADS text
    is never used on its own: the text mixes PMC old/new schemes, PCMC and
    village wards, and the review found most numbers can't be mapped.
    """
    try:
        with open(REVIEW_CSV, newline="") as f:
            return {r["work_id"]: int(r["candidate_2022_ward"])
                    for r in csv.DictReader(f) if r["candidate_2022_ward"].strip()}
    except FileNotFoundError:
        return {}


class _LocationStats:
    def __init__(self):
        self.geocoded = 0
        self.reviewed_ward = 0
        self.gazetteer = 0
        self.outside_pmc = 0
        self.unresolved = 0

    def summary(self, total: int) -> str:
        return (
            f"location resolved: {self.geocoded} via geocoded landmark, "
            f"{self.reviewed_ward} via reviewed ward, {self.gazetteer} via gazetteer place, "
            f"{self.outside_pmc} left unplaced as PCMC/rural text, {self.unresolved} unresolved (of {total})"
        )


def _ward_containing(conn, lat: float, lon: float) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM wards WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
            (lon, lat),
        )
        row = cur.fetchone()
    return row[0] if row else None


def _resolve_location(conn, description: str, work_id: str, reviewed: dict[str, int],
                      stats: _LocationStats):
    """Returns (lat, lon, ward_id, geom_confidence), any of which may be None.
    Order: geocoded landmark (precise) -> human-reviewed ward (its centroid)
    -> most specific gazetteer place named in the text (its OSM centre).
    Nothing found leaves geom NULL rather than guessing. Text that says the
    work is in PCMC or a rural taluka is never placed: its locality names
    can collide with PMC ones ("Pashan Mala, Tq. Shirur").
    """
    if outside_pmc_text(description):
        stats.outside_pmc += 1
        return None, None, None, None

    landmark = extract_landmark_phrase(description)
    if landmark and landmark.lower() not in JUNK_LANDMARKS and not is_route_phrase(landmark):
        point = geocode(f"{landmark}, Pune, Maharashtra, India")
        if point is not None:
            stats.geocoded += 1
            return point[0], point[1], _ward_containing(conn, *point), GEOM_CONF_GEOCODED

    ward_id = reviewed.get(work_id)
    if ward_id is not None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ST_Y(ST_Centroid(geom)), ST_X(ST_Centroid(geom)) FROM wards WHERE id = %s",
                (ward_id,),
            )
            row = cur.fetchone()
        if row:
            stats.reviewed_ward += 1
            return row[0], row[1], ward_id, GEOM_CONF_WARD_LEVEL

    place = find_gazetteer_place(description)
    if place is not None:
        lat, lon = float(place["lat"]), float(place["lon"])
        stats.gazetteer += 1
        return lat, lon, _ward_containing(conn, lat, lon), GEOM_CONF_WARD_LEVEL

    stats.unresolved += 1
    return None, None, None, None


def load_mplads(csv_path: str) -> int:
    """Loads MPLADS public-works records for Pune district into `works`.

    Maps free-text descriptions to civic_category, resolves each record to a
    point (see _resolve_location), binds to a ward via ST_Contains, and
    batch-embeds descriptions.
    """
    with open(csv_path, newline="") as f:
        rows = [r for r in csv.DictReader(f) if _is_pune_district(r)]

    descriptions = [r["workDescription"] or "" for r in rows]
    embeddings = _get_model().encode(descriptions, batch_size=64, show_progress_bar=False)

    stats = _LocationStats()
    reviewed = _reviewed_wards()

    with get_connection() as conn:
        for row, embedding in zip(rows, embeddings):
            description = row["workDescription"]
            category = map_work_category(description)
            lat, lon, ward_id, geom_confidence = _resolve_location(
                conn, description, row["workId"], reviewed, stats)

            geom_expr = "ST_SetSRID(ST_MakePoint(%s, %s), 4326)" if lat is not None else "NULL"
            geom_params = (lon, lat) if lat is not None else ()

            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO works (
                        work_name, description, cost, status, sanctioned_on,
                        completed_on, agency, constituency, category, geom,
                        ward_id, geom_confidence, source_record_id, embedding
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, {geom_expr}, %s, %s, %s, %s::vector
                    )
                    """,
                    (
                        _work_name(description),
                        description,
                        _parse_amount(row),
                        row["status"],
                        _parse_date(row["recommendationDate"]),
                        _parse_date(row["completedDate"]),
                        row["ida"],
                        row["constituency"],
                        category,
                        *geom_params,
                        ward_id,
                        geom_confidence,
                        row["workId"],
                        _embedding_literal(embedding),
                    ),
                )
        conn.commit()

    print(stats.summary(len(rows)))
    return len(rows)
