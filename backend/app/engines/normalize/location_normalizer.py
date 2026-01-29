"""Location normalization and classification."""

import re
from typing import Optional, Tuple


class LocationNormalizer:
    """Normalizes and classifies job locations."""

    # Remote indicators
    REMOTE_PATTERNS = [
        r"\bremote\b",
        r"\bwork\s*from\s*home\b",
        r"\bwfh\b",
        r"\bdistributed\b",
        r"\banywhere\b",
        r"\bfully\s*remote\b",
        r"\b100%\s*remote\b",
    ]

    # Hybrid indicators
    HYBRID_PATTERNS = [
        r"\bhybrid\b",
        r"\bflexible\b",
        r"\bremote.*office\b",
        r"\boffice.*remote\b",
        r"\b\d+\s*days?\s*(in\s*)?office\b",
    ]

    # On-site indicators
    ONSITE_PATTERNS = [
        r"\bon-?site\b",
        r"\bin-?office\b",
        r"\bin\s*person\b",
        r"\boffice\s*based\b",
        r"\bno\s*remote\b",
    ]

    # Country patterns for remote restrictions
    COUNTRY_PATTERNS = {
        "US": [r"\bus\b", r"\bu\.s\.\b", r"\bunited\s*states\b", r"\bamerica\b"],
        "UK": [r"\buk\b", r"\bu\.k\.\b", r"\bunited\s*kingdom\b", r"\bbritain\b", r"\bengland\b"],
        "EU": [r"\beu\b", r"\beurope\b", r"\beuropean\b"],
        "Canada": [r"\bcanada\b", r"\bcanadian\b"],
        "Australia": [r"\baustralia\b", r"\baustralian\b"],
        "Germany": [r"\bgermany\b", r"\bgerman\b"],
        "France": [r"\bfrance\b", r"\bfrench\b"],
        "India": [r"\bindia\b", r"\bindian\b"],
    }

    # US State abbreviations
    US_STATES = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC",
    }

    # Major tech hub cities
    TECH_HUBS = {
        "san francisco": "San Francisco, CA",
        "sf": "San Francisco, CA",
        "bay area": "San Francisco Bay Area, CA",
        "silicon valley": "San Francisco Bay Area, CA",
        "new york": "New York, NY",
        "nyc": "New York, NY",
        "los angeles": "Los Angeles, CA",
        "la": "Los Angeles, CA",
        "seattle": "Seattle, WA",
        "austin": "Austin, TX",
        "boston": "Boston, MA",
        "chicago": "Chicago, IL",
        "denver": "Denver, CO",
        "miami": "Miami, FL",
        "london": "London, UK",
        "berlin": "Berlin, Germany",
        "toronto": "Toronto, Canada",
        "vancouver": "Vancouver, Canada",
        "bangalore": "Bangalore, India",
        "bangalore": "Bangalore, India",
        "sydney": "Sydney, Australia",
        "dublin": "Dublin, Ireland",
        "amsterdam": "Amsterdam, Netherlands",
        "paris": "Paris, France",
        "singapore": "Singapore",
        "tokyo": "Tokyo, Japan",
    }

    def __init__(self):
        self.remote_re = [re.compile(p, re.IGNORECASE) for p in self.REMOTE_PATTERNS]
        self.hybrid_re = [re.compile(p, re.IGNORECASE) for p in self.HYBRID_PATTERNS]
        self.onsite_re = [re.compile(p, re.IGNORECASE) for p in self.ONSITE_PATTERNS]
        self.country_re = {
            country: [re.compile(p, re.IGNORECASE) for p in patterns]
            for country, patterns in self.COUNTRY_PATTERNS.items()
        }

    def normalize(self, location_raw: str) -> Tuple[Optional[str], list[str]]:
        """
        Normalize location string.

        Returns:
            Tuple of (location_type, locations_list)
            - location_type: 'remote', 'hybrid', 'onsite', or None
            - locations_list: List of normalized location strings
        """
        if not location_raw:
            return None, []

        location_raw = location_raw.strip()

        # Detect location type
        location_type = self._detect_type(location_raw)

        # Extract and normalize locations
        locations = self._extract_locations(location_raw)

        return location_type, locations

    def _detect_type(self, text: str) -> Optional[str]:
        """Detect location type (remote/hybrid/onsite)."""
        # Check for explicit remote
        for pattern in self.remote_re:
            if pattern.search(text):
                # Check if it's actually hybrid
                for hybrid_pattern in self.hybrid_re:
                    if hybrid_pattern.search(text):
                        return "hybrid"
                return "remote"

        # Check for hybrid
        for pattern in self.hybrid_re:
            if pattern.search(text):
                return "hybrid"

        # Check for on-site
        for pattern in self.onsite_re:
            if pattern.search(text):
                return "onsite"

        # If it's just a city/location, assume on-site
        if self._looks_like_location(text):
            return "onsite"

        return None

    def _looks_like_location(self, text: str) -> bool:
        """Check if text looks like a physical location."""
        # Check for known cities
        text_lower = text.lower()
        for city in self.TECH_HUBS:
            if city in text_lower:
                return True

        # Check for state abbreviations
        for state in self.US_STATES:
            if re.search(rf"\b{state}\b", text):
                return True

        # Check for country patterns
        for patterns in self.country_re.values():
            for pattern in patterns:
                if pattern.search(text):
                    return True

        # Check for city, state pattern
        if re.search(r"[A-Za-z]+,\s*[A-Z]{2}", text):
            return True

        return False

    def _extract_locations(self, text: str) -> list[str]:
        """Extract and normalize location names."""
        locations = []
        text_lower = text.lower()

        # Check for known tech hubs
        for hub_key, hub_name in self.TECH_HUBS.items():
            if hub_key in text_lower:
                if hub_name not in locations:
                    locations.append(hub_name)

        # Check for country mentions
        for country, patterns in self.country_re.items():
            for pattern in patterns:
                if pattern.search(text):
                    if country not in locations:
                        locations.append(country)

        # If no known locations found, try to parse as-is
        if not locations:
            # Clean up and use original
            cleaned = self._clean_location(text)
            if cleaned:
                locations.append(cleaned)

        return locations

    def _clean_location(self, text: str) -> Optional[str]:
        """Clean up a location string."""
        # Remove common prefixes/suffixes
        text = re.sub(r"^\s*(located?\s*(in|at)?|based\s*(in|at)?)\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*(area|region|office)?\s*$", "", text, flags=re.IGNORECASE)

        # Remove remote/hybrid indicators
        for pattern in self.remote_re + self.hybrid_re:
            text = pattern.sub("", text)

        # Clean whitespace
        text = " ".join(text.split())
        text = text.strip(" ,;-")

        return text if text and len(text) > 1 else None
