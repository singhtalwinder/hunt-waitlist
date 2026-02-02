#!/usr/bin/env python3
"""
Validate and Crawl ATS Companies Without Jobs

This script:
1. Finds all companies with ATS assigned but no jobs
2. Tests each company's crawlability (1 test each)
3. Marks failures with reasons
4. For successful ones: crawls all jobs, enriches them, generates embeddings

Usage:
    python -m scripts.validate_and_crawl_ats_companies
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from sqlalchemy import select, text, func

from app.db import async_session_factory, Company, Job
from app.engines.crawl.service import CrawlEngine
from app.engines.crawl.rate_limiter import RateLimiter
from app.engines.enrich.service import JobEnrichmentService

logger = structlog.get_logger()


# Invalid ATS identifier patterns - these indicate extraction errors
INVALID_IDENTIFIER_PATTERNS = [
    r"\$\{",            # Template variables like ${ASHBY_ORG}
    r"\$\(",            # Shell substitutions
    r"<[^>]+>",         # HTML tags
    r"class=",          # CSS class fragments  
    r"div>",            # HTML fragments
    r"\\n",             # Escaped newlines
    r"console\.",       # JavaScript code
    r"fetch\(",         # JavaScript code
    r"response\.",      # JavaScript code
    r"elementor",       # WordPress HTML
    r"data-domain=",    # BambooHR embed fragments
    r"script>",         # Script tags
    r"\\\"",            # Escaped quotes
    r"!res\.ok",        # JavaScript code
]


def is_invalid_identifier(identifier: str) -> bool:
    """Check if an ATS identifier is invalid/malformed."""
    if not identifier:
        return True
    
    # Check for known invalid patterns
    for pattern in INVALID_IDENTIFIER_PATTERNS:
        if re.search(pattern, identifier, re.IGNORECASE):
            return True
    
    # Check for excessively long identifiers (likely extraction errors)
    if len(identifier) > 100:
        return True
    
    # Check for identifiers that are just template placeholders
    if identifier.strip() in ["${ASHBY_ORG}", "null", "undefined", "The"]:
        return True
    
    return False


async def get_companies_with_ats_no_jobs(limit: int = 500) -> list[dict]:
    """Get all companies with ATS assigned but no active jobs."""
    async with async_session_factory() as db:
        result = await db.execute(text("""
            SELECT 
                c.id, c.name, c.domain, c.ats_type, c.ats_identifier, 
                c.careers_url, c.last_crawled_at
            FROM companies c
            WHERE c.is_active = true
            AND c.ats_type IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM jobs j 
                WHERE j.company_id = c.id AND j.is_active = true
            )
            ORDER BY c.ats_type, c.name
            LIMIT :limit
        """), {"limit": limit})
        
        companies = []
        for row in result.fetchall():
            companies.append({
                "id": str(row.id),
                "name": row.name,
                "domain": row.domain,
                "ats_type": row.ats_type,
                "ats_identifier": row.ats_identifier,
                "careers_url": row.careers_url,
                "last_crawled_at": row.last_crawled_at,
            })
        
        return companies


async def test_company_crawl(company_id: str, rate_limiter: RateLimiter) -> dict:
    """
    Test if a company's jobs can be crawled.
    
    Returns:
        dict with keys:
            - success: bool
            - jobs_extracted: int (if successful)
            - error: str (if failed)
            - reason: str (failure reason code)
    """
    async with async_session_factory() as db:
        engine = CrawlEngine(db, rate_limiter)
        try:
            result = await engine.crawl_company(UUID(company_id))
            
            if result.get("status") == "success":
                jobs_extracted = result.get("jobs_extracted", 0)
                return {
                    "success": True,
                    "jobs_extracted": jobs_extracted,
                    "unchanged": result.get("unchanged", False),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "reason": result.get("reason", "unknown"),
                    "status_code": result.get("status_code"),
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "reason": "exception",
            }
        finally:
            await engine.close()


async def mark_company_crawl_failed(company_id: str, reason: str, error: str):
    """Mark a company as having failed crawl (update maintenance fields)."""
    async with async_session_factory() as db:
        await db.execute(text("""
            UPDATE companies 
            SET 
                last_maintenance_at = :now,
                ats_detection_attempts = COALESCE(ats_detection_attempts, 0) + 1,
                ats_detection_last_at = :now
            WHERE id = :company_id
        """), {
            "company_id": company_id,
            "now": datetime.utcnow(),
        })
        await db.commit()


async def clear_invalid_ats_identifier(company_id: str, ats_identifier: str):
    """Clear invalid ATS identifier from company."""
    async with async_session_factory() as db:
        logger.warning(
            "Clearing invalid ATS identifier",
            company_id=company_id,
            invalid_identifier=ats_identifier[:50] + "..." if len(ats_identifier) > 50 else ats_identifier,
        )
        await db.execute(text("""
            UPDATE companies 
            SET ats_identifier = NULL
            WHERE id = :company_id
        """), {"company_id": company_id})
        await db.commit()


async def run_enrichment_for_ats_types(ats_types: list[str], batch_size: int = 500):
    """Run enrichment for specific ATS types."""
    for ats_type in ats_types:
        logger.info(f"Running enrichment for {ats_type}")
        async with async_session_factory() as db:
            service = JobEnrichmentService(db)
            try:
                result = await service.enrich_jobs_batch(
                    ats_type=ats_type,
                    batch_size=batch_size,
                    concurrency=5,
                )
                logger.info(f"Enrichment complete for {ats_type}", **result)
            finally:
                await service.close()


async def run_embeddings(batch_size: int = 100):
    """Generate embeddings for jobs without them."""
    try:
        from app.engines.normalize.service import generate_embeddings_batch
    except ImportError as e:
        logger.warning(f"Cannot import embeddings function: {e}")
        print("  Skipping embeddings (google-generativeai not installed)")
        return 0
    
    total_processed = 0
    while True:
        result = await generate_embeddings_batch(batch_size=batch_size)
        processed = result.get("processed", 0)
        remaining = result.get("remaining", 0)
        
        if processed == 0:
            break
        
        total_processed += processed
        logger.info(f"Generated embeddings: {processed}, remaining: {remaining}")
        
        if remaining == 0:
            break
    
    return total_processed


async def main():
    """Main entry point."""
    print("=" * 60)
    print("ATS Company Validation and Crawl")
    print("=" * 60)
    
    # Phase 1: Get companies with ATS but no jobs
    print("\n[Phase 1] Finding companies with ATS but no jobs...")
    companies = await get_companies_with_ats_no_jobs(limit=500)
    print(f"Found {len(companies)} companies to test")
    
    if not companies:
        print("No companies to process!")
        return
    
    # Group by ATS type for reporting
    by_ats = {}
    for c in companies:
        ats = c["ats_type"]
        if ats not in by_ats:
            by_ats[ats] = []
        by_ats[ats].append(c)
    
    print("\nCompanies by ATS type:")
    for ats, comps in sorted(by_ats.items(), key=lambda x: -len(x[1])):
        print(f"  {ats}: {len(comps)}")
    
    # Phase 2: Pre-filter companies with obviously invalid identifiers
    print("\n[Phase 2] Pre-filtering invalid ATS identifiers...")
    valid_companies = []
    invalid_identifiers = []
    
    for company in companies:
        identifier = company.get("ats_identifier")
        if identifier and is_invalid_identifier(identifier):
            invalid_identifiers.append(company)
            # Clear the invalid identifier
            await clear_invalid_ats_identifier(company["id"], identifier)
        else:
            valid_companies.append(company)
    
    print(f"  Valid identifiers: {len(valid_companies)}")
    print(f"  Invalid identifiers (cleared): {len(invalid_identifiers)}")
    
    if invalid_identifiers:
        print("\n  Companies with cleared invalid identifiers:")
        for c in invalid_identifiers[:10]:  # Show first 10
            id_preview = c["ats_identifier"][:40] + "..." if len(c["ats_identifier"]) > 40 else c["ats_identifier"]
            print(f"    - {c['name']}: {id_preview}")
        if len(invalid_identifiers) > 10:
            print(f"    ... and {len(invalid_identifiers) - 10} more")
    
    # Phase 3: Test crawlability for valid companies
    print(f"\n[Phase 3] Testing crawlability for {len(valid_companies)} companies...")
    
    rate_limiter = RateLimiter()
    results = {
        "success": [],
        "failed": [],
        "no_jobs": [],  # Crawled successfully but no jobs found
    }
    
    # Collect ATS types that had successful crawls
    successful_ats_types = set()
    
    # Process in batches with concurrency limit
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent crawls
    
    async def test_one(company: dict, idx: int, total: int):
        async with semaphore:
            name = company["name"]
            ats = company["ats_type"]
            
            # Skip companies without careers_url and identifier
            if not company.get("careers_url") and not company.get("ats_identifier"):
                result = {
                    "success": False,
                    "error": "No careers URL or ATS identifier",
                    "reason": "no_url_or_identifier",
                }
            else:
                result = await test_company_crawl(company["id"], rate_limiter)
            
            success = result.get("success", False)
            jobs = result.get("jobs_extracted", 0)
            
            status = "✓" if success else "✗"
            print(f"  [{idx+1}/{total}] {status} {name} ({ats}): ", end="")
            
            if success:
                if jobs > 0:
                    print(f"{jobs} jobs extracted")
                    results["success"].append({**company, "jobs": jobs})
                    successful_ats_types.add(ats)
                else:
                    print("0 jobs (possibly no openings)")
                    results["no_jobs"].append({**company, "reason": "no_jobs_found"})
            else:
                error = result.get("error", "Unknown")
                reason = result.get("reason", "unknown")
                print(f"FAILED - {reason}: {error[:50]}")
                results["failed"].append({**company, "error": error, "reason": reason})
                await mark_company_crawl_failed(company["id"], reason, error)
    
    # Run all tests
    tasks = [test_one(c, i, len(valid_companies)) for i, c in enumerate(valid_companies)]
    await asyncio.gather(*tasks)
    
    # Phase 4: Summary
    print("\n" + "=" * 60)
    print("[Phase 4] RESULTS SUMMARY")
    print("=" * 60)
    
    total_jobs = sum(c.get("jobs", 0) for c in results["success"])
    
    print(f"\n✓ Successful crawls with jobs: {len(results['success'])} ({total_jobs} jobs extracted)")
    print(f"○ Successful but no jobs: {len(results['no_jobs'])}")
    print(f"✗ Failed crawls: {len(results['failed'])}")
    print(f"⚠ Invalid identifiers cleared: {len(invalid_identifiers)}")
    
    # Show failure reasons breakdown
    if results["failed"]:
        print("\nFailure reasons breakdown:")
        reason_counts = {}
        for f in results["failed"]:
            r = f.get("reason", "unknown")
            reason_counts[r] = reason_counts.get(r, 0) + 1
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")
    
    # Save results to file
    results_file = Path(__file__).parent / "crawl_results.json"
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "success": len(results["success"]),
                "no_jobs": len(results["no_jobs"]),
                "failed": len(results["failed"]),
                "invalid_cleared": len(invalid_identifiers),
                "total_jobs_extracted": total_jobs,
            },
            "success": results["success"],
            "no_jobs": results["no_jobs"],
            "failed": results["failed"],
            "invalid_identifiers": invalid_identifiers,
        }, f, indent=2, default=str)
    print(f"\nResults saved to: {results_file}")
    
    # Phase 5: Enrichment for successful ATS types
    if results["success"] and successful_ats_types:
        print(f"\n[Phase 5] Running enrichment for ATS types: {', '.join(successful_ats_types)}")
        await run_enrichment_for_ats_types(list(successful_ats_types))
    
    # Phase 6: Generate embeddings
    if results["success"]:
        print("\n[Phase 6] Generating embeddings...")
        embeddings_count = await run_embeddings()
        print(f"Generated {embeddings_count} embeddings")
    
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
