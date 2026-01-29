"""Extraction Engine - main service for extracting jobs from pages."""

from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Company, CrawlSnapshot, JobRaw
from app.engines.extract.greenhouse import GreenhouseExtractor
from app.engines.extract.lever import LeverExtractor
from app.engines.extract.ashby import AshbyExtractor
from app.engines.extract.workable import WorkableExtractor
from app.engines.extract.generic import GenericExtractor
from app.engines.extract.llm_fallback import LLMFallbackExtractor
from app.engines.extract.base import ExtractedJob

# New ATS extractors
from app.engines.extract.bamboohr import BambooHRExtractor
from app.engines.extract.zoho_recruit import ZohoRecruitExtractor
from app.engines.extract.bullhorn import BullhornExtractor
from app.engines.extract.gem import GemExtractor
from app.engines.extract.jazzhr import JazzHRExtractor
from app.engines.extract.freshteam import FreshteamExtractor
from app.engines.extract.recruitee import RecruiteeExtractor
from app.engines.extract.pinpoint import PinpointExtractor
from app.engines.extract.pcrecruiter import PCRecruiterExtractor
from app.engines.extract.recruitcrm import RecruitCRMExtractor
from app.engines.extract.manatal import ManatalExtractor
from app.engines.extract.recooty import RecootyExtractor
from app.engines.extract.successfactors import SuccessFactorsExtractor
from app.engines.extract.gohire import GoHireExtractor
from app.engines.extract.folkshr import FolksHRExtractor
from app.engines.extract.boon import BoonExtractor
from app.engines.extract.talentreef import TalentReefExtractor
from app.engines.extract.eddy import EddyExtractor
from app.engines.extract.smartrecruiters import SmartRecruitersExtractor
from app.engines.extract.jobvite import JobviteExtractor
from app.engines.extract.icims import ICIMSExtractor

logger = structlog.get_logger()


class ExtractionEngine:
    """Engine for extracting jobs from crawled pages."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.extractors = {
            # Core ATS platforms (already implemented)
            "greenhouse": GreenhouseExtractor(),
            "lever": LeverExtractor(),
            "ashby": AshbyExtractor(),
            "workable": WorkableExtractor(),
            # New ATS platforms
            "bamboohr": BambooHRExtractor(),
            "zoho_recruit": ZohoRecruitExtractor(),
            "bullhorn": BullhornExtractor(),
            "gem": GemExtractor(),
            "jazzhr": JazzHRExtractor(),
            "freshteam": FreshteamExtractor(),
            "recruitee": RecruiteeExtractor(),
            "pinpoint": PinpointExtractor(),
            "pcrecruiter": PCRecruiterExtractor(),
            "recruitcrm": RecruitCRMExtractor(),
            "manatal": ManatalExtractor(),
            "recooty": RecootyExtractor(),
            "successfactors": SuccessFactorsExtractor(),
            "gohire": GoHireExtractor(),
            "folkshr": FolksHRExtractor(),
            "boon": BoonExtractor(),
            "talentreef": TalentReefExtractor(),
            "eddy": EddyExtractor(),
            # Additional popular ATS platforms
            "smartrecruiters": SmartRecruitersExtractor(),
            "jobvite": JobviteExtractor(),
            "icims": ICIMSExtractor(),
        }
        self.generic_extractor = GenericExtractor()
        self.llm_extractor = LLMFallbackExtractor()

    async def extract_from_snapshot(
        self,
        snapshot_id: UUID,
        use_llm_fallback: bool = True,
    ) -> list[JobRaw]:
        """Extract jobs from a crawl snapshot."""
        # Get snapshot with company
        result = await self.db.execute(
            select(CrawlSnapshot, Company)
            .join(Company, CrawlSnapshot.company_id == Company.id)
            .where(CrawlSnapshot.id == snapshot_id)
        )
        row = result.first()

        if not row:
            logger.warning("Snapshot not found", snapshot_id=str(snapshot_id))
            return []

        snapshot, company = row

        if not snapshot.html_content:
            logger.warning("Snapshot has no content", snapshot_id=str(snapshot_id))
            return []

        logger.info(
            "Extracting jobs",
            company=company.name,
            ats_type=company.ats_type,
            snapshot_id=str(snapshot_id),
        )

        # Get appropriate extractor
        extracted_jobs: list[ExtractedJob] = []

        if company.ats_type and company.ats_type in self.extractors:
            # Use ATS-specific extractor
            extractor = self.extractors[company.ats_type]
            extracted_jobs = await extractor.extract(
                html=snapshot.html_content,
                url=snapshot.url,
                company_identifier=company.ats_identifier,
            )
        else:
            # Try generic extractor
            extracted_jobs = await self.generic_extractor.extract(
                html=snapshot.html_content,
                url=snapshot.url,
            )

        # If no jobs found and LLM fallback enabled
        if not extracted_jobs and use_llm_fallback:
            logger.info("Using LLM fallback", company=company.name)
            extracted_jobs = await self.llm_extractor.extract(
                html=snapshot.html_content,
                url=snapshot.url,
            )

        # Save to database
        saved_jobs = []
        for job in extracted_jobs:
            try:
                raw_job = await self._save_raw_job(company.id, job)
                if raw_job:
                    saved_jobs.append(raw_job)
            except Exception as e:
                logger.error(
                    "Failed to save job",
                    title=job.title,
                    error=str(e),
                )

        logger.info(
            "Extraction complete",
            company=company.name,
            jobs_found=len(extracted_jobs),
            jobs_saved=len(saved_jobs),
        )

        return saved_jobs

    async def _save_raw_job(
        self,
        company_id: UUID,
        job: ExtractedJob,
    ) -> Optional[JobRaw]:
        """Save extracted job to database."""
        # Check if job already exists
        result = await self.db.execute(
            select(JobRaw).where(
                JobRaw.company_id == company_id,
                JobRaw.source_url == job.source_url,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.title_raw = job.title
            existing.description_raw = job.description
            existing.location_raw = job.location
            existing.department_raw = job.department
            existing.employment_type_raw = job.employment_type
            existing.posted_at_raw = job.posted_at
            existing.salary_raw = job.salary
            return existing
        else:
            # Create new
            raw_job = JobRaw(
                company_id=company_id,
                source_url=job.source_url,
                title_raw=job.title,
                description_raw=job.description,
                location_raw=job.location,
                department_raw=job.department,
                employment_type_raw=job.employment_type,
                posted_at_raw=job.posted_at,
                salary_raw=job.salary,
            )
            self.db.add(raw_job)
            await self.db.flush()
            return raw_job

    async def extract_for_company(
        self,
        company_id: UUID,
        use_llm_fallback: bool = True,
    ) -> list[JobRaw]:
        """Extract jobs from the latest snapshot for a company."""
        # Get latest snapshot
        result = await self.db.execute(
            select(CrawlSnapshot)
            .where(CrawlSnapshot.company_id == company_id)
            .order_by(CrawlSnapshot.crawled_at.desc())
            .limit(1)
        )
        snapshot = result.scalar_one_or_none()

        if not snapshot:
            logger.warning("No snapshot found for company", company_id=str(company_id))
            return []

        jobs = await self.extract_from_snapshot(snapshot.id, use_llm_fallback)
        await self.db.commit()

        return jobs


async def extract_jobs_for_company(company_id: str):
    """Extract jobs for a company (for background task)."""
    from app.db import async_session_factory

    async with async_session_factory() as db:
        engine = ExtractionEngine(db)
        await engine.extract_for_company(UUID(company_id))
