from app.ingest.category import map_work_category


def test_road_construction_maps_to_pothole_road():
    assert map_work_category("Road Concreting at Ward No.11, Sutardara Kothrud.") == "pothole_road"


def test_drainage_description_maps_to_drainage_sewage():
    assert map_work_category(
        "The project aims to provide an effective drainage system for the proper "
        "disposal of surface and wastewater."
    ) == "drainage_sewage"


def test_streetlight_description_maps_to_streetlight():
    assert map_work_category("Installation of LED street light poles near the market") == "streetlight"


def test_unrelated_community_work_falls_back_to_other():
    assert map_work_category(
        "Construction of a public hall at Mulashi Khurd, Pune District"
    ) == "other"


def test_empty_description_falls_back_to_other():
    assert map_work_category("") == "other"
    assert map_work_category(None) == "other"


def test_real_mplads_road_phrasings_map_to_pothole_road():
    for text in [
        "Construction of internal road at Vadar Galli, Prabhag 2, Daund City",
        "Construction A Road At Kalewadi Adarshnagar in Ganaraj Colony No 2",
        "Construction Of Raod Between Main Road to Praim Square Socity",
        "Construction of Concrete Road from Pachangre Sakat Vasti to Akshay Ghodake Vasti",
        "To concretize the road from Ganeshpeth Hussain Bakery to Vegetable Market.",
        "Sai Ganesh Park S.No. 122, Khandvenagar Lohegaon, road in front of Shri Aaij Niwas to be concretized.",
        "Road-related works at Dhor Galli, Ganesh Peth, within the Pune Lok Sabha constituency.",
        "Concretization of Galli No. 04 in Mauli Kripa Housing Society, Talwade",
    ]:
        assert map_work_category(text) == "pothole_road", text


def test_work_merely_located_on_a_road_is_not_a_road_work():
    assert map_work_category(
        "Construction of a defensive wall at Senapati Bapat Road Public Works Department"
    ) == "other"
    assert map_work_category("Construction a hall ARAI Road, Hanuman Nagar, Kothrud") == "other"


def test_paving_blocks_map_to_footpath_and_solar_lamps_to_streetlight():
    assert map_work_category("Installation of paving blocks near Rambagh Colony") == "footpath"
    assert map_work_category("Fitting of Paver Blocks beside Rokdai Temple") == "footpath"
    assert map_work_category("Fixing A Solar High Mast Lamp In Dongarwadi") == "streetlight"
    assert map_work_category("Fixing A 6 Solar Lamp pol Towrds Kalubai Road") == "streetlight"


def test_bus_stops_and_toilets_stay_other():
    assert map_work_category("Ward 11 Establishment of a bus stop at Ashish Garden, Kothrud Up") == "other"
    assert map_work_category("Repair of toilets in Chaitraban Colony, Hadapsar") == "other"


def test_hall_project_with_incidental_paving_stays_other():
    assert map_work_category("Construction of Community Hall along with Paving Block") == "other"
