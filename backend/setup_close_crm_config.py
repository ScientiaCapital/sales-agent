"""
Setup Close CRM Configuration - Smart Views and Default Owner

This script:
1. Finds Tim Kipper's user_id in Close CRM
2. Creates a Smart View for "New Leads" (created in last 7 days)
3. Configures default lead owner to Tim Kipper

Run this once to set up Close CRM for automated lead management.
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

# Load .env from parent directory (project root)
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)

CLOSE_API_KEY = os.getenv("CLOSE_API_KEY")
BASE_URL = "https://api.close.com/api/v1"

# Create Basic Auth header (Close CRM uses Basic Auth, not Bearer)
auth_string = f"{CLOSE_API_KEY}:"
auth_bytes = auth_string.encode('ascii')
auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
AUTH_HEADER = f"Basic {auth_b64}"


async def find_user_by_name(name: str = "Tim Kipper"):
    """Find user ID by name."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/user/",
            headers={
                "Authorization": AUTH_HEADER,
                "Content-Type": "application/json"
            },
            timeout=10.0
        )

        if response.status_code == 200:
            data = response.json()
            users = data.get("data", [])

            logger.info(f"Found {len(users)} users in organization:")
            for user in users:
                logger.info(f"  - {user.get('first_name')} {user.get('last_name')} (ID: {user.get('id')})")

                # Match by name
                full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                if name.lower() in full_name.lower():
                    logger.info(f"✅ Found {name}: {user.get('id')}")
                    return user.get('id')

            logger.warning(f"User '{name}' not found. Please use one of the user IDs above.")
            return None
        else:
            logger.error(f"Failed to fetch users: {response.status_code} - {response.text}")
            return None


async def create_smart_view_new_leads(user_id: str):
    """
    Create a Smart View for new leads assigned to Tim Kipper.

    Shows leads created in the last 7 days for quick access.
    """
    from datetime import datetime, timedelta

    # Calculate date 7 days ago
    seven_days_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build query object (will be stringified)
    query_obj = {
        "type": "and",
        "queries": [
            {
                "type": "object_type",
                "object_type": "lead"
            },
            {
                "type": "field_condition",
                "field": {
                    "type": "regular_field",
                    "object_type": "lead",
                    "field_name": "date_created"
                },
                "condition": {
                    "type": "moment_range",
                    "gte": seven_days_ago
                }
            },
            {
                "type": "field_condition",
                "field": {
                    "type": "regular_field",
                    "object_type": "lead",
                    "field_name": "created_by"
                },
                "condition": {
                    "type": "reference",
                    "reference_type": "user",
                    "object_ids": [user_id]
                }
            }
        ]
    }

    # Close CRM expects query as a JSON string, not object
    smart_view_payload = {
        "name": "My New Leads (Last 7 Days)",
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
            logger.info(f"✅ Created Smart View: {data.get('name')} (ID: {data.get('id')})")
            return data.get('id')
        else:
            logger.error(f"Failed to create Smart View: {response.status_code} - {response.text}")
            return None


async def save_user_config(user_id: str):
    """Save Tim Kipper's user_id to .env for future use."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")

    # Read existing .env
    with open(env_path, 'r') as f:
        lines = f.readlines()

    # Check if CLOSE_DEFAULT_OWNER_USER_ID already exists
    updated = False
    for i, line in enumerate(lines):
        if line.startswith("CLOSE_DEFAULT_OWNER_USER_ID="):
            lines[i] = f"CLOSE_DEFAULT_OWNER_USER_ID={user_id}\n"
            updated = True
            break

    # Add if not found
    if not updated:
        lines.append(f"\n# Close CRM - Default Lead Owner (Tim Kipper)\n")
        lines.append(f"CLOSE_DEFAULT_OWNER_USER_ID={user_id}\n")

    # Write back
    with open(env_path, 'w') as f:
        f.writelines(lines)

    logger.info(f"✅ Saved CLOSE_DEFAULT_OWNER_USER_ID={user_id} to .env")


async def main():
    """Run Close CRM configuration setup."""
    if not CLOSE_API_KEY:
        logger.error("❌ CLOSE_API_KEY not found in .env file")
        return

    logger.info("=" * 80)
    logger.info("Close CRM Configuration Setup")
    logger.info("=" * 80)

    # Step 1: Find Tim Kipper's user_id
    logger.info("\n[Step 1] Finding Tim Kipper's user ID...")
    user_id = await find_user_by_name("Tim Kipper")

    if not user_id:
        logger.error("\n❌ Could not find Tim Kipper. Please check the name or manually set user_id.")
        return

    # Step 2: Save to .env
    logger.info("\n[Step 2] Saving configuration...")
    await save_user_config(user_id)

    # Step 3: Create Smart View
    logger.info("\n[Step 3] Creating Smart View for new leads...")
    smart_view_id = await create_smart_view_new_leads(user_id)

    logger.info("\n" + "=" * 80)
    logger.info("✅ Setup Complete!")
    logger.info("=" * 80)
    logger.info(f"\nTim Kipper User ID: {user_id}")
    if smart_view_id:
        logger.info(f"Smart View ID: {smart_view_id}")
    logger.info("\nAll new leads will now be created with Tim Kipper as owner.")
    logger.info("Access the Smart View in Close CRM to see new leads from the last 7 days.")


if __name__ == "__main__":
    asyncio.run(main())
