"""Feedback Engine - generates explanations for matches."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Match, Job, CandidateProfile, Company

logger = structlog.get_logger()


class MatchExplanation:
    """Explanation for why a job was matched."""

    def __init__(
        self,
        headline: str,
        factors: list[str],
        score_description: str,
    ):
        self.headline = headline
        self.factors = factors
        self.score_description = score_description


class NoMatchExplanation:
    """Explanation for why no jobs were found."""

    def __init__(
        self,
        reason: str,
        suggestions: list[str],
    ):
        self.reason = reason
        self.suggestions = suggestions


class FeedbackEngine:
    """Engine for generating match explanations and feedback."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def explain_match(self, match_id: UUID) -> Optional[MatchExplanation]:
        """Generate explanation for a specific match."""
        # Get match with job and company
        result = await self.db.execute(
            select(Match, Job, Company)
            .join(Job, Match.job_id == Job.id)
            .join(Company, Job.company_id == Company.id)
            .where(Match.id == match_id)
        )
        row = result.first()

        if not row:
            return None

        match, job, company = row
        reasons = match.match_reasons or {}

        # Build headline
        headline = self._build_headline(job, company)

        # Build factors list
        factors = self._build_factors(job, reasons)

        # Score description
        score_description = self._describe_score(match.score)

        return MatchExplanation(
            headline=headline,
            factors=factors,
            score_description=score_description,
        )

    async def explain_no_matches(
        self,
        candidate_id: UUID,
    ) -> NoMatchExplanation:
        """Generate explanation for why a candidate has no matches."""
        # Get candidate profile
        result = await self.db.execute(
            select(CandidateProfile).where(CandidateProfile.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()

        if not candidate:
            return NoMatchExplanation(
                reason="Profile not found",
                suggestions=["Please complete your profile to receive job matches."],
            )

        # Analyze why no matches
        suggestions = []
        reasons = []

        # Check if profile is complete
        if not candidate.role_families:
            reasons.append("no role preferences set")
            suggestions.append("Add your preferred role types to your profile")

        if not candidate.location_types:
            reasons.append("no work type preferences set")
            suggestions.append("Specify if you're open to remote, hybrid, or on-site roles")

        # Check job availability
        week_ago = datetime.utcnow() - timedelta(days=7)

        # Count recent jobs matching role family
        if candidate.role_families:
            job_count = await self.db.scalar(
                select(func.count(Job.id)).where(
                    Job.is_active == True,
                    Job.role_family.in_(candidate.role_families),
                    Job.created_at >= week_ago,
                )
            )

            if job_count == 0:
                reasons.append(f"no new {candidate.role_families[0].replace('_', ' ')} roles this week")
                suggestions.append("Check back soon - new roles are added daily")
                suggestions.append("Consider expanding to related role families")

        # Check seniority availability
        if candidate.seniority:
            seniority_count = await self.db.scalar(
                select(func.count(Job.id)).where(
                    Job.is_active == True,
                    Job.seniority == candidate.seniority,
                    Job.created_at >= week_ago,
                )
            )

            if seniority_count < 5:
                reasons.append(f"few {candidate.seniority} level roles available")
                suggestions.append("Consider roles one level above or below")

        # Check location constraints
        if candidate.location_types and "remote" not in candidate.location_types:
            suggestions.append("Enabling remote positions expands your options significantly")

        # Build main reason
        if reasons:
            main_reason = "No matching jobs found because: " + ", ".join(reasons)
        else:
            main_reason = "No jobs matched your specific criteria this week"

        # Add generic suggestions if needed
        if len(suggestions) < 2:
            suggestions.append("New roles are added multiple times per day")
            suggestions.append("We'll email you when matching roles appear")

        return NoMatchExplanation(
            reason=main_reason,
            suggestions=suggestions[:4],  # Max 4 suggestions
        )

    def _build_headline(self, job: Job, company: Company) -> str:
        """Build a headline for the job match."""
        parts = []

        # Seniority
        if job.seniority:
            seniority_display = {
                "intern": "Intern",
                "junior": "Junior",
                "mid": "Mid-level",
                "senior": "Senior",
                "staff": "Staff",
                "principal": "Principal",
                "director": "Director",
                "vp": "VP",
                "c_level": "Executive",
            }
            parts.append(seniority_display.get(job.seniority, job.seniority.title()))

        # Role specialization or family
        if job.role_specialization:
            parts.append(job.role_specialization.title())
        elif job.role_family:
            family_display = job.role_family.replace("_", " ").title()
            parts.append(family_display)

        parts.append("role at")
        parts.append(company.name)

        return " ".join(parts)

    def _build_factors(self, job: Job, reasons: dict) -> list[str]:
        """Build list of match factors."""
        factors = []

        # Add reasons from match
        for key, value in reasons.items():
            if isinstance(value, str):
                factors.append(value)

        # Add location info
        if job.location_type:
            if job.location_type == "remote":
                factors.append("Fully remote position")
            elif job.location_type == "hybrid":
                loc = job.locations[0] if job.locations else "flexible location"
                factors.append(f"Hybrid role ({loc})")
            elif job.locations:
                factors.append(f"Based in {job.locations[0]}")

        # Add freshness
        if job.posted_at:
            days_ago = (datetime.utcnow() - job.posted_at).days
            if days_ago == 0:
                factors.append("Posted today")
            elif days_ago == 1:
                factors.append("Posted yesterday")
            elif days_ago < 7:
                factors.append(f"Posted {days_ago} days ago")

        # Add skills count
        if job.skills:
            factors.append(f"Requires {len(job.skills)} skills you may have")

        return factors[:5]  # Max 5 factors

    def _describe_score(self, score: float) -> str:
        """Describe the match score in human terms."""
        if score >= 0.9:
            return "Excellent match"
        elif score >= 0.8:
            return "Strong match"
        elif score >= 0.7:
            return "Good match"
        elif score >= 0.6:
            return "Moderate match"
        else:
            return "Potential match"


async def generate_match_explanation(match_id: str) -> Optional[dict]:
    """Generate explanation for a match (for API)."""
    from app.db import async_session_factory

    async with async_session_factory() as db:
        engine = FeedbackEngine(db)
        explanation = await engine.explain_match(UUID(match_id))

        if explanation:
            return {
                "headline": explanation.headline,
                "factors": explanation.factors,
                "score_description": explanation.score_description,
            }

        return None
