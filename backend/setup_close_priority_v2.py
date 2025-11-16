"""
Setup Close CRM Priority System v2 - Using Built-In Lead Status

This version uses Close CRM's built-in Lead Status field (works on all plans):
- Lead Status: "Hot ATL", "Validated ATL", "BTL", "New Lead"
- Description: Contains qualification score and contact level

Creates tiered Smart Views:
1. 🔥 Hot ATL Leads - status="Hot ATL", last 7 days
2. ⭐ Validated ATL Leads - status="Validated ATL"
3. 📋 BTL Leads - status="BTL"
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

# Load .env from parent directory
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)

CLOSE_API_KEY = os.getenv("CLOSE_API_KEY")
BASE_URL = "https://api.close.com/api/v1"
TIM_KIPPER_USER_ID = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")

# Create Basic Auth header
auth_string = f"{CLOSE_API_KEY}:"
auth_bytes = auth_string.encode('ascii')
auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
AUTH_HEADER = f"Basic {auth_b64}"


async def create_lead_status(status_label: str):
    """
    Create a Lead Status in Close CRM.

    Args:
        status_label: Status name (e.g., "Hot ATL")

    Returns:
        Status ID if successful, None otherwise
    """
    try:
        payload = {
            "label": status_label,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/status/lead/",
                headers={
                    "Authorization": AUTH_HEADER,
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=10.0
            )

            if response.status_code in (200, 201):
                data = response.json()
                logger.info(f"✅ Created lead status: {status_label} (ID: {data.get('id')})")
                return data.get('id')
            elif response.status_code == 400:
                error_data = response.json()
                if "already exists" in str(error_data).lower() or "duplicate" in str(error_data).lower():
                    logger.info(f"⚠️  Lead status '{status_label}' already exists")
                    return "exists"
                else:
                    logger.warning(f"Could not create status '{status_label}': {response.text}")
                    return None
            else:
                logger.warning(f"Could not create status '{status_label}': {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Error creating lead status '{status_label}': {e}")
        return None


async def get_lead_status_id(status_label: str):
    """Get the ID of an existing lead status by label."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/status/lead/",
                headers={
                    "Authorization": AUTH_HEADER,
                    "Content-Type": "application/json"
                },
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                statuses = data.get("data", [])
                for status in statuses:
                    if status.get("label") == status_label:
                        return status.get("id")
                return None
            else:
                return None

    except Exception as e:
        logger.error(f"Error getting lead status ID: {e}")
        return None


async def create_smart_view(name: str, query_obj: dict):
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


async def create_hot_atl_smart_view(status_id: str):
    """🔥 Hot ATL Leads - Decision-makers, created in last 7 days."""
    seven_days_ago = datetime.now() - timedelta(days=7)

    query_obj = {
        "type": "and",
        "queries": [
            {"type": "object_type", "object_type": "lead"},
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "date_created"},
                "condition": {"type": "moment_range", "gte": seven_days_ago.strftime("%Y-%m-%dT%H:%M:%SZ")}
            },
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "created_by"},
                "condition": {"type": "reference", "reference_type": "user", "object_ids": [TIM_KIPPER_USER_ID]}
            },
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "status_id"},
                "condition": {"type": "reference", "reference_type": "status", "object_ids": [status_id]}
            }
        ]
    }

    return await create_smart_view("🔥 Hot ATL Leads (Priority)", query_obj)


async def create_validated_atl_smart_view(status_id: str):
    """⭐ Validated ATL Leads - All decision-makers."""
    query_obj = {
        "type": "and",
        "queries": [
            {"type": "object_type", "object_type": "lead"},
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "created_by"},
                "condition": {"type": "reference", "reference_type": "user", "object_ids": [TIM_KIPPER_USER_ID]}
            },
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "status_id"},
                "condition": {"type": "reference", "reference_type": "status", "object_ids": [status_id]}
            }
        ]
    }

    return await create_smart_view("⭐ Validated ATL Leads", query_obj)


async def create_btl_smart_view(status_id: str):
    """📋 BTL Leads - Below-the-line contacts."""
    query_obj = {
        "type": "and",
        "queries": [
            {"type": "object_type", "object_type": "lead"},
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "created_by"},
                "condition": {"type": "reference", "reference_type": "user", "object_ids": [TIM_KIPPER_USER_ID]}
            },
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "status_id"},
                "condition": {"type": "reference", "reference_type": "status", "object_ids": [status_id]}
            }
        ]
    }

    return await create_smart_view("📋 BTL Leads (Lower Priority)", query_obj)


async def main():
    """Run Close CRM Priority System setup v2."""
    if not CLOSE_API_KEY:
        logger.error("❌ CLOSE_API_KEY not found in .env file")
        return

    if not TIM_KIPPER_USER_ID:
        logger.error("❌ CLOSE_DEFAULT_OWNER_USER_ID not found")
        logger.error("   Run setup_close_crm_config.py first")
        return

    logger.info("=" * 80)
    logger.info("Close CRM Priority System Setup v2 (Built-In Fields)")
    logger.info("=" * 80)

    # Step 1: Create lead statuses
    logger.info("\n[Step 1] Creating Lead Statuses...")

    hot_atl_id = await create_lead_status("Hot ATL")
    if hot_atl_id == "exists":
        hot_atl_id = await get_lead_status_id("Hot ATL")

    validated_atl_id = await create_lead_status("Validated ATL")
    if validated_atl_id == "exists":
        validated_atl_id = await get_lead_status_id("Validated ATL")

    btl_id = await create_lead_status("BTL")
    if btl_id == "exists":
        btl_id = await get_lead_status_id("BTL")

    new_lead_id = await create_lead_status("New Lead")
    if new_lead_id == "exists":
        new_lead_id = await get_lead_status_id("New Lead")

    logger.info(f"\nStatus IDs: Hot ATL={hot_atl_id}, Validated ATL={validated_atl_id}, BTL={btl_id}")

    # Step 2: Create Smart Views (only if we have valid status IDs)
    logger.info("\n[Step 2] Creating Smart Views...")

    if hot_atl_id:
        await create_hot_atl_smart_view(hot_atl_id)
    if validated_atl_id:
        await create_validated_atl_smart_view(validated_atl_id)
    if btl_id:
        await create_btl_smart_view(btl_id)

    logger.info("\n" + "=" * 80)
    logger.info("✅ Priority System v2 Setup Complete!")
    logger.info("=" * 80)

    logger.info("\n📊 Smart Views (in priority order):")
    logger.info("   1. 🔥 Hot ATL Leads (Priority) - Score >70, last 7 days")
    logger.info("   2. ⭐ Validated ATL Leads - All decision-makers")
    logger.info("   3. 📋 BTL Leads - Below-the-line (lower priority)")
    logger.info("   4. 🆕 My New Leads (Last 7 Days) - All new leads")

    logger.info("\n💡 Lead Status Values:")
    logger.info("   - Hot ATL: C-Level/VP/Director with qual score >70")
    logger.info("   - Validated ATL: Any decision-maker contact")
    logger.info("   - BTL: Individual contributors, lower-level roles")
    logger.info("   - New Lead: Uncategorized (will be auto-tagged)")

    logger.info("\n🎯 Pipeline will automatically:")
    logger.info("   - Set 'Hot ATL' for ATL contacts with score >70")
    logger.info("   - Set 'Validated ATL' for ATL contacts with score <70")
    logger.info("   - Set 'BTL' for below-the-line contacts")
    logger.info("   - Add qualification score to lead description")

    logger.info("\n📞 Your Call Workflow:")
    logger.info("   1. Open 🔥 Hot ATL Leads - Call these FIRST!")
    logger.info("   2. When empty, move to ⭐ Validated ATL Leads")
    logger.info("   3. Delegate 📋 BTL Leads to junior SDRs or nurture campaign")


if __name__ == "__main__":
    asyncio.run(main())
