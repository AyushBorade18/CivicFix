from app.ingest.osm_sensitive_sites import deduplicate_sites
from app.ingest.pmc_bus_stops import parse_stop_rows

HEADER = ["Route Type", "Route", "Stop Code", "Stop Seq", "Stop Name", "Stop Name Marathi", "LAT", "LONG", "Stage"]


def test_parses_stops_and_skips_rows_without_usable_coordinates():
    rows = [
        HEADER,
        ["BRTS", "100-D", "100-D-01", 1.0, "Swargate", "स्वारगेट", 18.5004408, 73.8594748, 1.0],
        ["BRTS", "100-D", "100-D-02", 2.0, "Nowhere", "", "", "", 1.0],       # blank coords
        ["BRTS", "100-D", "100-D-03", 3.0, "Swapped", "", 73.85, 18.50, 1.0],  # lat/lon swapped
        ["BRTS", "100-D", "100-D-04", 4.0, "Zero", "", 0.0, 0.0, 1.0],
    ]
    sites = parse_stop_rows(rows)
    assert [s["name"] for s in sites] == ["Swargate"]
    assert sites[0] == {"source_id": "pmc_pmpml:100-D-01", "category": "bus_stop", "name": "Swargate",
                        "lat": 18.5004408, "lon": 73.8594748}


def test_same_stop_on_two_routes_collapses_to_one_site():
    rows = [
        HEADER,
        ["BRTS", "100-D", "100-D-02", 2.0, "Tech Mahindra", "", 18.581104, 73.687604, 1.0],
        ["BRTS", "101-U", "101-U-07", 7.0, "Tech Mahindra", "", 18.5810162, 73.6877038, 1.0],  # ~15 m away
    ]
    assert len(deduplicate_sites(parse_stop_rows(rows))) == 1
