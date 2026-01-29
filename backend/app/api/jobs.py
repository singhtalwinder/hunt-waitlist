"""Job-related API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db, Job, Match, Company

router = APIRouter()


class CompanyResponse(BaseModel):
    """Company in job response."""

    id: UUID
    name: str
    domain: Optional[str] = None


class JobResponse(BaseModel):
    """Job response model."""

    id: UUID
    title: str
    description: Optional[str] = None
    source_url: str
    role_family: str
    role_specialization: Optional[str] = None
    seniority: Optional[str] = None
    location_type: Optional[str] = None
    locations: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    employment_type: Optional[str] = None
    posted_at: Optional[datetime] = None
    freshness_score: Optional[float] = None
    company: CompanyResponse
    created_at: datetime

    class Config:
        from_attributes = True


class MatchedJobResponse(BaseModel):
    """Job with match details."""

    job: JobResponse
    match_score: float
    match_reasons: Optional[dict] = None


class JobListResponse(BaseModel):
    """Paginated job list response."""

    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class MatchedJobListResponse(BaseModel):
    """Paginated matched job list response."""

    jobs: list[MatchedJobResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
    no_matches_reason: Optional[str] = None


@router.get("", response_model=JobListResponse)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role_family: Optional[str] = None,
    seniority: Optional[str] = None,
    location_type: Optional[str] = None,
    is_active: bool = True,
):
    """List all jobs with optional filters."""
    offset = (page - 1) * page_size

    # Build query
    query = select(Job).options(selectinload(Job.company)).where(Job.is_active == is_active)

    if role_family:
        query = query.where(Job.role_family == role_family)
    if seniority:
        query = query.where(Job.seniority == seniority)
    if location_type:
        query = query.where(Job.location_type == location_type)

    # Order by freshness
    query = query.order_by(Job.posted_at.desc().nullslast(), Job.created_at.desc())

    # Get total count
    count_result = await db.execute(select(Job.id).where(Job.is_active == is_active))
    total = len(count_result.all())

    # Get paginated results
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return JobListResponse(
        jobs=[
            JobResponse(
                id=job.id,
                title=job.title,
                description=job.description,
                source_url=job.source_url,
                role_family=job.role_family,
                role_specialization=job.role_specialization,
                seniority=job.seniority,
                location_type=job.location_type,
                locations=job.locations,
                skills=job.skills,
                min_salary=job.min_salary,
                max_salary=job.max_salary,
                employment_type=job.employment_type,
                posted_at=job.posted_at,
                freshness_score=job.freshness_score,
                company=CompanyResponse(
                    id=job.company.id,
                    name=job.company.name,
                    domain=job.company.domain,
                ),
                created_at=job.created_at,
            )
            for job in jobs
        ],
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + len(jobs) < total,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific job by ID."""
    result = await db.execute(
        select(Job).options(selectinload(Job.company)).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        id=job.id,
        title=job.title,
        description=job.description,
        source_url=job.source_url,
        role_family=job.role_family,
        role_specialization=job.role_specialization,
        seniority=job.seniority,
        location_type=job.location_type,
        locations=job.locations,
        skills=job.skills,
        min_salary=job.min_salary,
        max_salary=job.max_salary,
        employment_type=job.employment_type,
        posted_at=job.posted_at,
        freshness_score=job.freshness_score,
        company=CompanyResponse(
            id=job.company.id,
            name=job.company.name,
            domain=job.company.domain,
        ),
        created_at=job.created_at,
    )


@router.post("/{job_id}/click")
async def track_job_click(job_id: UUID, candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Track when a candidate clicks on a job."""
    result = await db.execute(
        select(Match).where(Match.job_id == job_id, Match.candidate_id == candidate_id)
    )
    match = result.scalar_one_or_none()

    if match:
        match.clicked_at = datetime.utcnow()
        await db.commit()

    return {"status": "tracked"}
