"""Base class and models for discovery sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, Optional, Set


class DeduplicationService:
    """Shared deduplication across all discovery sources.
    
    This service allows sources to check early if a domain/ATS is already known,
    preventing expensive HTTP requests for companies that will be skipped anyway.
    """
    
    def __init__(self):
        self._existing_domains: Set[str] = set()
        self._discovered_domains: Set[str] = set()
        self._existing_ats: Set[str] = set()  # "ats_type:identifier" pairs
    
    def load_existing(
        self, 
        domains: Set[str], 
        queued: Set[str],
        ats_pairs: Optional[Set[str]] = None,
    ):
        """Load existing data from database.
        
        Args:
            domains: Set of existing company domains
            queued: Set of domains in discovery queue
            ats_pairs: Set of "ats_type:identifier" strings for existing ATS boards
        """
        self._existing_domains = domains | queued
        if ats_pairs:
            self._existing_ats = ats_pairs
    
    def is_domain_known(self, domain: str) -> bool:
        """Check if domain already exists or was discovered this run."""
        if not domain:
            return False
        domain = domain.lower()
        return domain in self._existing_domains or domain in self._discovered_domains
    
    def is_ats_known(self, ats_type: str, identifier: str) -> bool:
        """Check if ATS board already exists."""
        if not ats_type or not identifier:
            return False
        key = f"{ats_type}:{identifier.lower()}"
        return key in self._existing_ats
    
    def mark_discovered(self, domain: str, ats_type: str = None, ats_identifier: str = None):
        """Mark a domain/ATS as discovered during this run."""
        if domain:
            self._discovered_domains.add(domain.lower())
        if ats_type and ats_identifier:
            self._existing_ats.add(f"{ats_type}:{ats_identifier.lower()}")
    
    @property
    def discovered_count(self) -> int:
        """Number of domains discovered in this run."""
        return len(self._discovered_domains)


@dataclass
class DiscoveredCompany:
    """A company discovered from a source."""
    
    name: str
    domain: Optional[str] = None
    careers_url: Optional[str] = None
    website_url: Optional[str] = None
    
    # Source metadata
    source: str = ""  # e.g., "ats_greenhouse", "yc_directory", "github"
    source_url: Optional[str] = None  # URL where this company was found
    
    # Location info (for US filtering)
    location: Optional[str] = None
    country: Optional[str] = None
    
    # Additional context
    description: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    funding_stage: Optional[str] = None
    
    # ATS info if detected
    ats_type: Optional[str] = None
    ats_identifier: Optional[str] = None
    
    # Timestamp
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Normalize domain from website URL if not provided."""
        if not self.domain and self.website_url:
            from urllib.parse import urlparse
            parsed = urlparse(self.website_url)
            if parsed.netloc:
                # Remove www. prefix
                domain = parsed.netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                self.domain = domain
        
        # Also extract domain from careers_url if still no domain
        if not self.domain and self.careers_url:
            from urllib.parse import urlparse
            parsed = urlparse(self.careers_url)
            if parsed.netloc:
                # Skip if it's an ATS domain
                netloc = parsed.netloc.lower()
                ats_domains = [
                    "greenhouse.io", "lever.co", "ashbyhq.com",
                    "workday.com", "myworkdayjobs.com"
                ]
                if not any(ats in netloc for ats in ats_domains):
                    domain = netloc
                    if domain.startswith("www."):
                        domain = domain[4:]
                    self.domain = domain


@dataclass
class DiscoveryStats:
    """Statistics for a discovery run."""
    
    source: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    total_discovered: int = 0
    new_companies: int = 0
    updated_companies: int = 0
    skipped_duplicates: int = 0
    filtered_non_us: int = 0
    errors: int = 0
    
    def duration_seconds(self) -> Optional[float]:
        """Get duration of the run in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class DiscoverySource(ABC):
    """Abstract base class for discovery sources.
    
    Each source should implement the discover() method which yields
    DiscoveredCompany objects. The source should handle its own rate
    limiting and error handling.
    """
    
    # Shared deduplication service (injected by orchestrator)
    dedup: Optional[DeduplicationService] = None
    
    # Progress tracking - sources can set these for UI updates
    _progress_total: int = 0
    _progress_current: int = 0
    
    def set_dedup_service(self, dedup: DeduplicationService):
        """Set shared deduplication service."""
        self.dedup = dedup
    
    @property
    def progress_total(self) -> int:
        """Total items to process (if known). Override or set _progress_total."""
        return self._progress_total
    
    @property
    def progress_current(self) -> int:
        """Current item being processed. Override or set _progress_current."""
        return self._progress_current
    
    def is_duplicate(self, domain: str) -> bool:
        """Check if domain is duplicate (use before yielding).
        
        Call this early in discovery to skip expensive operations
        for companies we already know about.
        """
        if self.dedup:
            return self.dedup.is_domain_known(domain)
        return False
    
    def is_ats_duplicate(self, ats_type: str, identifier: str) -> bool:
        """Check if ATS board is duplicate."""
        if self.dedup:
            return self.dedup.is_ats_known(ats_type, identifier)
        return False
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this source."""
        pass
    
    @property
    def source_description(self) -> str:
        """Human-readable description of this source."""
        return self.source_name
    
    @abstractmethod
    async def discover(self) -> AsyncIterator[DiscoveredCompany]:
        """Yield discovered companies from this source.
        
        Implementations should:
        - Handle rate limiting appropriately
        - Log errors but continue processing
        - Set the source field on each DiscoveredCompany
        - Yield companies as they are found (for streaming processing)
        - Use self.is_duplicate(domain) to skip known companies early
        """
        pass
    
    async def initialize(self) -> None:
        """Initialize the source (e.g., setup HTTP clients).
        
        Override if your source needs initialization.
        """
        pass
    
    async def cleanup(self) -> None:
        """Cleanup resources (e.g., close HTTP clients).
        
        Override if your source needs cleanup.
        """
        pass
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
        return False
