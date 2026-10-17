"""Fail-closed policy engine. Unknown roles, tools, actions, or risk tiers are denied."""
from __future__ import annotations

from dataclasses import dataclass

from .models import ActionKind, Platform, Principal, RiskTier, TaskRequest


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason_code: str
    requires_approval: bool


# Deliberately small defaults. Expand only through reviewed policy changes.
ROLE_ACTIONS: dict[str, frozenset[ActionKind]] = {
    "viewer": frozenset({ActionKind.READ, ActionKind.ANALYZE}),
    "analyst": frozenset({ActionKind.READ, ActionKind.ANALYZE}),
    "engineer": frozenset({ActionKind.READ, ActionKind.ANALYZE, ActionKind.PROPOSE_CHANGE}),
    "security_reviewer": frozenset({ActionKind.READ, ActionKind.ANALYZE, ActionKind.PROPOSE_CHANGE}),
    "operator": frozenset({ActionKind.READ, ActionKind.ANALYZE, ActionKind.PROPOSE_CHANGE}),
    "approver": frozenset({ActionKind.READ, ActionKind.ANALYZE}),
    "administrator": frozenset({ActionKind.READ, ActionKind.ANALYZE, ActionKind.PROPOSE_CHANGE}),
}

# These capabilities are never granted by this initial control plane.
ALWAYS_DENIED = frozenset({
    ActionKind.MOVE_MONEY,
    ActionKind.SIGN_TRANSACTION,
    ActionKind.CHANGE_POLICY,
    ActionKind.ACCESS_SECRET,
    ActionKind.DEPLOY,
    ActionKind.WRITE_REPOSITORY,
})
ALLOWED_TOOLS = frozenset({
    "read_repository", "read_documentation", "run_unit_tests", "static_analysis",
    "dependency_audit", "draft_patch", "query_approved_knowledge",
})


class PolicyEngine:
    def evaluate(self, principal: Principal, task: TaskRequest) -> PolicyDecision:
        if not principal.authenticated:
            return PolicyDecision(False, "AUTHENTICATION_REQUIRED", False)
        if task.action in ALWAYS_DENIED:
            return PolicyDecision(False, "ACTION_DISABLED_BY_BASELINE_POLICY", False)
        if task.platform not in principal.platform_scopes and Platform.SHARED not in principal.platform_scopes:
            return PolicyDecision(False, "PLATFORM_SCOPE_DENIED", False)
        actions: set[ActionKind] = set()
        for role in principal.roles:
            actions.update(ROLE_ACTIONS.get(role, frozenset()))
        if task.action not in actions:
            return PolicyDecision(False, "ROLE_ACTION_DENIED", False)
        unknown_tools = task.requested_tools - ALLOWED_TOOLS
        if unknown_tools:
            return PolicyDecision(False, "UNKNOWN_TOOL_DENIED", False)
        if task.risk_tier in {RiskTier.HIGH, RiskTier.CRITICAL}:
            return PolicyDecision(True, "HUMAN_APPROVAL_REQUIRED_HIGH_RISK", True)
        if task.action == ActionKind.PROPOSE_CHANGE:
            return PolicyDecision(True, "HUMAN_APPROVAL_REQUIRED_FOR_CHANGE", True)
        return PolicyDecision(True, "POLICY_ALLOWED", False)
