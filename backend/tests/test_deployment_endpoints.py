"""Tests for deployment and monitoring endpoints."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import backend.server as server


class _ReadyDB:
    async def command(self, name: str):
        assert name == "ping"
        return {"ok": 1}


def _build_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(server, "_get_assistant", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(server, "_get_voice_router", lambda: SimpleNamespace())
    monkeypatch.setattr(server, "db", _ReadyDB())
    return TestClient(server.app)


def test_health_endpoint_reports_ok(monkeypatch: pytest.MonkeyPatch):
    client = _build_client(monkeypatch)

    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "jarvis-backend"


def test_metrics_endpoint_reports_runtime_data(monkeypatch: pytest.MonkeyPatch):
    client = _build_client(monkeypatch)

    response = client.get("/metrics")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "process" in data
    assert "system" in data
    assert data["process"]["pid"] > 0


def test_ready_endpoint_reports_ready(monkeypatch: pytest.MonkeyPatch):
    client = _build_client(monkeypatch)

    response = client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["status"] == "ready"
    assert data["checks"]["database"]["ready"] is True
