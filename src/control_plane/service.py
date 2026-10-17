"""Application service: authorization, task lifecycle, approvals, audit events."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from .agents import AgentAdapter, ReviewOnlyAgent
from .audit import AuditLog
from .models import (ActionKind, ApprovalRequest, Platform, Principal, RiskTier, TaskRecord,
                     TaskRequest, TaskStatus)
from .policy import PolicyEngine
from .store import ConflictError, TaskStore


class ControlPlaneService:
    def __init__(self, store: TaskStore, audit: AuditLog, *, execution_enabled: bool = False,
                 approval_ttl_seconds: int = 1800, policy: PolicyEngine | None = None,
                 agents: dict[str, AgentAdapter] | None = None) -> None:
        self.store = store
        self.audit = audit
        self.execution_enabled = execution_enabled
        self.approval_ttl_seconds = approval_ttl_seconds
        self.policy = policy or PolicyEngine()
        self.agents = agents or {"review-only": ReviewOnlyAgent()}

    def submit(self, principal: Principal, request: TaskRequest) -> tuple[TaskRecord, bool]:
        decision = self.policy.evaluate(principal, request)
        if not decision.allowed:
            self.audit.append(event_id=str(uuid4()), actor=principal.subject, event_type="task.denied",
                              subject_id=request.idempotency_key, payload={"reason_code": decision.reason_code})
            raise PermissionError(decision.reason_code)
        if request.agent_profile not in self.agents:
            raise ValueError("Unknown agent profile")
        now = datetime.now(timezone.utc)
        record = TaskRecord(
            idempotency_key=request.idempotency_key, platform=request.platform, objective=request.objective,
            agent_profile=request.agent_profile, action=request.action, risk_tier=request.risk_tier,
            status=TaskStatus.AWAITING_APPROVAL if decision.requires_approval else TaskStatus.PROPOSED,
            requested_by=principal.subject, requested_tools=request.requested_tools, evidence=request.evidence,
            created_at=now, updated_at=now,
        )
        record, created = self.store.create_task(record)
        if not created:
            return record, False
        self.audit.append(event_id=str(uuid4()), actor=principal.subject, event_type="task.created",
                          subject_id=str(record.task_id), payload={"platform": record.platform.value,
                          "risk_tier": record.risk_tier.value, "action": record.action.value,
                          "status": record.status.value})
        if decision.requires_approval:
            approval_id = uuid4()
            record.approval_id = approval_id
            approval = ApprovalRequest(task_id=record.task_id, requested_by=principal.subject,
                reason=f"Approval required for {request.action.value} / {request.risk_tier.value} task.",
                expires_at=now + timedelta(seconds=self.approval_ttl_seconds))
            self.store.create_approval(approval_id, approval)
            self.store.update_task(record)
            self.audit.append(event_id=str(uuid4()), actor="system:policy", event_type="approval.requested",
                              subject_id=str(approval_id), payload={"task_id": str(record.task_id),
                              "expires_at": approval.expires_at.isoformat()})
        return record, True

    def decide(self, principal: Principal, approval_id: UUID, decision: str, justification: str) -> TaskRecord:
        if not principal.authenticated or "approver" not in principal.roles:
            raise PermissionError("APPROVER_ROLE_REQUIRED")
        approval = self.store.get_approval(approval_id)
        req = ApprovalRequest.model_validate_json(approval["request_json"])
        if req.expires_at <= datetime.now(timezone.utc):
            raise ConflictError("Approval expired; submit a new request")
        if principal.subject == req.requested_by:
            raise PermissionError("SELF_APPROVAL_FORBIDDEN")
        decided = self.store.decide_approval(approval_id, decision, principal.subject, justification)
        task = self.store.get_task(req.task_id)
        task.status = TaskStatus.APPROVED if decision == "approve" else TaskStatus.DENIED
        self.store.update_task(task)
        self.audit.append(event_id=str(uuid4()), actor=principal.subject, event_type=f"approval.{decision}",
                          subject_id=str(approval_id), payload={"task_id": str(task.task_id),
                          "justification": justification, "decision_recorded_by": decided["decided_by"]})
        return task

    async def run(self, principal: Principal, task_id: UUID) -> TaskRecord:
        task = self.store.get_task(task_id)
        if task.requested_by != principal.subject and "administrator" not in principal.roles:
            raise PermissionError("TASK_OWNERSHIP_REQUIRED")
        if not self.execution_enabled:
            raise PermissionError("EXECUTION_DISABLED_BY_CONFIGURATION")
        if task.status not in {TaskStatus.PROPOSED, TaskStatus.APPROVED}:
            raise ConflictError(f"Task cannot run from status {task.status.value}")
        if task.risk_tier in {RiskTier.HIGH, RiskTier.CRITICAL, RiskTier.MODERATE} and task.status != TaskStatus.APPROVED:
            raise PermissionError("EXPLICIT_APPROVAL_REQUIRED")
        task.status = TaskStatus.RUNNING
        self.store.update_task(task)
        self.audit.append(event_id=str(uuid4()), actor=principal.subject, event_type="task.started",
                          subject_id=str(task.task_id), payload={"agent_profile": task.agent_profile})
        try:
            result = await self.agents[task.agent_profile].execute(task)
            task.result = result.model_dump(mode="json")
            task.status = TaskStatus.SUCCEEDED
            self.audit.append(event_id=str(uuid4()), actor=f"agent:{task.agent_profile}", event_type="task.succeeded",
                              subject_id=str(task.task_id), payload={"requires_human_decision": result.requires_human_decision,
                              "evidence_count": len(result.evidence), "warning_count": len(result.warnings)})
        except Exception as exc:
            # Do not persist exception messages; they may contain sensitive input or provider details.
            task.status = TaskStatus.FAILED
            task.error_code = "AGENT_EXECUTION_FAILED"
            self.audit.append(event_id=str(uuid4()), actor=f"agent:{task.agent_profile}", event_type="task.failed",
                              subject_id=str(task.task_id), payload={"error_code": task.error_code,
                              "exception_type": type(exc).__name__})
        self.store.update_task(task)
        return task
