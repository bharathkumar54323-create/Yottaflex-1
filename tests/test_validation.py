"""
Step 8 & Step 10: 8-Gate Automated Validation & Reproducibility Test Suite
Location: tests/test_validation.py
Run from project root:
  pytest -v tests/test_validation.py
"""

import csv
import json
import os
import sys
import tempfile
from pathlib import Path
import pytest

# Allow importing generate_dataset from ../database
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "database"))
from generate_dataset import generate_all


@pytest.fixture(scope="module")
def starter_dir():
    with tempfile.TemporaryDirectory() as tmp1:
        generate_all(seed=20261022, scale_name="starter", out_dir=tmp1)
        yield tmp1


def read_csv_dicts(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_gate1_primary_key_uniqueness(starter_dir):
    checks = [
        ("learners.csv", "learner_id"),
        ("courses.csv", "course_id"),
        ("cohorts.csv", "cohort_id"),
        ("enrollments.csv", "enrollment_id"),
        ("activity_events.csv", "event_id"),
        ("assessments.csv", "assessment_id"),
        ("attempts.csv", "attempt_id"),
        ("completion_rules.csv", "rule_id"),
        ("content_items.csv", "content_item_id"),
        ("course_outcomes.csv", "outcome_id"),
    ]
    for fname, pk in checks:
        rows = read_csv_dicts(os.path.join(starter_dir, fname))
        ids = [r[pk] for r in rows]
        assert len(ids) == len(set(ids)), f"Duplicate PK found in {fname}"


def test_gate2_foreign_key_integrity(starter_dir):
    learners = {r["learner_id"] for r in read_csv_dicts(os.path.join(starter_dir, "learners.csv"))}
    courses = {r["course_id"] for r in read_csv_dicts(os.path.join(starter_dir, "courses.csv"))}
    enrollments = read_csv_dicts(os.path.join(starter_dir, "enrollments.csv"))
    for enr in enrollments:
        assert enr["learner_id"] in learners
        assert enr["course_id"] in courses


def test_gate3_allowed_enums(starter_dir):
    allowed_events = {"VIDEO_PLAY", "VIDEO_COMPLETE", "DOC_READ", "LAB_SUBMIT", "QUIZ_VIEW"}
    events = read_csv_dicts(os.path.join(starter_dir, "activity_events.csv"))
    for ev in events:
        assert ev["event_type"] in allowed_events


def test_gate4_and_7_ground_truth_isolation(starter_dir):
    for fname in ["activity_events.csv", "course_outcomes.csv", "enrollments.csv"]:
        with open(os.path.join(starter_dir, fname), "r", encoding="utf-8") as f:
            header = f.readline().strip().split(",")
            assert "issue_type" not in header
            assert "ground_truth" not in header

    gt = read_csv_dicts(os.path.join(starter_dir, "ground_truth.csv"))
    issue_types = {r["issue_type"] for r in gt}
    assert "DUPLICATE_EVENT_INFLATION" in issue_types
    assert "UNENROLLED_LEARNER_ACTIVITY" in issue_types
    assert "COMPLETION_BEFORE_ASSESSMENT" in issue_types
    assert "TIMEZONE_DAY_MISASSIGNMENT" in issue_types


def test_gate5_event_deduplication_catches_edge_case_1(starter_dir):
    events = read_csv_dicts(os.path.join(starter_dir, "activity_events.csv"))
    seen = set()
    dups = 0
    for ev in events:
        key = (ev["enrollment_id"], ev["content_item_id"], ev["event_type"], ev["client_event_uuid"])
        if key in seen:
            dups += 1
        seen.add(key)
    assert dups > 0, "Expected injected duplicate events to be detected by idempotency key"


def test_step10_double_run_reproducibility():
    with tempfile.TemporaryDirectory() as run1, tempfile.TemporaryDirectory() as run2:
        generate_all(seed=20261022, scale_name="starter", out_dir=run1)
        generate_all(seed=20261022, scale_name="starter", out_dir=run2)
        m1 = json.load(open(os.path.join(run1, "source_manifest.json"), encoding="utf-8"))
        m2 = json.load(open(os.path.join(run2, "source_manifest.json"), encoding="utf-8"))
        assert m1["checksums_sha256"] == m2["checksums_sha256"], "SHA-256 mismatch between two identical seed runs"