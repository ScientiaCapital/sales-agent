"""
Comprehensive tests for the LeadService class.

This module tests all CRUD operations, error handling, and business logic
for the lead management service.
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import datetime

from app.services.leads import LeadService
from app.models.lead import Lead
from app.core.exceptions import LeadNotFoundError, LeadValidationError, DatabaseError


class TestLeadService:
    """Test the LeadService class functionality."""
    
    @pytest.fixture
    def lead_service(self):
        """Create a LeadService instance for testing."""
        return LeadService()
    
    @pytest.fixture
    def mock_lead(self):
        """Create a mock Lead object for testing."""
        lead = Mock(spec=Lead)
        lead.id = 1
        lead.company_name = "Test Company"
        lead.email = "test@testcompany.com"
        lead.phone = "+1-555-0123"
        lead.website = "https://testcompany.com"
        lead.qualification_score = None
        lead.qualification_reasoning = None
        lead.qualification_model = None
        lead.qualification_latency_ms = None
        lead.qualified_at = None
        lead.additional_data = {}
        lead.created_at = datetime.utcnow()
        lead.updated_at = datetime.utcnow()
        return lead
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session for testing."""
        session = Mock()
        session.query.return_value = session
        session.filter.return_value = session
        session.first.return_value = None
        session.all.return_value = []
        session.add.return_value = None
        session.commit.return_value = None
        session.refresh.return_value = None
        session.rollback.return_value = None
        return session


class TestCreateLead:
    """Test lead creation functionality."""
    
    @pytest.mark.unit
    def test_create_lead_success(self, lead_service, mock_db_session, mock_lead):
        """Test successful lead creation."""
        # Mock the query to return no existing lead
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Mock the new lead creation
        with patch('app.services.leads.Lead') as mock_lead_class:
            mock_lead_class.return_value = mock_lead
            
            result = lead_service.create_lead(
                db=mock_db_session,
                company_name="Test Company",
                email="test@testcompany.com",
                phone="+1-555-0123",
                website="https://testcompany.com"
            )
            
            assert result == mock_lead
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()
            mock_db_session.refresh.assert_called_once()
    
    @pytest.mark.unit
    def test_create_lead_duplicate_email(self, lead_service, mock_db_session, mock_lead):
        """Test lead creation with duplicate email."""
        # Mock the query to return an existing lead
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        
        with pytest.raises(LeadValidationError, match="Lead with email .* already exists"):
            lead_service.create_lead(
                db=mock_db_session,
                company_name="Test Company",
                email="test@testcompany.com",
                phone="+1-555-0123",
                website="https://testcompany.com"
            )
    
    @pytest.mark.unit
    def test_create_lead_database_error(self, lead_service, mock_db_session):
        """Test lead creation with database error."""
        # Mock the query to return no existing lead
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Mock database error on commit
        mock_db_session.commit.side_effect = SQLAlchemyError("Database error")
        
        with patch('app.services.leads.Lead') as mock_lead_class:
            mock_lead_class.return_value = Mock()
            
            with pytest.raises(DatabaseError, match="Failed to create lead"):
                lead_service.create_lead(
                    db=mock_db_session,
                    company_name="Test Company",
                    email="test@testcompany.com",
                    phone="+1-555-0123",
                    website="https://testcompany.com"
                )
            
            # Verify rollback was called
            mock_db_session.rollback.assert_called_once()


class TestGetLead:
    """Test lead retrieval functionality."""
    
    @pytest.mark.unit
    def test_get_lead_success(self, lead_service, mock_db_session, mock_lead):
        """Test successful lead retrieval."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        
        result = lead_service.get_lead(mock_db_session, 1)
        
        assert result == mock_lead
        mock_db_session.query.assert_called_once()
    
    @pytest.mark.unit
    def test_get_lead_not_found(self, lead_service, mock_db_session):
        """Test lead retrieval when lead doesn't exist."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(LeadNotFoundError, match="Lead with ID 1 not found"):
            lead_service.get_lead(mock_db_session, 1)


class TestUpdateLead:
    """Test lead update functionality."""
    
    @pytest.mark.unit
    def test_update_lead_success(self, lead_service, mock_db_session, mock_lead):
        """Test successful lead update."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        
        result = lead_service.update_lead(
            db=mock_db_session,
            lead_id=1,
            company_name="Updated Company",
            email="updated@testcompany.com"
        )
        
        assert result == mock_lead
        assert mock_lead.company_name == "Updated Company"
        assert mock_lead.email == "updated@testcompany.com"
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()
    
    @pytest.mark.unit
    def test_update_lead_not_found(self, lead_service, mock_db_session):
        """Test lead update when lead doesn't exist."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(LeadNotFoundError, match="Lead with ID 1 not found"):
            lead_service.update_lead(
                db=mock_db_session,
                lead_id=1,
                company_name="Updated Company"
            )
    
    @pytest.mark.unit
    def test_update_lead_database_error(self, lead_service, mock_db_session, mock_lead):
        """Test lead update with database error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        mock_db_session.commit.side_effect = SQLAlchemyError("Database error")
        
        with pytest.raises(DatabaseError, match="Failed to update lead"):
            lead_service.update_lead(
                db=mock_db_session,
                lead_id=1,
                company_name="Updated Company"
            )
        
        mock_db_session.rollback.assert_called_once()


class TestUpdateQualification:
    """Test lead qualification update functionality."""
    
    @pytest.mark.unit
    def test_update_qualification_success(self, lead_service, mock_db_session, mock_lead):
        """Test successful qualification update."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        
        result = lead_service.update_qualification(
            db=mock_db_session,
            lead_id=1,
            score=85.5,
            reasoning="High-quality lead with strong indicators",
            model="cerebras-llama3.1-8b",
            latency_ms=650.0
        )
        
        assert result == mock_lead
        assert mock_lead.qualification_score == 85.5
        assert mock_lead.qualification_reasoning == "High-quality lead with strong indicators"
        assert mock_lead.qualification_model == "cerebras-llama3.1-8b"
        assert mock_lead.qualification_latency_ms == 650.0
        assert mock_lead.qualified_at is not None
        assert mock_lead.updated_at is not None
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()
    
    @pytest.mark.unit
    def test_update_qualification_lead_not_found(self, lead_service, mock_db_session):
        """Test qualification update when lead doesn't exist."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(LeadNotFoundError, match="Lead with ID 1 not found"):
            lead_service.update_qualification(
                db=mock_db_session,
                lead_id=1,
                score=85.5,
                reasoning="Test reasoning",
                model="test-model"
            )
    
    @pytest.mark.unit
    def test_update_qualification_database_error(self, lead_service, mock_db_session, mock_lead):
        """Test qualification update with database error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        mock_db_session.commit.side_effect = SQLAlchemyError("Database error")
        
        with pytest.raises(DatabaseError, match="Failed to update qualification"):
            lead_service.update_qualification(
                db=mock_db_session,
                lead_id=1,
                score=85.5,
                reasoning="Test reasoning",
                model="test-model"
            )
        
        mock_db_session.rollback.assert_called_once()
    
    @pytest.mark.unit
    def test_update_qualification_unexpected_error(self, lead_service, mock_db_session, mock_lead):
        """Test qualification update with unexpected error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        mock_db_session.commit.side_effect = Exception("Unexpected error")
        
        with pytest.raises(DatabaseError, match="Failed to update qualification"):
            lead_service.update_qualification(
                db=mock_db_session,
                lead_id=1,
                score=85.5,
                reasoning="Test reasoning",
                model="test-model"
            )
        
        mock_db_session.rollback.assert_called_once()


class TestUpdateEnrichment:
    """Test lead enrichment update functionality."""
    
    @pytest.mark.unit
    def test_update_enrichment_success(self, lead_service, mock_db_session, mock_lead):
        """Test successful enrichment update."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        
        enrichment_data = {
            "apollo": {
                "company_size": "50-200",
                "industry": "Technology",
                "annual_revenue": "10M-50M"
            },
            "linkedin": {
                "employee_count": 150,
                "headquarters": "San Francisco, CA"
            }
        }
        
        result = lead_service.update_enrichment(
            db=mock_db_session,
            lead_id=1,
            enrichment_data=enrichment_data
        )
        
        assert result == mock_lead
        assert mock_lead.additional_data["enrichment"] == enrichment_data
        assert mock_lead.updated_at is not None
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()
    
    @pytest.mark.unit
    def test_update_enrichment_merge_existing(self, lead_service, mock_db_session, mock_lead):
        """Test enrichment update merging with existing data."""
        # Set up existing enrichment data
        mock_lead.additional_data = {
            "enrichment": {
                "apollo": {
                    "company_size": "50-200",
                    "industry": "Technology"
                }
            }
        }
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        
        new_enrichment_data = {
            "linkedin": {
                "employee_count": 150,
                "headquarters": "San Francisco, CA"
            }
        }
        
        result = lead_service.update_enrichment(
            db=mock_db_session,
            lead_id=1,
            enrichment_data=new_enrichment_data
        )
        
        assert result == mock_lead
        expected_data = {
            "apollo": {
                "company_size": "50-200",
                "industry": "Technology"
            },
            "linkedin": {
                "employee_count": 150,
                "headquarters": "San Francisco, CA"
            }
        }
        assert mock_lead.additional_data["enrichment"] == expected_data
    
    @pytest.mark.unit
    def test_update_enrichment_lead_not_found(self, lead_service, mock_db_session):
        """Test enrichment update when lead doesn't exist."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(LeadNotFoundError, match="Lead with ID 1 not found"):
            lead_service.update_enrichment(
                db=mock_db_session,
                lead_id=1,
                enrichment_data={"test": "data"}
            )
    
    @pytest.mark.unit
    def test_update_enrichment_database_error(self, lead_service, mock_db_session, mock_lead):
        """Test enrichment update with database error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        mock_db_session.commit.side_effect = SQLAlchemyError("Database error")
        
        with pytest.raises(DatabaseError, match="Failed to update enrichment"):
            lead_service.update_enrichment(
                db=mock_db_session,
                lead_id=1,
                enrichment_data={"test": "data"}
            )
        
        mock_db_session.rollback.assert_called_once()
    
    @pytest.mark.unit
    def test_update_enrichment_unexpected_error(self, lead_service, mock_db_session, mock_lead):
        """Test enrichment update with unexpected error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        mock_db_session.commit.side_effect = Exception("Unexpected error")
        
        with pytest.raises(DatabaseError, match="Failed to update enrichment"):
            lead_service.update_enrichment(
                db=mock_db_session,
                lead_id=1,
                enrichment_data={"test": "data"}
            )
        
        mock_db_session.rollback.assert_called_once()


class TestDeleteLead:
    """Test lead deletion functionality."""
    
    @pytest.mark.unit
    def test_delete_lead_success(self, lead_service, mock_db_session, mock_lead):
        """Test successful lead deletion."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        
        result = lead_service.delete_lead(mock_db_session, 1)
        
        assert result is True
        mock_db_session.delete.assert_called_once_with(mock_lead)
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.unit
    def test_delete_lead_not_found(self, lead_service, mock_db_session):
        """Test lead deletion when lead doesn't exist."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(LeadNotFoundError, match="Lead with ID 1 not found"):
            lead_service.delete_lead(mock_db_session, 1)
    
    @pytest.mark.unit
    def test_delete_lead_database_error(self, lead_service, mock_db_session, mock_lead):
        """Test lead deletion with database error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        mock_db_session.commit.side_effect = SQLAlchemyError("Database error")
        
        with pytest.raises(DatabaseError, match="Failed to delete lead"):
            lead_service.delete_lead(mock_db_session, 1)
        
        mock_db_session.rollback.assert_called_once()


class TestListLeads:
    """Test lead listing functionality."""
    
    @pytest.mark.unit
    def test_list_leads_success(self, lead_service, mock_db_session, mock_lead):
        """Test successful lead listing."""
        mock_db_session.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = [mock_lead]
        mock_db_session.query.return_value.count.return_value = 1
        
        result = lead_service.list_leads(
            db=mock_db_session,
            skip=0,
            limit=10,
            qualification_score_min=80.0
        )
        
        assert len(result["leads"]) == 1
        assert result["total"] == 1
        assert result["leads"][0] == mock_lead
    
    @pytest.mark.unit
    def test_list_leads_empty(self, lead_service, mock_db_session):
        """Test lead listing with no results."""
        mock_db_session.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = []
        mock_db_session.query.return_value.count.return_value = 0
        
        result = lead_service.list_leads(
            db=mock_db_session,
            skip=0,
            limit=10
        )
        
        assert len(result["leads"]) == 0
        assert result["total"] == 0


class TestSearchLeads:
    """Test lead search functionality."""
    
    @pytest.mark.unit
    def test_search_leads_success(self, lead_service, mock_db_session, mock_lead):
        """Test successful lead search."""
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_lead]
        
        result = lead_service.search_leads(
            db=mock_db_session,
            query="Test Company"
        )
        
        assert len(result) == 1
        assert result[0] == mock_lead
    
    @pytest.mark.unit
    def test_search_leads_no_results(self, lead_service, mock_db_session):
        """Test lead search with no results."""
        mock_db_session.query.return_value.filter.return_value.all.return_value = []
        
        result = lead_service.search_leads(
            db=mock_db_session,
            query="Nonexistent Company"
        )
        
        assert len(result) == 0


class TestErrorHandlingConsistency:
    """Test that error handling is consistent across all methods."""
    
    @pytest.mark.unit
    def test_all_methods_handle_lead_not_found(self, lead_service, mock_db_session):
        """Test that all methods properly handle LeadNotFoundError."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Test all methods that can raise LeadNotFoundError
        methods_to_test = [
            ("get_lead", (mock_db_session, 1)),
            ("update_lead", (mock_db_session, 1, company_name="Test")),
            ("update_qualification", (mock_db_session, 1, 85.5, "reasoning", "model")),
            ("update_enrichment", (mock_db_session, 1, {"test": "data"})),
            ("delete_lead", (mock_db_session, 1))
        ]
        
        for method_name, args in methods_to_test:
            method = getattr(lead_service, method_name)
            with pytest.raises(LeadNotFoundError):
                method(*args)
    
    @pytest.mark.unit
    def test_all_methods_handle_database_errors(self, lead_service, mock_db_session, mock_lead):
        """Test that all methods properly handle database errors."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_lead
        mock_db_session.commit.side_effect = SQLAlchemyError("Database error")
        
        # Test methods that perform database operations
        methods_to_test = [
            ("update_lead", (mock_db_session, 1, company_name="Test")),
            ("update_qualification", (mock_db_session, 1, 85.5, "reasoning", "model")),
            ("update_enrichment", (mock_db_session, 1, {"test": "data"})),
            ("delete_lead", (mock_db_session, 1))
        ]
        
        for method_name, args in methods_to_test:
            method = getattr(lead_service, method_name)
            with pytest.raises(DatabaseError):
                method(*args)
            
            # Verify rollback was called
            mock_db_session.rollback.assert_called()
            mock_db_session.reset_mock()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
