"""Workable job extractor."""

import json
from typing import Optional

import structlog

from app.engines.extract.base import BaseExtractor, ExtractedJob

logger = structlog.get_logger()


class WorkableExtractor(BaseExtractor):
    """Extract jobs from Workable widget API responses."""

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from Workable API JSON response."""
        jobs = []

        try:
            # The content should be JSON from the widget API
            if html.strip().startswith("{"):
                data = json.loads(html)
                jobs = self._extract_from_json(data)
            else:
                logger.warning("Workable content is not JSON")

        except Exception as e:
            logger.error("Workable extraction failed", error=str(e))

        logger.info("Extracted from Workable", job_count=len(jobs))
        return jobs

    def _extract_from_json(self, data: dict) -> list[ExtractedJob]:
        """Extract jobs from Workable widget API response."""
        jobs = []

        for job in data.get("jobs", []):
            try:
                title = job.get("title", "")
                if not title:
                    continue

                # Build location using base class helper
                location = self._build_location_from_parts(
                    city=job.get("city"),
                    state=job.get("state"),
                    country=job.get("country"),
                )

                # Get job URL
                source_url = job.get("url") or job.get("shortlink")

                jobs.append(
                    ExtractedJob(
                        title=title,
                        source_url=source_url,
                        location=location,
                        department=job.get("department"),
                        employment_type=job.get("employment_type") or job.get("type"),
                        posted_at=job.get("published_on") or job.get("created_at"),
                    )
                )

            except Exception as e:
                logger.debug(f"Failed to extract Workable job: {e}")

        return jobs
