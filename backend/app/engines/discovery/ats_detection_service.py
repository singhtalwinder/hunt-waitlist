"""Service for detecting ATS type for companies missing ATS information."""

import re
from datetime import datetime, timezone
from typing import Optional, Tuple
from urllib.parse import urlparse
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


# Patterns that indicate a URL is NOT a careers page
BAD_URL_PATTERNS = [
    r"/news/",
    r"/article/",
    r"/blog/",
    r"/press/",
    r"/press-release",
    r"slack\.com/",
    r"discord\.gg/",
    r"discord\.com/invite",
    r"community\.",
    r"forum\.",
    r"/layoffs",
    r"dub\.co/",  # Link shortener fallback
    r"bit\.ly/",
    r"t\.co/",
    r"linkedin\.com/posts",
    r"twitter\.com/",
    r"x\.com/",
]

# Compiled patterns for efficiency
BAD_URL_REGEX = re.compile("|".join(BAD_URL_PATTERNS), re.IGNORECASE)


def is_valid_careers_url(url: str) -> bool:
    """
    Check if a URL looks like a valid careers page.
    
    Returns False for:
    - News articles
    - Blog posts
    - Community/forum links
    - Link shorteners
    - Social media posts
    """
    if not url:
        return False
    
    if BAD_URL_REGEX.search(url):
        return False
    
    return True


def is_parent_company_redirect(original_domain: str, redirect_url: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a redirect went to a different company's careers page.
    
    Returns:
        (is_redirect, parent_domain) - True if it's a parent company redirect
    """
    if not original_domain or not redirect_url:
        return False, None
    
    parsed = urlparse(redirect_url)
    redirect_host = parsed.netloc.lower()
    original_domain = original_domain.lower()
    
    # Extract base domains
    original_parts = original_domain.split(".")
    redirect_parts = redirect_host.split(".")
    
    original_base = ".".join(original_parts[-2:]) if len(original_parts) >= 2 else original_domain
    redirect_base = ".".join(redirect_parts[-2:]) if len(redirect_parts) >= 2 else redirect_host
    
    # If redirected to a different domain that's NOT a known ATS platform
    ats_domains = [
        "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com",
        "myworkdayjobs.com", "bamboohr.com", "recruitee.com",
        "smartrecruiters.com", "jobvite.com", "icims.com",
        "rippling.com", "personio.de", "personio.com", "teamtailor.com",
    ]
    
    # Check if redirect is to an ATS domain (that's normal, not a parent redirect)
    for ats_domain in ats_domains:
        if redirect_host.endswith(ats_domain):
            return False, None
    
    # If base domains are different, it might be a parent company
    if original_base != redirect_base:
        return True, redirect_base
    
    return False, None


async def _get_or_create_parent_company(
    db: AsyncSession,
    parent_domain: str,
) -> Optional[UUID]:
    """
    Look up a parent company by domain, or create a stub if not found.
    
    Returns:
        UUID of the parent company, or None if creation failed
    """
    # First, try to find existing company with this domain
    result = await db.execute(
        text("SELECT id FROM companies WHERE domain = :domain LIMIT 1"),
        {"domain": parent_domain}
    )
    row = result.fetchone()
    
    if row:
        return row.id
    
    # Also try without www prefix
    if parent_domain.startswith("www."):
        alt_domain = parent_domain[4:]
    else:
        alt_domain = f"www.{parent_domain}"
    
    result = await db.execute(
        text("SELECT id FROM companies WHERE domain = :domain LIMIT 1"),
        {"domain": alt_domain}
    )
    row = result.fetchone()
    
    if row:
        return row.id
    
    # Not found - create a stub company for the parent
    # Extract company name from domain (e.g., "gm.com" -> "GM")
    name_part = parent_domain.split(".")[0]
    company_name = name_part.upper() if len(name_part) <= 3 else name_part.title()
    
    try:
        from uuid import uuid4
        new_id = uuid4()
        
        await db.execute(
            text('''
                INSERT INTO companies (id, name, domain, website_url, discovery_source, is_active)
                VALUES (:id, :name, :domain, :website_url, 'parent_company_stub', true)
                ON CONFLICT (domain) DO UPDATE SET id = companies.id
                RETURNING id
            '''),
            {
                "id": new_id,
                "name": company_name,
                "domain": parent_domain,
                "website_url": f"https://{parent_domain}",
            }
        )
        await db.commit()
        
        # Verify it was created or get existing
        result = await db.execute(
            text("SELECT id FROM companies WHERE domain = :domain LIMIT 1"),
            {"domain": parent_domain}
        )
        row = result.fetchone()
        
        if row:
            logger.info("Created parent company stub", domain=parent_domain, id=row.id)
            return row.id
        
        return new_id
    except Exception as e:
        logger.warning("Failed to create parent company stub", domain=parent_domain, error=str(e))
        try:
            await db.rollback()
        except Exception:
            pass
        return None


def extract_job_links_from_html(html: str, base_url: str) -> list[str]:
    """
    Extract potential job links from a careers page HTML.
    
    Looks for links that look like individual job postings.
    Returns at most 3 links to check.
    """
    job_links = []
    
    # Patterns that suggest a link is a job posting
    job_link_patterns = [
        r'href="([^"]+/jobs?/[^"]+)"',  # /job/ or /jobs/
        r'href="([^"]+/positions?/[^"]+)"',  # /position/ or /positions/
        r'href="([^"]+/careers?/[^"]+)"',  # /career/ or /careers/ (but with more path)
        r'href="([^"]+/openings?/[^"]+)"',
        r'href="([^"]+/opportunities?/[^"]+)"',
        r'href="([^"]+/apply/[^"]+)"',
        r'href="([^"]+\?gh_jid=\d+[^"]*)"',  # Greenhouse job ID
    ]
    
    parsed_base = urlparse(base_url)
    seen = set()
    
    for pattern in job_link_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            # Normalize URL
            if match.startswith("//"):
                url = f"{parsed_base.scheme}:{match}"
            elif match.startswith("/"):
                url = f"{parsed_base.scheme}://{parsed_base.netloc}{match}"
            elif match.startswith("http"):
                url = match
            else:
                url = f"{parsed_base.scheme}://{parsed_base.netloc}/{match}"
            
            # Skip if already seen or too short
            if url in seen or len(url) < 20:
                continue
            
            # Skip navigation links
            if url.rstrip("/") == base_url.rstrip("/"):
                continue
            
            seen.add(url)
            job_links.append(url)
            
            # Only need a few to check
            if len(job_links) >= 3:
                return job_links
    
    return job_links


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
    batch_size: int = 50,
    include_retries: bool = False,
    max_attempts: int = 3,
    run_id: Optional[UUID] = None,
    continuous: bool = True,
) -> dict:
    """
    Detect ATS type for companies that are missing it.
    
    Runs continuously in batches until no more companies are found.
    
    Args:
        db: Database session
        batch_size: Number of companies to process per batch (default 50, smaller = more reliable)
        include_retries: If True, also retry companies that failed before (up to max_attempts)
        max_attempts: Maximum number of detection attempts per company
        run_id: Optional pipeline run ID for logging
        continuous: If True, keep running batches until no more companies found
    
    Returns:
        Dict with detection results
    """
    effective_batch_size = batch_size
    
    total_detected = 0
    total_not_detected = 0
    total_errors = 0
    total_processed = 0
    batch_number = 0
    
    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
    ) as client:
        while True:
            batch_number += 1
            
            # Check for cancellation at the start of each batch
            if run_id and await _check_if_cancelled(db, run_id):
                logger.info("ATS detection cancelled by user")
                await _log_to_run(
                    db, run_id, "warn", "Cancelled by user",
                    current_step="Cancelled",
                    progress_count=total_detected,
                )
                return {
                    "processed": total_processed,
                    "detected": total_detected,
                    "not_detected": total_not_detected,
                    "errors": total_errors,
                    "batches": batch_number - 1,
                    "cancelled": True,
                }
            
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
                result = await db.execute(query, {"limit": effective_batch_size, "max_attempts": max_attempts})
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
                result = await db.execute(query, {"limit": effective_batch_size})
            
            companies = result.fetchall()
            batch_count = len(companies)
            
            # If no companies found, we're done
            if not companies:
                if batch_number == 1:
                    # First batch with no companies
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
                        "batches": 0,
                    }
                else:
                    # No more companies after previous batches
                    logger.info(f"No more companies to process after {batch_number - 1} batches")
                    break
            
            logger.info(f"Starting ATS detection batch {batch_number}", count=batch_count, include_retries=include_retries)
            
            if run_id:
                await _log_to_run(
                    db, run_id, "info", 
                    f"Batch {batch_number}: Processing {batch_count} companies (total so far: {total_processed})",
                    current_step=f"Batch {batch_number}: 0/{batch_count}",
                    progress_count=total_detected,
                )
            
            batch_detected = 0
            batch_not_detected = 0
            batch_errors = 0
            batch_processed = 0
            
            for company in companies:
                # Check for cancellation every iteration
                if run_id and await _check_if_cancelled(db, run_id):
                    logger.info("ATS detection cancelled by user")
                    await _log_to_run(
                        db, run_id, "warn", "Cancelled by user",
                        current_step="Cancelled",
                        progress_count=total_detected + batch_detected,
                    )
                    return {
                        "processed": total_processed + batch_processed,
                        "detected": total_detected + batch_detected,
                        "not_detected": total_not_detected + batch_not_detected,
                        "errors": total_errors + batch_errors,
                        "batches": batch_number,
                        "cancelled": True,
                    }
                
                batch_processed += 1
                company_id = company.id
                name = company.name
                domain = company.domain
                careers_url = company.careers_url
                website_url = company.website_url
                
                try:
                    ats_type, ats_identifier, parent_domain = await _detect_ats_for_company(
                        client, domain, careers_url, website_url
                    )
                    
                    # Update the company - commit immediately to prevent timeout
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
                        await db.commit()  # Commit immediately after each update
                        batch_detected += 1
                        logger.info("ATS detected", company=name, ats_type=ats_type, identifier=ats_identifier)
                        
                        # Log successful detection
                        if run_id:
                            await _log_to_run(
                                db, run_id, "info", 
                                f"✓ Detected: {name} - {ats_type}" + (f" ({ats_identifier})" if ats_identifier else ""),
                                data={"company": name, "domain": domain, "ats_type": ats_type, "ats_identifier": ats_identifier},
                                current_step=f"Batch {batch_number}: {batch_processed}/{batch_count}",
                                progress_count=total_detected + batch_detected,
                            )
                    elif parent_domain:
                        # Redirect to parent company - look up or create parent, then link
                        parent_company_id = await _get_or_create_parent_company(
                            db, parent_domain
                        )
                        
                        await db.execute(
                            text('''
                                UPDATE companies
                                SET ats_type = 'uses_parent_ats',
                                    ats_identifier = :parent_domain,
                                    parent_company_id = :parent_company_id,
                                    ats_detection_attempts = COALESCE(ats_detection_attempts, 0) + 1,
                                    ats_detection_last_at = :now
                                WHERE id = :id
                            '''),
                            {
                                "id": company_id, 
                                "parent_domain": parent_domain,
                                "parent_company_id": parent_company_id,
                                "now": now,
                            }
                        )
                        await db.commit()
                        batch_detected += 1  # Count as detected (we know the situation)
                        
                        parent_msg = f"→ {parent_domain}"
                        if parent_company_id:
                            parent_msg += " (linked)"
                        logger.info("Parent company redirect detected", company=name, parent_domain=parent_domain, parent_id=parent_company_id)
                        
                        if run_id:
                            await _log_to_run(
                                db, run_id, "info", 
                                f"↪ Parent redirect: {name} {parent_msg}",
                                data={"company": name, "domain": domain, "parent_domain": parent_domain, "parent_company_id": str(parent_company_id) if parent_company_id else None},
                                current_step=f"Batch {batch_number}: {batch_processed}/{batch_count}",
                                progress_count=total_detected + batch_detected,
                            )
                    else:
                        # Get current attempt count to check if we're exhausting retries
                        current_attempts = company.ats_detection_attempts or 0
                        new_attempts = current_attempts + 1
                        
                        if new_attempts >= max_attempts:
                            # Mark as custom - we've exhausted retries
                            await db.execute(
                                text('''
                                    UPDATE companies
                                    SET ats_type = 'custom',
                                        ats_detection_attempts = :new_attempts,
                                        ats_detection_last_at = :now
                                    WHERE id = :id
                                '''),
                                {"id": company_id, "new_attempts": new_attempts, "now": now}
                            )
                            await db.commit()
                            batch_detected += 1  # Count as "resolved"
                            logger.info("Marked as custom (exhausted retries)", company=name, attempts=new_attempts)
                            
                            if run_id:
                                await _log_to_run(
                                    db, run_id, "info", 
                                    f"⚙ Custom: {name} (after {new_attempts} attempts)",
                                    data={"company": name, "domain": domain, "attempts": new_attempts},
                                    current_step=f"Batch {batch_number}: {batch_processed}/{batch_count}",
                                    progress_count=total_detected + batch_detected,
                                )
                        else:
                            await db.execute(
                                text('''
                                    UPDATE companies
                                    SET ats_detection_attempts = :new_attempts,
                                        ats_detection_last_at = :now
                                    WHERE id = :id
                                '''),
                                {"id": company_id, "new_attempts": new_attempts, "now": now}
                            )
                            await db.commit()
                            batch_not_detected += 1
                            logger.debug("No ATS detected", company=name, attempts=new_attempts)
                        
                except Exception as e:
                    batch_errors += 1
                    logger.warning("ATS detection error", company=name, error=str(e))
                    
                    # Rollback any pending transaction before continuing
                    try:
                        await db.rollback()
                    except Exception:
                        pass
                    
                    # Log error
                    if run_id:
                        await _log_to_run(
                            db, run_id, "warn", f"Error: {name} - {str(e)[:100]}",
                            data={"company": name, "error": str(e)[:200]}
                        )
                    
                    # Still increment attempt count in a fresh transaction
                    try:
                        await db.execute(
                            text('''
                                UPDATE companies
                                SET ats_detection_attempts = COALESCE(ats_detection_attempts, 0) + 1,
                                    ats_detection_last_at = :now
                                WHERE id = :id
                            '''),
                            {"id": company_id, "now": datetime.now(timezone.utc)}
                        )
                        await db.commit()
                    except Exception:
                        pass  # Don't let this block other companies
                
                # Log progress every 10 companies within a batch
                if run_id and batch_processed % 10 == 0:
                    await _log_to_run(
                        db, run_id, "info", 
                        f"Batch {batch_number} progress: {batch_processed}/{batch_count} ({batch_detected} detected)",
                        current_step=f"Batch {batch_number}: {batch_processed}/{batch_count}",
                        progress_count=total_detected + batch_detected,
                    )
            
            # Update totals
            total_processed += batch_processed
            total_detected += batch_detected
            total_not_detected += batch_not_detected
            total_errors += batch_errors
            
            logger.info(
                f"Batch {batch_number} complete",
                batch_processed=batch_processed,
                batch_detected=batch_detected,
                total_processed=total_processed,
                total_detected=total_detected,
            )
            
            # Log batch completion
            if run_id:
                await _log_to_run(
                    db, run_id, "info", 
                    f"Batch {batch_number} complete: {batch_detected} detected, {batch_not_detected} not detected. Total: {total_detected} detected",
                    data={"batch": batch_number, "batch_detected": batch_detected, "total_detected": total_detected},
                    current_step=f"Batch {batch_number} complete",
                    progress_count=total_detected,
                )
            
            # If not continuous mode or we processed fewer than batch_size, we're done
            if not continuous or batch_count < effective_batch_size:
                break
    
    logger.info(
        "ATS detection complete",
        total_batches=batch_number,
        processed=total_processed,
        detected=total_detected,
        not_detected=total_not_detected,
        errors=total_errors,
    )
    
    # Log completion
    if run_id:
        await _log_to_run(
            db, run_id, "info", 
            f"Completed: {total_detected} detected, {total_not_detected} not detected, {total_errors} errors in {batch_number} batches",
            data={"detected": total_detected, "not_detected": total_not_detected, "errors": total_errors, "processed": total_processed, "batches": batch_number},
            current_step="Completed",
            progress_count=total_detected,
        )
    
    return {
        "processed": total_processed,
        "detected": total_detected,
        "not_detected": total_not_detected,
        "errors": total_errors,
        "batches": batch_number,
    }


async def _detect_ats_for_company(
    client: httpx.AsyncClient,
    domain: Optional[str],
    careers_url: Optional[str],
    website_url: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Try to detect ATS type for a company.
    
    Strategy:
    1. Validate URL (reject news articles, slack links, etc.)
    2. Try URL pattern matching
    3. Fetch page and check HTML patterns
    4. Check for parent company redirect
    5. Follow 1-2 job links to detect ATS from redirect
    
    Returns:
        Tuple of (ats_type, ats_identifier, parent_domain) 
        - parent_domain is set if this company redirects to a parent company's careers
    """
    html_content = None
    parent_domain = None
    
    # Step 1: Validate careers_url
    if careers_url and not is_valid_careers_url(careers_url):
        logger.debug("Invalid careers URL (news/blog/social)", url=careers_url)
        # Don't use this URL, but continue with domain-based detection
        careers_url = None
    
    # Step 2: Try existing careers_url if available
    if careers_url:
        # Try URL pattern matching first
        ats_type, ats_identifier = detect_ats_from_url(careers_url)
        if ats_type:
            return ats_type, ats_identifier, None
        
        # Fetch the page
        try:
            response = await client.get(careers_url)
            if response.status_code == 200:
                final_url = str(response.url)
                html_content = response.text
                
                # Check if we got redirected to an ATS
                ats_type, ats_identifier = detect_ats_from_url(final_url)
                if ats_type:
                    return ats_type, ats_identifier, None
                
                # Check for parent company redirect
                is_parent, parent = is_parent_company_redirect(domain, final_url)
                if is_parent:
                    logger.debug("Parent company redirect detected", domain=domain, parent=parent)
                    parent_domain = parent
                    # Still try to detect ATS on the parent page
                
                # Check HTML patterns
                ats_type = detect_ats_from_html(html_content)
                if ats_type:
                    ats_identifier = extract_identifier_from_html(html_content, ats_type)
                    return ats_type, ats_identifier, parent_domain
        except Exception as e:
            logger.debug("Failed to fetch careers URL", url=careers_url, error=str(e))
    
    # Step 3: Try to find careers URL from domain
    if domain and not html_content:
        found_careers_url = await get_careers_url(client, domain)
        if found_careers_url and found_careers_url != careers_url:
            ats_type, ats_identifier = detect_ats_from_url(found_careers_url)
            if ats_type:
                return ats_type, ats_identifier, None
            
            try:
                response = await client.get(found_careers_url)
                if response.status_code == 200:
                    html_content = response.text
                    final_url = str(response.url)
                    
                    # Check if redirected to ATS
                    ats_type, ats_identifier = detect_ats_from_url(final_url)
                    if ats_type:
                        return ats_type, ats_identifier, None
                    
                    # Check HTML
                    ats_type = detect_ats_from_html(html_content)
                    if ats_type:
                        ats_identifier = extract_identifier_from_html(html_content, ats_type)
                        return ats_type, ats_identifier, None
            except Exception:
                pass
    
    # Step 4: Try website_url paths as fallback
    if website_url and not html_content:
        for path in ["/careers", "/jobs"]:
            try:
                url = website_url.rstrip("/") + path
                response = await client.get(url)
                if response.status_code == 200:
                    final_url = str(response.url)
                    html_content = response.text
                    
                    ats_type, ats_identifier = detect_ats_from_url(final_url)
                    if ats_type:
                        return ats_type, ats_identifier, None
                    
                    ats_type = detect_ats_from_html(html_content)
                    if ats_type:
                        ats_identifier = extract_identifier_from_html(html_content, ats_type)
                        return ats_type, ats_identifier, None
                    
                    break  # Got content, move to job link following
            except Exception:
                continue
    
    # Step 5: Follow job links to detect ATS from redirect
    if html_content:
        base_url = careers_url or website_url or f"https://{domain}"
        job_links = extract_job_links_from_html(html_content, base_url)
        
        for job_link in job_links[:2]:  # Only check first 2
            try:
                response = await client.get(job_link, follow_redirects=True)
                final_url = str(response.url)
                
                # Many companies use ATS for individual jobs but embed on careers page
                ats_type, ats_identifier = detect_ats_from_url(final_url)
                if ats_type:
                    logger.debug("ATS detected from job link redirect", job_link=job_link, ats_type=ats_type)
                    return ats_type, ats_identifier, parent_domain
                
                # Check HTML of job page
                if response.status_code == 200:
                    ats_type = detect_ats_from_html(response.text)
                    if ats_type:
                        ats_identifier = extract_identifier_from_html(response.text, ats_type)
                        return ats_type, ats_identifier, parent_domain
            except Exception:
                continue
    
    return None, None, parent_domain


async def get_ats_detection_stats(db: AsyncSession) -> dict:
    """Get statistics about ATS detection status."""
    result = await db.execute(text('''
        SELECT 
            COUNT(*) FILTER (WHERE is_active = true AND ats_type IS NULL AND (ats_detection_attempts IS NULL OR ats_detection_attempts = 0)) as never_tried,
            COUNT(*) FILTER (WHERE is_active = true AND ats_type IS NULL AND ats_detection_attempts > 0 AND ats_detection_attempts < 3) as tried_pending,
            COUNT(*) FILTER (WHERE is_active = true AND ats_type IS NULL AND ats_detection_attempts >= 3) as exhausted,
            COUNT(*) FILTER (WHERE is_active = true AND ats_type IS NOT NULL) as detected,
            COUNT(*) FILTER (WHERE is_active = true AND ats_type = 'custom') as custom,
            COUNT(*) FILTER (WHERE is_active = true AND ats_type = 'uses_parent_ats') as uses_parent
        FROM companies
    '''))
    row = result.fetchone()
    
    return {
        "never_tried": row.never_tried or 0,
        "tried_pending": row.tried_pending or 0,
        "exhausted": row.exhausted or 0,
        "detected": row.detected or 0,
        "custom": row.custom or 0,
        "uses_parent": row.uses_parent or 0,
    }


# SQL to create the companies_dormant table
COMPANIES_DORMANT_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS companies_dormant (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255),
    website_url TEXT,
    discovery_source VARCHAR(100),
    country VARCHAR(2),
    location TEXT,
    description TEXT,
    industry VARCHAR(100),
    employee_count INTEGER,
    funding_stage VARCHAR(50),
    dormant_reason VARCHAR(100),  -- 'no_careers_url', 'domain_unreachable', etc.
    last_checked_at TIMESTAMPTZ,
    check_count INTEGER DEFAULT 0,
    moved_at TIMESTAMPTZ DEFAULT NOW(),
    original_created_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_companies_dormant_domain ON companies_dormant(domain);
CREATE INDEX IF NOT EXISTS idx_companies_dormant_reason ON companies_dormant(dormant_reason);
'''


async def ensure_dormant_table_exists(db: AsyncSession) -> None:
    """Create the companies_dormant table if it doesn't exist."""
    await db.execute(text(COMPANIES_DORMANT_TABLE_SQL))
    await db.commit()


async def move_companies_to_dormant(
    db: AsyncSession,
    reason: str = "no_careers_url",
    limit: int = 100,
) -> dict:
    """
    Move companies without careers_url (and no way to find jobs) to dormant table.
    
    These are typically:
    - University labs
    - Non-profits that don't hire
    - Companies we couldn't find careers pages for
    
    Returns:
        Dict with count of moved companies
    """
    await ensure_dormant_table_exists(db)
    
    # Find companies to move
    if reason == "no_careers_url":
        query = text('''
            SELECT id, name, domain, website_url, discovery_source, country, 
                   location, description, industry, employee_count, funding_stage, created_at
            FROM companies
            WHERE is_active = true
            AND careers_url IS NULL
            AND ats_type IS NULL
            AND (website_url IS NULL OR website_url = '')
            LIMIT :limit
        ''')
    else:
        # Generic query for other reasons
        query = text('''
            SELECT id, name, domain, website_url, discovery_source, country, 
                   location, description, industry, employee_count, funding_stage, created_at
            FROM companies
            WHERE is_active = true
            AND careers_url IS NULL
            AND ats_type IS NULL
            AND ats_detection_attempts >= 3
            LIMIT :limit
        ''')
    
    result = await db.execute(query, {"limit": limit})
    companies = result.fetchall()
    
    if not companies:
        return {"moved": 0, "reason": reason}
    
    moved = 0
    for company in companies:
        try:
            # Insert into dormant table
            await db.execute(
                text('''
                    INSERT INTO companies_dormant 
                    (id, name, domain, website_url, discovery_source, country, location, 
                     description, industry, employee_count, funding_stage, dormant_reason, 
                     original_created_at)
                    VALUES 
                    (:id, :name, :domain, :website_url, :discovery_source, :country, :location,
                     :description, :industry, :employee_count, :funding_stage, :reason,
                     :created_at)
                    ON CONFLICT (id) DO NOTHING
                '''),
                {
                    "id": company.id,
                    "name": company.name,
                    "domain": company.domain,
                    "website_url": company.website_url,
                    "discovery_source": company.discovery_source,
                    "country": company.country,
                    "location": company.location,
                    "description": company.description,
                    "industry": company.industry,
                    "employee_count": company.employee_count,
                    "funding_stage": company.funding_stage,
                    "reason": reason,
                    "created_at": company.created_at,
                }
            )
            
            # Deactivate in main table (don't delete - keeps referential integrity)
            await db.execute(
                text("UPDATE companies SET is_active = false WHERE id = :id"),
                {"id": company.id}
            )
            
            moved += 1
        except Exception as e:
            logger.warning("Failed to move company to dormant", company=company.name, error=str(e))
            await db.rollback()
            continue
    
    await db.commit()
    logger.info(f"Moved {moved} companies to dormant table", reason=reason)
    
    return {"moved": moved, "reason": reason}


async def recheck_dormant_companies(
    db: AsyncSession,
    limit: int = 50,
) -> dict:
    """
    Periodically re-check dormant companies to see if they've added careers pages.
    
    Companies that have been dormant for a while might have:
    - Added a careers page
    - Started using an ATS
    - Become reachable
    
    Returns:
        Dict with reactivated count
    """
    import httpx
    
    await ensure_dormant_table_exists(db)
    
    # Get dormant companies that haven't been checked recently
    result = await db.execute(
        text('''
            SELECT id, name, domain, website_url
            FROM companies_dormant
            WHERE domain IS NOT NULL
            AND (last_checked_at IS NULL OR last_checked_at < NOW() - INTERVAL '30 days')
            ORDER BY COALESCE(last_checked_at, moved_at) ASC
            LIMIT :limit
        '''),
        {"limit": limit}
    )
    companies = result.fetchall()
    
    if not companies:
        return {"checked": 0, "reactivated": 0}
    
    checked = 0
    reactivated = 0
    
    async with httpx.AsyncClient(
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)"}
    ) as client:
        for company in companies:
            checked += 1
            
            try:
                # Try to find careers URL
                careers_url = await get_careers_url(client, company.domain)
                
                if careers_url:
                    # Company now has a careers page! Reactivate
                    ats_type, ats_identifier = detect_ats_from_url(careers_url)
                    
                    if not ats_type:
                        # Try fetching and detecting
                        try:
                            response = await client.get(careers_url)
                            if response.status_code == 200:
                                ats_type = detect_ats_from_html(response.text)
                                if ats_type:
                                    ats_identifier = extract_identifier_from_html(response.text, ats_type)
                        except Exception:
                            pass
                    
                    # Reactivate in main companies table
                    await db.execute(
                        text('''
                            UPDATE companies 
                            SET is_active = true,
                                careers_url = :careers_url,
                                ats_type = :ats_type,
                                ats_identifier = :ats_identifier,
                                ats_detection_attempts = 0
                            WHERE id = :id
                        '''),
                        {
                            "id": company.id,
                            "careers_url": careers_url,
                            "ats_type": ats_type,
                            "ats_identifier": ats_identifier,
                        }
                    )
                    
                    # Remove from dormant
                    await db.execute(
                        text("DELETE FROM companies_dormant WHERE id = :id"),
                        {"id": company.id}
                    )
                    
                    await db.commit()
                    reactivated += 1
                    logger.info("Reactivated dormant company", company=company.name, careers_url=careers_url)
                else:
                    # Still no careers page, update check timestamp
                    await db.execute(
                        text('''
                            UPDATE companies_dormant 
                            SET last_checked_at = NOW(),
                                check_count = check_count + 1
                            WHERE id = :id
                        '''),
                        {"id": company.id}
                    )
                    await db.commit()
                    
            except Exception as e:
                logger.debug("Error checking dormant company", company=company.name, error=str(e))
                # Update check timestamp anyway
                try:
                    await db.execute(
                        text('''
                            UPDATE companies_dormant 
                            SET last_checked_at = NOW(),
                                check_count = check_count + 1
                            WHERE id = :id
                        '''),
                        {"id": company.id}
                    )
                    await db.commit()
                except Exception:
                    pass
    
    return {"checked": checked, "reactivated": reactivated}
