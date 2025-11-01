# Pipeline Testing System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an API endpoint that orchestrates Qualification → Enrichment → Deduplication → Close CRM pipeline with complete observability for testing 200 real prospects.

**Architecture:** FastAPI endpoint with PipelineOrchestrator service coordinating four agents sequentially. Each stage tracks latency, cost, and errors. Results logged to database table for analysis.

**Tech Stack:** FastAPI, SQLAlchemy, pandas (CSV), existing LangGraph agents (Qualification, Enrichment), DeduplicationEngine, CloseCRMAgent

---

## Task 1: Database Model for Pipeline Executions

Create SQLAlchemy model to store pipeline test results.

**Files:**
- Create: `backend/app/models/pipeline_models.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Write failing test for PipelineTestExecution model**

Create: `backend/tests/models/test_pipeline_models.py`

```python
"""
Tests for pipeline testing models
"""
import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.pipeline_models import PipelineTestExecution


def test_pipeline_test_execution_creation(db_session: Session):
    """Test creating a pipeline test execution record"""
    execution = PipelineTestExecution(
        lead_name="Test Company Inc",
        success=True,
        total_latency_ms=4250,
        total_cost_usd=0.002014,
        stages_json={
            "qualification": {"status": "success", "latency_ms": 633},
            "enrichment": {"status": "success", "latency_ms": 2450},
            "deduplication": {"status": "no_duplicate", "latency_ms": 45},
            "close_crm": {"status": "created", "latency_ms": 1122}
        }
    )

    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)

    assert execution.id is not None
    assert execution.lead_name == "Test Company Inc"
    assert execution.success is True
    assert execution.total_latency_ms == 4250
    assert execution.stages_json["qualification"]["latency_ms"] == 633


def test_pipeline_test_execution_query_by_lead_name(db_session: Session):
    """Test querying executions by lead name"""
    execution1 = PipelineTestExecution(
        lead_name="Company A",
        success=True,
        total_latency_ms=4000,
        total_cost_usd=0.002
    )
    execution2 = PipelineTestExecution(
        lead_name="Company B",
        success=False,
        total_latency_ms=1500,
        total_cost_usd=0.001
    )

    db_session.add_all([execution1, execution2])
    db_session.commit()

    results = db_session.query(PipelineTestExecution).filter_by(lead_name="Company A").all()
    assert len(results) == 1
    assert results[0].lead_name == "Company A"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source ../venv/bin/activate && export PYTHONPATH=$PWD && pytest tests/models/test_pipeline_models.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'app.models.pipeline_models'"

**Step 3: Create PipelineTestExecution model**

Create: `backend/app/models/pipeline_models.py`

```python
"""
Pipeline Testing Database Models

Models for tracking end-to-end pipeline test executions.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, Text, Index
from sqlalchemy.sql import func
from datetime import datetime

from app.models.database import Base


class PipelineTestExecution(Base):
    """
    Track end-to-end pipeline test executions.

    Stores results from testing leads through the complete qualification →
    enrichment → deduplication → close CRM pipeline.
    """
    __tablename__ = "pipeline_test_executions"

    id = Column(Integer, primary_key=True, index=True)

    # Lead identification
    lead_name = Column(String(255), nullable=False, index=True)
    lead_email = Column(String(255), nullable=True)
    lead_phone = Column(String(50), nullable=True)
    csv_index = Column(Integer, nullable=True)  # Index in source CSV if applicable

    # Execution results
    success = Column(Boolean, nullable=False, index=True)
    error_stage = Column(String(50), nullable=True)  # Which stage failed (if any)
    error_message = Column(Text, nullable=True)

    # Performance metrics
    total_latency_ms = Column(Integer, nullable=True)
    total_cost_usd = Column(Float, nullable=True)

    # Stage-by-stage results (JSON)
    stages_json = Column(JSON, nullable=True)  # Detailed results per stage

    # Pipeline configuration
    stop_on_duplicate = Column(Boolean, default=True)
    skip_enrichment = Column(Boolean, default=False)
    create_in_crm = Column(Boolean, default=True)
    dry_run = Column(Boolean, default=False)

    # Timing
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    def __repr__(self):
        return f"<PipelineTestExecution(id={self.id}, lead='{self.lead_name}', success={self.success})>"


# Indexes for performance optimization
Index('idx_pipeline_test_lead_created', PipelineTestExecution.lead_name, PipelineTestExecution.created_at)
Index('idx_pipeline_test_success', PipelineTestExecution.success, PipelineTestExecution.created_at)
```

**Step 4: Add model to __init__.py exports**

Modify: `backend/app/models/__init__.py`

Find the imports section and add:

```python
from .pipeline_models import PipelineTestExecution
```

Find the `__all__` list and add:

```python
    "PipelineTestExecution",
```

**Step 5: Run test to verify it passes**

Run: `cd backend && source ../venv/bin/activate && export PYTHONPATH=$PWD && pytest tests/models/test_pipeline_models.py -v`

Expected: PASS (2 tests)

**Step 6: Create Alembic migration**

Run: `cd backend && source ../venv/bin/activate && alembic revision --autogenerate -m "Add pipeline_test_executions table"`

Expected: New migration file created in `backend/app/alembic/versions/`

**Step 7: Apply migration**

Run: `cd backend && source ../venv/bin/activate && alembic upgrade head`

Expected: "Running upgrade ... -> <hash>, Add pipeline_test_executions table"

**Step 8: Commit**

```bash
git add backend/app/models/pipeline_models.py \
        backend/app/models/__init__.py \
        backend/tests/models/test_pipeline_models.py \
        backend/app/alembic/versions/*.py
git commit -m "feat: add PipelineTestExecution database model"
```

---

## Task 2: Pydantic Schemas for API

Create request/response schemas for pipeline testing API.

**Files:**
- Create: `backend/app/schemas/pipeline.py`
- Modify: `backend/app/schemas/__init__.py`

**Step 1: Write failing test for schemas**

Create: `backend/tests/schemas/test_pipeline_schemas.py`

```python
"""
Tests for pipeline testing schemas
"""
import pytest
from pydantic import ValidationError

from app.schemas.pipeline import (
    PipelineTestRequest,
    PipelineTestOptions,
    PipelineStageResult,
    PipelineTestResponse
)


def test_pipeline_test_request_validation():
    """Test PipelineTestRequest accepts valid data"""
    request = PipelineTestRequest(
        lead={
            "name": "A & A GENPRO INC.",
            "email": "contact@aagenpro.com",
            "phone": "(713) 830-3280",
            "company": "A & A GENPRO INC.",
            "website": "https://www.aagenpro.com/",
            "icp_score": 72.8,
            "oem_certifications": ["Generac", "Cummins"]
        },
        options=PipelineTestOptions()
    )

    assert request.lead["name"] == "A & A GENPRO INC."
    assert request.options.stop_on_duplicate is True
    assert request.options.create_in_crm is True


def test_pipeline_test_request_missing_required_field():
    """Test validation fails when required lead fields missing"""
    with pytest.raises(ValidationError):
        PipelineTestRequest(
            lead={},  # Missing required "name" field
            options=PipelineTestOptions()
        )


def test_pipeline_stage_result():
    """Test PipelineStageResult schema"""
    stage = PipelineStageResult(
        status="success",
        latency_ms=633,
        cost_usd=0.000006,
        output={"score": 72, "tier": "high_value"}
    )

    assert stage.status == "success"
    assert stage.latency_ms == 633
    assert stage.output["score"] == 72


def test_pipeline_test_response():
    """Test complete PipelineTestResponse schema"""
    response = PipelineTestResponse(
        success=True,
        total_latency_ms=4250,
        total_cost_usd=0.002014,
        stages={
            "qualification": PipelineStageResult(
                status="success",
                latency_ms=633,
                cost_usd=0.000006,
                output={"score": 72}
            )
        }
    )

    assert response.success is True
    assert response.total_latency_ms == 4250
    assert "qualification" in response.stages
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source ../venv/bin/activate && export PYTHONPATH=$PWD && pytest tests/schemas/test_pipeline_schemas.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'app.schemas.pipeline'"

**Step 3: Create pipeline schemas**

Create: `backend/app/schemas/pipeline.py`

```python
"""
Pydantic schemas for pipeline testing API
"""
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional, List
from datetime import datetime


class PipelineTestOptions(BaseModel):
    """Options for pipeline test execution"""
    stop_on_duplicate: bool = Field(default=True, description="Halt if duplicate detected")
    skip_enrichment: bool = Field(default=False, description="Skip enrichment stage")
    create_in_crm: bool = Field(default=True, description="Actually create lead in CRM")
    dry_run: bool = Field(default=False, description="Test without CRM writes")


class PipelineTestRequest(BaseModel):
    """Request to test a lead through the pipeline"""
    lead: Dict[str, Any] = Field(..., description="Lead data from CSV or manual input")
    options: PipelineTestOptions = Field(default_factory=PipelineTestOptions)

    @field_validator('lead')
    def validate_lead_has_name(cls, v):
        """Ensure lead has at minimum a name"""
        if not v.get('name') and not v.get('company'):
            raise ValueError("Lead must have 'name' or 'company' field")
        return v


class PipelineStageResult(BaseModel):
    """Result from a single pipeline stage"""
    status: str = Field(..., description="Stage status: success, failed, skipped, duplicate")
    latency_ms: Optional[int] = Field(None, description="Stage execution time in milliseconds")
    cost_usd: Optional[float] = Field(None, description="Stage cost in USD")
    confidence: Optional[float] = Field(None, description="Confidence score (for deduplication)")
    output: Optional[Dict[str, Any]] = Field(None, description="Stage output data")
    error: Optional[str] = Field(None, description="Error message if failed")


class PipelineTestResponse(BaseModel):
    """Complete pipeline test result"""
    success: bool = Field(..., description="Overall pipeline success")
    total_latency_ms: int = Field(..., description="Total execution time")
    total_cost_usd: float = Field(..., description="Total cost across all stages")
    lead_name: str = Field(..., description="Lead name for tracking")

    stages: Dict[str, PipelineStageResult] = Field(..., description="Per-stage results")

    error_stage: Optional[str] = Field(None, description="Stage that caused failure")
    error_message: Optional[str] = Field(None, description="Failure error message")

    timeline: Optional[List[Dict[str, Any]]] = Field(None, description="Stage timing timeline")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "total_latency_ms": 4250,
                "total_cost_usd": 0.002014,
                "lead_name": "A & A GENPRO INC.",
                "stages": {
                    "qualification": {
                        "status": "success",
                        "latency_ms": 633,
                        "cost_usd": 0.000006,
                        "output": {"score": 72, "tier": "high_value"}
                    }
                }
            }
        }


class CSVLeadImportRequest(BaseModel):
    """Request to import lead from CSV by index"""
    csv_path: str = Field(..., description="Absolute path to CSV file")
    lead_index: int = Field(..., ge=0, le=199, description="Lead index (0-199)")
    options: PipelineTestOptions = Field(default_factory=PipelineTestOptions)
```

**Step 4: Add schemas to __init__.py exports**

Modify: `backend/app/schemas/__init__.py`

Find the imports and add:

```python
from .pipeline import (
    PipelineTestRequest,
    PipelineTestOptions,
    PipelineStageResult,
    PipelineTestResponse,
    CSVLeadImportRequest
)
```

Find `__all__` and add:

```python
    "PipelineTestRequest",
    "PipelineTestOptions",
    "PipelineStageResult",
    "PipelineTestResponse",
    "CSVLeadImportRequest",
```

**Step 5: Run test to verify it passes**

Run: `cd backend && source ../venv/bin/activate && export PYTHONPATH=$PWD && pytest tests/schemas/test_pipeline_schemas.py -v`

Expected: PASS (4 tests)

**Step 6: Commit**

```bash
git add backend/app/schemas/pipeline.py \
        backend/app/schemas/__init__.py \
        backend/tests/schemas/test_pipeline_schemas.py
git commit -m "feat: add pipeline testing Pydantic schemas"
```

---

## Task 3: CSV Importer Utility

Create utility to load leads from dealer-scraper CSV.

**Files:**
- Create: `backend/app/services/csv_lead_importer.py`

**Step 1: Write failing test for CSV importer**

Create: `backend/tests/services/test_csv_lead_importer.py`

```python
"""
Tests for CSV lead importer
"""
import pytest
import pandas as pd
from pathlib import Path
import tempfile

from app.services.csv_lead_importer import LeadCSVImporter


@pytest.fixture
def sample_csv():
    """Create temporary CSV file with sample data"""
    csv_content = """name,phone,domain,website,email,ICP_Score,OEMs_Certified,city,state
A & A GENPRO INC.,(713) 830-3280,aagenpro.com,https://www.aagenpro.com/,contact@aagenpro.com,72.8,"Generac, Cummins",Houston,TX
Another Company Inc,(555) 123-4567,another.com,https://another.com/,info@another.com,65.2,"Kohler, Generac",Austin,TX
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        return f.name


def test_csv_importer_initialization(sample_csv):
    """Test CSV importer loads file successfully"""
    importer = LeadCSVImporter(csv_path=sample_csv)

    assert importer.df is not None
    assert len(importer.df) == 2
    assert "name" in importer.df.columns
    assert "ICP_Score" in importer.df.columns


def test_get_lead_by_index(sample_csv):
    """Test extracting lead by index"""
    importer = LeadCSVImporter(csv_path=sample_csv)

    lead = importer.get_lead(0)

    assert lead["name"] == "A & A GENPRO INC."
    assert lead["phone"] == "(713) 830-3280"
    assert lead["icp_score"] == 72.8
    assert "Generac" in lead["oem_certifications"]
    assert "Cummins" in lead["oem_certifications"]


def test_get_lead_invalid_index(sample_csv):
    """Test error handling for invalid index"""
    importer = LeadCSVImporter(csv_path=sample_csv)

    with pytest.raises(IndexError):
        importer.get_lead(999)


def test_get_lead_count(sample_csv):
    """Test getting total lead count"""
    importer = LeadCSVImporter(csv_path=sample_csv)

    assert importer.get_lead_count() == 2


def test_get_all_leads(sample_csv):
    """Test getting all leads"""
    importer = LeadCSVImporter(csv_path=sample_csv)

    leads = importer.get_all_leads()

    assert len(leads) == 2
    assert all("name" in lead for lead in leads)
    assert all("icp_score" in lead for lead in leads)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source ../venv/bin/activate && export PYTHONPATH=$PWD && pytest tests/services/test_csv_lead_importer.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.csv_lead_importer'"

**Step 3: Implement LeadCSVImporter**

Create: `backend/app/services/csv_lead_importer.py`

```python
"""
CSV Lead Importer

Utility for loading leads from dealer-scraper CSV files.
Transforms CSV rows into pipeline-ready lead dictionaries.
"""
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class LeadCSVImporter:
    """
    Import and transform leads from CSV files.

    Designed for dealer-scraper-mvp CSV format with columns:
    - name, phone, domain, website, email
    - ICP_Score, OEMs_Certified, city, state, zip
    """

    def __init__(self, csv_path: str):
        """
        Initialize importer with CSV file path.

        Args:
            csv_path: Absolute path to CSV file

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV is empty or missing required columns
        """
        self.csv_path = Path(csv_path)

        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # Load CSV
        self.df = pd.read_csv(csv_path)

        if self.df.empty:
            raise ValueError("CSV file is empty")

        # Validate required columns
        required_cols = ['name']
        missing_cols = [col for col in required_cols if col not in self.df.columns]
        if missing_cols:
            raise ValueError(f"CSV missing required columns: {missing_cols}")

        logger.info(f"Loaded {len(self.df)} leads from {csv_path}")

    def get_lead(self, index: int) -> Dict[str, Any]:
        """
        Extract lead at given index (0-based).

        Args:
            index: Row index in CSV (0 = first lead)

        Returns:
            Dictionary with lead data ready for pipeline

        Raises:
            IndexError: If index out of bounds
        """
        if index < 0 or index >= len(self.df):
            raise IndexError(f"Lead index {index} out of range (0-{len(self.df)-1})")

        row = self.df.iloc[index]

        # Transform CSV row to pipeline format
        lead = {
            "name": row.get("name"),
            "phone": row.get("phone"),
            "domain": row.get("domain"),
            "website": row.get("website"),
            "email": row.get("email") if pd.notna(row.get("email")) else None,
            "icp_score": float(row["ICP_Score"]) if "ICP_Score" in row and pd.notna(row["ICP_Score"]) else None,
        }

        # Parse OEM certifications (comma-separated string)
        if "OEMs_Certified" in row and pd.notna(row["OEMs_Certified"]):
            oems = row["OEMs_Certified"]
            if isinstance(oems, str):
                lead["oem_certifications"] = [oem.strip() for oem in oems.split(",")]
            else:
                lead["oem_certifications"] = []
        else:
            lead["oem_certifications"] = []

        # Add location data if available
        if "city" in row and pd.notna(row.get("city")):
            lead["city"] = row["city"]
        if "state" in row and pd.notna(row.get("state")):
            lead["state"] = row["state"]

        return lead

    def get_lead_count(self) -> int:
        """Get total number of leads in CSV"""
        return len(self.df)

    def get_all_leads(self) -> List[Dict[str, Any]]:
        """
        Get all leads from CSV.

        Returns:
            List of lead dictionaries
        """
        return [self.get_lead(i) for i in range(len(self.df))]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source ../venv/bin/activate && export PYTHONPATH=$PWD && pytest tests/services/test_csv_lead_importer.py -v`

Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add backend/app/services/csv_lead_importer.py \
        backend/tests/services/test_csv_lead_importer.py
git commit -m "feat: add CSV lead importer utility"
```

---

## Task 4: Pipeline Orchestrator Service

Create service to coordinate pipeline execution.

**Files:**
- Create: `backend/app/services/pipeline_orchestrator.py`

**Step 1: Write failing test for orchestrator**

Create: `backend/tests/services/test_pipeline_orchestrator.py`

```python
"""
Tests for pipeline orchestrator
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.schemas.pipeline import PipelineTestOptions


@pytest.fixture
def mock_agents():
    """Mock all agents used by orchestrator"""
    with patch('app.services.pipeline_orchestrator.QualificationAgent') as mock_qual, \
         patch('app.services.pipeline_orchestrator.EnrichmentAgent') as mock_enrich, \
         patch('app.services.pipeline_orchestrator.get_deduplication_engine') as mock_dedup_factory, \
         patch('app.services.pipeline_orchestrator.get_close_crm_agent') as mock_crm_factory:

        # Setup qualification agent mock
        qual_instance = AsyncMock()
        qual_instance.qualify = AsyncMock(return_value=(
            MagicMock(qualification_score=72, tier="high_value", qualification_reasoning="Good fit"),
            633,  # latency_ms
            {"model": "llama3.1-8b", "estimated_cost_usd": 0.000006}
        ))
        mock_qual.return_value = qual_instance

        # Setup enrichment agent mock
        enrich_instance = AsyncMock()
        enrich_instance.enrich = AsyncMock(return_value=(
            {"email": "found@example.com", "linkedin": "https://linkedin.com/company/test"},
            2450,  # latency_ms
            {"estimated_cost_usd": 0.00027}
        ))
        mock_enrich.return_value = enrich_instance

        # Setup deduplication engine mock
        dedup_instance = AsyncMock()
        dedup_result = MagicMock()
        dedup_result.is_duplicate = False
        dedup_result.confidence = 0.0
        dedup_result.matches = []
        dedup_instance.find_duplicates = AsyncMock(return_value=dedup_result)
        mock_dedup_factory.return_value = dedup_instance

        # Setup Close CRM agent mock
        crm_instance = AsyncMock()
        crm_instance.process = AsyncMock(return_value={
            "status": "success",
            "lead_id": "lead_abc123",
            "latency_ms": 1122,
            "cost_usd": 0.00027
        })
        mock_crm_factory.return_value = crm_instance

        yield {
            "qualification": qual_instance,
            "enrichment": enrich_instance,
            "deduplication": dedup_instance,
            "close_crm": crm_instance
        }


@pytest.mark.asyncio
async def test_pipeline_orchestrator_success_path(mock_agents, db_session: Session):
    """Test complete pipeline execution with all stages succeeding"""
    orchestrator = PipelineOrchestrator(db=db_session)

    lead_data = {
        "name": "Test Company Inc",
        "email": "test@company.com",
        "phone": "(555) 123-4567",
        "website": "https://company.com",
        "icp_score": 72.8
    }

    options = PipelineTestOptions(
        stop_on_duplicate=True,
        skip_enrichment=False,
        create_in_crm=True,
        dry_run=False
    )

    result = await orchestrator.run_pipeline(lead_data, options)

    assert result.success is True
    assert result.total_latency_ms > 0
    assert result.total_cost_usd > 0
    assert "qualification" in result.stages
    assert "enrichment" in result.stages
    assert "deduplication" in result.stages
    assert "close_crm" in result.stages
    assert result.stages["qualification"].status == "success"


@pytest.mark.asyncio
async def test_pipeline_stops_on_duplicate(mock_agents, db_session: Session):
    """Test pipeline halts when duplicate detected"""
    # Configure deduplication to return duplicate
    mock_agents["deduplication"].find_duplicates = AsyncMock(return_value=MagicMock(
        is_duplicate=True,
        confidence=95.0,
        matches=[MagicMock(contact=MagicMock(email="test@company.com"))]
    ))

    orchestrator = PipelineOrchestrator(db=db_session)

    lead_data = {"name": "Duplicate Company", "email": "test@company.com"}
    options = PipelineTestOptions(stop_on_duplicate=True)

    result = await orchestrator.run_pipeline(lead_data, options)

    assert result.success is False
    assert result.error_stage == "deduplication"
    assert "duplicate" in result.error_message.lower()
    assert result.stages["deduplication"].confidence == 95.0


@pytest.mark.asyncio
async def test_pipeline_skips_enrichment_when_configured(mock_agents, db_session: Session):
    """Test enrichment stage is skipped when skip_enrichment=True"""
    orchestrator = PipelineOrchestrator(db=db_session)

    lead_data = {"name": "Test Company"}
    options = PipelineTestOptions(skip_enrichment=True)

    result = await orchestrator.run_pipeline(lead_data, options)

    # Enrichment agent should not have been called
    mock_agents["enrichment"].enrich.assert_not_called()
    assert result.stages["enrichment"].status == "skipped"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source ../venv/bin/activate && export PYTHONPATH=$PWD && pytest tests/services/test_pipeline_orchestrator.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.pipeline_orchestrator'"

**Step 3: Implement PipelineOrchestrator** (Part 1 - Setup)

Create: `backend/app/services/pipeline_orchestrator.py`

```python
"""
Pipeline Orchestrator

Coordinates execution of the complete lead processing pipeline:
Qualification → Enrichment → Deduplication → Close CRM
"""
import logging
import time
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.services.langgraph.agents import QualificationAgent, EnrichmentAgent
from app.services.crm.deduplication import get_deduplication_engine
from app.services.langgraph.agents.close_crm_agent import get_close_crm_agent
from app.schemas.pipeline import (
    PipelineTestOptions,
    PipelineTestResponse,
    PipelineStageResult
)
from app.models.pipeline_models import PipelineTestExecution

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Orchestrates complete pipeline execution with observability.

    Tracks latency and cost for each stage:
    1. Qualification (Cerebras, <1000ms, ~$0.000006)
    2. Enrichment (Apollo + LinkedIn, <3000ms, ~$0.00027)
    3. Deduplication (in-memory, <100ms, $0)
    4. Close CRM (DeepSeek, <2000ms, ~$0.00027)
    """

    def __init__(self, db: Session):
        """
        Initialize orchestrator with database session.

        Args:
            db: SQLAlchemy database session for logging
        """
        self.db = db

        # Initialize agents (lazy load to handle import errors gracefully)
        try:
            self.qualification_agent = QualificationAgent()
        except Exception as e:
            logger.warning(f"QualificationAgent unavailable: {e}")
            self.qualification_agent = None

        try:
            self.enrichment_agent = EnrichmentAgent()
        except Exception as e:
            logger.warning(f"EnrichmentAgent unavailable: {e}")
            self.enrichment_agent = None

        self.deduplication_engine = get_deduplication_engine(db=db, threshold=85.0)
        self.close_crm_agent = get_close_crm_agent()

    async def run_pipeline(
        self,
        lead_data: Dict[str, Any],
        options: PipelineTestOptions
    ) -> PipelineTestResponse:
        """
        Execute complete pipeline for a single lead.

        Args:
            lead_data: Lead information from CSV or manual input
            options: Pipeline configuration options

        Returns:
            PipelineTestResponse with stage-by-stage results
        """
        pipeline_start = time.time()
        stages = {}
        total_cost = 0.0
        timeline = []

        lead_name = lead_data.get("name") or lead_data.get("company", "Unknown")
        logger.info(f"Starting pipeline for lead: {lead_name}")

        try:
            # Stage 1: Qualification
            qual_result = await self._run_qualification(lead_data)
            stages["qualification"] = qual_result
            total_cost += qual_result.cost_usd or 0.0

            timeline.append({
                "stage": "qualification",
                "start": 0,
                "end": qual_result.latency_ms
            })

            # Check if lead qualifies (score >= 60)
            if qual_result.status == "success" and qual_result.output:
                score = qual_result.output.get("score", 0)
                if score < 60:
                    return self._build_response(
                        success=False,
                        lead_name=lead_name,
                        stages=stages,
                        total_cost=total_cost,
                        pipeline_start=pipeline_start,
                        error_stage="qualification",
                        error_message=f"Lead score ({score}) below threshold (60)",
                        timeline=timeline
                    )

            # Stage 2: Enrichment (optional)
            if options.skip_enrichment:
                stages["enrichment"] = PipelineStageResult(
                    status="skipped",
                    latency_ms=0
                )
            else:
                enrich_start = qual_result.latency_ms or 0
                enrich_result = await self._run_enrichment(lead_data)
                stages["enrichment"] = enrich_result
                total_cost += enrich_result.cost_usd or 0.0

                timeline.append({
                    "stage": "enrichment",
                    "start": enrich_start,
                    "end": enrich_start + (enrich_result.latency_ms or 0)
                })

            # Stage 3: Deduplication
            dedup_start = timeline[-1]["end"] if timeline else 0
            dedup_result = await self._run_deduplication(lead_data, stages.get("enrichment"))
            stages["deduplication"] = dedup_result

            timeline.append({
                "stage": "deduplication",
                "start": dedup_start,
                "end": dedup_start + (dedup_result.latency_ms or 0)
            })

            # Check if duplicate detected
            if dedup_result.status == "duplicate" and options.stop_on_duplicate:
                return self._build_response(
                    success=False,
                    lead_name=lead_name,
                    stages=stages,
                    total_cost=total_cost,
                    pipeline_start=pipeline_start,
                    error_stage="deduplication",
                    error_message=f"Duplicate detected (confidence: {dedup_result.confidence}%)",
                    timeline=timeline
                )

            # Stage 4: Close CRM (if enabled)
            if options.create_in_crm and not options.dry_run:
                crm_start = timeline[-1]["end"]
                crm_result = await self._run_close_crm(lead_data, stages)
                stages["close_crm"] = crm_result
                total_cost += crm_result.cost_usd or 0.0

                timeline.append({
                    "stage": "close_crm",
                    "start": crm_start,
                    "end": crm_start + (crm_result.latency_ms or 0)
                })

                if crm_result.status != "created":
                    return self._build_response(
                        success=False,
                        lead_name=lead_name,
                        stages=stages,
                        total_cost=total_cost,
                        pipeline_start=pipeline_start,
                        error_stage="close_crm",
                        error_message=crm_result.error or "CRM creation failed",
                        timeline=timeline
                    )
            else:
                stages["close_crm"] = PipelineStageResult(
                    status="skipped" if options.dry_run else "disabled",
                    latency_ms=0
                )

            # Success! All stages completed
            return self._build_response(
                success=True,
                lead_name=lead_name,
                stages=stages,
                total_cost=total_cost,
                pipeline_start=pipeline_start,
                timeline=timeline
            )

        except Exception as e:
            logger.error(f"Pipeline failed for {lead_name}: {str(e)}", exc_info=True)
            return self._build_response(
                success=False,
                lead_name=lead_name,
                stages=stages,
                total_cost=total_cost,
                pipeline_start=pipeline_start,
                error_stage="unknown",
                error_message=str(e),
                timeline=timeline
            )
```

**Step 4: Implement stage methods** (Part 2 - Stage Execution)

Continue in `backend/app/services/pipeline_orchestrator.py`:

```python
    async def _run_qualification(self, lead_data: Dict[str, Any]) -> PipelineStageResult:
        """Execute qualification stage"""
        if not self.qualification_agent:
            return PipelineStageResult(
                status="failed",
                error="QualificationAgent not available"
            )

        try:
            start_time = time.time()

            result, latency_ms, metadata = await self.qualification_agent.qualify(
                company_name=lead_data.get("name") or lead_data.get("company"),
                company_website=lead_data.get("website"),
                company_size=lead_data.get("company_size"),
                industry=lead_data.get("industry"),
                contact_name=lead_data.get("contact_name"),
                contact_title=lead_data.get("contact_title"),
                notes=lead_data.get("notes")
            )

            return PipelineStageResult(
                status="success",
                latency_ms=latency_ms,
                cost_usd=metadata.get("estimated_cost_usd", 0.000006),
                output={
                    "score": result.qualification_score,
                    "tier": result.tier,
                    "reasoning": result.qualification_reasoning
                }
            )

        except Exception as e:
            logger.error(f"Qualification failed: {str(e)}")
            return PipelineStageResult(
                status="failed",
                error=str(e),
                latency_ms=int((time.time() - start_time) * 1000)
            )

    async def _run_enrichment(self, lead_data: Dict[str, Any]) -> PipelineStageResult:
        """Execute enrichment stage"""
        if not self.enrichment_agent:
            return PipelineStageResult(
                status="failed",
                error="EnrichmentAgent not available"
            )

        try:
            start_time = time.time()

            result, latency_ms, metadata = await self.enrichment_agent.enrich(
                company_name=lead_data.get("name") or lead_data.get("company"),
                company_domain=lead_data.get("domain"),
                linkedin_url=lead_data.get("linkedin_url")
            )

            return PipelineStageResult(
                status="success",
                latency_ms=latency_ms,
                cost_usd=metadata.get("estimated_cost_usd", 0.00027),
                output=result
            )

        except Exception as e:
            logger.warning(f"Enrichment failed (non-blocking): {str(e)}")
            # Enrichment failures are non-blocking - use CSV data
            return PipelineStageResult(
                status="failed",
                error=str(e),
                latency_ms=int((time.time() - start_time) * 1000),
                output={"fallback": "using_csv_data"}
            )

    async def _run_deduplication(
        self,
        lead_data: Dict[str, Any],
        enrichment_result: PipelineStageResult
    ) -> PipelineStageResult:
        """Execute deduplication stage"""
        try:
            start_time = time.time()

            # Use enriched email if available, otherwise CSV email
            email = lead_data.get("email")
            if enrichment_result and enrichment_result.output:
                email = enrichment_result.output.get("email", email)

            result = await self.deduplication_engine.find_duplicates(
                email=email,
                phone=lead_data.get("phone"),
                company=lead_data.get("name") or lead_data.get("company"),
                linkedin_url=lead_data.get("linkedin_url")
            )

            latency_ms = int((time.time() - start_time) * 1000)

            return PipelineStageResult(
                status="duplicate" if result.is_duplicate else "no_duplicate",
                latency_ms=latency_ms,
                confidence=result.confidence,
                output={
                    "is_duplicate": result.is_duplicate,
                    "match_count": len(result.matches)
                }
            )

        except Exception as e:
            logger.error(f"Deduplication failed: {str(e)}")
            return PipelineStageResult(
                status="failed",
                error=str(e),
                latency_ms=int((time.time() - start_time) * 1000)
            )

    async def _run_close_crm(
        self,
        lead_data: Dict[str, Any],
        stages: Dict[str, PipelineStageResult]
    ) -> PipelineStageResult:
        """Execute Close CRM creation stage"""
        try:
            start_time = time.time()

            # Gather data from enrichment if available
            enrichment_output = stages.get("enrichment", {}).output or {}

            crm_input = {
                "action": "create_lead",
                "company_name": lead_data.get("name") or lead_data.get("company"),
                "contact_email": enrichment_output.get("email") or lead_data.get("email"),
                "contact_name": lead_data.get("contact_name"),
                "contact_phone": lead_data.get("phone"),
                "website": lead_data.get("website")
            }

            result = await self.close_crm_agent.process(crm_input)

            latency_ms = result.get("latency_ms", int((time.time() - start_time) * 1000))

            return PipelineStageResult(
                status="created" if result.get("status") == "success" else "failed",
                latency_ms=latency_ms,
                cost_usd=result.get("cost_usd", 0.00027),
                output={
                    "lead_id": result.get("lead_id"),
                    "crm_url": result.get("crm_url")
                },
                error=result.get("error")
            )

        except Exception as e:
            logger.error(f"Close CRM creation failed: {str(e)}")
            return PipelineStageResult(
                status="failed",
                error=str(e),
                latency_ms=int((time.time() - start_time) * 1000)
            )

    def _build_response(
        self,
        success: bool,
        lead_name: str,
        stages: Dict[str, PipelineStageResult],
        total_cost: float,
        pipeline_start: float,
        timeline: list,
        error_stage: str = None,
        error_message: str = None
    ) -> PipelineTestResponse:
        """Build final pipeline response and log to database"""
        total_latency_ms = int((time.time() - pipeline_start) * 1000)

        # Create database record
        execution = PipelineTestExecution(
            lead_name=lead_name,
            success=success,
            total_latency_ms=total_latency_ms,
            total_cost_usd=total_cost,
            stages_json={k: v.model_dump() for k, v in stages.items()},
            error_stage=error_stage,
            error_message=error_message
        )

        self.db.add(execution)
        self.db.commit()

        return PipelineTestResponse(
            success=success,
            total_latency_ms=total_latency_ms,
            total_cost_usd=round(total_cost, 6),
            lead_name=lead_name,
            stages=stages,
            error_stage=error_stage,
            error_message=error_message,
            timeline=timeline
        )
```

**Step 5: Run test to verify it passes**

Run: `cd backend && source ../venv/bin/activate && export PYTHONPATH=$PWD && pytest tests/services/test_pipeline_orchestrator.py -v`

Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add backend/app/services/pipeline_orchestrator.py \
        backend/tests/services/test_pipeline_orchestrator.py
git commit -m "feat: add pipeline orchestrator service"
```

---

## Task 5: API Endpoint

Create FastAPI endpoint for pipeline testing.

**Files:**
- Create: `backend/app/api/test_pipeline.py`
- Modify: `backend/app/main.py` (to register router)

**Step 1: Write failing test for API endpoint**

Create: `backend/tests/api/test_test_pipeline.py`

```python
"""
Tests for pipeline testing API endpoint
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app


client = TestClient(app)


@pytest.fixture
def mock_orchestrator():
    """Mock pipeline orchestrator"""
    with patch('app.api.test_pipeline.PipelineOrchestrator') as mock:
        instance = mock.return_value
        instance.run_pipeline = AsyncMock(return_value=MagicMock(
            success=True,
            total_latency_ms=4250,
            total_cost_usd=0.002014,
            lead_name="Test Company",
            stages={
                "qualification": MagicMock(status="success", latency_ms=633),
                "enrichment": MagicMock(status="success", latency_ms=2450),
                "deduplication": MagicMock(status="no_duplicate", latency_ms=45),
                "close_crm": MagicMock(status="created", latency_ms=1122)
            }
        ))
        yield instance


def test_test_pipeline_endpoint_success(mock_orchestrator):
    """Test successful pipeline execution via API"""
    request_data = {
        "lead": {
            "name": "Test Company Inc",
            "email": "test@company.com",
            "phone": "(555) 123-4567"
        },
        "options": {
            "stop_on_duplicate": True,
            "skip_enrichment": False,
            "create_in_crm": True,
            "dry_run": False
        }
    }

    response = client.post("/api/leads/test-pipeline", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total_latency_ms"] > 0
    assert "stages" in data


def test_test_pipeline_endpoint_validation_error():
    """Test API validation for missing required fields"""
    request_data = {
        "lead": {},  # Missing required name/company field
        "options": {}
    }

    response = client.post("/api/leads/test-pipeline", json=request_data)

    assert response.status_code == 422  # Validation error
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source ../venv/bin/activate && export PYTHONPATH=$PWD && pytest tests/api/test_test_pipeline.py -v`

Expected: FAIL (endpoint not found or import error)

**Step 3: Create API endpoint**

Create: `backend/app/api/test_pipeline.py`

```python
"""
Pipeline Testing API Endpoints

Endpoints for testing leads through the complete pipeline with observability.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
import logging

from app.models import get_db
from app.schemas.pipeline import (
    PipelineTestRequest,
    PipelineTestResponse,
    CSVLeadImportRequest
)
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.csv_lead_importer import LeadCSVImporter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads/test-pipeline", tags=["pipeline-testing"])


@router.post("", response_model=PipelineTestResponse)
async def test_pipeline(
    request: PipelineTestRequest,
    db: Session = Depends(get_db)
):
    """
    Test a lead through the complete pipeline.

    **Pipeline Stages**:
    1. Qualification (Cerebras, <1000ms, ~$0.000006)
    2. Enrichment (Apollo + LinkedIn, <3000ms, ~$0.00027)
    3. Deduplication (in-memory, <100ms, $0)
    4. Close CRM (DeepSeek, <2000ms, ~$0.00027)

    **Total Target**: <5000ms, <$0.002 per lead

    **Options**:
    - stop_on_duplicate: Halt if duplicate detected (default: true)
    - skip_enrichment: Skip enrichment stage (default: false)
    - create_in_crm: Actually create in CRM (default: true)
    - dry_run: Test without CRM writes (default: false)

    Returns detailed stage-by-stage results with latency and cost tracking.
    """
    logger.info(f"Pipeline test request for lead: {request.lead.get('name')}")

    orchestrator = PipelineOrchestrator(db=db)
    result = await orchestrator.run_pipeline(request.lead, request.options)

    logger.info(
        f"Pipeline test complete: lead={result.lead_name}, "
        f"success={result.success}, latency={result.total_latency_ms}ms, "
        f"cost=${result.total_cost_usd}"
    )

    return result


@router.get("/quick", response_model=PipelineTestResponse)
async def test_pipeline_quick(
    lead_index: int = Query(..., ge=0, le=199, description="Lead index in CSV (0-199)"),
    csv_path: str = Query(
        default="/Users/tmkipper/Desktop/dealer-scraper-mvp/output/top_200_prospects_final_20251029.csv",
        description="Path to CSV file"
    ),
    stop_on_duplicate: bool = Query(default=True),
    skip_enrichment: bool = Query(default=False),
    create_in_crm: bool = Query(default=True),
    dry_run: bool = Query(default=False),
    db: Session = Depends(get_db)
):
    """
    Quick test: Load lead from CSV and run through pipeline.

    **Use Case**: Testing individual leads from dealer-scraper CSV.

    **Example**:
    ```
    GET /api/leads/test-pipeline/quick?lead_index=0
    ```

    Loads lead at index 0 (\"A & A GENPRO INC.\") and tests through pipeline.

    **CSV Format**: dealer-scraper-mvp format with columns:
    - name, phone, domain, website, email
    - ICP_Score, OEMs_Certified, city, state
    """
    logger.info(f"Quick pipeline test: csv={csv_path}, index={lead_index}")

    # Validate CSV path
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"CSV file not found: {csv_path}"
        )

    # Load lead from CSV
    try:
        importer = LeadCSVImporter(csv_path=csv_path)
        lead_data = importer.get_lead(lead_index)
    except IndexError:
        raise HTTPException(
            status_code=400,
            detail=f"Lead index {lead_index} out of range (0-{importer.get_lead_count()-1})"
        )
    except Exception as e:
        logger.error(f"Failed to load lead from CSV: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load lead from CSV: {str(e)}"
        )

    # Create request
    from app.schemas.pipeline import PipelineTestOptions
    request = PipelineTestRequest(
        lead=lead_data,
        options=PipelineTestOptions(
            stop_on_duplicate=stop_on_duplicate,
            skip_enrichment=skip_enrichment,
            create_in_crm=create_in_crm,
            dry_run=dry_run
        )
    )

    # Run pipeline
    orchestrator = PipelineOrchestrator(db=db)
    result = await orchestrator.run_pipeline(request.lead, request.options)

    logger.info(
        f"Quick test complete: index={lead_index}, lead={result.lead_name}, "
        f"success={result.success}, latency={result.total_latency_ms}ms"
    )

    return result
```

**Step 4: Register router in main.py**

Modify: `backend/app/main.py`

Find where other routers are imported (look for `from app.api import`), add:

```python
from app.api import test_pipeline
```

Find where routers are included (look for `app.include_router`), add:

```python
app.include_router(test_pipeline.router, prefix="/api")
```

**Step 5: Run test to verify it passes**

Run: `cd backend && source ../venv/bin/activate && export PYTHONPATH=$PWD && pytest tests/api/test_test_pipeline.py -v`

Expected: PASS (2 tests)

**Step 6: Commit**

```bash
git add backend/app/api/test_pipeline.py \
        backend/app/main.py \
        backend/tests/api/test_test_pipeline.py
git commit -m "feat: add pipeline testing API endpoints"
```

---

## Task 6: Manual Testing with Real Lead

Test the complete system with first lead from CSV.

**Step 1: Verify database is running**

Run: `docker ps | grep postgres`

Expected: PostgreSQL container running on port 5433

If not running: `cd backend && docker-compose up -d postgres`

**Step 2: Verify Redis is running**

Run: `docker ps | grep redis`

Expected: Redis container running on port 6379

If not running: `cd backend && docker-compose up -d redis`

**Step 3: Start server**

Run: `cd backend && source ../venv/bin/activate && python start_server.py`

Expected: Server starts on http://localhost:8001

**Step 4: Test with lead index 0**

In new terminal:

Run: `curl -X GET "http://localhost:8001/api/leads/test-pipeline/quick?lead_index=0&dry_run=true" | python3 -m json.tool`

Expected: JSON response with:
- success: true
- total_latency_ms: <5000
- stages.qualification.status: "success"
- stages.enrichment.status: "success"
- stages.deduplication.status: "no_duplicate"
- stages.close_crm.status: "skipped" (due to dry_run=true)

**Step 5: Verify database record**

Run: `psql $DATABASE_URL -c "SELECT lead_name, success, total_latency_ms, total_cost_usd FROM pipeline_test_executions ORDER BY created_at DESC LIMIT 1;"`

Expected: Row with lead "A & A GENPRO INC.", success=true

**Step 6: Document results**

Create: `docs/testing/2024-10-31-first-pipeline-test.md`

```markdown
# First Pipeline Test Results

**Date**: 2024-10-31
**Lead**: A & A GENPRO INC. (Index 0)
**Configuration**: dry_run=true, stop_on_duplicate=true

## Results

- **Success**: [✓/✗]
- **Total Latency**: [X]ms (target: <5000ms)
- **Total Cost**: $[X] (target: <$0.002)

### Stage Breakdown

1. **Qualification**: [X]ms, $[X]
   - Score: [X]/100
   - Tier: [tier]

2. **Enrichment**: [X]ms, $[X]
   - Email found: [yes/no]
   - LinkedIn found: [yes/no]

3. **Deduplication**: [X]ms
   - Duplicate: [yes/no]
   - Confidence: [X]%

4. **Close CRM**: skipped (dry_run)

## Issues Found

[List any issues encountered]

## Next Steps

- [ ] Test with dry_run=false
- [ ] Test leads 1-4
- [ ] Test duplicate detection
- [ ] Test missing email scenario
```

**Step 7: Commit test results**

```bash
git add docs/testing/2024-10-31-first-pipeline-test.md
git commit -m "docs: add first pipeline test results"
```

---

## Success Criteria Checklist

After completing all tasks, verify:

**Functionality**:
- [ ] POST /api/leads/test-pipeline endpoint works
- [ ] GET /api/leads/test-pipeline/quick endpoint works
- [ ] CSV importer loads dealer-scraper format
- [ ] All 4 pipeline stages execute in sequence
- [ ] Pipeline stops on duplicate (when configured)
- [ ] Pipeline skips enrichment (when configured)
- [ ] Database logs all executions

**Performance**:
- [ ] Qualification: <1000ms
- [ ] Enrichment: <3000ms
- [ ] Deduplication: <100ms
- [ ] Close CRM: <2000ms
- [ ] Total pipeline: <5000ms

**Testing**:
- [ ] All unit tests passing (models, schemas, services)
- [ ] API endpoint tests passing
- [ ] Manual test with lead index 0 successful

**Documentation**:
- [ ] Test results documented
- [ ] API endpoints documented in code
- [ ] Database schema migrated

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2024-10-31-pipeline-testing-implementation.md`.**

**Two execution options:**

**1. Subagent-Driven (this session)** - Dispatch fresh subagent per task, review between tasks, fast iteration with @superpowers:subagent-driven-development

**2. Parallel Session (separate)** - Open new session with @superpowers:executing-plans for batch execution with checkpoints

**Which approach would you prefer?**
