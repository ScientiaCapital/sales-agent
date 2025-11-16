"""
Cleanup Duplicate Smart Views in Close CRM

This script removes duplicate smart views that were created by accident.
"""
import os
import asyncio
import httpx
from dotenv import load_dotenv
import logging
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env from project root
env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
load_dotenv(env_path)

CLOSE_API_KEY = os.getenv("CLOSE_API_KEY")
BASE_URL = "https://api.close.com/api/v1"

# Create Basic Auth header
auth_string = f"{CLOSE_API_KEY}:"
auth_bytes = auth_string.encode('ascii')
auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
AUTH_HEADER = f"Basic {auth_b64}"


async def list_smart_views():
    """List all smart views in Close CRM."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/saved_search/",
                headers={
                    "Authorization": AUTH_HEADER,
                    "Content-Type": "application/json"
                },
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                smart_views = data.get("data", [])
                return smart_views
            else:
                logger.error(f"Failed to list smart views: {response.status_code}")
                return []

    except Exception as e:
        logger.error(f"Error listing smart views: {e}")
        return []


async def delete_smart_view(view_id: str, view_name: str):
    """Delete a smart view by ID."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{BASE_URL}/saved_search/{view_id}/",
                headers={
                    "Authorization": AUTH_HEADER,
                    "Content-Type": "application/json"
                },
                timeout=10.0
            )

            if response.status_code in (200, 204):
                logger.info(f"✅ Deleted: {view_name} (ID: {view_id})")
                return True
            else:
                logger.error(f"Failed to delete {view_name}: {response.status_code}")
                return False

    except Exception as e:
        logger.error(f"Error deleting smart view {view_name}: {e}")
        return False


async def main():
    """Remove duplicate smart views."""
    if not CLOSE_API_KEY:
        logger.error("❌ CLOSE_API_KEY not found in .env file")
        return

    logger.info("=" * 80)
    logger.info("Close CRM - Cleanup Duplicate Smart Views")
    logger.info("=" * 80)

    # Get all smart views
    logger.info("\n[Step 1/2] Fetching all smart views...")
    smart_views = await list_smart_views()

    if not smart_views:
        logger.warning("No smart views found")
        return

    # Group by name to find duplicates
    views_by_name = {}
    for view in smart_views:
        name = view.get("name", "")
        if name not in views_by_name:
            views_by_name[name] = []
        views_by_name[name].append(view)

    # Display all smart views
    logger.info(f"\n📋 Found {len(smart_views)} total smart views:")
    for name, views in views_by_name.items():
        count = len(views)
        if count > 1:
            logger.info(f"   ❌ {name} - {count} copies (DUPLICATE)")
        else:
            logger.info(f"   ✅ {name} - 1 copy")

    # Find duplicates
    duplicates_to_delete = []
    for name, views in views_by_name.items():
        if len(views) > 1:
            # Keep the first one (oldest), delete the rest
            logger.info(f"\n🔍 Found {len(views)} copies of '{name}':")
            for i, view in enumerate(views):
                view_id = view.get("id")
                created = view.get("date_created", "unknown")
                if i == 0:
                    logger.info(f"   ✅ KEEP: {view_id} (created: {created})")
                else:
                    logger.info(f"   ❌ DELETE: {view_id} (created: {created})")
                    duplicates_to_delete.append((view_id, name))

    if not duplicates_to_delete:
        logger.info("\n✅ No duplicates found!")
        return

    # Delete duplicates
    logger.info(f"\n[Step 2/2] Deleting {len(duplicates_to_delete)} duplicate smart views...")
    deleted_count = 0
    for view_id, view_name in duplicates_to_delete:
        success = await delete_smart_view(view_id, view_name)
        if success:
            deleted_count += 1

    logger.info("\n" + "=" * 80)
    logger.info(f"✅ Cleanup Complete! Deleted {deleted_count} duplicate smart views")
    logger.info("=" * 80)

    # Show final state
    logger.info("\n📋 Remaining Smart Views:")
    remaining_views = await list_smart_views()
    for view in remaining_views:
        name = view.get("name")
        logger.info(f"   ✅ {name}")


if __name__ == "__main__":
    asyncio.run(main())
