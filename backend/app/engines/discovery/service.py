"""Discovery Engine - identifies companies and career pages to crawl."""

import re
from typing import Optional
from urllib.parse import urlparse

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Company
from app.engines.discovery.seed_companies import SEED_COMPANIES
from app.engines.discovery.ats_detector import detect_ats_type, get_careers_url

logger = structlog.get_logger()


class DiscoveryEngine:
    """Engine for discovering companies and their career pages."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "HuntBot/1.0 (+https://hunt.dev/bot)"},
        )

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()

    async def seed_initial_companies(self) -> dict:
        """Seed database with initial company list."""
        created = 0
        updated = 0
        skipped = 0

        for company_data in SEED_COMPANIES:
            try:
                # Check if company exists
                result = await self.db.execute(
                    select(Company).where(Company.domain == company_data["domain"])
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update if needed
                    if (
                        existing.ats_type != company_data.get("ats_type")
                        or existing.careers_url != company_data.get("careers_url")
                    ):
                        existing.ats_type = company_data.get("ats_type")
                        existing.careers_url = company_data.get("careers_url")
                        existing.ats_identifier = company_data.get("ats_identifier")
                        existing.crawl_priority = company_data.get("crawl_priority", 50)
                        updated += 1
                    else:
                        skipped += 1
                else:
                    # Create new
                    company = Company(
                        name=company_data["name"],
                        domain=company_data["domain"],
                        careers_url=company_data.get("careers_url"),
                        ats_type=company_data.get("ats_type"),
                        ats_identifier=company_data.get("ats_identifier"),
                        crawl_priority=company_data.get("crawl_priority", 50),
                    )
                    self.db.add(company)
                    created += 1

            except Exception as e:
                logger.error("Failed to seed company", company=company_data["name"], error=str(e))
                skipped += 1

        await self.db.commit()

        logger.info(
            "Seeding complete",
            created=created,
            updated=updated,
            skipped=skipped,
        )

        return {"created": created, "updated": updated, "skipped": skipped}

    async def discover_company(
        self,
        name: str,
        domain: str,
        careers_url: Optional[str] = None,
    ) -> Optional[Company]:
        """Discover a company's ATS type and careers page."""
        # Try to find careers URL if not provided
        if not careers_url:
            careers_url = await get_careers_url(self.http_client, domain)

        if not careers_url:
            logger.warning("Could not find careers URL", domain=domain)
            return None

        # Detect ATS type
        ats_type, ats_identifier = await detect_ats_type(self.http_client, careers_url)

        # Create or update company
        result = await self.db.execute(select(Company).where(Company.domain == domain))
        company = result.scalar_one_or_none()

        if company:
            company.careers_url = careers_url
            company.ats_type = ats_type
            company.ats_identifier = ats_identifier
        else:
            company = Company(
                name=name,
                domain=domain,
                careers_url=careers_url,
                ats_type=ats_type,
                ats_identifier=ats_identifier,
            )
            self.db.add(company)

        await self.db.commit()
        await self.db.refresh(company)

        logger.info(
            "Discovered company",
            name=name,
            domain=domain,
            ats_type=ats_type,
            careers_url=careers_url,
        )

        return company

    async def discover_from_url(self, url: str) -> Optional[Company]:
        """Discover a company from a job board or careers URL."""
        parsed = urlparse(url)

        # Detect ATS type from URL
        ats_type, ats_identifier = await detect_ats_type(self.http_client, url)

        if not ats_type:
            logger.warning("Could not detect ATS type", url=url)
            return None

        # Extract company name/domain from URL or page
        domain = None
        name = ats_identifier or parsed.netloc

        # For known ATS, the identifier is usually the company
        if ats_type in ("greenhouse", "lever", "ashby"):
            # Try to find the company's main domain
            # This would require additional lookup or the page content
            pass

        # Create company without domain for now
        company = Company(
            name=name.title().replace("-", " ").replace("_", " "),
            domain=domain,
            careers_url=url,
            ats_type=ats_type,
            ats_identifier=ats_identifier,
        )
        self.db.add(company)
        await self.db.commit()
        await self.db.refresh(company)

        return company

    async def get_companies_to_crawl(
        self,
        ats_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[Company]:
        """Get companies that need to be crawled, ordered by priority."""
        query = (
            select(Company)
            .where(Company.is_active == True)
            .where(Company.careers_url.isnot(None))
            .order_by(Company.crawl_priority.desc(), Company.last_crawled_at.asc().nullsfirst())
            .limit(limit)
        )

        if ats_type:
            query = query.where(Company.ats_type == ats_type)

        result = await self.db.execute(query)
        return list(result.scalars().all())


async def seed_companies(db: AsyncSession) -> dict:
    """Seed initial companies into the database."""
    engine = DiscoveryEngine(db)
    try:
        return await engine.seed_initial_companies()
    finally:
        await engine.close()
