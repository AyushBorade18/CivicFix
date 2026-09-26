# Complaint Writing Guide

We need **45 civic complaints about Pune**, written by the three of us, to test
and train WardSentry. Each person writes **15**. It takes about 1.5–2 hours.

Please read this whole page once before you start.

---

## 1. Where to write

One shared **Google Sheet** named `WardSentry complaints`.

- Row 1 = the headers below, exactly as written (copy-paste them).
- Everyone writes in the same sheet, in their own block of rows.
- When everyone is done, one person does **File → Download → Comma-separated values (.csv)**
  and sends it over. It goes into the repo as `data/labelling/lo2_gold_complaints.csv`.

Headers (paste into cell A1):

```
gold_id,split,text,locality,reported_date,dup_group,category,secondary_category,severity
```

Tip: in Google Sheets, paste this into A1, then **Data → Split text to columns**.

---

## 2. Who writes which rows

| Person | Rows (`gold_id`) | `test` rows | `seed` rows |
|---|---|---|---|
| Person 1 | G001 – G015 | G001 – G005 | G006 – G015 |
| Person 2 | G016 – G030 | G016 – G020 | G021 – G030 |
| Person 3 | G031 – G045 | G031 – G035 | G036 – G045 |

- **test** = hidden exam. These are never shown to ChatGPT or any AI, and never
  used to tweak the app. Only used at the end to score it.
- **seed** = examples we later give to an AI to create more variations.

---

## 3. What each column means

| Column | What to write | Example |
|---|---|---|
| `gold_id` | Your row ID from the table above | `G001` |
| `split` | `test` or `seed` (from the table above) | `test` |
| `text` | The complaint, like a real resident would type it. 8–60 words. | `gutter overflowing near Kelewadi bus stop, smell is unbearable` |
| `locality` | The place, in plain words. **Leave empty** if the complaint doesn't mention a place. | `Kelewadi, Kothrud` |
| `reported_date` | Any date in the last 2 months, format `YYYY-MM-DD`. **Complaints in the same `dup_group` must be within 7 days of each other** (section 6). | `2026-09-12` |
| `dup_group` | Same code for complaints about the **same actual problem** (see section 6). Otherwise leave empty. | `D01` |
| `category` | One from the list in section 4, spelled exactly | `drainage_sewage` |
| `secondary_category` | Only if the complaint mentions a second problem. Otherwise empty. | `garbage_waste` |
| `severity` | `cosmetic`, `moderate` or `critical` (section 5) | `critical` |

---

## 4. Categories: use these exact words

| Category | Total rows | Covers |
|---|---|---|
| `pothole_road` | 8 | potholes, broken road, road dug up and not refilled |
| `drainage_sewage` | 8 | blocked drain/gutter, sewage overflow, open manhole, waterlogging |
| `garbage_waste` | 7 | garbage not picked up, dumping spot, waste being burnt |
| `water_supply` | 6 | no water, low pressure, leaking pipe, dirty water |
| `streetlight` | 5 | light not working, flickering, broken pole |
| `footpath` | 4 | broken tiles, footpath blocked by stalls, missing slab |
| `traffic_signage` | 4 | signal not working, sign missing, zebra crossing faded |
| `other` | 3 | anything else: stray dogs, fallen tree, noise |

Per person that's roughly: 3 pothole, 3 drainage, 2–3 garbage, 2 water,
1–2 streetlight, 1–2 footpath, 1–2 traffic, 1 other. Decide the exact split
together before starting.

---

## 5. Severity

- **critical**: someone could get hurt. Open manhole, live wire, sewage mixing
  with drinking water, someone already fell or got injured.
- **moderate**: broken, blocked or not working, but no immediate danger.
- **cosmetic**: annoying or ugly, no real harm.

Aim for roughly 3 critical, 8 moderate, 4 cosmetic per person.

---

## 6. Duplicate groups (`dup_group`): the important part

In real life, several people report **the same problem** in different words.
The app must recognise these as one issue. We need to test that.

**Before anyone starts writing, spend 10 minutes together and agree on 10
"shared problems"**, e.g.:

| Group | Shared problem | Split |
|---|---|---|
| D01 | Drain overflowing near Kelewadi bus stop, Kothrud | test |
| D02 | Big pothole on Sutardara main road, Kothrud | seed |
| D03 | … | … |

Rules:
- Each group gets **2–3 complaints, written by different people**, each in their
  own words. **Don't look at each other's versions.**
- All complaints of one group must have `reported_date`s **within 7 days of
  each other**. The app only merges reports that close together, so a
  group spread over 3 weeks would never merge, and that would count against the app unfairly.
  Agree on a date for each group in step 1 and stay within ±3 days of it.
- All complaints of one group must have the **same split** (all `test` or all
  `seed`). Make 3–4 groups `test` and 6–7 groups `seed`.
- That's about 25 of the 45 rows. The rest are one-off complaints with `dup_group` empty.
- Also write **5 "trick" complaints**: **same place** as a group but a
  **different problem** (e.g. a streetlight at Kelewadi bus stop). Leave
  `dup_group` empty for these. They check the app doesn't wrongly merge
  complaints just because the place matches.

---

## 7. Locations

Only places inside **Pune Municipal Corporation (PMC)**.
**Not** Pimpri, Chinchwad, Nigdi, Wakad, Hinjewadi (those are PCMC).

**At least 12 complaints (4 each) must be in these areas.** Government public
works have already been done here, and our app links complaints to them:

| Area | Write complaints about |
|---|---|
| Kothrud: Sutardara, Kelewadi, Hanumannagar, Kishkindhanagar, Shastrinagar, Shelar Complex, Shravandhara | drainage, sewage, roads |
| Senapati Bapat (SB) Road, near NCC HQ | drainage, water |
| Ganesh Peth: Shivramdada Talim, Mari Aai Mata Mandir lane | roads, drainage |
| Lohegaon: Sai Ganesh Park | potholes |

Spread the rest around Pune: Hadapsar, Baner, Aundh, Katraj, Yerwada, Kharadi,
Warje, Kondhwa, Bibvewadi, Shivajinagar, Kasba Peth, Viman Nagar, Dhayari, etc.

---

## 8. How to write them so they feel real

This matters more than anything else. If they all sound neat and similar,
the test is useless.

**Mix it up:**
- **Language:** about 9 in English, 4 in Hinglish/Marathi typed in English
  letters (`gutter ka paani road pe aa raha hai`), 2 in Devanagari
  (`रस्त्यावर मोठे खड्डे आहेत`).
- **Length:** some very short (`streetlight off since 3 days sutardara`), some long rants.
- **Location detail:** some with a landmark (`opp Kelewadi bus stop`), some with
  just the area, and **1 per person with no location at all**.
- **Tone:** angry, polite, fed up (`3rd time complaining`), sarcastic.
- **Typos, no punctuation, CAPS**: type how people actually type on WhatsApp.
- **1 per person that mentions two problems** → fill `secondary_category`.

**Don't:**
- Use real people's names, phone numbers or house numbers.
- Write "fraud", "corrupt", "scam", or blame a named official or corporator.
- Copy wording from government records ("Laying of drainage line at Ward No. 11…").
- Put the category word in the text (`this is a pothole_road issue`).
- Show your `test` rows to ChatGPT or any AI tool, **ever**.

---

## 9. Examples

| gold_id | split | text | locality | reported_date | dup_group | category | secondary_category | severity |
|---|---|---|---|---|---|---|---|---|
| G001 | test | Drainage chamber near Kelewadi bus stop overflowing since 4 days, whole lane smells, kids walk through this to school | Kelewadi, Kothrud | 2026-09-12 | D01 | drainage_sewage | | critical |
| G016 | test | kelewadi mein gutter ka paani road pe aa raha hai koi dekhne nahi aaya | Kelewadi | 2026-09-14 | D01 | drainage_sewage | | moderate |
| G036 | seed | सुतारदरा रस्त्यावर मोठे खड्डे पडले आहेत, रात्री बाइक घसरते | Sutardara, Kothrud | 2026-09-03 | D02 | pothole_road | | moderate |
| G034 | test | light not working for a week and garbage piling up below the same pole | | 2026-09-20 | | streetlight | garbage_waste | cosmetic |

G001 and G016 are the **same problem** by two different people → both `D01`.

---

## 10. Step by step

1. **Together, 10 min:** agree on the 10 duplicate-group problems (section 6)
   and who writes which categories (section 4). Write the group list in a
   second tab of the sheet.
2. **Alone, ~60 min:** write your 15 rows.
3. **Category check, ~15 min:** in a new tab `check`, each person looks at
   another person's `text` only (hide the `category` column) and writes which
   category they think it is, as `gold_id, category_check`. This tells us
   how often even humans disagree. Download that tab as
   `lo2_category_check.csv`.
4. **Together, ~10 min:** where the check disagrees with `category`, discuss
   and fix `category` in the main tab if needed.
5. **Download both tabs as CSV** and hand them over.

---

## Checklist before handing over

- [ ] 15 rows each, IDs match the table in section 2
- [ ] Category words spelled exactly as in section 4
- [ ] Each duplicate group has 2–3 rows from different people, all the same split, dates within 7 days
- [ ] 5 "trick" same-place-different-problem rows exist
- [ ] At least 12 rows in the Kothrud / SB Road / Ganesh Peth / Lohegaon areas
- [ ] No real names, phone numbers, "fraud"/"corrupt"
- [ ] Dates are `YYYY-MM-DD`
- [ ] Test rows never pasted into any AI tool
