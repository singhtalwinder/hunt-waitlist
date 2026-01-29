"""Role family and specialization mapping."""

import re
from typing import Optional, Tuple

# Map from frontend TECH_FIELDS to role families
FIELD_TO_ROLE_FAMILY = {
    "Software Engineering": "software_engineering",
    "Frontend Development": "software_engineering",
    "Backend Development": "software_engineering",
    "Full Stack Development": "software_engineering",
    "Mobile Development (iOS)": "software_engineering",
    "Mobile Development (Android)": "software_engineering",
    "DevOps / SRE": "infrastructure",
    "Cloud / Infrastructure": "infrastructure",
    "Data Engineering": "data",
    "Data Science": "data",
    "Machine Learning / AI": "data",
    "Security Engineering": "infrastructure",
    "QA / Testing": "software_engineering",
    "Product Management": "product",
    "Product Design": "design",
    "UX Research": "design",
    "UI/UX Design": "design",
    "Technical Program Management": "product",
    "Engineering Management": "engineering_management",
    "Solutions Architecture": "infrastructure",
    "Technical Writing": "other",
    "Developer Relations": "marketing",
    "Sales Engineering": "sales",
    "Sales / Account Executive": "sales",
    "Business Development": "sales",
    "Customer Success": "customer_success",
    "Marketing": "marketing",
    "Growth Marketing": "marketing",
    "Content Marketing": "marketing",
    "Product Marketing": "marketing",
    "Operations": "operations",
    "People / HR": "people",
    "Finance": "finance",
    "Legal": "legal",
    "Other": "other",
}

# Title patterns for role family detection
ROLE_PATTERNS = {
    "software_engineering": [
        r"software\s*engineer",
        r"developer",
        r"programmer",
        r"frontend",
        r"front-end",
        r"backend",
        r"back-end",
        r"fullstack",
        r"full-stack",
        r"mobile\s*(developer|engineer)",
        r"ios\s*(developer|engineer)",
        r"android\s*(developer|engineer)",
        r"web\s*(developer|engineer)",
        r"api\s*(developer|engineer)",
        r"platform\s*engineer",
        r"qa\s*engineer",
        r"quality\s*engineer",
        r"test\s*engineer",
        r"sdet",
    ],
    "infrastructure": [
        r"devops",
        r"sre",
        r"site\s*reliability",
        r"infrastructure",
        r"platform",
        r"cloud\s*engineer",
        r"systems?\s*engineer",
        r"network\s*engineer",
        r"security\s*engineer",
        r"solutions?\s*architect",
    ],
    "data": [
        r"data\s*engineer",
        r"data\s*scientist",
        r"machine\s*learning",
        r"ml\s*engineer",
        r"ai\s*engineer",
        r"analytics",
        r"data\s*analyst",
        r"business\s*intelligence",
    ],
    "product": [
        r"product\s*manager",
        r"program\s*manager",
        r"technical\s*program",
        r"project\s*manager",
        r"scrum\s*master",
    ],
    "design": [
        r"product\s*designer",
        r"ux\s*designer",
        r"ui\s*designer",
        r"ux/ui",
        r"user\s*experience",
        r"user\s*interface",
        r"ux\s*researcher",
        r"design\s*lead",
    ],
    "engineering_management": [
        r"engineering\s*manager",
        r"eng\s*manager",
        r"technical\s*lead",
        r"tech\s*lead",
        r"team\s*lead",
        r"director.*engineering",
        r"vp.*engineering",
        r"head\s*of\s*engineering",
        r"cto",
    ],
    "sales": [
        r"sales\s*engineer",
        r"solutions?\s*engineer",
        r"account\s*executive",
        r"sales\s*representative",
        r"business\s*development",
        r"sales\s*manager",
    ],
    "marketing": [
        r"marketing",
        r"growth",
        r"content\s*writer",
        r"copywriter",
        r"developer\s*advocate",
        r"developer\s*relations",
        r"devrel",
    ],
    "customer_success": [
        r"customer\s*success",
        r"customer\s*support",
        r"support\s*engineer",
        r"technical\s*support",
    ],
    "operations": [
        r"operations",
        r"ops\s*manager",
        r"business\s*operations",
    ],
    "people": [
        r"recruiter",
        r"talent",
        r"hr\s*",
        r"human\s*resources",
        r"people\s*",
    ],
    "finance": [
        r"finance",
        r"accountant",
        r"financial",
        r"controller",
        r"cfo",
    ],
    "legal": [
        r"legal",
        r"counsel",
        r"attorney",
        r"lawyer",
        r"compliance",
    ],
}

# Specialization patterns
SPECIALIZATION_PATTERNS = {
    "frontend": [r"frontend", r"front-end", r"front end", r"react", r"vue", r"angular", r"ui\s*engineer"],
    "backend": [r"backend", r"back-end", r"back end", r"server", r"api"],
    "fullstack": [r"fullstack", r"full-stack", r"full stack"],
    "mobile": [r"mobile", r"ios", r"android", r"react\s*native", r"flutter"],
    "ios": [r"\bios\b", r"swift", r"objective-c"],
    "android": [r"android", r"kotlin"],
    "devops": [r"devops", r"dev\s*ops"],
    "sre": [r"\bsre\b", r"site\s*reliability"],
    "ml": [r"machine\s*learning", r"\bml\b", r"deep\s*learning"],
    "data": [r"data\s*engineer", r"data\s*pipeline", r"etl"],
    "security": [r"security", r"infosec", r"appsec", r"cybersecurity"],
    "cloud": [r"\baws\b", r"azure", r"\bgcp\b", r"cloud"],
    "platform": [r"platform"],
}


class RoleMapper:
    """Maps job titles to role families and specializations."""

    def __init__(self):
        # Compile patterns
        self.role_patterns = {
            family: [re.compile(p, re.IGNORECASE) for p in patterns]
            for family, patterns in ROLE_PATTERNS.items()
        }
        self.spec_patterns = {
            spec: [re.compile(p, re.IGNORECASE) for p in patterns]
            for spec, patterns in SPECIALIZATION_PATTERNS.items()
        }

    def map_title(self, title: str) -> Tuple[str, Optional[str]]:
        """
        Map a job title to role family and specialization.

        Returns:
            Tuple of (role_family, role_specialization)
        """
        # Detect role family
        role_family = self._detect_role_family(title)

        # Detect specialization
        specialization = self._detect_specialization(title)

        return role_family, specialization

    def _detect_role_family(self, title: str) -> str:
        """Detect role family from title."""
        for family, patterns in self.role_patterns.items():
            for pattern in patterns:
                if pattern.search(title):
                    return family

        return "other"

    def _detect_specialization(self, title: str) -> Optional[str]:
        """Detect role specialization from title."""
        for spec, patterns in self.spec_patterns.items():
            for pattern in patterns:
                if pattern.search(title):
                    return spec

        return None


def map_field_to_role_families(field: str) -> list[str]:
    """
    Map a frontend TECH_FIELD to role families for matching.

    Returns list since some fields map to multiple families.
    """
    role_family = FIELD_TO_ROLE_FAMILY.get(field, "other")
    return [role_family]
