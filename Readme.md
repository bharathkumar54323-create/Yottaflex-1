
# CohortGuard – 3-Tier Course Participation, Assessment Progress & Completion System

An end-to-end, 100% offline 3-Tier Analytics and Reconciliation Platform designed to analyze learner cohort participation, content usage, assessment progress, and rule-based course completion.

CohortGuard identifies data inconsistencies, handles edge cases, quarantines invalid activity records, and maintains complete audit traceability.

---

## 1. Project Overview

CohortGuard provides an analytics platform for monitoring learner participation and course completion across multiple cohorts.

The platform follows a 3-tier architecture:

- **Tier 1 – Frontend:** Interactive dashboard built using HTML5, CSS3, and Vanilla JavaScript.
- **Tier 2 – Backend:** FastAPI REST API with SQLAlchemy and a rule-based completion engine.
- **Tier 3 – Database:** SQLite relational database with synthetic data generation, audit history, and reconciliation.

### Key Features

- Learner participation and engagement analytics.
- Course and cohort performance monitoring.
- Content consumption tracking.
- Assessment progress and completion monitoring.
- Rule-based course completion validation.
- Duplicate activity event detection.
- Invalid activity quarantine.
- Append-only enrollment state history.
- Deterministic synthetic dataset generation.
- SHA-256 dataset reproducibility validation.
- Fully offline execution without external CDNs or cloud dependencies.

---

## 2. System Architecture

```text
                TIER 1 – PRESENTATION
        ┌────────────────────────────────┐
        │       HTML5 + CSS3 + JS        │
        │                                │
        │       Interactive Dashboard   │
        │       Actor Switcher          │
        │       Analytics & Charts      │
        └───────────────┬────────────────┘
                        │
                  HTTP REST API
                        │
                        ▼
                TIER 2 – APPLICATION
        ┌────────────────────────────────┐
        │            FastAPI             │
        │                                │
        │       API Endpoints            │
        │       Business Rule Engine     │
        │       Data Validation          │
        │       Reconciliation           │
        │       Audit Processing         │
        └───────────────┬────────────────┘
                        │
                   SQLAlchemy
                        │
                        ▼
                TIER 3 – DATABASE
        ┌────────────────────────────────┐
        │           SQLite               │
        │                                │
        │       10 Core Entities         │
        │       Enrollment History       │
        │       Activity Events          │
        │       Assessment Records       │
        │       Quarantine Audit Log     │
        └────────────────────────────────┘
```

---

## 3. Technology Stack

| Component | Technology |
|---|---|
| Frontend | HTML5, CSS3, JavaScript ES6+ |
| Visualization | HTML5 Canvas |
| Backend | Python, FastAPI |
| API Server | Uvicorn |
| ORM | SQLAlchemy 2.x |
| Validation | Pydantic 2.x |
| Database | SQLite 3 |
| Synthetic Data | NumPy |
| Testing | Pytest, HTTPX |
| Integrity | SHA-256 |

### System Requirements

- Windows 10 / Windows 11 (64-bit)
- Python 3.10–3.13 (64-bit)
- No external database server required.
- No internet connection required after dependency installation.

---

## 4. Project Folder Structure

```text
Yottaflex.ai-hackation/
│
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
│   └── data_dictionary.md
│
├── tests/
│   └── test_validation.py
│
├── data_starter/
│   ├── CSV datasets
│   ├── ground_truth.csv
│   └── source_manifest.json
│
├── data_full/
│   ├── CSV datasets
│   ├── ground_truth.csv
│   └── source_manifest.json
│
├── requirements.txt
├── README.md
└── database/cohort_analytics.db
```

---

## 5. Synthetic Dataset Generation

CohortGuard uses a deterministic synthetic dataset generator powered by NumPy.

**Random Seed:** `20261022`

### Full Dataset Statistics

| Entity | Records |
|---|---:|
| Learners | 20,000 |
| Courses | 500 |
| Enrollments | 100,000 |
| Activity Events | 2,000,000 |

Two dataset configurations are supported:

- **Starter:** 1% dataset for quick development and testing.
- **Full:** Complete dataset for large-scale analytics and reconciliation.

### Generate Starter Dataset

```powershell
python database/generate_dataset.py --seed 20261022 --scale starter --out .\data_starter
```

### Generate Full Dataset

```powershell
python database/generate_dataset.py --seed 20261022 --scale full --out .\data_full
```

---

## 6. Core Actors

The application supports five different actors through the dashboard actor switcher.

1. **Academic Admin:** Monitors overall academic performance and completion.
2. **Learner:** Tracks personal course participation and assessment progress.
3. **Support Staff:** Investigates enrollment and activity exceptions.
4. **Instructor:** Monitors learner engagement and assessment performance.
5. **Platform Admin:** Monitors system integrity, reconciliation, and audit records.

---

## 7. Core Entities

The platform maintains 10 core entity categories:

| Entity | Description |
|---|---|
| LRN | Learner information |
| CRS | Course information |
| ENR | Learner enrollment |
| CNT | Course content |
| EVT | Learner activity events |
| ASM | Assessment information |
| ATT | Assessment attempts |
| RUL | Completion rules |
| COH | Cohort information |
| OUT | Completion outcomes |

The relational structure maintains data lineage across learners, courses, enrollments, events, assessments, and completion outcomes.

---

## 8. Edge Cases & Reconciliation

CohortGuard addresses four important data integrity scenarios.

### 1. Duplicate Events Inflate Engagement

**Problem:** Mobile applications may retry event synchronization, creating duplicate activity records.

**Solution:** Deduplicate events using `client_event_uuid` and retain the canonical event using:

```sql
ROW_NUMBER() OVER (
    PARTITION BY client_event_uuid
    ORDER BY event_timestamp_utc
)
```

### 2. Activity From Unenrolled Learners

**Problem:** Activity may be generated by learners who are not enrolled or have already withdrawn.

**Solution:** Invalid activity records are isolated in `quarantine_audit_log`.

### 3. Completion Before Required Assessment

**Problem:** A learner may claim course completion without satisfying mandatory assessment requirements.

**Solution:** The completion rule engine validates assessment requirements before accepting completion.

### 4. Timezone Shifts Misassign Days

**Problem:** Different client timezones can cause incorrect daily and weekly activity reporting.

**Solution:** Client timestamps are normalized to canonical UTC ISO-8601 timestamps before aggregation.

Weekly grouping:

```sql
strftime('%Y-W%W', event_timestamp_utc)
```

---

## 9. Installation & Setup (Windows PowerShell)

### Step 1 – Clone the Repository

```powershell
git clone <YOUR_REPOSITORY_URL>
cd Yottaflex.ai-hackation
```

### Step 2 – Create Virtual Environment

```powershell
python -m venv yottaflex
```

### Step 3 – Activate Environment

```powershell
.\yottaflex\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

### Step 4 – Install Dependencies

```powershell
python -m pip install --upgrade pip
```

```powershell
python -m pip install --only-binary :all: -r requirements.txt
```

### Step 5 – Create Package Markers

```powershell
New-Item -ItemType File -Path backend\__init__.py, database\__init__.py -Force
```

### Step 6 – Generate Starter Dataset

```powershell
python database\generate_dataset.py --seed 20261022 --scale starter --out .\data_starter
```

### Step 7 – Run Validation Tests

```powershell
python -m pytest -v tests\test_validation.py
```

### Step 8 – Start the Application

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

The backend automatically initializes the SQLite database and loads the starter dataset on first startup.

---

## 10. Access the Application

After starting the backend, access the following local URLs:

| Service | URL |
|---|---|
| Interactive Dashboard | http://127.0.0.1:8000 |
| FastAPI Swagger Docs | http://127.0.0.1:8000/docs |
| Health Check | http://127.0.0.1:8000/api/v1/health |

All application services run locally.

---

## 11. Loading the Full Dataset

To load the complete 2-million-event dataset into SQLite:

```powershell
python backend\load_db.py --data-dir .\data_full
```

**Note:** The full dataset requires additional disk space, memory, and processing time compared with the starter dataset.

---

## 12. Testing & Validation

CohortGuard includes an automated integrity validation suite.

Run:

```powershell
python -m pytest -v tests\test_validation.py
```

### Validation Coverage

- Primary key uniqueness.
- Foreign key integrity.
- Allowed enumeration values.
- Ground-truth leakage prevention.
- Duplicate event detection.
- Dataset consistency.
- Deterministic generation.
- SHA-256 reproducibility across independent runs.

The validation process helps ensure that generated datasets remain consistent and reproducible.

---

## 13. Data Provenance & Security

- All datasets are synthetically generated.
- No external learner PII is used.
- No third-party restricted datasets are required.
- Fixed random seed ensures reproducibility.
- SQLite operates locally without database credentials.
- No external CDN dependencies.
- Audit history supports traceability of enrollment state changes.
- Invalid records are preserved separately for investigation.

---

## 14. Future Enhancements

- Advanced cohort-level predictive analytics.
- Learner dropout risk identification.
- Assessment performance forecasting.
- More granular audit reporting.
- Role-based authentication and authorization.
- Large-scale database performance optimization.

---

## 15. Project Summary

CohortGuard demonstrates an end-to-end 3-tier analytics architecture combining frontend visualization, backend business rules, relational database management, deterministic synthetic data generation, and automated data integrity validation.

The system focuses on reliable learner participation analytics, accurate course completion decisions, transparent exception handling, and complete audit traceability.

**Built with Python, FastAPI, SQLite, SQLAlchemy, NumPy, HTML5, CSS3, and JavaScript.**
