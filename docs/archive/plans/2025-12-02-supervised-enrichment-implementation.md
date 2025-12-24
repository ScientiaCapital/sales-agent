# Supervised Enrichment Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an interactive terminal-based enrichment pipeline that processes 2 companies in parallel through 4 sequential stages (Apollo Free → LinkedIn → Hunter → Apollo Paid) with manual checkpoints.

**Architecture:** Pure asyncio orchestrator that wraps existing `enrich_*.py` scripts as callable stages. Redis tracks real-time state per company. Supabase persists final results. Terminal UI shows progress with keyboard controls (c/s/r/q).

**Tech Stack:** Python 3.11, asyncio, Redis, Supabase, rich (terminal UI), existing enrich_*.py scripts

---

## Task 1: Create Module Structure

**Files:**
- Create: `backend/app/services/supervised_pipeline/__init__.py`
- Create: `backend/app/services/supervised_pipeline/orchestrator.py`
- Create: `backend/app/services/supervised_pipeline/state_manager.py`
- Create: `backend/app/services/supervised_pipeline/budget_tracker.py`

**Step 1: Create directory and __init__.py**

```bash
mkdir -p backend/app/services/supervised_pipeline
```

```python
# backend/app/services/supervised_pipeline/__init__.py
"""
Supervised Enrichment Pipeline

Interactive terminal-based enrichment with manual checkpoints.
Processes 2 companies in parallel through 4 sequential stages.
"""

from .orchestrator import SupervisedOrchestrator
from .state_manager import StateManager
from .budget_tracker import BudgetTracker

__all__ = [
    "SupervisedOrchestrator",
    "StateManager",
    "BudgetTracker",
]
```

**Step 2: Commit structure**

```bash
git add backend/app/services/supervised_pipeline/__init__.py
git commit -m "feat: create supervised_pipeline module structure"
```

---

## Task 2: Implement State Manager (Redis + Supabase)

**Files:**
- Create: `backend/app/services/supervised_pipeline/state_manager.py`
- Test: `backend/tests/services/test_state_manager.py`

**Step 1: Write the failing test**

```python
# backend/tests/services/test_state_manager.py
"""Tests for StateManager - Redis + Supabase state tracking."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestStateManager:
    """Test StateManager functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.hset = AsyncMock()
        redis.hget = AsyncMock(return_value=None)
        redis.hgetall = AsyncMock(return_value={})
        redis.delete = AsyncMock()
        return redis

    @pytest.fixture
    def mock_supabase(self):
        """Create mock Supabase client."""
        supabase = MagicMock()
        supabase.table.return_value.update.return_value.eq.return_value.execute = MagicMock()
        return supabase

    @pytest.mark.asyncio
    async def test_update_stage_status(self, mock_redis, mock_supabase):
        """Test updating company stage status in Redis."""
        from app.services.supervised_pipeline.state_manager import StateManager

        manager = StateManager(redis=mock_redis, supabase=mock_supabase)

        await manager.update_stage_status(
            company_id="test-123",
            stage="apollo_free",
            status="done"
        )

        mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_get_company_status(self, mock_redis, mock_supabase):
        """Test retrieving company status from Redis."""
        from app.services.supervised_pipeline.state_manager import StateManager

        mock_redis.hgetall.return_value = {
            b"stage": b"linkedin",
            b"apollo_free": b"done",
            b"linkedin": b"running",
        }

        manager = StateManager(redis=mock_redis, supabase=mock_supabase)
        status = await manager.get_company_status("test-123")

        assert status["stage"] == "linkedin"
        assert status["apollo_free"] == "done"

    @pytest.mark.asyncio
    async def test_sync_to_supabase(self, mock_redis, mock_supabase):
        """Test syncing completion status to Supabase."""
        from app.services.supervised_pipeline.state_manager import StateManager

        manager = StateManager(redis=mock_redis, supabase=mock_supabase)

        await manager.sync_to_supabase(
            company_id="test-123",
            stage="apollo_free",
            cost_usd=0.0
        )

        mock_supabase.table.assert_called_with("dim_companies")
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/services/test_state_manager.py -v`
Expected: FAIL with "No module named 'app.services.supervised_pipeline.state_manager'"

**Step 3: Write minimal implementation**

```python
# backend/app/services/supervised_pipeline/state_manager.py
"""
State Manager - Redis + Supabase State Tracking

Tracks enrichment progress per company in Redis (real-time)
and syncs to Supabase (persistence) after each stage.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.logging import setup_logging

logger = setup_logging(__name__)


class StateManager:
    """Manages enrichment state in Redis and Supabase."""

    STAGE_ORDER = ["apollo_free", "linkedin", "hunter", "apollo_paid"]

    def __init__(self, redis, supabase):
        """
        Initialize StateManager.

        Args:
            redis: Async Redis client
            supabase: Supabase client
        """
        self.redis = redis
        self.supabase = supabase

    def _key(self, company_id: str) -> str:
        """Generate Redis key for company status."""
        return f"enrichment:{company_id}:status"

    async def init_company(self, company_id: str) -> None:
        """Initialize tracking for a new company."""
        key = self._key(company_id)
        initial_state = {
            "stage": "apollo_free",
            "apollo_free": "pending",
            "linkedin": "pending",
            "hunter": "pending",
            "apollo_paid": "pending",
            "cost_usd": "0.0",
            "started_at": datetime.utcnow().isoformat(),
        }
        for field, value in initial_state.items():
            await self.redis.hset(key, field, value)

    async def update_stage_status(
        self,
        company_id: str,
        stage: str,
        status: str,
        cost_usd: float = 0.0
    ) -> None:
        """
        Update a stage's status in Redis.

        Args:
            company_id: Company UUID
            stage: Stage name (apollo_free, linkedin, hunter, apollo_paid)
            status: Status (pending, running, done, failed, skipped)
            cost_usd: Cost incurred for this stage
        """
        key = self._key(company_id)
        await self.redis.hset(key, stage, status)
        await self.redis.hset(key, "stage", stage)

        # Accumulate cost
        current_cost = await self.redis.hget(key, "cost_usd")
        current_cost = float(current_cost) if current_cost else 0.0
        await self.redis.hset(key, "cost_usd", str(current_cost + cost_usd))

        logger.info(f"Company {company_id}: {stage} -> {status}")

    async def get_company_status(self, company_id: str) -> Dict[str, Any]:
        """
        Get current status for a company.

        Returns:
            Dict with stage statuses and metadata
        """
        key = self._key(company_id)
        raw = await self.redis.hgetall(key)

        if not raw:
            return {}

        # Decode bytes to strings
        return {
            k.decode() if isinstance(k, bytes) else k:
            v.decode() if isinstance(v, bytes) else v
            for k, v in raw.items()
        }

    async def sync_to_supabase(
        self,
        company_id: str,
        stage: str,
        cost_usd: float = 0.0
    ) -> None:
        """
        Sync stage completion to Supabase.

        Args:
            company_id: Company UUID
            stage: Completed stage name
            cost_usd: Cost for this stage
        """
        timestamp_field = f"{stage}_enriched_at" if stage != "apollo_paid" else "apollo_paid_at"

        # Map stage names to Supabase column names
        column_map = {
            "apollo_free": "apollo_enriched_at",
            "linkedin": "linkedin_enriched_at",
            "hunter": "hunter_enriched_at",
            "apollo_paid": "apollo_paid_at",
        }

        update_data = {
            column_map.get(stage, timestamp_field): datetime.utcnow().isoformat(),
        }

        # Accumulate cost
        if cost_usd > 0:
            # Note: In production, use atomic increment
            update_data["enrichment_cost_usd"] = cost_usd

        try:
            self.supabase.table("dim_companies").update(
                update_data
            ).eq("id", company_id).execute()

            logger.info(f"Synced {stage} to Supabase for {company_id}")
        except Exception as e:
            logger.error(f"Failed to sync to Supabase: {e}")

    async def mark_complete(self, company_id: str) -> None:
        """Mark company enrichment as complete."""
        key = self._key(company_id)
        await self.redis.hset(key, "completed_at", datetime.utcnow().isoformat())

        # Update Supabase
        self.supabase.table("dim_companies").update({
            "enrichment_status": "completed",
        }).eq("id", company_id).execute()

    async def mark_failed(self, company_id: str, error: str) -> None:
        """Mark company enrichment as failed."""
        key = self._key(company_id)
        await self.redis.hset(key, "error", error)
        await self.redis.hset(key, "failed_at", datetime.utcnow().isoformat())

        # Update Supabase
        self.supabase.table("dim_companies").update({
            "enrichment_status": "failed",
            "enrichment_error": error,
        }).eq("id", company_id).execute()

    async def cleanup(self, company_id: str) -> None:
        """Remove Redis state for a company (after sync)."""
        key = self._key(company_id)
        await self.redis.delete(key)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/services/test_state_manager.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/app/services/supervised_pipeline/state_manager.py
git add backend/tests/services/test_state_manager.py
git commit -m "feat: add StateManager for Redis + Supabase tracking"
```

---

## Task 3: Implement Budget Tracker

**Files:**
- Create: `backend/app/services/supervised_pipeline/budget_tracker.py`
- Test: `backend/tests/services/test_budget_tracker.py`

**Step 1: Write the failing test**

```python
# backend/tests/services/test_budget_tracker.py
"""Tests for BudgetTracker - per-batch cost limits."""

import pytest
from unittest.mock import AsyncMock


class TestBudgetTracker:
    """Test BudgetTracker functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.hset = AsyncMock()
        redis.hget = AsyncMock(return_value=b"0.0")
        redis.hgetall = AsyncMock(return_value={})
        redis.hincrby = AsyncMock()
        redis.hincrbyfloat = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_init_batch(self, mock_redis):
        """Test initializing a new batch with budget."""
        from app.services.supervised_pipeline.budget_tracker import BudgetTracker

        tracker = BudgetTracker(redis=mock_redis, batch_id="batch-001", limit_usd=5.0)
        await tracker.init_batch(total_companies=100)

        mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_can_proceed_under_budget(self, mock_redis):
        """Test can_proceed returns True when under budget."""
        from app.services.supervised_pipeline.budget_tracker import BudgetTracker

        mock_redis.hget.side_effect = lambda key, field: {
            b"spent_usd": b"1.50",
            b"limit_usd": b"5.00",
        }.get(field.encode() if isinstance(field, str) else field, b"0")

        tracker = BudgetTracker(redis=mock_redis, batch_id="batch-001", limit_usd=5.0)

        can_proceed = await tracker.can_proceed()
        assert can_proceed is True

    @pytest.mark.asyncio
    async def test_can_proceed_over_budget(self, mock_redis):
        """Test can_proceed returns False when over budget."""
        from app.services.supervised_pipeline.budget_tracker import BudgetTracker

        mock_redis.hget.side_effect = lambda key, field: {
            "spent_usd": b"5.50",
            "limit_usd": b"5.00",
        }.get(field, b"0")

        tracker = BudgetTracker(redis=mock_redis, batch_id="batch-001", limit_usd=5.0)
        tracker._spent_usd = 5.50  # Simulate over budget

        can_proceed = await tracker.can_proceed()
        assert can_proceed is False

    @pytest.mark.asyncio
    async def test_add_cost(self, mock_redis):
        """Test adding cost to batch total."""
        from app.services.supervised_pipeline.budget_tracker import BudgetTracker

        tracker = BudgetTracker(redis=mock_redis, batch_id="batch-001", limit_usd=5.0)
        await tracker.add_cost(0.05)

        mock_redis.hincrbyfloat.assert_called()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/services/test_budget_tracker.py -v`
Expected: FAIL with "No module named 'app.services.supervised_pipeline.budget_tracker'"

**Step 3: Write minimal implementation**

```python
# backend/app/services/supervised_pipeline/budget_tracker.py
"""
Budget Tracker - Per-Batch Cost Limits

Tracks spending across a batch and enforces limits.
Pauses processing when budget is exceeded.
"""

from typing import Dict, Any, Optional

from app.core.logging import setup_logging

logger = setup_logging(__name__)


class BudgetTracker:
    """Tracks and enforces per-batch budget limits."""

    def __init__(self, redis, batch_id: str, limit_usd: float):
        """
        Initialize BudgetTracker.

        Args:
            redis: Async Redis client
            batch_id: Unique batch identifier
            limit_usd: Maximum budget for this batch
        """
        self.redis = redis
        self.batch_id = batch_id
        self.limit_usd = limit_usd
        self._spent_usd = 0.0

    def _key(self) -> str:
        """Generate Redis key for batch budget."""
        return f"enrichment:batch:{self.batch_id}:budget"

    async def init_batch(self, total_companies: int) -> None:
        """
        Initialize budget tracking for a new batch.

        Args:
            total_companies: Total companies in this batch
        """
        key = self._key()
        await self.redis.hset(key, "limit_usd", str(self.limit_usd))
        await self.redis.hset(key, "spent_usd", "0.0")
        await self.redis.hset(key, "companies_total", str(total_companies))
        await self.redis.hset(key, "companies_processed", "0")
        await self.redis.hset(key, "stop_reason", "")

        logger.info(f"Batch {self.batch_id}: Budget ${self.limit_usd:.2f} for {total_companies} companies")

    async def add_cost(self, cost_usd: float) -> None:
        """
        Add cost to batch total.

        Args:
            cost_usd: Cost to add
        """
        key = self._key()
        await self.redis.hincrbyfloat(key, "spent_usd", cost_usd)
        self._spent_usd += cost_usd

    async def increment_processed(self) -> None:
        """Increment processed company count."""
        key = self._key()
        await self.redis.hincrby(key, "companies_processed", 1)

    async def can_proceed(self) -> bool:
        """
        Check if we can proceed with more processing.

        Returns:
            True if under budget, False if budget exceeded
        """
        key = self._key()
        spent_raw = await self.redis.hget(key, "spent_usd")
        spent = float(spent_raw) if spent_raw else self._spent_usd

        if spent >= self.limit_usd:
            await self.redis.hset(key, "stop_reason", "budget_exceeded")
            logger.warning(f"Batch {self.batch_id}: Budget exceeded (${spent:.2f} >= ${self.limit_usd:.2f})")
            return False

        return True

    async def get_status(self) -> Dict[str, Any]:
        """
        Get current budget status.

        Returns:
            Dict with budget info
        """
        key = self._key()
        spent_raw = await self.redis.hget(key, "spent_usd")
        processed_raw = await self.redis.hget(key, "companies_processed")
        total_raw = await self.redis.hget(key, "companies_total")

        spent = float(spent_raw) if spent_raw else 0.0
        processed = int(processed_raw) if processed_raw else 0
        total = int(total_raw) if total_raw else 0

        return {
            "batch_id": self.batch_id,
            "limit_usd": self.limit_usd,
            "spent_usd": spent,
            "remaining_usd": max(0, self.limit_usd - spent),
            "percent_used": (spent / self.limit_usd * 100) if self.limit_usd > 0 else 0,
            "companies_processed": processed,
            "companies_remaining": max(0, total - processed),
        }

    async def set_stop_reason(self, reason: str) -> None:
        """Set the reason for stopping (manual, budget, error)."""
        key = self._key()
        await self.redis.hset(key, "stop_reason", reason)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/services/test_budget_tracker.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/app/services/supervised_pipeline/budget_tracker.py
git add backend/tests/services/test_budget_tracker.py
git commit -m "feat: add BudgetTracker for per-batch cost limits"
```

---

## Task 4: Implement Stage Wrappers

**Files:**
- Create: `backend/app/services/supervised_pipeline/stages/__init__.py`
- Create: `backend/app/services/supervised_pipeline/stages/base.py`
- Create: `backend/app/services/supervised_pipeline/stages/apollo_free.py`
- Create: `backend/app/services/supervised_pipeline/stages/linkedin.py`
- Create: `backend/app/services/supervised_pipeline/stages/hunter.py`
- Create: `backend/app/services/supervised_pipeline/stages/apollo_paid.py`

**Step 1: Create stages module**

```python
# backend/app/services/supervised_pipeline/stages/__init__.py
"""
Enrichment Stages

Wrappers around existing enrich_*.py scripts for orchestration.
"""

from .base import BaseStage, StageResult
from .apollo_free import ApolloFreeStage
from .linkedin import LinkedInStage
from .hunter import HunterStage
from .apollo_paid import ApolloPaidStage

__all__ = [
    "BaseStage",
    "StageResult",
    "ApolloFreeStage",
    "LinkedInStage",
    "HunterStage",
    "ApolloPaidStage",
]
```

**Step 2: Create base stage class**

```python
# backend/app/services/supervised_pipeline/stages/base.py
"""Base class for enrichment stages."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class StageResult:
    """Result from an enrichment stage."""
    success: bool
    data: Dict[str, Any]
    cost_usd: float = 0.0
    error: Optional[str] = None
    latency_ms: int = 0


class BaseStage(ABC):
    """Abstract base class for enrichment stages."""

    name: str = "base"
    cost_per_call: float = 0.0

    @abstractmethod
    async def execute(self, company: Dict[str, Any]) -> StageResult:
        """
        Execute the enrichment stage for a company.

        Args:
            company: Company data from Supabase

        Returns:
            StageResult with enrichment data
        """
        pass
```

**Step 3: Create Apollo Free stage wrapper**

```python
# backend/app/services/supervised_pipeline/stages/apollo_free.py
"""Apollo Free enrichment stage."""

import asyncio
import time
from typing import Any, Dict

from .base import BaseStage, StageResult
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class ApolloFreeStage(BaseStage):
    """Apollo Free API enrichment stage."""

    name = "apollo_free"
    cost_per_call = 0.0  # Free tier

    async def execute(self, company: Dict[str, Any]) -> StageResult:
        """
        Execute Apollo Free enrichment.

        Uses existing enrich_apollo.py logic.
        """
        start_time = time.time()
        company_id = company.get("id")
        domain = company.get("domain")

        if not domain:
            return StageResult(
                success=False,
                data={},
                error="No domain for Apollo lookup",
                latency_ms=0
            )

        try:
            # Import and use existing Apollo enrichment
            # This wraps the existing enrich_apollo.py functionality
            from app.services.apollo import ApolloService

            apollo = ApolloService()
            result = await apollo.enrich_company(domain=domain)

            latency_ms = int((time.time() - start_time) * 1000)

            if result:
                logger.info(f"Apollo Free: {domain} -> {len(result.get('contacts', []))} contacts")
                return StageResult(
                    success=True,
                    data=result,
                    cost_usd=0.0,
                    latency_ms=latency_ms
                )
            else:
                return StageResult(
                    success=True,  # No error, just no data
                    data={},
                    cost_usd=0.0,
                    latency_ms=latency_ms
                )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Apollo Free error for {domain}: {e}")
            return StageResult(
                success=False,
                data={},
                error=str(e),
                latency_ms=latency_ms
            )
```

**Step 4: Create LinkedIn stage wrapper**

```python
# backend/app/services/supervised_pipeline/stages/linkedin.py
"""LinkedIn enrichment stage (Browserbase scraping)."""

import time
from typing import Any, Dict

from .base import BaseStage, StageResult
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class LinkedInStage(BaseStage):
    """LinkedIn company page scraping via Browserbase."""

    name = "linkedin"
    cost_per_call = 0.0  # Browserbase sessions

    async def execute(self, company: Dict[str, Any]) -> StageResult:
        """
        Execute LinkedIn scraping.

        Uses existing enrich_linkedin.py logic.
        """
        start_time = time.time()
        company_name = company.get("name")
        linkedin_url = company.get("linkedin_url")

        if not linkedin_url and not company_name:
            return StageResult(
                success=False,
                data={},
                error="No LinkedIn URL or company name",
                latency_ms=0
            )

        try:
            # Import and use existing LinkedIn enrichment
            from app.services.browserbase_team_scraper import BrowserbaseTeamScraper

            scraper = BrowserbaseTeamScraper()

            if linkedin_url:
                result = await scraper.scrape_company_page(linkedin_url)
            else:
                # Search by company name
                result = await scraper.search_and_scrape(company_name)

            latency_ms = int((time.time() - start_time) * 1000)

            if result:
                logger.info(f"LinkedIn: {company_name} -> {result.get('employee_count', 'N/A')} employees")
                return StageResult(
                    success=True,
                    data=result,
                    cost_usd=0.0,
                    latency_ms=latency_ms
                )
            else:
                return StageResult(
                    success=True,
                    data={},
                    cost_usd=0.0,
                    latency_ms=latency_ms
                )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"LinkedIn error for {company_name}: {e}")
            return StageResult(
                success=False,
                data={},
                error=str(e),
                latency_ms=latency_ms
            )
```

**Step 5: Create Hunter stage wrapper**

```python
# backend/app/services/supervised_pipeline/stages/hunter.py
"""Hunter.io email enrichment stage."""

import time
from typing import Any, Dict

from .base import BaseStage, StageResult
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class HunterStage(BaseStage):
    """Hunter.io email finder stage."""

    name = "hunter"
    cost_per_call = 0.01  # ~$0.01 per lookup

    async def execute(self, company: Dict[str, Any]) -> StageResult:
        """
        Execute Hunter.io email lookup.

        Uses existing enrich_hunter.py logic.
        """
        start_time = time.time()
        domain = company.get("domain")
        contacts = company.get("contacts", [])

        if not domain:
            return StageResult(
                success=False,
                data={},
                error="No domain for Hunter lookup",
                latency_ms=0
            )

        try:
            # Import and use existing Hunter service
            from app.services.hunter_service import HunterService

            hunter = HunterService()

            # Find emails for each contact
            enriched_contacts = []
            total_cost = 0.0

            for contact in contacts[:5]:  # Limit to 5 contacts per company
                name = contact.get("name")
                if name:
                    email_result = await hunter.find_email(domain=domain, name=name)
                    if email_result and email_result.get("email"):
                        contact["email"] = email_result["email"]
                        contact["email_confidence"] = email_result.get("confidence", 0)
                        total_cost += self.cost_per_call
                    enriched_contacts.append(contact)

            latency_ms = int((time.time() - start_time) * 1000)

            found_emails = sum(1 for c in enriched_contacts if c.get("email"))
            logger.info(f"Hunter: {domain} -> {found_emails}/{len(enriched_contacts)} emails found")

            return StageResult(
                success=True,
                data={"contacts": enriched_contacts},
                cost_usd=total_cost,
                latency_ms=latency_ms
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Hunter error for {domain}: {e}")
            return StageResult(
                success=False,
                data={},
                error=str(e),
                latency_ms=latency_ms
            )
```

**Step 6: Create Apollo Paid stage wrapper**

```python
# backend/app/services/supervised_pipeline/stages/apollo_paid.py
"""Apollo Paid (credit-based) enrichment stage."""

import time
from typing import Any, Dict

from .base import BaseStage, StageResult
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class ApolloPaidStage(BaseStage):
    """Apollo Paid API enrichment (uses credits)."""

    name = "apollo_paid"
    cost_per_call = 0.05  # ~$0.05 per credit

    async def execute(self, company: Dict[str, Any]) -> StageResult:
        """
        Execute Apollo Paid enrichment.

        Only runs if previous stages didn't find enough data.
        Uses existing enrich_apollo_paid.py logic.
        """
        start_time = time.time()
        domain = company.get("domain")
        existing_contacts = company.get("contacts", [])

        # Skip if we already have good data
        contacts_with_email = [c for c in existing_contacts if c.get("email")]
        if len(contacts_with_email) >= 2:
            logger.info(f"Apollo Paid: Skipping {domain} - already have {len(contacts_with_email)} emails")
            return StageResult(
                success=True,
                data={"skipped": True, "reason": "sufficient_contacts"},
                cost_usd=0.0,
                latency_ms=0
            )

        if not domain:
            return StageResult(
                success=False,
                data={},
                error="No domain for Apollo Paid lookup",
                latency_ms=0
            )

        try:
            # Import and use existing Apollo Paid service
            from app.services.apollo_rate_limited import ApolloRateLimitedService

            apollo = ApolloRateLimitedService()
            result = await apollo.enrich_with_credits(domain=domain)

            latency_ms = int((time.time() - start_time) * 1000)

            if result:
                new_contacts = result.get("contacts", [])
                logger.info(f"Apollo Paid: {domain} -> {len(new_contacts)} additional contacts")
                return StageResult(
                    success=True,
                    data=result,
                    cost_usd=self.cost_per_call * len(new_contacts),
                    latency_ms=latency_ms
                )
            else:
                return StageResult(
                    success=True,
                    data={},
                    cost_usd=self.cost_per_call,  # Still costs to query
                    latency_ms=latency_ms
                )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Apollo Paid error for {domain}: {e}")
            return StageResult(
                success=False,
                data={},
                error=str(e),
                latency_ms=latency_ms
            )
```

**Step 7: Commit stages**

```bash
git add backend/app/services/supervised_pipeline/stages/
git commit -m "feat: add stage wrappers for Apollo, LinkedIn, Hunter enrichment"
```

---

## Task 5: Implement Orchestrator

**Files:**
- Create: `backend/app/services/supervised_pipeline/orchestrator.py`
- Test: `backend/tests/services/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# backend/tests/services/test_orchestrator.py
"""Tests for SupervisedOrchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSupervisedOrchestrator:
    """Test SupervisedOrchestrator functionality."""

    @pytest.fixture
    def mock_state_manager(self):
        """Create mock StateManager."""
        manager = AsyncMock()
        manager.init_company = AsyncMock()
        manager.update_stage_status = AsyncMock()
        manager.sync_to_supabase = AsyncMock()
        manager.mark_complete = AsyncMock()
        manager.get_company_status = AsyncMock(return_value={})
        return manager

    @pytest.fixture
    def mock_budget_tracker(self):
        """Create mock BudgetTracker."""
        tracker = AsyncMock()
        tracker.can_proceed = AsyncMock(return_value=True)
        tracker.add_cost = AsyncMock()
        tracker.increment_processed = AsyncMock()
        tracker.get_status = AsyncMock(return_value={"spent_usd": 0.0, "limit_usd": 5.0})
        return tracker

    @pytest.mark.asyncio
    async def test_enrich_single_company(self, mock_state_manager, mock_budget_tracker):
        """Test enriching a single company through all stages."""
        from app.services.supervised_pipeline.orchestrator import SupervisedOrchestrator
        from app.services.supervised_pipeline.stages.base import StageResult

        # Mock all stages
        with patch.multiple(
            'app.services.supervised_pipeline.orchestrator',
            ApolloFreeStage=MagicMock(),
            LinkedInStage=MagicMock(),
            HunterStage=MagicMock(),
            ApolloPaidStage=MagicMock(),
        ):
            orchestrator = SupervisedOrchestrator(
                state_manager=mock_state_manager,
                budget_tracker=mock_budget_tracker,
            )

            # Mock stage execution
            mock_result = StageResult(success=True, data={}, cost_usd=0.0, latency_ms=100)
            for stage in orchestrator.stages:
                stage.execute = AsyncMock(return_value=mock_result)

            company = {"id": "test-123", "name": "Test Co", "domain": "test.com"}
            result = await orchestrator.enrich_company(company)

            assert result["success"] is True
            mock_state_manager.mark_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_parallel_batch(self, mock_state_manager, mock_budget_tracker):
        """Test processing 2 companies in parallel."""
        from app.services.supervised_pipeline.orchestrator import SupervisedOrchestrator
        from app.services.supervised_pipeline.stages.base import StageResult

        with patch.multiple(
            'app.services.supervised_pipeline.orchestrator',
            ApolloFreeStage=MagicMock(),
            LinkedInStage=MagicMock(),
            HunterStage=MagicMock(),
            ApolloPaidStage=MagicMock(),
        ):
            orchestrator = SupervisedOrchestrator(
                state_manager=mock_state_manager,
                budget_tracker=mock_budget_tracker,
            )

            mock_result = StageResult(success=True, data={}, cost_usd=0.0, latency_ms=100)
            for stage in orchestrator.stages:
                stage.execute = AsyncMock(return_value=mock_result)

            companies = [
                {"id": "test-1", "name": "Company 1", "domain": "c1.com"},
                {"id": "test-2", "name": "Company 2", "domain": "c2.com"},
            ]

            results = await orchestrator.process_batch(companies)

            assert len(results) == 2
            assert all(r["success"] for r in results)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/services/test_orchestrator.py -v`
Expected: FAIL with "No module named 'app.services.supervised_pipeline.orchestrator'"

**Step 3: Write minimal implementation**

```python
# backend/app/services/supervised_pipeline/orchestrator.py
"""
Supervised Orchestrator - Asyncio-based Enrichment Pipeline

Processes companies through 4 sequential stages with 2-company parallelism.
"""

import asyncio
from typing import Any, Dict, List

from .state_manager import StateManager
from .budget_tracker import BudgetTracker
from .stages import ApolloFreeStage, LinkedInStage, HunterStage, ApolloPaidStage
from .stages.base import StageResult

from app.core.logging import setup_logging

logger = setup_logging(__name__)


class SupervisedOrchestrator:
    """
    Orchestrates enrichment pipeline with manual checkpoints.

    Processes 2 companies in parallel, each going through 4 sequential stages:
    1. Apollo Free
    2. LinkedIn
    3. Hunter.io
    4. Apollo Paid (if needed)
    """

    def __init__(
        self,
        state_manager: StateManager,
        budget_tracker: BudgetTracker,
    ):
        """
        Initialize orchestrator.

        Args:
            state_manager: StateManager for Redis + Supabase tracking
            budget_tracker: BudgetTracker for cost limits
        """
        self.state_manager = state_manager
        self.budget_tracker = budget_tracker

        # Initialize stages in order
        self.stages = [
            ApolloFreeStage(),
            LinkedInStage(),
            HunterStage(),
            ApolloPaidStage(),
        ]

    async def enrich_company(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich a single company through all stages.

        Args:
            company: Company data from Supabase

        Returns:
            Dict with success status and enrichment results
        """
        company_id = company.get("id")
        company_name = company.get("name", "Unknown")

        logger.info(f"Starting enrichment for: {company_name}")

        # Initialize tracking
        await self.state_manager.init_company(company_id)

        accumulated_data = dict(company)
        total_cost = 0.0
        total_latency = 0

        for stage in self.stages:
            # Check budget before each stage
            if not await self.budget_tracker.can_proceed():
                logger.warning(f"Budget exceeded, stopping at {stage.name}")
                await self.state_manager.update_stage_status(
                    company_id, stage.name, "skipped"
                )
                break

            # Update status to running
            await self.state_manager.update_stage_status(
                company_id, stage.name, "running"
            )

            # Execute stage
            result: StageResult = await stage.execute(accumulated_data)

            # Update tracking
            status = "done" if result.success else "failed"
            await self.state_manager.update_stage_status(
                company_id, stage.name, status, result.cost_usd
            )

            # Sync to Supabase after each stage
            await self.state_manager.sync_to_supabase(
                company_id, stage.name, result.cost_usd
            )

            # Track costs
            total_cost += result.cost_usd
            total_latency += result.latency_ms
            await self.budget_tracker.add_cost(result.cost_usd)

            # Merge results into accumulated data
            if result.success and result.data:
                # Merge contacts
                if "contacts" in result.data:
                    existing_contacts = accumulated_data.get("contacts", [])
                    new_contacts = result.data["contacts"]
                    # Deduplicate by name
                    existing_names = {c.get("name") for c in existing_contacts}
                    for contact in new_contacts:
                        if contact.get("name") not in existing_names:
                            existing_contacts.append(contact)
                    accumulated_data["contacts"] = existing_contacts
                # Merge other data
                for key, value in result.data.items():
                    if key != "contacts" and value:
                        accumulated_data[key] = value

            if not result.success:
                logger.warning(f"{stage.name} failed for {company_name}: {result.error}")

        # Mark complete
        await self.state_manager.mark_complete(company_id)
        await self.budget_tracker.increment_processed()

        return {
            "success": True,
            "company_id": company_id,
            "company_name": company_name,
            "data": accumulated_data,
            "cost_usd": total_cost,
            "latency_ms": total_latency,
            "contacts_found": len(accumulated_data.get("contacts", [])),
            "emails_found": sum(
                1 for c in accumulated_data.get("contacts", []) if c.get("email")
            ),
        }

    async def process_batch(
        self,
        companies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of companies in parallel.

        Args:
            companies: List of company dicts (max 2 for now)

        Returns:
            List of results, one per company
        """
        logger.info(f"Processing batch of {len(companies)} companies")

        # Process in parallel using asyncio.gather
        tasks = [self.enrich_company(company) for company in companies]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                company = companies[i]
                logger.error(f"Exception enriching {company.get('name')}: {result}")
                await self.state_manager.mark_failed(
                    company.get("id"), str(result)
                )
                processed_results.append({
                    "success": False,
                    "company_id": company.get("id"),
                    "company_name": company.get("name"),
                    "error": str(result),
                })
            else:
                processed_results.append(result)

        return processed_results
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/services/test_orchestrator.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/app/services/supervised_pipeline/orchestrator.py
git add backend/tests/services/test_orchestrator.py
git commit -m "feat: add SupervisedOrchestrator with asyncio parallelism"
```

---

## Task 6: Create Terminal UI Runner

**Files:**
- Create: `backend/run_supervised_enrichment.py`

**Step 1: Write the runner script**

```python
#!/usr/bin/env python3
"""
Supervised Enrichment Runner

Interactive terminal-based enrichment with manual checkpoints.
Processes 2 companies in parallel through 4 sequential stages.

Usage:
    python run_supervised_enrichment.py --budget 5.00 --batch-size 2

Controls:
    [c] Continue to next batch
    [s] Stop and save progress
    [r] Retry failed companies
    [v] View detailed results
    [q] Quit
"""

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.live import Live
except ImportError:
    print("ERROR: pip install rich")
    sys.exit(1)

try:
    import redis.asyncio as aioredis
except ImportError:
    print("ERROR: pip install redis")
    sys.exit(1)

try:
    from supabase import create_client
except ImportError:
    print("ERROR: pip install supabase")
    sys.exit(1)

from app.services.supervised_pipeline import (
    SupervisedOrchestrator,
    StateManager,
    BudgetTracker,
)
from app.core.logging import setup_logging

logger = setup_logging(__name__)
console = Console()


async def get_unenriched_companies(supabase, limit: int) -> List[Dict[str, Any]]:
    """Fetch companies needing enrichment from Supabase."""
    result = supabase.table("dim_companies").select(
        "id", "name", "domain", "linkedin_url", "icp_tier"
    ).is_("enrichment_status", "null").order(
        "icp_tier", desc=False  # PLATINUM first
    ).limit(limit).execute()

    return result.data if result.data else []


def display_header(budget: float, batch_size: int, total_companies: int):
    """Display the header panel."""
    console.print(Panel(
        f"[bold cyan]SUPERVISED ENRICHMENT PIPELINE v2.0[/bold cyan]\n"
        f"Budget: [green]${budget:.2f}[/green] | "
        f"Parallelism: [yellow]{batch_size} companies[/yellow] | "
        f"Stages: [blue]4[/blue] | "
        f"Queued: [magenta]{total_companies}[/magenta]",
        title="[bold white]Sales Agent[/bold white]",
        border_style="cyan"
    ))


def display_batch_progress(batch_num: int, total_batches: int, companies: List[Dict]):
    """Display current batch progress."""
    console.print(f"\n[bold]📊 Batch {batch_num} of {total_batches}[/bold]")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Company", width=30)
    table.add_column("Apollo", justify="center", width=8)
    table.add_column("LinkedIn", justify="center", width=10)
    table.add_column("Hunter", justify="center", width=8)
    table.add_column("Paid", justify="center", width=6)

    for company in companies:
        table.add_row(
            company.get("name", "Unknown")[:28],
            "○", "○", "○", "○"  # Pending
        )

    console.print(table)


def display_batch_results(results: List[Dict[str, Any]], budget_status: Dict):
    """Display results after a batch completes."""
    console.print("\n[bold green]═══ BATCH COMPLETE ═══[/bold green]\n")

    table = Table(show_header=True, header_style="bold green")
    table.add_column("Company", width=28)
    table.add_column("Contacts", justify="center", width=10)
    table.add_column("Emails", justify="center", width=8)
    table.add_column("Cost", justify="right", width=8)

    for result in results:
        status_icon = "✓" if result.get("success") else "✗"
        table.add_row(
            f"{status_icon} {result.get('company_name', 'Unknown')[:25]}",
            str(result.get("contacts_found", 0)),
            str(result.get("emails_found", 0)),
            f"${result.get('cost_usd', 0):.2f}"
        )

    console.print(table)

    # Budget summary
    spent = budget_status.get("spent_usd", 0)
    limit = budget_status.get("limit_usd", 0)
    percent = budget_status.get("percent_used", 0)

    console.print(f"\n💰 Budget: [yellow]${spent:.2f}[/yellow] / ${limit:.2f} ([cyan]{percent:.1f}%[/cyan])")


def prompt_action() -> str:
    """Prompt user for next action."""
    console.print("\n[bold]What would you like to do?[/bold]")
    console.print("  [c] Continue to next batch")
    console.print("  [s] Stop and save progress")
    console.print("  [r] Retry failed companies")
    console.print("  [v] View detailed results")
    console.print("  [q] Quit\n")

    while True:
        action = console.input("[bold cyan]> [/bold cyan]").strip().lower()
        if action in ("c", "s", "r", "v", "q"):
            return action
        console.print("[red]Invalid option. Please enter c, s, r, v, or q.[/red]")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Supervised Enrichment Pipeline")
    parser.add_argument("--budget", type=float, default=5.0, help="Budget limit in USD")
    parser.add_argument("--batch-size", type=int, default=2, help="Companies per batch")
    parser.add_argument("--limit", type=int, default=100, help="Max companies to process")
    args = parser.parse_args()

    # Initialize clients
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis = aioredis.from_url(redis_url)

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        console.print("[red]ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY required[/red]")
        sys.exit(1)

    supabase = create_client(supabase_url, supabase_key)

    # Fetch companies
    companies = await get_unenriched_companies(supabase, args.limit)
    if not companies:
        console.print("[yellow]No companies need enrichment.[/yellow]")
        return

    # Initialize pipeline
    batch_id = f"batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    state_manager = StateManager(redis=redis, supabase=supabase)
    budget_tracker = BudgetTracker(redis=redis, batch_id=batch_id, limit_usd=args.budget)
    await budget_tracker.init_batch(total_companies=len(companies))

    orchestrator = SupervisedOrchestrator(
        state_manager=state_manager,
        budget_tracker=budget_tracker,
    )

    # Display header
    display_header(args.budget, args.batch_size, len(companies))

    # Process in batches
    batch_num = 0
    total_batches = (len(companies) + args.batch_size - 1) // args.batch_size
    all_results = []
    failed_companies = []

    while companies:
        batch_num += 1
        batch = companies[:args.batch_size]
        companies = companies[args.batch_size:]

        # Check budget
        if not await budget_tracker.can_proceed():
            console.print("[yellow]Budget exceeded. Stopping.[/yellow]")
            break

        # Show progress
        display_batch_progress(batch_num, total_batches, batch)

        # Process batch
        with console.status("[bold green]Processing...[/bold green]"):
            results = await orchestrator.process_batch(batch)

        # Collect failures
        for result in results:
            if not result.get("success"):
                failed_companies.append(result)
            all_results.append(result)

        # Display results
        budget_status = await budget_tracker.get_status()
        display_batch_results(results, budget_status)

        # Prompt for action
        action = prompt_action()

        if action == "c":
            continue
        elif action == "s":
            console.print("[green]Progress saved. Stopping.[/green]")
            break
        elif action == "r":
            if failed_companies:
                console.print(f"[yellow]Retrying {len(failed_companies)} failed companies...[/yellow]")
                # Re-add to queue
                companies = [{"id": f["company_id"], "name": f["company_name"]} for f in failed_companies] + companies
                failed_companies = []
            else:
                console.print("[green]No failed companies to retry.[/green]")
        elif action == "v":
            console.print_json(data=results)
        elif action == "q":
            console.print("[yellow]Quitting. Progress saved.[/yellow]")
            break

    # Final summary
    console.print("\n[bold cyan]═══ SESSION COMPLETE ═══[/bold cyan]")
    console.print(f"Total processed: {len(all_results)}")
    console.print(f"Successful: {sum(1 for r in all_results if r.get('success'))}")
    console.print(f"Failed: {len(failed_companies)}")

    budget_status = await budget_tracker.get_status()
    console.print(f"Total cost: ${budget_status.get('spent_usd', 0):.2f}")

    # Cleanup
    await redis.close()


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Make executable and test**

```bash
chmod +x backend/run_supervised_enrichment.py
cd backend && python run_supervised_enrichment.py --help
```

Expected output: Help message with --budget, --batch-size, --limit options

**Step 3: Commit**

```bash
git add backend/run_supervised_enrichment.py
git commit -m "feat: add interactive terminal runner for supervised enrichment"
```

---

## Task 7: Create Slash Commands

**Files:**
- Create: `.claude/commands/enrich-supervised.md`
- Create: `.claude/commands/enrich-status.md`
- Update: `.claude/commands/enrich-single.md`
- Create: `.claude/commands/enrich-retry-failed.md`

**Step 1: Create enrich-supervised command**

```markdown
# /enrich-supervised

Start the supervised enrichment pipeline with Claude guidance.

## Usage
```
/enrich-supervised [--budget 5.00] [--batch-size 2]
```

## Workflow

1. **Query Supabase** for unenriched companies
2. **Launch terminal pipeline** with specified budget
3. **Monitor progress** and interpret results
4. **Guide next actions** based on outcomes

## Execution

```bash
cd backend
source ../venv/bin/activate
python run_supervised_enrichment.py --budget $ARG_BUDGET --batch-size $ARG_BATCH_SIZE
```

## After Each Batch

Review results and suggest:
- Continue if success rate > 80%
- Investigate if errors occur
- Stop if budget approaching limit

## Example Session

```
You: /enrich-supervised --budget 3.00

Claude: Starting supervised enrichment with $3.00 budget...

[Launches pipeline, monitors output]

Batch 1 complete:
- Acme HVAC: 3 contacts, 2 emails ($0.01)
- Pacific Solar: 1 contact, 1 email ($0.01)

Budget: $0.02 / $3.00 (0.7%)
Success rate: 100%

Recommendation: Continue [c]
```
```

**Step 2: Create enrich-status command**

```markdown
# /enrich-status

Check current enrichment progress across all companies.

## Usage
```
/enrich-status
```

## What This Shows

1. **Overall Progress**
   - Total companies in Supabase
   - Completed enrichments
   - In-progress (if any)
   - Failed (needs retry)
   - Remaining

2. **Recent Batches**
   - Last 5 batch IDs with status
   - Cost per batch

3. **Cost Summary**
   - Total spent today
   - Remaining budget

## Execution

Query Supabase:
```sql
SELECT
  COUNT(*) as total,
  COUNT(*) FILTER (WHERE enrichment_status = 'completed') as completed,
  COUNT(*) FILTER (WHERE enrichment_status = 'failed') as failed,
  COUNT(*) FILTER (WHERE enrichment_status IS NULL) as pending
FROM dim_companies;
```

Query Redis for active batches:
```bash
redis-cli KEYS "enrichment:batch:*"
```
```

**Step 3: Create enrich-retry-failed command**

```markdown
# /enrich-retry-failed

Retry all companies that failed in previous enrichment batches.

## Usage
```
/enrich-retry-failed [--budget 2.00]
```

## Workflow

1. **Find failed companies** from:
   - Supabase: `enrichment_status = 'failed'`
   - CSV: `FAILED_ENRICHMENT.csv`

2. **Reset status** to pending

3. **Re-run through pipeline** with exponential backoff

## Execution

```bash
cd backend
source ../venv/bin/activate

# Reset failed companies
python -c "
from supabase import create_client
import os

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
supabase.table('dim_companies').update({
    'enrichment_status': None,
    'enrichment_error': None
}).eq('enrichment_status', 'failed').execute()
print('Reset complete')
"

# Re-run enrichment
python run_supervised_enrichment.py --budget $ARG_BUDGET
```
```

**Step 4: Commit slash commands**

```bash
git add .claude/commands/enrich-supervised.md
git add .claude/commands/enrich-status.md
git add .claude/commands/enrich-retry-failed.md
git commit -m "feat: add Claude Code slash commands for supervised enrichment"
```

---

## Task 8: Update Module __init__.py

**Files:**
- Modify: `backend/app/services/supervised_pipeline/__init__.py`

**Step 1: Update exports**

```python
# backend/app/services/supervised_pipeline/__init__.py
"""
Supervised Enrichment Pipeline

Interactive terminal-based enrichment with manual checkpoints.
Processes 2 companies in parallel through 4 sequential stages:
1. Apollo Free - Company enrichment (free tier)
2. LinkedIn - Company page scraping via Browserbase
3. Hunter.io - Email finding ($0.01/lookup)
4. Apollo Paid - Additional contacts if needed ($0.05/credit)

Usage:
    python run_supervised_enrichment.py --budget 5.00 --batch-size 2

Claude Code Commands:
    /enrich-supervised - Start pipeline with guidance
    /enrich-status - Check progress
    /enrich-retry-failed - Retry failures
"""

from .orchestrator import SupervisedOrchestrator
from .state_manager import StateManager
from .budget_tracker import BudgetTracker
from .stages import (
    BaseStage,
    StageResult,
    ApolloFreeStage,
    LinkedInStage,
    HunterStage,
    ApolloPaidStage,
)

__all__ = [
    "SupervisedOrchestrator",
    "StateManager",
    "BudgetTracker",
    "BaseStage",
    "StageResult",
    "ApolloFreeStage",
    "LinkedInStage",
    "HunterStage",
    "ApolloPaidStage",
]
```

**Step 2: Commit**

```bash
git add backend/app/services/supervised_pipeline/__init__.py
git commit -m "docs: update supervised_pipeline module docstring and exports"
```

---

## Task 9: Final Integration Test

**Files:**
- Test: `backend/tests/integration/test_supervised_pipeline.py`

**Step 1: Write integration test**

```python
# backend/tests/integration/test_supervised_pipeline.py
"""Integration tests for supervised enrichment pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSupervisedPipelineIntegration:
    """Integration tests for full pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_two_companies(self):
        """Test processing 2 companies through all stages."""
        from app.services.supervised_pipeline import (
            SupervisedOrchestrator,
            StateManager,
            BudgetTracker,
        )
        from app.services.supervised_pipeline.stages.base import StageResult

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.hset = AsyncMock()
        mock_redis.hget = AsyncMock(return_value=b"0.0")
        mock_redis.hgetall = AsyncMock(return_value={})
        mock_redis.hincrby = AsyncMock()
        mock_redis.hincrbyfloat = AsyncMock()
        mock_redis.delete = AsyncMock()

        # Mock Supabase
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute = MagicMock()

        # Create components
        state_manager = StateManager(redis=mock_redis, supabase=mock_supabase)
        budget_tracker = BudgetTracker(redis=mock_redis, batch_id="test-batch", limit_usd=5.0)
        await budget_tracker.init_batch(total_companies=2)

        orchestrator = SupervisedOrchestrator(
            state_manager=state_manager,
            budget_tracker=budget_tracker,
        )

        # Mock stage execution
        mock_result = StageResult(
            success=True,
            data={"contacts": [{"name": "John Doe", "email": "john@test.com"}]},
            cost_usd=0.01,
            latency_ms=100
        )

        for stage in orchestrator.stages:
            stage.execute = AsyncMock(return_value=mock_result)

        # Test companies
        companies = [
            {"id": "company-1", "name": "Test Company 1", "domain": "test1.com"},
            {"id": "company-2", "name": "Test Company 2", "domain": "test2.com"},
        ]

        # Process batch
        results = await orchestrator.process_batch(companies)

        # Verify
        assert len(results) == 2
        assert all(r["success"] for r in results)
        assert all(r["contacts_found"] >= 1 for r in results)

        # Verify state manager was called
        assert mock_redis.hset.call_count > 0
        assert mock_supabase.table.called
```

**Step 2: Run integration test**

Run: `cd backend && pytest tests/integration/test_supervised_pipeline.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/integration/test_supervised_pipeline.py
git commit -m "test: add integration test for supervised pipeline"
```

---

## Task 10: Final Commit and Summary

**Step 1: Verify all tests pass**

```bash
cd backend && pytest tests/services/test_state_manager.py tests/services/test_budget_tracker.py tests/services/test_orchestrator.py tests/integration/test_supervised_pipeline.py -v
```

Expected: All tests PASS

**Step 2: Final commit with design doc**

```bash
git add docs/plans/2025-12-02-supervised-enrichment-design.md
git commit -m "docs: add supervised enrichment design document"
```

**Step 3: Summary commit**

```bash
git log --oneline -10
```

Expected commits:
1. `docs: add supervised enrichment design document`
2. `test: add integration test for supervised pipeline`
3. `docs: update supervised_pipeline module docstring and exports`
4. `feat: add Claude Code slash commands for supervised enrichment`
5. `feat: add interactive terminal runner for supervised enrichment`
6. `feat: add SupervisedOrchestrator with asyncio parallelism`
7. `feat: add stage wrappers for Apollo, LinkedIn, Hunter enrichment`
8. `feat: add BudgetTracker for per-batch cost limits`
9. `feat: add StateManager for Redis + Supabase tracking`
10. `feat: create supervised_pipeline module structure`

---

## Success Criteria Checklist

- [ ] Module structure created (`supervised_pipeline/`)
- [ ] StateManager tracks progress in Redis + Supabase
- [ ] BudgetTracker enforces per-batch limits
- [ ] 4 stage wrappers created and tested
- [ ] SupervisedOrchestrator processes 2 companies in parallel
- [ ] Terminal runner with interactive controls (c/s/r/v/q)
- [ ] 4 slash commands created for Claude Code
- [ ] All unit tests pass
- [ ] Integration test passes
- [ ] Design doc committed
