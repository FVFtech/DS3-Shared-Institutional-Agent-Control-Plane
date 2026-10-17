import pytest

from control_plane.models import ActionKind, Platform, Principal, RiskTier, TaskRequest, TaskStatus
from control_plane.service import ControlPlaneService
from control_plane.store import ConflictError


def task(key="idempotency-key-0001", **overrides):
    payload = dict(idempotency_key=key, platform=Platform.DS3,
                   objective="Analyze a proposed collateral reconciliation flow",
                   agent_profile="review-only", action=ActionKind.ANALYZE, risk_tier=RiskTier.LOW)
    payload.update(overrides)
    return TaskRequest(**payload)


def principal(name="alice", *roles):
    return Principal(subject=name, roles=frozenset(roles or ("analyst",)),
                     platform_scopes=frozenset({Platform.SHARED}), authenticated=True)


def test_idempotency_returns_same_task(service):
    first, created1 = service.submit(principal(), task())
    second, created2 = service.submit(principal(), task())
    assert created1 is True
    assert created2 is False
    assert first.task_id == second.task_id


def test_idempotency_key_cannot_be_reused_for_other_objective(service):
    service.submit(principal(), task())
    with pytest.raises(ConflictError):
        service.submit(principal(), task(objective="Analyze a different workflow with the same key"))


def test_change_task_requires_approval(service):
    record, created = service.submit(principal("alice", "engineer"), task(
        key="change-key-00001", action=ActionKind.PROPOSE_CHANGE, risk_tier=RiskTier.HIGH))
    assert created and record.status == TaskStatus.AWAITING_APPROVAL
    assert record.approval_id is not None


def test_self_approval_forbidden(service):
    record, _ = service.submit(principal("alice", "engineer"), task(
        key="change-key-00002", action=ActionKind.PROPOSE_CHANGE, risk_tier=RiskTier.HIGH))
    with pytest.raises(PermissionError, match="SELF_APPROVAL_FORBIDDEN"):
        service.decide(principal("alice", "approver"), record.approval_id, "approve", "I reviewed this request carefully")


def test_approver_can_decide_for_other_person(service):
    record, _ = service.submit(principal("alice", "engineer"), task(
        key="change-key-00003", action=ActionKind.PROPOSE_CHANGE, risk_tier=RiskTier.HIGH))
    updated = service.decide(principal("bob", "approver"), record.approval_id, "approve", "Independent review completed")
    assert updated.status == TaskStatus.APPROVED


@pytest.mark.asyncio
async def test_execution_disabled_by_default(service):
    record, _ = service.submit(principal(), task())
    with pytest.raises(PermissionError, match="EXECUTION_DISABLED_BY_CONFIGURATION"):
        await service.run(principal(), record.task_id)

@pytest.mark.asyncio
async def test_low_risk_task_runs_when_explicitly_enabled(tmp_path):
    from control_plane.audit import AuditLog
    from control_plane.store import TaskStore
    active = ControlPlaneService(TaskStore(str(tmp_path / "run.db")), AuditLog(str(tmp_path / "run.db")), execution_enabled=True)
    record, _ = active.submit(principal(), task(key="run-low-risk-0001"))
    result = await active.run(principal(), record.task_id)
    assert result.status == TaskStatus.SUCCEEDED
    assert result.result is not None
    assert "No external tool was invoked" in result.result["summary"]


@pytest.mark.asyncio
async def test_moderate_risk_requires_approval_even_when_execution_enabled(tmp_path):
    from control_plane.audit import AuditLog
    from control_plane.store import TaskStore
    active = ControlPlaneService(TaskStore(str(tmp_path / "run2.db")), AuditLog(str(tmp_path / "run2.db")), execution_enabled=True)
    record, _ = active.submit(principal(), task(key="run-medium-risk-0001", risk_tier=RiskTier.MODERATE))
    with pytest.raises(PermissionError, match="EXPLICIT_APPROVAL_REQUIRED"):
        await active.run(principal(), record.task_id)


def test_non_approver_cannot_decide(service):
    record, _ = service.submit(principal("alice", "engineer"), task(
        key="change-key-00004", action=ActionKind.PROPOSE_CHANGE, risk_tier=RiskTier.HIGH))
    with pytest.raises(PermissionError, match="APPROVER_ROLE_REQUIRED"):
        service.decide(principal("bob", "analyst"), record.approval_id, "deny", "Not authorized to decide")


def test_approval_cannot_be_decided_twice(service):
    record, _ = service.submit(principal("alice", "engineer"), task(
        key="change-key-00005", action=ActionKind.PROPOSE_CHANGE, risk_tier=RiskTier.HIGH))
    service.decide(principal("bob", "approver"), record.approval_id, "deny", "Independent reviewer denied request")
    with pytest.raises(ConflictError, match="already been decided"):
        service.decide(principal("carol", "approver"), record.approval_id, "approve", "Second reviewer tries to decide")
