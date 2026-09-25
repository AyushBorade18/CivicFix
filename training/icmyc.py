"""iCMyC (I Change My City, 2019-2022) -> classifier training rows.

This is BENGALURU data (BBMP, BWSSB, BESCOM agencies), used only as
auxiliary Indian civic-complaint English. It is never Pune data and must
never be presented as such. Every output row carries source=icmyc_bengaluru.

Mapping is by the portal's own sub-category, onto our 8 categories.
Sub-categories that could honestly be two of ours (e.g. road flooding:
pothole_road or drainage_sewage?) or are unknown ("Others") are dropped,
not guessed. Class balance is left to the training step.

Run: python -m training.icmyc  (reads ~/civicfix-data/raw/icmyc_complaints.csv)
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

SOURCE_CSV = Path.home() / "civicfix-data/raw/icmyc_complaints.csv"
OUTPUT_CSV = Path(__file__).parent / "icmyc_mapped.csv"
MAX_CHARS = 600

# Exact sub_category_title -> our category. Checked against all 220 values.
SUBCATEGORY_MAP = {
    # pothole_road
    "Fixing/Reparing Potholes": "pothole_road",
    "Tarring Or Asphalting Of Existing Road": "pothole_road",
    "Tarring Or Asphalting Of Mud/Kutcha/Unpaved Road": "pothole_road",
    "Repair of Potholes on Roads": "pothole_road",
    # drainage_sewage
    "Construction Of Roadside Drains": "drainage_sewage",
    "Desilting Existing Roadside Drains": "drainage_sewage",
    "Need Covering Slabs For Roadside Drains": "drainage_sewage",
    "Open Manholes Or Drains": "drainage_sewage",
    "Maintanence of sewage lines": "drainage_sewage",
    "Construction of sewage lines": "drainage_sewage",
    "Repair  of broken storm water drains": "drainage_sewage",
    "Construction of storm water drains": "drainage_sewage",
    "Desilting of Storm water Drains": "drainage_sewage",
    "Maintenance And Repair Of Sewage Lines": "drainage_sewage",
    "Sewarage Or Storm Water Overflow": "drainage_sewage",
    "Maintenance And Repair Of Manholes": "drainage_sewage",
    "Construction of Sewage Lines": "drainage_sewage",
    "Removal Of Sewer Pipe Blockages and Overflows": "drainage_sewage",
    "Cleaning Of Drain": "drainage_sewage",
    "Maintenance And Repair Of Storm Water Drains": "drainage_sewage",
    "Desilting/Remove Blockage of Storm Water Drains": "drainage_sewage",
    "Improper Disposal Of Feacal Waste Or  Septage": "drainage_sewage",
    # water_supply
    "Regular Water Supply": "water_supply",
    "Stop Water Leakage": "water_supply",
    "Maintenance Of Existing Water Pipeline": "water_supply",
    "Provision for a New Water Pipeline": "water_supply",
    "Reduce water leakage and wastage": "water_supply",
    "Maintain regular water supply": "water_supply",
    "Regular supply of water": "water_supply",
    "Maintenance Of Existing Water Tank": "water_supply",
    # streetlight
    "Maintenance/Repair Of Streetlights": "streetlight",
    "Installation Of New Streetlights": "streetlight",
    "Installation/Maintenance Of Streetlight Timer": "streetlight",
    "Repair of  mast light at a busy road (main road) junction": "streetlight",
    # garbage_waste
    "Clearance Of Garbage Dump Or Black Spot": "garbage_waste",
    "Collection Of Door-to-door Garbage": "garbage_waste",
    "Garbage Dumping In Vacant Lot/Land": "garbage_waste",
    "Stop/Prevent Burning Of Garbage": "garbage_waste",
    "Burning of garbage in open space": "garbage_waste",
    "Regular Sweeping Of Streets": "garbage_waste",
    "Sweeping Not Done": "garbage_waste",
    "Clearing Of Roadside Dustbin": "garbage_waste",
    "Dustbins not cleared": "garbage_waste",
    "Cleaning of litter bins": "garbage_waste",
    "Garbage Dump": "garbage_waste",
    "Garbage dump": "garbage_waste",
    "Wet Waste Vehicle Not Arrived": "garbage_waste",
    "Garbage vehicle not arrived": "garbage_waste",
    "Removal Of Roadside Debris (Construction Material)": "garbage_waste",
    "Debris removal or construction material": "garbage_waste",
    "Report Garbage or Debris on Footpath": "garbage_waste",
    "2C- Remove Garbage or Debris on Footpath": "garbage_waste",
    # footpath (hawkers/parking on footpath -> footpath, per the labelling guide)
    "Construction of new footpaths": "footpath",
    "Repair Of Existing Footpaths": "footpath",
    "Build new footpaths and repair broken footpaths": "footpath",
    "Report A Broken Footpath": "footpath",
    "Require A New Footpath": "footpath",
    "2A- Require New Footpath": "footpath",
    "2B- Repair Broken Footpath": "footpath",
    "Management Of Hawkers and Vendors": "footpath",
    "Parking On Footpath": "footpath",
    # traffic_signage
    "Need Lane Markings/Street Name/Road Signages": "traffic_signage",
    "Maintenance/Repair Of Traffic or Pedestrain Lights": "traffic_signage",
    "Installation Of Traffic Sign Boards": "traffic_signage",
    "Installation Of Traffic or Pedestrain Lights": "traffic_signage",
    "Repair of pedestrian lights": "traffic_signage",
    "Installation of traffic lights": "traffic_signage",
}

# Whole portal categories that are real civic complaints outside our 8.
OTHER_CATEGORIES = {
    "Animal Husbandry", "Animal Catcher", "Crime and Safety", "Safety and Crime",
    "Trees and Saplings", "Parks & Recreation", "Parks & Garden", "Playgrounds",
    "Public Toilets", "Electricity and Power Supply", "Electricity & Power", "Power supply",
    "Lakes", "Public Transport - BMTC", "Public transport (BMTC and Metro)",
}
OTHER_SUBCATEGORIES = {
    "Noise Pollution", "Air Pollution", "Fogging (Mosquito Menace) Or Pest Control",
    "Report A Public Urination or Yellow Spot", "1A- Address Public Urination or Yellow Spots",
    "Require A New Public Toilet", "1B- Require New Public Toilet",
    "Report A Dirty or Unusable Public Toilet", "Report A Dirty or Unusable Mobile Public Toilet",
    "1C- Repair Dirty or Unusable Public Toilet",
    "Government Land/Property Encroachment", "Stop Unauthorised Construction",
    # Traffic behaviour, not signage
    "Traffic Jams/Congestion Or Bottlenecks", "Riding Without A Helmet", "No Parking",
    "Wrong Parking", "Wrong parking", "Autorickshaws Meter Issues", "Riding On Footpath",
    "One Way/No Entry", "Pillion Rider Not Wearing Helmet", "Using Mobile Phone",
    "Defective/Fancy Number Plate", "Triple Riding", "Stopped on Zebra Cross",
    "Jumping Traffic Signal", "Violating lane discipline",
    "Taking a U-turn where U-turn is prohibited", "Stunt Riding", "Not wearing seat belt",
}


def map_category(category_title: str, sub_category_title: str) -> str | None:
    """Our category, or None to drop the row (ambiguous or unknown)."""
    if sub_category_title in SUBCATEGORY_MAP:
        return SUBCATEGORY_MAP[sub_category_title]
    if sub_category_title in OTHER_SUBCATEGORIES or category_title in OTHER_CATEGORIES:
        return "other"
    return None


_EMAIL = re.compile(r"\S+@\S+\.\w+")
_PHONE = re.compile(r"(?:\+?91[\s-]?)?\d{5}[\s-]?\d{5}\b")
_LONG_NUMBER = re.compile(r"\d{6,}")
_TITLED_NAME = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Shri|Smt)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?")
# A sign-off word near the end takes the rest of the text with it (usually a
# name, often a phone). "in regards to ..." is ordinary prose, not a sign-off.
_SIGNOFF = re.compile(
    r"[\s,]*\b(?i:regards|thanks|thank you|thanking you|yours (?:sincerely|faithfully|truly))\b"
    r"(?!\s+to\b)(?s:.{0,250})$"
)


def mask_pii(text: str) -> str:
    # ponytail: regex masking catches phones/emails/numbers/titled names/sign-offs,
    # not bare names mid-sentence; fine for auxiliary training text, not for publishing.
    text = _EMAIL.sub("[EMAIL]", text)
    text = _PHONE.sub("[PHONE]", text)
    text = _LONG_NUMBER.sub("[NUMBER]", text)
    text = _TITLED_NAME.sub("[NAME]", text)
    return _SIGNOFF.sub("", text).strip()


def build_text(title: str, description: str, sub_category_title: str) -> str:
    """Description, with the title in front only when it adds something.
    A title equal to the sub-category would leak the label."""
    title, description = title.strip(), description.strip()
    stem = title.rstrip(".").rstrip()
    if (not title or title.lower() == sub_category_title.strip().lower()
            or description.lower().startswith(stem.lower())):
        return description
    return f"{title}. {description}"


def build(source: Path = SOURCE_CSV, output: Path = OUTPUT_CSV) -> Counter:
    csv.field_size_limit(sys.maxsize)
    seen, counts = set(), Counter()
    with open(source, newline="") as f_in, open(output, "w", newline="") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(["source_id", "text", "category", "source", "orig_category", "orig_subcategory"])
        for row in csv.DictReader(f_in):
            category = map_category(row["category_title"], row["sub_category_title"])
            if category is None:
                counts["dropped_unmapped"] += 1
                continue
            text = mask_pii(build_text(row["title"], row["description"], row["sub_category_title"]))
            text = " ".join(text.split())[:MAX_CHARS]
            if len(text) < 15 or text.lower() in seen:
                counts["dropped_short_or_duplicate"] += 1
                continue
            seen.add(text.lower())
            writer.writerow([row["_id"], text, category, "icmyc_bengaluru",
                             row["category_title"], row["sub_category_title"]])
            counts[category] += 1
    return counts


if __name__ == "__main__":
    for key, n in sorted(build().items(), key=lambda kv: -kv[1]):
        print(f"{n:6}  {key}")
