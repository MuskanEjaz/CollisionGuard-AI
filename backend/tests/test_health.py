"""Tests for GET /health."""
import pytest
from fastapi.testclient import TestClient

from main import app
from schemas.health import HealthResponse

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_schema():
    """Response body must deserialise into HealthResponse without error."""
    response = client.get("/health")
    # Raises ValidationError if the schema contract is broken
    parsed = HealthResponse.model_validate(response.json())
    assert parsed is not None


def test_health_status_is_ok():
    response = client.get("/health")
    assert response.json()["status"] == "ok"


def test_health_contains_version():
    response = client.get("/health")
    body = response.json()
    assert "version" in body
    assert isinstance(body["version"], str)
    assert len(body["version"]) > 0


def test_health_components_present():
    response = client.get("/health")
    body = response.json()
    assert "components" in body
    assert "data_layer" in body["components"]
    assert body["components"]["data_layer"]["status"] == "ok"
