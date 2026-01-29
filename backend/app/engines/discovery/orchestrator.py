"""Discovery Orchestrator - coordinates all discovery sources.

The orchestrator:
1. Runs all enabled discovery sources
2. Deduplicates discovered companies by domain
3. Filters for US companies
4. Queues companies for ATS detection and processing
5. Tracks discovery runs and statistics
"""

from datetime import datetime
from typing import AsyncIterator, List, Optional, Type

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Company, DiscoveryQueue, DiscoveryRun
from app.engines.discovery.sources.base import (
    DeduplicationService,
    DiscoveredCompany,
    DiscoverySource,
    DiscoveryStats,
)
from app.engines.discovery.sources import (
    ATSDirectoriesSource,
    YCCompaniesSource,
    GitHubOrgsSource,
    NetworkCrawlerSource,
    FundingNewsSource,
    JobAggregatorsSource,
    ATSProberSource,
    GoogleSearchSource,
)
from app.engines.discovery.us_detector import USLocationDetector, detect_us_from_location
from app.engines.discovery.ats_detector import detect_ats_type, get_careers_url

logger = structlog.get_logger()


class DiscoveryOrchestrator:
    """Orchestrates company discovery from multiple sources."""
    
    # Default sources to run (order matters - fastest first, slowest last)
    # Note: GoogleSearchSource is excluded from defaults as it costs money
    DEFAULT_SOURCES: List[Type[DiscoverySource]] = [
        ATSDirectoriesSource,
        YCCompaniesSource,
        GitHubOrgsSource,
        FundingNewsSource,
        JobAggregatorsSource,
        ATSProberSource,      # Fast ATS probing with verification
        NetworkCrawlerSource, # Last - slowest but finds network connections
    ]
    
    def __init__(
        self,
        db: AsyncSession,
        sources: Optional[List[DiscoverySource]] = None,
        us_only: bool = False,  # Disabled for now
        check_website_location: bool = False,  # Can be slow
    ):
        """Initialize the orchestrator.
        
        Args:
            db: Database session
            sources: List of discovery sources to use (uses defaults if not provided)
            us_only: Only discover US companies
            check_website_location: Fetch websites to detect location (slower but more accurate)
        """
        self.db = db
        self.sources = sources
        self.us_only = us_only
        self.check_website_location = check_website_location
        self._existing_domains: set[str] = set()
        self._queued_domains: set[str] = set()
        self.dedup = DeduplicationService()
    
    async def _load_existing_domains(self) -> None:
        """Load existing company domains from database."""
        # Get domains from companies table
        result = await self.db.execute(
            select(Company.domain).where(Company.domain.isnot(None))
        )
        self._existing_domains = {row[0].lower() for row in result.fetchall()}
        
        # Get domains from discovery queue (pending or processing)
        result = await self.db.execute(
            select(DiscoveryQueue.domain)
            .where(DiscoveryQueue.domain.isnot(None))
            .where(DiscoveryQueue.status.in_(["pending", "processing"]))
        )
        self._queued_domains = {row[0].lower() for row in result.fetchall() if row[0]}
        
        # Also load ATS pairs for dedup service
        result = await self.db.execute(
            select(Company.ats_type, Company.ats_identifier)
            .where(Company.ats_type.isnot(None))
            .where(Company.ats_identifier.isnot(None))
        )
        ats_pairs = {
            f"{r[0]}:{r[1].lower()}" 
            for r in result.fetchall() 
            if r[0] and r[1]
        }
        
        # Initialize shared dedup service
        self.dedup.load_existing(self._existing_domains, self._queued_domains, ats_pairs)
        
        logger.info(
            "Loaded existing domains",
            companies=len(self._existing_domains),
            queued=len(self._queued_domains),
            ats_pairs=len(ats_pairs),
        )
    
    async def run_discovery(
        self,
        source_names: Optional[List[str]] = None,
        force_network_recrawl: bool = False,
    ) -> List[DiscoveryStats]:
        """Run discovery from all or specified sources.
        
        Args:
            source_names: Optional list of source names to run (runs all if not specified)
            force_network_recrawl: If True, re-crawl all companies in network_crawler
                                   (by default, only crawls companies never crawled before)
            
        Returns:
            List of DiscoveryStats for each source
        """
        await self._load_existing_domains()
        
        # Initialize sources
        sources = self.sources
        if sources is None:
            sources = []
            for cls in self.DEFAULT_SOURCES:
                # Some sources need db session and options
                if cls == NetworkCrawlerSource:
                    sources.append(cls(db=self.db, force_recrawl=force_network_recrawl))
                elif cls == ATSProberSource:
                    sources.append(cls(db=self.db))
                else:
                    sources.append(cls())
        
        # Filter by source names if specified
        if source_names:
            sources = [s for s in sources if s.source_name in source_names]
        
        # Inject dedup service into all sources
        for source in sources:
            source.set_dedup_service(self.dedup)
        
        stats_list = []
        
        for source in sources:
            try:
                stats = await self._run_source(source)
                stats_list.append(stats)
            except Exception as e:
                logger.error("Error running discovery source", source=source.source_name, error=str(e))
                # Create failed stats
                stats = DiscoveryStats(
                    source=source.source_name,
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                    errors=1,
                )
                stats_list.append(stats)
        
        return stats_list
    
    async def _log_to_run(
        self, 
        run: DiscoveryRun, 
        level: str, 
        msg: str, 
        data: dict = None,
        commit: bool = True,
        current_step: str = None,
        progress_count: int = None,
        progress_total: int = None,
    ) -> None:
        """Add a log entry to the discovery run with immediate commit for real-time visibility.
        
        Args:
            run: The DiscoveryRun to log to
            level: Log level (info, warn, error, debug)
            msg: Log message
            data: Optional additional data
            commit: Whether to commit immediately (default True for real-time visibility)
            current_step: Update current step
            progress_count: Update progress count
            progress_total: Update progress total
        """
        # Create short run ID for display (first 8 chars of UUID)
        run_id_short = str(run.id)[:8]
        
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "msg": msg,
            "run_id": run_id_short,
        }
        if data:
            log_entry["data"] = data
        
        # Append to logs
        if run.logs is None:
            run.logs = []
        run.logs = run.logs + [log_entry]  # Create new list to trigger change detection
        
        # Update progress fields if provided
        if current_step is not None:
            run.current_step = current_step
        if progress_count is not None:
            run.progress_count = progress_count
        if progress_total is not None:
            run.progress_total = progress_total
        
        # Commit immediately for real-time visibility
        if commit:
            try:
                await self.db.commit()
            except Exception:
                try:
                    await self.db.rollback()
                except Exception:
                    pass
    
    async def _run_source(self, source: DiscoverySource) -> DiscoveryStats:
        """Run a single discovery source."""
        stats = DiscoveryStats(
            source=source.source_name,
            started_at=datetime.utcnow(),
        )
        
        # Create discovery run record
        run = DiscoveryRun(
            source=source.source_name,
            status="running",
            logs=[],
            current_step="Initializing",
            progress_count=0,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        
        logger.info("Starting discovery", source=source.source_name)
        await self._log_to_run(run, "info", f"Starting discovery from {source.source_name}")
        
        try:
            async with source:
                logger.info("Source initialized", source=source.source_name)
                await self._log_to_run(
                    run, "info", "Source initialized, beginning discovery",
                    current_step="Discovering companies",
                    commit=True
                )
                
                company_count = 0
                last_commit_count = 0
                last_progress_update = 0
                
                async for company in source.discover():
                    company_count += 1
                    
                    # Update progress from source (for sources that track their own progress)
                    # This gives us "crawling X/Y" for network_crawler
                    source_progress = source.progress_current
                    source_total = source.progress_total
                    
                    # Update run stats and progress frequently (every company or when source progress changes)
                    if source_progress != last_progress_update or company_count % 5 == 0:
                        last_progress_update = source_progress
                        
                        # Update stats on the run object in real-time
                        run.total_discovered = stats.total_discovered
                        run.new_companies = stats.new_companies
                        run.skipped_duplicates = stats.skipped_duplicates
                        run.filtered_non_us = stats.filtered_non_us
                        run.errors = stats.errors
                        run.updated_companies = stats.updated_companies
                        
                        # Set progress info
                        if source_total > 0:
                            run.progress_count = source_progress
                            run.progress_total = source_total
                            step = f"Crawling companies ({source_progress}/{source_total})"
                        else:
                            run.progress_count = company_count
                            step = f"Discovering companies ({company_count} found)"
                        
                        run.current_step = step
                        
                        # Log progress
                        if company_count % 5 == 0:
                            logger.info("Discovery progress", source=source.source_name, 
                                       crawled=source_progress, total=source_total, found=company_count)
                            await self._log_to_run(
                                run, "info", f"Crawled {source_progress}/{source_total} companies" if source_total > 0 else f"Found {company_count} companies",
                                data={
                                    "new": stats.new_companies, 
                                    "duplicates": stats.skipped_duplicates,
                                    "errors": stats.errors,
                                },
                                commit=True
                            )
                    
                    # Commit every 10 new companies to save progress frequently
                    if stats.new_companies - last_commit_count >= 10:
                        try:
                            await self.db.commit()
                            last_commit_count = stats.new_companies
                            logger.info(f"💾 Saved {stats.new_companies} companies to database")
                        except Exception as e:
                            logger.warning(f"Commit error (will retry): {e}")
                    
                    try:
                        result = await self._process_discovered_company(company)
                        stats.total_discovered += 1
                        
                        # Refresh run object to get latest state (may have been invalidated by rollback)
                        # Then re-apply current in-memory stats
                        await self.db.refresh(run)
                        run.total_discovered = stats.total_discovered
                        run.new_companies = stats.new_companies
                        run.skipped_duplicates = stats.skipped_duplicates
                        run.errors = stats.errors
                        
                        if result == "new":
                            stats.new_companies += 1
                            # Log all new companies for visibility
                            ats_info = f" (ATS: {company.ats_type})" if company.ats_type else ""
                            await self._log_to_run(
                                run, "info", f"✓ New: {company.name} ({company.domain}){ats_info}",
                                data={"domain": company.domain, "ats": company.ats_type, "careers_url": company.careers_url}
                            )
                        elif result == "queued":
                            # Queued for later processing (incomplete data)
                            stats.new_companies += 1
                            await self._log_to_run(
                                run, "info", f"⏳ Queued: {company.name} ({company.domain})",
                                data={"domain": company.domain, "reason": "needs_enrichment"}
                            )
                        elif result == "duplicate":
                            stats.skipped_duplicates += 1
                        elif result == "non_us":
                            stats.filtered_non_us += 1
                        elif result == "updated":
                            stats.updated_companies += 1
                            
                    except Exception as e:
                        stats.errors += 1
                        await self._log_to_run(
                            run, "warn", f"Error processing {company.name}: {str(e)[:100]}"
                        )
                        logger.warning(
                            "Error processing discovered company",
                            company=company.name,
                            error=str(e),
                        )
                    
                    # Force commit every 50 companies regardless of new count
                    if company_count % 50 == 0:
                        try:
                            await self.db.commit()
                            logger.info(f"💾 Checkpoint: {company_count} processed, {stats.new_companies} new saved")
                        except Exception:
                            pass
                
                logger.info("Source discovery complete", source=source.source_name, total=company_count)
                await self._log_to_run(
                    run, "info", f"Discovery complete: {company_count} total companies processed",
                    current_step="Finalizing",
                    progress_count=company_count,
                    commit=True
                )
                
                # Commit batch to avoid connection timeouts on long runs
                await self.db.commit()
            
            # Update run record
            run.status = "completed"
            run.total_discovered = stats.total_discovered
            run.new_companies = stats.new_companies
            run.updated_companies = stats.updated_companies
            run.skipped_duplicates = stats.skipped_duplicates
            run.filtered_non_us = stats.filtered_non_us
            run.errors = stats.errors
            run.completed_at = datetime.utcnow()
            run.current_step = "Completed"
            
            await self._log_to_run(
                run, "info", 
                f"Run completed: {stats.new_companies} new, {stats.skipped_duplicates} duplicates, {stats.filtered_non_us} filtered",
                data={
                    "new_companies": stats.new_companies,
                    "updated": stats.updated_companies,
                    "duplicates": stats.skipped_duplicates,
                    "filtered_non_us": stats.filtered_non_us,
                    "errors": stats.errors,
                }
            )
            
        except Exception as e:
            logger.error("Discovery source failed", source=source.source_name, error=str(e))
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()
            run.current_step = "Failed"
            await self._log_to_run(run, "error", f"Discovery failed: {str(e)[:200]}")
            raise
        
        finally:
            await self.db.commit()
        
        stats.completed_at = datetime.utcnow()
        
        logger.info(
            "Discovery completed",
            source=source.source_name,
            total=stats.total_discovered,
            new=stats.new_companies,
            duplicates=stats.skipped_duplicates,
            non_us=stats.filtered_non_us,
            errors=stats.errors,
            duration_seconds=stats.duration_seconds(),
        )
        
        return stats
    
    async def _process_discovered_company(
        self,
        company: DiscoveredCompany,
    ) -> str:
        """Process a discovered company.
        
        If the company has complete data (domain + careers_url), creates a Company
        record directly. Otherwise, adds to the discovery queue for later processing.
        
        Returns:
            "new" - Created new company
            "duplicate" - Already exists
            "non_us" - Filtered out (not US)
            "updated" - Updated existing record
            "queued" - Added to queue for later processing
        """
        domain = company.domain.lower() if company.domain else None
        
        # Check for duplicates FIRST - before any processing
        if domain:
            if domain in self._existing_domains or domain in self._queued_domains:
                return "duplicate"
            
            # Immediately mark as seen to prevent duplicates within the same run
            # This is critical for parallel discovery from multiple sources
            self._existing_domains.add(domain)
            self.dedup.mark_discovered(domain, company.ats_type, company.ats_identifier)
        
        # Apply US filter (but be lenient for companies with ATS careers pages)
        if self.us_only:
            is_us = False
            filter_reason = None
            
            # Trusted US sources - these are known US-focused platforms
            trusted_us_sources = {
                "yc_directory", "yc_directory_waas",  # Y Combinator is US-based
                "github_orgs",  # GitHub trending is heavily US
                "funding_news",  # Funding news tends to be US-focused
                "job_aggregators",  # US job boards
            }
            
            # Check explicit country
            if company.country and company.country.upper() == "US":
                is_us = True
            # Check location string
            elif company.location:
                is_us, _ = detect_us_from_location(company.location)
                if not is_us:
                    filter_reason = f"location '{company.location}' not recognized as US"
            # If company has an ATS careers URL, it's likely a legit company worth reviewing
            elif company.careers_url and company.ats_type:
                is_us = True  # Accept companies with detected ATS, let manual review filter
            # If source is from network_crawler with _careers suffix, it has a career page
            elif company.source and "_careers" in company.source:
                is_us = True
            # Trust companies from known US-focused sources even without location data
            elif company.source and company.source in trusted_us_sources:
                is_us = True
            else:
                filter_reason = "no country, location, or ATS info provided"
            
            if not is_us:
                logger.debug(
                    "Filtered non-US company",
                    name=company.name,
                    domain=company.domain,
                    reason=filter_reason,
                    country=company.country,
                    location=company.location,
                    has_careers_url=bool(company.careers_url),
                    ats_type=company.ats_type,
                    source=company.source,
                )
                return "non_us"
        
        # If we have complete data (domain + careers_url), create Company directly
        if domain and company.careers_url:
            try:
                new_company = Company(
                    name=company.name,
                    domain=domain,
                    website_url=company.website_url or f"https://{domain}",
                    careers_url=company.careers_url,
                    ats_type=company.ats_type,
                    ats_identifier=company.ats_identifier,
                    discovery_source=company.source,
                    discovered_at=datetime.utcnow(),
                    country=company.country or ("US" if self.us_only else None),
                    location=company.location,
                    description=company.description,
                    industry=company.industry,
                    employee_count=company.employee_count,
                    funding_stage=company.funding_stage,
                    crawl_priority=30,  # Lower priority for discovered companies
                    is_active=True,
                )
                self.db.add(new_company)
                
                return "new"
                
            except Exception as e:
                # If insert fails (e.g., unique constraint violation), treat as duplicate
                # CRITICAL: Must rollback to clear the session's error state
                await self.db.rollback()
                
                error_str = str(e).lower()
                if "duplicate" in error_str or "unique" in error_str:
                    logger.debug(f"Duplicate company {domain} (constraint violation)")
                    return "duplicate"
                # For other errors, log and continue without queuing
                logger.warning(f"Error creating company {domain}: {e}")
                return "duplicate"  # Don't queue on errors, domain is already tracked
        
        # Only queue companies with incomplete data (no careers_url)
        # This should be rare - most discoveries have complete data
        if not company.careers_url:
            queue_item = DiscoveryQueue(
                name=company.name,
                domain=domain,
                careers_url=company.careers_url,
                website_url=company.website_url,
                source=company.source,
                source_url=company.source_url,
                location=company.location,
                country=company.country or ("US" if self.us_only else None),
                description=company.description,
                industry=company.industry,
                employee_count=company.employee_count,
                funding_stage=company.funding_stage,
                ats_type=company.ats_type,
                ats_identifier=company.ats_identifier,
                status="pending",
            )
            
            self.db.add(queue_item)
            
            # Track in queued domains for dedup
            if domain:
                self._queued_domains.add(domain)
            
            return "queued"
        
        # Shouldn't reach here, but treat as duplicate if we do
        return "duplicate"
    
    async def process_queue(
        self,
        limit: int = 100,
        detect_ats: bool = True,
    ) -> dict:
        """Process items from the discovery queue.
        
        Args:
            limit: Maximum items to process
            detect_ats: Whether to detect ATS type
            
        Returns:
            Stats dict with processed, created, failed counts
        """
        import httpx
        
        stats = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "failed": 0,
            "skipped": 0,
            "review": 0,
        }
        
        # Get pending items with row locking for parallel processing
        # FOR UPDATE SKIP LOCKED ensures each processor gets different items
        result = await self.db.execute(
            select(DiscoveryQueue)
            .where(DiscoveryQueue.status == "pending")
            .order_by(DiscoveryQueue.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        items = list(result.scalars().all())
        
        if not items:
            return stats
        
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "HuntBot/1.0 (+https://hunt.dev/bot)"},
        ) as http_client:
            for item in items:
                try:
                    item.status = "processing"
                    await self.db.commit()
                    
                    result = await self._process_queue_item(item, http_client, detect_ats)
                    stats["processed"] += 1
                    
                    if result == "created":
                        stats["created"] += 1
                    elif result == "updated":
                        stats["updated"] += 1
                    elif result == "skipped":
                        stats["skipped"] += 1
                    elif result == "review":
                        stats["review"] += 1
                        
                except Exception as e:
                    stats["failed"] += 1
                    try:
                        await self.db.rollback()
                    except Exception:
                        pass
                    
                    # Re-fetch the item since we rolled back
                    try:
                        result = await self.db.execute(
                            select(DiscoveryQueue).where(DiscoveryQueue.id == item.id)
                        )
                        item = result.scalar_one_or_none()
                        if item:
                            item.status = "failed" if item.retry_count >= 3 else "pending"
                            item.retry_count += 1
                            item.error_message = str(e)[:500]
                            await self.db.commit()
                    except Exception:
                        pass
                    
                    logger.warning(
                        "Failed to process queue item",
                        item_id=str(item.id) if item else "unknown",
                        error=str(e)[:200],
                    )
                    continue
                
                try:
                    await self.db.commit()
                except Exception as e:
                    logger.warning("Commit failed", error=str(e)[:200])
                    try:
                        await self.db.rollback()
                    except Exception:
                        pass
        
        return stats
    
    async def _process_queue_item(
        self,
        item: DiscoveryQueue,
        http_client,
        detect_ats: bool,
    ) -> str:
        """Process a single queue item.
        
        Returns:
            "created", "updated", or "skipped"
        """
        # Check if company already exists
        existing = None
        if item.domain:
            result = await self.db.execute(
                select(Company).where(Company.domain == item.domain)
            )
            existing = result.scalar_one_or_none()
        
        # Try to detect careers URL and ATS if needed
        careers_url = item.careers_url
        ats_type = item.ats_type
        ats_identifier = item.ats_identifier
        
        if detect_ats and item.website_url and not careers_url:
            # Try to find careers page
            domain = item.domain or item.website_url.replace("https://", "").replace("http://", "").split("/")[0]
            careers_url = await get_careers_url(http_client, domain)
        
        if detect_ats and careers_url and not ats_type:
            # Detect ATS type
            ats_type, ats_identifier = await detect_ats_type(http_client, careers_url)
        
        if existing:
            # Update existing company
            if careers_url and not existing.careers_url:
                existing.careers_url = careers_url
            if ats_type and not existing.ats_type:
                existing.ats_type = ats_type
                existing.ats_identifier = ats_identifier
            if item.description and not existing.description:
                existing.description = item.description
            if item.industry and not existing.industry:
                existing.industry = item.industry
            if item.employee_count and not existing.employee_count:
                existing.employee_count = item.employee_count
            
            item.status = "completed"
            item.company_id = existing.id
            item.processed_at = datetime.utcnow()
            
            return "updated"
        
        elif item.domain or careers_url:
            # Create new company - handle race condition with parallel processors
            try:
                company = Company(
                    name=item.name,
                    domain=item.domain,
                    website_url=item.website_url,
                    careers_url=careers_url,
                    ats_type=ats_type,
                    ats_identifier=ats_identifier,
                    discovery_source=item.source,
                    discovered_at=item.created_at,
                    country=item.country,
                    location=item.location,
                    description=item.description,
                    industry=item.industry,
                    employee_count=item.employee_count,
                    funding_stage=item.funding_stage,
                    crawl_priority=30,  # Lower priority for discovered companies
                )
                
                self.db.add(company)
                await self.db.flush()
                
                item.status = "completed"
                item.company_id = company.id
            except Exception as e:
                # CRITICAL: Always rollback on error to clear session state
                await self.db.rollback()
                
                # Handle duplicate key error (parallel processor already inserted)
                if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                    # Re-check for existing company
                    result = await self.db.execute(
                        select(Company).where(Company.domain == item.domain)
                    )
                    existing = result.scalar_one_or_none()
                    if existing:
                        item.status = "completed"
                        item.company_id = existing.id
                        item.processed_at = datetime.utcnow()
                        return "updated"
                raise
            item.processed_at = datetime.utcnow()
            
            return "created"
        
        else:
            # Can't find careers page - mark for manual review
            item.status = "review"
            item.error_message = "Could not find careers page automatically"
            item.processed_at = datetime.utcnow()
            return "review"
    
    async def get_stats(self) -> dict:
        """Get discovery statistics."""
        from sqlalchemy import text
        
        # Queue stats
        queue_result = await self.db.execute(
            select(
                DiscoveryQueue.status,
                func.count(DiscoveryQueue.id),
            ).group_by(DiscoveryQueue.status)
        )
        queue_stats = {row[0]: row[1] for row in queue_result.fetchall()}
        
        # Queue activity - items added in last hour (helps detect ongoing discoveries)
        recent_queue_result = await self.db.execute(text("""
            SELECT 
                COUNT(*) as added_last_hour,
                MAX(created_at) as last_added_at
            FROM discovery_queue
            WHERE created_at > NOW() - INTERVAL '1 hour'
        """))
        recent_row = recent_queue_result.fetchone()
        queue_stats["added_last_hour"] = recent_row[0] if recent_row else 0
        queue_stats["last_added_at"] = recent_row[1].isoformat() if recent_row and recent_row[1] else None
        
        # Source stats
        source_result = await self.db.execute(
            select(
                DiscoveryQueue.source,
                func.count(DiscoveryQueue.id),
            ).group_by(DiscoveryQueue.source)
        )
        source_stats = {row[0]: row[1] for row in source_result.fetchall()}
        
        # Recent runs (including running count for visibility)
        runs_result = await self.db.execute(
            select(DiscoveryRun)
            .order_by(DiscoveryRun.started_at.desc())
            .limit(10)
        )
        runs_list = list(runs_result.scalars().all())
        recent_runs = [
            {
                "source": run.source,
                "status": run.status,
                "total_discovered": run.total_discovered,
                "new_companies": run.new_companies,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            }
            for run in runs_list
        ]
        
        # Count running discoveries
        running_count = sum(1 for run in runs_list if run.status == "running")
        
        # Total companies from discovery
        discovered_count = await self.db.execute(
            select(func.count(Company.id))
            .where(Company.discovery_source.isnot(None))
        )
        
        # Companies ready for pipeline (have ATS, haven't been crawled in 24h)
        ready_for_crawl_result = await self.db.execute(text("""
            SELECT COUNT(*) 
            FROM companies 
            WHERE is_active = true 
            AND ats_type IS NOT NULL 
            AND (
                last_crawled_at IS NULL 
                OR last_crawled_at < NOW() - INTERVAL '24 hours'
            )
        """))
        ready_for_crawl = ready_for_crawl_result.scalar() or 0
        
        return {
            "queue": queue_stats,
            "by_source": source_stats,
            "recent_runs": recent_runs,
            "running_count": running_count,
            "total_discovered_companies": discovered_count.scalar() or 0,
            "ready_for_crawl": ready_for_crawl,
        }
