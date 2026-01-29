"""Discovery sources for autonomous company discovery."""

from app.engines.discovery.sources.base import (
    DeduplicationService,
    DiscoveredCompany,
    DiscoverySource,
    DiscoveryStats,
)
from app.engines.discovery.sources.ats_directories import ATSDirectoriesSource
from app.engines.discovery.sources.yc_companies import YCCompaniesSource
from app.engines.discovery.sources.github_orgs import GitHubOrgsSource
from app.engines.discovery.sources.network_crawler import NetworkCrawlerSource
from app.engines.discovery.sources.funding_news import FundingNewsSource
from app.engines.discovery.sources.job_aggregators import JobAggregatorsSource
from app.engines.discovery.sources.ats_prober import ATSProberSource
from app.engines.discovery.sources.google_search import GoogleSearchSource

__all__ = [
    # Base classes
    "DeduplicationService",
    "DiscoveredCompany",
    "DiscoverySource",
    "DiscoveryStats",
    # Sources
    "ATSDirectoriesSource",
    "YCCompaniesSource",
    "GitHubOrgsSource",
    "NetworkCrawlerSource",
    "FundingNewsSource",
    "JobAggregatorsSource",
    "ATSProberSource",
    "GoogleSearchSource",
]
