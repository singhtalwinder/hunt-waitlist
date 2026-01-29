"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # Database
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL connection URL (asyncpg)",
    )

    # Redis
    redis_url: RedisDsn = Field(
        ...,
        description="Redis connection URL for job queue and caching",
    )

    # Supabase (for auth verification)
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_anon_key: str = Field(..., description="Supabase anonymous key")
    supabase_service_role_key: str = Field(
        default="",
        description="Supabase service role key for admin operations",
    )

    # OpenAI (optional - only used for LLM fallback extraction)
    openai_api_key: str = Field(default="", description="OpenAI API key for LLM extraction")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model to use")

    # Resend (email)
    resend_api_key: str = Field(default="", description="Resend API key for email notifications")
    email_from: str = Field(default="Hunt <jobs@hunt.dev>", description="Email from address")

    # Sentry
    sentry_dsn: str = Field(default="", description="Sentry DSN for error tracking")

    # Crawling
    crawl_user_agent: str = Field(
        default="HuntBot/1.0 (+https://hunt.dev/bot)",
        description="User agent for crawling",
    )
    crawl_rate_limit_per_domain: float = Field(
        default=1.0,
        description="Requests per second per domain",
    )
    crawl_timeout_seconds: int = Field(default=30, description="HTTP request timeout")

    # Matching
    match_score_threshold: float = Field(
        default=0.4,
        description="Minimum score to show a job match",
    )
    freshness_half_life_days: int = Field(
        default=7,
        description="Days for freshness score to decay to 0.5",
    )

    # Verification (job board uniqueness checking via direct scraping)
    verification_sample_size: int = Field(
        default=50,
        description="Number of jobs to verify per run (lower = less risk of blocking)",
    )
    verification_reverify_days: int = Field(
        default=7,
        description="Days before re-verifying a job on a board",
    )
    verification_request_delay: float = Field(
        default=3.0,
        description="Minimum seconds between requests to same job board",
    )
    
    # Google Search API (optional - for discovery)
    google_api_key: str = Field(
        default="",
        description="Google Custom Search API key",
    )
    google_cx: str = Field(
        default="",
        description="Google Custom Search Engine ID",
    )
    
    # Google Gemini API (optional - for embeddings)
    gemini_api_key: str = Field(
        default="",
        description="Google Gemini API key for embeddings (get from aistudio.google.com)",
    )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
