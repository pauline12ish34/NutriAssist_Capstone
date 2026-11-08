"""Caregiver consent record (app/consent.py) and the 90-day limit on unanswered questions (privacy policy)."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from consent import AGREED, CONSENT_VERSION, DECLINED, consent_log, record_consent  # noqa: E402
from nutriassist.api.app import UNANSWERED_KEEP_DAYS, prune_log  # noqa: E402

NOW = datetime(2026, 11, 8, 10, 0, tzinfo=timezone.utc)


def test_consent_record_holds_the_decision_and_nothing_about_the_family(tmp_path):
    path = tmp_path / "consent.jsonl"
    record_consent(AGREED, "CHW-DEMO-001", "rw", path=path, now=NOW)
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row == {"time": "2026-11-08T10:00:00+00:00", "chw_id": "CHW-DEMO-001", "decision": "agreed",
                   "consent_version": CONSENT_VERSION, "language": "rw"}


def test_a_refusal_is_recorded_too(tmp_path):
    path = tmp_path / "consent.jsonl"
    record_consent(AGREED, "CHW-DEMO-001", "en", path=path)
    record_consent(DECLINED, None, "en", path=path)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [r["decision"] for r in rows] == ["agreed", "declined"]
    assert rows[1]["chw_id"] == "not signed in"


def test_only_agreed_or_declined_is_accepted(tmp_path):
    with pytest.raises(ValueError):
        record_consent("maybe", "CHW-DEMO-001", "en", path=tmp_path / "c.jsonl")


def test_consent_log_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("NUTRIASSIST_CONSENT_LOG", "off")
    assert consent_log() is None


def test_unanswered_questions_older_than_90_days_are_deleted(tmp_path):
    path = tmp_path / "unanswered.jsonl"
    rows = [{"time": (NOW - timedelta(days=d)).isoformat(), "question": f"q{d}"} for d in (1, 89, 91, 400)]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows) + "not json\n", encoding="utf-8")
    assert prune_log(path, UNANSWERED_KEEP_DAYS, now=NOW) == 3
    kept = [json.loads(line)["question"] for line in path.read_text(encoding="utf-8").splitlines()]
    assert kept == ["q1", "q89"]


def test_pruning_a_missing_log_does_nothing(tmp_path):
    assert prune_log(tmp_path / "none.jsonl", UNANSWERED_KEEP_DAYS) == 0
