"""Agent interfaces and safe default implementation. No external LLM is invoked here."""
from __future__ import annotations

from typing import Protocol

from .models import AgentResult, TaskRecord


class AgentAdapter(Protocol):
    profile: str

    async def execute(self, task: TaskRecord) -> AgentResult: ...


class ReviewOnlyAgent:
    """Deterministic scaffold: returns a bounded plan, never executes tools or changes systems."""

    profile = "review-only"

    async def execute(self, task: TaskRecord) -> AgentResult:
        return AgentResult(
            summary=("Task accepted for controlled analysis only. No external tool was invoked and "
                     "no repository, production system, ledger, key, or payment rail was modified. "
                     f"Objective: {task.objective}"),
            evidence=task.evidence,
            proposed_changes=[
                "Identify authoritative requirements and cite versioned sources.",
                "Produce a minimal change plan with explicit preconditions and rollback.",
                "Run deterministic tests and independent security review before proposing a merge.",
            ],
            warnings=["Default adapter is a scaffold; connect a reviewed model/provider adapter before use."],
            requires_human_decision=True,
        )
