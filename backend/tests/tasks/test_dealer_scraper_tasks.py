"""
Tests for dealer-scraper pipeline Celery tasks.

Tests cover:
- Domain verification with mock HTTP responses
- Push to Supabase with mock client
- Pipeline orchestration
- Stats retrieval

Note: Uses importlib to directly load dealer_scraper_tasks module
without going through app.tasks.__init__.py which has complex dependencies.
"""

import os
from pathlib import Path
import sys
import importlib.util

# Set mock DATABASE_URL BEFORE any imports
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from dotenv import load_dotenv

# Load environment variables BEFORE importing app modules
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sqlite3
import tempfile
from datetime import datetime


def load_dealer_scraper_module():
    """
    Load dealer_scraper_tasks directly without going through app.tasks.__init__.py.
    This avoids the complex import chain that requires database connections.
    """
    # First, ensure celery_app is loadable (mock if needed)
    import types
    from functools import wraps

    def mock_task_decorator(**task_kwargs):
        """Mock Celery task decorator that handles bind=True."""
        def decorator(func):
            if task_kwargs.get('bind', False):
                # For bound tasks, strip the 'self' argument
                @wraps(func)
                def wrapper(*args, **kwargs):
                    return func(None, *args, **kwargs)
                return wrapper
            return func
        return decorator

    # Create a mock celery_app module with the essential decorators
    mock_celery = types.ModuleType('app.celery_app')
    mock_celery.celery_app = MagicMock()
    mock_celery.celery_app.task = mock_task_decorator
    sys.modules['app.celery_app'] = mock_celery

    # Create mock app.core.logging
    mock_logging = types.ModuleType('app.core.logging')
    mock_logging.setup_logging = lambda name: MagicMock()
    sys.modules['app.core.logging'] = mock_logging
    sys.modules['app.core'] = types.ModuleType('app.core')

    # Now load the dealer_scraper_tasks module directly
    module_path = Path(__file__).parent.parent.parent / 'app' / 'tasks' / 'dealer_scraper_tasks.py'
    spec = importlib.util.spec_from_file_location(
        "app.tasks.dealer_scraper_tasks",
        module_path
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules['app.tasks.dealer_scraper_tasks'] = module
    spec.loader.exec_module(module)
    return module


# Load module once at import time
_dealer_module = load_dealer_scraper_module()


class TestVerifyDealerDomainsTask:
    """Tests for verify_dealer_domains_task."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary SQLite database with test data."""
        db_path = tmp_path / "test_pipeline.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create contractors table
        cursor.execute("""
            CREATE TABLE contractors (
                id INTEGER PRIMARY KEY,
                company_name TEXT,
                normalized_name TEXT,
                primary_domain TEXT,
                website_url TEXT,
                primary_phone TEXT,
                primary_email TEXT,
                street TEXT,
                city TEXT,
                state TEXT,
                zip TEXT,
                company_linkedin_url TEXT,
                year_founded INTEGER,
                employee_count INTEGER,
                estimated_revenue TEXT,
                icp_score INTEGER,
                icp_tier TEXT,
                is_resimercial INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0,
                pushed_to_sales_agent INTEGER DEFAULT 0,
                pushed_at TEXT,
                domain_verified_at TEXT,
                domain_is_valid INTEGER,
                domain_check_status TEXT
            )
        """)

        # Insert test companies
        test_companies = [
            (1, "Good Roofing Co", "good-roofing-co", "goodroofing.com", 0, None, None, None),
            (2, "Better HVAC Inc", "better-hvac-inc", "betterhvac.com", 0, None, None, None),
            (3, "Sheet Metal Works", "sheet-metal-works", "sheetmetal.com", 0, None, None, None),  # ICP filter
            (4, "Already Verified", "already-verified", "verified.com", 0, "2024-01-01", 1, "200"),
        ]

        for company in test_companies:
            cursor.execute("""
                INSERT INTO contractors (
                    id, company_name, normalized_name, primary_domain, is_deleted,
                    domain_verified_at, domain_is_valid, domain_check_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, company)

        conn.commit()
        conn.close()
        return str(db_path)

    @pytest.mark.asyncio
    async def test_verify_domains_batch_success(self):
        """Test batch domain verification with mock HTTP responses."""
        _verify_domains_batch = _dealer_module._verify_domains_batch

        domains = ["goodroofing.com", "betterhvac.com"]

        with patch.object(_dealer_module, "httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.url = "https://goodroofing.com"

            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_httpx.AsyncClient.return_value = mock_instance

            results = await _verify_domains_batch(domains)

        assert len(results) == 2
        for result in results:
            assert result["valid"] is True
            assert result["status"] == 200

    @pytest.mark.asyncio
    async def test_verify_single_domain_timeout(self):
        """Test domain verification handling timeout."""
        import httpx
        _verify_single_domain = _dealer_module._verify_single_domain

        with patch.object(_dealer_module, "httpx") as mock_httpx:
            mock_httpx.TimeoutException = httpx.TimeoutException
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_httpx.AsyncClient.return_value = mock_instance

            result = await _verify_single_domain("slow-domain.com")

        assert result["valid"] is False
        assert result["status"] == "timeout"

    def test_verify_task_filters_icp_excluded(self, temp_db):
        """Test that ICP-filtered companies are excluded from verification."""
        verify_dealer_domains_task = _dealer_module.verify_dealer_domains_task

        with patch.object(_dealer_module, "asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = [
                {"domain": "goodroofing.com", "valid": True, "status": 200},
                {"domain": "betterhvac.com", "valid": True, "status": 200},
            ]

            result = verify_dealer_domains_task(batch_size=10, db_path=temp_db)

        assert result["status"] == "complete"
        # Sheet Metal Works should be filtered out by ICP filter
        assert result["checked"] == 2
        assert result["valid"] == 2

    def test_verify_task_no_unverified_domains(self, tmp_path):
        """Test handling when no unverified domains exist."""
        db_path = tmp_path / "empty_pipeline.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE contractors (
                id INTEGER PRIMARY KEY,
                company_name TEXT,
                primary_domain TEXT,
                is_deleted INTEGER DEFAULT 0,
                domain_verified_at TEXT,
                domain_is_valid INTEGER,
                domain_check_status TEXT
            )
        """)

        # Insert already verified company
        cursor.execute("""
            INSERT INTO contractors (id, company_name, primary_domain, is_deleted, domain_verified_at, domain_is_valid)
            VALUES (1, 'Verified Co', 'verified.com', 0, '2024-01-01', 1)
        """)

        conn.commit()
        conn.close()

        verify_dealer_domains_task = _dealer_module.verify_dealer_domains_task

        result = verify_dealer_domains_task(batch_size=10, db_path=str(db_path))

        assert result["status"] == "complete"
        assert result["checked"] == 0

    def test_verify_task_db_not_found(self):
        """Test handling when database doesn't exist."""
        verify_dealer_domains_task = _dealer_module.verify_dealer_domains_task

        result = verify_dealer_domains_task(db_path="/nonexistent/path.db")

        assert result["status"] == "error"
        assert "not found" in result["error"]


class TestPushVerifiedDealersTask:
    """Tests for push_verified_dealers_task."""

    @pytest.fixture
    def temp_db_with_verified(self, tmp_path):
        """Create a temp SQLite database with verified companies."""
        db_path = tmp_path / "test_pipeline.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE contractors (
                id INTEGER PRIMARY KEY,
                company_name TEXT,
                normalized_name TEXT,
                primary_domain TEXT,
                website_url TEXT,
                primary_phone TEXT,
                primary_email TEXT,
                street TEXT,
                city TEXT,
                state TEXT,
                zip TEXT,
                company_linkedin_url TEXT,
                year_founded INTEGER,
                employee_count INTEGER,
                estimated_revenue TEXT,
                icp_score INTEGER,
                icp_tier TEXT,
                is_resimercial INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0,
                pushed_to_sales_agent INTEGER DEFAULT 0,
                pushed_at TEXT,
                domain_verified_at TEXT,
                domain_is_valid INTEGER
            )
        """)

        # Insert verified companies
        test_companies = [
            (1, "Verified Roofing", "verified-roofing", "verifiedroofing.com",
             "https://verifiedroofing.com", "555-1234", "info@verifiedroofing.com",
             "123 Main St", "Orlando", "FL", "32801", None, 2010, 50, "$5M",
             75, "GOLD", 0, 0, 0, None, "2024-01-01T00:00:00Z", 1),
            (2, "Another HVAC", "another-hvac", "anotherhvac.com",
             "https://anotherhvac.com", "555-5678", "info@anotherhvac.com",
             "456 Oak Ave", "Tampa", "FL", "33601", None, 2015, 25, "$2M",
             60, "SILVER", 0, 0, 0, None, "2024-01-01T00:00:00Z", 1),
        ]

        for company in test_companies:
            cursor.execute("""
                INSERT INTO contractors (
                    id, company_name, normalized_name, primary_domain,
                    website_url, primary_phone, primary_email,
                    street, city, state, zip, company_linkedin_url,
                    year_founded, employee_count, estimated_revenue,
                    icp_score, icp_tier, is_resimercial, is_deleted, pushed_to_sales_agent,
                    pushed_at, domain_verified_at, domain_is_valid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, company)

        conn.commit()
        conn.close()
        return str(db_path)

    @pytest.fixture
    def mock_supabase_client(self):
        """Create a mock Supabase client."""
        client = MagicMock()

        def create_table_mock(table_name):
            table = MagicMock()

            if table_name == "dim_companies":
                # Select for dedup check
                select_mock = MagicMock()
                select_mock.eq = MagicMock(return_value=select_mock)
                select_mock.execute = MagicMock(return_value=MagicMock(data=[]))

                # Insert mock
                insert_mock = MagicMock()
                insert_mock.execute = MagicMock(return_value=MagicMock(data=[{
                    "company_id": "test-uuid-123"
                }]))

                table.select = MagicMock(return_value=select_mock)
                table.insert = MagicMock(return_value=insert_mock)

            return table

        client.table = MagicMock(side_effect=create_table_mock)
        return client

    def test_push_dry_run(self, temp_db_with_verified, mock_supabase_client):
        """Test dry run mode - preview without writing."""
        push_verified_dealers_task = _dealer_module.push_verified_dealers_task

        # Mock the supabase module at import time
        mock_supabase_module = MagicMock()
        mock_supabase_module.create_client = MagicMock(return_value=mock_supabase_client)

        with patch.dict(sys.modules, {'supabase': mock_supabase_module}):
            with patch.dict(os.environ, {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_SERVICE_KEY": "test-key"
            }):
                result = push_verified_dealers_task(
                    batch_size=5,
                    db_path=temp_db_with_verified,
                    dry_run=True
                )

        assert result["status"] == "complete"
        assert result["dry_run"] is True
        assert result["pushed"] == 0  # Nothing pushed in dry run

    def test_push_skips_duplicates(self, temp_db_with_verified):
        """Test that duplicates are skipped."""
        push_verified_dealers_task = _dealer_module.push_verified_dealers_task

        mock_client = MagicMock()

        def create_table_mock(table_name):
            table = MagicMock()
            if table_name == "dim_companies":
                select_mock = MagicMock()
                # Return existing company for dedup check
                select_mock.eq = MagicMock(return_value=select_mock)
                select_mock.execute = MagicMock(return_value=MagicMock(data=[{
                    "company_id": "existing-uuid"
                }]))
                table.select = MagicMock(return_value=select_mock)
            return table

        mock_client.table = MagicMock(side_effect=create_table_mock)

        mock_supabase_module = MagicMock()
        mock_supabase_module.create_client = MagicMock(return_value=mock_client)

        with patch.dict(sys.modules, {'supabase': mock_supabase_module}):
            with patch.dict(os.environ, {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_SERVICE_KEY": "test-key"
            }):
                result = push_verified_dealers_task(
                    batch_size=5,
                    db_path=temp_db_with_verified
                )

        assert result["skipped"] == 2  # Both companies are "duplicates"
        assert result["pushed"] == 0

    def test_push_missing_credentials(self, temp_db_with_verified):
        """Test handling when Supabase credentials are missing."""
        push_verified_dealers_task = _dealer_module.push_verified_dealers_task

        with patch.dict(os.environ, {}, clear=True):
            result = push_verified_dealers_task(db_path=temp_db_with_verified)

        assert result["status"] == "error"
        assert "credentials" in result["error"]


class TestGetDealerPipelineStats:
    """Tests for get_dealer_pipeline_stats."""

    @pytest.fixture
    def temp_db_with_stats(self, tmp_path):
        """Create a temp SQLite database with various pipeline stages."""
        db_path = tmp_path / "stats_pipeline.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE contractors (
                id INTEGER PRIMARY KEY,
                primary_domain TEXT,
                is_deleted INTEGER DEFAULT 0,
                pushed_to_sales_agent INTEGER DEFAULT 0,
                domain_verified_at TEXT,
                domain_is_valid INTEGER
            )
        """)

        # Insert companies at various stages
        stages = [
            # Unverified (2)
            (1, "unverified1.com", 0, 0, None, None),
            (2, "unverified2.com", 0, 0, None, None),
            # Verified valid (3)
            (3, "valid1.com", 0, 0, "2024-01-01", 1),
            (4, "valid2.com", 0, 0, "2024-01-01", 1),
            (5, "valid3.com", 0, 0, "2024-01-01", 1),
            # Verified invalid (1)
            (6, "invalid.com", 0, 0, "2024-01-01", 0),
            # Pushed (2)
            (7, "pushed1.com", 0, 1, "2024-01-01", 1),
            (8, "pushed2.com", 0, 1, "2024-01-01", 1),
            # Deleted (1) - should not count
            (9, "deleted.com", 1, 0, None, None),
        ]

        for stage in stages:
            cursor.execute("""
                INSERT INTO contractors (id, primary_domain, is_deleted, pushed_to_sales_agent, domain_verified_at, domain_is_valid)
                VALUES (?, ?, ?, ?, ?, ?)
            """, stage)

        conn.commit()
        conn.close()
        return str(db_path)

    def test_stats_complete(self, temp_db_with_stats):
        """Test that stats are correctly calculated."""
        get_dealer_pipeline_stats = _dealer_module.get_dealer_pipeline_stats

        result = get_dealer_pipeline_stats(db_path=temp_db_with_stats)

        assert result["status"] == "complete"
        assert result["total"] == 8  # Excludes deleted
        assert result["with_domain"] == 8
        assert result["unverified"] == 2
        assert result["verified_valid"] == 5  # 3 valid + 2 pushed
        assert result["verified_invalid"] == 1
        assert result["pushed"] == 2
        assert result["pending_push"] == 3  # verified valid but not pushed

    def test_stats_db_not_found(self):
        """Test handling when database doesn't exist."""
        get_dealer_pipeline_stats = _dealer_module.get_dealer_pipeline_stats

        result = get_dealer_pipeline_stats(db_path="/nonexistent/path.db")

        assert result["status"] == "error"
        assert "not found" in result["error"]


class TestRunDealerEnrichmentPipeline:
    """Tests for run_dealer_enrichment_pipeline."""

    def test_pipeline_triggers_enrichment(self):
        """Test that pipeline triggers enrichment task."""
        run_dealer_enrichment_pipeline = _dealer_module.run_dealer_enrichment_pipeline

        company_ids = ["uuid-1", "uuid-2", "uuid-3"]

        # Mock the enrichment task that's imported inside the function
        mock_enrichment = MagicMock()
        mock_enrichment.delay = MagicMock()

        with patch.dict(sys.modules, {
            'app.tasks.enrichment_tasks': MagicMock(run_website_enrichment_batch=mock_enrichment)
        }):
            result = run_dealer_enrichment_pipeline(company_ids)

        assert result["status"] == "triggered"
        assert result["companies"] == 3
        mock_enrichment.delay.assert_called_once_with(batch_size=3)

    def test_pipeline_skips_empty_list(self):
        """Test that pipeline skips when no company IDs provided."""
        run_dealer_enrichment_pipeline = _dealer_module.run_dealer_enrichment_pipeline

        # Need to mock enrichment_tasks since import happens before empty check
        mock_enrichment = MagicMock()
        mock_enrichment.delay = MagicMock()

        with patch.dict(sys.modules, {
            'app.tasks.enrichment_tasks': MagicMock(run_website_enrichment_batch=mock_enrichment)
        }):
            result = run_dealer_enrichment_pipeline([])

        assert result["status"] == "skipped"
        assert "No company" in result["reason"]
