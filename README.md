# DS3 Shared Institutional Agent Control Plane

A security-first control plane foundation shared by Digital Settlements (DS3), Secure Chain OS, and CHRONOS. It centralizes task intake, policy evaluation, human approval, task lifecycle, and tamper-evident audit events. It is intentionally **not** a financial execution engine and does not connect to a bank, blockchain, custodian, HSM, or production repository.

## Safety posture

- Execution is disabled by default (`DS3_ENABLE_EXECUTION=false`).
- Money movement, transaction signing, deployment, repository writes, secret access, and policy changes are denied by baseline policy.
- High/critical-risk tasks and proposed changes require approval; requester self-approval is denied.
- The bootstrap API token grants viewer-only access. Role claims are loaded from server-side token-hash configuration, never from client-supplied role headers.
- Unknown agent profiles and tools fail closed.
- Task submission is idempotent; reuse of a key for materially different work is rejected.
- Audit events are hash chained and guarded against UPDATE/DELETE using SQLite triggers. This is tamper-evidence, **not** regulatory-grade immutable/WORM storage; production must export events to independently controlled append-only storage.
- The built-in agent is a deterministic review-only scaffold. It does not invoke an LLM or external tools.

## Quick start

Python 3.11+ is required.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
python -m pip install -e '.[test]'
cp .env.example .env
export DS3_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export DS3_DATABASE_PATH=./var/control-plane.sqlite3
export DS3_ENABLE_EXECUTION=false
uvicorn control_plane.api:app --host 127.0.0.1 --port 8080
```

The API requires a bearer token by default. The bootstrap token grants only viewer permissions. For local-only tests, `DS3_REQUIRE_AUTH=false` grants a viewer-only development identity and must never be used in a deployed environment.

### Configure named principals

`DS3_PRINCIPAL_TOKENS_JSON` is a JSON object keyed by the SHA-256 hex digest of each individual bearer token. Values define the identity on the server. Example generator:

```bash
python - <<'PY'
import hashlib, json, secrets
raw = secrets.token_urlsafe(48)
claims = {hashlib.sha256(raw.encode()).hexdigest(): {
  "subject": "independent-approver-01",
  "roles": ["approver", "security_reviewer"],
  "platform_scopes": ["shared"]
}}
print("Bearer token (store in secret manager):", raw)
print("DS3_PRINCIPAL_TOKENS_JSON=", json.dumps(claims))
PY
```

Inject the bearer token and JSON claims through a secrets manager. Do not commit either value. The JSON configuration contains token hashes, not raw tokens, but still carries privileged identity claims and must be treated as sensitive. A shared token should not be used across people or services. For production, replace static-token authentication with an OIDC provider or mTLS-backed workload identity, signed claims, key rotation, and revocation.

## API surface

- `GET /health` — liveness/configuration summary; does not prove downstream readiness.
- `POST /v1/tasks` — authorize and create an idempotent task.
- `GET /v1/tasks/{task_id}` — task owner or administrator may read task.
- `POST /v1/approvals/{approval_id}/decision` — separate approver identity records approve/deny decision.
- `POST /v1/tasks/{task_id}/run` — executes only when the deployment explicitly enables execution and lifecycle gates pass.
- `GET /v1/audit/verify` — security reviewer/administrator verifies hash chain.
- `GET /v1/audit/events?limit=100` — security reviewer/administrator lists audit events.

Interactive OpenAPI docs are available at `/docs` outside `DS3_ENV=production`.

## Submit an analysis task

```bash
curl -sS http://127.0.0.1:8080/v1/tasks \\
  -H "Authorization: Bearer $DS3_API_TOKEN" \\
  -H 'Content-Type: application/json' \\
  -d '{
    "idempotency_key":"ds3-review-2026-0001",
    "platform":"ds3",
    "objective":"Review reconciliation workflow controls and identify missing tests",
    "agent_profile":"review-only",
    "action":"analyze",
    "risk_tier":"low",
    "requested_tools":[],
    "evidence":[],
    "metadata":{}
  }'
```

## Test and quality gates

```bash
ruff check src tests
mypy src/control_plane
pytest --cov=control_plane --cov-report=term-missing --cov-fail-under=80
```

CI also runs CodeQL. The workflows use pinned major action versions; production hardening should pin every action to a verified full commit SHA and use a centrally managed dependency-update process.

## Architecture

```text
API / Identity boundary
        |
        v
Policy Engine (fail closed) ----> Denial + audit event
        |
        v
Task Store + idempotency
        |
        +---- high risk / change ----> Independent approval record
        |
        v
Agent Adapter Interface (review-only default)
        |
        v
Result proposal + audit event (no implicit external side effects)
```

See `docs/ARCHITECTURE.md`, `docs/SECURITY_MODEL.md`, `docs/OPERATIONS.md`, and `docs/ROADMAP.md`.

## Explicit non-goals for this release

No production banking/payment connectivity, no transaction signing, no ledger writes, no autonomous repository merges, no autonomous deployment, no secrets retrieval, no unreviewed model self-modification, no claim of SOC 2/ISO/PCI/FFIEC compliance, and no claim that the SQLite log is immutable. Integrations must be added behind narrowly scoped adapters and independently assessed.
