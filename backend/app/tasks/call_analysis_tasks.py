"""
Celery tasks for call analysis and intelligence extraction.

Runs async after calls complete to:
- Transcribe recordings via AssemblyAI
- Extract sentiment, objections, buying signals
- Calculate call quality scores
- Persist insights for dashboard and automation
"""
import asyncio
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.core.logging import setup_logging
from app.models.database import async_session_maker

logger = setup_logging(__name__)


@celery_app.task(
    name="analyze_call_recording",
    bind=True,
    max_retries=2,
    soft_time_limit=300,  # 5 minutes max per call
    time_limit=360,  # Hard limit 6 minutes
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
)
def analyze_call_recording(
    self,
    voice_session_id: str,
    audio_url: str,
    lead_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze a completed call recording.

    Args:
        voice_session_id: Voice session ID from voice_session_logs
        audio_url: URL to the call recording
        lead_id: Optional lead ID for linking

    Returns:
        Analysis result summary
    """
    logger.info(f"Starting call analysis for session {voice_session_id}")

    try:
        result = asyncio.get_event_loop().run_until_complete(
            _analyze_call_async(voice_session_id, audio_url, lead_id)
        )
        return result
    except SoftTimeLimitExceeded:
        logger.warning(f"Call analysis timed out for {voice_session_id}")
        return {
            "success": False,
            "error": "Analysis timed out",
            "voice_session_id": voice_session_id,
        }
    except Exception as e:
        logger.error(f"Call analysis failed for {voice_session_id}: {e}")
        raise


async def _analyze_call_async(
    voice_session_id: str,
    audio_url: str,
    lead_id: Optional[str],
) -> Dict[str, Any]:
    """Async implementation of call analysis."""
    from app.services.intelligence import CallInsightsService

    async with async_session_maker() as db:
        service = CallInsightsService(db)

        lead_uuid = UUID(lead_id) if lead_id else None

        insight = await service.analyze_call(
            voice_session_id=voice_session_id,
            audio_url=audio_url,
            lead_id=lead_uuid,
        )

        if insight:
            logger.info(
                f"Analysis complete for {voice_session_id}: "
                f"sentiment={insight.sentiment_label}, outcome={insight.outcome}, "
                f"score={insight.call_score}"
            )
            return {
                "success": True,
                "voice_session_id": voice_session_id,
                "insight_id": str(insight.id),
                "sentiment": insight.sentiment_label,
                "outcome": insight.outcome,
                "call_score": insight.call_score,
                "objection_count": insight.objection_count,
                "buying_signal_count": insight.buying_signal_count,
            }
        else:
            return {
                "success": False,
                "error": "Analysis returned no results",
                "voice_session_id": voice_session_id,
            }


@celery_app.task(
    name="reanalyze_call",
    bind=True,
    max_retries=1,
)
def reanalyze_call(
    self,
    insight_id: str,
    audio_url: str,
) -> Dict[str, Any]:
    """
    Re-analyze a call with updated analyzer.

    Useful when analyzer is updated and we want to refresh insights.
    """
    logger.info(f"Re-analyzing call insight {insight_id}")

    try:
        result = asyncio.get_event_loop().run_until_complete(
            _reanalyze_call_async(insight_id, audio_url)
        )
        return result
    except Exception as e:
        logger.error(f"Re-analysis failed for {insight_id}: {e}")
        raise


async def _reanalyze_call_async(
    insight_id: str,
    audio_url: str,
) -> Dict[str, Any]:
    """Async implementation of re-analysis."""
    from app.services.intelligence import CallInsightsService
    from app.models.call_insight import CallInsight

    async with async_session_maker() as db:
        service = CallInsightsService(db)

        # Get existing insight
        insight = await service.get_insight_by_id(UUID(insight_id))
        if not insight:
            return {
                "success": False,
                "error": "Insight not found",
                "insight_id": insight_id,
            }

        # Re-run analysis
        new_insight = await service.analyze_call(
            voice_session_id=insight.voice_session_id,
            audio_url=audio_url,
            lead_id=insight.lead_id,
        )

        if new_insight:
            return {
                "success": True,
                "insight_id": str(new_insight.id),
                "sentiment": new_insight.sentiment_label,
                "outcome": new_insight.outcome,
                "call_score": new_insight.call_score,
            }
        else:
            return {
                "success": False,
                "error": "Re-analysis returned no results",
                "insight_id": insight_id,
            }


@celery_app.task(
    name="batch_analyze_calls",
    bind=True,
    max_retries=1,
    soft_time_limit=1800,  # 30 minutes for batch
    time_limit=1860,
)
def batch_analyze_calls(
    self,
    call_records: list,
) -> Dict[str, Any]:
    """
    Batch analyze multiple calls.

    Args:
        call_records: List of dicts with voice_session_id, audio_url, lead_id

    Returns:
        Batch results summary
    """
    logger.info(f"Starting batch analysis for {len(call_records)} calls")

    results = {
        "total": len(call_records),
        "success": 0,
        "failed": 0,
        "results": [],
    }

    for record in call_records:
        try:
            result = asyncio.get_event_loop().run_until_complete(
                _analyze_call_async(
                    record["voice_session_id"],
                    record["audio_url"],
                    record.get("lead_id"),
                )
            )
            if result.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1
            results["results"].append(result)
        except Exception as e:
            results["failed"] += 1
            results["results"].append({
                "success": False,
                "error": str(e),
                "voice_session_id": record.get("voice_session_id"),
            })

    logger.info(
        f"Batch analysis complete: {results['success']}/{results['total']} successful"
    )
    return results
