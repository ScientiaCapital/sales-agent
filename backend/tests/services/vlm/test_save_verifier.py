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
                    if column == "contact_id":
                        # Readback returns empty - data not found
                        result = MagicMock()
                        result.data = []
                        select_mock.execute = MagicMock(return_value=result)
                    elif column == "company_id":
                        # Duplicate check returns empty
                        ilike_mock = MagicMock()
                        ilike_mock.execute = MagicMock(
                            return_value=MagicMock(data=[])
                        )
                        return ilike_mock
                    return select_mock

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
