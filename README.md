# CivicFix 🏛️

Civic complaints shouldn't disappear into a queue. CivicFix is an intelligent civic issue triage and accountability platform designed for municipal corporations. It bridges the gap between citizens reporting local issues and the government agencies responsible for resolving them, while cross-referencing complaints with funded public works (like MPLADS) to enforce transparency.

## 🌟 Key Features

### For Citizens
* **Multilingual Intake:** Report civic issues in your native language via text or speech.
* **Smart Duplication Prevention:** The system automatically groups your complaint with similar ones nearby to form a single, high-priority tracked issue.
* **Transparent Tracking:** Browse an interactive spatial map of all issues across wards, check priority scores, and verify public records.
* **Feedback Loop:** Once an issue is marked resolved by the municipality, residents can confirm the fix or dispute it with fresh evidence.

### For Administrators
* **Spatial Evidence Map:** A comprehensive view of citizen issues, matched public works, and sensitive sites (hospitals, schools) on a single interactive canvas.
* **Auditable Priority Formulas:** Triage issues not based on guesswork, but on a deterministic, fully transparent formula considering severity, exposure, recurrence, and time open.
* **MPLADS Cross-Check:** Automatically matches civic complaints with existing government-funded public work records to flag works that may need a closer look, for human review.
* **Verification Signals:** Highlights data discrepancies and priority signals through automated auditing algorithms.

## 🏗️ Architecture & Tech Stack

CivicFix is built using a modern, scalable stack:

**Frontend**
* **React 18** via Vite
* **Tailwind CSS v4** for responsive, utility-first styling
* **Lucide React** for beautiful, consistent iconography
* Custom **Glowing UI Components** for a modern, interactive design system

**Backend**
* **FastAPI (Python)** providing high-performance, asynchronous REST endpoints
* **Geospatial Processing** for ward mapping and coordinate clustering
* **Deterministic Matching Engine** for public works verification

## 🚀 Getting Started

### Prerequisites
* Node.js (v18+)
* Python 3.12
* PostgreSQL 17 with **PostGIS** and **pgvector** (the app is geospatial and
  stores embeddings; it will not start against a plain Postgres)
* Git

### Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/CivicFix.git
   cd CivicFix
   ```

2. **Database.** This project uses a dedicated cluster on port **5433** so it
   never collides with a system Postgres on 5432:
   ```bash
   createdb -p 5433 civicfix
   psql -p 5433 -d civicfix -c "CREATE EXTENSION postgis; CREATE EXTENSION vector;"
   psql -p 5433 -d civicfix -f schema.sql
   ```
   Then create `.env` in the repo root:
   ```
   DATABASE_URL=postgresql://<user>@localhost:5433/civicfix
   TEST_DATABASE_URL=postgresql://<user>@localhost:5433/civicfix_test
   ```
   `TEST_DATABASE_URL` must point at a **separate** database — the test
   fixtures truncate what they touch.

3. **Start the Backend API** (from the repo root, not `app/`):
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python -m spacy download en_core_web_sm
   uvicorn app.api.main:app --reload --port 8000
   ```

4. **Start the Frontend Development Server:**
   ```bash
   # Open a new terminal tab
   cd web
   npm install
   npm run dev
   ```

5. **Access the application:**
   Open your browser and navigate to `http://localhost:5173`. 
   * **Citizen Portal:** `/citizen`
   * **Admin Console:** `/admin`

## 🎨 UI/UX Highlights

The application uses a light, high-contrast console interface with a monospaced
data voice, so counts, scores and record ids stay legible when they are on a
projector. The `GlowingCard` component tracks mouse proximity to illuminate
borders, emphasising spatial interaction without decorating the numbers.

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).
