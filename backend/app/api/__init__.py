"""API routes module."""

from fastapi import APIRouter

from app.api import jobs, candidates, admin, internal

router = APIRouter()

# Public routes
router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
router.include_router(candidates.router, prefix="/candidates", tags=["candidates"])

# Admin routes
router.include_router(admin.router, prefix="/admin", tags=["admin"])

# Internal routes (for workers)
router.include_router(internal.router, prefix="/internal", tags=["internal"])
