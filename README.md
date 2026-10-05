# CivicFix 🏛️

> **Don't just manage complaints. Find the civic problem behind them — and verify whether the fix actually worked.**

**CivicFix** is an AI-assisted civic intelligence platform for intelligent citizen grievance triage, deduplication, prioritization, public-work correlation, and resolution verification.

Instead of treating every complaint as an independent ticket, CivicFix converts scattered citizen reports into **unified Civic Issues**, enriches them with civic context, connects them to relevant public works where evidence supports the match, and flags recurring or conflicting evidence for **human verification**.

---

## Problem

Traditional grievance systems primarily track individual complaints.

This creates several problems:

* One underlying civic problem can produce dozens of separate complaints.
* Similar complaints in different languages may not be recognized as the same issue.
* A long queue does not necessarily represent the most important civic problems.
* A ticket marked **Resolved** does not necessarily mean the physical problem is fixed.
* Administrators may lack the historical context needed to understand recurring issues.
* Public project records and citizen complaints are often stored separately.
* Low complaint volume does not necessarily mean low civic need.

CivicFix focuses on the gap between **what the complaint system records** and **what may actually be happening on the ground**.

---

# Core Idea

```text
Citizen Reports
      ↓
AI Understanding
      ↓
Semantic + Spatial + Temporal Clustering
      ↓
Unified Civic Issue
      ↓
Explainable Priority
      ↓
Civic Context
      ↓
Public Work Matching
      ↓
Intervention
      ↓
Recurrence / Outcome Check
      ↓
Human Verification
```

### CivicFix principle

> **AI understands. Evidence supports. Rules explain. Humans decide.**

---

# Key Features

## 1. One Problem, Not 50 Tickets

CivicFix combines:

* semantic similarity
* spatial proximity
* temporal proximity

to identify reports that may belong to the same underlying civic problem.

Example:

```text
50 citizen complaints
        ↓
Semantic + spatial + temporal analysis
        ↓
1 unified Civic Issue
```

This reduces duplicate administrative work and allows authorities to act on the **underlying issue** rather than individual tickets.

The prototype architecture uses sentence-transformer embeddings with clustering and distance/time constraints.

---

## 2. Explainable Priority

CivicFix does not use a black-box model to make the final priority decision.

Priority is based on published factors such as:

* Exposure
* Severity
* Recurrence
* Time Open

Conceptually:

```text
Priority =
w₁ × Exposure +
w₂ × Severity +
w₃ × Recurrence +
w₄ × TimeOpen
```

Each priority should be accompanied by an explanation.

Example:

```text
Priority: 84 / 100 — High

Exposure       +24
Severity       +22
Recurrence     +20
Time Open      +18
```

> **AI helps understand the issue. Transparent rules explain how urgently it should be handled.**

---

## 3. Civic Visibility Gap

CivicFix does not assume that complaint volume is a complete representation of civic need.

It can compare:

### Reported Signal

What citizens are reporting.

### Independent Civic Context

What available infrastructure, exposure, service, maintenance, and public-record data indicate.

When these signals disagree, CivicFix can create a **potential Civic Visibility Gap**.

Example:

```text
Complaint visibility       LOW
Infrastructure context     HIGH
Public exposure             HIGH
Maintenance history         OLD

→ Potential Visibility Gap
→ Verification recommended
```

This is a **verification signal**, not proof that an area has an undisclosed problem.

Ward-level literacy, where available, should be treated only as a contextual reporting indicator and should not directly determine the severity of an individual complaint.

---

## 4. Civic Memory

CivicFix maintains the history of a location or issue across time.

Example:

```text
2024 → Drainage complaint
2025 → Public work
2025 → Recurring complaint
2026 → New reports
2026 → Verification
```

This allows the system to recognize recurring patterns rather than treating every new complaint as an isolated event.

> **The city should not have to rediscover the same problem every year.**

---

## 5. Work → Outcome Check

Where documented public records support a match, CivicFix connects an issue to a relevant public work.

Evidence may include:

* project
* location
* category
* authority/agency
* dates
* status
* tender information where available

Then CivicFix checks subsequent complaint evidence.

Example:

```text
Recurring Issue
      ↓
Related Public Work
      ↓
Recorded Completion
      ↓
New Similar Reports
      ↓
Post-Intervention Recurrence
      ↓
Verification Recommended
```

A completed public work is **not automatically treated as proof that the underlying problem was solved**.

The project-matching architecture uses semantic similarity, geographic proximity, and date relationships, with a threshold before a project is linked.

---

## 6. Evidence-Backed Verification

CivicFix generates verification cases when evidence suggests that human review is needed.

Examples:

* recurrence after closure
* evidence disagreement
* possible public-work mismatch
* continued reports after intervention
* low complaint visibility with strong independent signals

Each flag should show the evidence that triggered it.

```text
Issue
  ↓
Evidence
  ├── Citizen reports
  ├── Location
  ├── Context
  ├── Public work
  └── Timeline
  ↓
Verification Case
  ↓
Human Review
```

CivicFix does not make the final decision autonomously.

---

## 7. Confirm Before Dispatch

Before unnecessary field dispatch, CivicFix can ask whether the issue still exists.

```text
Issue ready for dispatch
        ↓
Citizen / Officer confirmation
        ↓
Still Present → Dispatch
Fixed → Avoid unnecessary dispatch
Unclear → Verification
```

This helps reduce wasted field visits and supports the distinction between a reported ticket and a current physical problem.

---

## 8. Multilingual Complaint Understanding

CivicFix is designed for:

* English
* Hindi
* Marathi
* Code-mixed text

Example:

> `School ke saamne road pe paani jama hai.`

The pipeline can:

```text
Language Detection
        ↓
Normalization
        ↓
Location / Landmark Extraction
        ↓
Category Classification
        ↓
Issue Matching
```

Original citizen text should be retained as evidence while normalized representations are used for processing.

---

## 9. Location Intelligence

The system supports:

* GPS
* map location
* road names
* landmarks
* informal location descriptions

Example:

> “Opposite the old post office near the school.”

Location phrases can be extracted before geocoding.

If exact geocoding fails, CivicFix should fall back to a coarser location such as the ward rather than inventing a precise point.

---

# 10. Administrator Portal

CivicFix includes role-based administrative workflows.

## Ward Officer

The Ward Officer can:

* view ward issues
* inspect priority
* review issue clusters
* view the ward map
* assign work
* monitor SLA risk
* inspect public-work context
* trigger or respond to verification

## Reviewer

The Reviewer can:

* inspect verification cases
* inspect evidence bundles
* review recurrence signals
* review project matches
* record a verdict
* maintain the evidence trail

The architecture explicitly separates the **Ward Officer Dashboard** and **Reviewer Console**.

---

# 11. CivicFix Chatbot

The CivicFix Assistant provides a conversational interface to the platform.

Citizens can use it to:

* report an issue naturally
* use Marathi/Hindi/English
* provide location
* attach evidence
* find related Civic Issues
* track an issue
* understand priority
* confirm recurrence
* view available public-work context

Administrators can use it to:

* ask for today's priority issues
* search issues
* understand why an issue was flagged
* inspect evidence
* review recurrence
* open verification cases

The chatbot is an interface to CivicFix services, not a generic AI assistant.

---

# 12. Notifications & Automation

CivicFix can use **n8n** as the workflow automation layer between Supabase and notification channels.

Basic event flow:

```text
Supabase
   ↓
Database Event
   ↓
n8n
   ↓
Status Routing
   ├── Registered
   ├── In Progress
   ├── Resolved
   └── Verification Required
   ↓
Citizen Notification
```

Example:

### Complaint Registered

> Your complaint has been successfully registered with CivicFix.

### In Progress

> Your CivicFix issue is now being handled by the responsible team.

### Resolved

> Your CivicFix issue has been marked as resolved. CivicFix will continue monitoring for recurrence.

### Verification Required

> New evidence related to your issue requires additional verification.

Future automation can include:

* recurrence notifications
* SLA-risk alerts
* daily ward officer summaries
* reviewer notifications
* status-change notifications

n8n should handle **event-driven automation**, while CivicFix's backend remains responsible for AI, business rules, prioritization, clustering, matching and verification logic.

---

# Architecture

```text
                         CIVICFIX
                            │
             ┌──────────────┴──────────────┐
             │                             │
      CITIZEN PLANE                 PUBLIC RECORDS PLANE
             │                             │
      Text / Photo / GPS             Government Data
      Web / App / Chatbot            Civic Infrastructure
             │                             │
             └──────────────┬──────────────┘
                            │
                            ↓
                CIVIC INTELLIGENCE ENGINE
                            │
        ┌───────────────────┼───────────────────┐
        ↓                   ↓                   ↓
   Classification      Issue Clustering     Location
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ↓
                     Priority Engine
                            ↓
                    Civic Context
                            ↓
                    Project Matcher
                            ↓
                    Signal Detection
                            ↓
                    Verification
                            ↓
                 Administrative Action
                            ↓
                         Outcome
```

Your architecture uses PostgreSQL/PostGIS with pgvector for issue and public-work storage and geospatial/vector operations.

---

# Technology Stack

| Layer                   | Technology                |
| ----------------------- | ------------------------- |
| Frontend                | React + Vite              |
| Maps                    | Leaflet                   |
| Backend                 | FastAPI                   |
| Database                | PostgreSQL / Supabase     |
| Geospatial              | PostGIS                   |
| Vector Search           | pgvector                  |
| Embeddings              | Sentence Transformers     |
| Language Identification | fastText                  |
| Geocoding               | OpenStreetMap / Nominatim |
| Automation              | n8n                       |
| Notification            | Email / future channels   |

The stack and architectural components follow the system design in the submission.

---

# AI Components

## Load-bearing AI

### Location Phrase Extraction

NER extracts informal location phrases from complaint text.

### Semantic Deduplication

Sentence-transformer embeddings help identify complaints with different wording but similar meaning.

### Complaint Classification

Classification across the supported civic categories, including code-mixed language.

### Project Matching

Embedding similarity + geographic proximity + temporal relationship are used to identify potential links between civic issues and public works.

AI components produce suggestions/signals; thresholds and human review control consequential actions.

---

# What We Deliberately Do Not Automate

CivicFix deliberately avoids using a black-box AI model to make final municipal decisions.

### Priority

Formula-driven and explainable.

### Verification

Human-controlled.

### Project Links

Only shown when evidence meets the required threshold.

### Location

No unsupported precise coordinates are guessed.

### Severity from Images

Images remain supporting evidence unless a properly validated model is available.

> **AI suggests. Rules decide. Humans verify.**

---

# Dataset Overview

## Core

| Dataset                        | Use                                                              |
| ------------------------------ | ---------------------------------------------------------------- |
| PMC Complaint / Grievance Data | Complaint status, categories, recurrence, backlog and validation |
| MPLADS Public Works            | Match issues to funded works, agencies, cost, status and dates   |
| PMC Open Data                  | Pune civic infrastructure and administrative context             |
| Pune Ward Boundaries           | GIS ward mapping                                                 |

## Civic Context

| Dataset                          | Use                                        |
| -------------------------------- | ------------------------------------------ |
| Road Condition Data              | Road-condition context                     |
| Pune Footpaths and Roads         | Pedestrian and road infrastructure context |
| Bus Stops & Routes               | Transport/public-exposure context          |
| Water Supply / Distribution Loss | Water-service context                      |
| Water Treatment Plants           | Water infrastructure context               |
| Water Pollution Data             | Environmental/water context                |
| Waste Collection Data            | Garbage-service context                    |
| Government Hospitals             | Nearby public-health facilities            |
| Private Hospitals                | Healthcare context                         |
| Private Clinics                  | Healthcare-service context                 |
| Dispensaries                     | Primary healthcare context                 |
| Hospital Capacity & Facilities   | Potential health exposure                  |
| PMC Schools                      | School/exposure context                    |
| Schools – Student Enrollment     | Education-facility exposure                |
| Public Toilets Data              | Sanitation context                         |

## Supporting / Prototype Data

| Dataset                   | Use                                                        |
| ------------------------- | ---------------------------------------------------------- |
| NYC 311                   | Auxiliary training/tuning and validation support           |
| Synthetic Pune Complaints | Prototype evaluation, controlled scenarios and demos       |
| MahaTenders               | Procurement/tender evidence where documented matches exist |

NYC 311 and synthetic complaints are not presented as Pune ground-truth complaint data. The submission identifies NYC 311 as training/tuning support and synthetic complaints as prototype evaluation data.

---

# Example End-to-End Scenario

### Citizen report

> “There is water logging outside the school near the main road.”

### Step 1 — Understand

CivicFix extracts:

* category
* location
* landmark
* language
* severity signals

### Step 2 — Cluster

The system finds similar nearby reports.

```text
8 reports
   ↓
1 Civic Issue
```

### Step 3 — Prioritize

Example:

```text
Exposure    +24
Severity    +22
Recurrence  +20
Time        +18

Priority = 84 / 100
```

### Step 4 — Context

CivicFix identifies:

* nearby school
* road context
* public transport context
* recurrence history

### Step 5 — Public Work

A documented public work is found nearby with sufficient matching evidence.

### Step 6 — Outcome

The work is recorded as completed.

### Step 7 — Recurrence

Similar reports appear afterward.

### Step 8 — Verification

CivicFix produces:

> **Post-intervention recurrence detected — verification recommended.**

A human reviewer makes the final decision.

---

# Civic Issue Lifecycle

```text
Reported
   ↓
Understood
   ↓
Clustered
   ↓
Prioritized
   ↓
Assigned
   ↓
In Progress
   ↓
Resolved
   ↓
Verified
```

Possible recurrence:

```text
Resolved
   ↓
New Similar Evidence
   ↓
Reopened
   ↓
Verification Required
```

---

# Security & Responsible AI

CivicFix follows a human-in-the-loop model.

Important principles:

* No autonomous municipal decisions
* Explainable priority
* Confidence thresholds
* Evidence-linked signals
* Human verification
* Graceful location fallback
* Limited exposure of citizen information
* No unsupported accusations
* No treating synthetic records as real citizen records
* No unsupported project/contractor attribution

---

# Impact

## Citizens

* Easier multilingual reporting
* One issue view instead of fragmented tickets
* Transparent priority explanation
* Status and tracking
* Visibility into relevant public records
* Recurrence reporting

## Ward Officers

* Fewer duplicate issues to process
* Ranked operational queue
* Better geographic context
* Crew planning
* SLA awareness
* Evidence-backed verification

## Reviewers / Institutions

* Traceable evidence
* Public-work context
* Recurrence monitoring
* Reviewable anomaly signals
* Audit trail

The project's intended impact includes reducing duplicate administrative work, improving prioritization, and strengthening evidence-backed verification.

---

# Key Differentiators

### 01 — One Problem, Not 50 Tickets

**Semantic + spatial + temporal clustering**

### 02 — Priority You Can Explain

**Exposure + severity + recurrence + time**

### 03 — Civic Visibility Gap

**Detect where complaint visibility may not fully represent civic conditions**

### 04 — Civic Memory

**Remember the history of places, issues and interventions**

### 05 — Work → Outcome Check

**A recorded completion is checked against subsequent evidence**

### 06 — Evidence Conflict

**Conflicting signals produce verification instead of false certainty**

### 07 — Evidence-Backed Verification

**Every important flag can be traced to its supporting records**

---

# Project Positioning

Traditional grievance system:

```text
Complaint
   ↓
Department
   ↓
Ticket
   ↓
Closed
```

CivicFix:

```text
Complaint
   ↓
Underlying Issue
   ↓
Context
   ↓
Priority
   ↓
Public Intervention
   ↓
Outcome
   ↓
Verification
```

> **A closed complaint is a status. A verified resolution is evidence.**

---

# Future Scope

Potential future extensions include:

* stronger multilingual voice intake
* richer image evidence processing
* additional civic data connectors
* WhatsApp/SMS notifications
* automated daily operational summaries
* broader state/city integrations
* improved asset-level civic memory
* calibrated visibility-gap evaluation with field-verified samples

The architecture is intended to scale from Pune to other urban local bodies by replacing city-specific data connectors while keeping the intelligence and workflow layers consistent.

---

# Project Structure

A suggested repository structure:

```text
civicfix/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── layouts/
│   │   ├── services/
│   │   ├── hooks/
│   │   ├── types/
│   │   └── utils/
│   └── ...
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   ├── ml/
│   │   ├── db/
│   │   └── utils/
│   └── ...
│
├── n8n/
│   └── workflows/
│
├── data/
│   ├── complaints/
│   ├── public_works/
│   ├── civic_context/
│   └── synthetic/
│
└── README.md
```

Adapt this structure to the actual repository rather than restructuring an existing codebase unnecessarily.

---

# Local Development

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

> Use the actual project scripts and dependency files present in the repository.

---

# Environment Variables

Keep secrets server-side.

Typical configuration may include:

```env
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
DATABASE_URL=
GEOCODING_URL=
N8N_WEBHOOK_URL=
EMAIL_PROVIDER_CONFIG=
```

Do not commit secrets to Git.

Do not expose Supabase server/secret keys or private credentials in the React frontend.

Use the project's actual variable names when configuring deployment.

---

# Demo Flow

For a hackathon demonstration, the recommended flow is:

```text
Citizen submits complaint
        ↓
Multilingual AI understanding
        ↓
Location extraction
        ↓
Similar reports found
        ↓
8 reports → 1 Civic Issue
        ↓
Explainable priority
        ↓
Civic context
        ↓
Related public work
        ↓
Work marked completed
        ↓
New reports detected
        ↓
Post-intervention recurrence
        ↓
Verification Case
        ↓
Human reviewer decision
        ↓
Audit trail
        ↓
Citizen notification
```

---

# Core Message

## CivicFix

> **From scattered complaints to verified civic accountability.**

Or, for a shorter pitch:

> **“CivicFix doesn't just manage complaints. It identifies the underlying civic problem, connects it to evidence, and verifies whether the fix actually worked.”**

---

# Team

**Team Vision-17**
Vishwakarma Institute of Technology, Pune

Built for:

**Global SDG + AI Hackathon 2026**

Problem Statement:

**PS-18 — Intelligent Citizen Grievance Triage, Deduplication and Accountability**

SDG focus:

* **SDG 11 — Sustainable Cities and Communities**
* **SDG 16 — Peace, Justice and Strong Institutions**

---

# Responsible Data Note

Public datasets, auxiliary datasets, and synthetic prototype data have different purposes.

* Public records are used for civic context and evidence where applicable.
* NYC 311 is auxiliary training/tuning data.
* Synthetic complaints are used for prototype evaluation and controlled demonstrations.
* Data should not be presented as real citizen evidence unless it is genuinely sourced and verified.
* Public-work relationships should be described as **related/matched evidence** unless independently verified.

---


## 📜 License

This project is open-source and available under the [MIT License](LICENSE).
