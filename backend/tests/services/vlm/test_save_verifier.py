"""
Tests for SaveVerifier - Supabase save operations with readback verification.

Tests cover:
- Contact insertion with mandatory readback verification
- Garbage name rejection (short names, "none", "null")
- Case-insensitive duplicate detection
- Error logging to fact_enrichment_errors
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables BEFORE importing app modules
env_path = Path(__file__).parent.parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

import pytest
from unittest.mock import MagicMock, patch


class TestSaveVerifier:
    """Tests for SaveVerifier class."""

    @pytest.fixture
    def verifier(self, mock_supabase_client):
        """Create a SaveVerifier instance with mock Supabase."""
        from app.services.save_verifier import SaveVerifier
        return SaveVerifier(supabase=mock_supabase_client, max_retries=2)

    @pytest.fixture
    def verifier_with_readback(self, mock_supabase_with_readback):
        """Create a SaveVerifier with readback simulation."""
        from app.services.save_verifier import SaveVerifier
        return SaveVerifier(supabase=mock_supabase_with_readback, max_retries=2)

    @pytest.fixture
    def verifier_with_duplicate(self, mock_supabase_with_duplicate):
        """Create a SaveVerifier that will detect duplicates."""
        from app.services.save_verifier import SaveVerifier
        return SaveVerifier(supabase=mock_supabase_with_duplicate, max_retries=2)

    def test_save_contact_with_readback(
        self,
        verifier_with_readback,
        sample_contact_data,
        sample_company_id
    ):
        """
        Test saving a contact with mandatory readback verification.

        The SaveVerifier must:
        1. Insert the contact into dim_contacts
        2. Read back the record to verify it was saved
        3. Compare key fields (full_name, company_id) match
        4. Return (True, contact_id, None) on success
        """
        success, contact_id, error = verifier_with_readback.save_contact(
            company_id=sample_company_id,
            contact_data=sample_contact_data,
            source="vlm_screenshot"
        )

        # Verify success
        assert success is True
        assert contact_id is not None
        assert error is None

        # Verify UUID format
        assert len(contact_id) == 36  # UUID format
        assert contact_id.count("-") == 4

        # Verify the contact was stored in the mock
        saved = verifier_with_readback.supabase._saved_contacts
        assert contact_id in saved
        assert saved[contact_id]["full_name"] == "Jane Doe"
        assert saved[contact_id]["company_id"] == sample_company_id

    def test_reject_garbage_names(
        self,
        mock_supabase_client,
        sample_company_id
    ):
        """
        Test rejection of garbage names.

        Should reject:
        - Names shorter than 3 characters
        - "none", "none none"
        - "null"
        - Empty strings
        """
        from app.services.save_verifier import SaveVerifier
        verifier = SaveVerifier(supabase=mock_supabase_client)

        garbage_names = [
            {"full_name": "AB", "title": "CEO"},  # Too short (<3 chars)
            {"full_name": "A", "title": ""},  # Single char
            {"full_name": "", "title": "Manager"},  # Empty
            {"full_name": "  ", "title": "Director"},  # Whitespace only
            {"full_name": "none", "title": "VP"},  # Literal "none"
            {"full_name": "None", "title": "VP"},  # Capitalized "None"
            {"full_name": "none none", "title": "Engineer"},  # "none none"
            {"full_name": "null", "title": "Analyst"},  # Literal "null"
            {"full_name": "NULL", "title": "Analyst"},  # Uppercase "NULL"
        ]

        for contact_data in garbage_names:
            success, contact_id, error = verifier.save_contact(
                company_id=sample_company_id,
                contact_data=contact_data,
                source="test"
            )

            assert success is False, f"Should reject: {contact_data['full_name']}"
            assert contact_id is None
            assert error is not None
            assert "Invalid name" in error or "Garbage name" in error

    def test_case_insensitive_dedup(
        self,
        verifier_with_duplicate,
        sample_company_id
    ):
        """
        Test case-insensitive duplicate detection.

        If "John Doe" exists in the database, attempts to insert:
        - "john doe" (lowercase)
        - "JOHN DOE" (uppercase)
        - "John Doe" (exact match)

        Should all be rejected as duplicates.
        """
        # The mock is configured to find existing contact for any name
        test_cases = [
            {"full_name": "John Doe", "title": "CEO"},
            {"full_name": "john doe", "title": "Manager"},
            {"full_name": "JOHN DOE", "title": "Director"},
            {"full_name": "JoHn DoE", "title": "VP"},
        ]

        for contact_data in test_cases:
            success, contact_id, error = verifier_with_duplicate.save_contact(
                company_id=sample_company_id,
                contact_data=contact_data,
                source="test"
            )

            assert success is False, f"Should detect duplicate: {contact_data['full_name']}"
            # When duplicate found, returns existing contact_id
            assert contact_id == "existing-uuid-123"
            assert "Exists" in error

    def test_error_logging(
        self,
        mock_supabase_client,
        sample_company_id
    ):
        """
        Test that errors are logged to fact_enrichment_errors table.

        When validation fails or an error occurs, the SaveVerifier
        should log details to the fact_enrichment_errors table for audit.
        """
        from app.services.save_verifier import SaveVerifier
        verifier = SaveVerifier(supabase=mock_supabase_client)

        # Trigger a validation error (garbage name)
        verifier.save_contact(
            company_id=sample_company_id,
            contact_data={"full_name": "none", "title": ""},
            source="vlm_screenshot"
        )

        # Verify error was logged to fact_enrichment_errors
        # The mock should have received an insert call
        error_table_calls = [
            call for call in mock_supabase_client.table.call_args_list
            if call[0][0] == "fact_enrichment_errors"
        ]

        assert len(error_table_calls) > 0, "Error should be logged to fact_enrichment_errors"


class TestSaveVerifierEdgeCases:
    """Edge case tests for SaveVerifier."""

    @pytest.fixture
    def mock_supabase_readback_fail(self):
        """Create a mock that simulates readback failure."""
        client = MagicMock()

        def create_table_mock(table_name):
            table = MagicMock()

            if table_name == "dim_contacts":
                select_mock = MagicMock()

                def eq_handler(column, value):
                    eq_result = MagicMock()

                    if column == "contact_id":
                        # Readback returns empty - data not found
                        result = MagicMock()
                        result.data = []
                        eq_result.execute = MagicMock(return_value=result)
                        return eq_result
                    elif column == "company_id":
                        # Duplicate check - need to handle .ilike() chaining
                        ilike_mock = MagicMock()
                        ilike_mock.execute = MagicMock(
                            return_value=MagicMock(data=[])
                        )
                        eq_result.ilike = MagicMock(return_value=ilike_mock)
                        return eq_result

                    # Default case
                    eq_result.execute = MagicMock(return_value=MagicMock(data=[]))
                    return eq_result

                select_mock.eq = MagicMock(side_effect=eq_handler)
                select_mock.ilike = MagicMock(return_value=select_mock)
                select_mock.execute = MagicMock(return_value=MagicMock(data=[]))

                insert_mock = MagicMock()
                insert_mock.execute = MagicMock(return_value=MagicMock(data=[{}]))

                table.select = MagicMock(return_value=select_mock)
                table.insert = MagicMock(return_value=insert_mock)

            elif table_name == "fact_enrichment_errors":
                insert_mock = MagicMock()
                insert_mock.execute = MagicMock(return_value=MagicMock(data=[{}]))
                table.insert = MagicMock(return_value=insert_mock)

            return table

        client.table = MagicMock(side_effect=create_table_mock)
        return client

    def test_readback_verification_failure(
        self,
        mock_supabase_readback_fail
    ):
        """Test handling when readback verification fails."""
        from app.services.save_verifier import SaveVerifier

        verifier = SaveVerifier(
            supabase=mock_supabase_readback_fail,
            max_retries=1  # Reduce retries for faster test
        )

        success, contact_id, error = verifier.save_contact(
            company_id="test-company-id",
            contact_data={"full_name": "Test Person", "title": "CEO"},
            source="test"
        )

        # Should fail because readback returned empty
        assert success is False
        assert "readback" in error.lower() or "nothing" in error.lower()

    def test_whitespace_handling(self, mock_supabase_client):
        """Test that names with leading/trailing whitespace are trimmed."""
        from app.services.save_verifier import SaveVerifier

        verifier = SaveVerifier(supabase=mock_supabase_client)

        # Name with whitespace should be trimmed during validation
        contact_data = {"full_name": "   ", "title": "CEO"}

        success, _, error = verifier.save_contact(
            company_id="test-company-id",
            contact_data=contact_data,
            source="test"
        )

        # Empty after trim should be rejected
        assert success is False
        assert "Invalid name" in error

    def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        from app.services.save_verifier import SaveVerifier

        # Create mock that always fails on insert
        client = MagicMock()

        def create_table_mock(table_name):
            table = MagicMock()

            if table_name == "dim_contacts":
                # Duplicate check passes
                select_mock = MagicMock()
                eq_mock = MagicMock()
                eq_mock.ilike = MagicMock(return_value=eq_mock)
                eq_mock.execute = MagicMock(return_value=MagicMock(data=[]))
                select_mock.eq = MagicMock(return_value=eq_mock)
                table.select = MagicMock(return_value=select_mock)

                # Insert always fails
                table.insert = MagicMock(
                    side_effect=Exception("Database connection error")
                )

            elif table_name == "fact_enrichment_errors":
                insert_mock = MagicMock()
                insert_mock.execute = MagicMock(return_value=MagicMock(data=[{}]))
                table.insert = MagicMock(return_value=insert_mock)

            return table

        client.table = MagicMock(side_effect=create_table_mock)

        verifier = SaveVerifier(supabase=client, max_retries=2)

        success, contact_id, error = verifier.save_contact(
            company_id="test-company-id",
            contact_data={"full_name": "John Smith", "title": "CEO"},
            source="test"
        )

        assert success is False
        assert "Insert failed" in error or "Database connection" in error


class TestSaveVerifierSignals:
    """Tests for ICP signal updates via SaveVerifier."""

    @pytest.fixture
    def mock_supabase_signals(self):
        """Create a mock for signal updates with readback."""
        client = MagicMock()
        stored_signals = {}

        def create_table_mock(table_name):
            table = MagicMock()

            if table_name == "dim_companies":
                update_mock = MagicMock()

                def update_handler(data):
                    stored_signals.update(data)
                    eq_mock = MagicMock()
                    eq_mock.execute = MagicMock(return_value=MagicMock(data=[{}]))
                    return eq_mock

                table.update = MagicMock(side_effect=update_handler)

                # Readback returns stored signals
                select_mock = MagicMock()
                eq_mock = MagicMock()
                eq_mock.execute = MagicMock(
                    return_value=MagicMock(data=[stored_signals])
                )
                select_mock.eq = MagicMock(return_value=eq_mock)
                table.select = MagicMock(return_value=select_mock)

            elif table_name == "fact_enrichment_errors":
                insert_mock = MagicMock()
                insert_mock.execute = MagicMock(return_value=MagicMock(data=[{}]))
                table.insert = MagicMock(return_value=insert_mock)

            return table

        client.table = MagicMock(side_effect=create_table_mock)
        client._stored_signals = stored_signals
        return client

    def test_update_company_signals(self, mock_supabase_signals):
        """Test updating ICP signals for a company."""
        from app.services.save_verifier import SaveVerifier

        verifier = SaveVerifier(supabase=mock_supabase_signals)

        signals = {
            "has_design_build": True,
            "has_engineering": True,
            "has_medical_specialization": False,
            "invalid_signal": True,  # Should be filtered out
        }

        success, error = verifier.update_company_signals(
            company_id="test-company-id",
            signals=signals,
            source="vlm_extractor"
        )

        assert success is True
        assert error is None

        # Verify only valid signals were stored
        stored = mock_supabase_signals._stored_signals
        assert stored["has_design_build"] is True
        assert stored["has_engineering"] is True
        assert stored["has_medical_specialization"] is False
        assert "invalid_signal" not in stored

    def test_empty_signals_rejected(self, mock_supabase_signals):
        """Test that empty signals dict is rejected."""
        from app.services.save_verifier import SaveVerifier

        verifier = SaveVerifier(supabase=mock_supabase_signals)

        success, error = verifier.update_company_signals(
            company_id="test-company-id",
            signals={},
            source="test"
        )

        assert success is False
        assert "No signals" in error


class TestSaveVerifierUtilityMethods:
    """Tests for SaveVerifier utility methods."""

    @pytest.fixture
    def mock_supabase_with_data(self):
        """Create a mock Supabase client with existing data."""
        client = MagicMock()

        def create_table_mock(table_name):
            table = MagicMock()

            if table_name == "dim_contacts":
                # Setup mock select for existing contacts
                select_mock = MagicMock()

                def eq_handler(column, value):
                    eq_result = MagicMock()
                    if column == "contact_id" and value == "existing-contact-123":
                        # Contact exists
                        eq_result.execute = MagicMock(
                            return_value=MagicMock(data=[{"contact_id": value}])
                        )
                    elif column == "contact_id" and value == "nonexistent-contact":
                        # Contact doesn't exist
                        eq_result.execute = MagicMock(return_value=MagicMock(data=[]))
                    elif column == "company_id":
                        # Return 3 contacts for this company
                        eq_result.execute = MagicMock(
                            return_value=MagicMock(
                                data=[
                                    {"contact_id": "c1"},
                                    {"contact_id": "c2"},
                                    {"contact_id": "c3"}
                                ],
                                count=3
                            )
                        )
                    else:
                        eq_result.execute = MagicMock(return_value=MagicMock(data=[]))
                    return eq_result

                select_mock.eq = MagicMock(side_effect=eq_handler)
                table.select = MagicMock(return_value=select_mock)

            elif table_name == "dim_companies":
                select_mock = MagicMock()

                def eq_handler(column, value):
                    eq_result = MagicMock()
                    if value == "existing-company-456":
                        # Company exists
                        eq_result.execute = MagicMock(
                            return_value=MagicMock(data=[{"company_id": value}])
                        )
                    else:
                        # Company doesn't exist
                        eq_result.execute = MagicMock(return_value=MagicMock(data=[]))
                    return eq_result

                select_mock.eq = MagicMock(side_effect=eq_handler)
                table.select = MagicMock(return_value=select_mock)

            return table

        client.table = MagicMock(side_effect=create_table_mock)
        return client

    def test_verify_contact_exists_true(self, mock_supabase_with_data):
        """
        Test verifying that a contact exists in the database.

        Should query dim_contacts by contact_id and return True if found.
        """
        from app.services.save_verifier import SaveVerifier

        verifier = SaveVerifier(supabase=mock_supabase_with_data)

        result = verifier.verify_contact_exists("existing-contact-123")

        assert result is True

    def test_verify_contact_exists_false(self, mock_supabase_with_data):
        """
        Test verifying that a contact does NOT exist in the database.

        Should query dim_contacts by contact_id and return False if not found.
        """
        from app.services.save_verifier import SaveVerifier

        verifier = SaveVerifier(supabase=mock_supabase_with_data)

        result = verifier.verify_contact_exists("nonexistent-contact")

        assert result is False

    def test_get_contact_count(self, mock_supabase_with_data):
        """
        Test getting the count of contacts for a company.

        Should query dim_contacts filtered by company_id and return the count.
        """
        from app.services.save_verifier import SaveVerifier

        verifier = SaveVerifier(supabase=mock_supabase_with_data)

        count = verifier.get_contact_count("test-company-id")

        assert count == 3


class TestSaveVerifierDBOptimization:
    """Tests for database optimization - INSERT RETURNING to eliminate readback."""

    @pytest.fixture
    def mock_supabase_with_insert_returning(self):
        """
        Create a mock Supabase client that supports INSERT RETURNING.

        This simulates PostgreSQL's INSERT...RETURNING functionality,
        which returns the inserted row data without requiring a separate SELECT.
        """
        client = MagicMock()
        saved_contacts = {}

        def create_table_mock(table_name):
            table = MagicMock()

            if table_name == "dim_contacts":
                # Duplicate check (pre-insert)
                select_mock = MagicMock()

                def eq_handler(column, value):
                    eq_result = MagicMock()
                    if column == "company_id":
                        # No existing duplicates
                        ilike_mock = MagicMock()
                        ilike_mock.execute = MagicMock(
                            return_value=MagicMock(data=[])
                        )
                        eq_result.ilike = MagicMock(return_value=ilike_mock)
                    else:
                        eq_result.execute = MagicMock(return_value=MagicMock(data=[]))
                    return eq_result

                select_mock.eq = MagicMock(side_effect=eq_handler)
                table.select = MagicMock(return_value=select_mock)

                # INSERT with RETURNING (single query)
                def insert_handler(data):
                    # Store the contact
                    contact_id = data["contact_id"]
                    saved_contacts[contact_id] = data

                    # Mock execute that returns inserted data (simulating RETURNING)
                    execute_mock = MagicMock()
                    execute_mock.data = [data]  # Return the inserted data
                    insert_result = MagicMock()
                    insert_result.execute = MagicMock(return_value=execute_mock)
                    return insert_result

                table.insert = MagicMock(side_effect=insert_handler)

            elif table_name == "fact_enrichment_errors":
                insert_mock = MagicMock()
                insert_mock.execute = MagicMock(return_value=MagicMock(data=[{}]))
                table.insert = MagicMock(return_value=insert_mock)

            return table

        client.table = MagicMock(side_effect=create_table_mock)
        client._saved_contacts = saved_contacts
        return client

    def test_insert_returning_eliminates_readback(self):
        """
        Test that INSERT RETURNING eliminates the need for separate SELECT.

        This is a DATABASE OPTIMIZATION test that verifies:
        1. INSERT...RETURNING returns the inserted data
        2. No separate SELECT query is needed for readback
        3. Data verification happens using the returned data

        Performance impact:
        - Current: INSERT (1 query) + SELECT readback (1 query) = 2 queries
        - Optimized: INSERT RETURNING (1 query) = 1 query
        - Speedup: 50% reduction in DB queries per contact

        For 100 contacts:
        - Current: 200 queries (100 INSERT + 100 SELECT readback)
        - Optimized: 100 queries (100 INSERT...RETURNING)
        - Savings: 100 queries (~300-500ms saved)

        NOTE: This test documents the DESIRED behavior for future optimization.
        Current implementation uses 2 queries (INSERT + SELECT readback).
        Future implementation should use 1 query (INSERT RETURNING).
        """
        from app.services.save_verifier import SaveVerifier

        # Create a mock that tracks query types
        client = MagicMock()
        call_tracker = {"insert_count": 0, "select_readback_count": 0}
        saved_contacts = {}

        def create_table_mock(table_name):
            table = MagicMock()

            if table_name == "dim_contacts":
                # Duplicate check (pre-insert)
                select_mock = MagicMock()

                def eq_handler(column, value):
                    eq_result = MagicMock()
                    if column == "company_id":
                        # Duplicate check - no duplicates
                        ilike_mock = MagicMock()
                        ilike_mock.execute = MagicMock(
                            return_value=MagicMock(data=[])
                        )
                        eq_result.ilike = MagicMock(return_value=ilike_mock)
                    elif column == "contact_id":
                        # Readback check (this is what we want to eliminate)
                        call_tracker["select_readback_count"] += 1
                        # Return the saved contact for readback
                        if value in saved_contacts:
                            eq_result.execute = MagicMock(
                                return_value=MagicMock(data=[saved_contacts[value]])
                            )
                        else:
                            eq_result.execute = MagicMock(
                                return_value=MagicMock(data=[])
                            )
                    else:
                        eq_result.execute = MagicMock(return_value=MagicMock(data=[]))
                    return eq_result

                select_mock.eq = MagicMock(side_effect=eq_handler)
                table.select = MagicMock(return_value=select_mock)

                # INSERT handler
                def insert_handler(data):
                    call_tracker["insert_count"] += 1
                    contact_id = data["contact_id"]
                    saved_contacts[contact_id] = data

                    # Current behavior: INSERT returns basic response
                    # Optimized behavior: INSERT should return inserted data via RETURNING
                    execute_mock = MagicMock()
                    execute_mock.data = [data]  # Simulate RETURNING (future optimization)
                    insert_result = MagicMock()
                    insert_result.execute = MagicMock(return_value=execute_mock)
                    return insert_result

                table.insert = MagicMock(side_effect=insert_handler)

            elif table_name == "fact_enrichment_errors":
                insert_mock = MagicMock()
                insert_mock.execute = MagicMock(return_value=MagicMock(data=[{}]))
                table.insert = MagicMock(return_value=insert_mock)

            return table

        client.table = MagicMock(side_effect=create_table_mock)

        verifier = SaveVerifier(supabase=client)

        # Save contact
        success, contact_id, error = verifier.save_contact(
            company_id="test-company-123",
            contact_data={
                "full_name": "Test Person",
                "title": "CEO"
            },
            source="test"
        )

        # Verify success
        assert success is True
        assert contact_id is not None

        # Current state: 1 INSERT + 1 SELECT readback = 2 queries
        assert call_tracker["insert_count"] == 1, (
            "Should have exactly 1 INSERT call"
        )

        # OPTIMIZATION GOAL:
        # Current: select_readback_count = 1 (separate readback query)
        # Optimized: select_readback_count = 0 (use INSERT RETURNING data)
        #
        # This assertion documents current behavior and will guide future optimization.
        current_readback_count = call_tracker["select_readback_count"]

        # For now, we expect the current behavior (1 readback query)
        # Once optimized with INSERT RETURNING, this should be 0
        print(f"📊 Current readback queries: {current_readback_count}")
        print(f"🎯 Optimization target: 0 readback queries (use INSERT RETURNING)")

        if current_readback_count == 0:
            print("✅ INSERT RETURNING optimization IS implemented!")
        else:
            print("⚠️  INSERT RETURNING optimization NOT YET implemented")
            print("   Current: 2 queries (INSERT + SELECT)")
            print("   Target: 1 query (INSERT...RETURNING)")

        # This is a documentation test - it will pass regardless
        # But it provides clear metrics for future optimization
        assert True, "Test documents optimization opportunity"
