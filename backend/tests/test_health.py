"""Tests for health check endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint returns correct response."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Sales Agent API"
    assert data["version"] == "0.1.0"
    assert data["docs"] == "/api/docs"


def test_health_check():
    """Test basic health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "development"


def test_detailed_health_check():
    """Test detailed health check endpoint."""
    response = client.get("/api/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
    assert "services" in data
    assert data["services"]["api"] == "operational"
    # Database and Redis not configured yet
    assert data["services"]["database"] == "not_configured"
    assert data["services"]["redis"] == "not_configured"
    assert data["services"]["cerebras"] == "not_configured"
