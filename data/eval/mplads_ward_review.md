# MPLADS ward-number review

Data review only. No code, database or production data changed. This is
**not** a crosswalk. Row-level detail is in `mplads_ward_review.csv`.

## Scope and sources

- **Records:** every Pune-filtered MPLADS record (same `ida`/`constituency`
  "pune" filter as `app/ingest/mplads.py`, 318 rows) whose `workDescription`
  mentions "ward", "prabhag" or "Sub.Div". That is **67 records**. The
  original text is copied verbatim into `original_location_text`.
- **41-prabhag list:** `Pune - Zone-wise Public Toilets Data.csv` from
  `~/Downloads/L08.zip` (sha256 `7f0824ae…0bafd`). **L08 is not in the
  project repo.** The file lists Ward No. 1–41 with Zone Name and Ward Name,
  plus one composite row `42(12,7,10,8,9)`. It carries no year or source. It
  is treated as an older PMC prabhag scheme **because its names fit**, not
  because the file says so.
- **76-prabhag list:** `PMC.zip` → `Road/Footpath Details.xlsx` (Prabhag_no 1–76).
- **2022 wards:** `data/wards/pune-2022-wards.geojson` and `ward-attributes.csv` (58).
- **Geocodes:** existing `data/cache/geocode_cache.json` only. No new geocoding.

## How to read the CSV

- `candidate_41_prabhag` / `prabhag_name`: the 41-scheme prabhag with the same number, shown for comparison.
- `prabhag_agreement`: does the **named locality** fit that prabhag?
  - `yes`: fits
  - `no`: the locality belongs elsewhere
  - `ambiguous`: can't test, or it conflicts
  - `not_found`: no PMC scheme applies (PCMC, Daund, Nira)
- `confidence` rates **the 41-prabhag judgement**, not the 2022 ward.
- `candidate_2022_ward` is filled only where the locality name appears in
  exactly one 2022 ward name, or where a cached geocode supports it. Every
  one of these is a **ward-name match**. None is a geometric verification.
  **The MPLADS number itself was never used to pick a 2022 ward.**

## Counts (67 reviewed)

| Result | Count |
|---|---|
| Clear 41-prabhag alignment (`yes`, high) | **9** |
| Probable alignment (`yes`, medium) | **16**, mostly zone-level only: Kothrud localities vs the Kothrud Bavdhan zone (prabhags 10–12) |
| Weak alignment (`yes`, low: relies on general knowledge or on other records) | **6** |
| Ambiguous | **6** |
| No alignment (`no`) | **6** |
| No PMC scheme applies (`not_found`) | **24**: 22 PCMC, 1 Daund Municipal Council, 1 Nira |
| Defensible PMC 2022 ward | **0 verified. 1 probable** (192199 → 30: "Kelewadi" is in ward 30's name and the cached Kelewadi point falls in ward 30). **10 more are name-level only** (13 ×4, 34 ×3, 9, 11, 16) and need checking against the polygons. |

So of the 43 records inside PMC: 31 agree with the 41-prabhag scheme to some
degree, 6 disagree and 6 are ambiguous.

## Key evidence

- **169582** says "New Ward No 36, **Old Ward No 13**", Sahakar Udyan
  Erandvana. 41-prabhag 13 is Erandawana-Happy Colony. This is the strongest
  single piece of evidence that MPLADS "old" numbers use the 41 scheme. The
  "new" 36 matches neither 2022 ward 36 (Karvenagar) nor 76-scheme 36, so the
  "new" scheme is unidentified.
- **Ward 11 + Kothrud / Sutardara / Kishkindhanagar:** 41-prabhag 11 (Rambaugh
  Colony-Shivtirth Nagar) is in zone Kothrud Bavdhan. The 76-scheme lists
  "Sutardara - Kishkindha Nagar" as prabhag **27**, so it isn't the 76-scheme.
  2022 ward 11 is Bopodi-SPPU, so it isn't 2022 either. The fit is at zone
  level only, because the 41 list has names but no boundaries.
- **Ward 9 + Baner, Ward 32 + Warje Malwadi, Ward 6 + Yerawada:** the locality
  is in the 41-prabhag name. Ward 9 Baner also fits 76-scheme 9 (Baner
  Balewadi), so those records alone don't separate the 41 and 76 schemes.

## Important conflicts

- **SB Road / NCC:** 202716–202718 ("Ward No. 16 … NCC Headquarters, SB
  Road") vs 234314 ("SB Road … NCC Branch at Ward No. 14"). Same road, two
  numbers. 14 fits 41-prabhag 14 (Deccan Gymkhana-Model Colony) on general
  knowledge; 16 fits neither the 41 scheme (Kasba Peth-Somwarpeth) nor the
  76 scheme. The records appear to mix schemes.
- **249736** "Ward 11 … Dahanukar Colony, Kothrud": Dahanukar Colony is named
  in 41-prabhag **12**, not 11.
- **250707** "Ward number 12 … Modern High School, Pune University": Pune
  University is 41-prabhag **7** and 76-scheme 7, not 12.
- **275395** "Hadapsar Ward No. 37": 41-prabhag 37 is Upper Indra Nagar
  (Bibwewadi zone), 76-scheme 37 is Shaniwarwada, and 2022 ward 37 is Janata
  Vasahat-Dattawadi. No scheme fits.
- **192204** "Sub.Div.No.3 Office … Shivkirti Ghorpadi ward no.20": Ghorpadi
  is in 41-prabhag **21**. "Sub.Div.No.3" suggests another body's numbering.
- **304483** (PCMC, Kalewadi Prabhag 22): the existing geocode cache puts
  "Indian Colony, Pune" inside PMC 2022 ward 11, which is a wrong geocode.

## Important ambiguous cases

- **Ward 12 batch** (249742 SNDT College, 250708 Sakal Nagar, 250707 Pune
  University): the same number is used for places that don't obviously share
  a prabhag.
- **250737** Kalmkar Vasti and **250717** Rajyog Society ("Ward 9"): the
  localities aren't in any reference file.
- **241217** "Kharadi, Prabhag No. 4" and **246089** "Kondhwa Ward No. 41":
  both numbers also match the 2022 scheme's numbering and names, so these
  records can't tell the schemes apart.
- **192201** "Sub.Div.No.3 Office. Ward no 20": no locality at all.

## Can CivicFix safely use MPLADS ward numbers to automatically assign a PMC 2022 ward?

**No.** Based on the 67 records reviewed:

1. **At least four numbering schemes appear in the text:**
   - an older 41-prabhag scheme (most PMC-area records);
   - an unidentified "new" scheme (169582);
   - PCMC wards (22 records);
   - other local bodies (Daund, Nira, possibly "Sub.Div.No.3").
2. **The number doesn't say which scheme it belongs to.** It equals the
   correct 2022 ward only by coincidence (e.g. Kharadi 4, Kondhwa 41). It is
   wrong for 2022 in the clearest cases: Ward 11 Kothrud → 2022 ward 11 is
   Bopodi-SPPU; Ward 6 Yerawada → 2022 ward 6 is Vadgaon Sheri-Ramwadi.
3. **Even the 41-scheme interpretation can't be converted to 2022 wards
   automatically.** There are no 41-prabhag boundaries, so the conversion
   depends on locality names, and one locality (e.g. Kothrud) spans several
   2022 wards.
4. **The current production behaviour** (`extract_ward_number` →
   `wards.id`) assigns the wrong ward in these cases. That should be treated
   as a known defect when using the `works` table.

**What is safe:** using the **named locality** with human review, and
treating any 2022 ward from this table as a candidate until it's checked
against the polygons.
