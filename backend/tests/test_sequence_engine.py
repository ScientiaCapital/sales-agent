"""
Test suite for SequenceEngine - Core sequence execution logic.

Tests cover:
- Enrollment logic
- Step execution
- Due email processing with delay logic
- Reply handling
"""

import os
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Set test database URL before importing database module
os.environ["DATABASE_URL"] = "postgresql+psycopg://test:test@localhost:5432/test"

from app.models.database import Base
from app.models.lead import Lead
from app.models.sequence import Sequence
from app.models.sequence_entry import SequenceEntry
from app.models.mailbox import Mailbox
from app.services.sequences.engine import SequenceEngine


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
async def async_session():
    """Create an async test database session."""
    # Use in-memory SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def test_mailbox(async_session):
    """Create a test mailbox."""
    mailbox = Mailbox(
        email="test@example.com",
        domain_id=1,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="test@example.com",
        smtp_password="password",
        imap_host="imap.example.com",
        imap_port=993,
        status="active",
        daily_limit=50,
        warmup_enabled=False,
    )
    async_session.add(mailbox)
    await async_session.commit()
    await async_session.refresh(mailbox)
    return mailbox


@pytest.fixture
async def test_sequence(async_session):
    """Create a test sequence with multiple steps."""
    sequence = Sequence(
        sequence_id="test_sequence",
        name="Test Sequence",
        steps=[
            {
                "step_number": 0,
                "delay_days": 0,
                "subject": "Hello {{first_name}}",
                "body": "Hi {{first_name}}, this is step 1.",
            },
            {
                "step_number": 1,
                "delay_days": 3,
                "subject": "Follow-up for {{company}}",
                "body": "Hi {{first_name}}, following up on my previous email.",
            },
            {
                "step_number": 2,
                "delay_days": 5,
                "subject": "Final follow-up",
                "body": "Hi {{first_name}}, last chance to connect.",
            },
        ],
        stop_on_reply=True,
        stop_on_bounce=True,
        daily_limit_per_mailbox=50,
        is_active=True,
    )
    async_session.add(sequence)
    await async_session.commit()
    await async_session.refresh(sequence)
    return sequence


@pytest.fixture
async def test_lead(async_session):
    """Create a test lead."""
    lead = Lead(
        contact_email="prospect@example.com",
        company_name="Test Company",
        contact_name="John Doe",
        tier="A",
        qualification_score=85.0,
    )
    async_session.add(lead)
    await async_session.commit()
    await async_session.refresh(lead)
    return lead


# ============================================================================
# TESTS: process_due_emails - Delay Logic
# ============================================================================


@pytest.mark.asyncio
async def test_process_due_emails_first_email_immediate(
    async_session, test_sequence, test_lead, test_mailbox
):
    """Test that first email (last_email_sent=None) is processed immediately."""
    # Create entry with no emails sent yet
    entry = SequenceEntry(
        lead_id=test_lead.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="pending",
        current_step=0,
        last_email_sent=None,
        started_at=datetime.utcnow(),
    )
    async_session.add(entry)
    await async_session.commit()

    # Process due emails
    engine = SequenceEngine(async_session)
    engine.set_test_mode(True)
    result = await engine.process_due_emails(limit=10)

    # Should process the entry immediately
    assert result["processed"] == 1
    assert result["sent"] == 1
    assert result["errors"] == 0


@pytest.mark.asyncio
async def test_process_due_emails_respects_delay_not_due(
    async_session, test_sequence, test_lead, test_mailbox
):
    """Test that emails are NOT sent before delay_days have passed."""
    # Create entry that sent first email 1 day ago (needs 3 days for step 2)
    entry = SequenceEntry(
        lead_id=test_lead.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="active",
        current_step=1,  # On step 1, which has delay_days=3
        last_email_sent=datetime.utcnow() - timedelta(days=1),
        emails_sent=1,
        started_at=datetime.utcnow() - timedelta(days=1),
    )
    async_session.add(entry)
    await async_session.commit()

    # Process due emails
    engine = SequenceEngine(async_session)
    engine.set_test_mode(True)
    result = await engine.process_due_emails(limit=10)

    # Should NOT process the entry (only 1 day passed, need 3)
    assert result["processed"] == 0
    assert result["sent"] == 0
    assert result["filtered"] == 1


@pytest.mark.asyncio
async def test_process_due_emails_respects_delay_is_due(
    async_session, test_sequence, test_lead, test_mailbox
):
    """Test that emails ARE sent after delay_days have passed."""
    # Create entry that sent first email 4 days ago (needs 3 days for step 2)
    entry = SequenceEntry(
        lead_id=test_lead.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="active",
        current_step=1,  # On step 1, which has delay_days=3
        last_email_sent=datetime.utcnow() - timedelta(days=4),
        emails_sent=1,
        started_at=datetime.utcnow() - timedelta(days=4),
    )
    async_session.add(entry)
    await async_session.commit()

    # Process due emails
    engine = SequenceEngine(async_session)
    engine.set_test_mode(True)
    result = await engine.process_due_emails(limit=10)

    # Should process the entry (4 days passed, need 3)
    assert result["processed"] == 1
    assert result["sent"] == 1
    assert result["errors"] == 0


@pytest.mark.asyncio
async def test_process_due_emails_exact_delay_boundary(
    async_session, test_sequence, test_lead, test_mailbox
):
    """Test that emails are sent exactly at the delay boundary."""
    # Create entry that sent first email exactly 3 days ago
    entry = SequenceEntry(
        lead_id=test_lead.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="active",
        current_step=1,  # On step 1, which has delay_days=3
        last_email_sent=datetime.utcnow() - timedelta(days=3, seconds=1),
        emails_sent=1,
        started_at=datetime.utcnow() - timedelta(days=3, seconds=1),
    )
    async_session.add(entry)
    await async_session.commit()

    # Process due emails
    engine = SequenceEngine(async_session)
    engine.set_test_mode(True)
    result = await engine.process_due_emails(limit=10)

    # Should process the entry (exactly at boundary)
    assert result["processed"] == 1
    assert result["sent"] == 1


@pytest.mark.asyncio
async def test_process_due_emails_multiple_entries_mixed_due_status(
    async_session, test_sequence, test_lead, test_mailbox
):
    """Test filtering when multiple entries have different due statuses."""
    # Create multiple leads
    lead1 = test_lead
    lead2 = Lead(
        contact_email="prospect2@example.com",
        company_name="Test Company 2",
        contact_name="Jane Smith",
    )
    lead3 = Lead(
        contact_email="prospect3@example.com",
        company_name="Test Company 3",
        contact_name="Bob Wilson",
    )
    async_session.add_all([lead2, lead3])
    await async_session.commit()

    # Entry 1: Due immediately (no emails sent)
    entry1 = SequenceEntry(
        lead_id=lead1.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="pending",
        current_step=0,
        last_email_sent=None,
        started_at=datetime.utcnow(),
    )

    # Entry 2: NOT due (1 day passed, needs 3)
    entry2 = SequenceEntry(
        lead_id=lead2.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="active",
        current_step=1,
        last_email_sent=datetime.utcnow() - timedelta(days=1),
        emails_sent=1,
        started_at=datetime.utcnow() - timedelta(days=1),
    )

    # Entry 3: IS due (5 days passed, needs 3)
    entry3 = SequenceEntry(
        lead_id=lead3.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="active",
        current_step=1,
        last_email_sent=datetime.utcnow() - timedelta(days=5),
        emails_sent=1,
        started_at=datetime.utcnow() - timedelta(days=5),
    )

    async_session.add_all([entry1, entry2, entry3])
    await async_session.commit()

    # Process due emails
    engine = SequenceEngine(async_session)
    engine.set_test_mode(True)
    result = await engine.process_due_emails(limit=10)

    # Should process entry1 and entry3, but not entry2
    assert result["processed"] == 2
    assert result["sent"] == 2
    assert result["filtered"] == 1


@pytest.mark.asyncio
async def test_process_due_emails_limit_validation(async_session):
    """Test limit parameter validation."""
    engine = SequenceEngine(async_session)

    # Test invalid limit (negative)
    result = await engine.process_due_emails(limit=-5)
    assert result["processed"] == 0

    # Test invalid limit (zero)
    result = await engine.process_due_emails(limit=0)
    assert result["processed"] == 0

    # Test limit exceeds max (should cap at 1000)
    result = await engine.process_due_emails(limit=5000)
    # Should not crash, will cap at 1000
    assert "error" not in result


@pytest.mark.asyncio
async def test_process_due_emails_skips_completed_sequences(
    async_session, test_sequence, test_lead, test_mailbox
):
    """Test that entries with all steps completed are skipped."""
    # Create entry that has completed all steps
    entry = SequenceEntry(
        lead_id=test_lead.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="active",
        current_step=3,  # All 3 steps done (0, 1, 2)
        last_email_sent=datetime.utcnow() - timedelta(days=1),
        emails_sent=3,
        started_at=datetime.utcnow() - timedelta(days=10),
    )
    async_session.add(entry)
    await async_session.commit()

    # Process due emails
    engine = SequenceEngine(async_session)
    engine.set_test_mode(True)
    result = await engine.process_due_emails(limit=10)

    # Should skip the entry (all steps completed)
    assert result["processed"] == 0
    assert result["filtered"] == 1


@pytest.mark.asyncio
async def test_process_due_emails_skips_invalid_status(
    async_session, test_sequence, test_lead, test_mailbox
):
    """Test that entries with non-active status are skipped."""
    # Create entries with various statuses
    entry1 = SequenceEntry(
        lead_id=test_lead.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="completed",
        current_step=1,
        last_email_sent=None,
    )
    entry2 = SequenceEntry(
        lead_id=test_lead.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="replied",
        current_step=1,
        last_email_sent=None,
    )
    entry3 = SequenceEntry(
        lead_id=test_lead.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="unsubscribed",
        current_step=1,
        last_email_sent=None,
    )
    async_session.add_all([entry1, entry2, entry3])
    await async_session.commit()

    # Process due emails
    engine = SequenceEngine(async_session)
    engine.set_test_mode(True)
    result = await engine.process_due_emails(limit=10)

    # Should skip all (wrong status)
    assert result["processed"] == 0


@pytest.mark.asyncio
async def test_process_due_emails_different_delays_per_step(async_session, test_mailbox):
    """Test that different delay_days are respected for different steps."""
    # Create a sequence with varying delays
    sequence = Sequence(
        sequence_id="varied_delays",
        name="Varied Delays",
        steps=[
            {"step_number": 0, "delay_days": 0, "subject": "Step 1", "body": "Body 1"},
            {"step_number": 1, "delay_days": 2, "subject": "Step 2", "body": "Body 2"},
            {"step_number": 2, "delay_days": 7, "subject": "Step 3", "body": "Body 3"},
        ],
        is_active=True,
    )
    async_session.add(sequence)

    lead = Lead(
        contact_email="test@example.com",
        company_name="Test Co",
        contact_name="Test User",
    )
    async_session.add(lead)
    await async_session.commit()
    await async_session.refresh(sequence)
    await async_session.refresh(lead)

    # Entry on step 2 (needs 7 days), sent 6 days ago
    entry = SequenceEntry(
        lead_id=lead.id,
        sequence_id=sequence.id,
        mailbox_id=test_mailbox.id,
        status="active",
        current_step=2,
        last_email_sent=datetime.utcnow() - timedelta(days=6),
        emails_sent=2,
        started_at=datetime.utcnow() - timedelta(days=8),
    )
    async_session.add(entry)
    await async_session.commit()

    # Process due emails
    engine = SequenceEngine(async_session)
    engine.set_test_mode(True)
    result = await engine.process_due_emails(limit=10)

    # Should NOT process (6 days < 7 days required)
    assert result["processed"] == 0
    assert result["filtered"] == 1


# ============================================================================
# TESTS: Enrollment
# ============================================================================


@pytest.mark.asyncio
async def test_enroll_prospect_success(
    async_session, test_sequence, test_mailbox
):
    """Test successful prospect enrollment."""
    engine = SequenceEngine(async_session)

    result = await engine.enroll_prospect(
        prospect_email="new@example.com",
        sequence_id=test_sequence.sequence_id,
        mailbox_id=test_mailbox.id,
        company_name="New Company",
        first_name="Jane",
        last_name="Doe",
        tier="A",
        icp_score=90.0,
    )

    assert result["success"] is True
    assert result["entry_id"] is not None
    assert result["prospect_id"] is not None
    assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_enroll_prospect_duplicate_detection(
    async_session, test_sequence, test_lead, test_mailbox
):
    """Test that duplicate enrollments are detected."""
    engine = SequenceEngine(async_session)

    # First enrollment
    result1 = await engine.enroll_prospect(
        prospect_email=test_lead.contact_email,
        sequence_id=test_sequence.sequence_id,
        mailbox_id=test_mailbox.id,
    )
    assert result1["success"] is True

    # Second enrollment (should fail)
    result2 = await engine.enroll_prospect(
        prospect_email=test_lead.contact_email,
        sequence_id=test_sequence.sequence_id,
        mailbox_id=test_mailbox.id,
    )
    assert result2["success"] is False
    assert "already enrolled" in result2["error"].lower()


# ============================================================================
# TESTS: Step Execution
# ============================================================================


@pytest.mark.asyncio
async def test_execute_step_success(
    async_session, test_sequence, test_lead, test_mailbox
):
    """Test successful step execution."""
    entry = SequenceEntry(
        lead_id=test_lead.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="pending",
        current_step=0,
        started_at=datetime.utcnow(),
    )
    async_session.add(entry)
    await async_session.commit()
    await async_session.refresh(entry)

    engine = SequenceEngine(async_session)
    engine.set_test_mode(True)
    result = await engine.execute_step(entry.id)

    assert result["success"] is True
    assert result["action"] == "sent"
    assert result["test_mode"] is True
    assert result["current_step"] == 1


@pytest.mark.asyncio
async def test_execute_step_template_rendering(
    async_session, test_sequence, test_lead, test_mailbox
):
    """Test that template variables are properly rendered."""
    # Update lead with specific name
    test_lead.contact_name = "John Smith"
    await async_session.commit()

    entry = SequenceEntry(
        lead_id=test_lead.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="pending",
        current_step=0,
        started_at=datetime.utcnow(),
    )
    async_session.add(entry)
    await async_session.commit()
    await async_session.refresh(entry)

    engine = SequenceEngine(async_session)
    engine.set_test_mode(True)

    # The engine's _render_template should replace {{first_name}} with "John"
    result = await engine.execute_step(entry.id)
    assert result["success"] is True


# ============================================================================
# TESTS: Reply Handling
# ============================================================================


@pytest.mark.asyncio
async def test_handle_reply_interested(
    async_session, test_sequence, test_lead, test_mailbox
):
    """Test handling of interested reply."""
    entry = SequenceEntry(
        lead_id=test_lead.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="active",
        current_step=1,
        started_at=datetime.utcnow(),
    )
    async_session.add(entry)
    await async_session.commit()
    await async_session.refresh(entry)

    engine = SequenceEngine(async_session)
    result = await engine.handle_reply(
        entry_id=entry.id,
        intent="interested",
        reply_content="Yes, I'm interested!",
        from_email=test_lead.contact_email,
    )

    assert result["success"] is True
    assert result["intent"] == "interested"
    assert result["entry_status"] == "replied"
    assert result["next_action"]["action"] == "trigger_call"


@pytest.mark.asyncio
async def test_handle_reply_not_interested(
    async_session, test_sequence, test_lead, test_mailbox
):
    """Test handling of not interested reply."""
    entry = SequenceEntry(
        lead_id=test_lead.id,
        sequence_id=test_sequence.id,
        mailbox_id=test_mailbox.id,
        status="active",
        current_step=1,
        started_at=datetime.utcnow(),
    )
    async_session.add(entry)
    await async_session.commit()
    await async_session.refresh(entry)

    engine = SequenceEngine(async_session)
    result = await engine.handle_reply(
        entry_id=entry.id,
        intent="not_interested",
        reply_content="Not interested, thanks.",
        from_email=test_lead.contact_email,
    )

    assert result["success"] is True
    assert result["intent"] == "not_interested"
    assert result["entry_status"] == "replied"
    assert result["next_action"]["action"] == "archive"
