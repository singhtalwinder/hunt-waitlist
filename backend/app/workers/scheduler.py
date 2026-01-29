"""Task scheduler using APScheduler."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import structlog

from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger()

scheduler = AsyncIOScheduler()


def setup_scheduler():
    """Configure and start the scheduler."""

    # Import tasks here to avoid circular imports
    from app.workers.tasks import (
        crawl_all_companies_task,
        match_all_candidates_task,
        send_all_digests_task,
        render_unrendered_task,
        enrich_jobs_task,
        run_discovery_task,
        run_discovery_source_task,
        process_discovery_queue_task,
        ats_prober_task,
    )

    # ============================================
    # DISCOVERY SCHEDULES (Per-Source)
    # ============================================

    # Funding News - Every hour (RSS feeds update frequently)
    scheduler.add_job(
        lambda: run_discovery_source_task.send("funding_news"),
        trigger=IntervalTrigger(hours=1),
        id="discovery_funding_news",
        name="Discovery: Funding News (hourly)",
        replace_existing=True,
    )

    # Network Crawler - Every 4 hours (slow, batched)
    scheduler.add_job(
        lambda: run_discovery_source_task.send("network_crawler"),
        trigger=IntervalTrigger(hours=4),
        id="discovery_network_crawler",
        name="Discovery: Network Crawler (4h)",
        replace_existing=True,
    )

    # Job Aggregators - Every 4 hours
    scheduler.add_job(
        lambda: run_discovery_source_task.send("job_aggregators"),
        trigger=IntervalTrigger(hours=4),
        id="discovery_job_aggregators",
        name="Discovery: Job Aggregators (4h)",
        replace_existing=True,
    )

    # ATS Directories - Daily at 3 AM UTC
    scheduler.add_job(
        lambda: run_discovery_source_task.send("ats_directories"),
        trigger=CronTrigger(hour=3, minute=0),
        id="discovery_ats_directories",
        name="Discovery: ATS Directories (daily)",
        replace_existing=True,
    )

    # GitHub Orgs - Daily at 4 AM UTC
    scheduler.add_job(
        lambda: run_discovery_source_task.send("github_orgs"),
        trigger=CronTrigger(hour=4, minute=0),
        id="discovery_github_orgs",
        name="Discovery: GitHub Orgs (daily)",
        replace_existing=True,
    )

    # YC Companies - Weekly on Sunday at 2 AM UTC
    scheduler.add_job(
        lambda: run_discovery_source_task.send("yc_directory"),
        trigger=CronTrigger(day_of_week="sun", hour=2, minute=0),
        id="discovery_yc_companies",
        name="Discovery: YC Companies (weekly)",
        replace_existing=True,
    )

    # ATS Prober - Every 2 hours (continuous background probing)
    scheduler.add_job(
        lambda: ats_prober_task.send(limit=200),
        trigger=IntervalTrigger(hours=2),
        id="discovery_ats_prober",
        name="Discovery: ATS Prober (2h)",
        replace_existing=True,
    )

    # NOTE: Google Search is NOT scheduled - manual only (costs money)

    # Process discovery queue every 30 minutes
    scheduler.add_job(
        lambda: process_discovery_queue_task.send(100),
        trigger=IntervalTrigger(minutes=30),
        id="process_discovery_queue",
        name="Process discovery queue",
        replace_existing=True,
    )

    # ============================================
    # CRAWL SCHEDULES
    # ============================================

    # Crawl all companies every 6 hours
    scheduler.add_job(
        crawl_all_companies_task.send,
        trigger=IntervalTrigger(hours=6),
        id="crawl_all_companies",
        name="Crawl all companies",
        replace_existing=True,
    )

    # Render unrendered snapshots every hour
    scheduler.add_job(
        lambda: render_unrendered_task.send(50),
        trigger=IntervalTrigger(hours=1),
        id="render_unrendered",
        name="Render unrendered snapshots",
        replace_existing=True,
    )

    # ============================================
    # ENRICHMENT SCHEDULES
    # ============================================

    # Enrich jobs without descriptions every 2 hours
    scheduler.add_job(
        lambda: enrich_jobs_task.send(50),
        trigger=IntervalTrigger(hours=2),
        id="enrich_jobs",
        name="Enrich jobs without descriptions",
        replace_existing=True,
    )

    # ============================================
    # MATCHING SCHEDULES
    # ============================================

    # Run matching daily at 6 AM UTC
    scheduler.add_job(
        match_all_candidates_task.send,
        trigger=CronTrigger(hour=6, minute=0),
        id="daily_matching",
        name="Daily matching for all candidates",
        replace_existing=True,
    )

    # ============================================
    # NOTIFICATION SCHEDULES
    # ============================================

    # Send weekly digests on Monday at 9 AM UTC
    scheduler.add_job(
        send_all_digests_task.send,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="weekly_digests",
        name="Weekly job digest emails",
        replace_existing=True,
    )

    logger.info("Scheduler configured with jobs")


def start_scheduler():
    """Start the scheduler."""
    setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    """Stop the scheduler."""
    scheduler.shutdown()
    logger.info("Scheduler stopped")


# For running as standalone scheduler process
if __name__ == "__main__":
    import asyncio

    async def main():
        setup_scheduler()
        scheduler.start()
        logger.info("Scheduler started")
        
        # Keep the scheduler running
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            stop_scheduler()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Scheduler shutdown by keyboard interrupt")
