from scripts.build_gazetteer import build_rows


def _node(i, name, place, lat, lon, **tags):
    return {"type": "node", "id": i, "lat": lat, "lon": lon, "tags": {"name": name, "place": place, **tags}}


def _road(i, name, lat, lon):
    return {"type": "way", "id": i, "center": {"lat": lat, "lon": lon},
            "tags": {"name": name, "highway": "primary"}}


def test_same_name_far_apart_is_marked_ambiguous():
    rows = build_rows([_node(1, "Ganesh Nagar", "neighbourhood", 18.50, 73.85),
                       _node(2, "Ganesh Nagar", "neighbourhood", 18.60, 73.95)])
    assert [r["kind"] for r in rows] == ["ambiguous"]


def test_same_name_close_keeps_higher_rank_kind_and_marathi():
    rows = build_rows([_node(1, "Kothrud", "neighbourhood", 18.5070, 73.8070),
                       _node(2, "Kothrud", "suburb", 18.5074, 73.8077, **{"name:mr": "कोथरूड"})])
    assert rows[0]["kind"] == "suburb" and rows[0]["name_marathi"] == "कोथरूड"


def test_road_segments_collapse_to_median_point():
    rows = build_rows([_road(1, "FC Road", 18.50, 73.84), _road(2, "FC Road", 18.52, 73.84),
                       _road(3, "FC Road", 18.53, 73.84)])
    assert len(rows) == 1 and rows[0]["kind"] == "road" and rows[0]["lat"] == 18.52
