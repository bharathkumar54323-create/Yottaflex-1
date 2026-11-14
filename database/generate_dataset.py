"""
Tier 3: Deterministic Fixed-Seed Synthetic Data Generator
Project: Learner Cohort Participation, Assessment Progress & Completion
Author: Bharath Kumar Reddy
Usage:
  python generate_dataset.py --seed 20261022 --scale starter --out ./data_starter
  python generate_dataset.py --seed 20261022 --scale full --out ./data_full
"""

import argparse
import csv
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
import numpy as np


SCALE_CONFIG = {
    "starter": {
        "learners": 200,
        "courses": 25,
        "cohorts": 5,
        "enrollments": 1000,
        "events": 20000,
    },
    "full": {
        "learners": 20000,
        "courses": 500,
        "cohorts": 50,
        "enrollments": 100000,
        "events": 2000000,
    },
}

TIMEZONES = [
    ("Asia/Kolkata", 330),
    ("America/Los_Angeles", -480),
    ("America/New_York", -300),
    ("Europe/London", 0),
    ("Asia/Tokyo", 540),
]

TRACKS = ["AI_ENG", "DATA_SCI", "CLOUD_SYS", "SEC_GOV", "FULL_STACK"]
EVENT_TYPES = ["VIDEO_PLAY", "VIDEO_COMPLETE", "DOC_READ", "LAB_SUBMIT", "QUIZ_VIEW"]


def deterministic_uuid(rng: np.random.Generator) -> str:
    raw = rng.bytes(16)
    return str(uuid.UUID(bytes=raw))


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: str, headers: list, rows: list):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def generate_all(seed: int, scale_name: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    cfg = SCALE_CONFIG[scale_name]
    rng = np.random.default_rng(seed)
    base_start = datetime(2026, 1, 5, 0, 0, 0, tzinfo=timezone.utc)  # Monday ISO week

    # 1. Cohorts
    cohorts = []
    for i in range(1, cfg["cohorts"] + 1):
        cid = f"COH-2026-{i:03d}"
        track = TRACKS[(i - 1) % len(TRACKS)]
        c_start = base_start + timedelta(weeks=(i - 1) % 4)
        c_end = c_start + timedelta(weeks=8)
        cohorts.append([cid, f"{track} Cohort {i}", c_start.isoformat(), c_end.isoformat(), "ACTIVE"])
    write_csv(
        os.path.join(out_dir, "cohorts.csv"),
        ["cohort_id", "track_name", "start_date_utc", "end_date_utc", "lifecycle_state"],
        cohorts,
    )

    # 2. Learners
    learners = []
    for i in range(1, cfg["learners"] + 1):
        lid = f"LRN-{i:06d}"
        cid = cohorts[(i - 1) % len(cohorts)][0]
        tz_name, tz_off = TIMEZONES[int(rng.integers(0, len(TIMEZONES)))]
        is_inactive = 1 if rng.random() < 0.155 else 0
        state = "INACTIVE" if is_inactive else "ACTIVE"
        created = (base_start - timedelta(days=int(rng.integers(5, 30)))).isoformat()
        learners.append([lid, cid, tz_name, tz_off, is_inactive, state, created])
    write_csv(
        os.path.join(out_dir, "learners.csv"),
        ["learner_id", "primary_cohort_id", "home_timezone", "tz_offset_minutes", "is_inactive_baseline", "lifecycle_state", "created_at_utc"],
        learners,
    )

    # 3. Courses & CompletionRules & ContentItems & Assessments
    courses, rules, content_items, assessments = [], [], [], []
    asm_counter = 1
    for i in range(1, cfg["courses"] + 1):
        crs_id = f"CRS-{i:06d}"
        track = TRACKS[(i - 1) % len(TRACKS)]
        mods = int(rng.integers(3, 6))
        hrs = round(float(rng.uniform(8.0, 40.0)), 1)
        courses.append([crs_id, f"{track} Module Series {i}", track, mods, hrs, "PUBLISHED"])

        rul_id = f"RUL-{crs_id}-V1"
        rules.append([rul_id, crs_id, 80.00, 1, 1, 7, "ACTIVE"])

        seq = 1
        for m in range(1, mods + 1):
            mod_id = f"CNT-{crs_id}-{seq:03d}"
            content_items.append([mod_id, crs_id, "", "MODULE", f"Module {m}", 1, 30, "ACTIVE"])
            seq += 1
            for l in range(1, 3):
                les_id = f"CNT-{crs_id}-{seq:03d}"
                content_items.append([les_id, crs_id, mod_id, "LESSON_UNIT", f"Lesson {m}.{l}", 1, 20, "ACTIVE"])
                seq += 1

        asm_id = f"ASM-2026-{asm_counter:06d}"
        asm_counter += 1
        assessments.append([asm_id, crs_id, "CAPSTONE_FINAL", 70.00, 3, "PUBLISHED"])

    write_csv(os.path.join(out_dir, "courses.csv"), ["course_id", "title", "domain_track", "total_modules", "estimated_hours", "lifecycle_state"], courses)
    write_csv(os.path.join(out_dir, "completion_rules.csv"), ["rule_id", "course_id", "min_mandatory_content_pct", "require_all_exams_passed", "enforce_exam_before_completion", "grace_period_days", "lifecycle_state"], rules)
    write_csv(os.path.join(out_dir, "content_items.csv"), ["content_item_id", "course_id", "parent_content_id", "hierarchy_level", "title", "is_mandatory", "duration_minutes", "lifecycle_state"], content_items)
    write_csv(os.path.join(out_dir, "assessments.csv"), ["assessment_id", "course_id", "assessment_type", "passing_score_pct", "max_attempts", "lifecycle_state"], assessments)

    # 4. Enrollments (N:M Bridge)
    enrollments = []
    seen_pairs = set()
    enr_idx = 0
    while len(enrollments) < cfg["enrollments"]:
        lrn = learners[enr_idx % len(learners)]
        crs = courses[(enr_idx * 7 + enr_idx // len(learners)) % len(courses)]
        enr_idx += 1
        pair = (lrn[0], crs[0])
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        enr_id = f"ENR-{lrn[0]}-{crs[0]}"
        enr_dt = base_start + timedelta(days=int(rng.integers(0, 5)))
        is_withdrawn = rng.random() < 0.05
        w_dt = (enr_dt + timedelta(days=int(rng.integers(10, 25)))).isoformat() if is_withdrawn else ""
        st = "WITHDRAWN" if is_withdrawn else ("INACTIVE" if lrn[4] == 1 else "IN_PROGRESS")
        enrollments.append([enr_id, lrn[0], crs[0], lrn[1], enr_dt.isoformat(), w_dt, st])

    write_csv(os.path.join(out_dir, "enrollments.csv"), ["enrollment_id", "learner_id", "course_id", "cohort_id", "enrolled_at_utc", "withdrawn_at_utc", "current_state"], enrollments)

    # 5. Attempts & Derived Baseline Outcomes
    attempts = []
    outcomes = []
    ground_truth = []

    course_to_asm = {a[1]: a[0] for a in assessments}
    for enr in enrollments:
        enr_id, lrn_id, crs_id, _, enr_ts_str, w_ts_str, st = enr
        asm_id = course_to_asm[crs_id]
        enr_dt = datetime.fromisoformat(enr_ts_str)

        if st in ("INACTIVE", "WITHDRAWN"):
            outcomes.append([f"OUT-{enr_id}", enr_id, st, 15.00, "", "", (enr_dt + timedelta(days=20)).isoformat()])
            continue

        num_att = int(rng.integers(1, 3))
        best_score = 0.0
        pass_ts = None
        for att_n in range(1, num_att + 1):
            score = round(float(rng.uniform(45.0, 98.0)), 2)
            best_score = max(best_score, score)
            sub_dt = enr_dt + timedelta(days=int(rng.integers(14, 45)))
            is_pass = 1 if score >= 70.0 else 0
            if is_pass and pass_ts is None:
                pass_ts = sub_dt
            attempts.append([f"ATT-{asm_id}-{enr_id}-{att_n:02d}", asm_id, enr_id, att_n, score, is_pass, sub_dt.isoformat(), "GRADED"])

        content_pct = round(float(rng.uniform(60.0, 100.0)), 2)
        if pass_ts is not None and content_pct >= 80.0:
            final_st = "COMPLETED"
            comp_ts = (pass_ts + timedelta(hours=2)).isoformat()
        else:
            final_st = "IN_PROGRESS"
            comp_ts = ""

        outcomes.append([f"OUT-{enr_id}", enr_id, final_st, content_pct, best_score, comp_ts, (enr_dt + timedelta(days=50)).isoformat()])

    # Inject Edge Case 3: Completion before required assessment (~0.5% of completed outcomes, min 3)
    completed_idxs = [idx for idx, row in enumerate(outcomes) if row[2] == "COMPLETED"]
    step = max(1, len(completed_idxs) // max(3, len(outcomes) // 200))
    for idx in completed_idxs[::step]:
        bad_ts = (base_start + timedelta(days=2)).isoformat()
        outcomes[idx][5] = bad_ts
        ground_truth.append([outcomes[idx][0], "CourseOutcome", "COMPLETION_BEFORE_ASSESSMENT", "BLOCK_COMPLETION_REVERT_IN_PROGRESS", bad_ts])

    write_csv(os.path.join(out_dir, "attempts.csv"), ["attempt_id", "assessment_id", "enrollment_id", "attempt_number", "score_pct", "is_passing", "submitted_at_utc", "lifecycle_state"], attempts)
    write_csv(os.path.join(out_dir, "course_outcomes.csv"), ["outcome_id", "enrollment_id", "final_status", "derived_content_pct", "best_exam_score_pct", "completed_at_utc", "evaluated_at_utc"], outcomes)

    # 6. ActivityEvents (Streamed directly to CSV to handle 2M rows with low RAM)
    evt_path = os.path.join(out_dir, "activity_events.csv")
    active_enrs = [e for e in enrollments if e[6] not in ("INACTIVE",)]
    crs_to_cnt = {}
    for c in content_items:
        crs_to_cnt.setdefault(c[1], []).append(c[0])

    with open(evt_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["event_id", "enrollment_id", "learner_id", "course_id", "content_item_id", "client_event_uuid", "event_type", "event_timestamp_utc", "client_local_timestamp", "tz_offset_minutes", "sync_mode", "duration_seconds"])

        target_base = int(cfg["events"] * 0.98)
        for i in range(1, target_base + 1):
            enr = active_enrs[i % len(active_enrs)]
            enr_id, lrn_id, crs_id, _, enr_ts_str, _, _ = enr
            cnt_list = crs_to_cnt[crs_id]
            cnt_id = cnt_list[i % len(cnt_list)]
            ev_uuid = deterministic_uuid(rng)
            ev_type = EVENT_TYPES[i % len(EVENT_TYPES)]
            ev_utc = datetime.fromisoformat(enr_ts_str) + timedelta(hours=int(rng.integers(1, 900)))
            tz_off = 330 if i % 2 == 0 else -480
            ev_local = ev_utc + timedelta(minutes=tz_off)
            sync_mode = "MOBILE_OFFLINE_SYNC" if i % 5 == 0 else "ONLINE"
            dur = int(rng.integers(60, 1800))
            ev_id = f"EVT-{enr_id}-{i:06d}"

            writer.writerow([ev_id, enr_id, lrn_id, crs_id, cnt_id, ev_uuid, ev_type, ev_utc.isoformat(), ev_local.isoformat(), tz_off, sync_mode, dur])

            # Edge Case 1: Duplicate event inflation (~1.5%)
            if i % 67 == 0:
                dup_id = f"EVT-{enr_id}-{i:06d}-DUP"
                writer.writerow([dup_id, enr_id, lrn_id, crs_id, cnt_id, ev_uuid, ev_type, (ev_utc + timedelta(seconds=1)).isoformat(), (ev_local + timedelta(seconds=1)).isoformat(), tz_off, "MOBILE_OFFLINE_SYNC", dur])
                ground_truth.append([dup_id, "ActivityEvent", "DUPLICATE_EVENT_INFLATION", "SUPPRESS_DUPLICATE_UUID", f"dup_of={ev_id}"])

            # Edge Case 4: Timezone boundary shift (~0.1%)
            if i % 950 == 0:
                sunday_utc = base_start + timedelta(days=6, hours=21)  # Sunday 21:00 UTC -> Monday 02:30 IST
                ist_local = sunday_utc + timedelta(minutes=330)
                tz_id = f"EVT-{enr_id}-{i:06d}-TZ"
                writer.writerow([tz_id, enr_id, lrn_id, crs_id, cnt_id, deterministic_uuid(rng), "DOC_READ", sunday_utc.isoformat(), ist_local.isoformat(), 330, "ONLINE", 300])
                ground_truth.append([tz_id, "ActivityEvent", "TIMEZONE_DAY_MISASSIGNMENT", "NORMALIZE_TO_UTC_ISO_WEEK", "local_monday_is_utc_sunday"])

        # Edge Case 2: Unenrolled learner activity
        unenrolled_count = max(10, int(cfg["events"] * 0.0012))
        for j in range(1, unenrolled_count + 1):
            fake_lrn = learners[(j * 13) % len(learners)][0]
            fake_crs = courses[(j * 17) % len(courses)][0]
            fake_enr = f"ENR-{fake_lrn}-{fake_crs}"
            if (fake_lrn, fake_crs) not in seen_pairs:
                u_id = f"EVT-{fake_enr}-{j:06d}-UNENR"
                cnt_id = crs_to_cnt[fake_crs][0]
                writer.writerow([u_id, fake_enr, fake_lrn, fake_crs, cnt_id, deterministic_uuid(rng), "VIDEO_PLAY", base_start.isoformat(), base_start.isoformat(), 0, "ONLINE", 420])
                ground_truth.append([u_id, "ActivityEvent", "UNENROLLED_LEARNER_ACTIVITY", "QUARANTINE_ORPHAN_EVENT", f"missing={fake_enr}"])

    # 7. Isolated Ground Truth (never leaked into input tables)
    write_csv(
        os.path.join(out_dir, "ground_truth.csv"),
        ["entity_id", "entity_type", "issue_type", "expected_engine_action", "injected_delta"],
        ground_truth,
    )

    # 8. Source Manifest & Checksums (Step 9 & 10)
    manifest = {
        "seed": seed,
        "scale": scale_name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": "100% synthetic deterministic generation (zero external PII)",
        "checksums_sha256": {
            fname: sha256_file(os.path.join(out_dir, fname))
            for fname in sorted(os.listdir(out_dir))
            if fname.endswith(".csv")
        },
    }
    with open(os.path.join(out_dir, "source_manifest.json"), "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)

    print(f"[OK] Generated '{scale_name}' dataset with seed={seed} in {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic 3-Tier Synthetic Dataset Generator")
    parser.add_argument("--seed", type=int, default=20261022)
    parser.add_argument("--scale", choices=["starter", "full"], default="starter")
    parser.add_argument("--out", type=str, default="./data_starter")
    args = parser.parse_args()