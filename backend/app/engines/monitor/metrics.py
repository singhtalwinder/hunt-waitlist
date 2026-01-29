"""Monitoring Engine - tracks system health and metrics."""

from datetime import datetime, timedelta
from typing import Optional

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Company, CrawlSnapshot, Job, JobRaw, CandidateProfile, Match, Metric

logger = structlog.get_logger()


class MonitoringEngine:
    """Engine for tracking system health and metrics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_metric(
        self,
        name: str,
        value: float,
        labels: Optional[dict] = None,
    ):
        """Record a metric value."""
        metric = Metric(
            name=name,
            value=value,
            labels=labels,
        )
        self.db.add(metric)
        await self.db.flush()

    async def get_system_health(self) -> dict:
        """Get overall system health status."""
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        health = {
            "status": "healthy",
            "issues": [],
            "metrics": {},
        }

        # Check crawl health
        crawl_metrics = await self._get_crawl_metrics(day_ago)
        health["metrics"]["crawl"] = crawl_metrics

        if crawl_metrics["success_rate"] < 0.9:
            health["issues"].append("Crawl success rate below 90%")
            health["status"] = "degraded"

        if crawl_metrics["jobs_discovered_24h"] == 0:
            health["issues"].append("No jobs discovered in last 24 hours")
            health["status"] = "warning"

        # Check extraction health
        extraction_metrics = await self._get_extraction_metrics(day_ago)
        health["metrics"]["extraction"] = extraction_metrics

        # Check matching health
        matching_metrics = await self._get_matching_metrics(day_ago)
        health["metrics"]["matching"] = matching_metrics

        if matching_metrics["match_yield"] == 0:
            health["issues"].append("No matches generated")
            health["status"] = "warning"

        # Check data freshness
        freshness_metrics = await self._get_freshness_metrics()
        health["metrics"]["freshness"] = freshness_metrics

        if freshness_metrics["avg_job_age_days"] > 14:
            health["issues"].append("Average job age exceeds 14 days")
            health["status"] = "warning"

        return health

    async def _get_crawl_metrics(self, since: datetime) -> dict:
        """Get crawl-related metrics."""
        # Total crawl attempts
        total_crawls = await self.db.scalar(
            select(func.count(CrawlSnapshot.id)).where(
                CrawlSnapshot.crawled_at >= since
            )
        ) or 0

        # Successful crawls (status 200)
        successful_crawls = await self.db.scalar(
            select(func.count(CrawlSnapshot.id)).where(
                CrawlSnapshot.crawled_at >= since,
                CrawlSnapshot.status_code == 200,
            )
        ) or 0

        # Jobs discovered
        jobs_discovered = await self.db.scalar(
            select(func.count(JobRaw.id)).where(
                JobRaw.extracted_at >= since
            )
        ) or 0

        success_rate = successful_crawls / total_crawls if total_crawls > 0 else 0

        return {
            "total_crawls_24h": total_crawls,
            "successful_crawls_24h": successful_crawls,
            "success_rate": round(success_rate, 3),
            "jobs_discovered_24h": jobs_discovered,
        }

    async def _get_extraction_metrics(self, since: datetime) -> dict:
        """Get extraction-related metrics."""
        # Raw jobs extracted
        raw_jobs = await self.db.scalar(
            select(func.count(JobRaw.id)).where(
                JobRaw.extracted_at >= since
            )
        ) or 0

        # Normalized jobs created
        normalized_jobs = await self.db.scalar(
            select(func.count(Job.id)).where(
                Job.created_at >= since
            )
        ) or 0

        # Extraction success rate
        success_rate = normalized_jobs / raw_jobs if raw_jobs > 0 else 0

        return {
            "raw_jobs_24h": raw_jobs,
            "normalized_jobs_24h": normalized_jobs,
            "extraction_success_rate": round(success_rate, 3),
        }

    async def _get_matching_metrics(self, since: datetime) -> dict:
        """Get matching-related metrics."""
        # Total matches created
        total_matches = await self.db.scalar(
            select(func.count(Match.id)).where(
                Match.created_at >= since
            )
        ) or 0

        # Average match score
        avg_score = await self.db.scalar(
            select(func.avg(Match.score)).where(
                Match.created_at >= since
            )
        )

        # Matches per candidate
        active_candidates = await self.db.scalar(
            select(func.count(CandidateProfile.id)).where(
                CandidateProfile.is_active == True
            )
        ) or 0

        match_yield = total_matches / active_candidates if active_candidates > 0 else 0

        return {
            "matches_created_24h": total_matches,
            "avg_match_score": round(avg_score, 3) if avg_score else 0,
            "active_candidates": active_candidates,
            "match_yield": round(match_yield, 2),
        }

    async def _get_freshness_metrics(self) -> dict:
        """Get data freshness metrics."""
        # Average job age
        avg_age = await self.db.scalar(
            select(
                func.avg(
                    func.extract("epoch", func.now() - Job.posted_at) / 86400
                )
            ).where(Job.is_active == True, Job.posted_at.isnot(None))
        )

        # Jobs by freshness bucket
        now = datetime.utcnow()

        jobs_today = await self.db.scalar(
            select(func.count(Job.id)).where(
                Job.is_active == True,
                Job.posted_at >= now - timedelta(days=1),
            )
        ) or 0

        jobs_week = await self.db.scalar(
            select(func.count(Job.id)).where(
                Job.is_active == True,
                Job.posted_at >= now - timedelta(days=7),
            )
        ) or 0

        jobs_month = await self.db.scalar(
            select(func.count(Job.id)).where(
                Job.is_active == True,
                Job.posted_at >= now - timedelta(days=30),
            )
        ) or 0

        return {
            "avg_job_age_days": round(avg_age, 1) if avg_age else 0,
            "jobs_posted_today": jobs_today,
            "jobs_posted_week": jobs_week,
            "jobs_posted_month": jobs_month,
        }

    async def record_crawl_result(
        self,
        company_id: str,
        ats_type: str,
        success: bool,
        jobs_found: int = 0,
    ):
        """Record crawl result for monitoring."""
        await self.record_metric(
            "crawl_result",
            1.0 if success else 0.0,
            {"company_id": company_id, "ats_type": ats_type},
        )

        if success and jobs_found > 0:
            await self.record_metric(
                "jobs_found",
                float(jobs_found),
                {"company_id": company_id, "ats_type": ats_type},
            )

    async def get_ats_stats(self) -> dict:
        """Get statistics per ATS type."""
        stats = {}

        # Companies by ATS
        result = await self.db.execute(
            select(Company.ats_type, func.count(Company.id))
            .where(Company.is_active == True)
            .group_by(Company.ats_type)
        )

        for ats_type, count in result:
            if ats_type:
                stats[ats_type] = {"companies": count}

        # Jobs by ATS
        result = await self.db.execute(
            select(Company.ats_type, func.count(Job.id))
            .join(Job, Company.id == Job.company_id)
            .where(Job.is_active == True)
            .group_by(Company.ats_type)
        )

        for ats_type, count in result:
            if ats_type and ats_type in stats:
                stats[ats_type]["jobs"] = count

        return stats


async def get_health_status() -> dict:
    """Get system health status (for API)."""
    from app.db import async_session_factory

    async with async_session_factory() as db:
        engine = MonitoringEngine(db)
        return await engine.get_system_health()
