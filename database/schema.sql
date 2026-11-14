-- ============================================================================
-- Tier 3: Zero-Credential Local SQLite Schema (database/schema.sql)
-- Project: Learner Cohort Participation, Assessment Progress & Completion
-- Runs 100% offline with Python 3.10's built-in sqlite3 (no passwords needed)
-- ============================================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cohorts (
    cohort_id        TEXT PRIMARY KEY,
    track_name       TEXT NOT NULL,
    start_date_utc   TEXT NOT NULL,
    end_date_utc     TEXT NOT NULL,
    lifecycle_state  TEXT NOT NULL CHECK(lifecycle_state IN ('SCHEDULED', 'ACTIVE', 'CONCLUDED'))
);

CREATE TABLE IF NOT EXISTS learners (
    learner_id           TEXT PRIMARY KEY,
    primary_cohort_id    TEXT NOT NULL REFERENCES cohorts(cohort_id),
    home_timezone        TEXT NOT NULL,
    tz_offset_minutes    INTEGER NOT NULL,
    is_inactive_baseline INTEGER NOT NULL DEFAULT 0,
    lifecycle_state      TEXT NOT NULL CHECK(lifecycle_state IN ('REGISTERED', 'ACTIVE', 'INACTIVE', 'ALUMNI')),
    created_at_utc       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    course_id       TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    domain_track    TEXT NOT NULL CHECK(domain_track IN ('AI_ENG', 'DATA_SCI', 'CLOUD_SYS', 'SEC_GOV', 'FULL_STACK')),
    total_modules   INTEGER NOT NULL,
    estimated_hours REAL NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('DRAFT', 'PUBLISHED', 'ARCHIVED'))
);

CREATE TABLE IF NOT EXISTS completion_rules (
    rule_id                        TEXT PRIMARY KEY,
    course_id                      TEXT NOT NULL REFERENCES courses(course_id),
    min_mandatory_content_pct      REAL NOT NULL DEFAULT 80.0,
    require_all_exams_passed       INTEGER NOT NULL DEFAULT 1,
    enforce_exam_before_completion INTEGER NOT NULL DEFAULT 1,
    grace_period_days              INTEGER NOT NULL DEFAULT 7,
    lifecycle_state                TEXT NOT NULL CHECK(lifecycle_state IN ('ACTIVE', 'SUPERSEDED'))
);

CREATE TABLE IF NOT EXISTS content_items (
    content_item_id   TEXT PRIMARY KEY,
    course_id         TEXT NOT NULL REFERENCES courses(course_id),
    parent_content_id TEXT NULL REFERENCES content_items(content_item_id),
    hierarchy_level   TEXT NOT NULL CHECK(hierarchy_level IN ('MODULE', 'LESSON_UNIT')),
    title             TEXT NOT NULL,
    is_mandatory      INTEGER NOT NULL DEFAULT 1,
    duration_minutes  INTEGER NOT NULL,
    lifecycle_state   TEXT NOT NULL CHECK(lifecycle_state IN ('ACTIVE', 'DEPRECATED'))
);

CREATE TABLE IF NOT EXISTS enrollments (
    enrollment_id    TEXT PRIMARY KEY,
    learner_id       TEXT NOT NULL REFERENCES learners(learner_id),
    course_id        TEXT NOT NULL REFERENCES courses(course_id),
    cohort_id        TEXT NOT NULL REFERENCES cohorts(cohort_id),
    enrolled_at_utc  TEXT NOT NULL,
    withdrawn_at_utc TEXT NULL,
    current_state    TEXT NOT NULL CHECK(current_state IN ('ENROLLED', 'IN_PROGRESS', 'INACTIVE', 'COMPLETED', 'WITHDRAWN', 'EXPIRED')),
    UNIQUE (learner_id, course_id)
);

CREATE TABLE IF NOT EXISTS enrollment_state_history (
    history_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id   TEXT NOT NULL REFERENCES enrollments(enrollment_id),
    from_state      TEXT NULL,
    to_state        TEXT NOT NULL,
    effective_from  TEXT NOT NULL,
    effective_to    TEXT NULL,
    changed_by      TEXT NOT NULL DEFAULT 'SYSTEM_RULE_ENGINE'
);

CREATE TABLE IF NOT EXISTS assessments (
    assessment_id     TEXT PRIMARY KEY,
    course_id         TEXT NOT NULL REFERENCES courses(course_id),
    assessment_type   TEXT NOT NULL CHECK(assessment_type IN ('MODULE_QUIZ', 'MIDTERM_PROJECT', 'CAPSTONE_FINAL')),
    passing_score_pct REAL NOT NULL DEFAULT 70.0,
    max_attempts      INTEGER NOT NULL DEFAULT 3,
    lifecycle_state   TEXT NOT NULL CHECK(lifecycle_state IN ('PUBLISHED', 'LOCKED'))
);

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id       TEXT PRIMARY KEY,
    assessment_id    TEXT NOT NULL REFERENCES assessments(assessment_id),
    enrollment_id    TEXT NOT NULL REFERENCES enrollments(enrollment_id),
    attempt_number   INTEGER NOT NULL,
    score_pct        REAL NOT NULL,
    is_passing       INTEGER NOT NULL,
    submitted_at_utc TEXT NOT NULL,
    lifecycle_state  TEXT NOT NULL CHECK(lifecycle_state IN ('STARTED', 'SUBMITTED', 'GRADED'))
);

-- Soft enrollment_id reference so Edge Case 2 orphan events can be ingested and quarantined
CREATE TABLE IF NOT EXISTS activity_events (
    event_id               TEXT PRIMARY KEY,
    enrollment_id          TEXT NOT NULL,
    learner_id             TEXT NOT NULL,
    course_id              TEXT NOT NULL,
    content_item_id        TEXT NOT NULL,
    client_event_uuid      TEXT NOT NULL,
    event_type             TEXT NOT NULL CHECK(event_type IN ('VIDEO_PLAY', 'VIDEO_COMPLETE', 'DOC_READ', 'LAB_SUBMIT', 'QUIZ_VIEW')),
    event_timestamp_utc    TEXT NOT NULL,
    client_local_timestamp TEXT NOT NULL,
    tz_offset_minutes      INTEGER NOT NULL,
    sync_mode              TEXT NOT NULL CHECK(sync_mode IN ('ONLINE', 'MOBILE_OFFLINE_SYNC')),
    duration_seconds       INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evt_dedup ON activity_events(enrollment_id, content_item_id, event_type, client_event_uuid);
CREATE INDEX IF NOT EXISTS idx_evt_time  ON activity_events(event_timestamp_utc);

CREATE TABLE IF NOT EXISTS course_outcomes (
    outcome_id          TEXT PRIMARY KEY,
    enrollment_id       TEXT NOT NULL UNIQUE REFERENCES enrollments(enrollment_id),
    final_status        TEXT NOT NULL CHECK(final_status IN ('COMPLETED', 'IN_PROGRESS', 'FAILED', 'WITHDRAWN', 'INACTIVE')),
    derived_content_pct REAL NOT NULL,
    best_exam_score_pct REAL NULL,
    completed_at_utc    TEXT NULL,
    evaluated_at_utc    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quarantine_audit_log (
    audit_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id        TEXT NOT NULL,
    parent_lineage   TEXT NOT NULL,
    issue_type       TEXT NOT NULL CHECK(issue_type IN ('DUPLICATE_EVENT_INFLATION', 'UNENROLLED_LEARNER_ACTIVITY', 'COMPLETION_BEFORE_ASSESSMENT', 'TIMEZONE_DAY_MISASSIGNMENT')),
    observed_detail  TEXT NOT NULL,
    engine_decision  TEXT NOT NULL,
    audit_status     TEXT NOT NULL,
    detected_at_utc  TEXT NOT NULL DEFAULT (datetime('now'))
);