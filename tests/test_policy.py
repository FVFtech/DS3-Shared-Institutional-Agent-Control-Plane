from control_plane.models import ActionKind, Platform, Principal, RiskTier, TaskRequest
from control_plane.policy import PolicyEngine


def request(**overrides):
    base = dict(idempotency_key="policy-test-key-0001", platform=Platform.DS3,
                objective="Review a proposed reconciliation workflow", agent_profile="review-only",
                action=ActionKind.ANALYZE, risk_tier=RiskTier.LOW)
    base.update(overrides)
    return TaskRequest(**base)


def test_unauthenticated_fails_closed():
    result = PolicyEngine().evaluate(Principal(subject="alice", roles=frozenset({"administrator"})), request())
    assert not result.allowed
    assert result.reason_code == "AUTHENTICATION_REQUIRED"


def test_payment_movement_never_allowed_by_baseline():
    principal = Principal(subject="alice", roles=frozenset({"administrator"}), authenticated=True)
    result = PolicyEngine().evaluate(principal, request(action=ActionKind.MOVE_MONEY))
    assert not result.allowed
    assert result.reason_code == "ACTION_DISABLED_BY_BASELINE_POLICY"


def test_unknown_tool_denied():
    principal = Principal(subject="alice", roles=frozenset({"analyst"}), authenticated=True)
    result = PolicyEngine().evaluate(principal, request(requested_tools=frozenset({"shell_exec"})))
    assert not result.allowed
    assert result.reason_code == "UNKNOWN_TOOL_DENIED"


def test_high_risk_requires_approval():
    principal = Principal(subject="alice", roles=frozenset({"engineer"}), authenticated=True)
    result = PolicyEngine().evaluate(principal, request(action=ActionKind.PROPOSE_CHANGE, risk_tier=RiskTier.HIGH))
    assert result.allowed and result.requires_approval
