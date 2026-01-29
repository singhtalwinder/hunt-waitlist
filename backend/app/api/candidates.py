"""Candidate-related API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db, CandidateProfile, Match, Job

router = APIRouter()


class CandidateProfileCreate(BaseModel):
    """Create candidate profile request."""

    email: EmailStr
    name: Optional[str] = None
    waitlist_id: Optional[UUID] = None
    role_families: Optional[list[str]] = None
    seniority: Optional[str] = None
    min_salary: Optional[int] = None
    locations: Optional[list[str]] = None
    location_types: Optional[list[str]] = None
    role_types: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    exclusions: Optional[list[str]] = None


class CandidateProfileUpdate(BaseModel):
    """Update candidate profile request."""

    name: Optional[str] = None
    role_families: Optional[list[str]] = None
    seniority: Optional[str] = None
    min_salary: Optional[int] = None
    locations: Optional[list[str]] = None
    location_types: Optional[list[str]] = None
    role_types: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    exclusions: Optional[list[str]] = None


class CandidateProfileResponse(BaseModel):
    """Candidate profile response."""

    id: UUID
    email: str
    name: Optional[str] = None
    role_families: Optional[list[str]] = None
    seniority: Optional[str] = None
    min_salary: Optional[int] = None
    locations: Optional[list[str]] = None
    location_types: Optional[list[str]] = None
    role_types: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    exclusions: Optional[list[str]] = None
    last_matched_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MatchResponse(BaseModel):
    """Match response with job details."""

    id: UUID
    job_id: UUID
    job_title: str
    company_name: str
    score: float
    hard_match: bool
    match_reasons: Optional[dict] = None
    source_url: str
    posted_at: Optional[datetime] = None
    shown_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    created_at: datetime


class MatchListResponse(BaseModel):
    """Paginated match list."""

    matches: list[MatchResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
    no_matches_reason: Optional[str] = None


@router.post("", response_model=CandidateProfileResponse)
async def create_candidate(
    profile: CandidateProfileCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new candidate profile."""
    # Check if email already exists
    existing = await db.execute(
        select(CandidateProfile).where(CandidateProfile.email == profile.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    candidate = CandidateProfile(
        email=profile.email,
        name=profile.name,
        waitlist_id=profile.waitlist_id,
        role_families=profile.role_families,
        seniority=profile.seniority,
        min_salary=profile.min_salary,
        locations=profile.locations,
        location_types=profile.location_types,
        role_types=profile.role_types,
        skills=profile.skills,
        exclusions=profile.exclusions,
    )
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)

    return candidate


@router.get("/{candidate_id}", response_model=CandidateProfileResponse)
async def get_candidate(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get candidate profile by ID."""
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return candidate


@router.patch("/{candidate_id}", response_model=CandidateProfileResponse)
async def update_candidate(
    candidate_id: UUID,
    updates: CandidateProfileUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update candidate profile."""
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Update fields
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(candidate, field, value)

    candidate.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(candidate)

    return candidate


@router.get("/{candidate_id}/matches", response_model=MatchListResponse)
async def get_candidate_matches(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    min_score: float = Query(0.4, ge=0, le=1),
):
    """Get matched jobs for a candidate."""
    offset = (page - 1) * page_size

    # Get matches with jobs
    query = (
        select(Match)
        .options(selectinload(Match.job).selectinload(Job.company))
        .where(Match.candidate_id == candidate_id, Match.score >= min_score)
        .order_by(Match.score.desc(), Match.created_at.desc())
    )

    # Get total count
    count_result = await db.execute(
        select(Match.id).where(Match.candidate_id == candidate_id, Match.score >= min_score)
    )
    total = len(count_result.all())

    # Get paginated results
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    matches = result.scalars().all()

    # Build response
    match_responses = []
    for match in matches:
        # Mark as shown
        if not match.shown_at:
            match.shown_at = datetime.utcnow()

        match_responses.append(
            MatchResponse(
                id=match.id,
                job_id=match.job.id,
                job_title=match.job.title,
                company_name=match.job.company.name,
                score=match.score,
                hard_match=match.hard_match,
                match_reasons=match.match_reasons,
                source_url=match.job.source_url,
                posted_at=match.job.posted_at,
                shown_at=match.shown_at,
                clicked_at=match.clicked_at,
                created_at=match.created_at,
            )
        )

    await db.commit()

    # Determine no matches reason
    no_matches_reason = None
    if total == 0:
        no_matches_reason = "No jobs matching your preferences were found this week. Try expanding your location or role preferences."

    return MatchListResponse(
        matches=match_responses,
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + len(matches) < total,
        no_matches_reason=no_matches_reason,
    )


@router.post("/sync-from-waitlist")
async def sync_from_waitlist(
    waitlist_id: UUID,
    email: EmailStr,
    name: str,
    field: Optional[str] = None,
    seniority: Optional[str] = None,
    expected_pay: Optional[int] = None,
    country: Optional[str] = None,
    work_type: Optional[list[str]] = None,
    role_type: Optional[list[str]] = None,
    db: AsyncSession = Depends(get_db),
):
    """Sync candidate profile from waitlist details."""
    from app.engines.normalize.role_mapper import map_field_to_role_families

    # Check if profile exists
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.waitlist_id == waitlist_id)
    )
    candidate = result.scalar_one_or_none()

    # Map field to role families
    role_families = map_field_to_role_families(field) if field else None

    # Normalize locations from country
    locations = [country] if country else None

    if candidate:
        # Update existing
        candidate.name = name
        candidate.role_families = role_families
        candidate.seniority = seniority
        candidate.min_salary = expected_pay
        candidate.locations = locations
        candidate.location_types = work_type
        candidate.role_types = role_type
        candidate.updated_at = datetime.utcnow()
    else:
        # Create new
        candidate = CandidateProfile(
            email=email,
            name=name,
            waitlist_id=waitlist_id,
            role_families=role_families,
            seniority=seniority,
            min_salary=expected_pay,
            locations=locations,
            location_types=work_type,
            role_types=role_type,
        )
        db.add(candidate)

    await db.commit()
    await db.refresh(candidate)

    return {"status": "synced", "candidate_id": str(candidate.id)}
