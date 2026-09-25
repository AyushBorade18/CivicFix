from app.ingest.l08_sensitive_sites import parse_hospital_rows, parse_school_rows


def test_parses_hospital_rows_as_sites():
    rows = [
        ["City Name", "Ward No", "Ward Name", "Name of healthcare facility", "Type of facility",
         "Latitude", "Longitude"],
        ["Pune", "6", "Kothrud-Bawdhan", "Jog Hospital", "private hospital", "18.5091699", "73.82159066"],
    ]
    sites = parse_hospital_rows(rows, source_prefix="l08_private_hospital")
    assert sites == [{"source_id": "l08_private_hospital:0", "category": "hospital",
                      "name": "Jog Hospital", "lat": 18.5091699, "lon": 73.82159066}]


def test_hospital_rows_skip_blank_coordinates():
    rows = [
        ["City Name", "Ward No", "Ward Name", "Name of healthcare facility", "Type of facility",
         "Latitude", "Longitude"],
        ["Pune", "6", "Kothrud-Bawdhan", "No Coords Clinic", "private hospital", "", ""],
    ]
    assert parse_hospital_rows(rows, source_prefix="l08_private_hospital") == []


def test_parses_school_rows_from_combined_lat_long_column():
    rows = [
        ["Sr No", "Facility Type/Category", "Name of Facility", "Address", "Location(lat,long)",
         "Prabhag Name", "Ward Name"],
        ["1", "School-Bhavan", "V D Ghate School", "Phulenagar, Yerwada",
         "(18.558191145225297, 73.87715113488775)", "Shanti Nagar", "Sangamwadi"],
    ]
    sites = parse_school_rows(rows)
    assert sites == [{"source_id": "l08_pmc_school:1", "category": "school", "name": "V D Ghate School",
                      "lat": 18.558191145225297, "lon": 73.87715113488775}]


def test_school_rows_skip_unparseable_or_missing_location():
    rows = [
        ["Sr No", "Facility Type/Category", "Name of Facility", "Address", "Location(lat,long)",
         "Prabhag Name", "Ward Name"],
        ["1", "School-Bhavan", "No Location School", "Somewhere", "", "Shanti Nagar", "Sangamwadi"],
        # footer/junk rows the real file ends with - no numeric Sr No, ragged columns
        ["Note- subject to change with addition/ deletion of facilities."],
        [""],
    ]
    assert parse_school_rows(rows) == []
