"""
Pipeline Testing API Endpoints
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.schemas.pipeline import (
    PipelineTestRequest,
    PipelineTestResponse,
    CSVLeadImportRequest
)
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.csv_lead_importer import LeadCSVImporter
from app.models.database import get_db
from app.models.pipeline_models import PipelineTestExecution

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads", tags=["Pipeline Testing"])


async def save_pipeline_execution(
    response: PipelineTestResponse,
    request: PipelineTestRequest,
    db: Session
) -> PipelineTestExecution:
    """
    Save pipeline execution results to database for tracking.

    Args:
        response: Pipeline execution response with metrics
        request: Original request with options
        db: Database session

    Returns:
        Saved PipelineTestExecution record
    """
    execution = PipelineTestExecution(
        lead_name=response.lead_name,
        lead_email=request.lead.get("email"),
        lead_phone=request.lead.get("phone"),
        csv_index=None,  # Can be set by CSV import endpoint

        success=response.success,
        error_stage=response.error_stage,
        error_message=response.error_message,

        total_latency_ms=response.total_latency_ms,
        total_cost_usd=response.total_cost_usd,
        stages_json={
            stage_name: {
                "status": stage.status,
                "latency_ms": stage.latency_ms,
                "cost_usd": stage.cost_usd,
                "confidence": stage.confidence,
                "error": stage.error
            }
            for stage_name, stage in response.stages.items()
        },

        stop_on_duplicate=request.options.stop_on_duplicate,
        skip_enrichment=request.options.skip_enrichment,
        create_in_crm=request.options.create_in_crm,
        dry_run=request.options.dry_run
    )

    db.add(execution)
    db.commit()
    db.refresh(execution)

    logger.info(
        f"Saved pipeline execution {execution.id} for lead '{response.lead_name}' "
        f"(success={response.success}, latency={response.total_latency_ms}ms)"
    )

    return execution


@router.post("/test-pipeline", response_model=PipelineTestResponse, status_code=200)
async def test_pipeline(
    request: PipelineTestRequest,
    db: Session = Depends(get_db)
) -> PipelineTestResponse:
    """
    Test lead through complete pipeline with performance tracking.

    **Pipeline Stages**:
    1. Qualification - Lead scoring and tier classification
    2. Enrichment - Company data enhancement (skippable)
    3. Deduplication - Check for existing leads
    4. Close CRM - Create lead in CRM (conditional)

    **Options**:
    - `stop_on_duplicate`: Halt if duplicate detected (default: True)
    - `skip_enrichment`: Skip enrichment stage (default: False)
    - `create_in_crm`: Actually create in CRM (default: True)
    - `dry_run`: Test without CRM writes (default: False)

    **Returns**: Complete pipeline results with per-stage metrics
    """
    try:
        orchestrator = PipelineOrchestrator()
        response = await orchestrator.execute(request)

        # Save execution to database
        await save_pipeline_execution(response, request, db)

        return response

    except Exception as e:
        logger.exception(f"Pipeline test failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline execution failed: {str(e)}"
        )


@router.post("/test-pipeline/csv", response_model=PipelineTestResponse, status_code=200)
async def test_pipeline_with_csv(
    request: CSVLeadImportRequest,
    db: Session = Depends(get_db)
) -> PipelineTestResponse:
    """
    Test lead from CSV file through pipeline.

    Loads lead by index from CSV file (dealer-scraper dataset with 200 leads).

    **CSV Format Expected**:
    - name, phone, domain, website, email, ICP_Score, OEMs_Certified, city, state

    **Lead Index**: 0-199 (200 leads in dealer-scraper dataset)

    **Returns**: Complete pipeline results with per-stage metrics
    """
    try:
        # Load lead from CSV
        importer = LeadCSVImporter(csv_path=request.csv_path)
        lead_data = importer.get_lead(request.lead_index)

        logger.info(
            f"Loaded lead '{lead_data.get('name')}' from CSV at index {request.lead_index}"
        )

        # Execute pipeline
        pipeline_request = PipelineTestRequest(
            lead=lead_data,
            options=request.options
        )

        orchestrator = PipelineOrchestrator()
        response = await orchestrator.execute(pipeline_request)

        # Save execution with CSV index
        execution = await save_pipeline_execution(response, pipeline_request, db)
        execution.csv_index = request.lead_index
        db.commit()

        return response

    except IndexError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lead index {request.lead_index}: {str(e)}"
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"CSV file not found: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"CSV pipeline test failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline execution failed: {str(e)}"
        )


@router.get("/test-pipeline/quick", response_model=PipelineTestResponse, status_code=200)
async def quick_pipeline_test(db: Session = Depends(get_db)) -> PipelineTestResponse:
    """
    Quick pipeline test with hardcoded lead for development/debugging.

    Uses "A & A GENPRO INC." as test lead (first lead from dealer-scraper dataset).

    **Options**: dry_run=True, create_in_crm=False for safety

    **Returns**: Complete pipeline results with per-stage metrics
    """
    try:
        # Hardcoded test lead (from dealer-scraper CSV)
        test_lead = {
            "name": "A & A GENPRO INC.",
            "email": "contact@aagenpro.com",
            "phone": "(713) 830-3280",
            "website": "https://www.aagenpro.com/",
            "domain": "aagenpro.com",
            "icp_score": 72.8,
            "oem_certifications": ["Generac", "Cummins"],
            "city": "Houston",
            "state": "TX"
        }

        request = PipelineTestRequest(
            lead=test_lead,
            options={
                "stop_on_duplicate": False,
                "skip_enrichment": False,
                "create_in_crm": False,
                "dry_run": True
            }
        )

        orchestrator = PipelineOrchestrator()
        response = await orchestrator.execute(request)

        # Save execution
        await save_pipeline_execution(response, request, db)

        logger.info(f"Quick test completed: {response.success}, {response.total_latency_ms}ms")

        return response

    except Exception as e:
        logger.exception(f"Quick pipeline test failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Quick test failed: {str(e)}"
        )
