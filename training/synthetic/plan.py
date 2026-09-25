"""Row plan for the synthetic Pune complaint dataset.

Every row's labels are fixed here BEFORE any text is written, from exact
quotas, so the category x language mix is guaranteed and the wording can't
drift toward one template. Text is then written per row id (batches/*.tsv)
and merged by assemble.py.

Two outputs, one pass:
  A. plan_complaints.csv - independent complaints, classifier training.
  B. plan_groups.csv     - groups of 3: the same problem at the same place,
     written by different people in different language styles. Used to
     fine-tune the embedding model (romanized Marathi <-> English etc.).

Labels match the human test set (data/labelling/lo2_gold_complaints.csv)
and the app (severity_band enum in schema.sql), so scores are comparable.
All text is synthetic (Claude-written) and labelled so everywhere.

Run: python -m training.synthetic.plan   (deterministic, seed 42)
"""
import csv
import random
from pathlib import Path

OUT_DIR = Path(__file__).parent
SEED = 42

# Language styles. Same values as the human test set.
#   hindi / marathi            Devanagari, the language itself (loanwords ok)
#   romanized_hindi / _marathi Latin script, the language itself
#   hinglish                   Hindi + English phrases mixed, any script
#   marathi_english            Marathi + English phrases mixed, any script
LANGUAGE_SHARE = {
    "english": 0.10, "hindi": 0.13, "marathi": 0.16, "romanized_hindi": 0.12,
    "romanized_marathi": 0.20, "hinglish": 0.15, "marathi_english": 0.14,
}
LATIN_ONLY = {"english", "romanized_hindi", "romanized_marathi"}

# Weighted toward categories iCMyC is short of (traffic_signage 80 rows,
# water_supply 327, drainage_sewage 646).
CATEGORY_QUOTA = {
    "pothole_road": 180, "garbage_waste": 180, "drainage_sewage": 220, "water_supply": 220,
    "streetlight": 190, "footpath": 200, "traffic_signage": 210, "other": 180,
}

# Inside PMC limits only, so the app's ward lookup can resolve them.
LOCALITIES = [
    "Kothrud", "Karve Nagar", "Warje", "Erandwane", "Deccan Gymkhana", "Shivajinagar",
    "Model Colony", "Aundh", "Baner", "Balewadi", "Pashan", "Bavdhan", "Sutarwadi",
    "Sinhagad Road", "Dhayari", "Vadgaon Budruk", "Dhankawadi", "Katraj", "Bibwewadi",
    "Market Yard", "Swargate", "Sadashiv Peth", "Narayan Peth", "Kasba Peth", "Shaniwar Peth",
    "Rasta Peth", "Bhavani Peth", "Camp", "Koregaon Park", "Kalyani Nagar", "Yerawada",
    "Vishrantwadi", "Dhanori", "Lohegaon", "Viman Nagar", "Kharadi", "Wadgaon Sheri",
    "Chandannagar", "Hadapsar", "Magarpatta", "Mundhwa", "Fursungi", "Undri", "Kondhwa",
    "NIBM Road", "Wanowrie", "Salunke Vihar", "Ghorpadi", "Gokhale Nagar", "Senapati Bapat Road",
    "FC Road", "JM Road", "Parvati", "Sahakar Nagar", "Ganesh Peth", "Tilak Road",
]

# (scenario, severity). Severity follows the scenario, not a coin flip.
SCENARIOS = {
    "pothole_road": [
        ("deep_potholes_main_road", "critical"), ("potholes_after_rain", "moderate"),
        ("road_dug_not_restored", "moderate"), ("patch_work_failed_again", "moderate"),
        ("loose_gravel_bikes_skid", "critical"), ("road_caved_in", "critical"),
        ("potholes_near_school", "critical"), ("unpaved_mud_road_new_colony", "moderate"),
        ("small_cracks_surface", "cosmetic"), ("water_filled_potholes", "moderate"),
        ("metro_work_damaged_road", "moderate"), ("service_road_broken", "moderate"),
        ("uneven_road_after_resurfacing", "cosmetic"), ("pothole_at_turn_accident_risk", "critical"),
    ],
    "drainage_sewage": [
        ("sewage_overflow_on_road", "moderate"), ("open_manhole", "critical"),
        ("broken_manhole_cover", "critical"), ("blocked_drain_waterlogging", "moderate"),
        ("nala_choked", "moderate"), ("chamber_smell", "moderate"),
        ("sewage_into_houses", "critical"), ("storm_drain_cover_missing", "critical"),
        ("stagnant_drain_mosquitoes", "moderate"), ("drain_not_cleaned_before_monsoon", "moderate"),
        ("chamber_overflows_every_morning", "moderate"), ("backflow_in_bathroom", "moderate"),
        ("drain_slab_sunk", "cosmetic"), ("sewage_line_leak_near_society_gate", "moderate"),
    ],
    "water_supply": [
        ("no_water_for_days", "critical"), ("low_pressure", "moderate"),
        ("dirty_yellow_tap_water", "critical"), ("timing_changed_no_notice", "moderate"),
        ("supply_only_late_night", "moderate"), ("pipeline_burst_on_road", "moderate"),
        ("main_line_leakage", "moderate"), ("society_depends_on_tanker", "moderate"),
        ("smell_in_drinking_water", "critical"), ("supply_only_short_time", "moderate"),
        ("valve_not_opened", "moderate"), ("upper_floors_no_water", "moderate"),
        ("public_tap_left_running", "cosmetic"), ("alternate_day_supply_missed", "moderate"),
    ],
    "streetlight": [
        ("whole_lane_dark", "moderate"), ("light_flickering", "cosmetic"),
        ("dark_near_bus_stop_unsafe", "moderate"), ("lights_on_during_day", "cosmetic"),
        ("pole_leaning", "critical"), ("exposed_wires_at_pole", "critical"),
        ("dark_stretch_near_park", "moderate"), ("only_few_lights_working", "moderate"),
        ("lights_switch_off_midnight", "moderate"), ("light_hidden_by_branches", "cosmetic"),
        ("new_road_no_lights", "moderate"), ("lamp_broken", "moderate"),
        ("dark_underpass", "moderate"),
    ],
    "garbage_waste": [
        ("garbage_not_collected_days", "moderate"), ("bin_overflowing", "moderate"),
        ("dumping_in_open_plot", "moderate"), ("burning_garbage_smoke", "moderate"),
        ("collection_vehicle_not_coming", "moderate"), ("dogs_tearing_bags_smell", "moderate"),
        ("construction_debris_dumped", "moderate"), ("garbage_near_school", "critical"),
        ("collectors_refuse_unsegregated", "cosmetic"), ("street_not_swept", "cosmetic"),
        ("market_waste_left_after_bazaar", "moderate"), ("garbage_pile_at_corner", "moderate"),
        ("hotel_waste_dumped_at_night", "moderate"),
    ],
    "footpath": [
        ("broken_paver_blocks", "moderate"), ("hawkers_on_footpath", "moderate"),
        ("bikes_parked_on_footpath", "moderate"), ("no_footpath_walk_on_road", "moderate"),
        ("footpath_dug_and_left", "moderate"), ("footpath_too_high_for_seniors", "cosmetic"),
        ("footpath_blocked_by_shop_extension", "moderate"), ("not_wheelchair_accessible", "moderate"),
        ("construction_material_on_footpath", "moderate"), ("tree_roots_broke_footpath", "cosmetic"),
        ("footpath_ends_suddenly", "moderate"), ("slippery_tiles", "moderate"),
    ],
    "traffic_signage": [
        ("signal_not_working", "critical"), ("zebra_crossing_faded", "moderate"),
        ("sign_board_missing", "cosmetic"), ("no_speed_breaker_near_school", "critical"),
        ("sign_hidden_by_tree_or_hoarding", "cosmetic"), ("lane_markings_faded", "moderate"),
        ("confusing_direction_board", "cosmetic"), ("pedestrian_signal_too_short", "moderate"),
        ("pedestrian_signal_broken", "moderate"), ("blinking_yellow_all_night", "moderate"),
        ("speed_breaker_unpainted", "critical"), ("road_name_board_missing", "cosmetic"),
        ("one_way_board_missing", "moderate"),
    ],
    "other": [
        ("stray_dogs", "moderate"), ("loud_music_noise", "cosmetic"),
        ("fallen_tree_branch", "moderate"), ("illegal_construction", "moderate"),
        ("mosquito_fogging_needed", "moderate"), ("public_toilet_dirty", "moderate"),
        ("home_power_cut_msedcl", "moderate"), ("dead_animal_on_road", "moderate"),
        ("encroachment_open_space", "cosmetic"), ("broken_park_equipment", "cosmetic"),
        ("stray_cattle_on_road", "moderate"), ("illegal_hoardings", "cosmetic"),
    ],
}

# Plausible co-occurring second problem, for multi-issue rows.
SECONDARY = {
    "pothole_road": ["footpath", "streetlight", "drainage_sewage"],
    "drainage_sewage": ["garbage_waste", "water_supply", "pothole_road"],
    "water_supply": ["drainage_sewage", "pothole_road"],
    "streetlight": ["traffic_signage", "footpath", "other"],
    "garbage_waste": ["drainage_sewage", "footpath", "other"],
    "footpath": ["pothole_road", "traffic_signage", "garbage_waste"],
    "traffic_signage": ["streetlight", "footpath", "pothole_road"],
    "other": ["garbage_waste", "streetlight"],
}

# Confusable neighbour, named in hard_boundary rows so the text shares its words.
BOUNDARY = {
    "pothole_road": "footpath", "footpath": "pothole_road", "drainage_sewage": "water_supply",
    "water_supply": "drainage_sewage", "streetlight": "traffic_signage",
    "traffic_signage": "streetlight", "garbage_waste": "drainage_sewage", "other": "streetlight",
}

TONES = ["polite", "frustrated", "angry", "sarcastic", "matter_of_fact", "worried", "pleading", "tired"]
VOICES = ["resident", "shopkeeper", "parent", "senior_citizen", "commuter", "student",
          "society_secretary", "office_goer", "two_wheeler_rider", "auto_driver", "woman_walking_alone",
          "delivery_rider"]
LENGTHS = ["short"] * 3 + ["medium"] * 5 + ["long"] * 2

GROUP_COUNT = 400  # x 3 variants
GROUP_STYLE_WEIGHT = {
    "romanized_marathi": 5, "english": 4, "marathi": 3, "romanized_hindi": 3,
    "hinglish": 3, "hindi": 2, "marathi_english": 2,
}


def _split(total: int, shares: dict[str, float]) -> dict[str, int]:
    """Largest-remainder split so the counts add up exactly."""
    raw = {k: total * v for k, v in shares.items()}
    counts = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - counts[k], reverse=True)[: total - sum(counts.values())]:
        counts[k] += 1
    return counts


def _script_hint(language: str, rng: random.Random) -> str:
    if language in LATIN_ONLY:
        return "latin"
    if language in ("hindi", "marathi"):
        return "devanagari"
    return rng.choice(["latin", "latin", "mixed"])  # code-mixed: mostly typed in Latin


def plan_complaints(rng: random.Random) -> list[dict]:
    rows = []
    for category, quota in CATEGORY_QUOTA.items():
        languages = [lang for lang, n in _split(quota, LANGUAGE_SHARE).items() for _ in range(n)]
        rng.shuffle(languages)
        scenarios = SCENARIOS[category]
        for i, language in enumerate(languages):
            scenario, severity = scenarios[i % len(scenarios)]
            roll = rng.random()
            if roll < 0.10:
                difficulty = "multi_issue"
            elif roll < 0.18:
                difficulty = "hard_boundary"
            elif roll < 0.23:
                difficulty = "hard_vague"
            elif roll < 0.31 and language not in ("hindi", "marathi"):
                difficulty = "hard_spelling"  # typos are a typed-Latin phenomenon
            else:
                difficulty = "normal"
            rows.append({
                "category": category,
                "secondary_category": rng.choice(SECONDARY[category]) if difficulty == "multi_issue" else "",
                "severity": severity,
                "language": language,
                "script_hint": _script_hint(language, rng),
                "locality": "" if rng.random() < 0.15 else rng.choice(LOCALITIES),
                "scenario": scenario,
                "difficulty": difficulty,
                "boundary_with": BOUNDARY[category] if difficulty == "hard_boundary" else "",
                "length": "short" if difficulty == "hard_vague" else rng.choice(LENGTHS),
                "tone": rng.choice(TONES),
                "voice": rng.choice(VOICES),
            })
    rng.shuffle(rows)  # batches mix categories and languages
    for n, row in enumerate(rows, 1):
        row["id"] = f"SYN-C-{n:04d}"
    return rows


def plan_groups(rng: random.Random) -> list[dict]:
    categories = [c for c in CATEGORY_QUOTA for _ in range(GROUP_COUNT // len(CATEGORY_QUOTA))]
    rng.shuffle(categories)
    styles, weights = list(GROUP_STYLE_WEIGHT), list(GROUP_STYLE_WEIGHT.values())
    rows = []
    for g, category in enumerate(categories, 1):
        scenario, severity = rng.choice(SCENARIOS[category])
        locality = rng.choice(LOCALITIES)
        chosen: list[str] = []
        while len(chosen) < 3:
            style = rng.choices(styles, weights)[0]
            if style not in chosen:
                chosen.append(style)
        voices = rng.sample(VOICES, 3)
        for v, (language, voice) in enumerate(zip(chosen, voices)):
            rows.append({
                "id": f"SYN-G-{g:03d}-{'abc'[v]}", "group_id": f"SYN-G-{g:03d}",
                "category": category, "severity": severity, "language": language,
                "script_hint": _script_hint(language, rng), "locality": locality,
                "scenario": scenario, "length": rng.choice(LENGTHS),
                "tone": rng.choice(TONES), "voice": voice,
            })
    return rows


def _write(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    rng = random.Random(SEED)
    complaints, groups = plan_complaints(rng), plan_groups(rng)
    _write(OUT_DIR / "plan_complaints.csv", complaints)
    _write(OUT_DIR / "plan_groups.csv", groups)
    print(len(complaints), "complaint rows,", len(groups), "group rows")
