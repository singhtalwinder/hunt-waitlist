"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import update, func

from app.api import router as api_router
from app.config import get_settings
from app.db.session import async_session_factory
from app.db.models import DiscoveryRun, VerificationRun, MaintenanceRun

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

settings = get_settings()
logger = structlog.get_logger()

# Initialize Sentry if configured
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1 if settings.is_production else 1.0,
    )


async def cleanup_orphaned_runs():
    """Mark any 'running' runs as failed on startup.
    
    When the server restarts (deploy, crash, etc.), any runs that were
    in progress are now orphaned since the process handling them is gone.
    """
    async with async_session_factory() as session:
        # Cleanup orphaned discovery runs
        result = await session.execute(
            update(DiscoveryRun)
            .where(DiscoveryRun.status == "running")
            .values(
                status="failed",
                error_message="Interrupted by server restart",
                completed_at=func.now(),
            )
        )
        discovery_count = result.rowcount
        
        # Cleanup orphaned verification runs
        result = await session.execute(
            update(VerificationRun)
            .where(VerificationRun.status == "running")
            .values(
                status="failed",
                error_message="Interrupted by server restart",
                completed_at=func.now(),
            )
        )
        verification_count = result.rowcount
        
        # Cleanup orphaned maintenance runs
        result = await session.execute(
            update(MaintenanceRun)
            .where(MaintenanceRun.status == "running")
            .values(
                status="failed",
                error_message="Interrupted by server restart",
                completed_at=func.now(),
            )
        )
        maintenance_count = result.rowcount
        
        await session.commit()
        
        total = discovery_count + verification_count + maintenance_count
        if total > 0:
            logger.info(
                "Cleaned up orphaned runs",
                discovery=discovery_count,
                verification=verification_count,
                maintenance=maintenance_count,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Hunt API", environment=settings.environment)
    await cleanup_orphaned_runs()
    yield
    # Shutdown
    logger.info("Shutting down Hunt API")


app = FastAPI(
    title="Hunt API",
    description="Job discovery and matching API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://hunt.dev",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard - overview and quick actions."""
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {"request": request, "page": "dashboard"}
    )


@app.get("/admin/pipeline", response_class=HTMLResponse)
async def admin_pipeline(request: Request):
    """Admin pipeline control center."""
    return templates.TemplateResponse(
        "admin/pipeline.html",
        {"request": request, "page": "pipeline"}
    )


@app.get("/admin/discovery", response_class=HTMLResponse)
async def admin_discovery(request: Request):
    """Admin company discovery management."""
    return templates.TemplateResponse(
        "admin/discovery.html",
        {"request": request, "page": "discovery"}
    )


@app.get("/admin/maintenance", response_class=HTMLResponse)
async def admin_maintenance(request: Request):
    """Admin maintenance - verify and update job listings."""
    return templates.TemplateResponse(
        "admin/maintenance.html",
        {"request": request, "page": "maintenance"}
    )


@app.get("/admin/companies", response_class=HTMLResponse)
async def admin_companies(request: Request):
    """Admin companies list."""
    return templates.TemplateResponse(
        "admin/companies.html",
        {"request": request, "page": "companies"}
    )


@app.get("/admin/jobs", response_class=HTMLResponse)
async def admin_jobs(request: Request):
    """Admin jobs list."""
    return templates.TemplateResponse(
        "admin/jobs.html",
        {"request": request, "page": "jobs"}
    )
