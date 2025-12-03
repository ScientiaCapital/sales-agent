"""
Dry Run Pipeline Testing - Shows what WOULD happen without touching Close CRM

This endpoint is for TESTING ONLY. It shows:
1. Deduplication recommendations
2. What action would be taken (create_new, add_contact_to_existing, skip, update)
3. Discovered ATL contacts from Hunter.io
4. Close CRM status changes
5. Smart view assignment

NO LEADS ARE CREATED - This is 100% read-only testing.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from app.models.database import get_db
from app.schemas.pipeline import PipelineTestRequest
from app.services.pipeline_orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads/dry-run", tags=["Pipeline Dry Run Testing"])


@router.post("/test", response_model=Dict[str, Any])
async def dry_run_test(
    request: PipelineTestRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    DRY RUN ONLY - Shows what WOULD happen without creating leads in Close CRM.

    **This endpoint:**
    - ✅ Runs qualification (Cerebras AI scoring)
    - ✅ Discovers ATL contacts via Hunter.io
    - ✅ Checks Close CRM for duplicates
    - ✅ Shows deduplication recommendation
    - ❌ Does NOT create/update any leads in Close CRM

    **Perfect for testing deduplication logic!**

    **Returns:**
    ```json
    {
      "company_name": "Generator Supercenter",
      "qualification_score": 58,
      "discovered_contacts": 7,
      "close_crm_check": {
        "company_exists": true/false,
        "recommendation": "create_new | add_contact_to_existing | skip_duplicate | update_existing_contact",
        "matched_lead_id": "lead_xxx...",
        "existing_contacts": 2,
        "atl_contacts": 1
      },
      "what_would_happen": {
        "action": "Would add 7 new contacts to existing lead_xxx",
        "smart_view": "⭐ Validated ATL Leads",
        "contacts_created": 7,
        "duplicate_prevented": true
      },
      "discovered_contacts": [
        {
          "name": "John Smith",
          "email": "john@company.com",
          "position": "CEO",
          "is_atl": true,
          "phone": "(555) 123-4567"
        }
      ]
    }
    ```
    """
    try:
        # Force dry_run mode
        request.options.dry_run = True
        request.options.create_in_crm = False  # Extra safety

        logger.info(f"🧪 DRY RUN TEST: {request.lead.get('name', 'Unknown')}")

        # Run pipeline
        orchestrator = PipelineOrchestrator(db=db)
        response = await orchestrator.execute(request)

        # Extract key information for user-friendly display
        lead_name = request.lead.get("name") or request.lead.get("company", "Unknown")

        # Qualification results
        qual_stage = response.stages.get("qualification", {})
        qual_output = qual_stage.output if qual_stage else {}
        qualification_score = qual_output.get("qualification_score", 0) if qual_output else 0
        discovered_contacts = qual_output.get("metadata", {}).get("discovered_contacts", []) if qual_output else []

        # Close CRM check results
        crm_check_stage = response.stages.get("crm_check", {})
        crm_check_output = crm_check_stage.output if crm_check_stage else {}

        # Deduplication results
        dedup_stage = response.stages.get("deduplication", {})
        dedup_output = dedup_stage.output if dedup_stage else {}
        recommendation = dedup_output.get("recommendation", "create_new") if dedup_output else "create_new"

        # Determine what WOULD happen
        company_exists = crm_check_output.get("company_exists", False) if crm_check_output else False
        matched_lead_id = crm_check_output.get("lead_id") or dedup_output.get("matched_lead_id")
        existing_contact_count = len(crm_check_output.get("existing_contacts", [])) if crm_check_output else 0
        atl_count_in_crm = len(crm_check_output.get("atl_contacts", [])) if crm_check_output else 0

        # Determine smart view assignment
        is_atl = discovered_contacts[0].get("is_atl", False) if discovered_contacts else False
        if is_atl:
            if qualification_score >= 70:
                smart_view = "🔥 Hot ATL Leads (Priority)"
                status = "Hot ATL"
            else:
                smart_view = "⭐ Validated ATL Leads"
                status = "Validated ATL"
        else:
            smart_view = "📋 BTL Leads (Lower Priority)"
            status = "BTL"

        # Build "What Would Happen" explanation
        what_would_happen = {}

        if recommendation == "create_new":
            what_would_happen = {
                "action": f"Would CREATE new lead '{lead_name}' with {len(discovered_contacts)} contacts",
                "smart_view": smart_view,
                "status": status,
                "contacts_created": len(discovered_contacts),
                "duplicate_prevented": False,
                "explanation": "Company does not exist in Close CRM (or match confidence < 85%)"
            }
        elif recommendation == "add_contact_to_existing":
            new_contacts = len(discovered_contacts)
            what_would_happen = {
                "action": f"Would ADD {new_contacts} new contacts to EXISTING lead {matched_lead_id}",
                "smart_view": smart_view,
                "status": status,
                "existing_lead_id": matched_lead_id,
                "existing_contacts": existing_contact_count,
                "new_contacts": new_contacts,
                "total_after": existing_contact_count + new_contacts,
                "duplicate_prevented": True,
                "explanation": f"Company exists with {existing_contact_count} contacts. These {new_contacts} contacts are NEW."
            }
        elif recommendation == "skip_duplicate":
            what_would_happen = {
                "action": "Would SKIP (contact already exists with same data)",
                "smart_view": "N/A - Contact already exists",
                "status": "No change",
                "duplicate_prevented": True,
                "explanation": "Contact email already exists in Close CRM with identical data"
            }
        elif recommendation == "update_existing_contact":
            what_would_happen = {
                "action": f"Would UPDATE existing contact in lead {matched_lead_id} with new data",
                "smart_view": smart_view,
                "status": "No change (contact updated)",
                "existing_lead_id": matched_lead_id,
                "fields_updated": ["phone", "linkedin_url", "department"],
                "duplicate_prevented": True,
                "explanation": "Contact exists but we have newer/more complete data"
            }

        # Build final response
        return {
            "dry_run": True,
            "company_name": lead_name,
            "qualification_score": qualification_score,
            "discovered_contacts_count": len(discovered_contacts),
            "close_crm_check": {
                "company_exists": company_exists,
                "recommendation": recommendation,
                "matched_lead_id": matched_lead_id,
                "existing_contacts": existing_contact_count,
                "existing_atl_contacts": atl_count_in_crm,
                "company_match_confidence": dedup_output.get("company_confidence", 0.0) if dedup_output else 0.0
            },
            "what_would_happen": what_would_happen,
            "discovered_contacts": [
                {
                    "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                    "email": c.get("email"),
                    "position": c.get("position"),
                    "is_atl": c.get("is_atl", False),
                    "phone": c.get("phone"),
                    "linkedin": c.get("linkedin")
                }
                for c in discovered_contacts
            ],
            "pipeline_stages": {
                "qualification": {
                    "status": qual_stage.status if qual_stage else "unknown",
                    "latency_ms": qual_stage.latency_ms if qual_stage else 0
                },
                "crm_check": {
                    "status": crm_check_stage.status if crm_check_stage else "unknown",
                    "latency_ms": crm_check_stage.latency_ms if crm_check_stage else 0
                },
                "deduplication": {
                    "status": dedup_stage.status if dedup_stage else "unknown",
                    "latency_ms": dedup_stage.latency_ms if dedup_stage else 0
                }
            },
            "total_latency_ms": response.total_latency_ms,
            "total_cost_usd": response.total_cost_usd
        }

    except Exception as e:
        logger.exception(f"Dry run test failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Dry run test failed: {str(e)}"
        )


@router.post("/batch-test", response_model=List[Dict[str, Any]])
async def dry_run_batch_test(
    csv_path: str,
    limit: int = 5,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Test multiple leads from CSV with dry_run.

    Perfect for testing deduplication across many leads.

    Args:
        csv_path: Path to CSV file (relative to project root)
        limit: Number of leads to test (default: 5, max: 20)

    Returns:
        List of dry run results showing what would happen for each lead
    """
    try:
        from app.services.csv_lead_importer import LeadCSVImporter

        limit = min(limit, 20)  # Cap at 20 for safety

        logger.info(f"🧪 DRY RUN BATCH TEST: Testing {limit} leads from {csv_path}")

        importer = LeadCSVImporter(csv_path=csv_path)
        results = []

        for i in range(limit):
            try:
                lead_data = importer.get_lead(i)

                request = PipelineTestRequest(
                    lead=lead_data,
                    options={
                        "stop_on_duplicate": False,
                        "skip_enrichment": False,
                        "create_in_crm": False,
                        "dry_run": True
                    }
                )

                result = await dry_run_test(request, db)
                results.append(result)

            except IndexError:
                break  # End of CSV
            except Exception as e:
                logger.error(f"Failed to test lead {i}: {e}")
                results.append({
                    "error": str(e),
                    "lead_index": i
                })

        return results

    except Exception as e:
        logger.exception(f"Batch dry run failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch dry run failed: {str(e)}"
        )
