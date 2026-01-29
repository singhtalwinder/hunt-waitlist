"""Pipeline Scheduler - handles automated background processing."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import structlog

from app.engines.pipeline.orchestrator import PipelineOrchestrator

logger = structlog.get_logger()


class PipelineScheduler:
    """Scheduler for running pipeline tasks on a schedule."""
    
    _instance: Optional["PipelineScheduler"] = None
    _running: bool = False
    _task: Optional[asyncio.Task] = None
    _last_run: Optional[datetime] = None
    _next_run: Optional[datetime] = None
    _interval_hours: int = 6
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def status(self) -> dict:
        return {
            "running": self._running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "next_run": self._next_run.isoformat() if self._next_run else None,
            "interval_hours": self._interval_hours,
        }
    
    async def start(self, interval_hours: int = 6):
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return
        
        self._running = True
        self._interval_hours = interval_hours
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Pipeline scheduler started", interval_hours=interval_hours)
    
    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Pipeline scheduler stopped")
    
    async def _run_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                # Calculate next run time
                self._next_run = datetime.utcnow() + timedelta(hours=self._interval_hours)
                
                # Wait for next scheduled run
                await asyncio.sleep(self._interval_hours * 3600)
                
                if not self._running:
                    break
                
                # Run the pipeline
                logger.info("Scheduler: Starting scheduled pipeline run")
                self._last_run = datetime.utcnow()
                
                orchestrator = PipelineOrchestrator()
                await orchestrator.run_full_pipeline(
                    skip_discovery=False,
                    skip_crawl=False,
                    skip_enrichment=False,
                    skip_embeddings=False,
                    crawl_limit=100,
                    enrich_limit=None,  # No limit - enrich all jobs without descriptions
                    embedding_batch_size=100,
                )
                
                logger.info("Scheduler: Pipeline run complete")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Scheduler error", error=str(e))
                # Wait a bit before retrying
                await asyncio.sleep(60)
    
    async def run_now(self) -> dict:
        """Trigger an immediate pipeline run."""
        orchestrator = PipelineOrchestrator()
        
        if orchestrator.is_running:
            return {"error": "Pipeline already running"}
        
        self._last_run = datetime.utcnow()
        
        result = await orchestrator.run_full_pipeline()
        return result


# Global scheduler instance
scheduler = PipelineScheduler()
