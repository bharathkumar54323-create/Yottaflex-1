# CohortGuard — 3-Tier Course Participation, Assessment Progress & Completion System

An end-to-end, 100% offline 3-Tier Analytics & Reconciliation Platform built to analyze learner cohort participation, content usage, assessment progress, and rule-based course completion while exposing edge-case exceptions and preserving full audit traceability.

## 1. System Requirements & Programming Versions

- **Operating System:** Windows 10 / 11 (64-bit)
- **Python Version:** Python 3.10 – 3.13 (64-bit)

**Tier 1 (Frontend):** HTML5, CSS3, Vanilla ES6+ JavaScript, HTML5 `<canvas>` (zero external CDNs)

**Tier 2 (Backend / Rule Engine):** FastAPI >=0.115.0, Uvicorn >=0.30.0, SQLAlchemy >=2.0.35, Pydantic >=2.9.0

**Tier 3 (Database & Seed Engine):** Built-in SQLite 3 (zero-credential local database) + NumPy >=2.1.0 (`default_rng(20261022)`)

**Testing & Validation:** Pytest >=8.3.0, HTTPX >=0.27.0

## 2. Project Folder Structure

    Yottaflex.ai-hackation/
    ├── frontend/
    │   └── index.html
    │
    ├── backend/
    │   ├── __init__.py
    │   ├── main.py
    │   └── load_db.py
    │
    ├── database/
    │   ├── __init__.py
    │   ├── schema.sql
    │   ├── generate_dataset.py
    │   ├── data_dictionary.md
    │   └── cohort_analytics.db
    │
    ├── tests/
    │   └── test_validation.py
    │
    ├── data_starter/
    ├── data_full/
    ├── requirements.txt
    └── README.md

## 3. Step-by-Step Setup & Run Instructions (Windows PowerShell)

### Step 1 — Create & Activate Virtual Environment

    python -m venv yottaflex
    .\yottaflex\Scripts\Activate.ps1

If PowerShell blocks script activation, run:

    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

### Step 2 — Install Dependencies

    .\yottaflex\Scripts\python.exe -m pip install --upgrade pip

    .\yottaflex\Scripts\python.exe -m pip install --only-binary :all: -r requirements.txt

### Step 3 — Create Package Markers

    New-Item -ItemType File -Path backend\__init__.py, database\__init__.py -Force

### Step 4 — Generate Deterministic Synthetic Datasets

Seed: `20261022`

**Starter Scale (1% volume — fast local testing):**

    .\yottaflex\Scripts\python.exe database\generate_dataset.py --seed 20261022 --scale starter --out .\data_starter

**Full Scale:**

20,000 learners, 500 courses, 100,000 enrollments, and 2,000,000 activity events.

    .\yottaflex\Scripts\python.exe database\generate_dataset.py --seed 20261022 --scale full --out .\data_full

### Step 5 — Run 8-Gate Validation & Reproducibility Tests

    .\yottaflex\Scripts\python.exe -m pytest -v tests\test_validation.py

Verifies primary-key uniqueness, foreign-key integrity, allowed enums, zero ground_truth.csv leakage, duplicate event detection, and bit-for-bit identical SHA-256 checksums across two independent runs with seed 20261022.

### Step 6 — Start the 3-Tier Application

    .\yottaflex\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

On first startup, `backend/main.py` automatically creates `database/cohort_analytics.db` from `database/schema.sql`, loads `data_starter/`, and populates `quarantine_audit_log`.

To load the full 2M-event dataset into SQLite manually:

    .\yottaflex\Scripts\python.exe backend\load_db.py --data-dir .\data_full

### Step 7 — Open the Application

- **Tier 1 Interactive Dashboard:** http://127.0.0.1:8000
- **Tier 2 FastAPI Swagger Docs:** http://127.0.0.1:8000/docs
- **Health Check JSON:** http://127.0.0.1:8000/api/v1/health

## 4. Core Entities, Actors & Edge Cases Covered

### 5 Primary Actors

1. Academic Admin
2. Learner
3. Support Staff
4. Instructor
5. Platform Admin

Selectable in the top-right Actor switcher.

### 10 Core Entities

- `LRN-*`
- `CRS-*`
- `ENR-*`
- `CNT-*`
- `EVT-*`
- `ASM-2026-*`
- `ATT-*`
- `RUL-*`
- `COH-*`
- `OUT-*`

Full relational lineage with `enrollment_state_history` preserving append-only state transitions.

### 4 Required Edge Cases

**1. Duplicate Events Inflate Engagement**

Mobile offline sync retries deduplicated via `client_event_uuid` (`ROW_NUMBER() = 1`).

**2. Activity From Unenrolled Learner**

Orphan or post-withdrawal events quarantined into `quarantine_audit_log`.

**3. Completion Before Required Assessment**

Premature `COMPLETED` claims blocked by `CompletionRule` checks.

**4. Timezone Shifts Misassign Days**

Local client offsets normalized to canonical UTC ISO-8601 week boundaries:

`strftime('%Y-W%W', event_timestamp_utc)`

## 5. Data Provenance & Lawful Use

100% synthetic dataset generated deterministically from fixed seed `20261022` with zero external PII or third-party restricted data.
