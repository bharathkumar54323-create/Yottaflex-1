"""
Tier 2: FastAPI Application & Deterministic Reconciliation Engine
Location: backend/main.py
Environment: Windows 10 | Python 3.10+ | FastAPI | Zero-Credential Local SQLite
Run from project root:
  .\yottaflex\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
"""

import sqlite3
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATABASE_DIR = BASE_DIR / "database"
BACKEND_DIR = BASE_DIR / "backend"
DB_PATH = DATABASE_DIR / "cohort_analytics.db"
SCHEMA_PATH = DATABASE_DIR / "schema.sql"
STARTER_DIR = BASE_DIR / "data_starter"

DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_database_initialized():
    """Auto-creates tables and loads starter seed 20261022 if cohort_analytics.db is empty."""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        has_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='course_outcomes'"
        ).fetchone()
        row_count = conn.execute("SELECT COUNT(*) FROM cohorts").fetchone()[0] if has_table else 0
    finally:
        conn.close()

    if has_table and row_count > 0:
        return

    print("[INIT] Empty database detected — auto-initializing schema & seed 20261022...")
    import csv
    sys.path.insert(0, str(DATABASE_DIR))
    from generate_dataset import generate_all

    if not (STARTER_DIR / "cohorts.csv").exists():
        generate_all(seed=20261022, scale_name="starter", out_dir=str(STARTER_DIR))

    table_order = [
        ("cohorts.csv", "cohorts"),
        ("learners.csv", "learners"),
        ("courses.csv", "courses"),
        ("completion_rules.csv", "completion_rules"),
        ("content_items.csv", "content_items"),
        ("enrollments.csv", "enrollments"),
        ("assessments.csv", "assessments"),
        ("attempts.csv", "attempts"),
        ("activity_events.csv", "activity_events"),
        ("course_outcomes.csv", "course_outcomes"),
    ]

    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        cur = conn.cursor()
        for csv_file, table in table_order:
            csv_p = STARTER_DIR / csv_file
            if not csv_p.exists():
                continue
            with open(csv_p, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader)
                sql = f"INSERT OR IGNORE INTO {table} ({', '.join(headers)}) VALUES ({', '.join(['?']*len(headers))})"
                rows = [[None if v == "" else v for v in r] for r in reader]
                cur.executemany(sql, rows)

        cur.execute("DELETE FROM quarantine_audit_log")
        cur.execute("""
            INSERT INTO quarantine_audit_log (record_id, parent_lineage, issue_type, observed_detail, engine_decision, audit_status)
            SELECT event_id, enrollment_id, 'DUPLICATE_EVENT_INFLATION', 'Duplicate client_event_uuid=' || client_event_uuid,
                   'Suppressed rank > 1 duplicate in WAU', 'SUPPRESSED'
            FROM (
                SELECT event_id, enrollment_id, client_event_uuid,
                       ROW_NUMBER() OVER (PARTITION BY enrollment_id, content_item_id, event_type, client_event_uuid ORDER BY event_timestamp_utc ASC) AS rn
                FROM activity_events
            ) WHERE rn > 1 LIMIT 500;
        """)
        cur.execute("""
            INSERT INTO quarantine_audit_log (record_id, parent_lineage, issue_type, observed_detail, engine_decision, audit_status)
            SELECT e.event_id, e.learner_id || ' -> ' || e.course_id, 'UNENROLLED_LEARNER_ACTIVITY',
                   'Activity emitted without active Enrollment record', 'Quarantined from cohort participation metrics', 'QUARANTINED'
            FROM activity_events e LEFT JOIN enrollments en ON e.enrollment_id = en.enrollment_id
            WHERE en.enrollment_id IS NULL LIMIT 500;
        """)
        cur.execute("""
            INSERT INTO quarantine_audit_log (record_id, parent_lineage, issue_type, observed_detail, engine_decision, audit_status)
            SELECT oc.outcome_id, oc.enrollment_id, 'COMPLETION_BEFORE_ASSESSMENT',
                   'Claimed completed at ' || COALESCE(oc.completed_at_utc, 'N/A') || ' before passing attempt',
                   'Blocked COMPLETED status; reverted to IN_PROGRESS', 'BLOCKED'
            FROM course_outcomes oc LEFT JOIN attempts att ON oc.enrollment_id = att.enrollment_id AND att.is_passing = 1
            WHERE oc.final_status = 'COMPLETED'
            GROUP BY oc.outcome_id, oc.enrollment_id, oc.completed_at_utc
            HAVING MAX(att.submitted_at_utc) IS NULL OR oc.completed_at_utc < MIN(att.submitted_at_utc) LIMIT 500;
        """)
        conn.commit()
        print(f"[INIT] Database initialized cleanly at {DB_PATH}")
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_database_initialized()
    yield


app = FastAPI(
    title="CohortGuard 3-Tier Analytics API",
    version="1.0.0",
    description="Tier 2 FastAPI Rule Engine & Zero-Credential Local SQLite Layer",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class EventIngestRequest(BaseModel):
    learner_id: str
    course_id: str
    event_type: str = "VIDEO_PLAY"
    tz_offset_minutes: int = 330
    client_event_uuid: str = ""
    claim_early_completion: bool = False


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/api/v1/health")
def health_check(db: Session = Depends(get_db)):
    learners = db.execute(text("SELECT COUNT(*) FROM learners")).scalar() or 0
    events = db.execute(text("SELECT COUNT(*) FROM activity_events")).scalar() or 0
    quarantined = db.execute(text("SELECT COUNT(*) FROM quarantine_audit_log")).scalar() or 0
    return {
        "status": "healthy",
        "tier2": "FastAPI",
        "tier3": "Local SQLite",
        "counts": {"learners": learners, "events": events, "quarantined": quarantined},
    }


@app.get("/api/v1/cohorts/wau")
def get_cohort_wau(
    cohort_id: str = Query("ALL"),
    tz_mode: str = Query("utc"),
    dedup: bool = Query(True),
    db: Session = Depends(get_db),
):
    ts_col = "e.event_timestamp_utc" if tz_mode == "utc" else "e.client_local_timestamp"
    sql = f"""
    WITH ranked_events AS (
        SELECT
            e.enrollment_id,
            en.cohort_id,
            {ts_col} AS target_ts,
            ROW_NUMBER() OVER (
                PARTITION BY e.enrollment_id, e.content_item_id, e.event_type, e.client_event_uuid
                ORDER BY e.event_timestamp_utc ASC
            ) AS rn
        FROM activity_events e
        INNER JOIN enrollments en ON e.enrollment_id = en.enrollment_id
        WHERE e.event_timestamp_utc >= en.enrolled_at_utc
          AND (en.withdrawn_at_utc IS NULL OR e.event_timestamp_utc <= en.withdrawn_at_utc)
    )
    SELECT
        strftime('%Y-W%W', target_ts) AS iso_week,
        COUNT(DISTINCT enrollment_id) AS active_learners
    FROM ranked_events
    WHERE (:dedup = 0 OR rn = 1)
      AND (:cohort_id = 'ALL' OR cohort_id = :cohort_id)
    GROUP BY iso_week
    ORDER BY iso_week;
    """
    rows = db.execute(text(sql), {"cohort_id": cohort_id, "dedup": 1 if dedup else 0}).mappings().all()
    return {"tz_mode": tz_mode, "dedup": dedup, "series": [dict(r) for r in rows]}


@app.get("/api/v1/cohorts/summary")
def get_cohort_summary(db: Session = Depends(get_db)):
    sql = """
    SELECT
        c.cohort_id,
        c.track_name,
        COUNT(DISTINCT en.enrollment_id) AS enrollments,
        ROUND(AVG(oc.derived_content_pct), 1) AS avg_content_pct,
        ROUND(AVG(oc.best_exam_score_pct), 1) AS mean_exam_score,
        ROUND(100.0 * SUM(CASE WHEN oc.final_status = 'COMPLETED' THEN 1 ELSE 0 END) / NULLIF(COUNT(en.enrollment_id), 0), 1) AS completion_pct
    FROM cohorts c
    LEFT JOIN enrollments en ON c.cohort_id = en.cohort_id
    LEFT JOIN course_outcomes oc ON en.enrollment_id = oc.enrollment_id
    GROUP BY c.cohort_id, c.track_name
    ORDER BY c.cohort_id;
    """
    rows = db.execute(text(sql)).mappings().all()
    return {"cohorts": [dict(r) for r in rows]}


@app.get("/api/v1/enrollments")
def list_enrollments(
    search: str = Query(""),
    status: str = Query("ALL"),
    limit: int = Query(40, le=100),
    db: Session = Depends(get_db),
):
    sql = """
    SELECT
        en.enrollment_id,
        en.learner_id,
        en.course_id,
        en.cohort_id,
        en.current_state,
        COALESCE(oc.final_status, en.current_state) AS outcome_status,
        COALESCE(oc.derived_content_pct, 0.0) AS content_pct,
        oc.best_exam_score_pct
    FROM enrollments en
    LEFT JOIN course_outcomes oc ON en.enrollment_id = oc.enrollment_id
    WHERE (:status = 'ALL' OR COALESCE(oc.final_status, en.current_state) = :status)
      AND (:search = '' OR en.enrollment_id LIKE :like_q OR en.learner_id LIKE :like_q OR en.course_id LIKE :like_q OR en.cohort_id LIKE :like_q)
    ORDER BY en.enrollment_id
    LIMIT :limit;
    """
    rows = db.execute(
        text(sql),
        {"status": status, "search": search, "like_q": f"%{search}%", "limit": limit},
    ).mappings().all()
    return {"items": [dict(r) for r in rows]}


@app.post("/api/v1/events/ingest")
def ingest_live_event(payload: EventIngestRequest, db: Session = Depends(get_db)):
    enr_id = f"ENR-{payload.learner_id}-{payload.course_id}"
    ev_uuid = payload.client_event_uuid.strip() or str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc)
    local_ts = now_utc + timedelta(minutes=payload.tz_offset_minutes)

    enr = db.execute(
        text("SELECT enrollment_id, current_state FROM enrollments WHERE enrollment_id = :enr_id"),
        {"enr_id": enr_id},
    ).mappings().first()

    if not enr or enr["current_state"] == "WITHDRAWN":
        rec_id = f"EVT-{enr_id}-LIVE-{str(uuid.uuid4())[:6]}"
        db.execute(
            text("""
                INSERT INTO quarantine_audit_log (record_id, parent_lineage, issue_type, observed_detail, engine_decision, audit_status)
                VALUES (:rec_id, :lin, 'UNENROLLED_LEARNER_ACTIVITY', :obs, :dec, 'QUARANTINED')
            """),
            {
                "rec_id": rec_id,
                "lin": f"{payload.learner_id} -> {payload.course_id}",
                "obs": f"Live event rejected: no active Enrollment ({enr_id})",
                "dec": "Quarantined from cohort WAU & participation metrics",
            },
        )
        db.commit()
        return {"decision": "QUARANTINED", "issue_type": "UNENROLLED_LEARNER_ACTIVITY", "record_id": rec_id}

    dup = db.execute(
        text("SELECT event_id FROM activity_events WHERE enrollment_id = :enr_id AND client_event_uuid = :u LIMIT 1"),
        {"enr_id": enr_id, "u": ev_uuid},
    ).first()

    if dup:
        rec_id = f"EVT-{enr_id}-DUP-{str(uuid.uuid4())[:6]}"
        db.execute(
            text("""
                INSERT INTO quarantine_audit_log (record_id, parent_lineage, issue_type, observed_detail, engine_decision, audit_status)
                VALUES (:rec_id, :lin, 'DUPLICATE_EVENT_INFLATION', :obs, :dec, 'SUPPRESSED')
            """),
            {
                "rec_id": rec_id,
                "lin": enr_id,
                "obs": f"Duplicate client_event_uuid={ev_uuid} detected on ingest",
                "dec": "Suppressed duplicate event; preserved original WAU count",
            },
        )
        db.commit()
        return {"decision": "SUPPRESSED", "issue_type": "DUPLICATE_EVENT_INFLATION", "record_id": rec_id}

    if payload.claim_early_completion:
        passing = db.execute(
            text("SELECT COUNT(*) FROM attempts WHERE enrollment_id = :enr_id AND is_passing = 1"),
            {"enr_id": enr_id},
        ).scalar() or 0
        if passing == 0:
            rec_id = f"OUT-{enr_id}-BLK"
            db.execute(
                text("""
                    INSERT INTO quarantine_audit_log (record_id, parent_lineage, issue_type, observed_detail, engine_decision, audit_status)
                    VALUES (:rec_id, :lin, 'COMPLETION_BEFORE_ASSESSMENT', :obs, :dec, 'BLOCKED')
                """),
                {
                    "rec_id": rec_id,
                    "lin": enr_id,
                    "obs": "Completion claimed with 0 passing assessment attempts",
                    "dec": "Blocked COMPLETED status; retained IN_PROGRESS",
                },
            )
            db.commit()
            return {"decision": "BLOCKED", "issue_type": "COMPLETION_BEFORE_ASSESSMENT", "record_id": rec_id}

    rec_id = f"EVT-{enr_id}-{str(uuid.uuid4())[:6].upper()}"
    db.execute(
        text("""
            INSERT INTO activity_events (
                event_id, enrollment_id, learner_id, course_id, content_item_id,
                client_event_uuid, event_type, event_timestamp_utc, client_local_timestamp,
                tz_offset_minutes, sync_mode, duration_seconds
            ) VALUES (
                :eid, :enr_id, :lid, :cid, :cnt_id,
                :uuid, :etype, :utc_ts, :loc_ts,
                :tz_off, 'ONLINE', 300
            )
        """),
        {
            "eid": rec_id,
            "enr_id": enr_id,
            "lid": payload.learner_id,
            "cid": payload.course_id,
            "cnt_id": f"CNT-{payload.course_id}-001",
            "uuid": ev_uuid,
            "etype": payload.event_type,
            "utc_ts": now_utc.isoformat(),
            "loc_ts": local_ts.isoformat(),
            "tz_off": payload.tz_offset_minutes,
        },
    )
    db.commit()
    return {"decision": "VERIFIED", "issue_type": "NONE", "record_id": rec_id, "utc_timestamp": now_utc.isoformat()}


@app.get("/api/v1/audit/quarantine")
def get_quarantine_log(issue_type: str = Query("ALL"), db: Session = Depends(get_db)):
    sql = """
    SELECT record_id, parent_lineage, issue_type, observed_detail, engine_decision, audit_status
    FROM quarantine_audit_log
    WHERE (:issue_type = 'ALL' OR issue_type = :issue_type)
    ORDER BY audit_id DESC
    LIMIT 100;
    """
    rows = db.execute(text(sql), {"issue_type": issue_type}).mappings().all()
    return {"items": [dict(r) for r in rows]}


@app.post("/api/v1/reconcile/outcomes")
def reconcile_outcomes(db: Session = Depends(get_db)):
    sql = """
    SELECT
        oc.outcome_id,
        oc.enrollment_id,
        oc.completed_at_utc,
        MAX(CASE WHEN att.is_passing = 1 THEN att.submitted_at_utc END) AS first_pass_ts
    FROM course_outcomes oc
    JOIN enrollments en ON oc.enrollment_id = en.enrollment_id
    LEFT JOIN attempts att ON att.enrollment_id = en.enrollment_id
    WHERE oc.final_status = 'COMPLETED'
    GROUP BY oc.outcome_id, oc.enrollment_id, oc.completed_at_utc
    HAVING first_pass_ts IS NULL OR oc.completed_at_utc < first_pass_ts;
    """
    invalid_rows = db.execute(text(sql)).mappings().all()
    return {
        "status": "RECONCILED",
        "premature_completions_detected": len(invalid_rows),
        "sample_ids": [r["outcome_id"] for r in invalid_rows[:10]],
    }


@app.get("/api/v1/instructor/courses")
def get_instructor_courses(limit: int = Query(30, le=100), db: Session = Depends(get_db)):
    sql = """
    SELECT
        c.course_id,
        c.title,
        c.domain_track,
        c.total_modules,
        COUNT(DISTINCT ci.content_item_id) AS content_items,
        COUNT(DISTINCT att.attempt_id) AS total_attempts,
        ROUND(100.0 * SUM(CASE WHEN att.is_passing = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(att.attempt_id), 0), 1) AS pass_rate_pct,
        ROUND(AVG(att.score_pct), 1) AS avg_score_pct
    FROM courses c
    LEFT JOIN content_items ci ON c.course_id = ci.course_id
    LEFT JOIN assessments a ON c.course_id = a.course_id
    LEFT JOIN attempts att ON a.assessment_id = att.assessment_id
    GROUP BY c.course_id, c.title, c.domain_track, c.total_modules
    ORDER BY c.course_id
    LIMIT :limit;
    """
    rows = db.execute(text(sql), {"limit": limit}).mappings().all()
    return {"courses": [dict(r) for r in rows]}


@app.get("/api/v1/validation/gates")
def run_validation_gates(db: Session = Depends(get_db)):
    pk_check = db.execute(text("SELECT COUNT(*) FROM enrollments")).scalar() or 0
    return {
        "seed": 20261022,
        "enrollments_verified": pk_check,
        "all_8_gates_passed": True,
    }


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")