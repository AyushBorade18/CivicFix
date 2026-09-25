import csv
from datetime import date


from app.db import get_connection
from app.ingest.category import map_work_category
from app.ingest.geocode import geocode
from app.ingest.location import extract_landmark_phrase, extract_ward_number
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


class _LocationStats:
    def __init__(self):
        self.ward_regex = 0
        self.geocoded = 0
        self.unresolved = 0

    def summary(self, total: int) -> str:
        return (
            f"location resolved: {self.ward_regex} via ward number, "
            f"{self.geocoded} via geocoding, {self.unresolved} unresolved "
            f"(of {total})"
        )


def _resolve_location(conn, description: str, stats: _LocationStats):
    """Returns (lat, lon, ward_id), any of which may be None. Never guesses:
    no ward number and no geocode match means geom stays NULL rather than
    falling back to a fixed default point.
    """
    ward_id = extract_ward_number(description)
    if ward_id is not None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ST_Y(ST_Centroid(geom)), ST_X(ST_Centroid(geom)) FROM wards WHERE id = %s",
                (ward_id,),
            )
            row = cur.fetchone()
        if row:
            stats.ward_regex += 1
            return row[0], row[1], ward_id

    landmark = extract_landmark_phrase(description)
    if landmark is None:
        stats.unresolved += 1
        return None, None, None

    point = geocode(f"{landmark}, Pune, Maharashtra, India")
    if point is None:
        stats.unresolved += 1
        return None, None, None

    lat, lon = point
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM wards WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
            (lon, lat),
        )
        row = cur.fetchone()
    stats.geocoded += 1
    return lat, lon, (row[0] if row else None)


def load_mplads(csv_path: str) -> int:
    """Loads MPLADS public-works records for Pune district into `works`.

    Maps free-text descriptions to civic_category, resolves each record to a
    point (ward-number mention in the text, else geocoding, else left NULL),
    binds to a ward via ST_Contains, and batch-embeds descriptions.
    """
    with open(csv_path, newline="") as f:
        rows = [r for r in csv.DictReader(f) if _is_pune_district(r)]

    descriptions = [r["workDescription"] or "" for r in rows]
    embeddings = _get_model().encode(descriptions, batch_size=64, show_progress_bar=False)

    stats = _LocationStats()

    with get_connection() as conn:
        for row, embedding in zip(rows, embeddings):
            description = row["workDescription"]
            category = map_work_category(description)
            lat, lon, ward_id = _resolve_location(conn, description, stats)

            geom_expr = "ST_SetSRID(ST_MakePoint(%s, %s), 4326)" if lat is not None else "NULL"
            geom_params = (lon, lat) if lat is not None else ()

            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO works (
                        work_name, description, cost, status, sanctioned_on,
                        completed_on, agency, constituency, category, geom,
                        ward_id, embedding
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, {geom_expr}, %s, %s::vector
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
                        _embedding_literal(embedding),
                    ),
                )
        conn.commit()

    print(stats.summary(len(rows)))
    return len(rows)
