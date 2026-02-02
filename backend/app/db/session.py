"""Database session management."""

from collections.abc import AsyncGenerator
from urllib.parse import urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()


def get_pooler_url(database_url: str) -> str:
    """
    Convert a direct Supabase database URL to use the connection pooler (Supavisor).
    
    Supabase pooler uses port 6543 instead of 5432.
    This dramatically increases connection capacity (from ~20 to thousands).
    
    Example:
        Input:  postgresql+asyncpg://user:pass@db.xxx.supabase.co:5432/postgres
        Output: postgresql+asyncpg://user:pass@db.xxx.supabase.co:6543/postgres
    """
    parsed = urlparse(database_url)
    
    # Only modify if it looks like a Supabase URL with port 5432
    if parsed.port == 5432 and 'supabase' in (parsed.hostname or ''):
        # Replace port 5432 with 6543 (pooler port)
        new_netloc = parsed.netloc.replace(':5432', ':6543')
        
        pooler_url = urlunparse((
            parsed.scheme,
            new_netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        return pooler_url
    
    return database_url


# Get database URL, converting to pooler if it's a Supabase direct connection
database_url = get_pooler_url(str(settings.database_url))

# Create async engine
# Using Supabase connection pooler (Supavisor) for better connection management.
# Reduced pool size since the external pooler handles connection multiplexing.
engine = create_async_engine(
    database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=3,       # Reduced from 10 - pooler handles multiplexing
    max_overflow=5,    # Reduced from 15 - max 8 local connections
    pool_timeout=60,   # Wait up to 60s for a connection before failing
    pool_recycle=300,  # Recycle connections every 5 min (pooler may close idle ones)
    # Required for pgbouncer/Supavisor transaction mode - disable prepared statements
    connect_args={"statement_cache_size": 0},
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
