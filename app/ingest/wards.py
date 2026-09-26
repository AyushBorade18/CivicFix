import csv
import json

from app.db import get_connection

POPULATION_CSV = "data/labelling/ward_population.csv"


def load_wards(geojson_path: str) -> int:
    """Load PMC ward boundaries from GeoJSON into the wards table.

    Ward id is taken from the `wardnum` property so it stays stable across
    reloads and can be referenced directly (e.g. from a "ward no. N" regex
    match during location extraction elsewhere in the pipeline).
    """
    with open(geojson_path) as f:
        collection = json.load(f)

    features = collection["features"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            for feature in features:
                props = feature["properties"]
                ward_id = props["wardnum"]
                name = props.get("Name2") or props["Name1"]
                geom_json = json.dumps(feature["geometry"])
                cur.execute(
                    """
                    INSERT INTO wards (id, name, geom)
                    VALUES (%s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)))
                    ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, geom = EXCLUDED.geom
                    """,
                    (ward_id, name, geom_json),
                )
            cur.execute(
                "SELECT setval(pg_get_serial_sequence('wards', 'id'), (SELECT max(id) FROM wards))"
            )
            # area_sqkm is derived from the boundary we just stored, so it is
            # never sourced or hand-entered. priority.py needs it together
            # with population to scale the exposure radius by ward density.
            cur.execute(
                "UPDATE wards SET area_sqkm = ST_Area(geom::geography) / 1000000.0"
            )
        conn.commit()

    return len(features)


def load_ward_population(csv_path: str = POPULATION_CSV) -> int:
    """Write the populations filled into the ward sheet; returns how many.

    Blank rows are skipped rather than defaulted: with population NULL,
    priority.py falls back to its base exposure radius and says so, which is
    honest. A made-up population would silently reshape every ranking.
    """
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["population"].strip()]

    with get_connection() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    "UPDATE wards SET population = %s WHERE id = %s",
                    (int(row["population"]), int(row["ward_2022_id"])),
                )
        conn.commit()

    return len(rows)
