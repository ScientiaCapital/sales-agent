"""
Close CRM Task Integration

Enables task activity creation, retrieval, and completion through Close CRM's Task API.
Supports automated follow-up task creation from reply routing workflows.

API Documentation: https://developer.close.com/resources/tasks/
"""

from typing import Optional, Dict, List, Any
from datetime import date, datetime
import httpx
import logging
import base64
import os
from dotenv import load_dotenv

# Ensure env vars are loaded
load_dotenv()

logger = logging.getLogger(__name__)


class CloseTaskClient:
    """
    Close CRM task integration for creating and managing follow-up tasks.

    Features:
    - Create tasks with due dates and assignments
    - Retrieve tasks by lead, status, or assignee
    - Complete tasks with optional outcome notes
    - CLOSE_WRITE_DISABLED safety check for production
    - Rate limiting support via Redis

    Close Task API Details:
    - Endpoint: POST /task/
    - Auth: Basic auth with API key
    - Automatic lead association
    - Support for task types and priorities
    """

    BASE_URL = "https://api.close.com/api/v1"

    # Task types for categorization
    TASK_TYPE_FOLLOW_UP = "follow-up"
    TASK_TYPE_CALL = "call"
    TASK_TYPE_EMAIL = "email"
    TASK_TYPE_MEETING = "meeting"
    TASK_TYPE_OTHER = "other"

    def __init__(
        self,
        api_key: Optional[str] = None,
        redis_client: Optional[Any] = None,
    ):
        """
        Initialize Close task client.

        Args:
            api_key: Close API key (falls back to CLOSE_API_KEY env var)
            redis_client: Redis client for rate limiting (optional)
        """
        self.api_key = api_key or os.getenv("CLOSE_API_KEY")
        if not self.api_key:
            raise ValueError("Close API key is required. Set CLOSE_API_KEY env var or pass api_key.")

        self.redis = redis_client

        # Close uses Basic auth with format "api_key:" (note the colon)
        auth_string = f"{self.api_key}:"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        self.auth_header = f"Basic {auth_b64}"

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
        }

    def _is_write_disabled(self) -> bool:
        """Check if Close CRM writes are disabled."""
        return os.getenv("CLOSE_WRITE_DISABLED", "False").lower() in ("true", "1", "yes")

    async def create_task(
        self,
        lead_id: str,
        text: str,
        due_date: date,
        assigned_to: Optional[str] = None,
        task_type: str = "follow-up",
        contact_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a task in Close CRM.

        Creates a follow-up task associated with a lead for workflow automation.
        Used by reply routing to create automated follow-ups based on intent.

        Args:
            lead_id: Close lead ID (required)
            text: Task description/text (required)
            due_date: Due date for the task
            assigned_to: Close user ID to assign to (optional, defaults to lead owner)
            task_type: Type of task (follow-up, call, email, meeting, other)
            contact_id: Close contact ID to associate with (optional)

        Returns:
            Dict with task details:
            {
                "id": "task_xxx",
                "lead_id": "lead_xxx",
                "text": "Review reply from contact",
                "due_date": "2024-12-27",
                "assigned_to": "user_xxx",
                "is_complete": False,
                "created_at": "2024-12-26T12:00:00Z"
            }

        Raises:
            RuntimeError: If CLOSE_WRITE_DISABLED is True
            httpx.HTTPStatusError: If API request fails
            ValueError: If required parameters missing
        """
        try:
            # Check if writes are disabled
            if self._is_write_disabled():
                logger.warning("CLOSE_WRITE_DISABLED: Skipping create_task()")
                return {
                    "status": "disabled",
                    "message": "Close CRM writes are disabled",
                    "text": text,
                    "due_date": due_date.isoformat(),
                }

            if not lead_id or not text:
                raise ValueError("lead_id and text are required")

            # Build task payload
            payload = {
                "lead_id": lead_id,
                "text": text,
                "date": due_date.isoformat(),  # Close uses "date" field for due date
                "is_complete": False,
            }

            # Add contact association if provided
            if contact_id:
                payload["contact_id"] = contact_id

            # Set assigned user
            if assigned_to:
                payload["assigned_to"] = assigned_to
            else:
                # Use default owner from environment if configured
                default_owner = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")
                if default_owner:
                    payload["assigned_to"] = default_owner

            # Add task type in the text (Close doesn't have native task types)
            # We prefix the text for filtering
            if task_type and task_type != "follow-up":
                payload["_type"] = task_type  # Store for reference

            # Create task via Close API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/task/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"Task created in Close CRM: {result.get('id')} "
                    f"for lead {lead_id}: {text[:50]}... (due: {due_date})"
                )

                return {
                    "id": result.get("id"),
                    "lead_id": lead_id,
                    "contact_id": contact_id,
                    "text": result.get("text"),
                    "due_date": result.get("date"),
                    "assigned_to": result.get("assigned_to"),
                    "is_complete": result.get("is_complete", False),
                    "created_at": result.get("date_created"),
                    "task_type": task_type,
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close Task API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to create task in Close: {e}")
            raise

    async def get_tasks(
        self,
        lead_id: Optional[str] = None,
        is_complete: Optional[bool] = None,
        assigned_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Fetch tasks from Close CRM with optional filters.

        Retrieves tasks optionally filtered by lead, completion status, or assignee.

        Args:
            lead_id: Filter by Close lead ID (optional)
            is_complete: Filter by completion status (optional)
            assigned_to: Filter by assigned user ID (optional)
            limit: Maximum tasks to return (default 100)
            offset: Pagination offset (default 0)

        Returns:
            List of task dicts:
            [
                {
                    "id": "task_xxx",
                    "lead_id": "lead_xxx",
                    "text": "Follow up with contact",
                    "due_date": "2024-12-27",
                    "is_complete": False,
                    "assigned_to": "user_xxx",
                    "date_created": "2024-12-26T12:00:00Z"
                },
                ...
            ]

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        try:
            # Build query parameters
            params = {
                "_limit": limit,
                "_skip": offset,
            }

            if lead_id:
                params["lead_id"] = lead_id
            if is_complete is not None:
                params["is_complete"] = str(is_complete).lower()
            if assigned_to:
                params["assigned_to"] = assigned_to

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/task/",
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0,
                )

                response.raise_for_status()
                data = response.json()

                tasks = data.get("data", [])
                logger.info(
                    f"Retrieved {len(tasks)} tasks from Close CRM "
                    f"(lead_id={lead_id}, is_complete={is_complete})"
                )

                return tasks

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close Task API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to get tasks from Close: {e}")
            raise

    async def get_tasks_since(
        self,
        since: datetime,
        is_complete: Optional[bool] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Fetch tasks created or updated since a given timestamp.

        Used for syncing tasks to the local database.

        Args:
            since: Fetch tasks created/updated after this timestamp
            is_complete: Filter by completion status (optional)
            limit: Maximum tasks to return (default 200)

        Returns:
            List of task dicts with creation/update timestamps
        """
        try:
            params = {
                "date_created__gte": since.strftime("%Y-%m-%dT%H:%M:%S"),
                "_limit": limit,
                "_order_by": "date_created",
            }

            if is_complete is not None:
                params["is_complete"] = str(is_complete).lower()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/task/",
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0,
                )

                response.raise_for_status()
                data = response.json()

                tasks = data.get("data", [])
                logger.info(
                    f"Retrieved {len(tasks)} tasks created since {since}"
                )

                return tasks

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close Task API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to get tasks since {since}: {e}")
            raise

    async def complete_task(
        self,
        task_id: str,
        outcome: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mark a task as complete in Close CRM.

        Updates the task status to complete, optionally with outcome notes.

        Args:
            task_id: Close task ID
            outcome: Optional outcome/completion notes

        Returns:
            Dict with updated task details:
            {
                "id": "task_xxx",
                "is_complete": True,
                "completed_at": "2024-12-26T15:00:00Z",
                "outcome": "Contact responded positively"
            }

        Raises:
            RuntimeError: If CLOSE_WRITE_DISABLED is True
            httpx.HTTPStatusError: If API request fails
        """
        try:
            # Check if writes are disabled
            if self._is_write_disabled():
                logger.warning("CLOSE_WRITE_DISABLED: Skipping complete_task()")
                return {
                    "status": "disabled",
                    "message": "Close CRM writes are disabled",
                    "task_id": task_id,
                }

            # Build update payload
            payload = {
                "is_complete": True,
            }

            # Append outcome to task text if provided
            # Close doesn't have a dedicated outcome field for tasks
            if outcome:
                # Get current task to append outcome
                current_task = await self.get_task(task_id)
                if current_task:
                    current_text = current_task.get("text", "")
                    payload["text"] = f"{current_text}\n\n[Outcome]: {outcome}"

            # Update task via Close API
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.BASE_URL}/task/{task_id}/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"Task completed in Close CRM: {task_id} "
                    f"(outcome: {outcome[:30]}...)" if outcome else f"Task completed: {task_id}"
                )

                return {
                    "id": result.get("id"),
                    "is_complete": result.get("is_complete"),
                    "completed_at": result.get("date_updated"),
                    "text": result.get("text"),
                    "outcome": outcome,
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close Task complete API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to complete task in Close: {e}")
            raise

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific task by ID.

        Args:
            task_id: Close task ID

        Returns:
            Task dict or None if not found
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/task/{task_id}/",
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Task not found: {task_id}")
                return None
            logger.error(
                f"Close Task API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            raise

    async def delete_task(self, task_id: str) -> bool:
        """
        Delete a task from Close CRM.

        Args:
            task_id: Close task ID

        Returns:
            True if deleted successfully

        Raises:
            RuntimeError: If CLOSE_WRITE_DISABLED is True
            httpx.HTTPStatusError: If API request fails
        """
        try:
            # Check if writes are disabled
            if self._is_write_disabled():
                logger.warning("CLOSE_WRITE_DISABLED: Skipping delete_task()")
                return False

            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.BASE_URL}/task/{task_id}/",
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                response.raise_for_status()
                logger.info(f"Task deleted: {task_id}")
                return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close Task delete API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to delete task {task_id}: {e}")
            raise

    async def update_task(
        self,
        task_id: str,
        text: Optional[str] = None,
        due_date: Optional[date] = None,
        assigned_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update a task in Close CRM.

        Args:
            task_id: Close task ID
            text: New task text (optional)
            due_date: New due date (optional)
            assigned_to: New assignee user ID (optional)

        Returns:
            Updated task dict

        Raises:
            RuntimeError: If CLOSE_WRITE_DISABLED is True
            httpx.HTTPStatusError: If API request fails
        """
        try:
            # Check if writes are disabled
            if self._is_write_disabled():
                logger.warning("CLOSE_WRITE_DISABLED: Skipping update_task()")
                return {
                    "status": "disabled",
                    "message": "Close CRM writes are disabled",
                    "task_id": task_id,
                }

            # Build update payload with only provided fields
            payload = {}
            if text is not None:
                payload["text"] = text
            if due_date is not None:
                payload["date"] = due_date.isoformat()
            if assigned_to is not None:
                payload["assigned_to"] = assigned_to

            if not payload:
                logger.warning("No fields to update for task")
                return await self.get_task(task_id)

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.BASE_URL}/task/{task_id}/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result = response.json()

                logger.info(f"Task updated in Close CRM: {task_id}")
                return result

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close Task update API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to update task {task_id}: {e}")
            raise


__all__ = ["CloseTaskClient"]
