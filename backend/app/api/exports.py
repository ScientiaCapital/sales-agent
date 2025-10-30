"""
Export API Endpoints

Provides endpoints for exporting analytics reports in various formats (CSV, PDF, Excel).
Integrates with QueryBuilder, PDFExporter, and ExcelExporter services.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime
import csv
import io
import logging

from app.models.database import get_db
from app.models.report_template import ReportTemplate
from app.services.analytics.query_builder import QueryBuilder, QueryValidationError
from app.services.exports.pdf_exporter import PDFExporter
from app.services.exports.excel_exporter import ExcelExporter


router = APIRouter(prefix="/exports", tags=["Exports"])
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Schemas
# ============================================================================

class ExportRequest(BaseModel):
    """Schema for export request"""
    template_id: Optional[str] = None
    query_config: Optional[dict] = None
    format: str = Field(..., pattern="^(csv|pdf|xlsx)$")
    title: Optional[str] = "Analytics Report"
    include_summary: bool = True


class ExportResponse(BaseModel):
    """Schema for export response (for async exports)"""
    export_id: str
    status: str
    download_url: Optional[str] = None
    created_at: datetime


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/report",
    summary="Export a report in specified format",
    description="Export analytics data as CSV, PDF, or Excel file"
)
async def export_report(
    request: ExportRequest,
    db: Session = Depends(get_db)
):
    """
    Export a report in the specified format.

    Supports three sources:
    1. Template ID - Use existing template
    2. Query Config - Custom query configuration
    3. Both - Template with query overrides

    Returns a streaming response with the file download.
    """
    # Determine data source
    if request.template_id:
        # Load template
        template = db.query(ReportTemplate).filter(
            ReportTemplate.template_id == request.template_id
        ).first()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template not found: {request.template_id}"
            )

        query_config = template.query_config.copy()
        title = request.title or template.name

        # Apply query overrides if provided
        if request.query_config:
            query_config.update(request.query_config)

        # Increment usage count
        template.usage_count += 1
        db.commit()

    elif request.query_config:
        query_config = request.query_config
        title = request.title
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either template_id or query_config"
        )

    # Execute query
    try:
        query_builder = QueryBuilder(db)
        result = query_builder.build_and_execute(query_config)

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No data found for the specified query"
            )

    except QueryValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query validation failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {str(e)}"
        )

    # Generate export based on format
    try:
        if request.format == "csv":
            return _export_csv(result.data, result.columns, title)
        elif request.format == "pdf":
            return _export_pdf(result.data, result.columns, title)
        elif request.format == "xlsx":
            return _export_excel(result.data, result.columns, title, request.include_summary)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported format: {request.format}"
            )

    except Exception as e:
        logger.error(f"Export generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export generation failed: {str(e)}"
        )


@router.post(
    "/template/{template_id}",
    summary="Export from template",
    description="Quick export using an existing report template"
)
async def export_from_template(
    template_id: str,
    format: str = Field(..., pattern="^(csv|pdf|xlsx)$"),
    db: Session = Depends(get_db)
):
    """
    Export a report using an existing template.

    Simplified endpoint that only requires template_id and format.
    """
    request = ExportRequest(
        template_id=template_id,
        format=format,
        include_summary=True
    )

    return await export_report(request, db)


# ============================================================================
# Helper Functions for Export Generation
# ============================================================================

def _export_csv(data: list, columns: list, title: str) -> StreamingResponse:
    """Generate CSV export as streaming response"""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)

    # Write header
    writer.writeheader()

    # Write data rows
    for row in data:
        # Filter row to only include requested columns
        filtered_row = {col: row.get(col, '') for col in columns}
        writer.writerow(filtered_row)

    # Convert to bytes
    output.seek(0)
    response = StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv"
    )

    # Set filename
    filename = f"{title.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"

    return response


def _export_pdf(data: list, columns: list, title: str) -> StreamingResponse:
    """Generate PDF export as streaming response"""
    exporter = PDFExporter(title=title, orientation="landscape")

    subtitle = f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    buffer = exporter.export_data_table(data, columns, subtitle=subtitle)

    response = StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/pdf"
    )

    filename = f"{title.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"

    return response


def _export_excel(data: list, columns: list, title: str, include_summary: bool = True) -> StreamingResponse:
    """Generate Excel export as streaming response"""
    exporter = ExcelExporter(title=title)

    # Add summary sheet if requested
    if include_summary:
        exporter.add_summary_sheet({
            "Report Title": title,
            "Generated": datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
            "Total Records": len(data),
            "Columns": len(columns)
        })

    # Add data sheet
    exporter.add_data_sheet(
        sheet_name="Data",
        data=data,
        columns=columns,
        add_table=True,
        add_summary_row=True,
        freeze_header=True
    )

    buffer = exporter.export()

    response = StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    filename = f"{title.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"

    return response


@router.get(
    "/formats",
    summary="Get supported export formats",
    description="List all supported export formats with their capabilities"
)
async def get_supported_formats():
    """
    Get information about supported export formats.
    """
    return {
        "formats": [
            {
                "format": "csv",
                "mime_type": "text/csv",
                "extension": ".csv",
                "supports_charts": False,
                "supports_formatting": False,
                "best_for": "Simple data exports, spreadsheet import"
            },
            {
                "format": "pdf",
                "mime_type": "application/pdf",
                "extension": ".pdf",
                "supports_charts": False,  # TODO: Add chart support
                "supports_formatting": True,
                "best_for": "Professional reports, presentations, archival"
            },
            {
                "format": "xlsx",
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "extension": ".xlsx",
                "supports_charts": True,
                "supports_formatting": True,
                "best_for": "Complex analysis, pivot tables, formulas"
            }
        ]
    }
