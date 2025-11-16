"""
CSV Import API Endpoints

Handles file upload, background processing, and status tracking for CSV lead imports.
"""
import logging
import asyncio
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.csv_import import CSVImport
from app.schemas.csv_import import (
    CSVUploadResponse,
    CSVImportStatus,
    CSVProcessingOptions
)
from app.services.csv_manager import CSVManager
from app.core.exceptions import (
    InvalidFileFormatError,
    FileSizeExceededError,
    InvalidInputError
)
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/leads", tags=["CSV Import"])


@router.post("/import/csv", response_model=CSVUploadResponse, status_code=202)
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file with lead data"),
    db: Session = Depends(get_db)
) -> CSVUploadResponse:
    """
    Upload CSV file for lead enrichment processing.

    **Workflow**:
    1. Validate file format and size (max 10 MB)
    2. Save to inbox directory
    3. Create database tracking record
    4. Start background processing
    5. Return import ID for status polling

    **CSV Format**:
    Required columns (case-insensitive):
    - `company_name` - Company name
    - `industry` - Industry vertical
    - `website` - Company website URL

    Optional columns:
    - `email` - Contact email
    - `phone` - Contact phone
    - `contact_name` - Contact person name
    - `company_size` - Employee count or range

    **Processing**:
    Each lead goes through 4-stage pipeline:
    1. Qualification - AI scoring with Cerebras
    2. Enrichment - Apollo.io + LinkedIn data
    3. Deduplication - Check for existing leads
    4. Close CRM - Create lead in CRM

    **Example**:
    ```bash
    curl -X POST http://localhost:8001/api/v1/leads/import/csv \\
      -F "file=@my_leads.csv"
    ```

    Returns:
        CSVUploadResponse with import_id for status tracking
    """
    # Validate file type
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only .csv files are accepted."
        )

    try:
        # Read file content
        file_content = await file.read()

        # Initialize CSV manager
        csv_manager = CSVManager(db)

        # Upload and validate CSV
        import_record = await csv_manager.upload_csv(
            file_content=file_content,
            filename=file.filename,
            max_size_mb=10.0  # 10 MB limit
        )

        logger.info(
            f"CSV uploaded: import_id={import_record.id}, "
            f"filename={import_record.filename}, "
            f"rows={import_record.total_rows}"
        )

        # Start background processing
        background_tasks.add_task(
            process_csv_import,
            import_id=import_record.id,
            db=db
        )

        return CSVUploadResponse(
            import_id=import_record.id,
            filename=import_record.filename,
            status="processing",
            total_rows=import_record.total_rows,
            message=f"CSV uploaded successfully. Processing {import_record.total_rows} leads in background."
        )

    except InvalidFileFormatError as e:
        logger.error(f"Invalid CSV format: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except FileSizeExceededError as e:
        logger.error(f"File too large: {e}")
        raise HTTPException(status_code=413, detail=str(e))

    except Exception as e:
        logger.error(f"CSV upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload CSV: {str(e)}"
        )


@router.get("/import/{import_id}/status", response_model=CSVImportStatus)
async def get_import_status(
    import_id: int,
    db: Session = Depends(get_db)
) -> CSVImportStatus:
    """
    Get current status of CSV import processing.

    **Poll this endpoint** to track progress:
    ```bash
    # Check status every 5 seconds
    while true; do
      curl http://localhost:8001/api/v1/leads/import/123/status
      sleep 5
    done
    ```

    **Status Values**:
    - `uploaded` - File received, waiting to process
    - `processing` - Currently enriching leads
    - `completed` - All leads processed successfully
    - `failed` - Processing failed with error
    - `archived` - Moved to archive after retention period

    Args:
        import_id: CSV import record ID

    Returns:
        CSVImportStatus with progress metrics
    """
    csv_manager = CSVManager(db)
    import_record = csv_manager.get_import_by_id(import_id)

    if not import_record:
        raise HTTPException(
            status_code=404,
            detail=f"CSV import {import_id} not found"
        )

    # Calculate progress percentage
    progress_percent = 0.0
    if import_record.total_rows > 0:
        progress_percent = (
            (import_record.processed_rows + import_record.failed_rows) /
            import_record.total_rows
        ) * 100

    return CSVImportStatus(
        import_id=import_record.id,
        filename=import_record.filename,
        status=import_record.status,
        total_rows=import_record.total_rows,
        processed_rows=import_record.processed_rows,
        failed_rows=import_record.failed_rows,
        progress_percent=round(progress_percent, 1),
        total_cost_usd=float(import_record.total_cost_usd),
        uploaded_at=import_record.uploaded_at,
        started_processing_at=import_record.started_processing_at,
        completed_at=import_record.completed_at,
        error_message=import_record.error_message
    )


# ============================================================================
# BACKGROUND PROCESSING
# ============================================================================

async def process_csv_import(import_id: int, db: Session):
    """
    Background task to process CSV file through pipeline.

    Reads CSV rows sequentially and processes each lead through:
    1. Qualification
    2. Enrichment
    3. Deduplication
    4. Close CRM

    Updates database progress after each row.

    Args:
        import_id: CSV import record ID
        db: Database session
    """
    from app.services.csv_lead_importer import LeadCSVImporter
    from app.services.pipeline_orchestrator import PipelineOrchestrator
    from app.schemas.pipeline import PipelineTestRequest, PipelineTestOptions

    csv_manager = CSVManager(db)

    try:
        # Move CSV from inbox to processing
        import_record = await csv_manager.start_processing(import_id)

        logger.info(
            f"Starting CSV processing: import_id={import_id}, "
            f"file={import_record.file_path}, "
            f"rows={import_record.total_rows}"
        )

        # Load CSV file
        csv_importer = LeadCSVImporter(import_record.file_path)

        # Initialize pipeline orchestrator
        pipeline = PipelineOrchestrator(db=db)

        # Process each lead
        processed_count = 0
        failed_count = 0
        total_cost = 0.0

        for row_index in range(csv_importer.get_lead_count()):
            try:
                # Get lead from CSV
                lead_data = csv_importer.get_lead(row_index)

                # Create pipeline request
                request = PipelineTestRequest(
                    lead=lead_data,
                    options=PipelineTestOptions(
                        stop_on_duplicate=False,  # Don't stop on duplicates in bulk import
                        skip_enrichment=False,
                        create_in_crm=True,
                        dry_run=False
                    )
                )

                # Execute pipeline
                result = await pipeline.execute(request)

                if result.success:
                    processed_count += 1
                    total_cost += result.total_cost_usd
                    logger.info(
                        f"Lead {row_index + 1}/{csv_importer.get_lead_count()} processed: "
                        f"{lead_data.get('name', 'Unknown')} "
                        f"(${result.total_cost_usd:.4f})"
                    )
                else:
                    failed_count += 1
                    logger.warning(
                        f"Lead {row_index + 1}/{csv_importer.get_lead_count()} failed: "
                        f"{lead_data.get('name', 'Unknown')} - "
                        f"{result.error_message}"
                    )

                # Update progress in database every 10 rows
                if (row_index + 1) % 10 == 0:
                    import_record.processed_rows = processed_count
                    import_record.failed_rows = failed_count
                    import_record.total_cost_usd = total_cost
                    db.commit()

            except Exception as e:
                failed_count += 1
                logger.error(
                    f"Failed to process row {row_index}: {e}",
                    exc_info=True
                )

        # Complete processing
        await csv_manager.complete_processing(
            import_id=import_id,
            processed_rows=processed_count,
            failed_rows=failed_count,
            total_cost=total_cost
        )

        logger.info(
            f"CSV processing completed: import_id={import_id}, "
            f"processed={processed_count}, "
            f"failed={failed_count}, "
            f"cost=${total_cost:.4f}"
        )

    except Exception as e:
        logger.error(
            f"CSV processing failed: import_id={import_id}, error={e}",
            exc_info=True
        )

        # Mark as failed
        await csv_manager.fail_processing(
            import_id=import_id,
            error_message=str(e)
        )
