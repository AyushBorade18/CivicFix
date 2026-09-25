from unittest.mock import patch

import numpy as np

from app.ingest.mplads import load_mplads

FIXTURE_PATH = "tests/fixtures/mplads_sample.csv"

WARD_5_CENTROID = (18.551054786274666, 73.93429308035661)


class _FakeModel:
    def encode(self, texts, batch_size=64, show_progress_bar=False):
        return np.zeros((len(texts), 384), dtype=float)


def _fake_geocode(query, cache_path=None):
    if "pashan lake" in query.lower():
        return WARD_5_CENTROID
    return None  # "public hall in an area nobody can geocode" -> unresolved


def _run_load():
    with patch("app.ingest.mplads._get_model", return_value=_FakeModel()), \
         patch("app.ingest.mplads.geocode", side_effect=_fake_geocode):
        return load_mplads(FIXTURE_PATH)


def test_load_mplads_filters_to_pune_district(clean_works):
    count = _run_load()
    assert count == 3  # the Nagaland row is excluded

    with clean_works.cursor() as cur:
        cur.execute("SELECT count(*) FROM works")
        assert cur.fetchone()[0] == 3


def test_raw_ward_number_alone_is_not_used_to_place_a_work(clean_works):
    # "Ward No.5" in MPLADS text mixes numbering schemes; without a reviewed
    # ward, a geocoded landmark or a gazetteer place, the work stays unplaced.
    _run_load()
    with clean_works.cursor() as cur:
        cur.execute(
            "SELECT category, ward_id, geom, geom_confidence, source_record_id FROM works "
            "WHERE work_name LIKE 'Road Concreting%'"
        )
        category, ward_id, geom, geom_confidence, source_record_id = cur.fetchone()
    assert category == "pothole_road"
    assert ward_id is None and geom is None and geom_confidence is None
    assert source_record_id == "900001"


def test_geocode_fallback_binds_ward_via_st_contains(clean_works):
    _run_load()
    with clean_works.cursor() as cur:
        cur.execute(
            "SELECT ward_id, ST_Y(geom), ST_X(geom), geom_confidence FROM works "
            "WHERE description LIKE '%Pashan lake%'"
        )
        ward_id, lat, lon, geom_confidence = cur.fetchone()
    assert ward_id == 5
    assert geom_confidence == 1.0
    assert lat == WARD_5_CENTROID[0]
    assert lon == WARD_5_CENTROID[1]


def test_unresolvable_location_leaves_geom_null_not_guessed(clean_works):
    _run_load()
    with clean_works.cursor() as cur:
        cur.execute(
            "SELECT geom, ward_id FROM works WHERE description LIKE '%public hall%'"
        )
        geom, ward_id = cur.fetchone()
    assert geom is None
    assert ward_id is None


def test_embedding_is_stored(clean_works):
    _run_load()
    with clean_works.cursor() as cur:
        cur.execute("SELECT count(*) FROM works WHERE embedding IS NOT NULL")
        assert cur.fetchone()[0] == 3
