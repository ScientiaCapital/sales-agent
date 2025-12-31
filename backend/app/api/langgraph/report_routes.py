"""Morning Report API routes - Daily report generation endpoints."""

import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException

from app.api.langgraph.schemas import ReportRunRequest, ReportRunResponse
from app.auth.dependencies import get_current_user
from app.core.logging import setup_logging

logger = setup_logging(__name__)
router = APIRouter(prefix="/report", tags=["langgraph-report"])


@router.post("/generate", response_model=ReportRunResponse, status_code=200)
async def generate_morning_report(
    request: ReportRunRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate morning report with overnight scout results and outreach drafts."""
    try:
        if request.async_mode:
            from app.tasks.agent_tasks import generate_morning_report_task
            task = generate_morning_report_task.delay(
                hours_back=request.hours_back,
                top_n=request.top_n,
                save_to_file=request.save_to_file
            )
            logger.info(f"Morning Report task queued: {task.id}")
            return ReportRunResponse(status="queued", task_id=task.id)
        else:
            from app.services.langgraph.agents.morning_report_agent import MorningReportAgent
            agent = MorningReportAgent(provider='cerebras')
            report = await agent.generate_report(hours_back=request.hours_back, top_n=request.top_n)

            file_path = None
            if request.save_to_file:
                file_path = await agent.save_report_to_file(report)

            logger.info(f"Morning Report generated: {report.total_scouted} leads, {report.hot_leads} HOT")
            return ReportRunResponse(
                status="success",
                generated_at=report.generated_at,
                report_date=report.report_date,
                total_scouted=report.total_scouted,
                hot_leads=report.hot_leads,
                warm_leads=report.warm_leads,
                cold_leads=report.cold_leads,
                top_leads_count=len(report.top_leads),
                signals_summary=report.signals_summary,
                summary=report.summary,
                file_path=file_path
            )
    except Exception as e:
        logger.error(f"Error generating Morning Report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Morning Report failed: {str(e)}")


@router.get("/latest", status_code=200)
async def get_latest_report(current_user: dict = Depends(get_current_user)):
    """Get the most recent morning report file."""
    try:
        reports_dir = Path("data/reports")
        if not reports_dir.exists():
            return {"status": "no_reports", "message": "No reports directory found. Run /report/generate first."}

        reports = sorted(reports_dir.glob("morning_report_*.md"), reverse=True)
        if not reports:
            return {"status": "no_reports", "message": "No morning reports found. Run /report/generate first."}

        latest = reports[0]
        content = latest.read_text()
        return {"status": "success", "file_name": latest.name, "file_path": str(latest), "content": content}
    except Exception as e:
        logger.error(f"Error getting latest report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get latest report: {str(e)}")
