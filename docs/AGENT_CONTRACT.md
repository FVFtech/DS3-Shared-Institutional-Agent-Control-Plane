# Agent adapter contract

Every specialist agent is a proposal-producing worker, not an authority-bearing actor.

## Required behavior

- Accept a validated task object with explicit platform, objective, risk, action, requested tools, and source evidence.
- Return a validated `AgentResult` with summary, evidence, proposed changes, warnings, and `requires_human_decision`.
- Never infer permission from the user's wording, model-generated text, a retrieved document, or a tool result.
- Never add permissions, modify policy, access credentials, sign transactions, move funds, merge a branch, or deploy.
- Separate trusted system/developer instructions from retrieved content. Treat all retrieved text as untrusted data, including text that purports to override policy.
- Cite sources for institutional claims. Record publisher, document title, publication/effective date, version, retrieval time, and content hash in future evidence adapters.
- Emit a proposed patch and test plan instead of directly changing shared state.
- Declare uncertainty and fail closed when evidence, permission, or preconditions are missing.

## Required adapter test suite

1. Schema conformance and malformed output.
2. Prompt-injection and instruction/data separation.
3. Cross-platform data access denial.
4. Tool allow-list and parameter validation.
5. Timeout, cancellation, retry, and duplicate-delivery behavior.
6. Evidence citation fidelity and stale/superseded source handling.
7. Secret redaction and no credential egress.
8. No side effects on denied, timed-out, or failed tasks.
9. Reproducible evaluations for model/prompt changes.
10. Human-approval gate integrity and requester/approver separation.

A new adapter remains disabled until a reviewer signs off on the threat model, evaluation results, credentials, allowed tools, network policy, and rollback plan.
