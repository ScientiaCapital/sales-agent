"""Webhooks package - External service webhook handlers"""

from app.api.webhooks.close_reply import router as close_reply_router
from fastapi import APIRouter

# Create main webhooks router
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Include sub-routers
router.include_router(close_reply_router)

__all__ = ["router"]
