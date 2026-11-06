"""Demo sign-in for community health workers (CHWs).

The demo checks a CHW ID against data/reference/demo_chw_ids.csv (made-up IDs, none belongs to a real person)
and a fixed code that stands in for a one-time code sent by SMS.

In a real rollout, ``DemoChwDirectory`` would be replaced by a lookup against the Ministry of Health's CHW records
(under a data-sharing agreement), and ``code_is_valid`` by a one-time SMS code sent to the phone number on record.
The app keeps only the signed-in CHW ID in the browser session; it stores nothing about the CHW.

Settings (environment variables, or Space secrets on Hugging Face):
    NUTRIASSIST_LOGIN       "off" turns the sign-in page off (default: on)
    NUTRIASSIST_DEMO_CODE   the code to accept (default: 123456; set a secret one on a public deployment)
"""

from __future__ import annotations

import csv
import hmac
import os
from dataclasses import dataclass
from pathlib import Path

DEMO_IDS = Path(__file__).resolve().parents[1] / "data" / "reference" / "demo_chw_ids.csv"
DEFAULT_CODE = "123456"
MAX_ATTEMPTS = 5   # wrong attempts allowed in one browser session


def login_required() -> bool:
    return os.environ.get("NUTRIASSIST_LOGIN", "on").strip().lower() not in ("off", "0", "false", "no")


def normalise(chw_id: str) -> str:
    """'  chw-demo-001 ' -> 'CHW-DEMO-001'."""
    return chw_id.strip().upper()


@dataclass(frozen=True)
class Chw:
    chw_id: str
    district: str


class DemoChwDirectory:
    """The CHWs allowed to sign in. Only active ones are kept, as a real registry would report them."""

    def __init__(self, path: Path = DEMO_IDS) -> None:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self._active = {normalise(row["chw_id"]): Chw(normalise(row["chw_id"]), row["district"].strip())
                        for row in rows if row["active"].strip().lower() == "yes"}

    def find(self, chw_id: str) -> Chw | None:
        return self._active.get(normalise(chw_id))

    def __len__(self) -> int:
        return len(self._active)


def expected_code() -> str:
    return os.environ.get("NUTRIASSIST_DEMO_CODE", "").strip() or DEFAULT_CODE


def code_is_valid(code: str, expected: str | None = None) -> bool:
    # compare_digest takes the same time whatever the input, so the code cannot be guessed one digit at a time.
    return hmac.compare_digest(code.strip().encode(), (expected or expected_code()).encode())


def sign_in(directory: DemoChwDirectory, chw_id: str, code: str) -> Chw | None:
    """The CHW when both the ID and the code are right, else None.

    The caller shows one message for every failure, so the page does not reveal which IDs exist.
    """
    chw = directory.find(chw_id)
    return chw if chw is not None and code_is_valid(code) else None
