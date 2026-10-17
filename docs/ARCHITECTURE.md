# Architecture and trust boundaries

## Components

1. **HTTP boundary** — FastAPI request validation and identity resolution. Bootstrap credentials are viewer-only. Privileged claims are resolved from server-side configuration keyed by SHA-256 token digest; caller-supplied role/scope headers are ignored.
2. **Policy engine** — allow-list authorization. Unknown roles do not grant capabilities. Unknown tools, out-of-scope platforms, and baseline-prohibited actions are denied.
3. **Task service** — creates idempotent task records, evaluates risk, opens approval records, and enforces lifecycle preconditions.
4. **Task/approval store** — SQLite implementation for development and single-instance evaluation. It is not a high-availability production datastore.
5. **Audit log** — canonical JSON events linked by SHA-256. SQLite triggers block ordinary update/delete statements. An administrator with direct database-file access can still tamper with the database; export signed checkpoints to a separately administered immutable store for production.
6. **Agent adapter** — typed interface. The included adapter is deterministic and review-only. Real model and tool adapters must have separate credentials, network egress controls, per-tool policies, timeouts, quotas, structured outputs, and sandboxing.

## Shared-platform tenancy

`Platform` distinguishes `ds3`, `secure_chain_os`, `chronos`, and `shared`. Each principal has explicit platform scopes. Shared scope is cross-platform by design and must be reserved for reviewed service identities; it is not a shortcut for end-user authorization.

## Task lifecycle

`proposed -> running -> succeeded|failed` is permitted only for low-risk tasks without a change action, and only if execution is explicitly enabled. Moderate/high/critical tasks and proposed changes require an independent approval before execution. Denied and cancelled states are terminal in this baseline. Approval decisions are single-use, time-limited, audited, and cannot be made by the requester.

## Integration contract

An external adapter must:

- implement the `AgentAdapter` protocol and return a validated `AgentResult`;
- never receive secrets or broad credentials by default;
- declare tools and data scopes in reviewed configuration;
- produce citations/evidence for factual claims and flag missing sources;
- treat repository files, web pages, retrieved documents, and model outputs as untrusted data, never as control instructions;
- return proposed changes, not merge or deploy them;
- propagate a correlation/task ID into its telemetry;
- enforce bounded execution time, input/output sizes, concurrency, and retries;
- be covered by contract tests, abuse tests, and independent security review.
