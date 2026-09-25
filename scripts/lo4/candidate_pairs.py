"""LO4: generate issue <-> public-work CANDIDATE pairs for human review.

    python -m scripts.lo4.candidate_pairs

Candidates only - nothing here is a label. Deliberately does NOT use:
  - app/core/matcher.py or any matcher score/threshold,
  - the `matches` table,
  - the synthetic generator's anchor choices as ground truth.

Inputs: data/eval/public_works_master.csv (build it first) and the
`issues`/`reports`/`wards` tables, read in a READ ONLY session.
Output: data/eval/lo4_candidate_examples.csv - a small, deterministic,
stratified sample (<= 20 rows) with an empty `label` column, plus per-
strategy coverage counts over every pair printed to stdout.

Strategies (flags, computed independently per pair):
  A near_location     both sides precisely located, <= 1000 m apart
  B same_ward         issue ward (PMC 2022) == work ward (from geocode only)
  B2 locality_overlap PMC locality words shared by issue text/ward name and work text
  C same_category / related_category (keyword categories on both sides)
  D keyword_overlap   shared content words between issue text and work text
  E completed_before  work completed before the issue was first reported
  F same locality, different category   (derived from B/B2 + not C)
  G same category, different locality   (derived from C + not A/B/B2)
"""
import csv
import math
import re
import sys
from datetime import date
from pathlib import Path

from app.db import get_connection
from app.ingest.synthetic import CATEGORY_TEMPLATES
from scripts.lo4.build_public_works_master import PMC_LOCALITIES

MASTER_CSV = Path("data/eval/public_works_master.csv")
OUTPUT_CSV = Path("data/eval/lo4_candidate_examples.csv")
MAX_EXAMPLES = 20
NEAR_M = 1000
OLD_WORK_DAYS = 365

RELATED_CATEGORIES = {
    frozenset({"pothole_road", "footpath"}),
    frozenset({"drainage_sewage", "water_supply"}),
    frozenset({"pothole_road", "drainage_sewage"}),  # road + drain works are often bundled
}

STOPWORDS = {
    "the", "and", "for", "near", "at", "of", "in", "on", "to", "from", "with", "is", "are",
    "has", "have", "been", "was", "a", "an", "no", "not", "very", "work", "works", "ward",
    "pune", "construction", "laying", "line", "area", "road",  # "road" is in nearly every work
}

OUTPUT_COLUMNS = [
    # LO4 schema
    "pair_id", "issue_text", "issue_category", "issue_location", "work_id",
    "work_description", "work_category", "work_location", "label", "reason", "source",
    # review aids
    "example_bucket", "issue_id", "issue_source", "issue_first_reported", "work_status",
    "work_completion_date", "strategies", "distance_m", "circular_risk", "work_matching_usability",
]

WARD_NUMBER = re.compile(r"ward\s*(?:no\.?|number)?\s*(\d{1,2})", re.I)


def _template_regexes() -> list[re.Pattern]:
    patterns = []
    for templates in CATEGORY_TEMPLATES.values():
        for template in templates:
            escaped = re.escape(template).replace(re.escape("{landmark}"), "(?P<cue>.+?)")
            patterns.append(re.compile(rf"^{escaped}$", re.I))
    return patterns


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in STOPWORDS}


def _localities(text: str) -> set[str]:
    lowered = (text or "").lower()
    return {loc for loc in PMC_LOCALITIES if re.search(rf"\b{re.escape(loc)}\b", lowered)}


def load_issues(conn, templates: list[re.Pattern], mplads_cues: set[str]) -> list[dict]:
    """One row per issue, represented by its earliest member report."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT i.id, i.category, i.ward_id, w.name, i.first_reported,
                   r.raw_text, r.location_phrase, r.geom_confidence,
                   ST_Y(i.geom), ST_X(i.geom)
            FROM issues i
            LEFT JOIN wards w ON w.id = i.ward_id
            JOIN LATERAL (
                SELECT raw_text, location_phrase, geom_confidence
                FROM reports WHERE issue_id = i.id ORDER BY id LIMIT 1
            ) r ON true
            ORDER BY i.id
            """
        )
        rows = cur.fetchall()

    issues = []
    for (issue_id, category, ward_id, ward_name, first_reported, text, phrase,
         geom_conf, lat, lon) in rows:
        cue = None
        for pattern in templates:
            match = pattern.match(text.strip())
            if match:
                cue = match.group("cue")
                break
        if cue is None:
            source = "ui_hand_typed"
        elif cue.lower() in mplads_cues:
            # The generator copied this cue from an MPLADS work description.
            source = "synthetic_cue_copied_from_mplads"
        else:
            source = "synthetic_template"
        issues.append({
            "id": issue_id, "category": category, "ward_id": ward_id,
            "ward_name": ward_name or "", "first_reported": first_reported,
            "text": text, "phrase": phrase or "", "cue": (cue or "").lower(),
            "precise": geom_conf == 1.0, "lat": lat, "lon": lon, "source": source,
            "localities": _localities(text) | _localities(ward_name or ""),
            "words": _words(text),
        })
    return issues


def pair_features(issue: dict, work: dict) -> dict:
    strategies = []
    distance = None
    if issue["precise"] and work["latitude"] and issue["lat"] is not None:
        distance = _haversine_m(issue["lat"], issue["lon"], float(work["latitude"]), float(work["longitude"]))
        if distance <= NEAR_M:
            strategies.append("A_near_location")
    same_ward = bool(work["ward_id"]) and issue["ward_id"] == int(work["ward_id"])
    if same_ward:
        strategies.append("B_same_ward")
    work_localities = set(filter(None, work["pmc_locality_hint"].split("|")))
    locality_overlap = issue["localities"] & work_localities
    if locality_overlap:
        strategies.append("B2_locality_overlap:" + "+".join(sorted(locality_overlap)))

    same_cat = issue["category"] == work["work_category"] and issue["category"] != "other"
    related_cat = frozenset({issue["category"], work["work_category"]}) in RELATED_CATEGORIES
    if same_cat:
        strategies.append("C_same_category")
    elif related_cat:
        strategies.append("C_related_category")

    shared_words = issue["words"] & _words(work["work_description"])
    if shared_words:
        strategies.append("D_keyword_overlap:" + "+".join(sorted(shared_words)[:4]))

    days_after = None
    if work["completion_date"] and issue["first_reported"] is not None:
        days_after = (issue["first_reported"].date() - date.fromisoformat(work["completion_date"])).days
        if days_after >= 0:
            strategies.append(f"E_completed_before_issue:{days_after}d")

    located_together = "A_near_location" in strategies or same_ward or bool(locality_overlap)
    if located_together and not (same_cat or related_cat):
        strategies.append("F_same_locality_diff_category")
    if same_cat and not located_together:
        strategies.append("G_same_category_diff_locality")

    # Ward numbers in synthetic text ("Ward 11") and MPLADS text ("Ward No.11")
    # are NOT a location signal: the schemes differ. Surfaced only as a risk.
    issue_ward_num = WARD_NUMBER.search(issue["text"])
    work_ward_num = WARD_NUMBER.search(work["ward_number_in_text"])
    ward_text_collision = bool(issue_ward_num and work_ward_num) and (
        issue_ward_num.group(1) == work_ward_num.group(1)
    )

    circular = []
    if issue["cue"] and issue["cue"] in work["work_description"].lower():
        circular.append("issue_cue_copied_from_this_work")
    if ward_text_collision:
        circular.append("ward_number_text_collision_unverified_scheme")

    return {
        "strategies": strategies, "distance": distance, "same_cat": same_cat,
        "related_cat": related_cat, "located_together": located_together,
        "days_after": days_after, "circular": circular,
    }


def _bucket(issue: dict, work: dict, f: dict) -> str | None:
    """Why a pair was selected for review - not what its label is."""
    completed = work["status"] == "completed"
    linked = f["same_cat"] or f["related_cat"] or f["located_together"]
    if f["circular"] and linked:
        # Looks like a match only because the synthetic issue reuses this
        # work's own location words - exactly the pair a reviewer must see.
        return "ambiguous_circular"
    if f["circular"]:
        return None
    if issue["category"] == "other" or work["matching_usability"].startswith("review"):
        return "ambiguous_category" if linked else None
    if f["same_cat"] and f["located_together"]:
        if not completed:
            return "ambiguous_not_completed"
        if (f["days_after"] or -1) > OLD_WORK_DAYS:
            return "old_completed_work"
        if (f["days_after"] or -1) >= 0:
            return "likely_match"
        return None
    if f["distance"] is not None and f["distance"] <= NEARBY_UNRELATED_M and not (f["same_cat"] or f["related_cat"]):
        return "nearby_unrelated"
    if f["located_together"] and not (f["same_cat"] or f["related_cat"]):
        return "same_locality_unrelated"
    if f["same_cat"] and completed and (f["days_after"] or -1) > OLD_WORK_DAYS:
        return "old_completed_work"
    if f["same_cat"] and completed:
        return "same_category_diff_location"
    return None


NEARBY_UNRELATED_M = 3000  # wider than strategy A; distance is shown per pair

BUCKET_QUOTA = {
    "likely_match": 4, "same_locality_unrelated": 3, "same_category_diff_location": 3,
    "nearby_unrelated": 2, "old_completed_work": 2, "ambiguous_circular": 3,
    "ambiguous_category": 2, "ambiguous_not_completed": 1,
}


def main() -> None:
    csv.field_size_limit(sys.maxsize)
    with MASTER_CSV.open(newline="") as f:
        works = [w for w in csv.DictReader(f) if not w["matching_usability"].startswith("exclude")]

    mplads_cues = set()
    for w in works:
        for part in w["location_text"].split("; "):
            if part:
                mplads_cues.add(part.lower())
        for m in WARD_NUMBER.finditer(w["work_description"]):
            mplads_cues.add(f"ward {m.group(1)}")

    with get_connection() as conn:
        conn.read_only = True
        issues = load_issues(conn, _template_regexes(), mplads_cues)

    coverage: dict[str, int] = {}
    by_bucket: dict[str, list] = {b: [] for b in BUCKET_QUOTA}
    for issue in issues:
        for work in works:
            f = pair_features(issue, work)
            for s in f["strategies"]:
                key = s.split(":")[0]
                coverage[key] = coverage.get(key, 0) + 1
            bucket = _bucket(issue, work, f)
            if bucket:
                by_bucket[bucket].append((issue, work, f))

    print(f"issues: {len(issues)}  works (non-excluded): {len(works)}  pairs: {len(issues) * len(works)}")
    print("issue sources:", {s: sum(1 for i in issues if i["source"] == s) for s in
                             ("ui_hand_typed", "synthetic_template", "synthetic_cue_copied_from_mplads")})
    print("strategy coverage over all pairs:", dict(sorted(coverage.items())))
    print("bucket sizes:", {b: len(v) for b, v in by_bucket.items()})

    # Deterministic, diverse pick: prefer hand-typed issues, never reuse an
    # issue, an issue text, or a work within the example set.
    source_rank = {"ui_hand_typed": 0, "synthetic_template": 1, "synthetic_cue_copied_from_mplads": 2}
    used_issues, used_texts, used_works, examples = set(), set(), set(), []
    for bucket, quota in BUCKET_QUOTA.items():
        ranked = sorted(by_bucket[bucket], key=lambda t: (
            source_rank[t[0]["source"]], t[0]["id"], t[1]["work_id"]))
        taken = 0
        for issue, work, f in ranked:
            if taken >= quota or len(examples) >= MAX_EXAMPLES:
                break
            text_key = issue["text"].strip().lower()
            if issue["id"] in used_issues or text_key in used_texts or work["work_id"] in used_works:
                continue
            used_issues.add(issue["id"])
            used_texts.add(text_key)
            used_works.add(work["work_id"])
            taken += 1
            examples.append((bucket, issue, work, f))

    with OUTPUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for n, (bucket, issue, work, f) in enumerate(examples, start=1):
            writer.writerow({
                "pair_id": f"LO4-EX-{n:03d}",
                "issue_text": issue["text"],
                "issue_category": issue["category"],
                "issue_location": "; ".join(p for p in (
                    issue["phrase"],
                    f"PMC ward {issue['ward_id']} {issue['ward_name']}" if issue["ward_id"] else "",
                ) if p),
                "work_id": work["work_id"],
                "work_description": work["work_description"],
                "work_category": work["work_category"],
                "work_location": "; ".join(p for p in (
                    work["location_text"],
                    f"geocoded ward {work['ward_id']} (unverified)" if work["ward_id"] else "",
                ) if p),
                "label": "",  # assigned by human review only
                "reason": "",  # reviewer's reason for the label
                "source": f"issue:{issue['source']} | work:{work['source']}",
                "example_bucket": bucket,
                "issue_id": issue["id"],
                "issue_source": issue["source"],
                "issue_first_reported": issue["first_reported"].date().isoformat(),
                "work_status": work["status"],
                "work_completion_date": work["completion_date"],
                "strategies": " | ".join(f["strategies"]),
                "distance_m": f"{f['distance']:.0f}" if f["distance"] is not None else "",
                "circular_risk": " | ".join(f["circular"]),
                "work_matching_usability": work["matching_usability"],
            })
    print(f"wrote {len(examples)} example candidate pairs to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
