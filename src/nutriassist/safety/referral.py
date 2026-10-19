"""Recognise answers that send the caregiver to a health service."""

from __future__ import annotations

import re
from typing import Sequence

# Phrases the reference answers use to send caregivers to health services.
REFERRAL_PATTERNS = (
    r"health (?:centre|center|facility|post|worker)s?",
    r"health ?care (?:provider|worker)s?", r"hospital", r"clinic", r"doctor", r"nurse", r"community health",
    r"[kb]igo nderabuzima", r"muganga", r"abaganga", r"ivuriro", r"ibitaro",
    r"umujyanama w'ubuzima", r"abajyanama b'ubuzima",
)


class ReferralDetector:
    """Does an answer send the caregiver to a health service?"""

    def __init__(self, patterns: Sequence[str] = REFERRAL_PATTERNS) -> None:
        self._pattern = re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)

    def refers(self, text: str) -> bool:
        return bool(self._pattern.search(text))
