# Implementation roadmap

## Phase 0 — Baseline scaffold (this branch)

Typed task contracts, fail-closed policy engine, viewer-only bootstrap identity, server-side principal claims, approval workflow, idempotency, SQLite task store, hash-chained audit, deterministic review-only adapter, API, tests, CI and CodeQL workflows.

## Phase 1 — Identity and platform hardening

Integrate enterprise OIDC/OAuth2 or mTLS workload identity; short-lived tokens; MFA and approval identity assurance; platform and tenant isolation; secret manager; rate limiting; structured security telemetry; dependency and container scanning; action pinning by commit SHA.

## Phase 2 — Durable orchestration

Move to a production-grade transactional database; schema migrations; transactional outbox; durable queue; lease-based workers; cancellation/deadline semantics; concurrency and retry budgets; dead-letter queue; task replay/idempotency contract; operational dashboards and SLOs.

## Phase 3 — Controlled specialist agents

Add architecture, implementation, test, security, documentation, and release agents behind a model gateway. Require source citations, structured outputs, prompt-injection tests, tool-by-tool grants, sandboxed patch generation, reproducible evaluation, and human-reviewed pull requests.

## Phase 4 — Institutional knowledge plane

Ingest authoritative publications with publisher, title, jurisdiction, publication/effective date, version, retrieval timestamp, content hash, license/terms, and supersession status. Distinguish binding rules, official manuals, technical standards, vendor documentation, and secondary commentary. Never imply that an authority endorses DS3.

## Phase 5 — Production assurance

Independent threat-model review and penetration testing; disaster recovery; load/fault-injection tests; signed build provenance; SBOM and vulnerability remediation SLAs; operational controls and legal/compliance review. Keep all financial execution capabilities out of scope until separately designed and authorized.
