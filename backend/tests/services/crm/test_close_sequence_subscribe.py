"""
TDD Tests for CloseSequencesClient Bulk Subscribe (RED Phase)

Tests the bulk_subscribe() method for subscribing multiple contacts
to a sequence in a single operation.

Test Status: RED - bulk_subscribe() method does not exist yet
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from app.services.crm.close_sequences import CloseSequencesClient


# ========== Test Fixtures ==========

@pytest.fixture
def close_client():
    """Create CloseSequencesClient instance with mock API key."""
    with patch.dict("os.environ", {"CLOSE_API_KEY": "test_api_key_12345"}):
        client = CloseSequencesClient(api_key="test_api_key_12345")
        # Enable writes for testing
        client.write_enabled = True
        return client


@pytest.fixture
def sample_sequence_id():
    """Sample Close sequence ID (cold-outbound post-pivot)."""
    return "seq_6Uh4dSRawisSC4Bwlwr8d2"


@pytest.fixture
def sample_contact_ids():
    """Sample Close contact IDs for bulk operations."""
    return ["cont_111", "cont_222", "cont_333"]


@pytest.fixture
def sample_sender_data():
    """Sample sender override data."""
    return {
        "sender_email": "tim@coperniq.io",
        "sender_name": "Tim Kipper"
    }


@pytest.fixture
def mock_subscription_response():
    """Mock successful subscription response from Close API."""
    def create_response(contact_id: str, sequence_id: str) -> Dict[str, Any]:
        return {
            "id": f"sub_{contact_id[-3:]}",
            "status": "active",
            "contact_id": contact_id,
            "sequence_id": sequence_id,
            "created_at": "2025-12-15T10:00:00Z",
            "updated_at": "2025-12-15T10:00:00Z"
        }
    return create_response


@pytest.fixture
def mock_existing_subscription():
    """Mock existing subscription returned by get_contact_subscriptions."""
    def create_subscription(contact_id: str, sequence_id: str) -> List[Dict[str, Any]]:
        return [{
            "id": f"sub_existing_{contact_id[-3:]}",
            "status": "active",
            "contact_id": contact_id,
            "sequence_id": sequence_id,
            "created_at": "2025-12-10T10:00:00Z"
        }]
    return create_subscription


# ========== Test 1: Bulk Subscribe Enrolls Multiple Contacts ==========

@pytest.mark.asyncio
async def test_bulk_subscribe_contacts_to_sequence(
    close_client,
    sample_sequence_id,
    sample_contact_ids,
    mock_subscription_response
):
    """
    Test subscribing multiple contacts to a sequence.

    Given: 3 contact IDs and a sequence ID
    When: bulk_subscribe() is called
    Then: All 3 contacts are subscribed successfully
    And: subscribe_contact() is called 3 times
    """
    # Setup: Mock subscribe_contact to return successful subscriptions
    with patch.object(
        close_client,
        'subscribe_contact',
        new_callable=AsyncMock
    ) as mock_subscribe:
        # Configure mock to return different subscription for each contact
        mock_subscribe.side_effect = [
            mock_subscription_response(cid, sample_sequence_id)
            for cid in sample_contact_ids
        ]

        # Also mock get_contact_subscriptions to return no existing subscriptions
        with patch.object(
            close_client,
            'get_contact_subscriptions',
            new_callable=AsyncMock
        ) as mock_get_subs:
            mock_get_subs.return_value = []

            # Execute: Call bulk_subscribe
            result = await close_client.bulk_subscribe(
                contact_ids=sample_contact_ids,
                sequence_id=sample_sequence_id
            )

            # Assert: All contacts subscribed
            assert result["subscribed_count"] == 3
            assert result["already_subscribed"] == 0
            assert result["failed_count"] == 0
            assert len(result["errors"]) == 0
            assert len(result["subscriptions"]) == 3

            # Assert: subscribe_contact called 3 times
            assert mock_subscribe.call_count == 3

            # Assert: Each contact was subscribed
            for contact_id in sample_contact_ids:
                mock_subscribe.assert_any_await(
                    sequence_id=sample_sequence_id,
                    contact_id=contact_id,
                    sender_account_id=None,
                    sender_name=None,
                    sender_email=None
                )


# ========== Test 2: Already Subscribed Contacts Are Skipped ==========

@pytest.mark.asyncio
async def test_bulk_subscribe_skips_already_subscribed(
    close_client,
    sample_sequence_id,
    sample_contact_ids,
    mock_existing_subscription,
    mock_subscription_response
):
    """
    Test that contacts already in sequence are skipped.

    Given: 3 contacts, where 1 is already subscribed
    When: bulk_subscribe() is called with skip_already_subscribed=True
    Then: Only 2 contacts are subscribed
    And: subscribe_contact() is called 2 times (not 3)
    And: already_subscribed count is 1
    """
    # Setup: Mock get_contact_subscriptions
    # First contact is already subscribed, others are not
    with patch.object(
        close_client,
        'get_contact_subscriptions',
        new_callable=AsyncMock
    ) as mock_get_subs:
        async def get_subs_side_effect(contact_id: str, active_only: bool = True):
            if contact_id == sample_contact_ids[0]:
                # First contact already subscribed
                return mock_existing_subscription(contact_id, sample_sequence_id)
            return []

        mock_get_subs.side_effect = get_subs_side_effect

        # Mock subscribe_contact for the 2 new subscriptions
        with patch.object(
            close_client,
            'subscribe_contact',
            new_callable=AsyncMock
        ) as mock_subscribe:
            mock_subscribe.side_effect = [
                mock_subscription_response(sample_contact_ids[1], sample_sequence_id),
                mock_subscription_response(sample_contact_ids[2], sample_sequence_id)
            ]

            # Execute: Call bulk_subscribe
            result = await close_client.bulk_subscribe(
                contact_ids=sample_contact_ids,
                sequence_id=sample_sequence_id,
                skip_already_subscribed=True
            )

            # Assert: Only 2 new subscriptions
            assert result["subscribed_count"] == 2
            assert result["already_subscribed"] == 1
            assert result["failed_count"] == 0

            # Assert: subscribe_contact called only 2 times (not for already subscribed)
            assert mock_subscribe.call_count == 2

            # Assert: First contact NOT subscribed again
            for call in mock_subscribe.call_args_list:
                assert call[1]["contact_id"] != sample_contact_ids[0]


# ========== Test 3: Sender Override Works ==========

@pytest.mark.asyncio
async def test_subscribe_with_sender_override(
    close_client,
    sample_sequence_id,
    sample_contact_ids,
    sample_sender_data,
    mock_subscription_response
):
    """
    Test subscribing with Tim Kipper as sender.

    Given: Contact IDs and sender override data
    When: bulk_subscribe() is called with sender_email and sender_name
    Then: subscribe_contact() is called with correct sender parameters
    """
    # Setup: Mock methods
    with patch.object(
        close_client,
        'get_contact_subscriptions',
        new_callable=AsyncMock
    ) as mock_get_subs:
        mock_get_subs.return_value = []

        with patch.object(
            close_client,
            'subscribe_contact',
            new_callable=AsyncMock
        ) as mock_subscribe:
            mock_subscribe.side_effect = [
                mock_subscription_response(cid, sample_sequence_id)
                for cid in sample_contact_ids
            ]

            # Execute: Call bulk_subscribe with sender override
            result = await close_client.bulk_subscribe(
                contact_ids=sample_contact_ids,
                sequence_id=sample_sequence_id,
                sender_email=sample_sender_data["sender_email"],
                sender_name=sample_sender_data["sender_name"]
            )

            # Assert: All subscribed with sender override
            assert result["subscribed_count"] == 3
            assert mock_subscribe.call_count == 3

            # Assert: Each call included sender parameters
            for call in mock_subscribe.call_args_list:
                assert call[1]["sender_email"] == "tim@coperniq.io"
                assert call[1]["sender_name"] == "Tim Kipper"
                assert call[1]["sender_account_id"] is None


# ========== Test 4: Partial Failures Are Handled ==========

@pytest.mark.asyncio
async def test_bulk_subscribe_handles_partial_failures(
    close_client,
    sample_sequence_id,
    sample_contact_ids,
    mock_subscription_response
):
    """
    Test that failures are tracked but don't stop the entire operation.

    Given: 3 contacts where 1 will fail to subscribe
    When: bulk_subscribe() is called
    Then: 2 succeed, 1 fails
    And: failed_count is 1
    And: errors list contains failure details
    """
    # Setup: Mock subscribe_contact with one failure
    with patch.object(
        close_client,
        'get_contact_subscriptions',
        new_callable=AsyncMock
    ) as mock_get_subs:
        mock_get_subs.return_value = []

        with patch.object(
            close_client,
            'subscribe_contact',
            new_callable=AsyncMock
        ) as mock_subscribe:
            # First succeeds, second fails (returns None), third succeeds
            mock_subscribe.side_effect = [
                mock_subscription_response(sample_contact_ids[0], sample_sequence_id),
                None,  # Failure
                mock_subscription_response(sample_contact_ids[2], sample_sequence_id)
            ]

            # Execute: Call bulk_subscribe
            result = await close_client.bulk_subscribe(
                contact_ids=sample_contact_ids,
                sequence_id=sample_sequence_id
            )

            # Assert: 2 succeeded, 1 failed
            assert result["subscribed_count"] == 2
            assert result["failed_count"] == 1
            assert result["already_subscribed"] == 0

            # Assert: Errors tracked
            assert len(result["errors"]) == 1
            assert sample_contact_ids[1] in result["errors"][0]

            # Assert: Successful subscriptions returned
            assert len(result["subscriptions"]) == 2


# ========== Test 5: Empty Contact List ==========

@pytest.mark.asyncio
async def test_bulk_subscribe_empty_contact_list(
    close_client,
    sample_sequence_id
):
    """
    Test bulk_subscribe with empty contact list.

    Given: Empty contact_ids list
    When: bulk_subscribe() is called
    Then: Returns zero counts and empty lists
    And: No API calls are made
    """
    # Execute: Call bulk_subscribe with empty list
    result = await close_client.bulk_subscribe(
        contact_ids=[],
        sequence_id=sample_sequence_id
    )

    # Assert: All counts are zero
    assert result["subscribed_count"] == 0
    assert result["already_subscribed"] == 0
    assert result["failed_count"] == 0
    assert len(result["errors"]) == 0
    assert len(result["subscriptions"]) == 0


# ========== Test 6: Skip Already Subscribed Flag False ==========

@pytest.mark.asyncio
async def test_bulk_subscribe_force_resubscribe(
    close_client,
    sample_sequence_id,
    sample_contact_ids,
    mock_existing_subscription,
    mock_subscription_response
):
    """
    Test bulk_subscribe with skip_already_subscribed=False.

    Given: Contacts that are already subscribed
    When: bulk_subscribe() is called with skip_already_subscribed=False
    Then: subscribe_contact() is called even for already subscribed contacts
    """
    # Setup: All contacts already subscribed
    with patch.object(
        close_client,
        'get_contact_subscriptions',
        new_callable=AsyncMock
    ) as mock_get_subs:
        # All contacts return existing subscriptions
        async def get_subs_side_effect(contact_id: str, active_only: bool = True):
            return mock_existing_subscription(contact_id, sample_sequence_id)

        mock_get_subs.side_effect = get_subs_side_effect

        with patch.object(
            close_client,
            'subscribe_contact',
            new_callable=AsyncMock
        ) as mock_subscribe:
            mock_subscribe.side_effect = [
                mock_subscription_response(cid, sample_sequence_id)
                for cid in sample_contact_ids
            ]

            # Execute: Call bulk_subscribe with skip=False
            result = await close_client.bulk_subscribe(
                contact_ids=sample_contact_ids,
                sequence_id=sample_sequence_id,
                skip_already_subscribed=False
            )

            # Assert: All contacts subscribed (despite existing subscriptions)
            assert result["subscribed_count"] == 3
            assert result["already_subscribed"] == 0
            assert mock_subscribe.call_count == 3


# ========== Test 7: Rate Limiting and Error Handling ==========

@pytest.mark.asyncio
async def test_bulk_subscribe_handles_exceptions(
    close_client,
    sample_sequence_id,
    sample_contact_ids
):
    """
    Test that exceptions during subscription are handled gracefully.

    Given: subscribe_contact raises an exception for one contact
    When: bulk_subscribe() is called
    Then: Exception is caught and tracked in errors
    And: Processing continues for remaining contacts
    """
    # Setup: Mock subscribe_contact to raise exception on second contact
    with patch.object(
        close_client,
        'get_contact_subscriptions',
        new_callable=AsyncMock
    ) as mock_get_subs:
        mock_get_subs.return_value = []

        with patch.object(
            close_client,
            'subscribe_contact',
            new_callable=AsyncMock
        ) as mock_subscribe:
            # First succeeds, second raises exception, third succeeds
            async def subscribe_side_effect(
                sequence_id, contact_id, sender_account_id=None,
                sender_name=None, sender_email=None
            ):
                if contact_id == sample_contact_ids[1]:
                    raise Exception("API rate limit exceeded")
                return {
                    "id": f"sub_{contact_id[-3:]}",
                    "status": "active",
                    "contact_id": contact_id,
                    "sequence_id": sequence_id
                }

            mock_subscribe.side_effect = subscribe_side_effect

            # Execute: Call bulk_subscribe
            result = await close_client.bulk_subscribe(
                contact_ids=sample_contact_ids,
                sequence_id=sample_sequence_id
            )

            # Assert: 2 succeeded, 1 failed with exception
            assert result["subscribed_count"] == 2
            assert result["failed_count"] == 1

            # Assert: Error message includes exception details
            assert len(result["errors"]) == 1
            assert "rate limit" in result["errors"][0].lower()
            assert sample_contact_ids[1] in result["errors"][0]


# ========== Test 8: Return Value Structure ==========

@pytest.mark.asyncio
async def test_bulk_subscribe_return_structure(
    close_client,
    sample_sequence_id,
    sample_contact_ids,
    mock_subscription_response
):
    """
    Test that bulk_subscribe returns the correct structure.

    Expected return structure:
    {
        "subscribed_count": int,
        "already_subscribed": int,
        "failed_count": int,
        "errors": List[str],
        "subscriptions": List[Dict]
    }
    """
    # Setup: Mock successful subscriptions
    with patch.object(
        close_client,
        'get_contact_subscriptions',
        new_callable=AsyncMock
    ) as mock_get_subs:
        mock_get_subs.return_value = []

        with patch.object(
            close_client,
            'subscribe_contact',
            new_callable=AsyncMock
        ) as mock_subscribe:
            mock_subscribe.side_effect = [
                mock_subscription_response(cid, sample_sequence_id)
                for cid in sample_contact_ids
            ]

            # Execute
            result = await close_client.bulk_subscribe(
                contact_ids=sample_contact_ids,
                sequence_id=sample_sequence_id
            )

            # Assert: All required keys present
            assert "subscribed_count" in result
            assert "already_subscribed" in result
            assert "failed_count" in result
            assert "errors" in result
            assert "subscriptions" in result

            # Assert: Correct types
            assert isinstance(result["subscribed_count"], int)
            assert isinstance(result["already_subscribed"], int)
            assert isinstance(result["failed_count"], int)
            assert isinstance(result["errors"], list)
            assert isinstance(result["subscriptions"], list)

            # Assert: subscriptions contain subscription objects
            assert all(isinstance(s, dict) for s in result["subscriptions"])
            assert all("id" in s for s in result["subscriptions"])
            assert all("contact_id" in s for s in result["subscriptions"])
