"""Internal API endpoints for workers."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, Company, CandidateProfile

router = APIRouter()


class TriggerResponse(BaseModel):
    """Trigger response."""

    status: str
    message: str
    task_id: Optional[str] = None


@router.post("/crawl/trigger", response_model=TriggerResponse)
async def trigger_crawl(
    company_id: Optional[UUID] = None,
    ats_type: Optional[str] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """Trigger crawl for a company or all companies of an ATS type."""
    from app.engines.crawl.service import crawl_company, crawl_all_companies

    if company_id:
        # Crawl specific company
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            return TriggerResponse(status="error", message="Company not found")

        background_tasks.add_task(crawl_company, str(company_id))
        return TriggerResponse(
            status="triggered",
            message=f"Crawl triggered for {company.name}",
        )

    elif ats_type:
        # Crawl all companies of this ATS type
        result = await db.execute(
            select(Company).where(Company.ats_type == ats_type, Company.is_active == True)
        )
        companies = result.scalars().all()
        count = len(companies)

        for company in companies:
            background_tasks.add_task(crawl_company, str(company.id))

        return TriggerResponse(
            status="triggered",
            message=f"Crawl triggered for {count} {ats_type} companies",
        )

    else:
        # Crawl all active companies
        background_tasks.add_task(crawl_all_companies)
        return TriggerResponse(
            status="triggered",
            message="Crawl triggered for all active companies",
        )


@router.post("/match/trigger", response_model=TriggerResponse)
async def trigger_matching(
    candidate_id: Optional[UUID] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """Trigger matching for a candidate or all candidates."""
    from app.engines.match.service import run_matching_for_candidate, run_matching_for_all

    if candidate_id:
        # Match specific candidate
        result = await db.execute(
            select(CandidateProfile).where(CandidateProfile.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            return TriggerResponse(status="error", message="Candidate not found")

        background_tasks.add_task(run_matching_for_candidate, str(candidate_id))
        return TriggerResponse(
            status="triggered",
            message=f"Matching triggered for {candidate.email}",
        )

    else:
        # Match all active candidates
        background_tasks.add_task(run_matching_for_all)
        return TriggerResponse(
            status="triggered",
            message="Matching triggered for all active candidates",
        )


@router.post("/notify/trigger", response_model=TriggerResponse)
async def trigger_notifications(
    candidate_id: Optional[UUID] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """Trigger email notifications for matched jobs."""
    from app.engines.feedback.notifier import send_digest, send_all_digests

    if candidate_id:
        result = await db.execute(
            select(CandidateProfile).where(CandidateProfile.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            return TriggerResponse(status="error", message="Candidate not found")

        background_tasks.add_task(send_digest, str(candidate_id))
        return TriggerResponse(
            status="triggered",
            message=f"Notification triggered for {candidate.email}",
        )

    else:
        background_tasks.add_task(send_all_digests)
        return TriggerResponse(
            status="triggered",
            message="Notifications triggered for all candidates",
        )


@router.post("/extract/reprocess", response_model=TriggerResponse)
async def reprocess_extraction(
    company_id: UUID,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """Reprocess job extraction for a company."""
    from app.engines.extract.service import extract_jobs_for_company

    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        return TriggerResponse(status="error", message="Company not found")

    background_tasks.add_task(extract_jobs_for_company, str(company_id))
    return TriggerResponse(
        status="triggered",
        message=f"Extraction reprocessing triggered for {company.name}",
    )


@router.post("/enrich/trigger", response_model=TriggerResponse)
async def trigger_enrichment(
    company_id: Optional[UUID] = None,
    limit: Optional[int] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """Trigger job enrichment to fetch missing descriptions."""
    from app.engines.enrich.service import enrich_jobs_without_descriptions

    limit_msg = f"limit: {limit}" if limit else "no limit"

    if company_id:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            return TriggerResponse(status="error", message="Company not found")

        background_tasks.add_task(
            enrich_jobs_without_descriptions,
            limit=limit,
            company_id=str(company_id),
        )
        return TriggerResponse(
            status="triggered",
            message=f"Enrichment triggered for {company.name} ({limit_msg})",
        )

    else:
        background_tasks.add_task(
            enrich_jobs_without_descriptions,
            limit=limit,
        )
        return TriggerResponse(
            status="triggered",
            message=f"Enrichment triggered for all jobs without descriptions ({limit_msg})",
        )


class EnrichmentStatsResponse(BaseModel):
    """Stats about job enrichment status."""

    total_jobs: int
    jobs_with_description: int
    jobs_without_description: int
    enrichment_rate: float


@router.get("/enrich/stats", response_model=EnrichmentStatsResponse)
async def get_enrichment_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get stats about job descriptions and enrichment status."""
    from sqlalchemy import func
    from app.db import JobRaw

    # Total jobs
    total_result = await db.execute(select(func.count(JobRaw.id)))
    total_jobs = total_result.scalar() or 0

    # Jobs with description
    with_desc_result = await db.execute(
        select(func.count(JobRaw.id)).where(JobRaw.description_raw.isnot(None))
    )
    jobs_with_description = with_desc_result.scalar() or 0

    jobs_without_description = total_jobs - jobs_with_description
    enrichment_rate = (jobs_with_description / total_jobs * 100) if total_jobs > 0 else 0

    return EnrichmentStatsResponse(
        total_jobs=total_jobs,
        jobs_with_description=jobs_with_description,
        jobs_without_description=jobs_without_description,
        enrichment_rate=round(enrichment_rate, 2),
    )


# ============================================
# VERIFICATION ENDPOINTS
# ============================================


class BoardStats(BaseModel):
    """Stats for a single job board."""

    verified: int
    found: int
    unique: int
    uniqueness_rate: float
    coverage_rate: float
    last_verified: Optional[str] = None


class RecentRun(BaseModel):
    """Recent verification run info."""

    id: str
    board: str
    jobs_checked: int
    uniqueness_rate: Optional[float]
    completed_at: Optional[str]


class VerificationStatsResponse(BaseModel):
    """Verification stats response."""

    total_jobs: int
    boards: dict[str, BoardStats]
    recent_runs: list[RecentRun]


@router.get("/verification/stats", response_model=VerificationStatsResponse)
async def get_verification_stats(
    board: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get job board verification statistics.

    Args:
        board: Optional board to filter by (linkedin, indeed).
    """
    from app.engines.verify.service import VerificationEngine

    engine = VerificationEngine(db)
    try:
        stats = await engine.get_uniqueness_stats(board=board)

        # Transform to response model
        boards = {}
        for board_name, board_stats in stats.get("boards", {}).items():
            boards[board_name] = BoardStats(
                verified=board_stats.get("verified", 0),
                found=board_stats.get("found", 0),
                unique=board_stats.get("unique", 0),
                uniqueness_rate=board_stats.get("uniqueness_rate", 0.0),
                coverage_rate=board_stats.get("coverage_rate", 0.0),
                last_verified=board_stats.get("last_verified"),
            )

        recent_runs = [
            RecentRun(
                id=run.get("id", ""),
                board=run.get("board", ""),
                jobs_checked=run.get("jobs_checked", 0),
                uniqueness_rate=run.get("uniqueness_rate"),
                completed_at=run.get("completed_at"),
            )
            for run in stats.get("recent_runs", [])
        ]

        return VerificationStatsResponse(
            total_jobs=stats.get("total_jobs", 0),
            boards=boards,
            recent_runs=recent_runs,
        )
    finally:
        await engine.close()


@router.post("/verification/run", response_model=TriggerResponse)
async def trigger_verification(
    board: str = "linkedin",
    sample_size: int = 100,
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Trigger a verification run for a job board.

    Args:
        board: The job board to verify against (linkedin, indeed).
        sample_size: Number of jobs to verify.
    """
    from app.engines.verify.service import verify_jobs_batch

    if board not in ["linkedin", "indeed"]:
        return TriggerResponse(
            status="error",
            message=f"Unsupported board: {board}. Use 'linkedin' or 'indeed'.",
        )

    background_tasks.add_task(verify_jobs_batch, board=board, limit=sample_size)

    return TriggerResponse(
        status="triggered",
        message=f"Verification triggered for {board} (sample size: {sample_size})",
    )


@router.post("/verification/run-all", response_model=TriggerResponse)
async def trigger_verification_all_boards(
    sample_size: int = 100,
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Trigger verification for all supported job boards.

    Args:
        sample_size: Number of jobs to verify per board.
    """
    from app.engines.verify.service import verify_jobs_batch

    for board in ["linkedin", "indeed"]:
        background_tasks.add_task(verify_jobs_batch, board=board, limit=sample_size)

    return TriggerResponse(
        status="triggered",
        message=f"Verification triggered for all boards (sample size: {sample_size} each)",
    )
