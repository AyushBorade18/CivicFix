from training.finetune_encoder import batches_without_repeated_groups, build_triplets, split_groups

CATEGORIES = ["pothole_road", "drainage_sewage", "water_supply", "streetlight",
              "garbage_waste", "footpath", "traffic_signage", "other"]


def _groups():
    # 8 categories x 5 groups x 3 variants; groups alternate between two localities.
    rows = []
    for c_i, cat in enumerate(CATEGORIES):
        for g in range(5):
            gid = f"G-{c_i}-{g}"
            for v in "abc":
                rows.append({"group_id": gid, "id": f"{gid}-{v}", "category": cat,
                             "locality": "Kothrud" if g % 2 else "Baner",
                             "language": "english", "text": f"{cat} {g} {v}"})
    return rows


def test_split_is_by_group_deterministic_and_covers_every_category():
    rows = _groups()
    train, test = split_groups(rows, test_per_category=1, seed=7)
    assert {r["group_id"] for r in train}.isdisjoint({r["group_id"] for r in test})
    assert {r["category"] for r in test} == set(CATEGORIES)
    assert split_groups(rows, test_per_category=1, seed=7)[1] == test


def test_triplets_use_same_group_positives_and_same_place_different_problem_negatives():
    rows = _groups()
    by_text = {r["text"]: r for r in rows}
    triplets = build_triplets(rows, seed=1)
    assert len(triplets) == 40 * 6  # every ordered pair of 3 variants, per group
    for group_id, (anchor, positive, negative) in triplets:
        a, p, n = by_text[anchor], by_text[positive], by_text[negative]
        assert a["group_id"] == p["group_id"] == group_id and a["id"] != p["id"]
        assert n["category"] != a["category"] and n["locality"] == a["locality"]


def test_no_batch_contains_two_triplets_from_the_same_group():
    # Two variants of one group in a batch would be scored as negatives of each other.
    triplets = build_triplets(_groups(), seed=1)
    batches = batches_without_repeated_groups(triplets, batch_size=16, seed=3)
    assert sum(len(b) for b in batches) == len(triplets)
    for batch in batches:
        groups = [g for g, _ in batch]
        assert len(groups) == len(set(groups))
