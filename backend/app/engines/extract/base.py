"""Base classes for job extraction."""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any

from bs4 import BeautifulSoup


@dataclass
class ExtractedJob:
    """Raw extracted job data."""

    title: str
    source_url: str
    description: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    employment_type: Optional[str] = None
    posted_at: Optional[str] = None
    salary: Optional[str] = None
    remote: Optional[bool] = None
    requirements: list[str] = field(default_factory=list)


class BaseExtractor(ABC):
    """Base class for job extractors."""

    @abstractmethod
    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """
        Extract jobs from HTML content.

        Args:
            html: The HTML content to parse
            url: The URL the content was fetched from
            company_identifier: Optional ATS-specific company identifier

        Returns:
            List of extracted jobs
        """
        pass

    def _clean_text(self, text: Optional[str]) -> Optional[str]:
        """Clean and normalize text content."""
        if not text:
            return None

        # Remove extra whitespace
        text = " ".join(text.split())

        # Remove common unwanted characters
        text = text.strip()

        return text if text else None

    def _extract_salary(self, text: str) -> Optional[str]:
        """Extract salary information from text."""
        # Common salary patterns
        patterns = [
            r"\$[\d,]+(?:\s*-\s*\$[\d,]+)?(?:\s*(?:per|/)\s*(?:year|yr|hour|hr))?",
            r"[\d,]+k\s*-\s*[\d,]+k",
            r"£[\d,]+(?:\s*-\s*£[\d,]+)?",
            r"€[\d,]+(?:\s*-\s*€[\d,]+)?",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)

        return None

    # -------------------------------------------------------------------------
    # Location Helpers
    # -------------------------------------------------------------------------

    def _build_location_from_parts(
        self,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
        fallback: Optional[str] = None,
    ) -> Optional[str]:
        """
        Build a location string from city, state, and country parts.
        
        This is a common pattern used across multiple extractors when parsing
        JSON responses from ATS APIs.
        
        Args:
            city: City name
            state: State/region name
            country: Country name
            fallback: Fallback location string if no parts are provided
            
        Returns:
            Formatted location string like "City, State, Country" or fallback
        """
        parts = []
        if city:
            parts.append(city)
        if state:
            parts.append(state)
        if country:
            parts.append(country)
        
        return ", ".join(parts) if parts else fallback

    # -------------------------------------------------------------------------
    # JSON-LD Parsing Helpers
    # -------------------------------------------------------------------------

    def _extract_json_ld(self, soup: BeautifulSoup, base_url: str) -> list[ExtractedJob]:
        """
        Extract jobs from JSON-LD structured data in the page.
        
        Looks for <script type="application/ld+json"> tags and parses
        JobPosting schema.org data.
        
        Args:
            soup: BeautifulSoup parsed HTML
            base_url: Base URL for resolving relative links
            
        Returns:
            List of extracted jobs from JSON-LD data
        """
        jobs: list[ExtractedJob] = []
        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
                self._parse_json_ld_recursive(data, base_url, jobs)
            except json.JSONDecodeError:
                continue

        return jobs

    def _parse_json_ld_recursive(
        self,
        data: Any,
        base_url: str,
        jobs: list[ExtractedJob],
    ) -> None:
        """
        Recursively parse JSON-LD data looking for JobPosting objects.
        
        Handles nested structures like @graph, itemListElement, mainEntity.
        
        Args:
            data: JSON-LD data (dict or list)
            base_url: Base URL for resolving relative links
            jobs: List to append extracted jobs to
        """
        if isinstance(data, list):
            for item in data:
                self._parse_json_ld_recursive(item, base_url, jobs)
        elif isinstance(data, dict):
            # Check if this is a JobPosting
            if data.get("@type") == "JobPosting":
                job = self._job_from_json_ld(data, base_url)
                if job:
                    jobs.append(job)
            # Check for nested items
            for key in ["@graph", "itemListElement", "mainEntity"]:
                if key in data:
                    self._parse_json_ld_recursive(data[key], base_url, jobs)

    def _job_from_json_ld(self, data: dict, base_url: str) -> Optional[ExtractedJob]:
        """
        Create an ExtractedJob from JSON-LD JobPosting data.
        
        Parses standard schema.org JobPosting fields including:
        - title/name
        - description
        - jobLocation (with address parsing)
        - baseSalary
        - datePosted
        - employmentType
        
        Args:
            data: JSON-LD JobPosting dictionary
            base_url: Base URL for the job
            
        Returns:
            ExtractedJob or None if title is missing
        """
        title = data.get("title") or data.get("name")
        if not title:
            return None

        # Parse location from jobLocation
        location = self._parse_json_ld_location(data.get("jobLocation"))

        # Parse salary from baseSalary
        salary = self._parse_json_ld_salary(data.get("baseSalary"))

        return ExtractedJob(
            title=title,
            source_url=data.get("url") or base_url,
            description=data.get("description"),
            location=location,
            posted_at=data.get("datePosted"),
            employment_type=data.get("employmentType"),
            salary=salary,
        )

    def _parse_json_ld_location(self, job_location: Any) -> Optional[str]:
        """
        Parse location from JSON-LD jobLocation field.
        
        Handles various formats:
        - String location
        - Object with address.addressLocality/addressRegion/addressCountry
        - List of locations (returns first)
        
        Args:
            job_location: JSON-LD jobLocation value
            
        Returns:
            Formatted location string or None
        """
        if not job_location:
            return None

        if isinstance(job_location, str):
            return job_location

        if isinstance(job_location, list):
            # Take first location if multiple
            if job_location:
                return self._parse_json_ld_location(job_location[0])
            return None

        if isinstance(job_location, dict):
            address = job_location.get("address", {})
            if isinstance(address, str):
                return address
            if isinstance(address, dict):
                return self._build_location_from_parts(
                    city=address.get("addressLocality"),
                    state=address.get("addressRegion"),
                    country=address.get("addressCountry"),
                )
            # Fallback to name if no address
            return job_location.get("name")

        return None

    def _parse_json_ld_salary(self, base_salary: Any) -> Optional[str]:
        """
        Parse salary from JSON-LD baseSalary field.
        
        Handles MonetaryAmount schema with value containing min/max.
        
        Args:
            base_salary: JSON-LD baseSalary value
            
        Returns:
            Formatted salary string or None
        """
        if not base_salary or not isinstance(base_salary, dict):
            return None

        value = base_salary.get("value", {})
        if isinstance(value, dict):
            min_val = value.get("minValue")
            max_val = value.get("maxValue")
            currency = base_salary.get("currency", "USD")
            
            if min_val and max_val:
                return f"{currency} {min_val:,} - {max_val:,}"
            elif min_val:
                return f"{currency} {min_val:,}+"
            elif max_val:
                return f"Up to {currency} {max_val:,}"

        return None
