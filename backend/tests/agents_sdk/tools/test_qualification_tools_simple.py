"""
Simplified tests for qualification MCP tools.

Note: Full integration tests are blocked by openai.__spec__ environment issue in transformers package.
These tests verify the tool interface without triggering the full import chain.
"""
import pytest


def test_qualification_tools_module_exists():
    """Test that qualification_tools module can be imported."""
    from app.agents_sdk.tools import qualification_tools
    assert qualification_tools is not None


def test_qualify_lead_tool_exists():
    """Test that qualify_lead_tool is defined."""
    from app.agents_sdk.tools import qualification_tools
    assert hasattr(qualification_tools, 'qualify_lead_tool')


def test_search_leads_tool_exists():
    """Test that search_leads_tool is defined."""
    from app.agents_sdk.tools import qualification_tools
    assert hasattr(qualification_tools, 'search_leads_tool')


def test_tools_exported_in_init():
    """Test that tools are exported in __init__.py."""
    from app.agents_sdk.tools import qualify_lead_tool, search_leads_tool
    assert qualify_lead_tool is not None
    assert search_leads_tool is not None


def test_qualify_lead_tool_has_correct_attributes():
    """Test that qualify_lead_tool has LangChain tool attributes."""
    from app.agents_sdk.tools import qualify_lead_tool
    # LangChain tools have a name attribute
    assert hasattr(qualify_lead_tool, 'name')
    assert hasattr(qualify_lead_tool, 'description')
    # It should be callable/invocable
    assert hasattr(qualify_lead_tool, 'invoke') or callable(qualify_lead_tool)


def test_search_leads_tool_has_correct_attributes():
    """Test that search_leads_tool has LangChain tool attributes."""
    from app.agents_sdk.tools import search_leads_tool
    # LangChain tools have a name attribute
    assert hasattr(search_leads_tool, 'name')
    assert hasattr(search_leads_tool, 'description')
    # It should be callable/invocable
    assert hasattr(search_leads_tool, 'invoke') or callable(search_leads_tool)
