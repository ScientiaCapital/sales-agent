"""
Create High-Intent Smart View in Close CRM

This script creates the "🔥 High-Intent ATL Contacts (3+ Opens)" Smart View
using the manually created custom field.
"""
import os
import asyncio
import httpx
from dotenv import load_dotenv
import logging
import base64
import json
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env from project root
env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
load_dotenv(env_path)

CLOSE_API_KEY = os.getenv("CLOSE_API_KEY")
BASE_URL = "https://api.close.com/api/v1"
TIM_KIPPER_USER_ID = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")

# Custom field ID provided by user
HIGH_INTENT_FIELD_ID = "cf_6lDArzDCbc6g92tqTPpcllDOptB8TbD6AcyCae6m2Gr"

# Create Basic Auth header
auth_string = f"{CLOSE_API_KEY}:"
auth_bytes = auth_string.encode('ascii')
auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
AUTH_HEADER = f"Basic {auth_b64}"


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


async def create_high_intent_smart_view():
    """
    Create Smart View for High-Intent ATL Contacts (3+ email opens).

    Filters for:
    - ATL contacts (Hot ATL or Validated ATL status)
    - High intent flag = "Yes"
    - Created by Tim Kipper
    - Last 7 days
    """
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

            # High intent flag = "Yes"
            {
                "type": "field_condition",
                "field": {"type": "custom_field", "custom_field_id": HIGH_INTENT_FIELD_ID},
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
    """Create the High-Intent Smart View."""
    if not CLOSE_API_KEY:
        logger.error("❌ CLOSE_API_KEY not found in .env file")
        return

    if not TIM_KIPPER_USER_ID:
        logger.error("❌ CLOSE_DEFAULT_OWNER_USER_ID not found")
        return

    logger.info("=" * 80)
    logger.info("Create High-Intent ATL Contacts Smart View")
    logger.info("=" * 80)

    logger.info(f"\n📋 Using custom field ID: {HIGH_INTENT_FIELD_ID}")
    logger.info(f"   Field name: High Intent Flag")

    logger.info("\n[Step 1/1] Creating Smart View...")
    smart_view_id = await create_high_intent_smart_view()

    if smart_view_id:
        logger.info("\n" + "=" * 80)
        logger.info("✅ Smart View Created Successfully!")
        logger.info("=" * 80)
        logger.info("\n📋 What was created:")
        logger.info("   ✅ Smart View: '🔥 High-Intent ATL Contacts (3+ Opens)'")
        logger.info("      - Filters for ATL contacts with High Intent Flag = 'Yes'")
        logger.info("      - Your HOTTEST prospects to call immediately")
        logger.info("")
        logger.info("\n🎯 Next Steps:")
        logger.info("   1. Go to Close CRM web interface")
        logger.info("   2. Check Smart Views in left sidebar")
        logger.info("   3. You'll see: 🔥 High-Intent ATL Contacts (3+ Opens)")
        logger.info("   4. Deploy social intelligence pipeline to start populating data")
        logger.info("")
        logger.info("\n💡 How it works:")
        logger.info("   - Pipeline scrapes LinkedIn/Twitter daily at 6 AM")
        logger.info("   - AI analyzes posts and creates email drafts in Close CRM")
        logger.info("   - When contact opens email 3+ times → High Intent Flag = 'Yes'")
        logger.info("   - Contact appears in Smart View → You call them ASAP!")
    else:
        logger.warning("\n⚠️  Smart View may already exist or there was an error")


if __name__ == "__main__":
    asyncio.run(main())
