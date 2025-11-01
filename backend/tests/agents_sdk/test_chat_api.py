"""Test chat API endpoints."""
import pytest


def test_chat_api_file_exists():
    """Test chat API module exists."""
    import os
    chat_api_path = "backend/app/api/chat.py"
    assert os.path.exists(chat_api_path)


def test_chat_router_can_be_defined():
    """Test chat router is properly defined (structure check)."""
    with open("backend/app/api/chat.py", "r") as f:
        content = f.read()

        # Check key components exist
        assert "router = APIRouter" in content
        assert "def sr_bdr_chat" in content
        assert "def pipeline_manager_chat" in content
        assert "def customer_success_chat" in content
        assert "def get_session" in content
        assert "def delete_session" in content

        # Check proper imports
        assert "from app.agents_sdk.agents import" in content
        assert "SRBDRAgent" in content
        assert "PipelineManagerAgent" in content
        assert "CustomerSuccessAgent" in content
