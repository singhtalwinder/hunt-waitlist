"""Pipeline run logging utilities.

Shared helpers for logging progress to pipeline_runs table.
"""

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


async def check_if_cancelled(db: AsyncSession, run_id: UUID) -> bool:
    """Check if the pipeline run has been cancelled."""
    try:
        result = await db.execute(
            text("SELECT status FROM pipeline_runs WHERE id = :run_id"),
            {"run_id": run_id}
        )
        row = result.fetchone()
        return row and row[0] == "cancelled"
    except Exception:
        return False


async def log_to_run(
    db: AsyncSession,
    run_id: UUID,
    level: str,
    msg: str,
    data: dict = None,
    current_step: str = None,
    progress_count: int = None,
    failed_count: int = None,
) -> None:
    """Add a log entry to the pipeline run with immediate commit for real-time visibility.
    
    Args:
        db: Database session
        run_id: The pipeline run ID
        level: Log level ('info', 'warn', 'error')
        msg: Log message
        data: Optional additional data
        current_step: Optional update to current step description
        progress_count: Optional update to processed count
        failed_count: Optional update to failed count
    """
    run_id_short = str(run_id)[:8]
    
    log_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        "run_id": run_id_short,
    }
    if data:
        log_entry["data"] = data
    
    # Convert to proper JSON string - escape single quotes for SQL
    log_entry_json = json.dumps([log_entry]).replace("'", "''")
    
    # Build the update parts - use direct SQL for JSONB append
    set_parts = [f"logs = COALESCE(logs, '[]'::jsonb) || '{log_entry_json}'::jsonb"]
    params = {"run_id": run_id}
    
    if current_step is not None:
        set_parts.append("current_step = :current_step")
        params["current_step"] = current_step
    if progress_count is not None:
        set_parts.append("processed = :progress_count")
        params["progress_count"] = progress_count
    if failed_count is not None:
        set_parts.append("failed = :failed_count")
        params["failed_count"] = failed_count
    
    query = f"UPDATE pipeline_runs SET {', '.join(set_parts)} WHERE id = :run_id"
    
    try:
        await db.execute(text(query), params)
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to log to run: {e}")
        try:
            await db.rollback()
        except Exception:
            pass


async def create_pipeline_run(
    db: AsyncSession,
    stage: str,
    current_step: str = None,
    cascade: bool = False,
) -> Optional[UUID]:
    """Create a new pipeline run entry.
    
    Args:
        db: Database session
        stage: The stage name (crawl, enrich, embeddings)
        current_step: Initial step description
        cascade: Whether this run cascades to subsequent stages
    
    Returns:
        The run ID or None if creation failed
    """
    try:
        result = await db.execute(text('''
            INSERT INTO pipeline_runs (stage, status, started_at, current_step, cascade)
            VALUES (:stage, 'running', NOW(), :current_step, :cascade)
            RETURNING id
        '''), {
            "stage": stage,
            "current_step": current_step or f"Starting {stage}",
            "cascade": cascade,
        })
        run_id = result.scalar()
        await db.commit()
        return run_id
    except Exception as e:
        logger.warning(f"Failed to create pipeline run: {e}")
        try:
            await db.rollback()
        except Exception:
            pass
        return None


async def complete_pipeline_run(
    db: AsyncSession,
    run_id: UUID,
    processed: int = 0,
    failed: int = 0,
    status: str = "completed",
    error: str = None,
) -> None:
    """Mark a pipeline run as completed or failed.
    
    Args:
        db: Database session
        run_id: The pipeline run ID
        processed: Number of successfully processed items
        failed: Number of failed items
        status: Final status ('completed' or 'failed')
        error: Error message if failed
    """
    try:
        await db.execute(text('''
            UPDATE pipeline_runs
            SET status = :status,
                completed_at = NOW(),
                processed = :processed,
                failed = :failed,
                error = :error,
                current_step = NULL
            WHERE id = :run_id AND status = 'running'
        '''), {
            "run_id": run_id,
            "status": status,
            "processed": processed,
            "failed": failed,
            "error": error,
        })
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to complete pipeline run: {e}")
        try:
            await db.rollback()
        except Exception:
            pass
