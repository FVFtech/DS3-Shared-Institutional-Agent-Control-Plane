import hashlib
import json

from fastapi.testclient import TestClient

import control_plane.api as api_module
from control_plane.api import app
from control_plane.audit import AuditLog
from control_plane.service import ControlPlaneService
from control_plane.store import TaskStore


def test_auth_required_by_default(monkeypatch):
    monkeypatch.setenv("DS3_REQUIRE_AUTH", "true")
    monkeypatch.setenv("DS3_API_TOKEN", "test-token-with-sufficient-entropy")
    monkeypatch.setenv("DS3_PRINCIPAL_TOKENS_JSON", "{}")
    client = TestClient(app)
    response = client.get("/v1/audit/verify")
    assert response.status_code == 401


def test_bootstrap_token_cannot_claim_approver_with_headers(monkeypatch):
    monkeypatch.setenv("DS3_REQUIRE_AUTH", "true")
    monkeypatch.setenv("DS3_API_TOKEN", "test-token-with-sufficient-entropy")
    monkeypatch.setenv("DS3_PRINCIPAL_TOKENS_JSON", "{}")
    client = TestClient(app)
    response = client.get("/v1/audit/verify", headers={
        "Authorization": "Bearer test-token-with-sufficient-entropy",
        "X-Roles": "administrator,approver,security_reviewer",
        "X-Actor": "attacker",
    })
    assert response.status_code == 403


def test_invalid_token_rejected(monkeypatch):
    monkeypatch.setenv("DS3_REQUIRE_AUTH", "true")
    monkeypatch.setenv("DS3_API_TOKEN", "another-test-token-with-entropy")
    monkeypatch.setenv("DS3_PRINCIPAL_TOKENS_JSON", "{}")
    client = TestClient(app)
    response = client.get("/v1/audit/verify", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_health_and_task_submission(monkeypatch, tmp_path):
    db = str(tmp_path / "api.db")
    monkeypatch.setattr(api_module, "service", ControlPlaneService(TaskStore(db), AuditLog(db)))
    monkeypatch.setenv("DS3_REQUIRE_AUTH", "false")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    response = client.post("/v1/tasks", json={
        "idempotency_key": "api-idempotency-0001", "platform": "ds3",
        "objective": "Analyze a test reconciliation workflow", "agent_profile": "review-only",
        "action": "analyze", "risk_tier": "low", "requested_tools": [], "evidence": [], "metadata": {}
    })
    assert response.status_code == 202
    task_id = response.json()["task_id"]
    assert client.get(f"/v1/tasks/{task_id}").status_code == 200
    assert client.get("/v1/audit/verify").status_code == 403


def test_configured_approver_identity_is_server_side(monkeypatch):
    raw_token = "independent-approver-test-token-with-entropy"
    digest = hashlib.sha256(raw_token.encode()).hexdigest()
    monkeypatch.setenv("DS3_REQUIRE_AUTH", "true")
    monkeypatch.setenv("DS3_API_TOKEN", "bootstrap-viewer-token-with-entropy")
    monkeypatch.setenv("DS3_PRINCIPAL_TOKENS_JSON", json.dumps({digest: {
        "subject": "approver-1", "roles": ["approver", "security_reviewer"], "platform_scopes": ["shared"]
    }}))
    client = TestClient(app)
    response = client.get("/v1/audit/verify", headers={"Authorization": f"Bearer {raw_token}"})
    assert response.status_code == 200
    assert response.json()["valid"] is True
