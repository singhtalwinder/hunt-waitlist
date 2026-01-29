"""Pipeline Orchestrator - coordinates all processing steps.

The pipeline orchestrates:
1. Discovery (via DiscoveryOrchestrator) - finding new companies
2. Crawling - fetching job listings from companies
3. Enrichment - adding full job descriptions
4. Embeddings - generating vectors for semantic search

CONCURRENT EXECUTION:
Operations that hit different infrastructure can run concurrently:
- Discovery hits company websites (stripe.com, etc.)
- Crawl/Enrich per ATS type (greenhouse.io, lever.co, ashby.com, etc.)
- Embeddings hits Gemini API (generativelanguage.googleapis.com)

These are tracked separately and can all run in parallel.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Set
from uuid import UUID

import structlog
from sqlalchemy import text

from app.db import async_session_factory
from app.engines.pipeline.run_logger import (
    check_if_cancelled,
    log_to_run,
    complete_pipeline_run,
)

logger = structlog.get_logger()


class PipelineStage(str, Enum):
    """Stages of the job processing pipeline."""
    IDLE = "idle"
    DISCOVERY = "discovery"
    CRAWLING = "crawling"
    ENRICHMENT = "enrichment"
    EMBEDDINGS = "embeddings"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class OperationStatus:
    """Status of a single running operation."""
    operation_type: str  # e.g., "discovery", "crawl_greenhouse", "embeddings"
    started_at: datetime
    current_step: str = ""
    progress: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "operation_type": self.operation_type,
            "started_at": self.started_at.isoformat(),
            "current_step": self.current_step,
            "progress": self.progress,
        }


class OperationRegistry:
    """
    Registry tracking running operations.
    
    Operations are keyed by type (e.g., "discovery", "crawl_greenhouse", "embeddings").
    Different operation types can run concurrently.
    Same operation type blocks (e.g., can't run two "crawl_greenhouse" at once).
    """
    _instance: Optional["OperationRegistry"] = None
    _running: Dict[str, OperationStatus] = {}
    _lock: asyncio.Lock = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._running = {}
            cls._instance._lock = asyncio.Lock()
        return cls._instance
    
    async def start_operation(self, operation_type: str) -> bool:
        """
        Try to start an operation. Returns True if started, False if already running.
        """
        async with self._lock:
            if operation_type in self._running:
                return False
            self._running[operation_type] = OperationStatus(
                operation_type=operation_type,
                started_at=datetime.utcnow(),
            )
            logger.info(f"Started operation: {operation_type}")
            return True
    
    async def end_operation(self, operation_type: str) -> None:
        """Mark an operation as complete."""
        async with self._lock:
            if operation_type in self._running:
                del self._running[operation_type]
                logger.info(f"Ended operation: {operation_type}")
    
    def is_running(self, operation_type: str) -> bool:
        """Check if a specific operation is running."""
        return operation_type in self._running
    
    def get_running_operations(self) -> Dict[str, OperationStatus]:
        """Get all running operations."""
        return dict(self._running)
    
    def update_progress(self, operation_type: str, current_step: str = None, progress: dict = None) -> None:
        """Update progress for a running operation."""
        if operation_type in self._running:
            if current_step is not None:
                self._running[operation_type].current_step = current_step
            if progress is not None:
                self._running[operation_type].progress.update(progress)
    
    @property
    def any_running(self) -> bool:
        """Check if any operation is running."""
        return len(self._running) > 0
    
    def to_dict(self) -> dict:
        """Get status of all operations."""
        return {
            "running_operations": {k: v.to_dict() for k, v in self._running.items()},
            "count": len(self._running),
        }


# Global registry instance
operation_registry = OperationRegistry()


@dataclass
class PipelineStatus:
    """Current status of the pipeline (legacy compatibility)."""
    stage: PipelineStage = PipelineStage.IDLE
    started_at: Optional[datetime] = None
    current_step: str = ""
    progress: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        # Include running operations from registry
        running_ops = operation_registry.get_running_operations()
        
        # Determine stage from running operations
        if not running_ops:
            stage = "idle"
        elif len(running_ops) == 1:
            op_type = list(running_ops.keys())[0]
            if op_type == "discovery":
                stage = "discovery"
            elif op_type.startswith("crawl"):
                stage = "crawling"
            elif op_type.startswith("enrich"):
                stage = "enrichment"
            elif op_type == "embeddings":
                stage = "embeddings"
            else:
                stage = op_type
        else:
            stage = f"concurrent ({len(running_ops)} ops)"
        
        return {
            "stage": stage,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "current_step": self.current_step,
            "progress": self.progress,
            "errors": self.errors[-10:],
            "running_operations": {k: v.to_dict() for k, v in running_ops.items()},
        }


class PipelineOrchestrator:
    """
    Orchestrates the full job discovery and processing pipeline.
    
    No longer a singleton - operations are tracked in OperationRegistry.
    Multiple orchestrators can exist, but each operation type can only run once.
    """
    
    def __init__(self):
        self._status = PipelineStatus()
        self._registry = operation_registry
    
    @property
    def status(self) -> PipelineStatus:
        return self._status
    
    @property
    def is_running(self) -> bool:
        """Legacy: returns True if ANY operation is running."""
        return self._registry.any_running
    
    def is_operation_running(self, operation_type: str) -> bool:
        """Check if a specific operation type is running."""
        return self._registry.is_running(operation_type)
    
    async def run_full_pipeline(
        self,
        skip_discovery: bool = False,
        skip_crawl: bool = False,
        skip_enrichment: bool = False,
        skip_embeddings: bool = False,
        crawl_limit: int = 100,
        enrich_limit: Optional[int] = None,
        embedding_batch_size: int = 100,
        crawl_run_id: Optional[UUID] = None,
        enrich_run_id: Optional[UUID] = None,
        embeddings_run_id: Optional[UUID] = None,
    ) -> dict:
        """Run the full pipeline: discovery -> crawl -> enrich -> embeddings.
        
        NOTE: This runs stages sequentially. For concurrent execution,
        use the individual stage methods or the admin API endpoints.
        
        Args:
            skip_discovery: Skip the discovery stage
            skip_crawl: Skip the crawl stage
            skip_enrichment: Skip the enrichment stage
            skip_embeddings: Skip the embeddings stage
            crawl_limit: Max companies to crawl
            enrich_limit: Optional max jobs to enrich per ATS (None = no limit)
            embedding_batch_size: Batch size for embeddings
            crawl_run_id: Optional pipeline_runs ID for crawl stage logging
            enrich_run_id: Optional pipeline_runs ID for enrich stage logging
            embeddings_run_id: Optional pipeline_runs ID for embeddings stage logging
        """
        # Register as "full_pipeline" - blocks other full pipelines but not individual ops
        if not await self._registry.start_operation("full_pipeline"):
            return {"error": "Full pipeline already running", "status": self._status.to_dict()}
        
        self._status = PipelineStatus(
            stage=PipelineStage.DISCOVERY,
            started_at=datetime.utcnow(),
        )
        
        results = {
            "started_at": self._status.started_at.isoformat(),
            "discovery": None,
            "crawl": None,
            "enrichment": None,
            "embeddings": None,
        }
        
        try:
            # Stage 1: Discovery
            if not skip_discovery:
                self._status.stage = PipelineStage.DISCOVERY
                self._status.current_step = "Discovering new companies from existing ones"
                self._registry.update_progress("full_pipeline", "Discovery stage")
                logger.info("Pipeline: Starting discovery stage")
                results["discovery"] = await self._run_discovery()
            
            # Stage 2: Crawl Jobs
            if not skip_crawl:
                self._status.stage = PipelineStage.CRAWLING
                self._status.current_step = "Crawling jobs from companies"
                self._registry.update_progress("full_pipeline", "Crawl stage")
                logger.info("Pipeline: Starting crawl stage")
                results["crawl"] = await self._run_crawl(limit=crawl_limit, run_id=crawl_run_id)
            
            # Stage 3: Enrich Jobs
            if not skip_enrichment:
                self._status.stage = PipelineStage.ENRICHMENT
                self._status.current_step = "Enriching jobs with descriptions"
                self._registry.update_progress("full_pipeline", "Enrichment stage")
                logger.info("Pipeline: Starting enrichment stage")
                results["enrichment"] = await self._run_enrichment(limit=enrich_limit, run_id=enrich_run_id)
            
            # Stage 4: Generate Embeddings
            if not skip_embeddings:
                self._status.stage = PipelineStage.EMBEDDINGS
                self._status.current_step = "Generating embeddings"
                self._registry.update_progress("full_pipeline", "Embeddings stage")
                logger.info("Pipeline: Starting embeddings stage")
                results["embeddings"] = await self._run_embeddings(batch_size=embedding_batch_size, run_id=embeddings_run_id)
            
            self._status.stage = PipelineStage.COMPLETE
            self._status.current_step = "Pipeline complete"
            results["completed_at"] = datetime.utcnow().isoformat()
            
        except Exception as e:
            self._status.stage = PipelineStage.ERROR
            self._status.errors.append(str(e))
            logger.error("Pipeline failed", error=str(e))
            results["error"] = str(e)
            
        finally:
            await self._registry.end_operation("full_pipeline")
        
        return results
    
    async def _run_discovery(self) -> dict:
        """Run discovery to find new companies.
        
        Delegates to DiscoveryOrchestrator - Pipeline just coordinates stages.
        """
        from app.engines.discovery import DiscoveryOrchestrator
        
        results = {
            "sources_run": 0,
            "total_discovered": 0,
            "new_companies": 0,
            "queue_processed": 0,
        }
        
        async with async_session_factory() as db:
            orchestrator = DiscoveryOrchestrator(db)
            
            # Run discovery from all sources
            stats_list = await orchestrator.run_discovery()
            
            results["sources_run"] = len(stats_list)
            for stats in stats_list:
                results["total_discovered"] += stats.total_discovered
                results["new_companies"] += stats.new_companies
            
            self._status.progress["discovery"] = {
                "sources_run": results["sources_run"],
                "total_discovered": results["total_discovered"],
                "new_companies": results["new_companies"],
            }
            
            # Process discovery queue to create companies
            queue_stats = await orchestrator.process_queue(limit=500)
            results["queue_processed"] = queue_stats.get("created", 0) + queue_stats.get("updated", 0)
            
            self._status.progress["discovery"]["queue_processed"] = results["queue_processed"]
        
        return results
    
    async def _run_crawl(self, limit: int = 100, run_id: Optional[UUID] = None, batch_size: int = 500, continuous: bool = True) -> dict:
        """Crawl jobs from companies.
        
        Runs continuously in batches until no more companies need crawling.
        
        Args:
            limit: Max companies to crawl per batch (deprecated, use batch_size)
            run_id: Optional pipeline_runs ID for logging
            batch_size: Number of companies to process per batch (default 500)
            continuous: If True, keep running batches until no more companies found
        """
        from app.engines.crawl.service import CrawlEngine
        from app.engines.crawl.rate_limiter import RateLimiter
        
        # Use batch_size if limit is the old default, otherwise respect explicit limit
        effective_batch_size = batch_size if limit == 100 else min(limit, batch_size)
        
        results = {"companies_crawled": 0, "jobs_found": 0, "failed": 0, "cancelled": False, "batches": 0}
        
        rate_limiter = RateLimiter()
        batch_number = 0
        
        while True:
            batch_number += 1
            
            async with async_session_factory() as db:
                # Check for cancellation at the start of each batch
                if run_id and await check_if_cancelled(db, run_id):
                    results["cancelled"] = True
                    await log_to_run(
                        db, run_id, "warn", "Crawl cancelled by user",
                        current_step="Cancelled"
                    )
                    break
                
                # Find companies that need crawling
                query = await db.execute(text('''
                    SELECT c.id, c.name
                    FROM companies c
                    WHERE c.is_active = true
                    AND c.ats_type IS NOT NULL
                    AND (
                        c.last_crawled_at IS NULL 
                        OR c.last_crawled_at < NOW() - INTERVAL '24 hours'
                    )
                    ORDER BY c.last_crawled_at NULLS FIRST
                    LIMIT :limit
                '''), {"limit": effective_batch_size})
                companies = query.fetchall()
                batch_count = len(companies)
                
                # If no companies found, we're done
                if not companies:
                    if batch_number == 1:
                        if run_id:
                            await log_to_run(
                                db, run_id, "info", "No companies to crawl",
                                current_step="Completed - no companies found"
                            )
                        results["batches"] = 0
                        return results
                    else:
                        logger.info(f"No more companies to crawl after {batch_number - 1} batches")
                        break
                
                self._status.progress["crawl"] = {
                    "batch": batch_number,
                    "batch_total": batch_count,
                    "completed": 0,
                    "jobs_found": results["jobs_found"],
                    "total_crawled": results["companies_crawled"],
                }
                
                if run_id:
                    await log_to_run(
                        db, run_id, "info", 
                        f"Batch {batch_number}: Found {batch_count} companies to crawl (total so far: {results['companies_crawled']})",
                        current_step=f"Batch {batch_number}: Crawling 0/{batch_count}",
                        data={"batch": batch_number, "batch_count": batch_count, "total_crawled": results["companies_crawled"]}
                    )
                
                batch_success = 0
                batch_failed = 0
                batch_jobs = 0
                
                for i, (company_id, company_name) in enumerate(companies):
                    # Check for cancellation
                    if run_id and await check_if_cancelled(db, run_id):
                        results["cancelled"] = True
                        results["companies_crawled"] += batch_success
                        results["jobs_found"] += batch_jobs
                        results["failed"] += batch_failed
                        results["batches"] = batch_number
                        await log_to_run(
                            db, run_id, "warn", "Crawl cancelled by user",
                            current_step="Cancelled"
                        )
                        return results
                    
                    try:
                        async with async_session_factory() as crawl_db:
                            engine = CrawlEngine(crawl_db, rate_limiter)
                            result = await engine.crawl_company(company_id)
                            
                            if result.get("status") == "success":
                                batch_success += 1
                                company_jobs = result.get("jobs_extracted", 0)
                                batch_jobs += company_jobs
                                
                                if run_id and company_jobs > 0:
                                    snapshot = result.get("snapshot")
                                    snapshot_id = str(snapshot.id) if snapshot else None
                                    await log_to_run(
                                        db, run_id, "info",
                                        f"Found {company_jobs} jobs from {company_name}",
                                        current_step=f"Batch {batch_number}: {i+1}/{batch_count}",
                                        progress_count=results["companies_crawled"] + batch_success,
                                        data={"company": company_name, "jobs": company_jobs, "snapshot_id": snapshot_id}
                                    )
                            else:
                                batch_failed += 1
                                error_msg = result.get("error", "Unknown error")
                                if run_id:
                                    await log_to_run(
                                        db, run_id, "warn",
                                        f"Failed {company_name}: {error_msg}",
                                        current_step=f"Batch {batch_number}: {i+1}/{batch_count}",
                                        failed_count=results["failed"] + batch_failed,
                                        data={"company": company_name, "error": error_msg}
                                    )
                    except Exception as e:
                        logger.debug(f"Crawl failed for {company_name}: {e}")
                        batch_failed += 1
                        if run_id:
                            await log_to_run(
                                db, run_id, "error",
                                f"Error crawling {company_name}: {str(e)[:80]}",
                                current_step=f"Batch {batch_number}: {i+1}/{batch_count}",
                                failed_count=results["failed"] + batch_failed,
                                data={"company": company_name, "error": str(e)[:200]}
                            )
                    
                    self._status.progress["crawl"]["completed"] = i + 1
                    self._status.progress["crawl"]["jobs_found"] = results["jobs_found"] + batch_jobs
                    
                    # Log progress every 50 companies
                    if run_id and (i + 1) % 50 == 0:
                        await log_to_run(
                            db, run_id, "info",
                            f"Batch {batch_number} progress: {i+1}/{batch_count} ({batch_jobs} jobs found)",
                            current_step=f"Batch {batch_number}: {i+1}/{batch_count}",
                            progress_count=results["companies_crawled"] + batch_success
                        )
                
                # Update totals
                results["companies_crawled"] += batch_success
                results["jobs_found"] += batch_jobs
                results["failed"] += batch_failed
                results["batches"] = batch_number
                
                logger.info(
                    f"Batch {batch_number} complete",
                    batch_success=batch_success,
                    batch_jobs=batch_jobs,
                    total_crawled=results["companies_crawled"],
                    total_jobs=results["jobs_found"],
                )
                
                if run_id:
                    await log_to_run(
                        db, run_id, "info",
                        f"Batch {batch_number} complete: {batch_success} companies, {batch_jobs} jobs. Total: {results['companies_crawled']} companies, {results['jobs_found']} jobs",
                        current_step=f"Batch {batch_number} complete",
                        progress_count=results["companies_crawled"],
                        data={"batch": batch_number, "batch_success": batch_success, "batch_jobs": batch_jobs}
                    )
                
                # If not continuous mode or we processed fewer than batch_size, we're done
                if not continuous or batch_count < effective_batch_size:
                    break
        
        if run_id and not results["cancelled"]:
            async with async_session_factory() as db:
                await log_to_run(
                    db, run_id, "info",
                    f"Crawl complete: {results['companies_crawled']} companies, {results['jobs_found']} jobs found, {results['failed']} failed in {results['batches']} batches",
                    progress_count=results["companies_crawled"],
                    failed_count=results["failed"]
                )
        
        return results
    
    async def _run_enrichment(self, limit: Optional[int] = None, run_id: Optional[UUID] = None) -> dict:
        """Enrich jobs with descriptions.
        
        Args:
            limit: Optional max jobs to enrich per ATS (None = no limit)
            run_id: Optional pipeline_runs ID for logging
        """
        from app.engines.enrich.service import JobEnrichmentService
        
        results = {"success": 0, "failed": 0, "cancelled": False}
        ats_types = ["greenhouse", "ashby", "workable"]
        
        async with async_session_factory() as db:
            if run_id:
                await log_to_run(
                    db, run_id, "info", 
                    f"Starting enrichment for {len(ats_types)} ATS types",
                    current_step="Starting enrichment",
                    data={"ats_types": ats_types, "limit_per_ats": limit or "unlimited"}
                )
            
            service = JobEnrichmentService(db)
            
            try:
                # Run enrichment for each ATS type
                for idx, ats_type in enumerate(ats_types):
                    # Check for cancellation
                    if run_id and await check_if_cancelled(db, run_id):
                        results["cancelled"] = True
                        await log_to_run(
                            db, run_id, "warn", "Enrichment cancelled by user",
                            current_step="Cancelled"
                        )
                        break
                    
                    self._status.current_step = f"Enriching {ats_type} jobs"
                    
                    if run_id:
                        limit_msg = f"up to {limit}" if limit else "all"
                        await log_to_run(
                            db, run_id, "info",
                            f"Enriching {ats_type} jobs ({limit_msg})",
                            current_step=f"Enriching {ats_type} ({idx+1}/{len(ats_types)})"
                        )
                    
                    result = await service.enrich_jobs_batch(
                        ats_type=ats_type,
                        limit=limit,
                        concurrency=10,  # Keep below pool limit (15) to leave room for parent sessions
                    )
                    
                    ats_success = result.get("success", 0)
                    ats_failed = result.get("failed", 0)
                    results["success"] += ats_success
                    results["failed"] += ats_failed
                    
                    if run_id:
                        await log_to_run(
                            db, run_id, "info",
                            f"Enriched {ats_type}: {ats_success} success, {ats_failed} failed",
                            current_step=f"Enriching {ats_type} ({idx+1}/{len(ats_types)})",
                            progress_count=results["success"],
                            failed_count=results["failed"],
                            data={"ats_type": ats_type, "success": ats_success, "failed": ats_failed}
                        )
                    
                    self._status.progress["enrichment"] = {
                        "success": results["success"],
                        "failed": results["failed"],
                    }
            finally:
                await service.close()
            
            if run_id and not results["cancelled"]:
                await log_to_run(
                    db, run_id, "info",
                    f"Enrichment complete: {results['success']} success, {results['failed']} failed",
                    progress_count=results["success"],
                    failed_count=results["failed"]
                )
        
        return results
    
    async def _run_embeddings(self, batch_size: int = 100, run_id: Optional[UUID] = None) -> dict:
        """Generate embeddings for jobs.
        
        Args:
            batch_size: Number of jobs per batch
            run_id: Optional pipeline_runs ID for logging
        """
        from app.engines.normalize.service import generate_embeddings_batch
        
        results = {"processed": 0, "batches": 0, "cancelled": False}
        
        # Run batches until all jobs have embeddings (no artificial limit)
        # Safety limit to prevent infinite loops
        max_batches = 500
        
        async with async_session_factory() as db:
            if run_id:
                await log_to_run(
                    db, run_id, "info",
                    f"Starting embeddings generation (batch size: {batch_size})",
                    current_step="Starting embeddings",
                    data={"batch_size": batch_size, "max_batches": max_batches}
                )
            
            for i in range(max_batches):
                # Check for cancellation every 5 batches
                if run_id and i % 5 == 0 and await check_if_cancelled(db, run_id):
                    results["cancelled"] = True
                    await log_to_run(
                        db, run_id, "warn", "Embeddings cancelled by user",
                        current_step="Cancelled"
                    )
                    break
                
                self._status.current_step = f"Generating embeddings batch {i + 1}"
                
                result = await generate_embeddings_batch(batch_size=batch_size)
                
                processed = result.get("processed", 0)
                remaining = result.get("remaining", 0)
                
                if processed == 0:
                    # No more jobs without embeddings
                    if run_id:
                        await log_to_run(
                            db, run_id, "info", "No more jobs to embed",
                            current_step="Completed"
                        )
                    break
                
                results["processed"] += processed
                results["batches"] += 1
                
                self._status.progress["embeddings"] = {
                    "processed": results["processed"],
                    "batches": results["batches"],
                    "remaining": remaining,
                }
                
                logger.info(
                    "Embeddings progress",
                    batch=i + 1,
                    processed=results["processed"],
                    remaining=remaining,
                )
                
                # Log every 5 batches or when there are few remaining
                if run_id and (results["batches"] % 5 == 0 or remaining < batch_size * 2):
                    await log_to_run(
                        db, run_id, "info",
                        f"Batch {results['batches']}: {results['processed']} total, {remaining} remaining",
                        current_step=f"Batch {results['batches']}: {remaining} remaining",
                        progress_count=results["processed"],
                        data={"batch": results["batches"], "remaining": remaining}
                    )
            
            if run_id and not results["cancelled"]:
                await log_to_run(
                    db, run_id, "info",
                    f"Embeddings complete: {results['processed']} processed in {results['batches']} batches",
                    progress_count=results["processed"]
                )
        
        return results
    
    async def get_stats(self) -> dict:
        """Get current pipeline statistics."""
        async with async_session_factory() as db:
            stats = {}
            
            # Company stats
            result = await db.execute(text('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN is_active THEN 1 END) as active,
                    COUNT(CASE WHEN ats_type IS NOT NULL THEN 1 END) as with_ats,
                    COUNT(CASE WHEN last_crawled_at > NOW() - INTERVAL '24 hours' THEN 1 END) as crawled_today
                FROM companies
            '''))
            row = result.fetchone()
            stats["companies"] = {
                "total": row[0],
                "active": row[1],
                "with_ats": row[2],
                "crawled_today": row[3],
            }
            
            # Job stats
            result = await db.execute(text('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN is_active THEN 1 END) as active,
                    COUNT(description) as with_description,
                    COUNT(posted_at) as with_posted_at,
                    COUNT(embedding) as with_embeddings
                FROM jobs
            '''))
            row = result.fetchone()
            stats["jobs"] = {
                "total": row[0],
                "active": row[1],
                "with_description": row[2],
                "with_posted_at": row[3],
                "with_embeddings": row[4],
            }
            
            # Discovery queue stats
            result = await db.execute(text('''
                SELECT status, COUNT(*) 
                FROM discovery_queue 
                GROUP BY status
            '''))
            queue_stats = {row[0]: row[1] for row in result.fetchall()}
            stats["discovery_queue"] = queue_stats
            
            stats["pipeline_status"] = self._status.to_dict()
            
            return stats
    
    # ========== STANDALONE STAGE METHODS ==========
    # These can run concurrently with each other
    
    async def run_discovery_standalone(self, run_id: Optional[UUID] = None) -> dict:
        """
        Run discovery as a standalone operation.
        Can run concurrently with crawl, enrich, and embeddings.
        """
        operation_type = "discovery"
        
        if not await self._registry.start_operation(operation_type):
            return {"error": f"{operation_type} already running"}
        
        try:
            logger.info("Starting standalone discovery")
            result = await self._run_discovery()
            return result
        finally:
            await self._registry.end_operation(operation_type)
    
    async def run_crawl_standalone(
        self,
        ats_type: Optional[str] = None,
        limit: int = 100,
        run_id: Optional[UUID] = None,
    ) -> dict:
        """
        Run crawl as a standalone operation.
        
        If ats_type is specified, only crawl that ATS and use operation key "crawl_{ats_type}".
        This allows concurrent crawling of different ATS types.
        """
        operation_type = f"crawl_{ats_type}" if ats_type else "crawl_all"
        
        if not await self._registry.start_operation(operation_type):
            return {"error": f"{operation_type} already running"}
        
        try:
            logger.info(f"Starting standalone crawl: {operation_type}")
            
            if ats_type:
                # Crawl specific ATS type
                result = await self._run_crawl_by_ats(ats_type, limit, run_id)
            else:
                # Crawl all (uses _run_crawl which mixes ATS types)
                result = await self._run_crawl(limit, run_id)
            
            return result
        finally:
            await self._registry.end_operation(operation_type)
    
    async def _run_crawl_by_ats(
        self,
        ats_type: str,
        limit: int = 100,
        run_id: Optional[UUID] = None,
        batch_size: int = 500,
        continuous: bool = True,
    ) -> dict:
        """Crawl jobs from companies with a specific ATS type.
        
        Runs continuously in batches until no more companies need crawling.
        
        Args:
            ats_type: The ATS type to crawl
            limit: Max companies to crawl per batch (deprecated, use batch_size)
            run_id: Optional pipeline_runs ID for logging
            batch_size: Number of companies to process per batch (default 500)
            continuous: If True, keep running batches until no more companies found
        """
        from app.engines.crawl.service import CrawlEngine
        from app.engines.crawl.rate_limiter import RateLimiter
        
        # Use batch_size if limit is the old default, otherwise respect explicit limit
        effective_batch_size = batch_size if limit == 100 else min(limit, batch_size)
        
        results = {"companies_crawled": 0, "jobs_found": 0, "failed": 0, "cancelled": False, "ats_type": ats_type, "batches": 0}
        
        rate_limiter = RateLimiter()
        batch_number = 0
        
        while True:
            batch_number += 1
            
            async with async_session_factory() as db:
                # Check for cancellation at the start of each batch
                if run_id and await check_if_cancelled(db, run_id):
                    results["cancelled"] = True
                    results["batches"] = batch_number - 1
                    break
                
                # Find companies with this ATS type that need crawling
                query = await db.execute(text('''
                    SELECT c.id, c.name
                    FROM companies c
                    WHERE c.is_active = true
                    AND c.ats_type = :ats_type
                    AND (
                        c.last_crawled_at IS NULL 
                        OR c.last_crawled_at < NOW() - INTERVAL '24 hours'
                    )
                    ORDER BY c.last_crawled_at NULLS FIRST
                    LIMIT :limit
                '''), {"ats_type": ats_type, "limit": effective_batch_size})
                companies = query.fetchall()
                batch_count = len(companies)
                
                # If no companies found, we're done
                if not companies:
                    if batch_number == 1:
                        if run_id:
                            await log_to_run(
                                db, run_id, "info", f"No {ats_type} companies to crawl",
                                current_step="Completed - no companies found"
                            )
                        results["batches"] = 0
                        return results
                    else:
                        logger.info(f"No more {ats_type} companies to crawl after {batch_number - 1} batches")
                        break
                
                self._registry.update_progress(f"crawl_{ats_type}", f"Batch {batch_number}: 0/{batch_count}", {
                    "batch": batch_number,
                    "batch_total": batch_count,
                    "completed": 0,
                    "jobs_found": results["jobs_found"],
                    "total_crawled": results["companies_crawled"],
                })
                
                if run_id:
                    await log_to_run(
                        db, run_id, "info", 
                        f"Batch {batch_number}: Found {batch_count} {ats_type} companies to crawl (total so far: {results['companies_crawled']})",
                        current_step=f"Batch {batch_number}: Crawling 0/{batch_count}",
                        data={"batch": batch_number, "batch_count": batch_count, "ats_type": ats_type, "total_crawled": results["companies_crawled"]}
                    )
                
                batch_success = 0
                batch_failed = 0
                batch_jobs = 0
                
                for i, (company_id, company_name) in enumerate(companies):
                    # Check for cancellation
                    if run_id and await check_if_cancelled(db, run_id):
                        results["cancelled"] = True
                        results["companies_crawled"] += batch_success
                        results["jobs_found"] += batch_jobs
                        results["failed"] += batch_failed
                        results["batches"] = batch_number
                        return results
                    
                    try:
                        async with async_session_factory() as crawl_db:
                            engine = CrawlEngine(crawl_db, rate_limiter)
                            result = await engine.crawl_company(company_id)
                            
                            if result.get("status") == "success":
                                batch_success += 1
                                company_jobs = result.get("jobs_extracted", 0)
                                batch_jobs += company_jobs
                            else:
                                batch_failed += 1
                    except Exception as e:
                        logger.debug(f"Crawl failed for {company_name}: {e}")
                        batch_failed += 1
                    
                    # Update progress
                    self._registry.update_progress(f"crawl_{ats_type}", f"Batch {batch_number}: {i+1}/{batch_count}", {
                        "batch": batch_number,
                        "completed": i + 1,
                        "jobs_found": results["jobs_found"] + batch_jobs,
                        "total_crawled": results["companies_crawled"] + batch_success,
                    })
                
                # Update totals
                results["companies_crawled"] += batch_success
                results["jobs_found"] += batch_jobs
                results["failed"] += batch_failed
                results["batches"] = batch_number
                
                logger.info(
                    f"Batch {batch_number} complete for {ats_type}",
                    batch_success=batch_success,
                    batch_jobs=batch_jobs,
                    total_crawled=results["companies_crawled"],
                    total_jobs=results["jobs_found"],
                )
                
                if run_id:
                    await log_to_run(
                        db, run_id, "info",
                        f"Batch {batch_number} complete: {batch_success} {ats_type} companies, {batch_jobs} jobs. Total: {results['companies_crawled']} companies",
                        current_step=f"Batch {batch_number} complete",
                        progress_count=results["companies_crawled"],
                        data={"batch": batch_number, "batch_success": batch_success, "batch_jobs": batch_jobs}
                    )
                
                # If not continuous mode or we processed fewer than batch_size, we're done
                if not continuous or batch_count < effective_batch_size:
                    break
        
        return results
    
    async def run_enrich_standalone(
        self,
        ats_type: Optional[str] = None,
        limit: Optional[int] = None,
        run_id: Optional[UUID] = None,
    ) -> dict:
        """
        Run enrichment as a standalone operation.
        
        If ats_type is specified, only enrich that ATS and use operation key "enrich_{ats_type}".
        This allows concurrent enrichment of different ATS types.
        """
        operation_type = f"enrich_{ats_type}" if ats_type else "enrich_all"
        
        if not await self._registry.start_operation(operation_type):
            return {"error": f"{operation_type} already running"}
        
        try:
            logger.info(f"Starting standalone enrichment: {operation_type}")
            
            if ats_type:
                result = await self._run_enrich_by_ats(ats_type, limit, run_id)
            else:
                result = await self._run_enrichment(limit, run_id)
            
            return result
        finally:
            await self._registry.end_operation(operation_type)
    
    async def _run_enrich_by_ats(
        self,
        ats_type: str,
        limit: Optional[int] = None,
        run_id: Optional[UUID] = None,
    ) -> dict:
        """Enrich jobs for a specific ATS type."""
        from app.engines.enrich.service import JobEnrichmentService
        
        results = {"success": 0, "failed": 0, "cancelled": False, "ats_type": ats_type}
        
        async with async_session_factory() as db:
            service = JobEnrichmentService(db)
            
            try:
                self._registry.update_progress(f"enrich_{ats_type}", f"Enriching {ats_type}", {})
                
                result = await service.enrich_jobs_batch(
                    ats_type=ats_type,
                    limit=limit,
                    concurrency=10,  # Keep below pool limit (15) to leave room for parent sessions
                )
                
                results["success"] = result.get("success", 0)
                results["failed"] = result.get("failed", 0)
                
                self._registry.update_progress(f"enrich_{ats_type}", "Complete", {
                    "success": results["success"],
                    "failed": results["failed"],
                })
            finally:
                await service.close()
        
        return results
    
    async def run_embeddings_standalone(
        self,
        batch_size: int = 100,
        run_id: Optional[UUID] = None,
    ) -> dict:
        """
        Run embeddings as a standalone operation.
        Can run concurrently with discovery, crawl, and enrich.
        """
        operation_type = "embeddings"
        
        if not await self._registry.start_operation(operation_type):
            return {"error": f"{operation_type} already running"}
        
        try:
            logger.info("Starting standalone embeddings")
            result = await self._run_embeddings(batch_size, run_id)
            return result
        finally:
            await self._registry.end_operation(operation_type)


# Convenience functions for running operations
async def run_concurrent_crawls(ats_types: list[str], limit_per_ats: int = 100) -> dict:
    """
    Run crawls for multiple ATS types concurrently.
    
    Example:
        results = await run_concurrent_crawls(["greenhouse", "lever", "ashby"], limit_per_ats=50)
    """
    orchestrator = PipelineOrchestrator()
    
    tasks = [
        orchestrator.run_crawl_standalone(ats_type=ats, limit=limit_per_ats)
        for ats in ats_types
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return {
        ats: result if not isinstance(result, Exception) else {"error": str(result)}
        for ats, result in zip(ats_types, results)
    }
