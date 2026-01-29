"""Verification engine for checking job uniqueness across job boards."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Company, Job, JobBoardListing, VerificationRun
from app.engines.verify.searcher import JobBoardScraper

logger = structlog.get_logger()

# Supported job boards
SUPPORTED_BOARDS = ["linkedin", "indeed"]


class VerificationEngine:
    """Engine for verifying job uniqueness across job boards."""

    def __init__(self, db: AsyncSession):
        """Initialize the verification engine.

        Args:
            db: Async database session.
        """
        self.db = db
        self.settings = get_settings()
        self.searcher = JobBoardScraper()

    async def close(self) -> None:
        """Clean up resources."""
        await self.searcher.close()

    async def verify_job(
        self,
        job_id: UUID,
        boards: Optional[list[str]] = None,
    ) -> dict[str, bool]:
        """Verify a single job against specified boards.

        Args:
            job_id: The job ID to verify.
            boards: List of boards to check. Defaults to all supported boards.

        Returns:
            Dict mapping board name to found status.
        """
        boards = boards or SUPPORTED_BOARDS

        # Get job with company info
        result = await self.db.execute(
            select(Job, Company)
            .join(Company, Job.company_id == Company.id)
            .where(Job.id == job_id)
        )
        row = result.first()

        if not row:
            logger.warning("Job not found for verification", job_id=str(job_id))
            return {}

        job, company = row

        results = {}
        for board in boards:
            if board not in SUPPORTED_BOARDS:
                logger.warning("Unsupported board", board=board)
                continue

            search_result = await self.searcher.search_job_on_board(
                company=company.name,
                title=job.title,
                board=board,
            )

            # Build search query for logging
            search_query = f'"{company.name}" "{job.title}" site:{board}'

            # Upsert the verification result
            listing = JobBoardListing(
                job_id=job.id,
                board=board,
                found=search_result.found,
                confidence=search_result.confidence,
                listing_url=search_result.listing_url,
                search_query=search_query,
                search_result_count=search_result.result_count,
                verified_at=datetime.now(timezone.utc),
            )

            # Use merge to handle upsert
            await self.db.merge(listing)
            results[board] = search_result.found

            logger.info(
                "Verified job on board",
                job_id=str(job_id),
                job_title=job.title,
                company=company.name,
                board=board,
                found=search_result.found,
                confidence=search_result.confidence,
            )

            # Small delay between searches to be nice to the API
            await asyncio.sleep(0.5)

        await self.db.commit()
        return results

    async def verify_batch(
        self,
        board: str = "linkedin",
        limit: Optional[int] = None,
        reverify_after_days: Optional[int] = None,
    ) -> VerificationRun:
        """Verify a batch of jobs against a board.

        Args:
            board: The board to check.
            limit: Max jobs to verify. Defaults to settings.
            reverify_after_days: Days before re-verification. Defaults to settings.

        Returns:
            VerificationRun with stats.
        """
        limit = limit or self.settings.verification_sample_size
        reverify_after_days = reverify_after_days or self.settings.verification_reverify_days

        # Create verification run
        run = VerificationRun(
            board=board,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        try:
            # Get jobs needing verification
            jobs = await self._get_jobs_for_verification(
                board=board,
                limit=limit,
                reverify_after_days=reverify_after_days,
            )

            logger.info(
                "Starting verification batch",
                run_id=str(run.id),
                board=board,
                jobs_to_verify=len(jobs),
            )

            jobs_found = 0
            jobs_unique = 0

            for job, company in jobs:
                search_result = await self.searcher.search_job_on_board(
                    company=company.name,
                    title=job.title,
                    board=board,
                )

                search_query = f'"{company.name}" "{job.title}" site:{board}'

                # Upsert verification result
                listing = JobBoardListing(
                    job_id=job.id,
                    board=board,
                    found=search_result.found,
                    confidence=search_result.confidence,
                    listing_url=search_result.listing_url,
                    search_query=search_query,
                    search_result_count=search_result.result_count,
                    verified_at=datetime.now(timezone.utc),
                )
                await self.db.merge(listing)

                if search_result.found:
                    jobs_found += 1
                else:
                    jobs_unique += 1

                run.jobs_checked += 1

                # Commit periodically
                if run.jobs_checked % 10 == 0:
                    await self.db.commit()
                    logger.info(
                        "Verification progress",
                        run_id=str(run.id),
                        checked=run.jobs_checked,
                        found=jobs_found,
                        unique=jobs_unique,
                    )

                # Rate limiting
                await asyncio.sleep(0.5)

            # Finalize run
            run.jobs_found = jobs_found
            run.jobs_unique = jobs_unique
            run.uniqueness_rate = (
                jobs_unique / run.jobs_checked if run.jobs_checked > 0 else 0.0
            )
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)

            await self.db.commit()

            logger.info(
                "Verification batch complete",
                run_id=str(run.id),
                board=board,
                jobs_checked=run.jobs_checked,
                jobs_found=jobs_found,
                jobs_unique=jobs_unique,
                uniqueness_rate=run.uniqueness_rate,
            )

            return run

        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            logger.error(
                "Verification batch failed",
                run_id=str(run.id),
                error=str(e),
            )
            raise

    async def _get_jobs_for_verification(
        self,
        board: str,
        limit: int,
        reverify_after_days: int,
    ) -> list[tuple[Job, Company]]:
        """Get jobs that need verification.

        Args:
            board: The board to check.
            limit: Max jobs to return.
            reverify_after_days: Days before re-verification.

        Returns:
            List of (Job, Company) tuples.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=reverify_after_days)

        # Subquery to get last verification time for each job on this board
        last_verified = (
            select(
                JobBoardListing.job_id,
                func.max(JobBoardListing.verified_at).label("last_verified"),
            )
            .where(JobBoardListing.board == board)
            .group_by(JobBoardListing.job_id)
            .subquery()
        )

        # Get active jobs that haven't been verified recently
        query = (
            select(Job, Company)
            .join(Company, Job.company_id == Company.id)
            .outerjoin(last_verified, Job.id == last_verified.c.job_id)
            .where(Job.is_active == True)  # noqa: E712
            .where(
                (last_verified.c.last_verified == None)  # noqa: E711
                | (last_verified.c.last_verified < cutoff)
            )
            .order_by(
                last_verified.c.last_verified.nulls_first(),
                Job.created_at.desc(),
            )
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.all())

    async def get_uniqueness_stats(
        self,
        board: Optional[str] = None,
    ) -> dict:
        """Get current uniqueness statistics.

        Args:
            board: Optional board to filter by.

        Returns:
            Dict with stats per board.
        """
        # Count total active jobs
        total_result = await self.db.execute(
            select(func.count(Job.id)).where(Job.is_active == True)  # noqa: E712
        )
        total_jobs = total_result.scalar() or 0

        # Get per-board stats
        board_filter = JobBoardListing.board == board if board else True

        stats_query = (
            select(
                JobBoardListing.board,
                func.count(JobBoardListing.id).label("verified"),
                func.count(JobBoardListing.id)
                .filter(JobBoardListing.found == True)  # noqa: E712
                .label("found"),
                func.count(JobBoardListing.id)
                .filter(JobBoardListing.found == False)  # noqa: E712
                .label("unique"),
                func.max(JobBoardListing.verified_at).label("last_verified"),
            )
            .join(Job, JobBoardListing.job_id == Job.id)
            .where(Job.is_active == True)  # noqa: E712
            .where(board_filter)
            .group_by(JobBoardListing.board)
        )

        result = await self.db.execute(stats_query)
        rows = result.all()

        boards = {}
        for row in rows:
            verified = row.verified or 0
            found = row.found or 0
            unique = row.unique or 0

            boards[row.board] = {
                "verified": verified,
                "found": found,
                "unique": unique,
                "uniqueness_rate": unique / verified if verified > 0 else 0.0,
                "coverage_rate": verified / total_jobs if total_jobs > 0 else 0.0,
                "last_verified": row.last_verified.isoformat() if row.last_verified else None,
            }

        # Get recent runs
        runs_query = (
            select(VerificationRun)
            .where(VerificationRun.status == "completed")
            .order_by(VerificationRun.completed_at.desc())
            .limit(10)
        )
        runs_result = await self.db.execute(runs_query)
        recent_runs = [
            {
                "id": str(run.id),
                "board": run.board,
                "jobs_checked": run.jobs_checked,
                "uniqueness_rate": run.uniqueness_rate,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            }
            for run in runs_result.scalars()
        ]

        return {
            "total_jobs": total_jobs,
            "boards": boards,
            "recent_runs": recent_runs,
        }


async def verify_jobs_batch(
    board: str = "linkedin",
    limit: int = 100,
) -> VerificationRun:
    """Convenience function to run verification batch.

    Args:
        board: The board to check.
        limit: Max jobs to verify.

    Returns:
        VerificationRun with stats.
    """
    from app.db import async_session_factory

    async with async_session_factory() as db:
        engine = VerificationEngine(db)
        try:
            return await engine.verify_batch(board=board, limit=limit)
        finally:
            await engine.close()


async def get_verification_stats() -> dict:
    """Convenience function to get verification stats.

    Returns:
        Dict with stats.
    """
    from app.db import async_session_factory

    async with async_session_factory() as db:
        engine = VerificationEngine(db)
        try:
            return await engine.get_uniqueness_stats()
        finally:
            await engine.close()
