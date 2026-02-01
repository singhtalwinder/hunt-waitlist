"""Admin API endpoints."""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

from app.db import get_db, async_session_factory, Company, Job, CandidateProfile, Match, Metric, DiscoveryQueue, DiscoveryRun

router = APIRouter()


class CompanyCreate(BaseModel):
    """Create company request."""

    name: str
    domain: Optional[str] = None
    careers_url: Optional[str] = None
    ats_type: Optional[str] = None
    ats_identifier: Optional[str] = None
    crawl_priority: int = 50


class CompanyResponse(BaseModel):
    """Company response."""

    id: UUID
    name: str
    domain: Optional[str] = None
    careers_url: Optional[str] = None
    ats_type: Optional[str] = None
    ats_identifier: Optional[str] = None
    crawl_priority: int
    last_crawled_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CompanyListResponse(BaseModel):
    """Paginated company list."""

    companies: list[CompanyResponse]
    total: int
    page: int
    page_size: int


class MetricsSummary(BaseModel):
    """System metrics summary."""

    total_companies: int
    active_companies: int
    total_jobs: int
    active_jobs: int
    jobs_last_24h: int
    jobs_last_7d: int
    total_candidates: int
    active_candidates: int
    total_matches: int
    matches_last_24h: int
    avg_match_score: Optional[float] = None
    crawl_success_rate: Optional[float] = None


@router.get("/metrics", response_model=MetricsSummary)
async def get_metrics(db: AsyncSession = Depends(get_db)):
    """Get system metrics summary."""
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    # Company counts
    total_companies = await db.scalar(select(func.count(Company.id)))
    active_companies = await db.scalar(
        select(func.count(Company.id)).where(Company.is_active == True)
    )

    # Job counts
    total_jobs = await db.scalar(select(func.count(Job.id)))
    active_jobs = await db.scalar(
        select(func.count(Job.id)).where(Job.is_active == True)
    )
    jobs_last_24h = await db.scalar(
        select(func.count(Job.id)).where(Job.created_at >= day_ago)
    )
    jobs_last_7d = await db.scalar(
        select(func.count(Job.id)).where(Job.created_at >= week_ago)
    )

    # Candidate counts
    total_candidates = await db.scalar(select(func.count(CandidateProfile.id)))
    active_candidates = await db.scalar(
        select(func.count(CandidateProfile.id)).where(CandidateProfile.is_active == True)
    )

    # Match counts
    total_matches = await db.scalar(select(func.count(Match.id)))
    matches_last_24h = await db.scalar(
        select(func.count(Match.id)).where(Match.created_at >= day_ago)
    )
    avg_match_score = await db.scalar(select(func.avg(Match.score)))

    return MetricsSummary(
        total_companies=total_companies or 0,
        active_companies=active_companies or 0,
        total_jobs=total_jobs or 0,
        active_jobs=active_jobs or 0,
        jobs_last_24h=jobs_last_24h or 0,
        jobs_last_7d=jobs_last_7d or 0,
        total_candidates=total_candidates or 0,
        active_candidates=active_candidates or 0,
        total_matches=total_matches or 0,
        matches_last_24h=matches_last_24h or 0,
        avg_match_score=float(avg_match_score) if avg_match_score else None,
    )


@router.get("/companies", response_model=CompanyListResponse)
async def list_companies(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    ats_type: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    """List all companies."""
    offset = (page - 1) * page_size

    query = select(Company).order_by(Company.crawl_priority.desc(), Company.name)

    if ats_type:
        query = query.where(Company.ats_type == ats_type)
    if is_active is not None:
        query = query.where(Company.is_active == is_active)

    # Count
    count_query = select(func.count(Company.id))
    if ats_type:
        count_query = count_query.where(Company.ats_type == ats_type)
    if is_active is not None:
        count_query = count_query.where(Company.is_active == is_active)
    total = await db.scalar(count_query) or 0

    # Paginate
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    companies = result.scalars().all()

    return CompanyListResponse(
        companies=[CompanyResponse.model_validate(c) for c in companies],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/companies", response_model=CompanyResponse)
async def create_company(
    company: CompanyCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new company."""
    # Check for duplicate domain
    if company.domain:
        existing = await db.execute(
            select(Company).where(Company.domain == company.domain)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Company with this domain already exists")

    new_company = Company(
        name=company.name,
        domain=company.domain,
        careers_url=company.careers_url,
        ats_type=company.ats_type,
        ats_identifier=company.ats_identifier,
        crawl_priority=company.crawl_priority,
    )
    db.add(new_company)
    await db.commit()
    await db.refresh(new_company)

    return new_company


@router.post("/companies/bulk")
async def bulk_create_companies(
    companies: list[CompanyCreate],
    db: AsyncSession = Depends(get_db),
):
    """Bulk create companies."""
    created = 0
    skipped = 0

    for company_data in companies:
        # Check for duplicate domain
        if company_data.domain:
            existing = await db.execute(
                select(Company).where(Company.domain == company_data.domain)
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

        new_company = Company(
            name=company_data.name,
            domain=company_data.domain,
            careers_url=company_data.careers_url,
            ats_type=company_data.ats_type,
            ats_identifier=company_data.ats_identifier,
            crawl_priority=company_data.crawl_priority,
        )
        db.add(new_company)
        created += 1

    await db.commit()

    return {"created": created, "skipped": skipped}


@router.post("/companies/seed")
async def seed_companies(db: AsyncSession = Depends(get_db)):
    """Seed database with initial company list."""
    from app.engines.discovery.service import DiscoveryEngine
    
    engine = DiscoveryEngine(db)
    try:
        result = await engine.seed_initial_companies()
        return {
            "status": "success",
            "message": f"Seeded {result['created']} companies, updated {result['updated']}, skipped {result['skipped']}",
            **result,
        }
    finally:
        await engine.close()


@router.post("/companies/discover")
async def discover_company(
    name: str,
    domain: str,
    careers_url: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Discover a new company's careers page and ATS type."""
    from app.engines.discovery.service import DiscoveryEngine
    
    engine = DiscoveryEngine(db)
    try:
        company = await engine.discover_company(name, domain, careers_url)
        if company:
            return CompanyResponse.model_validate(company)
        raise HTTPException(status_code=404, detail="Could not discover company careers page")
    finally:
        await engine.close()


@router.patch("/companies/{company_id}")
async def update_company(
    company_id: UUID,
    updates: dict,
    db: AsyncSession = Depends(get_db),
):
    """Update a company."""
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    allowed_fields = {
        "name", "domain", "careers_url", "ats_type", "ats_identifier",
        "crawl_priority", "is_active"
    }

    for field, value in updates.items():
        if field in allowed_fields:
            setattr(company, field, value)

    await db.commit()
    await db.refresh(company)

    return CompanyResponse.model_validate(company)


# ============================================
# DISCOVERY ENDPOINTS
# ============================================


class DiscoveryStatsResponse(BaseModel):
    """Discovery statistics response."""
    
    queue: dict
    by_source: dict
    recent_runs: list
    total_discovered_companies: int
    ready_for_crawl: int = 0  # Companies with ATS that haven't been crawled in 24h


class DiscoveryQueueItem(BaseModel):
    """Discovery queue item."""
    
    id: UUID
    name: str
    domain: Optional[str] = None
    source: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class DiscoveryRunResponse(BaseModel):
    """Discovery run response (summary without logs)."""
    
    id: UUID
    source: str
    status: str
    total_discovered: int
    new_companies: int
    updated_companies: int = 0
    skipped_duplicates: int = 0
    filtered_non_us: int = 0
    errors: int
    current_step: Optional[str] = None
    progress_count: int = 0
    progress_total: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DiscoveryRunDetailResponse(BaseModel):
    """Discovery run with full logs."""
    
    id: UUID
    source: str
    status: str
    total_discovered: int
    new_companies: int
    updated_companies: int = 0
    skipped_duplicates: int = 0
    filtered_non_us: int = 0
    errors: int
    error_message: Optional[str] = None
    current_step: Optional[str] = None
    progress_count: int = 0
    progress_total: Optional[int] = None
    logs: Optional[list] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


@router.get("/discovery/stats", response_model=DiscoveryStatsResponse)
async def get_discovery_stats(db: AsyncSession = Depends(get_db)):
    """Get discovery statistics."""
    from app.engines.discovery.orchestrator import DiscoveryOrchestrator
    
    orchestrator = DiscoveryOrchestrator(db)
    stats = await orchestrator.get_stats()
    
    return DiscoveryStatsResponse(**stats)


@router.get("/discovery/sources")
async def list_discovery_sources():
    """List available discovery sources."""
    from app.engines.discovery.orchestrator import DiscoveryOrchestrator
    
    sources = []
    for source_cls in DiscoveryOrchestrator.DEFAULT_SOURCES:
        source = source_cls()
        sources.append({
            "name": source.source_name,
            "description": source.source_description,
        })
    
    return {"sources": sources}


@router.post("/discovery/run")
async def run_discovery(
    background_tasks: BackgroundTasks,
    source_names: Optional[List[str]] = Query(None),
    sync: bool = Query(False, description="Run synchronously instead of via task queue"),
    force_network_recrawl: bool = Query(False, description="Re-crawl all companies in network_crawler (by default only crawls new)"),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a discovery run.
    
    CONCURRENT EXECUTION:
    - Discovery can run concurrently with crawl, enrich, and embeddings.
    - Discovery hits company websites (stripe.com, etc.), not ATS infrastructure.
    
    By default, tries to queue via Dramatiq (requires Redis).
    Set sync=true to run synchronously (useful for testing without Redis).
    
    For network_crawler: by default, only crawls companies that have never been
    crawled before. Set force_network_recrawl=true to re-crawl all companies.
    """
    from app.engines.pipeline.orchestrator import operation_registry
    
    # Check if discovery is already running
    if operation_registry.is_running("discovery"):
        return {"error": "Discovery already running", "running_operations": operation_registry.to_dict()}
    
    if sync:
        # Run synchronously (still uses operation registry)
        from app.engines.discovery.orchestrator import DiscoveryOrchestrator
        
        if not await operation_registry.start_operation("discovery"):
            return {"error": "Discovery already running"}
        
        try:
            orchestrator = DiscoveryOrchestrator(db)
            stats = await orchestrator.run_discovery(
                source_names=source_names,
                force_network_recrawl=force_network_recrawl,
            )
            
            return {
                "status": "completed",
                "results": [
                    {
                        "source": s.source,
                        "total_discovered": s.total_discovered,
                        "new_companies": s.new_companies,
                        "duplicates": s.skipped_duplicates,
                        "filtered_non_us": s.filtered_non_us,
                        "errors": s.errors,
                    }
                    for s in stats
                ],
            }
        finally:
            await operation_registry.end_operation("discovery")
    
    # Try to queue via Dramatiq
    try:
        from app.workers.tasks import run_discovery_task
        run_discovery_task.send(source_names=source_names, force_network_recrawl=force_network_recrawl)
        return {
            "status": "queued",
            "message": f"Discovery task queued for sources: {source_names or 'all'}" + 
                       (" (force recrawl)" if force_network_recrawl else ""),
            "operation_type": "discovery",
        }
    except Exception as e:
        # Dramatiq/Redis not available, run in background
        async def run_discovery_background():
            from app.engines.discovery.orchestrator import DiscoveryOrchestrator
            
            if not await operation_registry.start_operation("discovery"):
                return
            
            try:
                async with async_session_factory() as session:
                    orchestrator = DiscoveryOrchestrator(session)
                    await orchestrator.run_discovery(
                        source_names=source_names,
                        force_network_recrawl=force_network_recrawl,
                    )
            finally:
                await operation_registry.end_operation("discovery")
        
        background_tasks.add_task(run_discovery_background)
        
        return {
            "status": "started",
            "message": f"Discovery started in background for sources: {source_names or 'all'}",
            "operation_type": "discovery",
        }


@router.post("/discovery/run-sync")
async def run_discovery_sync(
    source_names: Optional[List[str]] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Run discovery synchronously (for testing).
    
    Warning: This can take a long time. Use /discovery/run for production.
    """
    from app.engines.discovery.orchestrator import DiscoveryOrchestrator
    
    orchestrator = DiscoveryOrchestrator(db)
    stats = await orchestrator.run_discovery(source_names=source_names)
    
    return {
        "status": "completed",
        "results": [
            {
                "source": s.source,
                "total_discovered": s.total_discovered,
                "new_companies": s.new_companies,
                "duplicates": s.skipped_duplicates,
                "filtered_non_us": s.filtered_non_us,
                "errors": s.errors,
                "duration_seconds": s.duration_seconds(),
            }
            for s in stats
        ],
    }


@router.post("/discovery/process-queue")
async def process_discovery_queue(
    limit: int = Query(100, ge=1, le=500),
    detect_ats: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """Process items from the discovery queue."""
    try:
        from app.engines.discovery.orchestrator import DiscoveryOrchestrator
        
        orchestrator = DiscoveryOrchestrator(db)
        stats = await orchestrator.process_queue(limit=limit, detect_ats=detect_ats)
        
        return {
            "status": "completed",
            **stats,
        }
    except Exception as e:
        import traceback
        logger.error(f"Process queue error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discovery/queue")
async def get_discovery_queue(
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get items from the discovery queue."""
    offset = (page - 1) * page_size
    
    query = select(DiscoveryQueue).order_by(DiscoveryQueue.created_at.desc())
    count_query = select(func.count(DiscoveryQueue.id))
    
    if status:
        query = query.where(DiscoveryQueue.status == status)
        count_query = count_query.where(DiscoveryQueue.status == status)
    if source:
        query = query.where(DiscoveryQueue.source == source)
        count_query = count_query.where(DiscoveryQueue.source == source)
    
    total = await db.scalar(count_query) or 0
    
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()
    
    return {
        "items": [DiscoveryQueueItem.model_validate(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/discovery/runs")
async def get_discovery_runs(
    db: AsyncSession = Depends(get_db),
    source: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    """Get recent discovery runs."""
    query = select(DiscoveryRun).order_by(DiscoveryRun.started_at.desc()).limit(limit)
    
    if source:
        query = query.where(DiscoveryRun.source == source)
    if status:
        query = query.where(DiscoveryRun.status == status)
    
    result = await db.execute(query)
    runs = result.scalars().all()
    
    return {
        "runs": [DiscoveryRunResponse.model_validate(run) for run in runs],
    }


@router.get("/discovery/runs/{run_id}")
async def get_discovery_run_detail(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single discovery run with full logs.
    
    Use this endpoint to view progress of a running or completed discovery.
    Logs are ordered chronologically and include timestamps.
    """
    result = await db.execute(
        select(DiscoveryRun).where(DiscoveryRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Discovery run not found")
    
    return DiscoveryRunDetailResponse.model_validate(run)


@router.post("/discovery/runs/{run_id}/cancel")
async def cancel_discovery_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running discovery process.
    
    This marks the run as cancelled. The worker will check this status
    and stop processing when it sees the run has been cancelled.
    """
    result = await db.execute(
        select(DiscoveryRun).where(DiscoveryRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Discovery run not found")
    
    if run.status != "running":
        raise HTTPException(status_code=400, detail=f"Cannot cancel run with status: {run.status}")
    
    # Mark as cancelled
    run.status = "cancelled"
    run.error_message = "Cancelled by user"
    run.completed_at = func.now()
    
    await db.commit()
    
    return {"status": "cancelled", "run_id": str(run_id)}


@router.delete("/discovery/queue/{item_id}")
async def delete_queue_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete an item from the discovery queue."""
    result = await db.execute(select(DiscoveryQueue).where(DiscoveryQueue.id == item_id))
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    
    await db.delete(item)
    await db.commit()
    
    return {"status": "deleted"}


@router.delete("/discovery/queue")
async def clear_queue(
    status: str = Query("failed"),
    db: AsyncSession = Depends(get_db),
):
    """Clear items from the discovery queue by status."""
    from sqlalchemy import delete
    
    result = await db.execute(
        delete(DiscoveryQueue).where(DiscoveryQueue.status == status)
    )
    await db.commit()
    
    return {"status": "cleared", "deleted_count": result.rowcount}


class ReviewItemResponse(BaseModel):
    """Item needing review."""
    
    id: UUID
    name: str
    domain: Optional[str] = None
    website_url: Optional[str] = None
    source: str
    description: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/discovery/review")
async def get_items_for_review(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get items that need manual review (no careers page found)."""
    offset = (page - 1) * page_size
    
    query = (
        select(DiscoveryQueue)
        .where(DiscoveryQueue.status == "review")
        .order_by(DiscoveryQueue.created_at.desc())
    )
    
    count_query = select(func.count(DiscoveryQueue.id)).where(
        DiscoveryQueue.status == "review"
    )
    total = await db.scalar(count_query) or 0
    
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()
    
    return {
        "items": [ReviewItemResponse.model_validate(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/discovery/review/{item_id}/approve")
async def approve_review_item(
    item_id: UUID,
    careers_url: str = Query(..., description="The careers page URL"),
    db: AsyncSession = Depends(get_db),
):
    """Approve a review item by providing the careers URL manually."""
    result = await db.execute(
        select(DiscoveryQueue).where(DiscoveryQueue.id == item_id)
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    if item.status != "review":
        raise HTTPException(status_code=400, detail="Item is not in review status")
    
    # Update with the provided careers URL and mark as pending for processing
    item.careers_url = careers_url
    item.status = "pending"
    item.error_message = None
    
    await db.commit()
    
    return {"status": "approved", "message": f"Item updated with careers URL: {careers_url}"}


@router.post("/discovery/review/{item_id}/reject")
async def reject_review_item(
    item_id: UUID,
    reason: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Reject a review item (not a real company, duplicate, etc.)."""
    result = await db.execute(
        select(DiscoveryQueue).where(DiscoveryQueue.id == item_id)
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Mark as skipped with reason
    item.status = "skipped"
    item.error_message = reason or "Manually rejected"
    
    await db.commit()
    
    return {"status": "rejected"}


# ============ Google Search Discovery (Manual Only) ============


@router.post("/discovery/google-search")
async def run_google_search_discovery(
    queries: Optional[List[str]] = Query(None, description="Custom search queries"),
    mode: str = Query("both", description="'ats_fallback', 'discovery', or 'both'"),
    limit: int = Query(50, ge=1, le=200, description="Max companies to search for ATS fallback"),
    db: AsyncSession = Depends(get_db),
):
    """
    Run Google Search discovery MANUALLY.
    
    This costs money (~$5 per 1000 queries), so it's not automated.
    
    Modes:
    - ats_fallback: Search for ATS boards for existing companies without ATS
    - discovery: Search for new companies using queries
    - both: Do both
    
    Custom queries example:
    - "Series A" startup careers hiring
    - site:boards.greenhouse.io "fintech"
    - "YC W24" careers
    """
    from app.engines.discovery.sources.google_search import GoogleSearchSource
    from app.engines.discovery.orchestrator import DiscoveryOrchestrator
    
    # Create source with custom settings
    source = GoogleSearchSource(
        db=db,
        mode=mode,
        custom_queries=queries,
        ats_fallback_limit=limit,
    )
    
    orchestrator = DiscoveryOrchestrator(db, sources=[source])
    stats = await orchestrator.run_discovery(source_names=["google_search"])
    
    return {
        "status": "completed",
        "mode": mode,
        "queries_used": queries or GoogleSearchSource.DISCOVERY_QUERIES if mode in ["discovery", "both"] else [],
        "results": {
            "total_discovered": stats[0].total_discovered if stats else 0,
            "new_companies": stats[0].new_companies if stats else 0,
            "duplicates": stats[0].skipped_duplicates if stats else 0,
            "errors": stats[0].errors if stats else 0,
        }
    }


@router.get("/discovery/google-search/queries")
async def get_google_search_queries():
    """Get default Google Search queries (for UI)."""
    from app.engines.discovery.sources.google_search import GoogleSearchSource
    
    return {
        "default_queries": GoogleSearchSource.DISCOVERY_QUERIES,
        "example_custom_queries": [
            '"Series A" startup careers hiring',
            '"YC W24" careers jobs',
            'site:boards.greenhouse.io "AI startup"',
            '"raised $10M" hiring software engineer',
            'fintech startup careers -linkedin -indeed',
        ],
    }


# ============ Re-detect ATS Endpoint ============


@router.post("/discovery/redetect-ats")
async def redetect_ats_from_careers_urls(
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Re-detect ATS for companies with careers_url but no ats_type.
    
    This makes HTTP requests to careers URLs to detect the ATS system.
    More thorough than the URL-pattern-based redetection.
    """
    from app.engines.discovery.ats_detector import detect_ats_type
    
    # Get companies with careers URL but no ATS
    result = await db.execute(
        select(Company)
        .where(Company.careers_url.isnot(None))
        .where(Company.ats_type.is_(None))
        .where(Company.is_active == True)
        .limit(limit)
    )
    companies = result.scalars().all()
    
    logger.info(f"Re-detecting ATS for {len(companies)} companies")
    
    updated = 0
    errors = 0
    
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for company in companies:
            try:
                ats_type, identifier = await detect_ats_type(client, company.careers_url)
                if ats_type:
                    company.ats_type = ats_type
                    company.ats_identifier = identifier
                    updated += 1
                    logger.info(f"Detected ATS for {company.name}: {ats_type}/{identifier}")
            except Exception as e:
                errors += 1
                logger.debug(f"Error detecting ATS for {company.name}: {e}")
        
        await db.commit()
    
    return {
        "status": "completed",
        "checked": len(companies),
        "updated": updated,
        "errors": errors,
    }


# ============ ATS Prober Endpoint ============


@router.post("/discovery/ats-prober")
async def run_ats_prober(
    limit: int = Query(200, ge=1, le=1000, description="Max companies to probe"),
    concurrency: int = Query(20, ge=1, le=50, description="Concurrent probes"),
    db: AsyncSession = Depends(get_db),
):
    """Run ATS prober to find ATS boards for companies without them.
    
    This probes company names against known ATS URL patterns and verifies
    by checking that the domain on the ATS page matches our company.
    """
    from app.engines.discovery.sources.ats_prober import ATSProberSource
    from app.engines.discovery.orchestrator import DiscoveryOrchestrator
    
    source = ATSProberSource(db=db, concurrency=concurrency, limit=limit)
    orchestrator = DiscoveryOrchestrator(db, sources=[source])
    stats = await orchestrator.run_discovery(source_names=["ats_prober"])
    
    return {
        "status": "completed",
        "probed": limit,
        "results": {
            "total_processed": stats[0].total_discovered if stats else 0,
            "verified_matches": stats[0].new_companies if stats else 0,
            "errors": stats[0].errors if stats else 0,
        }
    }


# ============ ATS Discovery Endpoints ============

class ATSStatsResponse(BaseModel):
    """ATS statistics response."""
    
    by_ats_type: list[dict]
    total_with_ats: int
    total_without_ats: int
    needs_discovery: int


@router.get("/ats/stats", response_model=ATSStatsResponse)
async def get_ats_stats(db: AsyncSession = Depends(get_db)):
    """Get ATS detection statistics."""
    # Count by ATS type
    ats_result = await db.execute(text("""
        SELECT 
            ats_type,
            COUNT(*) as count
        FROM companies 
        WHERE ats_type IS NOT NULL
        GROUP BY ats_type
        ORDER BY count DESC
    """))
    by_ats_type = [
        {"ats_type": row[0], "count": row[1]}
        for row in ats_result.fetchall()
    ]
    
    total_with_ats = sum(item["count"] for item in by_ats_type)
    
    # Count companies without ATS but with careers URL
    needs_discovery = await db.scalar(text("""
        SELECT COUNT(*) FROM companies 
        WHERE ats_type IS NULL 
          AND careers_url IS NOT NULL 
          AND is_active = TRUE
    """)) or 0
    
    # Count total without ATS
    total_without_ats = await db.scalar(text("""
        SELECT COUNT(*) FROM companies 
        WHERE ats_type IS NULL
    """)) or 0
    
    return ATSStatsResponse(
        by_ats_type=by_ats_type,
        total_with_ats=total_with_ats,
        total_without_ats=total_without_ats,
        needs_discovery=needs_discovery,
    )


@router.post("/ats/discover")
async def run_ats_discovery(
    background_tasks: BackgroundTasks,
    limit: int = Query(100, ge=1, le=500, description="Max companies to process"),
    concurrency: int = Query(5, ge=1, le=20, description="Concurrent requests"),
    sync: bool = Query(False, description="Run synchronously"),
    db: AsyncSession = Depends(get_db),
):
    """
    Discover ATS types for companies that don't have one detected.
    
    This crawls careers pages and follows job links to detect the underlying ATS.
    """
    from app.engines.crawl.service import discover_ats_for_companies
    
    if sync:
        # Run synchronously
        try:
            results = await discover_ats_for_companies(limit=limit, concurrency=concurrency)
            return {
                "status": "completed",
                **results,
            }
        except Exception as e:
            logger.error(f"ATS discovery error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Run in background
    async def run_in_background():
        try:
            await discover_ats_for_companies(limit=limit, concurrency=concurrency)
        except Exception as e:
            logger.error(f"Background ATS discovery error: {e}")
    
    background_tasks.add_task(run_in_background)
    
    return {
        "status": "started",
        "message": f"ATS discovery started for up to {limit} companies",
    }


@router.post("/ats/redetect")
async def redetect_ats_from_urls(
    db: AsyncSession = Depends(get_db),
):
    """
    Re-detect ATS types from existing careers URLs.
    
    This is a quick operation that updates ATS types based on URL patterns
    without needing to crawl the pages.
    """
    # Update ATS types from URL patterns
    result = await db.execute(text("""
        UPDATE companies
        SET 
          ats_type = CASE 
            WHEN careers_url ILIKE '%greenhouse.io%' THEN 'greenhouse'
            WHEN careers_url ILIKE '%lever.co%' THEN 'lever'
            WHEN careers_url ILIKE '%ashbyhq.com%' OR careers_url ILIKE '%ashby.com%' THEN 'ashby'
            WHEN careers_url ILIKE '%workable.com%' THEN 'workable'
            WHEN careers_url ILIKE '%myworkdayjobs.com%' THEN 'workday'
            WHEN careers_url ILIKE '%bamboohr.com%' THEN 'bamboohr'
            WHEN careers_url ILIKE '%zohorecruit%' THEN 'zoho_recruit'
            WHEN careers_url ILIKE '%bullhorn%' THEN 'bullhorn'
            WHEN careers_url ILIKE '%jobs.gem.com%' THEN 'gem'
            WHEN careers_url ILIKE '%applytojob.com%' OR careers_url ILIKE '%jazzhr%' THEN 'jazzhr'
            WHEN careers_url ILIKE '%freshteam.com%' THEN 'freshteam'
            WHEN careers_url ILIKE '%recruitee.com%' THEN 'recruitee'
            WHEN careers_url ILIKE '%pinpointhq.com%' THEN 'pinpoint'
            WHEN careers_url ILIKE '%pcrecruiter%' THEN 'pcrecruiter'
            WHEN careers_url ILIKE '%recruitcrm%' THEN 'recruitcrm'
            WHEN careers_url ILIKE '%manatal.com%' THEN 'manatal'
            WHEN careers_url ILIKE '%recooty.com%' THEN 'recooty'
            WHEN careers_url ILIKE '%successfactors%' THEN 'successfactors'
            WHEN careers_url ILIKE '%gohire.io%' THEN 'gohire'
            WHEN careers_url ILIKE '%jobvite.com%' THEN 'jobvite'
            WHEN careers_url ILIKE '%icims.com%' THEN 'icims'
            WHEN careers_url ILIKE '%smartrecruiters.com%' THEN 'smartrecruiters'
            ELSE ats_type
          END
        WHERE careers_url IS NOT NULL
          AND ats_type IS NULL
          AND (
            careers_url ILIKE '%greenhouse.io%'
            OR careers_url ILIKE '%lever.co%'
            OR careers_url ILIKE '%ashbyhq.com%'
            OR careers_url ILIKE '%ashby.com%'
            OR careers_url ILIKE '%workable.com%'
            OR careers_url ILIKE '%myworkdayjobs.com%'
            OR careers_url ILIKE '%bamboohr.com%'
            OR careers_url ILIKE '%zohorecruit%'
            OR careers_url ILIKE '%bullhorn%'
            OR careers_url ILIKE '%jobs.gem.com%'
            OR careers_url ILIKE '%applytojob.com%'
            OR careers_url ILIKE '%jazzhr%'
            OR careers_url ILIKE '%freshteam.com%'
            OR careers_url ILIKE '%recruitee.com%'
            OR careers_url ILIKE '%pinpointhq.com%'
            OR careers_url ILIKE '%pcrecruiter%'
            OR careers_url ILIKE '%recruitcrm%'
            OR careers_url ILIKE '%manatal.com%'
            OR careers_url ILIKE '%recooty.com%'
            OR careers_url ILIKE '%successfactors%'
            OR careers_url ILIKE '%gohire.io%'
            OR careers_url ILIKE '%jobvite.com%'
            OR careers_url ILIKE '%icims.com%'
            OR careers_url ILIKE '%smartrecruiters.com%'
          )
        RETURNING id, name, ats_type
    """))
    
    updated = result.fetchall()
    await db.commit()
    
    # Get summary by ATS type
    ats_counts = {}
    for row in updated:
        ats_type = row[2]
        ats_counts[ats_type] = ats_counts.get(ats_type, 0) + 1
    
    return {
        "status": "completed",
        "updated_count": len(updated),
        "by_ats_type": ats_counts,
    }


# ============ Job Crawling Endpoints ============

@router.get("/crawl/stats")
async def get_crawl_stats(db: AsyncSession = Depends(get_db)):
    """Get job crawling statistics."""
    from app.db.models import Job, CrawlSnapshot
    
    # Count by ATS type
    ats_result = await db.execute(text("""
        SELECT 
            ats_type,
            COUNT(*) as total,
            COUNT(CASE WHEN careers_url IS NOT NULL THEN 1 END) as with_careers,
            COUNT(CASE WHEN last_crawled_at IS NOT NULL THEN 1 END) as crawled
        FROM companies 
        GROUP BY ats_type
        ORDER BY total DESC
    """))
    ats_stats = [
        {
            "ats_type": row[0] or "unknown",
            "total": row[1],
            "with_careers": row[2],
            "crawled": row[3],
        }
        for row in ats_result.fetchall()
    ]
    
    # Total jobs
    jobs_result = await db.execute(select(func.count(Job.id)))
    total_jobs = jobs_result.scalar() or 0
    
    # Snapshots
    snapshots_result = await db.execute(select(func.count(CrawlSnapshot.id)))
    total_snapshots = snapshots_result.scalar() or 0
    
    return {
        "by_ats_type": ats_stats,
        "total_jobs": total_jobs,
        "total_snapshots": total_snapshots,
    }


@router.post("/crawl/run")
async def run_job_crawl(
    ats_type: Optional[str] = Query(None, description="Filter by ATS type (greenhouse, ashby, lever, etc.)"),
    limit: int = Query(50, ge=1, le=500),
    concurrency: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Run job crawling for companies."""
    from app.engines.crawl.service import CrawlEngine
    
    try:
        engine = CrawlEngine(db)
        
        if ats_type:
            # Crawl specific ATS type
            results = await engine.crawl_by_ats_type(
                ats_type=ats_type,
                limit=limit,
                concurrency=concurrency,
            )
        else:
            # Crawl companies with careers URLs, prioritizing those with known ATS
            query = (
                select(Company.id)
                .where(Company.is_active == True)
                .where(Company.careers_url.isnot(None))
                .order_by(
                    # Prioritize companies with known ATS (easier to extract)
                    Company.ats_type.isnot(None).desc(),
                    Company.crawl_priority.desc(),
                    Company.last_crawled_at.asc().nullsfirst(),
                )
                .limit(limit)
            )
            result = await db.execute(query)
            company_ids = [row[0] for row in result.fetchall()]
            
            logger.info(f"Crawling {len(company_ids)} companies")
            results = await engine.crawl_companies(company_ids, concurrency)
        
        await engine.close()
        
        return {
            "status": "completed",
            **results,
        }
    except Exception as e:
        logger.error(f"Crawl error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawl/company/{company_id}")
async def crawl_single_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Crawl a single company's career page."""
    from app.engines.crawl.service import CrawlEngine
    
    engine = CrawlEngine(db)
    try:
        result = await engine.crawl_company(company_id)
        await engine.close()
        
        if result.get("status") == "success":
            snapshot = result.get("snapshot")
            return {
                "status": "success",
                "snapshot_id": str(snapshot.id) if snapshot else None,
                "url": snapshot.url if snapshot else None,
                "jobs_extracted": result.get("jobs_extracted", 0),
            }
        else:
            return {
                "status": "failed",
                "error": result.get("error", "Unknown error"),
                "reason": result.get("reason"),
            }
    except Exception as e:
        await engine.close()
        raise HTTPException(status_code=500, detail=str(e))


# ========== Embedding Generation ==========

@router.get("/embeddings/stats")
async def get_embedding_stats(db: AsyncSession = Depends(get_db)):
    """Get stats on jobs with/without embeddings."""
    result = await db.execute(text('''
        SELECT 
            COUNT(*) as total_jobs,
            COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embeddings,
            COUNT(CASE WHEN embedding IS NULL THEN 1 END) as without_embeddings,
            COUNT(CASE WHEN is_active = true AND embedding IS NULL THEN 1 END) as active_without_embeddings,
            COUNT(CASE WHEN is_active = false AND embedding IS NULL THEN 1 END) as inactive_without_embeddings
        FROM jobs
    '''))
    row = result.fetchone()
    
    return {
        "total_jobs": row[0],
        "with_embeddings": row[1],
        "without_embeddings": row[2],
        "active_without_embeddings": row[3],
        "inactive_without_embeddings": row[4],
    }


@router.post("/embeddings/generate")
async def generate_embeddings(
    batch_size: int = Query(100, ge=1, le=500),
    background_tasks: BackgroundTasks = None,
):
    """Generate embeddings for jobs that don't have them."""
    from app.engines.normalize.service import generate_embeddings_batch
    
    try:
        result = await generate_embeddings_batch(batch_size=batch_size)
        return result
    except Exception as e:
        logger.error("Embedding generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ========== Job Enrichment ==========

@router.get("/enrich/stats")
async def get_enrichment_stats(db: AsyncSession = Depends(get_db)):
    """Get stats on jobs needing enrichment."""
    result = await db.execute(text('''
        SELECT 
            c.ats_type,
            COUNT(*) as total,
            COUNT(j.description) as with_desc,
            COUNT(j.posted_at) as with_posted_at
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        GROUP BY c.ats_type
        ORDER BY total DESC
    '''))
    
    stats = []
    for row in result.fetchall():
        stats.append({
            "ats_type": row[0],
            "total": row[1],
            "with_description": row[2],
            "with_posted_at": row[3],
            "missing_description": row[1] - row[2],
        })
    
    return {"by_ats_type": stats}


@router.post("/enrich/run")
async def run_job_enrichment(
    ats_type: Optional[str] = Query(None, description="Filter by ATS type"),
    limit: int = Query(100, ge=1, le=1000),
    concurrency: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Enrich jobs with descriptions and posted dates from source URLs."""
    from app.engines.enrich.service import JobEnrichmentService
    
    try:
        service = JobEnrichmentService(db)
        try:
            result = await service.enrich_jobs_batch(
                ats_type=ats_type,
                limit=limit,
                concurrency=concurrency,
            )
            return {"status": "completed", **result}
        finally:
            await service.close()
    except Exception as e:
        logger.error("Enrichment failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ========== Pipeline Management ==========

@router.get("/pipeline/operations")
async def list_running_operations():
    """List all currently running operations.
    
    Operations are keyed by type:
    - discovery: Finding new companies (hits company websites)
    - crawl_greenhouse, crawl_lever, crawl_ashby, etc.: Per-ATS crawling
    - enrich_greenhouse, enrich_lever, etc.: Per-ATS enrichment  
    - embeddings: Generating embeddings (hits Gemini API)
    - full_pipeline: Sequential full pipeline run
    
    Different operation types can run concurrently (e.g., discovery + crawl_greenhouse + embeddings).
    Same operation type blocks (e.g., can't run two crawl_greenhouse at once).
    
    Returns a dict keyed by operation type, e.g.:
    {"crawl_greenhouse": {...}, "embeddings": {...}}
    """
    from app.engines.pipeline.orchestrator import operation_registry
    
    # Return just the operations dict, not wrapped in {"running_operations": ..., "count": ...}
    running_ops = operation_registry.get_running_operations()
    return {k: v.to_dict() for k, v in running_ops.items()}


@router.get("/pipeline/stats")
async def get_pipeline_stats(db: AsyncSession = Depends(get_db)):
    """Get pipeline statistics for the admin UI."""
    # Companies ready to crawl (have ATS type but never crawled)
    ready_to_crawl_result = await db.execute(text('''
        SELECT COUNT(*) FROM companies 
        WHERE is_active = true 
        AND ats_type IS NOT NULL 
        AND (crawl_attempts IS NULL OR crawl_attempts = 0)
    '''))
    companies_ready_to_crawl = ready_to_crawl_result.scalar() or 0
    
    # Companies pending ATS detection - detailed breakdown
    ats_stats_result = await db.execute(text('''
        SELECT 
            COUNT(*) FILTER (WHERE ats_type IS NULL AND (ats_detection_attempts IS NULL OR ats_detection_attempts = 0)) as never_tried,
            COUNT(*) FILTER (WHERE ats_type IS NULL AND ats_detection_attempts > 0 AND ats_detection_attempts < 3) as tried_pending,
            COUNT(*) FILTER (WHERE ats_type IS NULL AND ats_detection_attempts >= 3) as exhausted
        FROM companies
        WHERE is_active = true
    '''))
    ats_row = ats_stats_result.fetchone()
    ats_never_tried = ats_row.never_tried or 0
    ats_tried_pending = ats_row.tried_pending or 0
    ats_exhausted = ats_row.exhausted or 0
    
    # Jobs missing descriptions
    missing_desc_result = await db.execute(text('''
        SELECT COUNT(*) FROM jobs 
        WHERE is_active = true 
        AND (description IS NULL OR description = '')
    '''))
    jobs_missing_description = missing_desc_result.scalar() or 0
    
    # Jobs missing embeddings
    missing_embed_result = await db.execute(text('''
        SELECT COUNT(*) FROM jobs 
        WHERE is_active = true 
        AND embedding IS NULL
    '''))
    jobs_missing_embeddings = missing_embed_result.scalar() or 0
    
    return {
        "companies_ready_to_crawl": companies_ready_to_crawl,
        "companies_pending_ats": ats_never_tried + ats_tried_pending,
        "ats_never_tried": ats_never_tried,
        "ats_tried_pending": ats_tried_pending,
        "ats_exhausted": ats_exhausted,
        "jobs_missing_description": jobs_missing_description,
        "jobs_missing_embeddings": jobs_missing_embeddings,
    }


@router.get("/pipeline/runs")
async def get_pipeline_runs(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    stage: Optional[str] = Query(None, description="Filter by stage"),
):
    """Get pipeline run history."""
    # Check if pipeline_runs table exists
    try:
        query = '''
            SELECT id, stage, status, started_at, completed_at, 
                   processed, failed, error, current_step, cascade, logs
            FROM pipeline_runs
        '''
        if stage:
            query += f" WHERE stage = '{stage}'"
        query += " ORDER BY started_at DESC LIMIT :limit"
        
        result = await db.execute(text(query), {"limit": limit})
        runs = []
        for row in result.fetchall():
            duration = None
            if row[3] and row[4]:
                delta = row[4] - row[3]
                duration = f"{int(delta.total_seconds())}s"
            runs.append({
                "id": str(row[0]),
                "stage": row[1],
                "status": row[2],
                "started_at": row[3].isoformat() if row[3] else None,
                "completed_at": row[4].isoformat() if row[4] else None,
                "processed": row[5] or 0,
                "failed": row[6] or 0,
                "error": row[7],
                "current_step": row[8],
                "cascade": row[9] or False,
                "logs": row[10] or [],
                "duration": duration,
            })
        return {"runs": runs}
    except Exception as e:
        # Table might not exist yet
        logger.debug(f"Pipeline runs query failed: {e}")
        return {"runs": []}


@router.post("/pipeline/runs/{run_id}/cancel")
async def cancel_pipeline_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running pipeline process.
    
    This marks the run as cancelled. The background task will check this status
    and stop processing when it sees the run has been cancelled.
    """
    result = await db.execute(
        text("SELECT id, status FROM pipeline_runs WHERE id = :run_id"),
        {"run_id": run_id}
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    if row[1] != "running":
        raise HTTPException(status_code=400, detail=f"Cannot cancel run with status: {row[1]}")
    
    # Mark as cancelled
    await db.execute(
        text("""
            UPDATE pipeline_runs 
            SET status = 'cancelled',
                error = 'Cancelled by user',
                completed_at = NOW(),
                current_step = 'Cancelled'
            WHERE id = :run_id
        """),
        {"run_id": run_id}
    )
    await db.commit()
    
    return {"status": "cancelled", "run_id": str(run_id)}


@router.get("/pipeline/status")
async def get_pipeline_status(db: AsyncSession = Depends(get_db)):
    """Get current pipeline status and statistics.
    
    Shows all currently running operations. Multiple operations can run concurrently:
    - discovery: Finding new companies (hits company websites)
    - crawl_greenhouse, crawl_lever, crawl_ashby, etc.: Per-ATS crawling
    - enrich_greenhouse, enrich_lever, etc.: Per-ATS enrichment
    - embeddings: Generating embeddings (hits Gemini API)
    """
    from app.engines.pipeline.orchestrator import PipelineOrchestrator, operation_registry
    from app.engines.pipeline.scheduler import scheduler
    
    orchestrator = PipelineOrchestrator()
    pipeline_status = orchestrator.status.to_dict()
    
    # Get all running operations from the registry
    running_operations = operation_registry.to_dict()
    
    # Also check for running pipeline_runs in the database (for detect_ats, custom_crawl, etc.)
    # These run outside the PipelineOrchestrator but we want to show their progress
    running_runs = []
    try:
        result = await db.execute(text('''
            SELECT id, stage, status, started_at, processed, failed, 
                   error, current_step, logs
            FROM pipeline_runs
            WHERE status = 'running'
            ORDER BY started_at DESC
        '''))
        for row in result.fetchall():
            running_runs.append({
                "id": str(row[0]),
                "stage": row[1],
                "status": row[2],
                "started_at": row[3].isoformat() if row[3] else None,
                "processed": row[4] or 0,
                "failed": row[5] or 0,
                "error": row[6],
                "current_step": row[7],
                "logs": row[8] or [],
            })
    except Exception as e:
        logger.debug(f"Could not fetch running pipeline runs: {e}")
    
    return {
        "pipeline": pipeline_status,
        "running_operations": running_operations,
        "running_runs": running_runs,
        "scheduler": scheduler.status,
        "stats": await orchestrator.get_stats(),
    }


@router.post("/pipeline/run")
async def run_pipeline(
    background_tasks: BackgroundTasks,
    skip_discovery: bool = Query(False, description="Skip discovery stage"),
    skip_crawl: bool = Query(False, description="Skip crawl stage"),
    skip_enrichment: bool = Query(False, description="Skip enrichment stage"),
    skip_embeddings: bool = Query(False, description="Skip embeddings stage"),
    crawl_limit: int = Query(100, ge=1, le=500, description="Max companies to crawl"),
    enrich_limit: Optional[int] = Query(None, ge=1, description="Max jobs to enrich per ATS (None = no limit)"),
    embedding_batch_size: int = Query(100, ge=10, le=500, description="Embedding batch size"),
):
    """Run the full pipeline (discovery -> crawl -> enrich -> embeddings).
    
    This runs stages SEQUENTIALLY. For parallel execution of individual stages,
    use the individual endpoints (/pipeline/crawl, /pipeline/enrich, /pipeline/embeddings).
    """
    from app.engines.pipeline.orchestrator import PipelineOrchestrator, operation_registry
    
    orchestrator = PipelineOrchestrator()
    
    # Full pipeline blocks other full pipelines (but individual ops can still run)
    if operation_registry.is_running("full_pipeline"):
        return {"error": "Full pipeline already running", "running_operations": operation_registry.to_dict()}
    
    async def run_in_background():
        await orchestrator.run_full_pipeline(
            skip_discovery=skip_discovery,
            skip_crawl=skip_crawl,
            skip_enrichment=skip_enrichment,
            skip_embeddings=skip_embeddings,
            crawl_limit=crawl_limit,
            enrich_limit=enrich_limit,
            embedding_batch_size=embedding_batch_size,
        )
    
    background_tasks.add_task(run_in_background)
    
    return {
        "status": "started",
        "message": "Full pipeline started in background. Check /pipeline/status for progress.",
        "operation_type": "full_pipeline",
    }


@router.post("/pipeline/crawl-concurrent")
async def run_concurrent_crawls(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    ats_types: List[str] = Query(["greenhouse", "lever", "ashby"], description="ATS types to crawl concurrently"),
    limit_per_ats: int = Query(50, ge=1, le=200, description="Max companies per ATS type"),
):
    """Run crawls for multiple ATS types CONCURRENTLY.
    
    This is more efficient than running them sequentially because each ATS
    has its own rate limits and infrastructure.
    
    Example: Crawl greenhouse, lever, and ashby all at the same time.
    """
    from app.engines.pipeline.orchestrator import run_concurrent_crawls as do_concurrent_crawls, operation_registry
    from app.engines.pipeline.run_logger import create_pipeline_run, complete_pipeline_run
    
    # Check which operations are already running
    already_running = [ats for ats in ats_types if operation_registry.is_running(f"crawl_{ats}")]
    if already_running:
        return {
            "error": f"Some crawls already running: {already_running}",
            "running_operations": operation_registry.to_dict(),
        }
    
    # Create a pipeline run for tracking
    run_id = await create_pipeline_run(
        db,
        stage="crawl_concurrent",
        current_step=f"Starting concurrent crawl for {', '.join(ats_types)}",
        cascade=False,
    )
    
    async def run_in_background():
        from app.db.session import async_session_factory
        try:
            results = await do_concurrent_crawls(ats_types, limit_per_ats)
            
            # Calculate totals
            total_crawled = sum(r.get("companies_crawled", 0) for r in results.values() if isinstance(r, dict))
            total_jobs = sum(r.get("jobs_found", 0) for r in results.values() if isinstance(r, dict))
            total_failed = sum(r.get("failed", 0) for r in results.values() if isinstance(r, dict))
            
            if run_id:
                async with async_session_factory() as session:
                    await complete_pipeline_run(
                        session,
                        run_id,
                        processed=total_crawled,
                        failed=total_failed,
                        status="completed",
                    )
        except Exception as e:
            if run_id:
                async with async_session_factory() as session:
                    await complete_pipeline_run(
                        session,
                        run_id,
                        status="failed",
                        error=str(e),
                    )
            raise
    
    background_tasks.add_task(run_in_background)
    
    return {
        "status": "started",
        "message": f"Concurrent crawl started for {len(ats_types)} ATS types: {', '.join(ats_types)}",
        "ats_types": ats_types,
        "limit_per_ats": limit_per_ats,
        "run_id": str(run_id) if run_id else None,
    }


@router.post("/pipeline/discover-from-companies")
async def discover_from_companies(
    background_tasks: BackgroundTasks,
):
    """Discover new companies from existing company networks.
    
    Uses the network_crawler discovery source to find related companies.
    """
    from app.engines.discovery import DiscoveryOrchestrator
    
    async def run_in_background():
        async with async_session_factory() as session:
            orchestrator = DiscoveryOrchestrator(session)
            # Run only network_crawler source which discovers from existing companies
            await orchestrator.run_discovery(source_names=["network_crawler"])
            # Process the queue to create companies
            await orchestrator.process_queue(limit=500)
    
    background_tasks.add_task(run_in_background)
    
    return {
        "status": "started",
        "message": "Discovering from company networks in background.",
    }


@router.post("/pipeline/detect-ats")
async def run_ats_detection(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    batch_size: int = Query(50, ge=1, le=500, description="Companies per batch (smaller = more reliable)"),
    include_retries: bool = Query(False, description="Include companies we tried before"),
):
    """Detect ATS type for companies missing it. Runs continuously until all are processed."""
    from app.engines.discovery.ats_detection_service import detect_ats_for_companies
    from app.engines.pipeline.orchestrator import operation_registry
    
    # Check if already running
    if operation_registry.is_running("detect_ats"):
        return {"error": "ATS detection already running", "running_operations": operation_registry.to_dict()}
    
    # Create a pipeline run for tracking
    run_id = None
    try:
        result = await db.execute(text('''
            INSERT INTO pipeline_runs (stage, status, started_at, current_step)
            VALUES ('detect_ats', 'running', NOW(), 'Starting ATS detection')
            RETURNING id
        '''))
        run_id = result.scalar()
        await db.commit()
    except Exception:
        pass  # Table might not exist
    
    async def run_in_background():
        from app.db.session import async_session_factory
        
        if not await operation_registry.start_operation("detect_ats"):
            return
        
        try:
            async with async_session_factory() as session:
                result = await detect_ats_for_companies(
                    session,
                    batch_size=batch_size,
                    include_retries=include_retries,
                    run_id=run_id,
                    continuous=True,  # Keep running until all companies processed
                )
                
                # Update pipeline run with final status (only if not cancelled)
                if run_id and not result.get("cancelled"):
                    await session.execute(text('''
                        UPDATE pipeline_runs
                        SET status = 'completed',
                            completed_at = NOW(),
                            processed = :processed,
                            failed = :failed
                        WHERE id = :id AND status = 'running'
                    '''), {
                        "id": run_id,
                        "processed": result["detected"],
                        "failed": result["not_detected"] + result["errors"],
                    })
                    await session.commit()
        except Exception as e:
            if run_id:
                async with async_session_factory() as session:
                    await session.execute(text('''
                        UPDATE pipeline_runs
                        SET status = 'failed',
                            completed_at = NOW(),
                            error = :error,
                            current_step = 'Failed'
                        WHERE id = :id AND status = 'running'
                    '''), {"id": run_id, "error": str(e)})
                    await session.commit()
            raise
        finally:
            await operation_registry.end_operation("detect_ats")
    
    background_tasks.add_task(run_in_background)
    
    msg = f"Detecting ATS continuously (batch size: {batch_size})"
    if include_retries:
        msg += " (including retries)"
    return {"status": "started", "message": msg, "run_id": str(run_id) if run_id else None, "operation_type": "detect_ats"}


@router.post("/pipeline/move-dormant")
async def move_companies_to_dormant_endpoint(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500, description="Max companies to move"),
    reason: str = Query("no_careers_url", description="Reason for moving to dormant"),
):
    """
    Move companies without careers pages to the dormant table.
    
    These companies can be periodically re-checked to see if they've added careers pages.
    """
    from app.engines.discovery.ats_detection_service import move_companies_to_dormant
    
    result = await move_companies_to_dormant(db, reason=reason, limit=limit)
    return result


@router.post("/pipeline/recheck-dormant")
async def recheck_dormant_companies_endpoint(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200, description="Max companies to check"),
):
    """
    Re-check dormant companies to see if they've added careers pages.
    
    Reactivates companies that now have detectable careers pages.
    """
    from app.engines.discovery.ats_detection_service import recheck_dormant_companies
    
    result = await recheck_dormant_companies(db, limit=limit)
    return result


@router.get("/pipeline/dormant-stats")
async def get_dormant_stats(db: AsyncSession = Depends(get_db)):
    """Get statistics about dormant companies."""
    from app.engines.discovery.ats_detection_service import ensure_dormant_table_exists
    
    await ensure_dormant_table_exists(db)
    
    result = await db.execute(text('''
        SELECT 
            dormant_reason,
            COUNT(*) as count,
            COUNT(*) FILTER (WHERE last_checked_at IS NULL) as never_checked,
            COUNT(*) FILTER (WHERE last_checked_at < NOW() - INTERVAL '30 days') as stale
        FROM companies_dormant
        GROUP BY dormant_reason
    '''))
    rows = result.fetchall()
    
    return {
        "by_reason": [
            {
                "reason": row.dormant_reason,
                "count": row.count,
                "never_checked": row.never_checked,
                "stale": row.stale,
            }
            for row in rows
        ],
        "total": sum(row.count for row in rows),
    }


@router.post("/pipeline/crawl-custom")
async def run_custom_crawl(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200, description="Max companies to crawl"),
    mark_exhausted: bool = Query(True, description="Mark exhausted ATS detection as custom"),
    enrich: bool = Query(False, description="Also enrich job descriptions"),
):
    """
    Crawl companies with custom career pages using Playwright + LLM.
    
    This handles companies where ATS detection failed. Uses browser rendering
    and AI to extract job listings from non-standard career pages.
    """
    from app.engines.pipeline.orchestrator import operation_registry
    
    # Check if already running
    if operation_registry.is_running("custom_crawl"):
        return {"error": "Custom crawl already running", "running_operations": operation_registry.to_dict()}
    
    # Create a pipeline run for tracking
    run_id = None
    try:
        result = await db.execute(text('''
            INSERT INTO pipeline_runs (stage, status, started_at, current_step)
            VALUES ('custom_crawl', 'running', NOW(), 'Starting custom crawl with Playwright')
            RETURNING id
        '''))
        run_id = result.scalar()
        await db.commit()
    except Exception:
        pass  # Table might not exist
    
    async def run_in_background():
        from app.db.session import async_session_maker
        from app.engines.crawl.custom_crawler import CustomCrawlerService
        
        if not await operation_registry.start_operation("custom_crawl"):
            return
        
        try:
            async with async_session_maker() as session:
                service = CustomCrawlerService(session)
                
                try:
                    # Mark exhausted as custom if requested
                    marked = 0
                    if mark_exhausted:
                        marked = await service.mark_exhausted_as_custom()
                        if run_id:
                            await session.execute(text('''
                                UPDATE pipeline_runs
                                SET current_step = :step
                                WHERE id = :id
                            '''), {
                                "id": run_id,
                                "step": f"Marked {marked} companies as custom, now crawling...",
                            })
                            await session.commit()
                    
                    # Crawl custom companies
                    crawl_result = await service.crawl_custom_companies(limit=limit)
                    
                    # Optionally enrich
                    enrich_result = {"success": 0, "failed": 0}
                    if enrich and crawl_result["jobs_found"] > 0:
                        if run_id:
                            await session.execute(text('''
                                UPDATE pipeline_runs
                                SET current_step = 'Enriching job descriptions...'
                                WHERE id = :id
                            '''), {"id": run_id})
                            await session.commit()
                        
                        enrich_result = await service.enrich_custom_jobs(limit=limit * 5)
                    
                    # Update pipeline run
                    if run_id:
                        await session.execute(text('''
                            UPDATE pipeline_runs
                            SET status = 'completed',
                                completed_at = NOW(),
                                processed = :processed,
                                failed = :failed,
                                current_step = NULL
                            WHERE id = :id
                        '''), {
                            "id": run_id,
                            "processed": crawl_result["jobs_found"] + enrich_result.get("success", 0),
                            "failed": crawl_result["errors"] + enrich_result.get("failed", 0),
                        })
                        await session.commit()
                        
                except Exception as e:
                    if run_id:
                        await session.execute(text('''
                            UPDATE pipeline_runs
                            SET status = 'failed',
                                completed_at = NOW(),
                                error = :error
                            WHERE id = :id
                        '''), {"id": run_id, "error": str(e)})
                        await session.commit()
                    raise
                finally:
                    await service.close()
        finally:
            await operation_registry.end_operation("custom_crawl")
    
    background_tasks.add_task(run_in_background)
    
    msg = f"Crawling up to {limit} custom companies with Playwright"
    if mark_exhausted:
        msg += " (marking exhausted as custom)"
    if enrich:
        msg += " + enriching descriptions"
    return {"status": "started", "message": msg, "run_id": str(run_id) if run_id else None, "operation_type": "custom_crawl"}


@router.post("/pipeline/crawl")
async def run_crawl_only(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    ats_type: Optional[str] = Query(None, description="Specific ATS type to crawl (allows concurrent crawls of different ATS)"),
    limit: int = Query(500, ge=1, le=10000, description="Max companies to crawl per batch (runs continuously)"),
    cascade: bool = Query(False, description="Also run enrich and embeddings after"),
):
    """Run the crawl stage, optionally followed by enrich and embeddings.
    
    CONCURRENT EXECUTION:
    - If ats_type is specified, only that ATS is crawled and other ATS types can run concurrently.
    - Example: You can run crawl_greenhouse, crawl_lever, and crawl_ashby all at the same time.
    - If ats_type is not specified, crawls all ATS types (blocks other crawl_all operations).
    """
    from app.engines.pipeline.orchestrator import PipelineOrchestrator, operation_registry
    from app.engines.pipeline.run_logger import create_pipeline_run, complete_pipeline_run
    
    orchestrator = PipelineOrchestrator()
    
    # Check if this specific operation is already running
    operation_type = f"crawl_{ats_type}" if ats_type else "crawl_all"
    if operation_registry.is_running(operation_type):
        return {"error": f"{operation_type} already running", "running_operations": operation_registry.to_dict()}
    
    # Create a pipeline run for tracking
    stage_name = f"crawl_{ats_type}" if ats_type else "crawl"
    run_id = await create_pipeline_run(
        db,
        stage=stage_name,
        current_step=f"Starting crawl for up to {limit} {ats_type or 'all'} companies",
        cascade=cascade,
    )
    
    async def run_in_background():
        from app.db.session import async_session_factory
        try:
            if cascade:
                # Use full pipeline for cascade mode
                result = await orchestrator.run_full_pipeline(
                    skip_discovery=True,
                    skip_enrichment=False,
                    skip_embeddings=False,
                    crawl_limit=limit,
                    crawl_run_id=run_id,
                )
                crawl_result = result.get("crawl", {}) or {}
            else:
                # Use standalone crawl for non-cascade mode (allows concurrent ops)
                crawl_result = await orchestrator.run_crawl_standalone(
                    ats_type=ats_type,
                    limit=limit,
                    run_id=run_id,
                )
            
            # Update pipeline run with final status
            if run_id:
                async with async_session_factory() as session:
                    await complete_pipeline_run(
                        session,
                        run_id,
                        processed=crawl_result.get("companies_crawled", 0),
                        failed=crawl_result.get("failed", 0),
                        status="completed" if not crawl_result.get("cancelled") else "cancelled",
                    )
        except Exception as e:
            if run_id:
                async with async_session_factory() as session:
                    await complete_pipeline_run(
                        session,
                        run_id,
                        status="failed",
                        error=str(e),
                    )
            raise
    
    background_tasks.add_task(run_in_background)
    
    msg = f"Crawling up to {limit} {ats_type or 'all'} companies"
    if cascade:
        msg += ", then enriching and generating embeddings"
    return {
        "status": "started",
        "message": msg,
        "run_id": str(run_id) if run_id else None,
        "operation_type": operation_type,
    }


@router.post("/pipeline/enrich")
async def run_enrich_only(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    ats_type: Optional[str] = Query(None, description="Specific ATS type to enrich (allows concurrent enrichment of different ATS)"),
    limit: Optional[int] = Query(None, ge=1, description="Max jobs to enrich per ATS (None = no limit)"),
    cascade: bool = Query(False, description="Also run embeddings after"),
):
    """Run the enrichment stage, optionally followed by embeddings.
    
    CONCURRENT EXECUTION:
    - If ats_type is specified, only that ATS is enriched and other ATS types can run concurrently.
    - Example: You can run enrich_greenhouse, enrich_lever, and enrich_ashby all at the same time.
    """
    from app.engines.pipeline.orchestrator import PipelineOrchestrator, operation_registry
    from app.engines.pipeline.run_logger import create_pipeline_run, complete_pipeline_run
    
    orchestrator = PipelineOrchestrator()
    
    # Check if this specific operation is already running
    operation_type = f"enrich_{ats_type}" if ats_type else "enrich_all"
    if operation_registry.is_running(operation_type):
        return {"error": f"{operation_type} already running", "running_operations": operation_registry.to_dict()}
    
    # Create a pipeline run for tracking
    stage_name = f"enrich_{ats_type}" if ats_type else "enrich"
    limit_msg = f"up to {limit}" if limit else "all"
    run_id = await create_pipeline_run(
        db,
        stage=stage_name,
        current_step=f"Starting enrichment for {limit_msg} {ats_type or 'all'} jobs",
        cascade=cascade,
    )
    
    async def run_in_background():
        from app.db.session import async_session_factory
        try:
            if cascade:
                # Use full pipeline for cascade mode
                result = await orchestrator.run_full_pipeline(
                    skip_discovery=True,
                    skip_crawl=True,
                    skip_embeddings=False,
                    enrich_limit=limit,
                    enrich_run_id=run_id,
                )
                enrich_result = result.get("enrichment", {}) or {}
            else:
                # Use standalone enrich for non-cascade mode (allows concurrent ops)
                enrich_result = await orchestrator.run_enrich_standalone(
                    ats_type=ats_type,
                    limit=limit,
                    run_id=run_id,
                )
            
            # Update pipeline run with final status
            if run_id:
                async with async_session_factory() as session:
                    await complete_pipeline_run(
                        session,
                        run_id,
                        processed=enrich_result.get("success", 0),
                        failed=enrich_result.get("failed", 0),
                        status="completed" if not enrich_result.get("cancelled") else "cancelled",
                    )
        except Exception as e:
            if run_id:
                async with async_session_factory() as session:
                    await complete_pipeline_run(
                        session,
                        run_id,
                        status="failed",
                        error=str(e),
                    )
            raise
    
    background_tasks.add_task(run_in_background)
    
    limit_desc = f"up to {limit}" if limit else "all"
    msg = f"Enriching {limit_desc} {ats_type or 'all'} jobs"
    if cascade:
        msg += ", then generating embeddings"
    return {
        "status": "started",
        "message": msg,
        "run_id": str(run_id) if run_id else None,
        "operation_type": operation_type,
    }


@router.post("/pipeline/embeddings")
async def run_embeddings_only(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    batch_size: int = Query(100, ge=10, le=500, description="Batch size"),
):
    """Run only the embeddings generation stage.
    
    CONCURRENT EXECUTION:
    - Embeddings can run concurrently with discovery, crawl, and enrich operations.
    - Uses Gemini API (generativelanguage.googleapis.com), not ATS infrastructure.
    """
    from app.engines.pipeline.orchestrator import PipelineOrchestrator, operation_registry
    from app.engines.pipeline.run_logger import create_pipeline_run, complete_pipeline_run
    
    orchestrator = PipelineOrchestrator()
    
    # Check if embeddings is already running
    operation_type = "embeddings"
    if operation_registry.is_running(operation_type):
        return {"error": f"{operation_type} already running", "running_operations": operation_registry.to_dict()}
    
    # Create a pipeline run for tracking
    run_id = await create_pipeline_run(
        db,
        stage="embeddings",
        current_step=f"Starting embeddings (batch size: {batch_size})",
        cascade=False,
    )
    
    async def run_in_background():
        from app.db.session import async_session_factory
        try:
            # Use standalone embeddings method (allows concurrent ops)
            embed_result = await orchestrator.run_embeddings_standalone(
                batch_size=batch_size,
                run_id=run_id,
            )
            
            # Update pipeline run with final status
            if run_id:
                async with async_session_factory() as session:
                    await complete_pipeline_run(
                        session,
                        run_id,
                        processed=embed_result.get("processed", 0),
                        failed=0,
                        status="completed" if not embed_result.get("cancelled") else "cancelled",
                    )
        except Exception as e:
            if run_id:
                async with async_session_factory() as session:
                    await complete_pipeline_run(
                        session,
                        run_id,
                        status="failed",
                        error=str(e),
                    )
            raise
    
    background_tasks.add_task(run_in_background)
    
    return {
        "status": "started",
        "message": "Generating embeddings (via Gemini API).",
        "run_id": str(run_id) if run_id else None,
        "operation_type": operation_type,
    }


# ========== Stage Detail Endpoints ==========

@router.get("/pipeline/discovery/status")
async def get_discovery_stage_status(db: AsyncSession = Depends(get_db)):
    """Get detailed discovery stage status for live monitoring."""
    from app.engines.pipeline.orchestrator import PipelineOrchestrator
    
    orchestrator = PipelineOrchestrator()
    pipeline_status = orchestrator.status
    
    # Get queue stats
    queue_result = await db.execute(text('''
        SELECT 
            status,
            COUNT(*) as count
        FROM discovery_queue
        GROUP BY status
    '''))
    queue_stats = {row[0]: row[1] for row in queue_result.fetchall()}
    
    # Get recent discoveries
    recent_result = await db.execute(text('''
        SELECT source, COUNT(*) as count
        FROM discovery_queue
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY source
        ORDER BY count DESC
    '''))
    recent_by_source = [{"source": row[0], "count": row[1]} for row in recent_result.fetchall()]
    
    # Get company counts
    company_result = await db.execute(text('''
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as added_today,
            COUNT(CASE WHEN ats_type IS NOT NULL THEN 1 END) as with_ats
        FROM companies
    '''))
    row = company_result.fetchone()
    
    is_active = pipeline_status.stage.value == "discovery"
    
    return {
        "stage": "discovery",
        "is_active": is_active,
        "current_step": pipeline_status.current_step if is_active else None,
        "progress": pipeline_status.progress.get("discovery", {}) if is_active else {},
        "queue": {
            "pending": queue_stats.get("pending", 0),
            "processing": queue_stats.get("processing", 0),
            "completed": queue_stats.get("completed", 0),
            "review": queue_stats.get("review", 0),
            "failed": queue_stats.get("failed", 0),
        },
        "recent_by_source": recent_by_source,
        "companies": {
            "total": row[0],
            "added_today": row[1],
            "with_ats": row[2],
        }
    }


@router.get("/pipeline/crawl/status")
async def get_crawl_stage_status(db: AsyncSession = Depends(get_db)):
    """Get detailed crawl stage status for live monitoring."""
    from app.engines.pipeline.orchestrator import PipelineOrchestrator
    
    orchestrator = PipelineOrchestrator()
    pipeline_status = orchestrator.status
    
    # Get crawl stats by ATS type
    ats_result = await db.execute(text('''
        SELECT 
            COALESCE(ats_type, 'unknown') as ats_type,
            COUNT(*) as total,
            COUNT(CASE WHEN last_crawled_at > NOW() - INTERVAL '24 hours' THEN 1 END) as crawled_today,
            COUNT(CASE WHEN last_crawled_at IS NULL OR last_crawled_at < NOW() - INTERVAL '24 hours' THEN 1 END) as needs_crawl
        FROM companies
        WHERE is_active = true AND ats_type IS NOT NULL
        GROUP BY ats_type
        ORDER BY total DESC
    '''))
    by_ats = [
        {"ats_type": row[0], "total": row[1], "crawled_today": row[2], "needs_crawl": row[3]}
        for row in ats_result.fetchall()
    ]
    
    # Get job stats
    job_result = await db.execute(text('''
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as added_today,
            COUNT(CASE WHEN updated_at > NOW() - INTERVAL '24 hours' THEN 1 END) as updated_today
        FROM jobs
    '''))
    job_row = job_result.fetchone()
    
    is_active = pipeline_status.stage.value == "crawling"
    
    return {
        "stage": "crawl",
        "is_active": is_active,
        "current_step": pipeline_status.current_step if is_active else None,
        "progress": pipeline_status.progress.get("crawl", {}) if is_active else {},
        "by_ats": by_ats,
        "jobs": {
            "total": job_row[0],
            "added_today": job_row[1],
            "updated_today": job_row[2],
        },
        "needs_crawl_total": sum(ats["needs_crawl"] for ats in by_ats),
    }


@router.get("/pipeline/enrich/status")
async def get_enrich_stage_status(db: AsyncSession = Depends(get_db)):
    """Get detailed enrichment stage status for live monitoring."""
    from app.engines.pipeline.orchestrator import PipelineOrchestrator
    
    orchestrator = PipelineOrchestrator()
    pipeline_status = orchestrator.status
    
    # Get enrichment stats by ATS type
    enrich_result = await db.execute(text('''
        SELECT 
            COALESCE(c.ats_type, 'unknown') as ats_type,
            COUNT(*) as total,
            COUNT(j.description) as with_description,
            COUNT(CASE WHEN j.description IS NULL THEN 1 END) as needs_enrichment,
            COUNT(CASE WHEN j.updated_at > NOW() - INTERVAL '1 hour' THEN 1 END) as enriched_recently
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        WHERE j.is_active = true
        GROUP BY c.ats_type
        ORDER BY total DESC
    '''))
    by_ats = [
        {
            "ats_type": row[0],
            "total": row[1],
            "with_description": row[2],
            "needs_enrichment": row[3],
            "enriched_recently": row[4],
        }
        for row in enrich_result.fetchall()
    ]
    
    # Total stats
    total_result = await db.execute(text('''
        SELECT 
            COUNT(*) as total,
            COUNT(description) as with_description,
            COUNT(CASE WHEN description IS NULL THEN 1 END) as needs_enrichment
        FROM jobs
        WHERE is_active = true
    '''))
    total_row = total_result.fetchone()
    
    is_active = pipeline_status.stage.value == "enrichment"
    
    return {
        "stage": "enrich",
        "is_active": is_active,
        "current_step": pipeline_status.current_step if is_active else None,
        "progress": pipeline_status.progress.get("enrichment", {}) if is_active else {},
        "by_ats": by_ats,
        "totals": {
            "total_jobs": total_row[0],
            "with_description": total_row[1],
            "needs_enrichment": total_row[2],
            "percent_complete": round(100 * total_row[1] / total_row[0], 1) if total_row[0] > 0 else 0,
        }
    }


@router.get("/pipeline/embeddings/status")
async def get_embeddings_stage_status(db: AsyncSession = Depends(get_db)):
    """Get detailed embeddings stage status for live monitoring."""
    from app.engines.pipeline.orchestrator import PipelineOrchestrator
    
    orchestrator = PipelineOrchestrator()
    pipeline_status = orchestrator.status
    
    # Get embedding stats
    embed_result = await db.execute(text('''
        SELECT 
            COUNT(*) as total,
            COUNT(embedding) as with_embeddings,
            COUNT(CASE WHEN embedding IS NULL THEN 1 END) as without_embeddings
        FROM jobs
        WHERE is_active = true
    '''))
    row = embed_result.fetchone()
    
    is_active = pipeline_status.stage.value == "embeddings"
    progress = pipeline_status.progress.get("embeddings", {}) if is_active else {}
    
    return {
        "stage": "embeddings",
        "is_active": is_active,
        "current_step": pipeline_status.current_step if is_active else None,
        "progress": {
            "processed": progress.get("processed", 0),
            "batches": progress.get("batches", 0),
            "remaining": progress.get("remaining", row[2]) if is_active else row[2],
        },
        "totals": {
            "total_jobs": row[0],
            "with_embeddings": row[1],
            "without_embeddings": row[2],
            "percent_complete": round(100 * row[1] / row[0], 1) if row[0] > 0 else 0,
        }
    }


# ========== Supported ATS Pipeline (One-Click Processing) ==========

@router.get("/pipeline/supported-ats")
async def get_supported_ats_info(db: AsyncSession = Depends(get_db)):
    """Get supported ATS types and stats for one-click processing.
    
    Supported ATS types have reliable API/scraping methods and can be
    processed with a single click: crawl -> enrich -> embeddings.
    """
    from app.engines.pipeline.supported_ats import get_supported_ats_types
    
    supported = get_supported_ats_types()
    supported_str = ", ".join(f"'{a}'" for a in supported)
    
    # Get stats for supported vs unsupported
    result = await db.execute(text(f'''
        WITH job_stats AS (
            SELECT 
                c.ats_type,
                CASE WHEN c.ats_type IN ({supported_str}) THEN 'supported' ELSE 'unsupported' END as category,
                COUNT(j.id) as total_jobs,
                COUNT(CASE WHEN j.description IS NOT NULL THEN 1 END) as with_description,
                COUNT(CASE WHEN j.description IS NULL THEN 1 END) as needs_enrichment,
                COUNT(CASE WHEN j.embedding IS NOT NULL THEN 1 END) as with_embeddings
            FROM jobs j
            JOIN companies c ON j.company_id = c.id
            WHERE j.is_active = true
            GROUP BY c.ats_type
        )
        SELECT 
            category,
            SUM(total_jobs) as total_jobs,
            SUM(with_description) as with_description,
            SUM(needs_enrichment) as needs_enrichment,
            SUM(with_embeddings) as with_embeddings
        FROM job_stats
        GROUP BY category
    '''))
    
    stats = {"supported": {}, "unsupported": {}}
    for row in result.fetchall():
        category = row[0]
        stats[category] = {
            "total_jobs": row[1],
            "with_description": row[2],
            "needs_enrichment": row[3],
            "with_embeddings": row[4],
            "percent_enriched": round(100 * row[2] / row[1], 1) if row[1] > 0 else 0,
            "percent_embedded": round(100 * row[4] / row[1], 1) if row[1] > 0 else 0,
        }
    
    # Get per-ATS breakdown for supported types
    result = await db.execute(text(f'''
        SELECT 
            c.ats_type,
            COUNT(j.id) as total_jobs,
            COUNT(CASE WHEN j.description IS NOT NULL THEN 1 END) as with_description,
            COUNT(CASE WHEN j.description IS NULL THEN 1 END) as needs_enrichment,
            COUNT(CASE WHEN j.embedding IS NOT NULL THEN 1 END) as with_embeddings
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        WHERE j.is_active = true AND c.ats_type IN ({supported_str})
        GROUP BY c.ats_type
        ORDER BY COUNT(j.id) DESC
    '''))
    
    by_ats = []
    for row in result.fetchall():
        by_ats.append({
            "ats_type": row[0],
            "total_jobs": row[1],
            "with_description": row[2],
            "needs_enrichment": row[3],
            "with_embeddings": row[4],
            "percent_enriched": round(100 * row[2] / row[1], 1) if row[1] > 0 else 0,
        })
    
    return {
        "supported_ats_types": supported,
        "stats": stats,
        "by_ats": by_ats,
    }


@router.post("/pipeline/supported-ats/run")
async def run_supported_ats_pipeline(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    enrich_limit: Optional[int] = Query(None, ge=1, description="Max jobs to enrich per ATS (None = no limit)"),
    embeddings_limit: Optional[int] = Query(None, ge=1, description="Max jobs to embed (None = no limit)"),
):
    """One-click pipeline for supported ATS types.
    
    Runs the full pipeline (enrich -> embeddings) for all supported ATS types:
    - greenhouse, lever, ashby, workable, jobvite, workday
    
    These ATS types have reliable API/scraping and typically achieve >95% success rate.
    """
    from app.engines.pipeline.orchestrator import PipelineOrchestrator, operation_registry
    from app.engines.pipeline.run_logger import create_pipeline_run, complete_pipeline_run, log_to_run
    from app.engines.pipeline.supported_ats import get_supported_ats_types
    from app.engines.enrich.service import JobEnrichmentService
    from app.engines.embed.service import EmbeddingService
    
    # Check if already running
    if operation_registry.is_running("supported_ats_pipeline"):
        return {"error": "Supported ATS pipeline already running", "running_operations": operation_registry.to_dict()}
    
    supported = get_supported_ats_types()
    
    # Create pipeline run
    run_id = await create_pipeline_run(
        db,
        stage="supported_ats",
        current_step=f"Starting one-click pipeline for {len(supported)} ATS types",
        cascade=True,
    )
    
    async def run_in_background():
        from app.db.session import async_session_factory
        
        operation_registry.start("supported_ats_pipeline")
        total_enriched = 0
        total_enrich_failed = 0
        total_embedded = 0
        total_embed_failed = 0
        
        try:
            # Phase 1: Enrich all supported ATS types
            async with async_session_factory() as session:
                await log_to_run(
                    session, run_id, "info",
                    f"Phase 1: Enriching {len(supported)} supported ATS types",
                    current_step="Phase 1: Enrichment",
                    data={"ats_types": supported}
                )
            
            enrich_service = JobEnrichmentService()
            for i, ats_type in enumerate(supported, 1):
                async with async_session_factory() as session:
                    await log_to_run(
                        session, run_id, "info",
                        f"Enriching {ats_type} ({i}/{len(supported)})",
                        current_step=f"Enriching {ats_type} ({i}/{len(supported)})"
                    )
                
                result = await enrich_service.enrich_jobs_batch(
                    ats_type=ats_type,
                    limit=enrich_limit,
                    run_id=run_id,
                )
                total_enriched += result.get("success", 0)
                total_enrich_failed += result.get("failed", 0)
                
                async with async_session_factory() as session:
                    await log_to_run(
                        session, run_id, "info",
                        f"Enriched {ats_type}: {result.get('success', 0)} success, {result.get('failed', 0)} failed",
                        data={"ats_type": ats_type, "success": result.get("success", 0), "failed": result.get("failed", 0)}
                    )
            
            await enrich_service.close()
            
            # Phase 2: Generate embeddings for all newly enriched jobs
            async with async_session_factory() as session:
                await log_to_run(
                    session, run_id, "info",
                    f"Phase 2: Generating embeddings (enriched {total_enriched} jobs)",
                    current_step="Phase 2: Embeddings"
                )
            
            embed_service = EmbeddingService()
            embed_result = await embed_service.embed_jobs_batch(
                limit=embeddings_limit,
                run_id=run_id,
            )
            total_embedded = embed_result.get("success", 0)
            total_embed_failed = embed_result.get("failed", 0)
            
            # Complete the run
            async with async_session_factory() as session:
                await complete_pipeline_run(
                    session,
                    run_id,
                    processed=total_enriched + total_embedded,
                    failed=total_enrich_failed + total_embed_failed,
                    status="completed",
                )
                await log_to_run(
                    session, run_id, "info",
                    f"One-click pipeline complete: {total_enriched} enriched, {total_embedded} embedded",
                    data={
                        "enriched": total_enriched,
                        "enrich_failed": total_enrich_failed,
                        "embedded": total_embedded,
                        "embed_failed": total_embed_failed,
                    }
                )
                
        except Exception as e:
            async with async_session_factory() as session:
                await complete_pipeline_run(
                    session,
                    run_id,
                    status="failed",
                    error=str(e),
                )
            raise
        finally:
            operation_registry.stop("supported_ats_pipeline")
    
    background_tasks.add_task(run_in_background)
    
    return {
        "status": "started",
        "message": f"One-click pipeline started for {len(supported)} ATS types: {', '.join(supported)}",
        "run_id": str(run_id),
        "supported_ats": supported,
    }


@router.get("/pipeline/supported-ats/status")
async def get_supported_ats_pipeline_status(db: AsyncSession = Depends(get_db)):
    """Get status of the supported ATS one-click pipeline."""
    from app.engines.pipeline.orchestrator import operation_registry
    
    # Get latest run
    result = await db.execute(text('''
        SELECT id, status, processed, failed, current_step, created_at, completed_at, logs
        FROM pipeline_runs
        WHERE stage = 'supported_ats'
        ORDER BY created_at DESC
        LIMIT 1
    '''))
    row = result.fetchone()
    
    if not row:
        return {"status": "never_run", "is_running": False}
    
    is_running = operation_registry.is_running("supported_ats_pipeline")
    
    return {
        "run_id": str(row[0]),
        "status": row[1],
        "is_running": is_running,
        "processed": row[2],
        "failed": row[3],
        "current_step": row[4],
        "started_at": row[5].isoformat() if row[5] else None,
        "completed_at": row[6].isoformat() if row[6] else None,
        "logs": row[7] if row[7] else [],
    }


@router.post("/pipeline/supported-ats/add/{ats_type}")
async def add_supported_ats_type(ats_type: str):
    """Add an ATS type to the supported list (runtime only).
    
    For permanent changes, update SUPPORTED_ATS_TYPES in supported_ats.py.
    """
    from app.engines.pipeline.supported_ats import add_supported_ats, get_supported_ats_types
    
    added = add_supported_ats(ats_type)
    return {
        "status": "added" if added else "already_exists",
        "ats_type": ats_type.lower(),
        "supported_ats_types": get_supported_ats_types(),
    }


@router.post("/pipeline/supported-ats/remove/{ats_type}")
async def remove_supported_ats_type(ats_type: str):
    """Remove an ATS type from the supported list (runtime only).
    
    For permanent changes, update SUPPORTED_ATS_TYPES in supported_ats.py.
    """
    from app.engines.pipeline.supported_ats import remove_supported_ats, get_supported_ats_types
    
    removed = remove_supported_ats(ats_type)
    return {
        "status": "removed" if removed else "not_found",
        "ats_type": ats_type.lower(),
        "supported_ats_types": get_supported_ats_types(),
    }


# ========== Scheduler Management ==========

@router.post("/scheduler/start")
async def start_scheduler(
    interval_hours: int = Query(6, ge=1, le=24, description="Hours between runs"),
):
    """Start the automated pipeline scheduler."""
    from app.engines.pipeline.scheduler import scheduler
    
    if scheduler.is_running:
        return {"status": "already_running", **scheduler.status}
    
    await scheduler.start(interval_hours=interval_hours)
    return {"status": "started", **scheduler.status}


@router.post("/scheduler/stop")
async def stop_scheduler():
    """Stop the automated pipeline scheduler."""
    from app.engines.pipeline.scheduler import scheduler
    
    if not scheduler.is_running:
        return {"status": "not_running"}
    
    await scheduler.stop()
    return {"status": "stopped"}


@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get scheduler status."""
    from app.engines.pipeline.scheduler import scheduler
    
    return scheduler.status


# ========== Analytics Endpoints ==========

class TimeSeriesPoint(BaseModel):
    """A single data point in a time series."""
    date: str
    value: int


class AnalyticsResponse(BaseModel):
    """Analytics data for dashboard charts."""
    # Time series data (last 30 days)
    crawls_per_day: list[TimeSeriesPoint]
    new_companies_per_day: list[TimeSeriesPoint]
    new_jobs_per_day: list[TimeSeriesPoint]
    delisted_jobs_per_day: list[TimeSeriesPoint]
    companies_with_new_jobs_per_day: list[TimeSeriesPoint]
    
    # Source breakdown
    sources: list[dict]
    
    # Summary stats
    totals: dict


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Get analytics data for dashboard charts."""
    from app.db.models import CrawlSnapshot, MaintenanceRun
    
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)
    
    # 1. Crawls per day (from crawl_snapshots)
    crawls_result = await db.execute(text("""
        SELECT DATE(crawled_at) as date, COUNT(*) as count
        FROM crawl_snapshots
        WHERE crawled_at >= :start_date
        GROUP BY DATE(crawled_at)
        ORDER BY date
    """), {"start_date": start_date})
    crawls_per_day = [
        {"date": str(row[0]), "value": row[1]}
        for row in crawls_result.fetchall()
    ]
    
    # 2. New companies per day
    new_companies_result = await db.execute(text("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM companies
        WHERE created_at >= :start_date
        GROUP BY DATE(created_at)
        ORDER BY date
    """), {"start_date": start_date})
    new_companies_per_day = [
        {"date": str(row[0]), "value": row[1]}
        for row in new_companies_result.fetchall()
    ]
    
    # 3. New jobs per day
    new_jobs_result = await db.execute(text("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM jobs
        WHERE created_at >= :start_date
        GROUP BY DATE(created_at)
        ORDER BY date
    """), {"start_date": start_date})
    new_jobs_per_day = [
        {"date": str(row[0]), "value": row[1]}
        for row in new_jobs_result.fetchall()
    ]
    
    # 4. Delisted jobs per day (jobs that became inactive)
    # We track this by looking at jobs where is_active=false and updated_at is recent
    delisted_result = await db.execute(text("""
        SELECT DATE(updated_at) as date, COUNT(*) as count
        FROM jobs
        WHERE is_active = FALSE
          AND updated_at >= :start_date
          AND updated_at != created_at
        GROUP BY DATE(updated_at)
        ORDER BY date
    """), {"start_date": start_date})
    delisted_jobs_per_day = [
        {"date": str(row[0]), "value": row[1]}
        for row in delisted_result.fetchall()
    ]
    
    # 5. Existing companies with new jobs per day
    # Companies that already existed before and got new jobs
    existing_companies_new_jobs_result = await db.execute(text("""
        SELECT DATE(j.created_at) as date, COUNT(DISTINCT j.company_id) as count
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        WHERE j.created_at >= :start_date
          AND c.created_at < j.created_at - INTERVAL '1 day'
        GROUP BY DATE(j.created_at)
        ORDER BY date
    """), {"start_date": start_date})
    companies_with_new_jobs_per_day = [
        {"date": str(row[0]), "value": row[1]}
        for row in existing_companies_new_jobs_result.fetchall()
    ]
    
    # 6. Sources breakdown (from discovery_queue and companies)
    sources_result = await db.execute(text("""
        SELECT 
            COALESCE(discovery_source, 'seed') as source,
            COUNT(*) as count
        FROM companies
        WHERE is_active = TRUE
        GROUP BY discovery_source
        ORDER BY count DESC
    """))
    sources = [
        {"name": row[0] or "unknown", "value": row[1]}
        for row in sources_result.fetchall()
    ]
    
    # 7. Summary totals
    total_companies = await db.scalar(select(func.count(Company.id)).where(Company.is_active == True))
    total_jobs = await db.scalar(select(func.count(Job.id)).where(Job.is_active == True))
    total_crawls = await db.scalar(
        select(func.count(CrawlSnapshot.id)).where(CrawlSnapshot.crawled_at >= start_date)
    )
    total_delisted = await db.scalar(
        select(func.count(Job.id)).where(
            Job.is_active == False,
            Job.updated_at >= start_date
        )
    )
    
    # Jobs added in the period
    jobs_added = await db.scalar(
        select(func.count(Job.id)).where(Job.created_at >= start_date)
    )
    
    # Companies added in the period
    companies_added = await db.scalar(
        select(func.count(Company.id)).where(Company.created_at >= start_date)
    )
    
    totals = {
        "total_companies": total_companies or 0,
        "total_jobs": total_jobs or 0,
        "total_crawls_period": total_crawls or 0,
        "jobs_added_period": jobs_added or 0,
        "companies_added_period": companies_added or 0,
        "jobs_delisted_period": total_delisted or 0,
    }
    
    return AnalyticsResponse(
        crawls_per_day=crawls_per_day,
        new_companies_per_day=new_companies_per_day,
        new_jobs_per_day=new_jobs_per_day,
        delisted_jobs_per_day=delisted_jobs_per_day,
        companies_with_new_jobs_per_day=companies_with_new_jobs_per_day,
        sources=sources,
        totals=totals,
    )


# ============================================
# MAINTENANCE ENDPOINTS
# ============================================


class MaintenanceStatsResponse(BaseModel):
    """Maintenance statistics response."""
    
    jobs_pending_verification: int
    jobs_verified_24h: int
    jobs_delisted_7d: int
    companies_pending_maintenance: int
    companies_maintained_24h: int
    by_ats: list[dict]


class MaintenanceRunResponse(BaseModel):
    """Maintenance run response (summary without logs)."""
    
    id: UUID
    run_type: str
    ats_type: Optional[str] = None
    status: str
    companies_checked: int
    jobs_verified: int
    jobs_new: int
    jobs_delisted: int
    jobs_unchanged: int
    errors: int
    current_step: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class MaintenanceRunDetailResponse(BaseModel):
    """Maintenance run with full logs."""
    
    id: UUID
    run_type: str
    ats_type: Optional[str] = None
    status: str
    companies_checked: int
    jobs_verified: int
    jobs_new: int
    jobs_delisted: int
    jobs_unchanged: int
    errors: int
    error_message: Optional[str] = None
    current_step: Optional[str] = None
    logs: Optional[list] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


@router.get("/maintenance/stats", response_model=MaintenanceStatsResponse)
async def get_maintenance_stats(db: AsyncSession = Depends(get_db)):
    """Get maintenance statistics."""
    from app.engines.maintenance.service import get_maintenance_stats as _get_stats
    
    stats = await _get_stats(db)
    return MaintenanceStatsResponse(**stats)


@router.get("/maintenance/runs")
async def get_maintenance_runs(
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None),
    ats_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    """Get recent maintenance runs."""
    from app.db import MaintenanceRun
    
    query = select(MaintenanceRun).order_by(MaintenanceRun.started_at.desc()).limit(limit)
    
    if status:
        query = query.where(MaintenanceRun.status == status)
    if ats_type:
        query = query.where(MaintenanceRun.ats_type == ats_type)
    
    result = await db.execute(query)
    runs = result.scalars().all()
    
    return {
        "runs": [MaintenanceRunResponse.model_validate(run) for run in runs],
    }


@router.get("/maintenance/runs/{run_id}")
async def get_maintenance_run_detail(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single maintenance run with full logs."""
    from app.db import MaintenanceRun
    
    result = await db.execute(
        select(MaintenanceRun).where(MaintenanceRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Maintenance run not found")
    
    return MaintenanceRunDetailResponse.model_validate(run)


@router.post("/maintenance/run")
async def run_maintenance(
    background_tasks: BackgroundTasks,
    ats_type: Optional[str] = Query(None, description="Filter by ATS type (use 'custom' for Playwright companies)"),
    limit: int = Query(100, ge=1, le=500, description="Max companies to check"),
    include_custom: bool = Query(True, description="Include custom/Playwright companies when ats_type is None"),
    sync: bool = Query(False, description="Run synchronously"),
    db: AsyncSession = Depends(get_db),
):
    """
    Run maintenance to verify job listings.
    
    This re-crawls companies to:
    - Verify existing jobs still exist on the ATS or custom career page
    - Find new jobs that have been posted
    - Delist jobs that have been removed (not delete)
    - Log all operations for audit trail
    
    Supports both:
    - Standard ATS (greenhouse, lever, ashby, workable, etc.)
    - Custom career pages (using Playwright + LLM) - use ats_type='custom'
    """
    from app.engines.maintenance.service import MaintenanceEngine
    from app.engines.pipeline.orchestrator import operation_registry
    
    # Check if maintenance is already running
    operation_type = f"maintenance_{ats_type}" if ats_type else "maintenance_all"
    if operation_registry.is_running(operation_type):
        return {"error": f"{operation_type} already running", "running_operations": operation_registry.to_dict()}
    
    if sync:
        # Run synchronously
        if not await operation_registry.start_operation(operation_type):
            return {"error": f"{operation_type} already running"}
        
        try:
            engine = MaintenanceEngine(db)
            results = await engine.run_maintenance(
                ats_type=ats_type,
                limit=limit,
                include_custom=include_custom,
            )
            return {"status": "completed", **results}
        finally:
            await operation_registry.end_operation(operation_type)
    
    # Create a run record for tracking
    from app.db import MaintenanceRun
    run = MaintenanceRun(
        run_type="ats_type" if ats_type else "full",
        ats_type=ats_type,
        status="running",
        current_step="Starting maintenance...",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    run_id = run.id
    
    async def run_in_background():
        from app.engines.maintenance.service import MaintenanceEngine
        
        if not await operation_registry.start_operation(operation_type):
            return
        
        try:
            async with async_session_factory() as session:
                engine = MaintenanceEngine(session)
                await engine.run_maintenance(
                    ats_type=ats_type,
                    limit=limit,
                    run_id=run_id,
                    include_custom=include_custom,
                )
        finally:
            await operation_registry.end_operation(operation_type)
    
    background_tasks.add_task(run_in_background)
    
    msg = f"Maintenance started for up to {limit} companies"
    if ats_type:
        msg += f" (ATS: {ats_type})"
    elif include_custom:
        msg += " (including custom pages)"
    
    return {
        "status": "started",
        "message": msg,
        "run_id": str(run_id),
        "operation_type": operation_type,
    }


@router.post("/maintenance/runs/{run_id}/cancel")
async def cancel_maintenance_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running maintenance process."""
    from app.db import MaintenanceRun
    
    result = await db.execute(
        select(MaintenanceRun).where(MaintenanceRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Maintenance run not found")
    
    if run.status != "running":
        raise HTTPException(status_code=400, detail=f"Cannot cancel run with status: {run.status}")
    
    # Mark as cancelled
    run.status = "cancelled"
    run.error_message = "Cancelled by user"
    run.completed_at = func.now()
    
    await db.commit()
    
    return {"status": "cancelled", "run_id": str(run_id)}


@router.get("/maintenance/delisted-jobs")
async def get_delisted_jobs(
    db: AsyncSession = Depends(get_db),
    days: int = Query(7, ge=1, le=90),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get recently delisted jobs."""
    offset = (page - 1) * page_size
    
    result = await db.execute(text("""
        SELECT 
            j.id,
            j.title,
            j.source_url,
            c.name as company_name,
            c.ats_type,
            j.delisted_at,
            j.delist_reason,
            j.created_at
        FROM jobs j
        JOIN companies c ON j.company_id = c.id
        WHERE j.is_active = false
          AND j.delisted_at IS NOT NULL
          AND j.delisted_at > NOW() - INTERVAL ':days days'
        ORDER BY j.delisted_at DESC
        OFFSET :offset LIMIT :limit
    """.replace(":days", str(days))), {"offset": offset, "limit": page_size})
    
    jobs = [
        {
            "id": str(row[0]),
            "title": row[1],
            "source_url": row[2],
            "company_name": row[3],
            "ats_type": row[4],
            "delisted_at": row[5].isoformat() if row[5] else None,
            "delist_reason": row[6],
            "created_at": row[7].isoformat() if row[7] else None,
        }
        for row in result.fetchall()
    ]
    
    # Get total count
    count_result = await db.execute(text(f"""
        SELECT COUNT(*) FROM jobs
        WHERE is_active = false
          AND delisted_at IS NOT NULL
          AND delisted_at > NOW() - INTERVAL '{days} days'
    """))
    total = count_result.scalar() or 0
    
    return {
        "jobs": jobs,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
