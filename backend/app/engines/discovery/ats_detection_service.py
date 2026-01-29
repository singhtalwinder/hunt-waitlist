"""Service for detecting ATS type for companies missing ATS information."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.discovery.ats_detector import (
    detect_ats_from_html,
    detect_ats_from_url,
    extract_identifier_from_html,
    get_careers_url,
)

logger = structlog.get_logger()


async def _check_if_cancelled(db: AsyncSession, run_id: UUID) -> bool:
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


async def _log_to_run(
    db: AsyncSession,
    run_id: UUID,
    level: str,
    msg: str,
    data: dict = None,
    current_step: str = None,
    progress_count: int = None,
    progress_total: int = None,
) -> None:
    """Add a log entry to the pipeline run with immediate commit for real-time visibility."""
    import json
    
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
    if progress_total is not None:
        # Store total in a way that's visible - we'll show it in current_step
        pass  # Don't overwrite failed with total
    
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


async def detect_ats_for_companies(
    db: AsyncSession,
    limit: int = 100,
    include_retries: bool = False,
    max_attempts: int = 3,
    run_id: Optional[UUID] = None,
) -> dict:
    """
    Detect ATS type for companies that are missing it.
    
    Args:
        db: Database session
        limit: Maximum number of companies to process
        include_retries: If True, also retry companies that failed before (up to max_attempts)
        max_attempts: Maximum number of detection attempts per company
        run_id: Optional pipeline run ID for logging
    
    Returns:
        Dict with detection results
    """
    # Build query based on whether we include retries
    if include_retries:
        # Include companies that have been tried but haven't exceeded max attempts
        query = text('''
            SELECT id, name, domain, careers_url, website_url, ats_detection_attempts
            FROM companies
            WHERE is_active = true
            AND ats_type IS NULL
            AND (ats_detection_attempts IS NULL OR ats_detection_attempts < :max_attempts)
            ORDER BY 
                COALESCE(ats_detection_attempts, 0) ASC,
                created_at DESC
            LIMIT :limit
        ''')
        result = await db.execute(query, {"limit": limit, "max_attempts": max_attempts})
    else:
        # Only companies never tried
        query = text('''
            SELECT id, name, domain, careers_url, website_url, ats_detection_attempts
            FROM companies
            WHERE is_active = true
            AND ats_type IS NULL
            AND (ats_detection_attempts IS NULL OR ats_detection_attempts = 0)
            ORDER BY created_at DESC
            LIMIT :limit
        ''')
        result = await db.execute(query, {"limit": limit})
    
    companies = result.fetchall()
    total_companies = len(companies)
    
    if not companies:
        if run_id:
            await _log_to_run(
                db, run_id, "info", "No companies to process",
                current_step="Completed - no companies found"
            )
        return {
            "processed": 0,
            "detected": 0,
            "not_detected": 0,
            "errors": 0,
        }
    
    logger.info("Starting ATS detection", count=total_companies, include_retries=include_retries)
    
    if run_id:
        await _log_to_run(
            db, run_id, "info", f"Starting ATS detection for {total_companies} companies",
            current_step=f"Processing 0/{total_companies}",
            progress_count=0,
            progress_total=total_companies,
        )
    
    detected = 0
    not_detected = 0
    errors = 0
    processed = 0
    
    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
    ) as client:
        for company in companies:
            # Check for cancellation every iteration
            if run_id and await _check_if_cancelled(db, run_id):
                logger.info("ATS detection cancelled by user")
                await _log_to_run(
                    db, run_id, "warn", "Cancelled by user",
                    current_step="Cancelled",
                    progress_count=detected,
                )
                return {
                    "processed": processed,
                    "detected": detected,
                    "not_detected": not_detected,
                    "errors": errors,
                    "cancelled": True,
                }
            
            processed += 1
            company_id = company.id
            name = company.name
            domain = company.domain
            careers_url = company.careers_url
            website_url = company.website_url
            
            try:
                ats_type, ats_identifier = await _detect_ats_for_company(
                    client, domain, careers_url, website_url
                )
                
                # Update the company
                now = datetime.now(timezone.utc)
                
                if ats_type:
                    await db.execute(
                        text('''
                            UPDATE companies
                            SET ats_type = :ats_type,
                                ats_identifier = :ats_identifier,
                                careers_url = COALESCE(careers_url, :careers_url),
                                ats_detection_attempts = COALESCE(ats_detection_attempts, 0) + 1,
                                ats_detection_last_at = :now
                            WHERE id = :id
                        '''),
                        {
                            "id": company_id,
                            "ats_type": ats_type,
                            "ats_identifier": ats_identifier,
                            "careers_url": careers_url,
                            "now": now,
                        }
                    )
                    detected += 1
                    logger.info("ATS detected", company=name, ats_type=ats_type, identifier=ats_identifier)
                    
                    # Log successful detection
                    if run_id:
                        await _log_to_run(
                            db, run_id, "info", 
                            f"✓ Detected: {name} - {ats_type}" + (f" ({ats_identifier})" if ats_identifier else ""),
                            data={"company": name, "domain": domain, "ats_type": ats_type, "ats_identifier": ats_identifier},
                            current_step=f"Processing {processed}/{total_companies}",
                            progress_count=detected,
                        )
                else:
                    await db.execute(
                        text('''
                            UPDATE companies
                            SET ats_detection_attempts = COALESCE(ats_detection_attempts, 0) + 1,
                                ats_detection_last_at = :now
                            WHERE id = :id
                        '''),
                        {"id": company_id, "now": now}
                    )
                    not_detected += 1
                    logger.debug("No ATS detected", company=name)
                    
            except Exception as e:
                errors += 1
                logger.warning("ATS detection error", company=name, error=str(e))
                
                # Log error
                if run_id:
                    await _log_to_run(
                        db, run_id, "warn", f"Error: {name} - {str(e)[:100]}",
                        data={"company": name, "error": str(e)[:200]}
                    )
                
                # Still increment attempt count
                await db.execute(
                    text('''
                        UPDATE companies
                        SET ats_detection_attempts = COALESCE(ats_detection_attempts, 0) + 1,
                            ats_detection_last_at = :now
                        WHERE id = :id
                    '''),
                    {"id": company_id, "now": datetime.now(timezone.utc)}
                )
            
            # Log progress every 10 companies
            if run_id and processed % 10 == 0:
                await _log_to_run(
                    db, run_id, "info", 
                    f"Progress: {processed}/{total_companies} ({detected} detected, {not_detected} not detected)",
                    current_step=f"Processing {processed}/{total_companies}",
                    progress_count=detected,
                )
    
    await db.commit()
    
    logger.info(
        "ATS detection complete",
        processed=total_companies,
        detected=detected,
        not_detected=not_detected,
        errors=errors,
    )
    
    # Log completion
    if run_id:
        await _log_to_run(
            db, run_id, "info", 
            f"Completed: {detected} detected, {not_detected} not detected, {errors} errors",
            data={"detected": detected, "not_detected": not_detected, "errors": errors, "processed": total_companies},
            current_step="Completed",
            progress_count=detected,
        )
    
    return {
        "processed": total_companies,
        "detected": detected,
        "not_detected": not_detected,
        "errors": errors,
    }


async def _detect_ats_for_company(
    client: httpx.AsyncClient,
    domain: Optional[str],
    careers_url: Optional[str],
    website_url: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """
    Try to detect ATS type for a company.
    
    Returns:
        Tuple of (ats_type, ats_identifier) or (None, None) if not detected
    """
    # First, try existing careers_url if available
    if careers_url:
        ats_type, ats_identifier = detect_ats_from_url(careers_url)
        if ats_type:
            return ats_type, ats_identifier
        
        # Try fetching the page
        try:
            response = await client.get(careers_url)
            if response.status_code == 200:
                html = response.text
                ats_type = detect_ats_from_html(html)
                if ats_type:
                    ats_identifier = extract_identifier_from_html(html, ats_type)
                    return ats_type, ats_identifier
        except Exception:
            pass
    
    # Try to find careers URL from domain
    if domain:
        found_careers_url = await get_careers_url(client, domain)
        if found_careers_url and found_careers_url != careers_url:
            ats_type, ats_identifier = detect_ats_from_url(found_careers_url)
            if ats_type:
                return ats_type, ats_identifier
            
            # Fetch and analyze
            try:
                response = await client.get(found_careers_url)
                if response.status_code == 200:
                    html = response.text
                    ats_type = detect_ats_from_html(html)
                    if ats_type:
                        ats_identifier = extract_identifier_from_html(html, ats_type)
                        return ats_type, ats_identifier
            except Exception:
                pass
    
    # Try website_url as fallback
    if website_url and website_url != careers_url:
        try:
            # Look for /careers or /jobs paths
            for path in ["/careers", "/jobs", "/careers/", "/jobs/"]:
                try:
                    url = website_url.rstrip("/") + path
                    response = await client.get(url)
                    if response.status_code == 200:
                        # Check final URL after redirects
                        final_url = str(response.url)
                        ats_type, ats_identifier = detect_ats_from_url(final_url)
                        if ats_type:
                            return ats_type, ats_identifier
                        
                        # Check HTML
                        html = response.text
                        ats_type = detect_ats_from_html(html)
                        if ats_type:
                            ats_identifier = extract_identifier_from_html(html, ats_type)
                            return ats_type, ats_identifier
                except Exception:
                    continue
        except Exception:
            pass
    
    return None, None


async def get_ats_detection_stats(db: AsyncSession) -> dict:
    """Get statistics about ATS detection status."""
    result = await db.execute(text('''
        SELECT 
            COUNT(*) FILTER (WHERE is_active = true AND ats_type IS NULL AND (ats_detection_attempts IS NULL OR ats_detection_attempts = 0)) as never_tried,
            COUNT(*) FILTER (WHERE is_active = true AND ats_type IS NULL AND ats_detection_attempts > 0 AND ats_detection_attempts < 3) as tried_pending,
            COUNT(*) FILTER (WHERE is_active = true AND ats_type IS NULL AND ats_detection_attempts >= 3) as exhausted,
            COUNT(*) FILTER (WHERE is_active = true AND ats_type IS NOT NULL) as detected
        FROM companies
    '''))
    row = result.fetchone()
    
    return {
        "never_tried": row.never_tried or 0,
        "tried_pending": row.tried_pending or 0,
        "exhausted": row.exhausted or 0,
        "detected": row.detected or 0,
    }
