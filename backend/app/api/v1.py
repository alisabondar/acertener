from fastapi import APIRouter

from app.api import admin, auth

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(admin.router)
