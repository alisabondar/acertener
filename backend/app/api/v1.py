from fastapi import APIRouter

from app.api import admin, auth, clinical, patients, summary, visits

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(admin.router)
router.include_router(patients.router)
router.include_router(visits.router)
router.include_router(clinical.router)
router.include_router(summary.router)
