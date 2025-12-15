import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_schedule_call_task_exists():
    """Celery task should be registered."""
    from app.services.calling.celery_tasks import schedule_call
    assert schedule_call is not None
    assert hasattr(schedule_call, 'delay')


def test_process_call_queue_task_exists():
    """Celery task for processing queue should exist."""
    from app.services.calling.celery_tasks import process_call_queue
    assert process_call_queue is not None


def test_retry_failed_call_task_exists():
    """Retry task should exist."""
    from app.services.calling.celery_tasks import retry_failed_call
    assert retry_failed_call is not None
