"""Matching Engine - matches jobs to candidates."""

from datetime import datetime
from typing import Optional
from uuid import UUID

import numpy as np
import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import Job, CandidateProfile, Match

settings = get_settings()
logger = structlog.get_logger()


class MatchResult:
    """Result of matching a job to a candidate."""

    def __init__(
        self,
        job_id: UUID,
        score: float,
        hard_match: bool,
        reasons: dict,
    ):
        self.job_id = job_id
        self.score = score
        self.hard_match = hard_match
        self.reasons = reasons


class MatchingEngine:
    """Engine for matching jobs to candidates."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.score_threshold = settings.match_score_threshold

    async def match_candidate(
        self,
        candidate_id: UUID,
        limit: int = 100,
    ) -> list[MatchResult]:
        """Find matching jobs for a candidate."""
        # Get candidate profile
        result = await self.db.execute(
            select(CandidateProfile).where(CandidateProfile.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()

        if not candidate:
            logger.warning("Candidate not found", candidate_id=str(candidate_id))
            return []

        logger.info(
            "Matching jobs for candidate",
            candidate_id=str(candidate_id),
            email=candidate.email,
        )

        # Get active jobs
        result = await self.db.execute(
            select(Job).where(Job.is_active == True).limit(1000)
        )
        jobs = result.scalars().all()

        # Score each job
        matches = []
        for job in jobs:
            match_result = self._score_job(candidate, job)
            if match_result and match_result.score >= self.score_threshold:
                matches.append(match_result)

        # Sort by score descending
        matches.sort(key=lambda m: m.score, reverse=True)

        # Limit results
        matches = matches[:limit]

        logger.info(
            "Matching complete",
            candidate_id=str(candidate_id),
            total_jobs=len(jobs),
            matches_found=len(matches),
        )

        return matches

    async def save_matches(
        self,
        candidate_id: UUID,
        match_results: list[MatchResult],
    ):
        """Save match results to database."""
        for result in match_results:
            # Check for existing match
            existing = await self.db.execute(
                select(Match).where(
                    and_(
                        Match.candidate_id == candidate_id,
                        Match.job_id == result.job_id,
                    )
                )
            )
            match = existing.scalar_one_or_none()

            if match:
                # Update existing
                match.score = result.score
                match.hard_match = result.hard_match
                match.match_reasons = result.reasons
            else:
                # Create new
                match = Match(
                    candidate_id=candidate_id,
                    job_id=result.job_id,
                    score=result.score,
                    hard_match=result.hard_match,
                    match_reasons=result.reasons,
                )
                self.db.add(match)

        await self.db.commit()

    def _score_job(
        self,
        candidate: CandidateProfile,
        job: Job,
    ) -> Optional[MatchResult]:
        """Score how well a job matches a candidate."""
        reasons = {}
        hard_match = True

        # === HARD CONSTRAINTS ===

        # 1. Role family match
        if candidate.role_families and job.role_family:
            if job.role_family not in candidate.role_families:
                return None  # Hard fail
            reasons["role_match"] = f"Matches your {job.role_family.replace('_', ' ')} preference"

        # 2. Seniority match
        if candidate.seniority and job.seniority:
            if not self._seniority_compatible(candidate.seniority, job.seniority):
                return None  # Hard fail
            reasons["seniority_match"] = f"Matches your {job.seniority} level"

        # 3. Location type match
        if candidate.location_types and job.location_type:
            if job.location_type not in candidate.location_types:
                return None  # Hard fail
            reasons["location_type_match"] = f"{job.location_type.title()} position"

        # 4. Salary match (if both specified)
        if candidate.min_salary and job.max_salary:
            if job.max_salary < candidate.min_salary * 0.8:  # 20% buffer
                return None  # Hard fail
            if job.min_salary and job.min_salary >= candidate.min_salary:
                reasons["salary_match"] = f"Meets your salary requirements"

        # 5. Exclusions check
        if candidate.exclusions:
            for exclusion in candidate.exclusions:
                if exclusion.lower() in (job.title or "").lower():
                    return None  # Hard fail
                if job.skills and exclusion.lower() in [s.lower() for s in job.skills]:
                    return None  # Hard fail

        # === SOFT SCORING ===

        scores = []
        weights = []

        # 1. Skills overlap (weight: 0.3)
        skills_score = self._calculate_skills_score(candidate.skills, job.skills)
        scores.append(skills_score)
        weights.append(0.3)
        if skills_score > 0.5 and job.skills:
            matching = len(set(candidate.skills or []) & set(job.skills))
            reasons["skills_match"] = f"Matches {matching} of your skills"

        # 2. Freshness score (weight: 0.3)
        freshness_score = job.freshness_score or 0.5
        scores.append(freshness_score)
        weights.append(0.3)
        if freshness_score > 0.7:
            reasons["freshness"] = "Posted recently"

        # 3. Semantic similarity (weight: 0.2)
        semantic_score = self._calculate_semantic_score(candidate.embedding, job.embedding)
        scores.append(semantic_score)
        weights.append(0.2)

        # 4. Location match quality (weight: 0.1)
        location_score = self._calculate_location_score(candidate.locations, job.locations)
        scores.append(location_score)
        weights.append(0.1)

        # 5. Specialization match (weight: 0.1)
        spec_score = 0.5  # Default
        if job.role_specialization:
            spec_score = 0.8  # Bonus for having specialization
        scores.append(spec_score)
        weights.append(0.1)

        # Calculate weighted average
        total_weight = sum(weights)
        final_score = sum(s * w for s, w in zip(scores, weights)) / total_weight

        # Boost for hard matches
        if hard_match:
            final_score = min(1.0, final_score * 1.1)

        return MatchResult(
            job_id=job.id,
            score=final_score,
            hard_match=hard_match,
            reasons=reasons,
        )

    def _seniority_compatible(self, candidate_seniority: str, job_seniority: str) -> bool:
        """Check if seniority levels are compatible."""
        SENIORITY_ORDER = ["intern", "junior", "mid", "senior", "staff", "principal", "director", "vp", "c_level"]

        try:
            candidate_idx = SENIORITY_ORDER.index(candidate_seniority)
            job_idx = SENIORITY_ORDER.index(job_seniority)

            # Allow one level above or below
            return abs(candidate_idx - job_idx) <= 1
        except ValueError:
            # Unknown seniority, allow
            return True

    def _calculate_skills_score(
        self,
        candidate_skills: Optional[list[str]],
        job_skills: Optional[list[str]],
    ) -> float:
        """Calculate skills overlap score using Jaccard similarity."""
        if not candidate_skills or not job_skills:
            return 0.5  # Default when skills unknown

        candidate_set = set(s.lower() for s in candidate_skills)
        job_set = set(s.lower() for s in job_skills)

        intersection = len(candidate_set & job_set)
        union = len(candidate_set | job_set)

        if union == 0:
            return 0.5

        return intersection / union

    def _calculate_semantic_score(
        self,
        candidate_embedding: Optional[list[float]],
        job_embedding: Optional[list[float]],
    ) -> float:
        """Calculate semantic similarity using cosine distance."""
        if not candidate_embedding or not job_embedding:
            return 0.5  # Default

        try:
            a = np.array(candidate_embedding)
            b = np.array(job_embedding)

            # Cosine similarity
            similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

            # Convert to 0-1 scale (cosine can be -1 to 1)
            return (similarity + 1) / 2
        except Exception:
            return 0.5

    def _calculate_location_score(
        self,
        candidate_locations: Optional[list[str]],
        job_locations: Optional[list[str]],
    ) -> float:
        """Calculate location compatibility score."""
        if not candidate_locations or not job_locations:
            return 0.5  # Default

        candidate_set = set(loc.lower() for loc in candidate_locations)
        job_set = set(loc.lower() for loc in job_locations)

        # Check for any overlap
        if candidate_set & job_set:
            return 1.0

        # Check for country-level match
        for c_loc in candidate_set:
            for j_loc in job_set:
                if c_loc in j_loc or j_loc in c_loc:
                    return 0.7

        return 0.3


async def run_matching_for_candidate(candidate_id: str):
    """Run matching for a single candidate (for background task)."""
    from app.db import async_session_factory

    async with async_session_factory() as db:
        engine = MatchingEngine(db)
        matches = await engine.match_candidate(UUID(candidate_id))
        await engine.save_matches(UUID(candidate_id), matches)

        # Update last matched timestamp
        result = await db.execute(
            select(CandidateProfile).where(CandidateProfile.id == UUID(candidate_id))
        )
        candidate = result.scalar_one_or_none()
        if candidate:
            candidate.last_matched_at = datetime.utcnow()
            await db.commit()


async def run_matching_for_all():
    """Run matching for all active candidates (for background task)."""
    from app.db import async_session_factory

    async with async_session_factory() as db:
        # Get all active candidates
        result = await db.execute(
            select(CandidateProfile).where(CandidateProfile.is_active == True)
        )
        candidates = result.scalars().all()

        engine = MatchingEngine(db)

        for candidate in candidates:
            try:
                matches = await engine.match_candidate(candidate.id)
                await engine.save_matches(candidate.id, matches)
                candidate.last_matched_at = datetime.utcnow()
            except Exception as e:
                logger.error(
                    "Matching failed for candidate",
                    candidate_id=str(candidate.id),
                    error=str(e),
                )

        await db.commit()

        logger.info(
            "Matching complete for all candidates",
            total_candidates=len(candidates),
        )
