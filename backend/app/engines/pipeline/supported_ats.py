"""Supported ATS Types Configuration.

These ATS types have reliable API/scraping methods and can be processed
with a one-click pipeline (crawl -> enrich -> embeddings).

Add new ATS types here as they are validated and tested.
"""

from typing import List, Set

# ATS types with reliable enrichment methods
# These support one-click processing: crawl -> enrich -> embeddings
SUPPORTED_ATS_TYPES: List[str] = [
    "greenhouse",   # API: boards-api.greenhouse.io
    "lever",        # JSON-LD extraction
    "ashby",        # API: api.ashbyhq.com
    "workable",     # API: apply.workable.com/api/v2
    "jobvite",      # JSON-LD extraction (generic)
    "workday",      # Generic JSON-LD (mostly BuiltIn URLs)
]

# Cache as a set for O(1) lookup
_SUPPORTED_ATS_SET: Set[str] = set(SUPPORTED_ATS_TYPES)


def is_supported_ats(ats_type: str | None) -> bool:
    """Check if an ATS type is in the supported list."""
    if not ats_type:
        return False
    return ats_type.lower() in _SUPPORTED_ATS_SET


def get_supported_ats_types() -> List[str]:
    """Get the list of supported ATS types."""
    return SUPPORTED_ATS_TYPES.copy()


def add_supported_ats(ats_type: str) -> bool:
    """Add a new ATS type to the supported list (runtime only).
    
    For permanent changes, update SUPPORTED_ATS_TYPES in this file.
    Returns True if added, False if already exists.
    """
    global _SUPPORTED_ATS_SET
    ats_lower = ats_type.lower()
    if ats_lower in _SUPPORTED_ATS_SET:
        return False
    SUPPORTED_ATS_TYPES.append(ats_lower)
    _SUPPORTED_ATS_SET.add(ats_lower)
    return True


def remove_supported_ats(ats_type: str) -> bool:
    """Remove an ATS type from the supported list (runtime only).
    
    For permanent changes, update SUPPORTED_ATS_TYPES in this file.
    Returns True if removed, False if not found.
    """
    global _SUPPORTED_ATS_SET
    ats_lower = ats_type.lower()
    if ats_lower not in _SUPPORTED_ATS_SET:
        return False
    SUPPORTED_ATS_TYPES.remove(ats_lower)
    _SUPPORTED_ATS_SET.remove(ats_lower)
    return True
