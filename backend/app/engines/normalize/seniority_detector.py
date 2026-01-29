"""Seniority level detection from job titles and descriptions."""

import re
from typing import Optional


class SeniorityDetector:
    """Detects seniority level from job titles and descriptions."""

    # Title patterns by seniority (checked in order)
    TITLE_PATTERNS = {
        "c_level": [
            r"\bceo\b",
            r"\bcto\b",
            r"\bcfo\b",
            r"\bcoo\b",
            r"\bcmo\b",
            r"\bchief\b",
            r"\bco-founder\b",
            r"\bfounder\b",
        ],
        "vp": [
            r"\bvp\b",
            r"\bvice\s*president\b",
            r"\bsvp\b",
            r"\bevp\b",
        ],
        "director": [
            r"\bdirector\b",
            r"\bhead\s+of\b",
        ],
        "principal": [
            r"\bprincipal\b",
            r"\bdistinguished\b",
            r"\bfellow\b",
        ],
        "staff": [
            r"\bstaff\b",
            r"\bsr\.\s*staff\b",
        ],
        "senior": [
            r"\bsenior\b",
            r"\bsr\.?\b",
            r"\bsr\s+",
            r"\blead\b",
        ],
        "mid": [
            # Mid-level is often default, but some explicit patterns
            r"\bmid-?level\b",
            r"\bintermediate\b",
            r"\bii\b",  # Level II
        ],
        "junior": [
            r"\bjunior\b",
            r"\bjr\.?\b",
            r"\bentry\s*level\b",
            r"\bnew\s*grad\b",
            r"\bgraduate\b",
            r"\bi\b",  # Level I (end of title)
        ],
        "intern": [
            r"\bintern\b",
            r"\binternship\b",
            r"\bco-?op\b",
        ],
    }

    # Years of experience patterns
    EXPERIENCE_PATTERNS = [
        (r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)", lambda x: int(x)),
        (r"(\d+)-(\d+)\s*(?:years?|yrs?)", lambda x, y: (int(x) + int(y)) // 2),
    ]

    # Experience to seniority mapping
    EXPERIENCE_TO_SENIORITY = [
        (0, 1, "intern"),
        (1, 2, "junior"),
        (2, 5, "mid"),
        (5, 8, "senior"),
        (8, 12, "staff"),
        (12, float("inf"), "principal"),
    ]

    def __init__(self):
        self.title_patterns = {
            seniority: [re.compile(p, re.IGNORECASE) for p in patterns]
            for seniority, patterns in self.TITLE_PATTERNS.items()
        }
        self.experience_patterns = [
            (re.compile(p, re.IGNORECASE), fn) for p, fn in self.EXPERIENCE_PATTERNS
        ]

    def detect(self, title: str, description: str = "") -> Optional[str]:
        """
        Detect seniority level from title and description.

        Returns one of: intern, junior, mid, senior, staff, principal, director, vp, c_level
        """
        # Check title patterns first (most reliable)
        title_seniority = self._detect_from_title(title)
        if title_seniority:
            return title_seniority

        # Check experience requirements in description
        if description:
            exp_seniority = self._detect_from_experience(description)
            if exp_seniority:
                return exp_seniority

        # Default to mid if can't determine
        return "mid"

    def _detect_from_title(self, title: str) -> Optional[str]:
        """Detect seniority from title patterns."""
        for seniority, patterns in self.title_patterns.items():
            for pattern in patterns:
                if pattern.search(title):
                    return seniority

        return None

    def _detect_from_experience(self, description: str) -> Optional[str]:
        """Detect seniority from experience requirements in description."""
        for pattern, extractor in self.experience_patterns:
            match = pattern.search(description)
            if match:
                try:
                    years = extractor(*match.groups())
                    return self._years_to_seniority(years)
                except (ValueError, TypeError):
                    continue

        return None

    def _years_to_seniority(self, years: int) -> str:
        """Convert years of experience to seniority level."""
        for min_years, max_years, seniority in self.EXPERIENCE_TO_SENIORITY:
            if min_years <= years < max_years:
                return seniority

        return "senior"  # Default for edge cases
