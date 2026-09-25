import random
from datetime import datetime, timedelta

from app.db import get_connection
from app.ingest.location import extract_landmark_phrase
from app.nlp.classify import classify
from app.nlp.embeddings import get_embedding_model as _get_embedding_model
from app.nlp.location import resolve_report_location
from app.nlp.severity import severity

CATEGORY_TEMPLATES = {
    "pothole_road": [
        "Big pothole near {landmark}, almost hit it on my scooter",
        "Road near {landmark} has huge craters, please fix urgently",
        "The road at {landmark} has been damaged for weeks now",
        "Deep pothole opened up near {landmark} after the rain",
    ],
    "drainage_sewage": [
        "Sewage overflowing near {landmark} again, terrible smell",
        "Open drain near {landmark} is a real hazard for kids",
        "Drainage blocked near {landmark}, water logging every time it rains",
        "Manhole near {landmark} has been open for days, very dangerous",
    ],
    "water_supply": [
        "No water supply near {landmark} for three days now",
        "Water pressure very low near {landmark} every morning",
        "Water tanker hasn't come to {landmark} this week",
    ],
    "streetlight": [
        "Streetlight near {landmark} not working for a week",
        "Completely dark near {landmark} at night, streetlight broken",
        "Several lamp posts near {landmark} have stopped working",
    ],
    "garbage_waste": [
        "Garbage not collected near {landmark} for many days",
        "Overflowing dustbin near {landmark}, foul smell everywhere",
        "Waste piling up near {landmark}, nobody has come to clear it",
    ],
    "footpath": [
        "Footpath near {landmark} is broken and unusable",
        "No proper footpath near {landmark}, pedestrians forced onto the road",
        "Footpath tiles near {landmark} are uneven and cracked",
    ],
    "traffic_signage": [
        "Traffic signal near {landmark} not working, causing jams",
        "Missing speed breaker near {landmark}, vehicles go too fast",
        "No zebra crossing near {landmark}, hard to cross safely",
    ],
    "other": [
        "Loud construction noise near {landmark} early in the morning",
        "Stray dogs near {landmark} have been chasing people",
        "Illegal parking near {landmark} blocking the road",
        "Unauthorized hawkers near {landmark} blocking the footpath",
    ],
}

ORDINARY_CATEGORY_WEIGHTS = {
    "pothole_road": 20,
    "garbage_waste": 18,
    "drainage_sewage": 14,
    "water_supply": 12,
    "footpath": 10,
    "streetlight": 12,
    "traffic_signage": 8,
    "other": 6,
}



def _anchor_location_cue(description: str, ward_id: int | None = None) -> str | None:
    """How a citizen would point at the anchor work, so the report pipeline
    resolves the complaint there independently - not by injecting a coordinate.

    Uses the work's own resolved 2022 ward ("Ward N" in a complaint means 2022
    ward N to app/nlp/location.py), else a landmark from its description. Never
    the raw "Ward No." in MPLADS text: those numbers mix old/new/PCMC schemes
    (see app/ingest/mplads.py), so they'd send the complaint to the wrong ward.
    """
    if ward_id is not None:
        return f"Ward {ward_id}"
    return extract_landmark_phrase(description)


def render_complaint(template: str, cue: str) -> str:
    return template.format(landmark=cue)


def _pick_reported_at(rng: random.Random, now: datetime | None = None, days_back: int = 120) -> datetime:
    now = now or datetime.now()
    offset_seconds = rng.uniform(0, days_back * 86400)
    return now - timedelta(seconds=offset_seconds)


def fetch_anchors(conn) -> list[dict]:
    """Real works the matcher can actually link (completed, dated, located,
    not 'other' - the same gates as app/core/matcher.py - and inside a PMC ward) are the only
    legitimate anchors for synthetic complaints meant to be findable.
    Nothing is forced: the matcher still has to discover each link.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT category, ward_id, ST_Y(geom), ST_X(geom), description "
            "FROM works WHERE geom IS NOT NULL AND category != 'other' "
            "AND status = 'completed' AND completed_on IS NOT NULL "
            "AND ward_id IS NOT NULL"  # inside a PMC ward: the demo is PMC Pune, not PCMC/rural
        )
        rows = cur.fetchall()

    anchors = []
    for category, ward_id, lat, lon, description in rows:
        cue = _anchor_location_cue(description, ward_id)
        if cue is None:
            continue
        anchors.append({
            "category": category,
            "ward_id": ward_id,
            "lat": lat,
            "lon": lon,
            "cue": cue,
        })
    return anchors


def _fetch_ward_ids(conn) -> list[int]:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM wards ORDER BY id")
        return [row[0] for row in cur.fetchall()]


def _build_specs(rng: random.Random, anchors: list[dict], ward_ids: list[int], n: int) -> list[dict]:
    """Returns a list of {category, cue} dicts describing each complaint to
    generate, without touching the DB or the NLP pipeline yet.
    """
    specs = []

    if anchors:
        n_anchor = round(n * 0.4)
        # One anchor gets a heavier share, to produce a genuinely recurring
        # issue (DEMO.md wants "reported 14 times") rather than uniform noise.
        weights = [1] * len(anchors)
        weights[0] = 3
        chosen_anchors = rng.choices(anchors, weights=weights, k=n_anchor)
        for anchor in chosen_anchors:
            specs.append({"category": anchor["category"], "cue": anchor["cue"]})
    else:
        n_anchor = 0

    remaining = n - n_anchor
    n_ordinary = round(remaining * 0.6)
    n_singleton = remaining - n_ordinary

    # Ordinary hotspots: a curated (ward, category) pair repeated a few
    # times each, so clustering/recurrence has real repeated-nearby cases
    # to work with beyond just the anchor points.
    hotspot_pool = []
    if ward_ids:
        n_hotspots = max(1, remaining // 6)
        for _ in range(n_hotspots):
            hotspot_pool.append({
                "ward_id": rng.choice(ward_ids),
                "category": rng.choices(
                    list(ORDINARY_CATEGORY_WEIGHTS), weights=list(ORDINARY_CATEGORY_WEIGHTS.values())
                )[0],
            })

    for _ in range(n_ordinary):
        if not hotspot_pool:
            break
        hotspot = rng.choice(hotspot_pool)
        specs.append({"category": hotspot["category"], "cue": f"Ward {hotspot['ward_id']}"})

    for _ in range(n_singleton):
        category = rng.choices(
            list(ORDINARY_CATEGORY_WEIGHTS), weights=list(ORDINARY_CATEGORY_WEIGHTS.values())
        )[0]
        cue = f"Ward {rng.choice(ward_ids)}" if ward_ids else "Pune"
        specs.append({"category": category, "cue": cue})

    # Rounding can leave us short/over by a couple - top up or trim so the
    # caller gets exactly n rows.
    while len(specs) < n:
        category = rng.choices(
            list(ORDINARY_CATEGORY_WEIGHTS), weights=list(ORDINARY_CATEGORY_WEIGHTS.values())
        )[0]
        cue = f"Ward {rng.choice(ward_ids)}" if ward_ids else "Pune"
        specs.append({"category": category, "cue": cue})
    del specs[n:]

    return specs


def generate_synthetic_reports(n: int = 400, seed: int = 42, conn=None) -> int:
    """Generates ~n synthetic Pune complaints and inserts them into
    `reports`, all labelled is_synthetic=true. A meaningful share is seeded
    around real, resolved, non-'other' MPLADS works (the only legitimate
    anchors - never fabricated), using the same location cue the anchor
    work itself resolved with, so the report pipeline (classify, resolve
    location, severity) discovers the match independently rather than
    having it injected. The rest are ordinary/singleton complaints spread
    across real wards, including deliberately non-matching 'other' noise.
    """
    rng = random.Random(seed)
    owns_conn = conn is None
    conn = conn or get_connection()
    try:
        anchors = fetch_anchors(conn)
        ward_ids = _fetch_ward_ids(conn)
        specs = _build_specs(rng, anchors, ward_ids, n)

        raw_texts = []
        for spec in specs:
            template = rng.choice(CATEGORY_TEMPLATES[spec["category"]])
            raw_texts.append(render_complaint(template, spec["cue"]))

        embeddings = _get_embedding_model().encode(raw_texts, batch_size=64, show_progress_bar=False)
        now = datetime.now()

        rows = []
        for text, embedding in zip(raw_texts, embeddings):
            category, category_conf = classify(text)
            severity_band = severity(text, category)
            lat, lon, geom_conf, ward_id, location_phrase = resolve_report_location(text, conn=conn)
            reported_at = _pick_reported_at(rng, now=now)
            rows.append((
                text, reported_at, category, category_conf, severity_band,
                location_phrase, lat, lon, geom_conf, ward_id, embedding,
            ))

        with conn.cursor() as cur:
            for (text, reported_at, category, category_conf, severity_band,
                 location_phrase, lat, lon, geom_conf, ward_id, embedding) in rows:
                geom_expr = "ST_SetSRID(ST_MakePoint(%s, %s), 4326)" if lat is not None else "NULL"
                geom_params = (lon, lat) if lat is not None else ()
                embedding_literal = "[" + ",".join(str(float(v)) for v in embedding) + "]"
                cur.execute(
                    f"""
                    INSERT INTO reports (
                        raw_text, reported_at, category, category_conf, severity,
                        location_phrase, geom, geom_confidence, ward_id, embedding,
                        is_synthetic
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, {geom_expr}, %s, %s, %s::vector, true
                    )
                    """,
                    (
                        text, reported_at, category, category_conf, severity_band,
                        location_phrase, *geom_params, geom_conf, ward_id, embedding_literal,
                    ),
                )
        conn.commit()

        return len(rows)
    finally:
        if owns_conn:
            conn.close()
