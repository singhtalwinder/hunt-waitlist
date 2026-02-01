"""SQLAlchemy database models."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Company(Base):
    """Company with job listings to crawl."""

    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    careers_url: Mapped[Optional[str]] = mapped_column(Text)
    website_url: Mapped[Optional[str]] = mapped_column(Text)
    ats_type: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # greenhouse, lever, ashby, workday, custom
    ats_identifier: Mapped[Optional[str]] = mapped_column(
        String(255)
    )  # e.g., "stripe" for greenhouse
    crawl_priority: Mapped[int] = mapped_column(Integer, default=50)
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Discovery metadata
    discovery_source: Mapped[Optional[str]] = mapped_column(
        String(100)
    )  # e.g., "ats_greenhouse", "yc_directory", "github"
    discovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    country: Mapped[Optional[str]] = mapped_column(String(2))  # ISO country code (US, etc.)
    location: Mapped[Optional[str]] = mapped_column(Text)  # Full location string
    description: Mapped[Optional[str]] = mapped_column(Text)
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    employee_count: Mapped[Optional[int]] = mapped_column(Integer)
    funding_stage: Mapped[Optional[str]] = mapped_column(String(50))
    
    # ATS detection tracking
    ats_detection_attempts: Mapped[int] = mapped_column(Integer, default=0)
    ats_detection_last_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Parent company relationship (for subsidiaries/brands that use parent's ATS)
    parent_company_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL")
    )
    
    # Maintenance tracking
    last_maintenance_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Network crawler tracking (for discovering new companies from existing ones)
    last_crawled_for_network: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    snapshots: Mapped[list["CrawlSnapshot"]] = relationship(back_populates="company")
    jobs_raw: Mapped[list["JobRaw"]] = relationship(back_populates="company")
    jobs: Mapped[list["Job"]] = relationship(back_populates="company")


class CrawlSnapshot(Base):
    """Raw crawled page snapshot for debugging and replay."""

    __tablename__ = "crawl_snapshots"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    html_hash: Mapped[Optional[str]] = mapped_column(String(64))  # SHA256
    html_content: Mapped[Optional[str]] = mapped_column(Text)  # Store raw HTML
    status_code: Mapped[Optional[int]] = mapped_column(Integer)
    rendered: Mapped[bool] = mapped_column(Boolean, default=False)  # Was JS rendered?
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="snapshots")


class JobRaw(Base):
    """Raw extracted job before normalization."""

    __tablename__ = "jobs_raw"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title_raw: Mapped[Optional[str]] = mapped_column(Text)
    description_raw: Mapped[Optional[str]] = mapped_column(Text)
    location_raw: Mapped[Optional[str]] = mapped_column(Text)
    department_raw: Mapped[Optional[str]] = mapped_column(Text)
    employment_type_raw: Mapped[Optional[str]] = mapped_column(Text)
    posted_at_raw: Mapped[Optional[str]] = mapped_column(Text)
    salary_raw: Mapped[Optional[str]] = mapped_column(Text)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="jobs_raw")
    job: Mapped[Optional["Job"]] = relationship(back_populates="raw_job")

    __table_args__ = (
        # Unique constraint on company + source URL
        {"postgresql_partition_by": None},
    )


class Job(Base):
    """Canonical normalized job."""

    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    raw_job_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs_raw.id", ondelete="SET NULL")
    )

    # Core fields
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Normalized fields
    role_family: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # software_engineering, product, design, etc.
    role_specialization: Mapped[Optional[str]] = mapped_column(
        String(100)
    )  # frontend, backend, fullstack, etc.
    seniority: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # junior, mid, senior, staff, director
    location_type: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # remote, hybrid, onsite
    locations: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    skills: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    min_salary: Mapped[Optional[int]] = mapped_column(Integer)
    max_salary: Mapped[Optional[int]] = mapped_column(Integer)
    employment_type: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # full_time, contract, etc.

    # Metadata
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    freshness_score: Mapped[Optional[float]] = mapped_column(Float)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Maintenance tracking
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delisted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delist_reason: Mapped[Optional[str]] = mapped_column(
        String(100)
    )  # removed_from_ats, company_inactive, page_not_found
    
    # Enrichment tracking - prevents infinite retries on permanently failing jobs
    enrich_failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="jobs")
    raw_job: Mapped[Optional["JobRaw"]] = relationship(back_populates="job")
    matches: Mapped[list["Match"]] = relationship(back_populates="job")
    board_listings: Mapped[list["JobBoardListing"]] = relationship(back_populates="job")


class CandidateProfile(Base):
    """Candidate profile for matching."""

    __tablename__ = "candidate_profiles"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    waitlist_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), unique=True
    )  # Reference to waitlist table
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))

    # Preferences (normalized from waitlist_details)
    role_families: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    seniority: Mapped[Optional[str]] = mapped_column(String(50))
    min_salary: Mapped[Optional[int]] = mapped_column(Integer)
    locations: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    location_types: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text)
    )  # remote, hybrid, onsite
    role_types: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text)
    )  # permanent, contract
    skills: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    exclusions: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text)
    )  # Companies/keywords to exclude

    # Matching
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384))
    last_matched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    matches: Mapped[list["Match"]] = relationship(back_populates="candidate")


class Match(Base):
    """Job match result for a candidate."""

    __tablename__ = "matches"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    candidate_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    job_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE")
    )

    # Match details
    score: Mapped[float] = mapped_column(Float, nullable=False)
    hard_match: Mapped[bool] = mapped_column(Boolean, default=False)
    match_reasons: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Tracking
    shown_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    candidate: Mapped["CandidateProfile"] = relationship(back_populates="matches")
    job: Mapped["Job"] = relationship(back_populates="matches")

    __table_args__ = (
        # Unique constraint on candidate + job
        {"postgresql_partition_by": None},
    )


class Metric(Base):
    """System metrics for monitoring."""

    __tablename__ = "metrics"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    labels: Mapped[Optional[dict]] = mapped_column(JSONB)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DiscoveryQueue(Base):
    """Queue for discovered companies pending processing."""

    __tablename__ = "discovery_queue"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    
    # Company identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    careers_url: Mapped[Optional[str]] = mapped_column(Text)
    website_url: Mapped[Optional[str]] = mapped_column(Text)
    
    # Source info
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    
    # Location info
    location: Mapped[Optional[str]] = mapped_column(Text)
    country: Mapped[Optional[str]] = mapped_column(String(2))
    
    # Additional metadata
    description: Mapped[Optional[str]] = mapped_column(Text)
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    employee_count: Mapped[Optional[int]] = mapped_column(Integer)
    funding_stage: Mapped[Optional[str]] = mapped_column(String(50))
    
    # ATS info if detected
    ats_type: Mapped[Optional[str]] = mapped_column(String(50))
    ats_identifier: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Processing status
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )  # pending, processing, completed, failed, skipped, review
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Reference to created company (if successful)
    company_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL")
    )


class DiscoveryRun(Base):
    """Track discovery runs for monitoring and debugging."""

    __tablename__ = "discovery_runs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="running"
    )  # running, completed, failed
    
    # Stats
    total_discovered: Mapped[int] = mapped_column(Integer, default=0)
    new_companies: Mapped[int] = mapped_column(Integer, default=0)
    updated_companies: Mapped[int] = mapped_column(Integer, default=0)
    skipped_duplicates: Mapped[int] = mapped_column(Integer, default=0)
    filtered_non_us: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Progress logs - list of log entries with timestamp, level, message
    # Each entry: {"ts": "2024-01-01T12:00:00Z", "level": "info", "msg": "...", "data": {...}}
    logs: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    
    # Current progress info for real-time UI updates
    current_step: Mapped[Optional[str]] = mapped_column(String(200))
    progress_count: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[Optional[int]] = mapped_column(Integer)
    
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class JobBoardListing(Base):
    """Verification result for a job on a specific job board."""

    __tablename__ = "job_board_listings"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    job_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    board: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # linkedin, indeed, glassdoor, ziprecruiter, etc.

    # Verification result
    found: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)  # 0-1
    listing_url: Mapped[Optional[str]] = mapped_column(Text)  # URL if found

    # Search metadata
    search_query: Mapped[Optional[str]] = mapped_column(Text)
    search_result_count: Mapped[Optional[int]] = mapped_column(Integer)

    # Timestamps
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    job: Mapped["Job"] = relationship(back_populates="board_listings")

    __table_args__ = (
        # Unique constraint on job + board
        {"postgresql_partition_by": None},
    )


class VerificationRun(Base):
    """Track verification runs for monitoring and stats."""

    __tablename__ = "verification_runs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    board: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="running"
    )  # running, completed, failed

    # Stats
    jobs_checked: Mapped[int] = mapped_column(Integer, default=0)
    jobs_found: Mapped[int] = mapped_column(Integer, default=0)  # Found on the board
    jobs_unique: Mapped[int] = mapped_column(Integer, default=0)  # NOT found (unique to us)
    uniqueness_rate: Mapped[Optional[float]] = mapped_column(Float)  # jobs_unique / jobs_checked

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class MaintenanceRun(Base):
    """Track maintenance runs that verify jobs still exist."""

    __tablename__ = "maintenance_runs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    
    # Run type
    run_type: Mapped[str] = mapped_column(
        String(50), default="full"
    )  # full, company, ats_type
    ats_type: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="running"
    )  # running, completed, failed, cancelled
    current_step: Mapped[Optional[str]] = mapped_column(String(200))
    
    # Statistics
    companies_checked: Mapped[int] = mapped_column(Integer, default=0)
    jobs_verified: Mapped[int] = mapped_column(Integer, default=0)
    jobs_new: Mapped[int] = mapped_column(Integer, default=0)
    jobs_delisted: Mapped[int] = mapped_column(Integer, default=0)
    jobs_unchanged: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Progress logs
    logs: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    
    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
