# Security model and control requirements

## Protected assets

Task instructions/results, privileged approval decisions, source-code change proposals, institutional reference material, audit records, identity configuration, model/provider credentials, and future integration credentials.

## Threats addressed in this baseline

- **Role spoofing:** roles are not accepted from request headers.
- **Unauthenticated requests:** denied by default.
- **Privilege escalation via unknown tools/actions:** allow-list policy denies unknown tools and high-impact actions.
- **Self-approval:** requester cannot approve their own request.
- **Duplicate submission:** idempotency key constraint; conflicting reuse returns a conflict.
- **Audit mutation through ordinary SQL:** update/delete triggers and a hash chain make accidental/ordinary tampering detectable.
- **Exception leakage:** agent exception message is not persisted to the task record or audit event.
- **Prompt injection:** adapter contract treats retrieved text and model output as untrusted; production adapters must implement explicit separation of instructions and data.

## Residual risks / production blockers

- Static bearer tokens are not a replacement for enterprise identity, short-lived OAuth/OIDC credentials, mTLS, or workload identity.
- SQLite is single-node evaluation storage, not an HA transactional production store.
- A local hash chain is not a digital signature or independently immutable log; a host/database administrator can rewrite the entire database.
- No rate limiter, distributed queue, tenant cryptographic isolation, network policy, KMS/HSM, model gateway, egress proxy, or provider adapter is included.
- No independent penetration test, threat-model signoff, regulatory mapping, or operational resilience exercise has been performed.
- The default agent does not call a model; model integration requires a separate reviewed change.

## Mandatory production controls

1. Enterprise identity (OIDC/OAuth2 or mTLS) with short-lived credentials, MFA for humans, service identities, token revocation, and role lifecycle controls.
2. Durable transactional datastore with migrations, backups, point-in-time recovery, tested restore, and access separation.
3. Signed audit checkpoints exported to separately controlled append-only/WORM storage; time synchronization and retention policy.
4. Central secret manager/KMS, no secrets in prompts or logs, key rotation, least privilege, and documented emergency revocation.
5. Network egress allow-list, private service networking, workload isolation, request quotas, and denial-of-service protections.
6. Independent security review, SAST, dependency/SBOM scanning, secret scanning, container scanning, and software provenance/signing.
7. Human-controlled release pipeline with protected branches, required reviews, environment approvals, and tested rollback.
8. Per-tool schemas, policy tests, replay protection, idempotency, timeouts, circuit breakers, and explicit failure modes.

## Financial safety boundary

This control plane must not independently move money, sign financial instructions, establish legal settlement finality, or represent a ledger update as legally final. Such capabilities require distinct authorization systems, legally reviewed operating procedures, independent controls, and specific deployment approval. They remain denied in the initial baseline.
