# Writing the 45 human complaints (LO2 gold set)

Output file: `data/labelling/lo2_gold_complaints.csv` (header already there).
Write in a shared Google Sheet with the exact same headers, then
File → Download → CSV (UTF-8) and replace the file above.

## Who writes what

3 writers × 15 complaints = 45. Writer codes: `W1`, `W2`, `W3`.

| split | rows | use |
|---|---|---|
| `test` | 15 (5 per writer) | Never shown to an LLM, never used to tune anything. This is the slide number. |
| `seed` | 30 (10 per writer) | Given to the LLM to expand into ~250 synthetic rows. |

## Columns

| column | filled by | values |
|---|---|---|
| `gold_id` | writer | `G001`…`G045` (W1: 001–015, W2: 016–030, W3: 031–045) |
| `split` | writer | `test` / `seed` |
| `writer_code` | writer | `W1` / `W2` / `W3` |
| `text` | writer | the complaint, 10–60 words |
| `language` | writer | `en` / `hi` / `mr` / `mixed` |
| `script` | writer | `latin` / `devanagari` / `mixed` |
| `locality` | writer | area as a human would say it, e.g. `Sutardara, Kothrud`. Leave empty if the text has no location. |
| `reported_date` | writer | `YYYY-MM-DD`, anywhere in the last 60 days |
| `dup_group` | writer | `D01`, `D02`… if this is the same real-world issue as another row; else empty |
| `category_a` | writer | category the writer intended (list below) |
| `category_b` | **a different teammate, without looking at `category_a`** | category list |
| `final_category` | whole team, at the end | agreed category |
| `secondary_category` | writer | only if the text mentions a 2nd issue |
| `severity` | writer | `cosmetic` / `moderate` / `critical` |
| `source` | fixed | `team_written` |
| `is_synthetic` | fixed | `true`: we wrote them, they are not real citizen reports. Say "human-written" in the pitch, never "real complaints". |
| `notes` | anyone | anything odd |

`category_a` vs `category_b` gives us an inter-annotator agreement number. Hide
the `category_a` column in the sheet while filling `category_b`.

## Categories (exact spelling, from `app/categories.py`)

| category | target rows | examples |
|---|---|---|
| `pothole_road` | 8 | potholes, broken road, road dug and not refilled |
| `drainage_sewage` | 8 | blocked drain, sewage overflow, open manhole, waterlogging |
| `garbage_waste` | 7 | garbage not collected, dumping spot, burning waste |
| `water_supply` | 6 | no water, low pressure, pipe leak, dirty water |
| `streetlight` | 5 | light off, flickering, pole damaged |
| `footpath` | 4 | broken tiles, encroached footpath, missing slab |
| `traffic_signage` | 4 | signal not working, missing sign, faded zebra crossing |
| `other` | 3 | stray dogs, tree fall, noise, anything outside the list |

Each writer takes about 1/3 of each category's rows (split it in the sheet before starting).

## Severity (bands from `app/nlp/severity.py`)

- `critical`: danger to people. Open manhole, sewage in drinking water, someone fell or got hurt, live wire.
- `moderate`: broken, blocked, not working, but no immediate danger.
- `cosmetic`: nuisance or appearance.

Aim for about 10 critical, 25 moderate, 10 cosmetic.

## Locations

Use real Pune (PMC) places. **At least 12 rows must be in these areas.**
Our MPLADS data has completed works there, so these rows test the core
issue → public-work link:

| area | work type there | write complaints about |
|---|---|---|
| Kothrud: Sutardara, Kelewadi, Hanumannagar, Kishkindhanagar, Shastrinagar, Shelar Complex, Shravandhara | drainage lines, road concreting | drainage, sewage, roads |
| Senapati Bapat (SB) Road, near NCC HQ | drainage line, water tank area | drainage, water |
| Ganesh Peth (Shivramdada Talim, Mari Aai Mata Mandir lane) | road asphalting, drainage | roads, drainage |
| Lohegaon, Sai Ganesh Park | lane asphalting | potholes |

Spread the rest across other PMC wards (full list in
`data/wards/pune-2022-wards.geojson`), e.g. Hadapsar, Baner, Aundh, Katraj,
Yerwada, Kharadi, Warje, Kondhwa, Bibvewadi, Shivajinagar, Kasba Peth.
**Not PCMC** (Pimpri, Chinchwad, Nigdi, Wakad, Hinjewadi): outside our wards.

Don't copy MPLADS wording ("Laying of drainage line at Ward No.11…").
Write like a resident. Copying makes the match look easier than it is.

## Duplicate groups (`dup_group`)

- Make **10 groups** of 2–3 rows each (~25 rows). Each group is one real-world
  issue reported by different people.
- Rows in a group must come from **different writers**. Agree on the 10
  issues first (5 minutes), then everyone writes their version without
  looking at the others'.
- Keep every row of a group in the same split (a group split across `test`
  and `seed` leaks test wording into the LLM). Put 6–7 groups in `seed`
  and 3–4 in `test`.
- Also write **5 hard negatives**: same locality as a group but a *different*
  issue (e.g. streetlight in Sutardara vs drainage in Sutardara). No `dup_group`.

## How to write them (the whole point is realism)

Mix these on purpose:
- Language: ~60% English, ~25% Hinglish/Marathi in Roman script
  ("gutter overflow ho raha hai"), ~15% Devanagari.
- Length: some 8-word one-liners, some 50-word rants.
- Location precision: landmark ("opp Kelewadi bus stop"), street, just the area,
  and **3–4 with no location at all** (these should go to the manual queue).
- Tone: angry, polite, sarcastic, "3rd time complaining".
- Typos, missing punctuation, all caps, as people actually type.
- 3–4 rows that mention two issues → fill `secondary_category`.

Don't:
- use real names, phone numbers, flat numbers of real people
- say "fraud", "corrupt", or blame a named official
- write the category word into every complaint (no "pothole_road issue")

## Example rows

```
G001,test,W1,"Drainage chamber near Kelewadi bus stop overflowing since 4 days, whole lane smells, kids walk through this to school",en,latin,"Kelewadi, Kothrud",2026-09-12,D01,drainage_sewage,,,,critical,team_written,true,
G016,test,W2,"kelewadi mein gutter ka paani road pe aa raha hai, koi dekhne nahi aaya",mixed,latin,"Kelewadi",2026-09-14,D01,drainage_sewage,,,,moderate,team_written,true,
G033,seed,W3,"सुतारदरा रस्त्यावर मोठे खड्डे पडले आहेत, रात्री बाइक घसरते",mr,devanagari,"Sutardara, Kothrud",2026-09-03,,pothole_road,,,,moderate,team_written,true,
G040,test,W3,"light not working for a week and garbage piling up below the same pole",en,latin,,2026-09-20,,streetlight,,,garbage_waste,cosmetic,team_written,true,no location on purpose
```

## Order of work (~2 hours total)

1. 10 min: agree on the 10 duplicate-group issues and who writes which categories.
2. 60 min: each writer fills their 15 rows (`category_b` empty).
3. 20 min: swap. Each person fills `category_b` for another writer's rows, blind.
4. 15 min: resolve disagreements into `final_category`. Record the count of disagreements.
5. Export CSV, then commit.
