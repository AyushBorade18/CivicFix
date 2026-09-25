# CIVICFIX — COMPLETE PROJECT HANDOFF / CONTEXT FOR CLAUDE CODE

You are taking over work on a hackathon project called CivicFix.

IMPORTANT:
Read this entire handoff before doing anything.

You are working in the user's local environment. Only the user has access to the main CivicFix codebase. Other teammates do NOT have access to this Claude Code environment and are working independently.

Your job right now is primarily DATA/ML preparation. Do NOT modify the existing CivicFix application, database, frontend, production model, or unrelated project files unless explicitly instructed.

============================================================
1. PROJECT IDEA
============================================================

CivicFix is an AI-powered civic complaint intelligence system for Pune, India.

The intended system takes a citizen complaint such as:

- "There is a huge pothole near Kothrud..."
- "Baner mein paani nahi aa raha"
- "रस्त्यावर खूप कचरा जमा झाला आहे"
- "street light band hai"
- "warje madhe drainage overflow hot aahe"

and performs civic issue classification and downstream civic intelligence.

The classifier has 8 target categories:

1. pothole_road
2. drainage_sewage
3. water_supply
4. streetlight
5. garbage_waste
6. footpath
7. traffic_signage
8. other

The model needs to support:

- English
- Hindi
- Marathi
- Romanized Hindi
- Romanized Marathi
- Hinglish
- mixed Hindi/English
- mixed Marathi/English
- code-switched complaints

The eventual demo should be Pune-focused.

============================================================
2. HACKATHON OBJECTIVE
============================================================

Before the hackathon, we want the important data and ML work already completed.

During the hackathon itself, the goal should mainly be:

- connect the trained model
- connect the backend/API
- connect data pipelines
- build/integrate the frontend
- demonstrate the complete workflow

We do NOT want to arrive at the hackathon still needing to:

- find the main training dataset
- train the primary classifier from scratch
- discover basic categories
- perform major data cleaning
- discover the Pune geography model
- build the core ML pipeline

The trained models can be brought into the hackathon.

============================================================
3. DATA SOURCES WE HAVE INVESTIGATED
============================================================

A major part of the previous work was searching for real Pune complaint-level data.

The following conclusions have already been established.

------------------------------------------------------------
3.1 PMC Open Data
------------------------------------------------------------

PMC has an open-data portal.

However, we did NOT find a downloadable complaint-level dataset containing citizen complaint text.

The portal contains useful civic datasets such as:

- ward maps
- streetlights
- sewage infrastructure
- etc.

But this does not solve the complaint-text training problem.

------------------------------------------------------------
3.2 PMC CARE
------------------------------------------------------------

PMC CARE exists and handles complaints.

However, publicly visible information was aggregate/statistical rather than a downloadable row-level complaint dataset.

Therefore it is NOT currently usable as our main complaint-training dataset.

------------------------------------------------------------
3.3 Maharashtra Grievance / CPGRAMS
------------------------------------------------------------

Dashboards/counts exist.

We did not find a verified downloadable complaint-text dataset suitable for CivicFix.

------------------------------------------------------------
3.4 MahaTenders
------------------------------------------------------------

We audited MahaTenders as a potential procurement/public-work evidence source.

Conclusion:

MahaTenders is potentially useful as an external evidence source, but we did not verify a free official API or bulk downloadable complaint/work dataset.

It should NOT become a core automatic dependency.

It can potentially be used for:

- tender evidence
- public-work references
- procurement stage information
- selected evidence links

But:

A tender is NOT proof that a work was completed.

The government portal should remain the provenance anchor.

Do not scrape it or bypass authentication.

------------------------------------------------------------
3.5 Tenderkart
------------------------------------------------------------

Tenderkart was investigated as another potential source.

It blocks structured automated collection without appropriate access.

Its terms also restrict scraping/extraction.

We therefore stopped.

No Tenderkart records were collected.

No dataset was created from it.

------------------------------------------------------------
4. L08 DATASET AUDIT
============================================================

An L08 package was audited.

It contained 13 files:

1. Pune Electoral Wards Map – 2022.kml
2. Pune – Zone-wise Public Toilets Data.csv
3. Pune Footpaths and Roads.csv
4. Pune Bus Stops and Routes.csv
5. Ward-wise Government Hospitals.csv
6. Ward-wise Private Hospitals.csv
7. Ward-wise Private Clinics.csv
8. Ward-wise Dispensaries.csv
9. Hospitals with Capacity and Facilities.csv
10. PMC Schools.csv
11. List of Schools in the PMC Area.csv
12. Schools – Students Enrolled Class-wise.csv
13. Total Number of Schools and Colleges.csv

Important findings:

- The ward KML duplicates our existing Pune 2022 ward GeoJSON.
- The bus-route CSV duplicates existing PMC data and contains routes rather than actual stop coordinates.
- Footpath/road data is aggregate data.
- Government hospitals: 50 points.
- Private hospitals: 228 points.
- Private clinics: 170 points.
- Dispensaries: 30 points.
- PMC schools: 71 usable coordinate points.
- The data provides useful exposure/sensitive-site information.
- It does NOT provide citizen complaints.

The L08 audit was read-only.

No CivicFix code/database was modified.

------------------------------------------------------------
5. WARD SCHEME FINDING
------------------------------------------------------------

L08 contained a 41-prabhag toilet dataset.

This was useful because some MPLADS records refer to ward numbers.

Several MPLADS ward mentions align with the 41-prabhag names.

Examples previously identified:

- Kothrud
- Baner
- Warje
- Yerawada
- Erandvana

However this is NOT a verified complete ward crosswalk.

There are multiple ward numbering schemes:

- 2022 electoral wards: 58 polygons
- 41-prabhag scheme
- 76-prabhag scheme
- 15 ward offices

Do NOT automatically assume they are equivalent.

The 41-prabhag mapping is only supporting evidence.

------------------------------------------------------------
6. OTHER EXISTING DATA
============================================================

The project already has/useful data including:

- Pune 2022 ward GeoJSON
- PMC.zip
- MPLADS/public-work information
- OSM-derived civic/site information
- L08 civic infrastructure data
- hospital/school point datasets
- bus-stop information from PMC.zip

These are primarily useful for:

- geography
- civic infrastructure
- public-work evidence
- exposure/site information
- ward context

They do NOT replace the missing complaint dataset.

============================================================
7. COMPLAINT DATASET SEARCH
============================================================

The biggest blocker has been finding real complaint-level data.

We investigated iChangeMyCity / iCMyC via OpenCity.

Initially it appeared promising because it was described as:

"I Change My City Complaints Log – 2019–2022"

and appeared to contain fields such as:

created_at
ward_id
title
description
sub_category_id
civic_agency_id
location
address
latitude
longitude
ward_title
category_id
category_title
sub_category_title
civic_agency_title
complaint_status_title
comment_count

However, the first downloaded file was actually an HTML 404 page.

Later, the correct CKAN datastore was found and downloaded.

IMPORTANT FINAL FINDING:

The real dataset contains:

16,071 rows.

Date range:

2019-01-01 to 2022-12-07.

18 columns.

The expected 17 CivicFix-relevant fields are present plus a datastore _id.

BUT:

It is effectively a BENGALURU dataset.

Detailed checks showed:

- 15,548 / 16,071 rows mention Bengaluru/Bangalore.
- Only one literal "pune" hit existed and it was a false positive involving "Puneet"/Puneeth Rajkumar Road.
- Other apparent Pune hits were also false positives/ambiguous Bengaluru localities.
- Civic agencies were Bengaluru agencies such as:
  - BBMP
  - BTP
  - BWSSB
  - KSPCB
  - BESCOM
  - BMTC
  - Bangalore Traffic Police
- The parent CKAN package also appeared Bengaluru-only.

Therefore:

DO NOT claim that iCMyC provides Pune complaint data.

DO NOT filter this dataset and call it Pune data.

There is effectively zero verified Pune data in this particular resource.

============================================================
8. iCMyC DATASET — WHAT IT IS STILL USEFUL FOR
============================================================

Although it is not Pune data, it may still be useful as an auxiliary Indian civic-complaint corpus.

It contains:

- 16,071 complaints
- civic issue categories
- complaint descriptions
- locations
- dates
- category/subcategory information

It can potentially help with:

- understanding Indian civic complaint language
- learning broad category structure
- auxiliary model training
- English Indian civic vocabulary
- robustness

But it must be labelled/documented as Bengaluru/India auxiliary data.

It must NOT be presented as Pune data.

============================================================
9. iCMyC CATEGORY FINDINGS
============================================================

category_title has 43 unique values.

sub_category_title has 220 unique values.

Important categories include things such as:

- Mobility - Roads/Footpaths/Infra
- Garbage and Unsanitary Practices
- Traffic and Road Safety
- Street lighting
- Streetlights
- Yellow Spot
- Animal Husbandry

Important subcategories include:

- Clearance Of Garbage Dump
- Fixing/Repairing Potholes
- Tarring/Asphalting Roads
- Streetlight Maintenance

There is some schema drift / near-duplicate category naming across time.

============================================================
10. iCMyC LANGUAGE FINDING
============================================================

A random sample of 300 non-empty descriptions was created.

The sample was overwhelmingly Latin-script English.

Approximate result:

- 299 Latin-script
- 0 Devanagari
- 1 neither

Manual inspection also suggested mostly English / Indian English.

There was no evidence that this dataset provides the multilingual Hindi/Marathi coverage we need.

This means iCMyC cannot solve our multilingual requirement by itself.

============================================================
11. iCMyC PII FINDING
============================================================

A heuristic scan of all 16,071 rows found:

- phone-like patterns: ~200 rows
- email-like patterns: 11 rows
- Aadhaar-like 12-digit patterns: 0
- long digit sequences: ~229
- "Regards/Thanks" + capitalized name sign-offs: ~638

Complaint text may also contain:

- names
- phone numbers
- email addresses
- exact addresses
- property/application IDs
- location-specific information

Any future training dataset must remove/mask PII.

============================================================
12. CURRENT COMPLAINT-DATA CONCLUSION
============================================================

After substantial research, we have NOT found a verified open Pune-specific complaint-level dataset that satisfies all requirements:

- Pune-specific
- complaint-level
- real citizen text
- sufficient volume
- multilingual
- usable for model training

Therefore the current project plan is moving toward a SYNTHETIC COMPLAINT DATASET.

This decision should be documented honestly.

Synthetic data must NEVER be represented as real citizen complaints.

============================================================
13. SYNTHETIC DATASET PLAN
============================================================

We want to create a high-quality synthetic dataset that approximates the type of Pune civic complaints CivicFix is expected to receive.

The dataset should contain realistic complaint text, but every record must explicitly be marked synthetic.

Suggested metadata:

source_type = synthetic
source_name = CivicFix synthetic generation
geography = Pune
is_synthetic = true

Do NOT fabricate a real government source.

Do NOT give synthetic records fake URLs or fake complaint IDs that could be mistaken for real government records.

============================================================
14. SYNTHETIC DATA REQUIREMENTS
============================================================

The dataset should cover all 8 categories:

1. pothole_road
2. drainage_sewage
3. water_supply
4. streetlight
5. garbage_waste
6. footpath
7. traffic_signage
8. other

Language coverage should include:

- English
- Hindi
- Marathi
- Romanized Hindi
- Romanized Marathi
- Hinglish
- Marathi-English mixed
- Hindi-English mixed

We want natural variation.

Examples of variation:

- short complaints
- long complaints
- informal complaints
- polite complaints
- angry/frustrated complaints
- incomplete sentences
- spelling mistakes
- abbreviations
- code-switching
- Romanized Indian language
- Devanagari
- location references
- landmarks
- road names
- neighbourhood names
- ward/locality references

But do NOT generate fake precise personal information.

Avoid:

- real people's names
- phone numbers
- email addresses
- Aadhaar numbers
- fake complaint IDs resembling government IDs
- unnecessary exact residential addresses

Use generic/public locality references where useful.

============================================================
15. VERY IMPORTANT SYNTHETIC DATA WARNING
============================================================

Do NOT generate thousands of records in one simplistic template.

Previous exploration showed a serious risk:

Synthetic complaints can become mechanically generated, with:

- repeated sentence structures
- repeated "URGENT"
- repeated "EMERGENCY"
- repeated wording
- near-duplicate complaints
- artificial clustering

That would create a weak model that learns the generator rather than civic language.

Therefore:

FIRST generate a SMALL PILOT.

Target pilot:

~200 records.

Then audit:

- duplicate rate
- near-duplicate rate
- category leakage
- language balance
- unnatural phrases
- repetitive templates
- geographic realism
- category ambiguity
- mixed-language quality

Only after the pilot is accepted should the larger dataset be generated.

============================================================
16. LO1 / LO2
============================================================

The intended dataset structure is:

LO1:
Complaint Candidate Dataset

Target:

~1,000–1,500 records.

LO1 is the main candidate training dataset.

LO2:
Human-reviewed Gold Dataset

Target:

~300–500 records.

LO2 should be independently reviewed by humans.

LO2 should NOT simply be treated as "Claude-generated labels that Claude agrees with."

Human review is important.

The purpose of LO2 is to provide a higher-confidence evaluation/gold set.

============================================================
17. IMPORTANT CHANGE FOR SYNTHETIC DATA
============================================================

Because the complaint data is synthetic:

Do NOT claim:

"These are real Pune citizen complaints."

Instead document:

"These are synthetic Pune civic complaint examples generated to approximate realistic multilingual civic-reporting language. They are used for model development because no suitable public Pune complaint-level dataset was found."

This distinction must remain in:

- README
- dataset metadata
- hackathon documentation
- presentation/demo explanation if relevant

============================================================
18. MODEL TRAINING STRATEGY
============================================================

The goal is NOT necessarily to train a huge language model from scratch.

The likely approach should be:

- use the synthetic multilingual complaint dataset for supervised classification
- optionally use iCMyC/Bengaluru as auxiliary Indian civic language data
- use existing project model architecture where available
- evaluate on LO2
- maintain category balance
- evaluate by language separately

Important evaluation dimensions:

Overall accuracy/F1 is not enough.

Check:

- per-category precision/recall/F1
- English performance
- Hindi performance
- Marathi performance
- Romanized Hindi performance
- Romanized Marathi performance
- Hinglish performance
- confusion matrix
- "other" performance

============================================================
19. GEOGRAPHY RULE
============================================================

Pune-specificity matters for the DEMO and civic evidence.

The complaint classifier itself does not necessarily require every training example to be from Pune.

A possible architecture is:

TRAINING:
- synthetic Pune complaints
- optionally auxiliary Indian civic complaints such as iCMyC/Bengaluru
- clearly track source/geography

DEMO:
- Pune complaints / synthetic Pune complaints
- Pune wards
- Pune civic infrastructure
- Pune public works
- Pune hospitals/schools/bus stops
- Pune geography

Do NOT silently mix Bengaluru and Pune records and call the whole dataset Pune.

============================================================
20. EXISTING TEAMMATE WORK
============================================================

Teammate 2/3 audited the iCMyC dataset.

Their work included:

- setting up Python 3.11
- installing pandas
- finding the correct CKAN datastore
- downloading the actual 16,071-row dataset
- schema inspection
- Pune filtering
- category analysis
- language sampling
- PII scanning

They did NOT modify the CivicFix repo.

Their final conclusion was that the dataset is Bengaluru-only.

The user has the main codebase.

============================================================
21. WHAT HAS ALREADY BEEN DONE
============================================================

Completed:

[DATA]
- Pune ward GeoJSON available
- PMC.zip available
- L08 dataset audited
- health/school infrastructure datasets audited
- bus-stop sources identified
- MPLADS/public-work data investigated
- MahaTenders source audited
- Tenderkart investigated and stopped
- iCMyC dataset found and downloaded
- iCMyC schema audited
- iCMyC Pune filtering attempted
- iCMyC language sample created
- iCMyC PII scan performed

[IMPORTANT FINDINGS]
- no verified open Pune complaint dataset found
- iCMyC resource is Bengaluru, not Pune
- no reliable public MahaTenders API verified
- L08 does not contain complaints
- L08 gives useful civic infrastructure/exposure data
- multilingual real complaint source remains unavailable

============================================================
22. WHAT REMAINS TO BE DONE
============================================================

HIGH PRIORITY:

1. Design synthetic complaint schema.
2. Generate ~200 synthetic pilot complaints.
3. Audit pilot for quality.
4. Improve generation strategy.
5. Generate LO1 (~1,000–1,500).
6. Create human-reviewed LO2 (~300–500).
7. Clean/mask PII.
8. Check duplicates/near-duplicates.
9. Check language distribution.
10. Check category balance.
11. Train the complaint classifier.
12. Evaluate on LO2.
13. Evaluate separately by language.
14. Save the final trained model.
15. Create reproducible preprocessing/inference pipeline.

SECONDARY:

16. Integrate iCMyC as optional auxiliary Indian civic data if useful.
17. Integrate Pune ward/infrastructure data.
18. Integrate public-work/MPLADS evidence.
19. Integrate bus stops.
20. Integrate hospital/school exposure sites.
21. Connect procurement evidence if legitimate/manual.

HACKATHON:

22. Backend integration.
23. Model inference API.
24. Frontend.
25. Complaint submission UI.
26. Multilingual demo.
27. Map visualization.
28. Civic evidence display.
29. End-to-end pipeline.
30. Demo testing.

============================================================
23. CURRENT IMMEDIATE TASK FOR YOU
============================================================

The immediate task is NOT to modify the main CivicFix application.

We are preparing the synthetic complaint dataset.

Start by designing the generation process.

DO NOT immediately generate 1,500+ records.

First:

1. Inspect the current ~/civicfix-data/raw/ directory.
2. Determine what data files already exist.
3. Do not delete anything.
4. Do not modify existing datasets.
5. Create a new isolated directory:

~/civicfix-data/raw/synthetic_complaints/

6. Create a generation plan/document.
7. Generate a PILOT of approximately 200 synthetic complaints.
8. Include all 8 categories.
9. Include multilingual and code-switched examples.
10. Ensure strong variation in wording.
11. Add metadata identifying every record as synthetic.
12. Run duplicate and near-duplicate checks.
13. Produce a quality report.
14. STOP and show me the report.

Do NOT generate the final 1,000–1,500 records until the pilot has been reviewed.

============================================================
24. EXPECTED SYNTHETIC DATA SCHEMA
============================================================

At minimum consider:

complaint_id
text
category
language
script
city
locality
source_type
source_name
is_synthetic

Optional:

created_at
severity
has_location
location_type

But do not invent unnecessary metadata that could create misleading realism.

Every record should have:

is_synthetic = true

and:

city = Pune

if it is intended as a synthetic Pune complaint.

============================================================
25. LOCALITY GUIDANCE
============================================================

Use real Pune locality/landmark names where appropriate, such as:

- Kothrud
- Baner
- Balewadi
- Warje
- Hadapsar
- Yerawada
- Shivajinagar
- Aundh
- Viman Nagar
- Kharadi
- Kondhwa
- Bibwewadi
- Karve Nagar
- Erandwane
- Swargate
- etc.

But do not create fake precise addresses or pretend a real complaint occurred at a particular house.

Locality references are for linguistic/geographic realism, not fabricated evidence.

============================================================
26. CATEGORY GUIDANCE
============================================================

pothole_road:
- potholes
- damaged roads
- road surface
- broken asphalt
- road repair

drainage_sewage:
- sewage overflow
- blocked drains
- drainage blockage
- wastewater
- manholes
- flooding caused by drainage

water_supply:
- no water
- low pressure
- irregular supply
- contaminated water
- water timing

streetlight:
- streetlight not working
- dark roads
- broken lamp
- lights flickering

garbage_waste:
- garbage accumulation
- overflowing bins
- waste collection
- illegal dumping
- garbage smell

footpath:
- broken footpaths
- blocked sidewalks
- missing pavement
- inaccessible pedestrian path

traffic_signage:
- missing signs
- damaged traffic signs
- signal/signage issues
- confusing road signs
- pedestrian/traffic signage

other:
- complaints that genuinely don't fit the above
- civic issues outside the defined categories

Be careful not to make category names trivially visible in every complaint.

============================================================
27. MULTILINGUAL REQUIREMENT
============================================================

Do not simply translate the same English sentence into 6 languages.

We need independent natural complaints.

For example, language variation should include:

English:
"The footpath near the bus stop is broken and people are walking on the road."

Hindi:
"यहाँ का नाला कई दिनों से जाम है और गंदा पानी सड़क पर आ रहा है।"

Marathi:
"या रस्त्यावरचे स्ट्रीट लाईट गेल्या आठवड्यापासून बंद आहेत."

Romanized Hindi:
"Baner mein do din se paani ka pressure bahut kam hai."

Romanized Marathi:
"Kothrud madhe footpath khup tutlela aahe, chalnyasathi jagach nahi."

Hinglish:
"Warje side ka road full potholes se bhara hai, especially near the junction."

These are examples of style only; do not copy them into the dataset.

============================================================
28. QUALITY RULES
============================================================

Reject records that:

- are obvious paraphrases of another record
- use identical sentence templates
- repeat "URGENT" excessively
- contain fake personal information
- contain impossible Pune geography
- are clearly machine-like
- have category labels inconsistent with the text
- use unnatural Hindi/Marathi
- are just translations of another record
- include irrelevant generic text
- contain government-looking fake IDs
- imply that the synthetic complaint is a real historical complaint

Aim for realistic diversity.

============================================================
29. DATA PROVENANCE
============================================================

Create:

README.md

and:

generation_metadata.json

The README should explicitly state:

- dataset is synthetic
- generated for CivicFix model development
- intended geography is Pune
- no records represent verified real citizen complaints
- real Pune complaint-level open data was not found during project research
- iCMyC was investigated but found to be Bengaluru-focused
- synthetic data is being used as a development substitute

============================================================
30. DO NOT DO THESE THINGS
============================================================

DO NOT:

- scrape government sites
- bypass Cloudflare
- bypass authentication
- scrape Tenderkart
- claim synthetic records are real
- modify the main CivicFix repo
- modify production databases
- delete existing datasets
- overwrite source datasets
- train the final model before pilot review
- fabricate provenance
- invent URLs
- invent government complaint IDs
- claim that iCMyC is Pune data
- claim that MahaTenders provides complaint data
- treat tenders as proof of completed work

============================================================
31. STOP CONDITION
============================================================

After generating and auditing the ~200-record pilot:

STOP.

Report:

1. number generated
2. category distribution
3. language distribution
4. script distribution
5. duplicate count
6. near-duplicate count
7. suspicious records
8. examples of quality problems
9. PII scan results
10. whether the generation approach should be changed
11. recommended changes before generating LO1

Do not proceed to 1,000–1,500 records without explicit approval.

============================================================
32. MOST IMPORTANT PRINCIPLE
============================================================

CivicFix needs to be credible.

The lack of a real Pune complaint dataset is a known project limitation.

Synthetic data is acceptable as a model-development strategy if it is:

- clearly disclosed
- carefully generated
- quality audited
- human reviewed
- evaluated transparently
- never presented as real citizen data

The objective is to build the best defensible hackathon prototype possible without misrepresenting the provenance of the data.

END OF HANDOFF.
