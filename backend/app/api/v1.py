from fastapi import APIRouter

from app.api import admin, auth, patients, visits

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(admin.router)
router.include_router(patients.router)
router.include_router(visits.router)
