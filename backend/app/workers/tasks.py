"""Background task definitions using Dramatiq."""

import asyncio
from typing import Optional

import dramatiq
from dramatiq.brokers.redis import RedisBroker
import structlog

from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger()

# Configure Redis broker
redis_broker = RedisBroker(url=str(settings.redis_url))
dramatiq.set_broker(redis_broker)


def run_async(coro):
    """Helper to run async functions in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================
# CRAWL TASKS
# ============================================


@dramatiq.actor(max_retries=3, min_backoff=30000)
def crawl_company_task(company_id: str):
    """Crawl a single company's career page."""
    from app.engines.crawl.service import crawl_company

    logger.info("Starting crawl task", company_id=company_id)
    run_async(crawl_company(company_id))
    logger.info("Crawl task complete", company_id=company_id)


@dramatiq.actor(max_retries=1)
def crawl_all_companies_task():
    """Crawl all active companies."""
    from app.engines.crawl.service import crawl_all_companies

    logger.info("Starting crawl all task")
    run_async(crawl_all_companies())
    logger.info("Crawl all task complete")


@dramatiq.actor(max_retries=3)
def crawl_by_ats_task(ats_type: str, limit: int = 100):
    """Crawl all companies of a specific ATS type."""
    from app.db import async_session_factory
    from app.engines.crawl.service import CrawlEngine

    async def crawl_by_ats():
        async with async_session_factory() as db:
            engine = CrawlEngine(db)
            try:
                await engine.crawl_by_ats_type(ats_type, limit)
            finally:
                await engine.close()

    logger.info("Starting ATS crawl task", ats_type=ats_type)
    run_async(crawl_by_ats())
    logger.info("ATS crawl task complete", ats_type=ats_type)


# ============================================
# RENDER TASKS
# ============================================


@dramatiq.actor(max_retries=2, min_backoff=60000)
def render_company_task(company_id: str):
    """Render the latest snapshot for a company."""
    from app.engines.render.service import render_company

    logger.info("Starting render task", company_id=company_id)
    run_async(render_company(company_id))
    logger.info("Render task complete", company_id=company_id)


@dramatiq.actor(max_retries=1)
def render_unrendered_task(limit: int = 50):
    """Render all unrendered snapshots."""
    from app.engines.render.service import render_unrendered_snapshots

    logger.info("Starting render unrendered task")
    run_async(render_unrendered_snapshots(limit))
    logger.info("Render unrendered task complete")


# ============================================
# EXTRACTION TASKS
# ============================================


@dramatiq.actor(max_retries=3)
def extract_company_task(company_id: str):
    """Extract jobs from a company's snapshots."""
    from app.engines.extract.service import extract_jobs_for_company

    logger.info("Starting extraction task", company_id=company_id)
    run_async(extract_jobs_for_company(company_id))
    logger.info("Extraction task complete", company_id=company_id)


# ============================================
# NORMALIZATION TASKS
# ============================================


@dramatiq.actor(max_retries=3)
def normalize_company_task(company_id: str):
    """Normalize jobs for a company."""
    from app.engines.normalize.service import normalize_jobs_for_company

    logger.info("Starting normalization task", company_id=company_id)
    run_async(normalize_jobs_for_company(company_id))
    logger.info("Normalization task complete", company_id=company_id)


# ============================================
# ENRICHMENT TASKS
# ============================================


@dramatiq.actor(max_retries=3, min_backoff=60000)
def enrich_jobs_task(limit: int = 50, company_id: Optional[str] = None):
    """Enrich jobs that are missing descriptions."""
    from app.engines.enrich.service import enrich_jobs_without_descriptions

    logger.info("Starting enrichment task", limit=limit, company_id=company_id)
    run_async(enrich_jobs_without_descriptions(limit=limit, company_id=company_id))
    logger.info("Enrichment task complete")


@dramatiq.actor(max_retries=1)
def enrich_all_jobs_task(batch_size: int = 50, max_batches: int = 10):
    """Enrich all jobs missing descriptions in batches."""
    from app.engines.enrich.service import enrich_jobs_without_descriptions

    logger.info("Starting enrich all jobs task", batch_size=batch_size, max_batches=max_batches)

    for batch_num in range(max_batches):
        enriched = run_async(enrich_jobs_without_descriptions(limit=batch_size))
        logger.info(f"Enrichment batch {batch_num + 1} complete", enriched=enriched)

        # Stop if no more jobs to enrich
        if enriched == 0:
            break

    logger.info("Enrich all jobs task complete")


# ============================================
# MATCHING TASKS
# ============================================


@dramatiq.actor(max_retries=3)
def match_candidate_task(candidate_id: str):
    """Run matching for a single candidate."""
    from app.engines.match.service import run_matching_for_candidate

    logger.info("Starting matching task", candidate_id=candidate_id)
    run_async(run_matching_for_candidate(candidate_id))
    logger.info("Matching task complete", candidate_id=candidate_id)


@dramatiq.actor(max_retries=1)
def match_all_candidates_task():
    """Run matching for all active candidates."""
    from app.engines.match.service import run_matching_for_all

    logger.info("Starting match all task")
    run_async(run_matching_for_all())
    logger.info("Match all task complete")


# ============================================
# NOTIFICATION TASKS
# ============================================


@dramatiq.actor(max_retries=3)
def send_digest_task(candidate_id: str):
    """Send job digest to a single candidate."""
    from app.engines.feedback.notifier import send_digest

    logger.info("Starting digest task", candidate_id=candidate_id)
    run_async(send_digest(candidate_id))
    logger.info("Digest task complete", candidate_id=candidate_id)


@dramatiq.actor(max_retries=1)
def send_all_digests_task():
    """Send job digests to all eligible candidates."""
    from app.engines.feedback.notifier import send_all_digests

    logger.info("Starting send all digests task")
    run_async(send_all_digests())
    logger.info("Send all digests task complete")


# ============================================
# DISCOVERY TASKS
# ============================================


@dramatiq.actor(max_retries=1, time_limit=3600000)  # 1 hour time limit
def run_discovery_task(source_names: Optional[list] = None, force_network_recrawl: bool = False):
    """Run company discovery from all or specified sources.
    
    Args:
        source_names: Optional list of source names to run (runs all if None)
        force_network_recrawl: If True, re-crawl all companies in network_crawler
                               (by default, only crawls companies never crawled before)
    """
    from app.db import async_session_factory
    from app.engines.discovery.orchestrator import DiscoveryOrchestrator

    async def run_discovery():
        async with async_session_factory() as db:
            orchestrator = DiscoveryOrchestrator(db)
            stats = await orchestrator.run_discovery(
                source_names=source_names,
                force_network_recrawl=force_network_recrawl,
            )
            return stats

    logger.info("Starting discovery task", sources=source_names, force_recrawl=force_network_recrawl)
    stats = run_async(run_discovery())
    
    # Log summary
    total_new = sum(s.new_companies for s in stats)
    total_discovered = sum(s.total_discovered for s in stats)
    logger.info(
        "Discovery task complete",
        total_discovered=total_discovered,
        new_companies=total_new,
        sources=[s.source for s in stats],
    )


@dramatiq.actor(max_retries=3, min_backoff=30000)
def process_discovery_queue_task(limit: int = 100, detect_ats: bool = True):
    """Process items from the discovery queue."""
    from app.db import async_session_factory
    from app.engines.discovery.orchestrator import DiscoveryOrchestrator

    async def process_queue():
        async with async_session_factory() as db:
            orchestrator = DiscoveryOrchestrator(db)
            stats = await orchestrator.process_queue(limit=limit, detect_ats=detect_ats)
            return stats

    logger.info("Starting discovery queue processing", limit=limit)
    stats = run_async(process_queue())
    logger.info(
        "Discovery queue processing complete",
        processed=stats.get("processed", 0),
        created=stats.get("created", 0),
        failed=stats.get("failed", 0),
    )


@dramatiq.actor(max_retries=1, time_limit=1800000)  # 30 min limit
def run_discovery_source_task(source_name: str):
    """Run discovery for a single source."""
    from app.db import async_session_factory
    from app.engines.discovery.orchestrator import DiscoveryOrchestrator

    async def run_source():
        async with async_session_factory() as db:
            orchestrator = DiscoveryOrchestrator(db)
            stats = await orchestrator.run_discovery(source_names=[source_name])
            return stats

    logger.info(f"Starting scheduled discovery: {source_name}")
    stats = run_async(run_source())
    
    if stats:
        s = stats[0]
        logger.info(
            f"Discovery complete: {source_name}",
            new=s.new_companies,
            duplicates=s.skipped_duplicates,
            errors=s.errors,
        )


@dramatiq.actor(max_retries=1, time_limit=3600000)  # 1 hour limit
def ats_prober_task(limit: int = 200):
    """Run ATS prober for companies without ATS detection."""
    from app.db import async_session_factory
    from app.engines.discovery.orchestrator import DiscoveryOrchestrator

    async def run_prober():
        async with async_session_factory() as db:
            orchestrator = DiscoveryOrchestrator(db)
            stats = await orchestrator.run_discovery(source_names=["ats_prober"])
            return stats

    logger.info("Starting ATS prober task", limit=limit)
    stats = run_async(run_prober())
    
    if stats:
        s = stats[0]
        logger.info("ATS prober complete", verified=s.new_companies, errors=s.errors)


# ============================================
# VERIFICATION TASKS
# ============================================


@dramatiq.actor(max_retries=1, time_limit=3600000)  # 1 hour time limit
def verify_jobs_task(board: str = "linkedin", limit: int = 100):
    """Verify jobs against a job board to check uniqueness.

    Args:
        board: The job board to check (linkedin, indeed).
        limit: Max number of jobs to verify.
    """
    from app.db import async_session_factory
    from app.engines.verify.service import VerificationEngine

    async def run_verification():
        async with async_session_factory() as db:
            engine = VerificationEngine(db)
            try:
                return await engine.verify_batch(board=board, limit=limit)
            finally:
                await engine.close()

    logger.info("Starting verification task", board=board, limit=limit)
    run = run_async(run_verification())
    logger.info(
        "Verification task complete",
        board=board,
        jobs_checked=run.jobs_checked,
        jobs_found=run.jobs_found,
        jobs_unique=run.jobs_unique,
        uniqueness_rate=run.uniqueness_rate,
    )


@dramatiq.actor(max_retries=1)
def verify_all_boards_task(limit: int = 100):
    """Verify jobs against all supported job boards.

    Args:
        limit: Max number of jobs to verify per board.
    """
    logger.info("Starting verification for all boards", limit=limit)

    # Queue verification for each board
    for board in ["linkedin", "indeed"]:
        verify_jobs_task.send(board=board, limit=limit)

    logger.info("Verification tasks queued for all boards")


@dramatiq.actor(max_retries=1)
def run_verification_report_task():
    """Generate and log verification stats report."""
    from app.engines.verify.service import get_verification_stats

    logger.info("Generating verification report")
    stats = run_async(get_verification_stats())

    # Log the stats
    logger.info(
        "Verification report",
        total_jobs=stats.get("total_jobs", 0),
        boards=stats.get("boards", {}),
    )

    # Log per-board details
    for board, board_stats in stats.get("boards", {}).items():
        logger.info(
            f"Board stats: {board}",
            verified=board_stats.get("verified", 0),
            unique=board_stats.get("unique", 0),
            found=board_stats.get("found", 0),
            uniqueness_rate=f"{board_stats.get('uniqueness_rate', 0) * 100:.1f}%",
            coverage_rate=f"{board_stats.get('coverage_rate', 0) * 100:.1f}%",
        )


# ============================================
# PIPELINE TASKS
# ============================================


@dramatiq.actor(max_retries=1)
def run_full_pipeline_task(company_id: str):
    """Run full pipeline for a company: crawl -> render -> extract -> normalize -> enrich."""
    logger.info("Starting full pipeline", company_id=company_id)

    # Chain the tasks
    crawl_company_task.send(company_id)
    # Note: In production, you'd use message options to chain these properly
    # For now, each task is independent
    # After extraction/normalization, enrich jobs for this company
    enrich_jobs_task.send(limit=100, company_id=company_id)

    logger.info("Pipeline tasks queued", company_id=company_id)


@dramatiq.actor(max_retries=1)
def run_daily_pipeline_task():
    """Run daily pipeline for all companies."""
    logger.info("Starting daily pipeline")

    # 1. Crawl all companies
    crawl_all_companies_task.send()

    # 2. After crawling, we'd trigger extraction and normalization
    # This is simplified - in production, use proper task chaining

    # 3. Enrich jobs that are missing descriptions
    enrich_all_jobs_task.send(batch_size=50, max_batches=20)

    # 4. Run matching for all candidates
    match_all_candidates_task.send()

    logger.info("Daily pipeline tasks queued")


@dramatiq.actor(max_retries=1)
def run_weekly_digests_task():
    """Send weekly digest emails."""
    logger.info("Starting weekly digests")
    send_all_digests_task.send()
    logger.info("Weekly digests task queued")
