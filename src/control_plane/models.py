"""Typed domain models. Models describe intent; they do not confer authority."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)


class Platform(StrEnum):
    DS3 = "ds3"
    SECURE_CHAIN_OS = "secure_chain_os"
    CHRONOS = "chronos"
    SHARED = "shared"


class TaskStatus(StrEnum):
    PROPOSED = "proposed"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    CANCELLED = "cancelled"


class RiskTier(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ActionKind(StrEnum):
    READ = "read"
    ANALYZE = "analyze"
    PROPOSE_CHANGE = "propose_change"
    WRITE_REPOSITORY = "write_repository"
    DEPLOY = "deploy"
    MOVE_MONEY = "move_money"
    SIGN_TRANSACTION = "sign_transaction"
    CHANGE_POLICY = "change_policy"
    ACCESS_SECRET = "access_secret"


class Principal(StrictModel):
    subject: str = Field(min_length=1, max_length=200)
    roles: frozenset[str] = frozenset()
    platform_scopes: frozenset[Platform] = frozenset({Platform.SHARED})
    authenticated: bool = False


class EvidenceRef(StrictModel):
    source_id: str = Field(min_length=1, max_length=200)
    uri: str = Field(min_length=8, max_length=2048)
    title: str = Field(min_length=1, max_length=300)
    retrieved_at: datetime
    content_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    excerpt: str | None = Field(default=None, max_length=1200)


class TaskRequest(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=200)
    platform: Platform
    objective: str = Field(min_length=10, max_length=8000)
    agent_profile: str = Field(min_length=1, max_length=100)
    action: ActionKind = ActionKind.ANALYZE
    risk_tier: RiskTier = RiskTier.MODERATE
    requested_tools: frozenset[str] = frozenset()
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=50)
    metadata: dict[str, str] = Field(default_factory=dict, max_length=30)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if any(ord(c) < 32 for c in value):
            raise ValueError("idempotency_key contains control characters")
        return value


class TaskRecord(StrictModel):
    task_id: UUID = Field(default_factory=uuid4)
    idempotency_key: str
    platform: Platform
    objective: str
    agent_profile: str
    action: ActionKind
    risk_tier: RiskTier
    status: TaskStatus = TaskStatus.PROPOSED
    requested_by: str
    requested_tools: frozenset[str] = frozenset()
    evidence: list[EvidenceRef] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    approval_id: UUID | None = None
    result: dict[str, Any] | None = None
    error_code: str | None = None


class ApprovalRequest(StrictModel):
    task_id: UUID
    requested_by: str
    reason: str = Field(min_length=10, max_length=1000)
    expires_at: datetime


class ApprovalDecision(StrictModel):
    approval_id: UUID
    decision: str = Field(pattern=r"^(approve|deny)$")
    justification: str = Field(min_length=10, max_length=1000)


class AgentResult(StrictModel):
    summary: str = Field(min_length=1, max_length=12000)
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=50)
    proposed_changes: list[str] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=100)
    requires_human_decision: bool = True


class HealthResponse(StrictModel):
    status: str
    execution_enabled: bool
    version: str
    timestamp: datetime = Field(default_factory=utcnow)
