"""
Imports Endpoint for Sales-Agent Dashboard

GET /api/imports - Returns CSV import history with field availability

Uses Supabase REST API (PostgREST) for serverless-compatible data fetching.
"""

import os
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Supabase REST API configuration (strip to handle Vercel env var newlines)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()


async def fetch_import_history(limit: int = 10) -> list | None:
    """
    Fetch import history from Supabase.

    Uses v_import_history view for import batches with progress.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("Supabase credentials not configured")
        return None

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/v_import_history",
                headers=headers,
                params={
                    "select": "*",
                    "limit": str(limit)
                }
            )

            if response.status_code != 200:
                logger.warning(f"Supabase query failed: {response.status_code}")
                return None

            rows = response.json()

            imports = []
            for row in rows:
                imports.append({
                    "id": row.get("id"),
                    "filename": row.get("filename"),
                    "imported_at": row.get("imported_at"),
                    "total_rows": row.get("total_rows", 0),
                    "fields": {
                        "company_name": row.get("has_company_name", True),
                        "phone": row.get("has_phone", False),
                        "email": row.get("has_email", False),
                        "website": row.get("has_website", False),
                        "contact_name": row.get("has_contact_name", False),
                    },
                    "source": row.get("source", "dealer-scraper-mvp"),
                    "progress": {
                        "processed": row.get("processed_count", 0),
                        "qualified": row.get("qualified_count", 0),
                        "enriched": row.get("enriched_count", 0),
                        "exported": row.get("exported_count", 0),
                        "failed": row.get("failed_count", 0),
                        "progress_pct": row.get("progress_pct", 0),
                        "qualification_rate": row.get("qualification_rate", 0),
                    }
                })

            return imports

    except Exception as e:
        logger.error(f"Supabase REST API error: {e}")
        return None


def get_mock_imports() -> list:
    """Return mock import data for development."""
    now = datetime.utcnow()

    return [
        {
            "id": "mock-1",
            "filename": "clean_leads_for_sales_agent_20251128.csv",
            "imported_at": now.isoformat(),
            "total_rows": 90,
            "fields": {
                "company_name": True,
                "phone": True,
                "email": True,
                "website": True,
                "contact_name": True,
            },
            "source": "dealer-scraper-mvp",
            "progress": {
                "processed": 90,
                "qualified": 72,
                "enriched": 65,
                "exported": 58,
                "failed": 5,
                "progress_pct": 100.0,
                "qualification_rate": 80.0,
            }
        },
        {
            "id": "mock-2",
            "filename": "top_1000_quality_leads.csv",
            "imported_at": (now.replace(day=26)).isoformat(),
            "total_rows": 1000,
            "fields": {
                "company_name": True,
                "phone": True,
                "email": False,
                "website": False,
                "contact_name": False,
            },
            "source": "dealer-scraper-mvp",
            "progress": {
                "processed": 850,
                "qualified": 680,
                "enriched": 520,
                "exported": 480,
                "failed": 45,
                "progress_pct": 85.0,
                "qualification_rate": 80.0,
            }
        },
        {
            "id": "mock-3",
            "filename": "cummins_bb_batch_001.csv",
            "imported_at": (now.replace(day=26)).isoformat(),
            "total_rows": 500,
            "fields": {
                "company_name": True,
                "phone": True,
                "email": True,
                "website": True,
                "contact_name": True,
            },
            "source": "dealer-scraper-mvp",
            "progress": {
                "processed": 500,
                "qualified": 425,
                "enriched": 400,
                "exported": 380,
                "failed": 12,
                "progress_pct": 100.0,
                "qualification_rate": 85.0,
            }
        }
    ]


@app.get("/api/imports")
async def get_imports(limit: int = 10) -> JSONResponse:
    """
    Get CSV import history with field availability and processing progress.

    Query params:
    - limit: Max number of imports to return (default 10)

    Shows what data was included in each import and pipeline progress.
    """
    # Try Supabase first
    data = await fetch_import_history(limit)

    if data is not None:
        logger.info("Using Supabase REST API import data")
        return JSONResponse(
            content={
                "imports": data,
                "total": len(data),
                "data_source": "supabase_rest",
                "updated_at": datetime.utcnow().isoformat()
            },
            headers={
                "Cache-Control": "public, max-age=300",
                "Access-Control-Allow-Origin": "*",
            }
        )

    # Fall back to mock
    logger.info("Using mock import data")
    mock = get_mock_imports()[:limit]
    return JSONResponse(
        content={
            "imports": mock,
            "total": len(mock),
            "data_source": "mock",
            "updated_at": datetime.utcnow().isoformat()
        },
        headers={
            "Cache-Control": "public, max-age=300",
            "Access-Control-Allow-Origin": "*",
        }
    )
