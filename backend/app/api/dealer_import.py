"""
Dealer Scraper Import API Endpoints

This module provides API endpoints for importing and processing data from the
dealer-scraper-mvp project, including ICP scoring, multi-OEM detection, and
tier-based lead prioritization.

Key Features:
- Import dealer scraper CSV files
- Preserve ICP scoring and tier classification
- Multi-OEM contractor detection and messaging
- SREC state priority and ITC urgency scoring
- Integration with existing sales-agent qualification and enrichment
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
import asyncio
import pandas as pd
from datetime import datetime

from app.services.dealer_scraper_importer import DealerScraperImporter
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/api/v1/dealer-import", tags=["dealer-import"])

# Global importer instance
dealer_importer: Optional[DealerScraperImporter] = None


@router.on_event("startup")
async def startup_event():
    """Initialize dealer scraper importer on startup."""
    global dealer_importer
    dealer_importer = DealerScraperImporter()
    logger.info("Dealer scraper importer initialized")


# ========== Request/Response Models ==========

class DealerImportRequest(BaseModel):
    """Request model for dealer import."""
    file_path: str = Field(..., description="Path to dealer scraper CSV file")
    batch_size: int = Field(50, description="Number of records to process per batch")
    qualification_enabled: bool = Field(True, description="Run AI qualification")
    enrichment_enabled: bool = Field(True, description="Run AI enrichment")


class DealerImportResponse(BaseModel):
    """Response model for dealer import."""
    success: bool
    total_records: int
    processed: int
    qualified: int
    enriched: int
    errors: int
    success_rate: float
    qualification_rate: float
    enrichment_rate: float
    import_timestamp: str
    source_file: str


class DealerSummaryResponse(BaseModel):
    """Response model for dealer data summary."""
    total_contractors: int
    tier_distribution: Dict[str, int]
    oem_distribution: Dict[str, int]
    state_distribution: Dict[str, int]
    capability_distribution: Dict[str, int]
    multi_oem_contractors: int
    high_priority_contractors: int
    average_icp_score: float
    top_oem_certifications: Dict[str, int]


class MultiOEMAnalysisResponse(BaseModel):
    """Response model for multi-OEM analysis."""
    total_multi_oem: int
    triple_oem_unicorns: int
    dual_oem_contractors: int
    top_oem_combinations: List[Dict[str, Any]]
    unicorn_contractors: List[Dict[str, Any]]
    top_dual_oem: List[Dict[str, Any]]


# ========== Import Endpoints ==========

@router.post("/import", response_model=DealerImportResponse)
async def import_dealer_data(
    file_path: str = Form(...),
    batch_size: int = Form(50),
    qualification_enabled: bool = Form(True),
    enrichment_enabled: bool = Form(True)
):
    """
    Import dealer scraper CSV data into the sales-agent system.
    
    Processes contractor data with:
    - ICP scoring preservation
    - Tier-based prioritization
    - Multi-OEM detection
    - AI qualification and enrichment
    """
    if not dealer_importer:
        raise HTTPException(status_code=500, detail="Dealer importer not initialized")
    
    try:
        # Import contractor data
        result = await dealer_importer.import_contractors_csv(
            file_path=file_path,
            batch_size=batch_size,
            qualification_enabled=qualification_enabled,
            enrichment_enabled=enrichment_enabled
        )
        
        return DealerImportResponse(
            success=result.get('success', True),
            total_records=result.get('total_records', 0),
            processed=result.get('processed', 0),
            qualified=result.get('qualified', 0),
            enriched=result.get('enriched', 0),
            errors=result.get('errors', 0),
            success_rate=result.get('success_rate', 0.0),
            qualification_rate=result.get('qualification_rate', 0.0),
            enrichment_rate=result.get('enrichment_rate', 0.0),
            import_timestamp=result.get('import_timestamp', datetime.now().isoformat()),
            source_file=result.get('source_file', file_path)
        )
        
    except Exception as e:
        logger.error(f"Dealer import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/upload-and-import", response_model=DealerImportResponse)
async def upload_and_import_dealer_data(
    file: UploadFile = File(...),
    batch_size: int = Form(50),
    qualification_enabled: bool = Form(True),
    enrichment_enabled: bool = Form(True)
):
    """
    Upload dealer scraper CSV file and import into the sales-agent system.
    
    Supports the same processing as /import but with file upload.
    """
    if not dealer_importer:
        raise HTTPException(status_code=500, detail="Dealer importer not initialized")
    
    try:
        import tempfile
        import os
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # Import contractor data
        result = await dealer_importer.import_contractors_csv(
            file_path=temp_file_path,
            batch_size=batch_size,
            qualification_enabled=qualification_enabled,
            enrichment_enabled=enrichment_enabled
        )
        
        # Clean up temp file
        os.unlink(temp_file_path)
        
        return DealerImportResponse(
            success=result.get('success', True),
            total_records=result.get('total_records', 0),
            processed=result.get('processed', 0),
            qualified=result.get('qualified', 0),
            enriched=result.get('enriched', 0),
            errors=result.get('errors', 0),
            success_rate=result.get('success_rate', 0.0),
            qualification_rate=result.get('qualification_rate', 0.0),
            enrichment_rate=result.get('enrichment_rate', 0.0),
            import_timestamp=result.get('import_timestamp', datetime.now().isoformat()),
            source_file=file.filename
        )
        
    except Exception as e:
        logger.error(f"Dealer upload and import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload and import failed: {str(e)}")


# ========== Analysis Endpoints ==========

@router.get("/summary/{file_path:path}", response_model=DealerSummaryResponse)
async def get_dealer_summary(file_path: str):
    """
    Get summary statistics for dealer scraper data before import.
    
    Provides insights into:
    - Tier distribution (PLATINUM/GOLD/SILVER/BRONZE)
    - OEM certification patterns
    - Geographic distribution
    - Capability analysis
    """
    if not dealer_importer:
        raise HTTPException(status_code=500, detail="Dealer importer not initialized")
    
    try:
        summary = await dealer_importer.get_import_summary(file_path)
        
        if 'error' in summary:
            raise HTTPException(status_code=400, detail=summary['error'])
        
        return DealerSummaryResponse(
            total_contractors=summary.get('total_contractors', 0),
            tier_distribution=summary.get('tier_distribution', {}),
            oem_distribution=summary.get('oem_distribution', {}),
            state_distribution=summary.get('state_distribution', {}),
            capability_distribution=summary.get('capability_distribution', {}),
            multi_oem_contractors=summary.get('multi_oem_contractors', 0),
            high_priority_contractors=summary.get('high_priority_contractors', 0),
            average_icp_score=summary.get('average_icp_score', 0.0),
            top_oem_certifications=summary.get('top_oem_certifications', {})
        )
        
    except Exception as e:
        logger.error(f"Failed to get dealer summary: {e}")
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")


@router.get("/multi-oem-analysis/{file_path:path}", response_model=MultiOEMAnalysisResponse)
async def get_multi_oem_analysis(file_path: str):
    """
    Analyze multi-OEM contractor patterns from dealer scraper data.
    
    Identifies:
    - Triple-OEM unicorns (managing 3+ platforms)
    - Dual-OEM contractors (juggling 2 platforms)
    - Most common OEM combinations
    - High-value prospect patterns
    """
    if not dealer_importer:
        raise HTTPException(status_code=500, detail="Dealer importer not initialized")
    
    try:
        # Load and analyze multi-OEM patterns
        df = pd.read_csv(file_path)
        
        # Filter multi-OEM contractors
        multi_oem_df = df[df['OEM_Count'] > 1].copy()
        triple_oem_df = df[df['OEM_Count'] >= 3].copy()
        dual_oem_df = df[df['OEM_Count'] == 2].copy()
        
        # Analyze OEM combinations
        oem_combinations = {}
        for _, row in multi_oem_df.iterrows():
            oems = str(row['OEMs_Certified']).split(', ')
            if len(oems) >= 2:
                combo = ', '.join(sorted(oems))
                oem_combinations[combo] = oem_combinations.get(combo, 0) + 1
        
        # Sort combinations by frequency
        top_combinations = sorted(
            oem_combinations.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        # Format unicorn contractors
        unicorn_contractors = []
        for _, row in triple_oem_df.iterrows():
            unicorn_contractors.append({
                'name': row['name'],
                'oems': row['OEMs_Certified'],
                'oem_count': row['OEM_Count'],
                'icp_score': row['ICP_Score'],
                'tier': row['ICP_Tier'],
                'state': row['state']
            })
        
        # Format top dual-OEM contractors
        top_dual_oem = []
        for _, row in dual_oem_df.nlargest(20, 'ICP_Score').iterrows():
            top_dual_oem.append({
                'name': row['name'],
                'oems': row['OEMs_Certified'],
                'icp_score': row['ICP_Score'],
                'tier': row['ICP_Tier'],
                'state': row['state']
            })
        
        return MultiOEMAnalysisResponse(
            total_multi_oem=len(multi_oem_df),
            triple_oem_unicorns=len(triple_oem_df),
            dual_oem_contractors=len(dual_oem_df),
            top_oem_combinations=[
                {'combination': combo, 'count': count} 
                for combo, count in top_combinations
            ],
            unicorn_contractors=unicorn_contractors,
            top_dual_oem=top_dual_oem
        )
        
    except Exception as e:
        logger.error(f"Multi-OEM analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Multi-OEM analysis failed: {str(e)}")


@router.get("/validate/{file_path:path}")
async def validate_dealer_csv(file_path: str):
    """
    Validate that a CSV file has the expected dealer scraper format.
    
    Checks for required fields and data structure compatibility.
    """
    if not dealer_importer:
        raise HTTPException(status_code=500, detail="Dealer importer not initialized")
    
    try:
        validation = await dealer_importer.validate_csv_format(file_path)
        return validation
        
    except Exception as e:
        logger.error(f"CSV validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


# ========== Messaging Endpoints ==========

@router.get("/messaging/multi-oem")
async def get_multi_oem_messaging():
    """
    Get messaging templates for multi-OEM contractors.
    
    Provides pain point messaging for:
    - Triple-OEM unicorns (3+ platforms)
    - Dual-OEM contractors (2 platforms)
    - Platform consolidation value props
    """
    return {
        "triple_oem_messaging": {
            "pain_point": "Managing 3+ separate monitoring platforms? That's 3 different logins, 3 UIs, 3 customer experiences.",
            "solution": "Coperniq consolidates all monitoring into one unified dashboard - one login, one customer app, one support team.",
            "key_benefits": [
                "Eliminate platform switching fatigue",
                "Consistent customer experience across brands",
                "Reduce training overhead for staff",
                "Simplify support complexity"
            ]
        },
        "dual_oem_messaging": {
            "pain_point": "Managing Generac and Enphase separately? Your customers are confused about which app to use.",
            "solution": "Coperniq gives your customers one app for both systems - batteries, generators, solar, all in one place.",
            "key_benefits": [
                "Eliminate customer confusion",
                "Reduce duplicate support calls",
                "Enable cross-sell opportunities",
                "Streamline customer onboarding"
            ]
        },
        "platform_consolidation_value": {
            "headline": "Stop juggling multiple monitoring platforms",
            "subheadline": "Coperniq is the only brand-agnostic monitoring platform for microinverters + batteries + generators + HVAC",
            "urgency": "ITC Deadline: Residential Dec 2025, Commercial Q2 2026",
            "srec_focus": "SREC State Focus: Sustainable markets post-ITC (state incentives continue)"
        }
    }


@router.get("/messaging/tier-based")
async def get_tier_based_messaging():
    """
    Get messaging templates based on ICP tier classification.
    
    Provides targeted messaging for:
    - PLATINUM tier (perfect fit)
    - GOLD tier (immediate outreach)
    - SILVER tier (nurture campaign)
    - BRONZE tier (long-term follow-up)
    """
    return {
        "platinum_tier": {
            "tier": "PLATINUM (80-100)",
            "description": "Triple-threat: Multi-OEM + Resimercial + Multi-trade",
            "count": 0,
            "messaging": "You're our ideal customer - managing multiple OEM platforms while serving both residential and commercial markets.",
            "approach": "Direct executive outreach, custom demo, fast-track to pilot"
        },
        "gold_tier": {
            "tier": "GOLD (60-79)",
            "description": "Strong 2-3 dimensions, immediate outreach candidates",
            "count": 50,
            "messaging": "You're juggling multiple platforms and serving diverse markets - Coperniq can simplify your operations.",
            "approach": "BDR outreach, standard demo, 30-day pilot program"
        },
        "silver_tier": {
            "tier": "SILVER (40-59)",
            "description": "Qualified prospects, nurture campaign targets",
            "count": 8160,
            "messaging": "As your business grows, platform consolidation becomes more important. Let's explore how Coperniq can help.",
            "approach": "Email nurture sequence, educational content, quarterly check-ins"
        },
        "bronze_tier": {
            "tier": "BRONZE (<40)",
            "description": "Low priority, limited fit",
            "count": 67,
            "messaging": "Keep us in mind as your business expands into multi-OEM territory.",
            "approach": "Long-term nurture, annual check-ins, referral program"
        }
    }


# ========== Health Check ==========

@router.get("/health")
async def health_check():
    """Perform health check on dealer import system."""
    if not dealer_importer:
        return {
            "status": "unhealthy",
            "error": "Dealer importer not initialized",
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        # Basic health check
        return {
            "status": "healthy",
            "importer_initialized": True,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
