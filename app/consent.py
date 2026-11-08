"""Caregiver consent before a community health worker (CHW) enters a child's measurements.

The CHW reads the consent text (texts.py, "consent_script") to the mother or caregiver, who answers aloud.
The CHW then taps "agreed" or "did not agree". Only the decision is recorded: when, which CHW, which
version of the text, and the language. Nothing about the caregiver or the child is written, so the record
proves consent was asked without becoming a list of families.

Settings (environment variables):
    NUTRIASSIST_CONSENT_LOG   where decisions are written (default logs/consent.jsonl; "off" records nothing)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

CONSENT_VERSION = "2026-11-08"   # change it whenever the consent text changes
DEFAULT_LOG = Path(__file__).resolve().parents[1] / "logs" / "consent.jsonl"
AGREED, DECLINED = "agreed", "declined"

log = logging.getLogger("nutriassist.consent")


def consent_log() -> Path | None:
    value = os.environ.get("NUTRIASSIST_CONSENT_LOG", "").strip()
    if value.lower() in ("off", "none", "0"):
        return None
    return Path(value) if value else DEFAULT_LOG


def record_consent(decision: str, chw_id: str | None, language: str, path: Path | None = None,
                   now: datetime | None = None) -> dict:
    """Write one consent decision and return the row. A disk that cannot be written does not stop the CHW."""
    if decision not in (AGREED, DECLINED):
        raise ValueError(f"decision must be {AGREED!r} or {DECLINED!r}")
    row = {"time": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
           "chw_id": chw_id or "not signed in", "decision": decision,
           "consent_version": CONSENT_VERSION, "language": language}
    path = path if path is not None else consent_log()
    if path is not None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
        except OSError:
            log.warning("Could not write %s", path, exc_info=True)
    return row
