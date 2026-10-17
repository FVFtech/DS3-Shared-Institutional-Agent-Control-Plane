# Operations runbook

## Local startup

1. Use Python 3.11+ and create an isolated virtual environment.
2. Install `pip install -e '.[test]'`.
3. Set a random `DS3_API_TOKEN` in the environment or secret manager.
4. Set `DS3_DATABASE_PATH` to a writable persistent path.
5. Keep `DS3_ENABLE_EXECUTION=false` until the runtime, identity, policy, persistence, and approval controls have been reviewed.
6. Start `uvicorn control_plane.api:app --host 127.0.0.1 --port 8080` for local evaluation.

## Audit verification

Run `ds3-control-plane verify-audit --database ./var/control-plane.sqlite3`. Exit code 2 means verification failed. Investigate immediately, preserve the database and host logs, and do not rewrite or delete records to make verification pass. The CLI is a diagnostic, not an independent forensic proof.

## Backup and recovery

The included SQLite database is for local/single-instance evaluation. Before any non-development deployment, define a backup policy, encrypt backups, isolate backup credentials, test restoration, and document RPO/RTO. WAL-aware backup procedures are required. Do not copy a live database file without a consistent snapshot procedure.

## Incident response

- Disable task execution and revoke affected tokens.
- Preserve application, host, identity-provider, network, and audit evidence.
- Verify the hash chain and export database plus relevant logs to controlled evidence storage.
- Identify affected task/approval IDs and downstream side effects; this release should have no financial side effects.
- Rotate credentials, rebuild from reviewed artifacts, run tests, and require independent approval before re-enabling.

## Readiness checklist

- [ ] Enterprise identity and short-lived credentials implemented.
- [ ] Privileged identities provisioned separately from requesters.
- [ ] Production database and migration/backup/restore strategy approved.
- [ ] External audit anchoring configured and independently administered.
- [ ] Observability, alerting, rate limiting, and incident response tested.
- [ ] Threat model and penetration test completed.
- [ ] Adapter-specific tool permissions reviewed.
- [ ] Deployment/rollback and disaster recovery exercises passed.
- [ ] Compliance counsel maps obligations for each intended asset, jurisdiction, and workflow.
- [ ] Production enablement approved by designated human authority.
