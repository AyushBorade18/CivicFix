# Synthetic Pune civic complaints

**Every row here is synthetic.** The text was written by Claude (an AI model)
for CivicFix model development. No row is a real citizen complaint, and none
may be presented as one. Every row carries `is_synthetic=true` and a
`source` of `synthetic_claude` or `synthetic_claude_pilot`.

## Why synthetic

We found no public, row-level Pune complaint dataset. PMC Open Data and PMC
CARE publish only aggregates. iCMyC is Bengaluru-only (see `../icmyc.py`),
and the multilingual text the app must handle (Marathi, Hindi and their
romanized and code-mixed forms) isn't available anywhere as labelled data.

## Files

| File | Rows | Use |
|---|---|---|
| `complaints.csv` | 1,680 (1,580 + 100 relabelled pilot) | Training the category classifier |
| `paraphrase_groups.csv` | 400 groups × 3 = 1,200 | Fine-tuning the embedding model: the three texts in a group describe the same problem at the same place, in different language styles |
| `plan_complaints.csv`, `plan_groups.csv` | | Labels fixed before any text was written (`plan.py`, seed 42) |
| `batches/*.tsv` | | The written text, one `id<TAB>text` per line |
| `qc_report.txt` | | Output of the last quality check |

## Labels

- **category:** the 8 app categories (`app/categories.py`).
- **severity:** `cosmetic`, `moderate` or `critical`, the same values as the
  `severity_band` enum in `schema.sql`.
- **language:** `english`, `hindi`, `marathi`, `romanized_hindi`,
  `romanized_marathi`, `hinglish` or `marathi_english`. These are the same
  values as the human test set (`data/labelling/lo2_gold_complaints.csv`), so
  per-language scores line up. Everyday loanwords (road, light, footpath,
  signal, drainage) don't make a text code-mixed; whole English phrases do.
- **script:** `latin`, `devanagari` or `mixed`, detected from the text itself.
- **difficulty:** `normal`, `multi_issue` (with `secondary_category` set),
  `hard_boundary` (shares vocabulary with a look-alike category),
  `hard_vague` (short but still decidable) or `hard_spelling` (typos, only in
  Latin-script text).

## How it was made

1. `plan.py` gave each row its category, language, place, scenario, severity,
   tone, speaker type and length, from exact quotas. Categories iCMyC is short
   of (traffic_signage, water_supply, drainage_sewage) got more rows.
   Romanized Marathi is the largest language share, because that is how many
   Pune residents actually type and the stock multilingual model handles it
   worst.
2. Each row was then written by hand to fit its plan, in batches of about 100.
3. `assemble.py` ran after every batch and every problem was fixed before
   moving on. It checks:
   - script against language
   - letters from other alphabets
   - personal details
   - near-duplicates (character trigram Jaccard ≥ 0.6)
   - text copied from iCMyC

## Known limits

- **Written by an AI and reviewed by no native speaker yet.** The Marathi and
  Hindi should be spot-checked by a native speaker (see the team plan).
- **The labels are the writer's own judgement.** Hard-boundary rows are
  contestable by design.
- **Places are real, the conditions are invented.** Only localities inside
  PMC limits are used. No text reports a real incident. Pilot rows that
  named places outside PMC keep their text but have a blank `locality`.
- **A score measured on this data only shows how well the model learned the
  writer's style.** Report accuracy on the human-written test set, never on
  these rows.

## Rebuild or check

```
python -m training.synthetic.plan       # regenerates the plans (deterministic)
python -m training.synthetic.assemble   # merges batches, runs QC, writes the CSVs
```
