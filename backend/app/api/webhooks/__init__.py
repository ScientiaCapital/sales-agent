"""Webhooks package - External service webhook handlers"""

from app.api.webhooks.close_reply import router as close_reply_router
from app.api.webhooks.close import router as close_v2_router
from fastapi import APIRouter

# Create main webhooks router
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Include sub-routers
router.include_router(close_reply_router)  # Legacy: /webhooks/close/email-reply
router.include_router(close_v2_router)     # New: /webhooks/close/events (v2)

__all__ = ["router"]
