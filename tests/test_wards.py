import csv

from app.ingest.wards import load_ward_population, load_wards

GEOJSON_PATH = "data/wards/pune-2022-wards.geojson"
POPULATION_CSV = "data/labelling/ward_population.csv"


def test_load_wards_inserts_all_features(clean_wards):
    count = load_wards(GEOJSON_PATH)
    assert count == 58

    with clean_wards.cursor() as cur:
        cur.execute("SELECT count(*) FROM wards")
        assert cur.fetchone()[0] == 58


def test_load_wards_geometry_is_valid(clean_wards):
    load_wards(GEOJSON_PATH)
    with clean_wards.cursor() as cur:
        cur.execute("SELECT count(*) FROM wards WHERE NOT ST_IsValid(geom)")
        assert cur.fetchone()[0] == 0


def test_load_wards_is_idempotent(clean_wards):
    load_wards(GEOJSON_PATH)
    count = load_wards(GEOJSON_PATH)
    assert count == 58
    with clean_wards.cursor() as cur:
        cur.execute("SELECT count(*) FROM wards")
        assert cur.fetchone()[0] == 58


def test_load_wards_fills_area_from_the_boundary_geometry(clean_wards):
    load_wards(GEOJSON_PATH)
    with clean_wards.cursor() as cur:
        cur.execute("SELECT count(*) FROM wards WHERE area_sqkm IS NULL")
        assert cur.fetchone()[0] == 0
        # PMC's published area is ~516 sq km; OSM-derived boundaries should
        # land close to it, and a unit slip (sq m vs sq km) would not.
        cur.execute("SELECT sum(area_sqkm) FROM wards")
        assert 480 < float(cur.fetchone()[0]) < 540


def test_population_sheet_covers_every_ward_with_a_citable_source(clean_wards):
    load_wards(GEOJSON_PATH)
    with open(POPULATION_CSV, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 58
    assert {int(r["ward_2022_id"]) for r in rows} == set(range(1, 59))
    for row in rows:
        assert row["ward_scheme"] == "PMC 2022"
        assert row["source_url"].endswith(".pdf"), "each row must name where to get the number"


def test_load_ward_population_skips_blank_rows_and_leaves_population_null(clean_wards, tmp_path):
    load_wards(GEOJSON_PATH)
    sheet = tmp_path / "blank.csv"
    with open(POPULATION_CSV, newline="") as src, open(sheet, "w", newline="") as dst:
        rows = list(csv.DictReader(src))
        writer = csv.DictWriter(dst, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    assert load_ward_population(str(sheet)) == 0
    with clean_wards.cursor() as cur:
        cur.execute("SELECT count(*) FROM wards WHERE population IS NOT NULL")
        assert cur.fetchone()[0] == 0


def test_load_ward_population_writes_the_numbers_that_are_filled_in(clean_wards, tmp_path):
    load_wards(GEOJSON_PATH)
    sheet = tmp_path / "filled.csv"
    with open(POPULATION_CSV, newline="") as src:
        rows = list(csv.DictReader(src))
    rows[0]["population"] = "84210"
    rows[1]["population"] = "51900"
    with open(sheet, "w", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    assert load_ward_population(str(sheet)) == 2
    with clean_wards.cursor() as cur:
        cur.execute("SELECT population FROM wards WHERE id = 1")
        assert cur.fetchone()[0] == 84210
        cur.execute("SELECT count(*) FROM wards WHERE population IS NOT NULL")
        assert cur.fetchone()[0] == 2


def test_load_ward_population_is_idempotent(clean_wards, tmp_path):
    load_wards(GEOJSON_PATH)
    sheet = tmp_path / "filled.csv"
    with open(POPULATION_CSV, newline="") as src:
        rows = list(csv.DictReader(src))
    rows[0]["population"] = "84210"
    with open(sheet, "w", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    assert load_ward_population(str(sheet)) == 1
    assert load_ward_population(str(sheet)) == 1
