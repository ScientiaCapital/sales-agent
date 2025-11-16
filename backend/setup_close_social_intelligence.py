"""
Setup Close CRM for Social Intelligence System

This script configures Close CRM with:
1. Custom field: "High Intent Flag" (boolean) - Marks contacts with 3+ email opens
2. Custom activity type: "Social Intelligence" - Stores LinkedIn/Twitter research
3. Smart View: "🔥 High-Intent ATL Contacts (3+ Opens)" - Filters hot prospects

Run this once before deploying the social intelligence pipeline.
"""
import os
import asyncio
import httpx
from dotenv import load_dotenv
import logging
import base64
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env from project root
env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
load_dotenv(env_path)

CLOSE_API_KEY = os.getenv("CLOSE_API_KEY")
BASE_URL = "https://api.close.com/api/v1"
TIM_KIPPER_USER_ID = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")

# Create Basic Auth header
auth_string = f"{CLOSE_API_KEY}:"
auth_bytes = auth_string.encode('ascii')
auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
AUTH_HEADER = f"Basic {auth_b64}"


async def create_custom_field(field_name: str, field_type: str, choices: list = None) -> str:
    """
    Create a custom field on Lead object.

    Args:
        field_name: Display name for the field
        field_type: Field type ('text', 'number', 'choices', 'datetime', etc.)
        choices: List of choice options for 'choices' type fields

    Returns:
        Custom field ID if successful, None otherwise
    """
    try:
        payload = {
            "name": field_name,
            "type": field_type,
            "editable_with_roles": ["admin", "user"],
        }

        if field_type == "choices" and choices:
            payload["choices"] = choices

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/custom_field/lead/",
                headers={
                    "Authorization": AUTH_HEADER,
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=10.0
            )

            if response.status_code in (200, 201):
                data = response.json()
                field_id = data.get('id')
                logger.info(f"✅ Created custom field: {field_name} (ID: {field_id})")
                return field_id
            elif response.status_code == 400:
                error_data = response.json()
                if "already exists" in str(error_data).lower():
                    logger.info(f"⚠️  Custom field '{field_name}' already exists")
                    return await get_custom_field_id(field_name)
                else:
                    logger.error(f"Failed: {response.text}")
                    return None
            else:
                logger.error(f"Failed: {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Error creating custom field '{field_name}': {e}")
        return None


async def get_custom_field_id(field_name: str) -> str:
    """Get the ID of an existing custom field by name."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/custom_field/lead/",
                headers={
                    "Authorization": AUTH_HEADER,
                    "Content-Type": "application/json"
                },
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                fields = data.get("data", [])
                for field in fields:
                    if field.get("name") == field_name:
                        return field.get("id")
                return None
            else:
                return None

    except Exception as e:
        logger.error(f"Error getting custom field ID: {e}")
        return None


async def create_custom_activity_type(name: str, description: str) -> str:
    """
    Create a custom activity type for storing social intelligence research.

    Args:
        name: Activity type name
        description: Activity type description

    Returns:
        Activity type ID if successful, None otherwise
    """
    try:
        payload = {
            "name": name,
            "description": description,
            "editable_with_roles": ["admin", "user"],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/custom_activity/",
                headers={
                    "Authorization": AUTH_HEADER,
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=10.0
            )

            if response.status_code in (200, 201):
                data = response.json()
                activity_id = data.get('id')
                logger.info(f"✅ Created custom activity type: {name} (ID: {activity_id})")
                return activity_id
            elif response.status_code == 400:
                error_data = response.json()
                if "already exists" in str(error_data).lower():
                    logger.info(f"⚠️  Custom activity type '{name}' already exists")
                    return "exists"
                else:
                    logger.error(f"Failed: {response.text}")
                    return None
            else:
                logger.error(f"Failed: {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Error creating custom activity type '{name}': {e}")
        return None


async def create_smart_view(name: str, query_obj: dict) -> str:
    """Create a Smart View (Saved Search) in Close CRM."""
    try:
        smart_view_payload = {
            "name": name,
            "object_type": "lead",
            "query": json.dumps(query_obj)
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/saved_search/",
                headers={
                    "Authorization": AUTH_HEADER,
                    "Content-Type": "application/json"
                },
                json=smart_view_payload,
                timeout=10.0
            )

            if response.status_code in (200, 201):
                data = response.json()
                logger.info(f"✅ Created Smart View: {name} (ID: {data.get('id')})")
                return data.get('id')
            elif response.status_code == 400:
                error_data = response.json()
                if "already exists" in str(error_data).lower():
                    logger.info(f"⚠️  Smart View '{name}' already exists")
                    return None
                else:
                    logger.error(f"Failed: {response.text}")
                    return None
            else:
                logger.error(f"Failed: {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Error creating Smart View '{name}': {e}")
        return None


async def create_high_intent_smart_view(high_intent_field_id: str):
    """
    Create Smart View for High-Intent ATL Contacts (3+ email opens).

    Filters for:
    - ATL contacts (Hot ATL or Validated ATL status)
    - High intent flag = true
    - Created by Tim Kipper
    - Last 7 days
    """
    from datetime import datetime, timedelta
    seven_days_ago = datetime.now() - timedelta(days=7)

    # Get status IDs from environment
    hot_atl_status = os.getenv("CLOSE_STATUS_HOT_ATL")
    validated_atl_status = os.getenv("CLOSE_STATUS_VALIDATED_ATL")

    query_obj = {
        "type": "and",
        "queries": [
            {"type": "object_type", "object_type": "lead"},

            # ATL contacts only (Hot ATL or Validated ATL)
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "status_id"},
                "condition": {
                    "type": "reference",
                    "reference_type": "status",
                    "object_ids": [hot_atl_status, validated_atl_status]
                }
            },

            # High intent flag = Yes
            {
                "type": "field_condition",
                "field": {"type": "custom_field", "custom_field_id": high_intent_field_id},
                "condition": {"type": "text", "value": "Yes"}
            },

            # Created by Tim Kipper
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "created_by"},
                "condition": {"type": "reference", "reference_type": "user", "object_ids": [TIM_KIPPER_USER_ID]}
            },

            # Last 7 days
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "date_created"},
                "condition": {"type": "moment_range", "gte": seven_days_ago.strftime("%Y-%m-%dT%H:%M:%SZ")}
            }
        ]
    }

    return await create_smart_view("🔥 High-Intent ATL Contacts (3+ Opens)", query_obj)


async def main():
    """Run Close CRM Social Intelligence setup."""
    if not CLOSE_API_KEY:
        logger.error("❌ CLOSE_API_KEY not found in .env file")
        return

    if not TIM_KIPPER_USER_ID:
        logger.error("❌ CLOSE_DEFAULT_OWNER_USER_ID not found")
        return

    logger.info("=" * 80)
    logger.info("Close CRM Social Intelligence Setup")
    logger.info("=" * 80)

    # Step 1: Create custom field for high intent flag
    logger.info("\n[Step 1/3] Creating custom field...")
    high_intent_field_id = await create_custom_field(
        "High Intent Flag",
        "choices",
        choices=["Yes", "No"]
    )

    if not high_intent_field_id:
        logger.warning("⚠️  Custom field creation via API is not supported on this plan")
        logger.warning("    You'll need to create it manually in Close CRM:")
        logger.warning("    1. Go to Settings → Custom Fields")
        logger.warning("    2. Create new field: 'High Intent Flag' (Dropdown/Choices)")
        logger.warning("    3. Add options: 'Yes', 'No'")
        logger.warning("    4. Save and get the field ID")
        logger.warning("")
        logger.warning("    Continuing with other setup steps...")
        # Don't return - continue with other steps

    # Step 2: Create custom activity type for social research
    logger.info("\n[Step 2/3] Creating custom activity type...")
    activity_type_id = await create_custom_activity_type(
        "Social Intelligence",
        "LinkedIn/Twitter research insights and talking points"
    )

    # Step 3: Create Smart View for high-intent contacts
    if high_intent_field_id:
        logger.info("\n[Step 3/3] Creating Smart View...")
        smart_view_id = await create_high_intent_smart_view(high_intent_field_id)
    else:
        logger.warning("\n[Step 3/3] Skipping Smart View creation (requires custom field first)")
        smart_view_id = None

    logger.info("\n" + "=" * 80)
    logger.info("✅ Close CRM Social Intelligence Setup Complete!")
    logger.info("=" * 80)

    logger.info("\n📋 What was configured:")
    if high_intent_field_id:
        logger.info("   ✅ 1. Custom Field: 'High Intent Flag' (Yes/No)")
        logger.info("      - Automatically set to 'Yes' when contact opens email 3+ times")
    else:
        logger.info("   ⚠️  1. Custom Field: 'High Intent Flag' - NEEDS MANUAL SETUP")
        logger.info("      - Go to Settings → Custom Fields → Create New")
        logger.info("      - Name: 'High Intent Flag', Type: Dropdown (Yes/No)")

    logger.info("")
    if activity_type_id:
        logger.info("   ✅ 2. Custom Activity Type: 'Social Intelligence'")
        logger.info("      - Stores LinkedIn/Twitter research notes")
    else:
        logger.info("   ⚠️  2. Custom Activity Type - May need manual setup")

    logger.info("")
    if smart_view_id:
        logger.info("   ✅ 3. Smart View: '🔥 High-Intent ATL Contacts (3+ Opens)'")
        logger.info("      - Filters for ATL contacts with 3+ email opens")
    else:
        logger.info("   ⚠️  3. Smart View - Can be created after custom field is ready")

    logger.info("\n🎯 Next Steps:")
    logger.info("   1. Go to Close CRM web interface")
    logger.info("   2. Check Smart Views in left sidebar")
    logger.info("   3. You'll see: 🔥 High-Intent ATL Contacts (3+ Opens)")
    logger.info("   4. Deploy social intelligence pipeline to start populating data")

    logger.info("\n💡 How it works:")
    logger.info("   - Pipeline scrapes LinkedIn/Twitter daily at 6 AM")
    logger.info("   - AI analyzes posts and creates email drafts in Close CRM")
    logger.info("   - When contact opens email 3+ times → High Intent Flag = 'Yes'")
    logger.info("   - Contact appears in Smart View → You call them ASAP!")
    logger.info("")


if __name__ == "__main__":
    asyncio.run(main())
