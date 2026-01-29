"""Discovery Engine - identifies companies and career pages to crawl.

This module provides:
- DiscoveryEngine: Original discovery service for manual company discovery
- DiscoveryOrchestrator: Autonomous discovery from multiple sources
- Discovery sources: ATS directories, YC companies, GitHub orgs, etc.
- US location detection: Filter for US-based companies
"""

from app.engines.discovery.service import DiscoveryEngine, seed_companies
from app.engines.discovery.orchestrator import DiscoveryOrchestrator
from app.engines.discovery.us_detector import USLocationDetector, detect_us_from_location
from app.engines.discovery.ats_detector import detect_ats_type, get_careers_url
from app.engines.discovery.sources import (
    DiscoveredCompany,
    DiscoverySource,
    DiscoveryStats,
    ATSDirectoriesSource,
    YCCompaniesSource,
    GitHubOrgsSource,
    NetworkCrawlerSource,
    FundingNewsSource,
)

__all__ = [
    # Core services
    "DiscoveryEngine",
    "DiscoveryOrchestrator",
    "seed_companies",
    # Detection
    "USLocationDetector",
    "detect_us_from_location",
    "detect_ats_type",
    "get_careers_url",
    # Source base classes
    "DiscoveredCompany",
    "DiscoverySource",
    "DiscoveryStats",
    # Source implementations
    "ATSDirectoriesSource",
    "YCCompaniesSource",
    "GitHubOrgsSource",
    "NetworkCrawlerSource",
    "FundingNewsSource",
]
