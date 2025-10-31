"""
Tests for CRM Deduplication Engine

Tests multi-field matching, confidence scoring, and duplicate detection.
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.crm.deduplication import (
    DeduplicationEngine,
    DuplicateMatch,
    DeduplicationResult,
    MatchDetails,
    get_deduplication_engine
)
from app.models.crm import CRMContact
from app.models.database import Base, engine


# ========== Fixtures ==========
# Note: db_session fixture is now provided by conftest.py

@pytest.fixture
def dedup_engine(db_session):
    """Create deduplication engine with test database"""
    return DeduplicationEngine(db=db_session, duplicate_threshold=85.0)


@pytest.fixture
def sample_contact(db_session):
    """Create sample contact for testing"""
    contact = CRMContact(
        email="john.doe@acmecorp.com",
        first_name="John",
        last_name="Doe",
        company="Acme Corporation",
        title="VP of Engineering",
        phone="+1-555-1234",
        linkedin_url="https://linkedin.com/in/johndoe",
        external_ids={"close": "lead_abc123"},
        source_platform="close",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    return contact


# ========== Email Match Tests ==========

@pytest.mark.asyncio
async def test_email_exact_match_100_confidence(dedup_engine, sample_contact):
    """Test email exact match returns 100% confidence"""
    result = await dedup_engine.find_duplicates(
        email="john.doe@acmecorp.com"
    )

    assert result.is_duplicate is True
    assert result.confidence == 100.0
    assert len(result.matches) == 1

    best_match = result.get_best_match()
    assert best_match is not None
    assert best_match.contact.email == "john.doe@acmecorp.com"
    assert any(d.field_name == "email" for d in best_match.match_details)


@pytest.mark.asyncio
async def test_email_case_insensitive(dedup_engine, sample_contact):
    """Test email matching is case insensitive"""
    result = await dedup_engine.find_duplicates(
        email="JOHN.DOE@ACMECORP.COM"
    )

    assert result.is_duplicate is True
    assert result.confidence == 100.0


# ========== Domain Match Tests ==========

@pytest.mark.asyncio
async def test_domain_match_80_confidence(dedup_engine, sample_contact):
    """Test domain match returns 80% confidence"""
    result = await dedup_engine.find_duplicates(
        email="jane.smith@acmecorp.com"  # Different person, same domain
    )

    assert result.confidence == 80.0  # Domain match only
    assert len(result.matches) == 1

    best_match = result.get_best_match()
    assert any(d.field_name == "domain" for d in best_match.match_details)


# ========== LinkedIn URL Match Tests ==========

@pytest.mark.asyncio
async def test_linkedin_url_exact_match_95_confidence(dedup_engine, sample_contact):
    """Test LinkedIn URL exact match returns 95% confidence"""
    result = await dedup_engine.find_duplicates(
        linkedin_url="https://linkedin.com/in/johndoe"
    )

    assert result.confidence == 95.0
    assert len(result.matches) == 1

    best_match = result.get_best_match()
    assert any(d.field_name == "linkedin_url" for d in best_match.match_details)


@pytest.mark.asyncio
async def test_linkedin_url_trailing_slash_normalization(dedup_engine, sample_contact):
    """Test LinkedIn URL normalization handles trailing slashes"""
    result = await dedup_engine.find_duplicates(
        linkedin_url="https://linkedin.com/in/johndoe/"  # Trailing slash
    )

    assert result.confidence == 95.0


# ========== Phone Match Tests ==========

@pytest.mark.asyncio
async def test_phone_normalized_match_70_confidence(dedup_engine, sample_contact):
    """Test phone normalization and matching"""
    result = await dedup_engine.find_duplicates(
        phone="(555) 1234"  # Different format, same number
    )

    assert result.confidence == 70.0
    assert len(result.matches) == 1

    best_match = result.get_best_match()
    assert any(d.field_name == "phone" for d in best_match.match_details)


# ========== Company Name Fuzzy Match Tests ==========

@pytest.mark.asyncio
async def test_company_fuzzy_match_high_similarity(dedup_engine, sample_contact):
    """Test company name fuzzy matching with high similarity"""
    result = await dedup_engine.find_duplicates(
        company="ACME Corp"  # Similar to "Acme Corporation"
    )

    assert result.confidence >= 80.0  # High similarity
    assert len(result.matches) == 1

    best_match = result.get_best_match()
    assert any(d.field_name == "company" for d in best_match.match_details)


@pytest.mark.asyncio
async def test_company_fuzzy_match_removes_suffixes(dedup_engine, sample_contact):
    """Test company name normalization removes common suffixes"""
    result = await dedup_engine.find_duplicates(
        company="Acme Inc"  # Different suffix
    )

    # Should match "Acme Corporation" after normalization
    assert result.confidence >= 75.0


# ========== Multiple Field Match Tests ==========

@pytest.mark.asyncio
async def test_multiple_field_match_aggregate_confidence(dedup_engine, sample_contact):
    """Test multiple field matches aggregate confidence correctly"""
    result = await dedup_engine.find_duplicates(
        email="john.doe@acmecorp.com",  # 100% match
        company="Acme Corporation",  # ~90% match
        phone="+1-555-1234"  # 70% match
    )

    # Should use max confidence (email exact match)
    assert result.confidence == 100.0
    assert result.is_duplicate is True

    best_match = result.get_best_match()
    # Should have match details for all fields
    field_names = {d.field_name for d in best_match.match_details}
    assert "email" in field_names
    assert "company" in field_names or "domain" in field_names
    assert "phone" in field_names


# ========== No Match Tests ==========

@pytest.mark.asyncio
async def test_no_match_returns_empty(dedup_engine, sample_contact):
    """Test no duplicates found returns empty result"""
    result = await dedup_engine.find_duplicates(
        email="nonexistent@example.com",
        company="Totally Different Company"
    )

    assert result.is_duplicate is False
    assert result.confidence == 0.0
    assert len(result.matches) == 0
    assert result.get_best_match() is None


# ========== Threshold Tests ==========

@pytest.mark.asyncio
async def test_threshold_90_blocks_domain_match(db_session, sample_contact):
    """Test higher threshold blocks lower-confidence matches"""
    engine = DeduplicationEngine(db=db_session, duplicate_threshold=90.0)

    result = await engine.find_duplicates(
        email="different@acmecorp.com"  # Domain match only (80%)
    )

    assert result.confidence == 80.0
    assert result.is_duplicate is False  # Below 90% threshold


@pytest.mark.asyncio
async def test_threshold_70_allows_phone_match(db_session, sample_contact):
    """Test lower threshold allows phone matches"""
    engine = DeduplicationEngine(db=db_session, duplicate_threshold=70.0)

    result = await engine.find_duplicates(
        phone="+1-555-1234"  # Phone match only (70%)
    )

    assert result.confidence == 70.0
    assert result.is_duplicate is True  # At 70% threshold


# ========== Utility Method Tests ==========

def test_extract_domain_from_email(dedup_engine):
    """Test domain extraction from email"""
    domain = dedup_engine._extract_domain("john@acme.com")
    assert domain == "acme.com"


def test_extract_domain_from_url(dedup_engine):
    """Test domain extraction from URL"""
    domain = dedup_engine._extract_domain("https://www.acme.com/path")
    assert domain == "acme.com"


def test_normalize_phone(dedup_engine):
    """Test phone number normalization"""
    assert dedup_engine._normalize_phone("+1 (555) 123-4567") == "15551234567"
    assert dedup_engine._normalize_phone("555.123.4567") == "5551234567"
    assert dedup_engine._normalize_phone("") == ""


def test_normalize_company_name(dedup_engine):
    """Test company name normalization"""
    assert dedup_engine._normalize_company_name("Acme Corp., Inc.") == "acme"
    assert dedup_engine._normalize_company_name("ACME Corporation") == "acme"
    assert dedup_engine._normalize_company_name("Acme Technologies, LLC") == "acme"


def test_levenshtein_distance(dedup_engine):
    """Test Levenshtein distance calculation"""
    assert dedup_engine._levenshtein_distance("kitten", "sitting") == 3
    assert dedup_engine._levenshtein_distance("acme", "acme") == 0
    assert dedup_engine._levenshtein_distance("abc", "xyz") == 3


def test_levenshtein_similarity(dedup_engine):
    """Test similarity calculation from Levenshtein distance"""
    # Identical strings
    assert dedup_engine._calculate_levenshtein_similarity("acme", "acme") == 1.0

    # Very similar
    similarity = dedup_engine._calculate_levenshtein_similarity("acme", "acm")
    assert similarity > 0.7

    # Different
    similarity = dedup_engine._calculate_levenshtein_similarity("acme", "xyz")
    assert similarity < 0.3


# ========== Factory Function Test ==========

def test_factory_function(db_session):
    """Test factory function creates engine correctly"""
    engine = get_deduplication_engine(db=db_session, threshold=90.0)
    assert isinstance(engine, DeduplicationEngine)
    assert engine.duplicate_threshold == 90.0


# ========== Edge Cases ==========

@pytest.mark.asyncio
async def test_empty_database_no_duplicates(dedup_engine):
    """Test deduplication with empty database"""
    result = await dedup_engine.find_duplicates(
        email="test@example.com"
    )

    assert result.is_duplicate is False
    assert len(result.matches) == 0


@pytest.mark.asyncio
async def test_all_null_fields_no_match(dedup_engine, sample_contact):
    """Test all null fields returns no match"""
    result = await dedup_engine.find_duplicates()

    # Should not raise error, just return no matches
    assert result.is_duplicate is False
    assert len(result.matches) == 0


@pytest.mark.asyncio
async def test_multiple_contacts_same_domain(db_session):
    """Test multiple contacts with same domain"""
    # Create multiple contacts with same domain
    contacts = [
        CRMContact(email=f"person{i}@acme.com", company=f"Acme Division {i}")
        for i in range(3)
    ]
    for contact in contacts:
        db_session.add(contact)
    db_session.commit()

    engine = DeduplicationEngine(db=db_session, duplicate_threshold=85.0)
    result = await engine.find_duplicates(email="newperson@acme.com")

    # Should find all 3 contacts (domain match)
    assert len(result.matches) == 3
    assert all(m.confidence == 80.0 for m in result.matches)  # All domain matches
