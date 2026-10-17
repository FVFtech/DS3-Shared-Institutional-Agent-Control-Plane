# Release checklist

## Code and tests
- [ ] Review the complete diff; no unrelated files or generated databases.
- [ ] Tests, lint, type checks, dependency audit, SAST, and secret scan pass.
- [ ] CI workflow and third-party actions reviewed; actions pinned to full commit SHA for production.
- [ ] SBOM and provenance artifacts generated and retained.

## Security and governance
- [ ] Enterprise identity and privileged identity provisioning tested.
- [ ] Separation of duties and no-self-approval tested.
- [ ] All high-impact actions remain denied unless separately designed and authorized.
- [ ] Audit records are exported to independently controlled append-only storage.
- [ ] Secrets, key custody, network egress, data retention, and privacy controls approved.
- [ ] Independent security reviewer approves findings and residual risks.

## Operations
- [ ] Monitoring, alerting, dashboards, and incident runbook ready.
- [ ] Backups restored in a test environment; RPO/RTO verified.
- [ ] Rollback and kill-switch exercise completed.
- [ ] Load, concurrency, chaos, and recovery tests pass.
- [ ] Named business owner and human approver accept release.

## Financial workflow readiness
- [ ] Legal and compliance teams define technical vs. legal finality.
- [ ] Provider authorization and contracts are verified; no sandbox is represented as production.
- [ ] Ledger invariants, idempotency, reconciliation, exception handling, and operational recovery tested end-to-end.
- [ ] No production payment, custody, or signing capability enabled by this control plane without a separately approved design.
