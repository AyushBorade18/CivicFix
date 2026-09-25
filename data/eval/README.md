# data/eval — LO4 (issue → public work matching) working data

Non-production. Nothing here is read by `app/`. The production `works`
table is untouched.

## Files

| File | What | Rebuild |
|---|---|---|
| `public_works_master.csv` | 318 normalized public-work records (MPLADS, Pune district filter) | `python -m scripts.lo4.build_public_works_master` |
| `lo4_candidate_examples.csv` | 16 example issue↔work candidate pairs, `label` empty | `python -m scripts.lo4.candidate_pairs` (needs the dev DB running; read-only) |

## Sources

| Source | Rows contributed | Why |
|---|---|---|
| MPLADS — `data/mplads/MPLADS_cleaned.csv` | 318 | Only file with actual work records. Same `ida`/`constituency` "pune" filter as `app/ingest/mplads.py`. |
| PMC Open Data — `PMC.zip` | 0 | Ward-level indicators, river water quality, water plant/supply summaries, PMPML bus routes/stops. No project or work records. |
| MPLADS older export — `~/Downloads/MPLADS.csv` | 0 | 38 Pune rows, all rural, all "Unsanctioned", generic "NA - <category>" text, no work id. |
| MahaTenders | 0 | Not in the repo yet. No placeholder rows. |

## Rules the master follows

- `ward_id` is set **only** from a cached geocode point that falls inside a
  PMC 2022 polygon **and** doesn't contradict the text (PCMC or rural cues).
  A "Ward No. N" in MPLADS text is never mapped to `ward_id`. It is kept in
  `ward_number_in_text` with `ward_mapping_status`, because MPLADS text mixes
  PMC old and new ward numbers, PCMC wards and village wards.
- Coordinates only come from `data/cache/geocode_cache.json`. There are no
  new lookups, and every coordinate is unverified.
- `work_category` is the keyword mapper from `app/ingest/category.py`
  (`category_method`). It misses many road, drain and light works
  (`other_but_mentions_civic_infra`).
- `start_date` and `source_url` are empty because MPLADS has neither.
  `recommended_date` is not a start date.
- `matching_usability` is a triage tier, not a label:
  - `candidate:*` — completed, civic category, positive PMC evidence
  - `review:*` — needs a human check (e.g. category mapper miss)
  - `negative_only:*` — PMC-area work usable as a hard negative
  - `exclude:*` — PCMC, rural, jurisdiction unknown

## Candidate pairs

Built by rules only (strategies A–G, see `scripts/lo4/candidate_pairs.py`).
They never use the matcher, its scores, the `matches` table or generator
anchors. `circular_risk` marks pairs whose issue text reuses the work's own
location words, which the synthetic generator does. `issue_source` separates
hand-typed UI reports from synthetic templates.
