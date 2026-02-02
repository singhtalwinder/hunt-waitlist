"""Normalization Engine - normalizes and classifies job data."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

import google.generativeai as genai
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import JobRaw, Job, Company
from app.engines.normalize.role_mapper import RoleMapper
from app.engines.normalize.seniority_detector import SeniorityDetector
from app.engines.normalize.location_normalizer import LocationNormalizer
from app.engines.normalize.skill_extractor import SkillExtractor

settings = get_settings()
logger = structlog.get_logger()

# Configure Gemini API (uses dedicated GEMINI_API_KEY for embeddings)
if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)


def get_gemini_embedding(text: str) -> Optional[List[float]]:
    """Get embedding from Google Gemini API."""
    if not settings.gemini_api_key:
        logger.warning("Gemini API key not set, skipping embedding (get one from aistudio.google.com)")
        return None
    
    try:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document",
            output_dimensionality=384,
        )
        return result['embedding']
    except Exception as e:
        logger.error("Gemini embedding failed", error=str(e))
        return None


def get_gemini_embeddings_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """Get embeddings for multiple texts from Google Gemini API."""
    if not settings.gemini_api_key:
        logger.warning("Gemini API key not set, skipping embeddings (get one from aistudio.google.com)")
        return [None] * len(texts)
    
    try:
        # Gemini supports batch embedding
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=texts,
            task_type="retrieval_document",
            output_dimensionality=384,
        )
        return result['embedding']
    except Exception as e:
        logger.error("Gemini batch embedding failed", error=str(e))
        return [None] * len(texts)


# Chunking constants for long text embedding
CHUNK_SIZE = 6000  # ~1500 tokens, safe for Gemini's 2048 token limit
CHUNK_OVERLAP = 500  # Overlap to preserve context at boundaries


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks for embedding long documents.
    
    Uses character-based chunking with word boundary awareness.
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        if end < len(text):
            # Try to break at a word boundary (look back for space)
            boundary = text.rfind(' ', start + chunk_size - 200, end)
            if boundary > start:
                end = boundary
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start, accounting for overlap
        start = end - overlap
        if start <= chunks[-1] if chunks else 0:
            start = end  # Prevent infinite loop
    
    return chunks


def mean_pool_embeddings(embeddings: List[List[float]]) -> List[float]:
    """Average multiple embeddings into one (mean pooling)."""
    if not embeddings:
        return []
    if len(embeddings) == 1:
        return embeddings[0]
    
    dim = len(embeddings[0])
    pooled = [0.0] * dim
    
    for emb in embeddings:
        for i, val in enumerate(emb):
            pooled[i] += val
    
    n = len(embeddings)
    return [v / n for v in pooled]


def get_long_text_embedding(text: str) -> Optional[List[float]]:
    """Get embedding for long text using chunking + mean pooling.
    
    Splits long text into overlapping chunks, embeds each chunk,
    then averages the embeddings to capture the full document semantics.
    """
    if not settings.gemini_api_key:
        return None
    
    chunks = chunk_text(text)
    
    if len(chunks) == 1:
        # Short text, use single embedding
        return get_gemini_embedding(chunks[0])
    
    # Embed all chunks
    chunk_embeddings = get_gemini_embeddings_batch(chunks)
    
    # Filter out any failed embeddings
    valid_embeddings = [e for e in chunk_embeddings if e is not None]
    
    if not valid_embeddings:
        return None
    
    # Mean pool to combine
    return mean_pool_embeddings(valid_embeddings)


class NormalizationEngine:
    """Engine for normalizing raw job data into canonical form."""

    def __init__(self, db: AsyncSession, skip_embeddings: bool = True):
        self.db = db
        self.role_mapper = RoleMapper()
        self.seniority_detector = SeniorityDetector()
        self.location_normalizer = LocationNormalizer()
        self.skill_extractor = SkillExtractor()
        self.skip_embeddings = skip_embeddings

    async def normalize_job(self, raw_job_id: UUID) -> Optional[Job]:
        """Normalize a raw job into canonical form."""
        # Get raw job with company
        result = await self.db.execute(
            select(JobRaw, Company)
            .join(Company, JobRaw.company_id == Company.id)
            .where(JobRaw.id == raw_job_id)
        )
        row = result.first()

        if not row:
            logger.warning("Raw job not found", raw_job_id=str(raw_job_id))
            return None

        raw_job, company = row

        logger.info(
            "Normalizing job",
            title=raw_job.title_raw,
            company=company.name,
        )

        # Extract role information
        role_family, role_specialization = self.role_mapper.map_title(raw_job.title_raw or "")

        # Detect seniority
        seniority = self.seniority_detector.detect(
            title=raw_job.title_raw or "",
            description=raw_job.description_raw or "",
        )

        # Normalize location
        location_type, locations = self.location_normalizer.normalize(
            raw_job.location_raw or ""
        )

        # Extract skills
        skills = self.skill_extractor.extract(
            title=raw_job.title_raw or "",
            description=raw_job.description_raw or "",
        )

        # Parse salary if present
        min_salary, max_salary = self._parse_salary(raw_job.salary_raw)

        # Parse employment type
        employment_type = self._normalize_employment_type(raw_job.employment_type_raw)

        # Parse posted date
        posted_at = self._parse_date(raw_job.posted_at_raw)

        # Calculate freshness score
        freshness_score = self._calculate_freshness(posted_at)

        # Generate embedding using Gemini API (skip if configured for async generation)
        embedding = None
        if not self.skip_embeddings:
            embedding_text = f"{raw_job.title_raw or ''} {role_family} {' '.join(skills or [])}"
            embedding = get_gemini_embedding(embedding_text)

        # Check if canonical job exists
        existing = await self.db.execute(
            select(Job).where(
                Job.company_id == raw_job.company_id,
                Job.source_url == raw_job.source_url,
            )
        )
        job = existing.scalar_one_or_none()

        if job:
            # Update existing
            job.raw_job_id = raw_job.id
            job.title = raw_job.title_raw or ""
            job.description = raw_job.description_raw
            job.role_family = role_family
            job.role_specialization = role_specialization
            job.seniority = seniority
            job.location_type = location_type
            job.locations = locations
            job.skills = skills
            job.min_salary = min_salary
            job.max_salary = max_salary
            job.employment_type = employment_type
            job.posted_at = posted_at
            job.freshness_score = freshness_score
            job.embedding = embedding
            job.updated_at = datetime.utcnow()
        else:
            # Create new
            job = Job(
                company_id=raw_job.company_id,
                raw_job_id=raw_job.id,
                title=raw_job.title_raw or "",
                description=raw_job.description_raw,
                source_url=raw_job.source_url,
                role_family=role_family,
                role_specialization=role_specialization,
                seniority=seniority,
                location_type=location_type,
                locations=locations,
                skills=skills,
                min_salary=min_salary,
                max_salary=max_salary,
                employment_type=employment_type,
                posted_at=posted_at,
                freshness_score=freshness_score,
                embedding=embedding,
            )
            self.db.add(job)

        await self.db.flush()

        logger.info(
            "Job normalized",
            job_id=str(job.id),
            role_family=role_family,
            seniority=seniority,
            location_type=location_type,
            skills_count=len(skills) if skills else 0,
        )

        return job

    async def normalize_company_jobs(self, company_id: UUID) -> list[Job]:
        """Normalize all raw jobs for a company."""
        result = await self.db.execute(
            select(JobRaw).where(JobRaw.company_id == company_id)
        )
        raw_jobs = result.scalars().all()

        normalized = []
        for raw_job in raw_jobs:
            job = await self.normalize_job(raw_job.id)
            if job:
                normalized.append(job)

        await self.db.commit()

        logger.info(
            "Company jobs normalized",
            company_id=str(company_id),
            total=len(raw_jobs),
            normalized=len(normalized),
        )

        return normalized

    def _parse_salary(self, salary_raw: Optional[str]) -> tuple[Optional[int], Optional[int]]:
        """Parse raw salary string into min/max values."""
        if not salary_raw:
            return None, None

        import re

        # Remove currency symbols and normalize
        salary = salary_raw.replace(",", "").replace("$", "").replace("£", "").replace("€", "")

        # Handle "k" notation
        salary = re.sub(r"(\d+)k", lambda m: str(int(m.group(1)) * 1000), salary, flags=re.IGNORECASE)

        # Extract numbers
        numbers = re.findall(r"\d+", salary)
        if not numbers:
            return None, None

        numbers = [int(n) for n in numbers]

        if len(numbers) == 1:
            return numbers[0], numbers[0]
        elif len(numbers) >= 2:
            return min(numbers[:2]), max(numbers[:2])

        return None, None

    def _normalize_employment_type(self, raw: Optional[str]) -> Optional[str]:
        """Normalize employment type."""
        if not raw:
            return None

        raw_lower = raw.lower()

        if any(term in raw_lower for term in ["full-time", "full time", "permanent"]):
            return "full_time"
        elif any(term in raw_lower for term in ["part-time", "part time"]):
            return "part_time"
        elif any(term in raw_lower for term in ["contract", "contractor"]):
            return "contract"
        elif any(term in raw_lower for term in ["freelance"]):
            return "freelance"
        elif any(term in raw_lower for term in ["intern", "internship"]):
            return "internship"

        return None

    def _parse_date(self, date_raw: Optional[str]) -> Optional[datetime]:
        """Parse raw date string."""
        if not date_raw:
            return None

        from dateutil import parser

        try:
            return parser.parse(date_raw)
        except Exception:
            return None

    def _calculate_freshness(self, posted_at: Optional[datetime]) -> float:
        """Calculate freshness score (0-1) based on posted date."""
        if not posted_at:
            return 0.5  # Default for unknown dates

        # Make datetime timezone-naive for comparison
        now = datetime.utcnow()
        post_date = posted_at
        
        # Handle timezone-aware datetimes
        if posted_at.tzinfo is not None:
            post_date = posted_at.replace(tzinfo=None)
        
        days_old = (now - post_date).days
        if days_old < 0:
            days_old = 0
            
        half_life = settings.freshness_half_life_days

        # Exponential decay
        return 0.5 ** (days_old / half_life)


    async def normalize_and_save(
        self,
        raw_job,  # ExtractedJob from extractor
        company_id: UUID,
        snapshot_id: UUID,
    ) -> Optional[Job]:
        """Save a raw extracted job and normalize it."""
        # Check if this job already exists (by company + source_url)
        existing = await self.db.execute(
            select(JobRaw).where(
                JobRaw.company_id == company_id,
                JobRaw.source_url == raw_job.source_url,
            )
        )
        existing_raw = existing.scalar_one_or_none()
        
        if existing_raw:
            # Job already exists - just update and renormalize
            existing_raw.title_raw = raw_job.title
            existing_raw.description_raw = raw_job.description
            existing_raw.location_raw = raw_job.location
            existing_raw.department_raw = raw_job.department
            existing_raw.employment_type_raw = raw_job.employment_type
            existing_raw.salary_raw = raw_job.salary
            existing_raw.posted_at_raw = raw_job.posted_at
            await self.db.flush()
            return await self.normalize_job(existing_raw.id)
        
        # Create new JobRaw record
        job_raw = JobRaw(
            company_id=company_id,
            source_url=raw_job.source_url,
            title_raw=raw_job.title,
            description_raw=raw_job.description,
            location_raw=raw_job.location,
            department_raw=raw_job.department,
            employment_type_raw=raw_job.employment_type,
            salary_raw=raw_job.salary,
            posted_at_raw=raw_job.posted_at,
        )
        self.db.add(job_raw)
        await self.db.flush()
        
        # Now normalize it
        return await self.normalize_job(job_raw.id)


async def normalize_jobs_for_company(company_id: str):
    """Normalize jobs for a company (for background task)."""
    from app.db import async_session_factory

    async with async_session_factory() as db:
        engine = NormalizationEngine(db)
        await engine.normalize_company_jobs(UUID(company_id))


def build_embedding_text(job: Job) -> str:
    """Build rich embedding text from job data.
    
    Includes FULL job description for deep semantic understanding.
    No truncation - long texts are handled via chunking + mean pooling.
    
    Structure prioritizes most important info first:
    1. Title and seniority (what the role is)
    2. Description (responsibilities, requirements, context) - FULL
    3. Skills and role family (supporting metadata)
    """
    parts = []
    
    # Title with seniority context
    title_part = job.title or ""
    if job.seniority:
        title_part = f"{job.seniority.title()} {title_part}"
    parts.append(title_part)
    
    # Full description - the core semantic content (no truncation)
    if job.description:
        parts.append(job.description)
    
    # Skills as comma-separated list
    if job.skills:
        parts.append(f"Skills: {', '.join(job.skills)}")
    
    # Role context
    if job.role_family:
        parts.append(f"Role: {job.role_family}")
    if job.role_specialization:
        parts.append(f"Specialization: {job.role_specialization}")
    
    # Location context (can matter for role matching)
    if job.location_type:
        parts.append(f"Work type: {job.location_type}")
    
    return " ".join(parts)


async def generate_embeddings_batch(batch_size: int = 100, require_description: bool = True) -> dict:
    """Generate embeddings for jobs that don't have them using Gemini API.
    
    Uses chunking + mean pooling to embed full job descriptions without truncation.
    Long descriptions are split into overlapping chunks, each chunk is embedded,
    then the embeddings are averaged to capture the complete semantic content.
    
    Args:
        batch_size: Number of jobs to process per batch
        require_description: If True, only process jobs that have descriptions.
                           This ensures embeddings capture the full semantic content.
    """
    from app.db import async_session_factory
    
    if not settings.gemini_api_key:
        logger.warning("Gemini API key not set, skipping embedding generation (get one from aistudio.google.com)")
        return {"processed": 0, "remaining": 0, "error": "Gemini API key not set - get one from aistudio.google.com"}
    
    async with async_session_factory() as db:
        # Find jobs without embeddings
        query = (
            select(Job)
            .where(Job.embedding.is_(None))
            .where(Job.is_active == True)
        )
        
        # Only embed jobs with descriptions for quality embeddings
        if require_description:
            query = query.where(Job.description.isnot(None))
            query = query.where(Job.description != "")
        
        query = query.limit(batch_size)
        result = await db.execute(query)
        jobs = result.scalars().all()
        
        if not jobs:
            return {"processed": 0, "remaining": 0}
        
        # Generate embeddings for each job (handles long text via chunking)
        processed = 0
        chunked_jobs = 0
        
        for job in jobs:
            text = build_embedding_text(job)
            
            # Use long text embedding (handles chunking + mean pooling automatically)
            embedding = get_long_text_embedding(text)
            
            if embedding:
                job.embedding = embedding
                processed += 1
                
                # Track how many needed chunking
                if len(text) > CHUNK_SIZE:
                    chunked_jobs += 1
        
        await db.commit()
        
        # Count remaining
        from sqlalchemy import func
        remaining_query = (
            select(func.count(Job.id))
            .where(Job.embedding.is_(None))
            .where(Job.is_active == True)
        )
        if require_description:
            remaining_query = remaining_query.where(Job.description.isnot(None))
            remaining_query = remaining_query.where(Job.description != "")
        
        remaining_result = await db.execute(remaining_query)
        remaining = remaining_result.scalar() or 0
        
        logger.info(
            "Embeddings generated via Gemini (full descriptions)",
            processed=processed,
            chunked=chunked_jobs,
            remaining=remaining,
            with_descriptions=require_description,
        )
        
        return {"processed": processed, "chunked": chunked_jobs, "remaining": remaining}
