from fastapi import APIRouter

from app.api.v1 import auth, billing, counties, health, leads, letters, tasks

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(billing.router)
api_router.include_router(leads.router)
api_router.include_router(letters.router)
api_router.include_router(counties.router)
api_router.include_router(tasks.router)
