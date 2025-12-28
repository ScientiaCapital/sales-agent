"""
Apollo Webhook Handler

Receives async phone number and email data from Apollo.
Apollo sends data to this webhook after processing reveal requests.

Endpoint:
- POST /webhooks/apollo/phone-reveal - Receive phone/email data from Apollo
"""

import os
import json
import logging
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/apollo", tags=["webhooks", "apollo"])


# ========== Apollo Webhook Models ==========

class ApolloDialerFlags(BaseModel):
    """Dialer flags from Apollo phone reveal."""
    country_name: Optional[str] = None
    country_enabled: Optional[bool] = None
    high_risk_calling_enabled: Optional[bool] = None
    potential_high_risk_number: Optional[bool] = None


class ApolloPhoneNumber(BaseModel):
    """Phone number data from Apollo webhook."""
    raw_number: str
    sanitized_number: str
    type_cd: Optional[str] = None  # "mobile", "work_direct", "other", etc.
    status_cd: str = "unknown"  # "valid_number", etc.
    confidence_cd: Optional[str] = None  # "high", etc.
    dnc_status_cd: Optional[str] = None
    dnc_other_info: Optional[dict] = None

    class Config:
        extra = "allow"  # Allow extra fields from Apollo


class ApolloPersonResult(BaseModel):
    """Person result from Apollo webhook people array."""
    id: str
    status: str = "unknown"  # "success", etc.
    phone_numbers: List[ApolloPhoneNumber] = Field(default_factory=list)

    class Config:
        extra = "allow"


class ApolloPhoneRevealPayload(BaseModel):
    """
    Actual payload from Apollo phone reveal webhook.
    Apollo sends: {status, people: [{id, status, phone_numbers: [...]}]}
    """
    status: str = "unknown"
    total_requested_enrichments: int = 0
    unique_enriched_records: int = 0
    missing_records: int = 0
    credits_consumed: int = 0
    people: List[ApolloPersonResult] = Field(default_factory=list)

    class Config:
        extra = "allow"


# ========== Apollo Phone Reveal Webhook ==========

@router.post("/phone-reveal")
async def handle_apollo_phone_reveal(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Receive async phone number and email data from Apollo.

    Apollo sends data asynchronously to this webhook after processing
    a reveal_phone_number request. The data is stored in Supabase.

    Flow:
    1. Apollo API request with reveal_phone_number=true + webhook_url
    2. Apollo processes request (can take minutes)
    3. Apollo POSTs phone/email data HERE
    4. We update dim_contacts and log ALL data for audit
    """
    try:
        # Get raw body for logging
        body = await request.body()
        body_str = body.decode('utf-8')

        # Log raw payload for debugging (truncated if large)
        logger.info(f"Apollo phone reveal webhook received: {len(body_str)} bytes")
        logger.debug(f"Apollo raw payload: {body_str[:2000]}")

        # Parse the payload
        try:
            payload_dict = json.loads(body_str)
            payload = ApolloPhoneRevealPayload(**payload_dict)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Apollo payload as JSON: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        except Exception as e:
            logger.warning(f"Failed to validate Apollo payload: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid payload structure: {e}")

        # Extract phone numbers from people array
        all_phone_numbers = []
        apollo_person_ids = []
        for person_result in payload.people:
            apollo_person_ids.append(person_result.id)
            all_phone_numbers.extend(person_result.phone_numbers)

        if not all_phone_numbers:
            logger.info(f"Apollo webhook: no phone numbers found (status={payload.status}, people={len(payload.people)})")
            return JSONResponse({
                "status": "received",
                "message": "No phone numbers in payload",
                "phones_updated": 0,
                "credits_consumed": payload.credits_consumed
            })

        # Get the best phone number (first valid one)
        best_phone = None
        for phone in all_phone_numbers:
            if phone.status_cd == "valid_number" and phone.sanitized_number:
                best_phone = phone.sanitized_number
                break

        if not best_phone and all_phone_numbers:
            best_phone = all_phone_numbers[0].sanitized_number

        logger.info(f"Apollo reveal: person_ids={apollo_person_ids}, "
              f"phones={len(all_phone_numbers)}, best_phone={best_phone}, "
              f"credits_consumed={payload.credits_consumed}")

        # Queue the update task in background
        background_tasks.add_task(
            store_apollo_phone_data,
            apollo_person_ids=apollo_person_ids,
            phone_numbers=all_phone_numbers,
            best_phone=best_phone,
            credits_consumed=payload.credits_consumed
        )

        return JSONResponse({
            "status": "received",
            "message": "Phone data queued for processing",
            "apollo_person_ids": apollo_person_ids,
            "phones_received": len(all_phone_numbers),
            "credits_consumed": payload.credits_consumed
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling Apollo webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


async def store_apollo_phone_data(
    apollo_person_ids: List[str],
    phone_numbers: List[ApolloPhoneNumber],
    best_phone: Optional[str],
    credits_consumed: int
):
    """
    Store Apollo phone reveal data.
    Since webhook doesn't include email, we store by apollo_person_id
    and reconcile later.
    """
    try:
        from supabase import create_client

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            logger.error("Supabase credentials not configured")
            return

        supabase = create_client(supabase_url, supabase_key)

        # Prepare phone data for storage
        all_phones = [
            {
                "raw": p.raw_number,
                "sanitized": p.sanitized_number,
                "type": p.type_cd,
                "status": p.status_cd,
                "confidence": p.confidence_cd
            }
            for p in phone_numbers
        ]

        logger.info(f"Storing Apollo phone data: person_ids={apollo_person_ids}, phones={len(phone_numbers)}")
        logger.debug(f"Phone numbers: {[p['sanitized'] for p in all_phones]}")

        # Try to find contact by apollo_person_id in our recent enrichments
        # For now, we'll store in fact_enrichments with the apollo data
        for person_id in apollo_person_ids:
            try:
                # Log to fact_enrichments - store apollo_person_id in error_message field for now
                # (until we add proper column)
                supabase.table("fact_enrichments").insert({
                    "method": "apollo_phone_reveal",
                    "contacts_found": len(phone_numbers),
                    "success": True,
                    "error_message": json.dumps({
                        "apollo_person_id": person_id,
                        "best_phone": best_phone,
                        "all_phones": all_phones,
                        "credits_consumed": credits_consumed
                    }),
                    "enriched_at": datetime.now(timezone.utc).isoformat()
                }).execute()
                logger.info(f"Stored phone data for apollo_person_id={person_id}")
            except Exception as e:
                logger.error(f"Failed to store enrichment for {person_id}: {e}")

        # Summary
        logger.info(f"Stored {len(phone_numbers)} phone numbers from Apollo (credits: {credits_consumed})")

    except Exception as e:
        logger.error(f"Failed to store Apollo phone data: {e}")


# ========== Health Check ==========

@router.get("/health")
async def apollo_webhook_health():
    """Check Apollo webhook configuration status."""
    webhook_base = os.getenv("APOLLO_WEBHOOK_BASE_URL")
    api_key_set = bool(os.getenv("APOLLO_API_KEY"))

    return {
        "status": "healthy",
        "webhook_base_url": webhook_base or "NOT_CONFIGURED",
        "full_webhook_url": f"{webhook_base}/api/v1/webhooks/apollo/phone-reveal" if webhook_base else "N/A",
        "api_key_configured": api_key_set
    }
