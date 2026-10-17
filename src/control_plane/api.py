"""HTTP API. Auth is a bearer token for bootstrap only; production should use OIDC/mTLS."""
from __future__ import annotations

import hmac
import hashlib
import json
import os
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from .audit import AuditLog
from .models import ApprovalDecision, HealthResponse, Platform, Principal, TaskRecord, TaskRequest
from .service import ControlPlaneService
from .store import ConflictError, NotFoundError, TaskStore


def build_service() -> ControlPlaneService:
    path = os.getenv("DS3_DATABASE_PATH", "./var/control-plane.sqlite3")
    Path(path).parent.mkdir(parents=True, exist_ok=True) if path != ":memory:" else None
    return ControlPlaneService(TaskStore(path), AuditLog(path),
        execution_enabled=os.getenv("DS3_ENABLE_EXECUTION", "false").lower() == "true",
        approval_ttl_seconds=int(os.getenv("DS3_APPROVAL_TTL_SECONDS", "1800")))


service = build_service()
app = FastAPI(title="DS3 Shared Institutional Agent Control Plane", version="0.1.0",
              docs_url="/docs" if os.getenv("DS3_ENV", "development") != "production" else None,
              redoc_url=None)


def get_principal(authorization: Annotated[str | None, Header()] = None) -> Principal:
    """Resolve identity from server-side token hashes; never trust client role headers."""
    require_auth = os.getenv("DS3_REQUIRE_AUTH", "true").lower() == "true"
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if not require_auth:
        # Explicit local-development bypass; it grants viewer-only permissions.
        return Principal(subject="local-development", roles=frozenset({"viewer"}),
                         platform_scopes=frozenset({Platform.SHARED}), authenticated=True)
    if not supplied:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    token_hash = hashlib.sha256(supplied.encode("utf-8")).hexdigest()
    try:
        configured = json.loads(os.getenv("DS3_PRINCIPAL_TOKENS_JSON", "{}"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=503, detail="Identity configuration invalid") from exc
    claims = configured.get(token_hash)
    if claims:
        try:
            subject = str(claims["subject"])
            roles = frozenset(str(role) for role in claims.get("roles", []))
            scopes = frozenset(Platform(scope) for scope in claims.get("platform_scopes", ["shared"]))
            return Principal(subject=subject, roles=roles, platform_scopes=scopes, authenticated=True)
        except (KeyError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=503, detail="Identity claim configuration invalid") from exc
    # Bootstrap token is deliberately viewer-only. It cannot approve or administer tasks.
    expected = os.getenv("DS3_API_TOKEN", "")
    if expected and hmac.compare_digest(supplied, expected):
        return Principal(subject="bootstrap-viewer", roles=frozenset({"viewer"}),
                         platform_scopes=frozenset({Platform.SHARED}), authenticated=True)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials",
                        headers={"WWW-Authenticate": "Bearer"})


@app.exception_handler(PermissionError)
async def permission_handler(_request: Request, exc: PermissionError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(ConflictError)
async def conflict_handler(_request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(NotFoundError)
async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", execution_enabled=service.execution_enabled, version="0.1.0")


@app.post("/v1/tasks", response_model=TaskRecord, status_code=202)
def submit_task(request: TaskRequest, principal: Annotated[Principal, Depends(get_principal)]) -> TaskRecord:
    try:
        task, _created = service.submit(principal, request)
        return task
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/v1/tasks/{task_id}", response_model=TaskRecord)
def get_task(task_id: UUID, principal: Annotated[Principal, Depends(get_principal)]) -> TaskRecord:
    try:
        task = service.store.get_task(task_id)
        if task.requested_by != principal.subject and "administrator" not in principal.roles:
            raise PermissionError("TASK_OWNERSHIP_REQUIRED")
        return task
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@app.post("/v1/approvals/{approval_id}/decision", response_model=TaskRecord)
def decide_approval(approval_id: UUID, request: ApprovalDecision,
                    principal: Annotated[Principal, Depends(get_principal)]) -> TaskRecord:
    if request.approval_id != approval_id:
        raise HTTPException(status_code=400, detail="Approval ID mismatch")
    try:
        return service.decide(principal, approval_id, request.decision, request.justification)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Approval not found") from exc


@app.post("/v1/tasks/{task_id}/run", response_model=TaskRecord)
async def run_task(task_id: UUID, principal: Annotated[Principal, Depends(get_principal)]) -> TaskRecord:
    try:
        return await service.run(principal, task_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@app.get("/v1/audit/verify")
def verify_audit(principal: Annotated[Principal, Depends(get_principal)]) -> dict[str, object]:
    if "security_reviewer" not in principal.roles and "administrator" not in principal.roles:
        raise HTTPException(status_code=403, detail="Security reviewer role required")
    valid, checked = service.audit.verify_chain()
    return {"valid": valid, "events_checked": checked}


@app.get("/v1/audit/events")
def list_audit(principal: Annotated[Principal, Depends(get_principal)],
               limit: Annotated[int, Query(ge=1, le=1000)] = 100) -> list[dict[str, object]]:
    if "security_reviewer" not in principal.roles and "administrator" not in principal.roles:
        raise HTTPException(status_code=403, detail="Security reviewer role required")
    return service.audit.list_events(limit)
