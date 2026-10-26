import pytest
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)


def test_get_cloud_config():
    res = client.get("/api/ai/config")
    assert res.status_code == 200
    data = res.json()
    assert "active_provider" in data
    assert "available_providers" in data
    assert len(data["available_providers"]) >= 4
    # Check that top cloud providers exist
    provider_ids = [p["id"] for p in data["available_providers"]]
    assert "gemini" in provider_ids
    assert "groq" in provider_ids
    assert "openai" in provider_ids
    assert "openrouter" in provider_ids


def test_test_cloud_key_local():
    res = client.post("/api/ai/config/test", json={"provider": "local"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "local" in data["model"]


def test_test_cloud_key_missing():
    res = client.post("/api/ai/config/test", json={"provider": "gemini", "api_key": ""})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "API Key is required" in data["error"]


def test_update_cloud_config_local():
    res = client.post("/api/ai/config", json={"provider": "local"})
    assert res.status_code == 200
    data = res.json()
    assert data["active_provider"] == "local"
