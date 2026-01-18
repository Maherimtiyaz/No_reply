import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_app_boots():
    """Test that the FastAPI app boots successfully"""
    assert app is not None
    assert app.title == "NoReply API"


def test_health_endpoint_returns_200():
    """Test that /health endpoint returns 200 OK"""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_response_format():
    """Test that /health endpoint returns correct format"""
    response = client.get("/health")
    data = response.json()
    
    assert "status" in data
    assert data["status"] == "ok"
    assert "service" in data
    assert data["service"] == "noreply-api"
    assert "version" in data
