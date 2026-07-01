# Deliver PR-grind delivery loop lessons

Session context: while delivering `hermes-busdriver-relay` PR #23, PR-grind/reviewer feedback repeatedly invalidated the prior clean state after amended commits. These lessons generalize to Delivery Mode work that wraps read-only PR-grind loops or updates PRs after review feedback.

## Delivery-loop discipline

1. Treat every amend, fix commit, or new PR head as stale proof.
   - Recompute the PR diff hash from `merge-base(base, HEAD)...HEAD`.
   - Re-run PR-mode Codex lead / litmus for that exact hash.
   - Re-dispatch the read-only security/bugs backstop for that exact hash.
   - If Busdriver marker persistence is required, route it only through a Busdriver/Claude trusted-writer runtime after the fresh Codex lead PASS exists; otherwise stop and report a blocker. Hermes must not write Busdriver markers directly.

2. Do not merge after “one clean review cycle” if a later push occurred.
   - Run latest-head `hermes-busdriver-pr-grind-loop` after the final push.
   - Merge only when the loop reports `ok=true`, `status=clean`, `clean=true`, `policy_gaps=[]`, and `latest_head` equals the PR head being merged.

3. When handing a backstop verdict to a trusted-writer runtime, prefer a checked temp JSON file plus stdin redirection inside that runtime:
   ```bash
   cat > /tmp/backstop-verdict.json <<'JSON'
   {"status":"PASS","model":"gpt-5.5","reviewed_diff_hash":"...","issues":[]}
   JSON
trusted-writer-runtime < /tmp/backstop-verdict.json
   ```
This avoids “pipe to interpreter” security warnings and leaves an inspectable payload. Hermes must stop if no Busdriver/Claude trusted-writer runtime is available.

## Implementation pitfalls found by reviewers

When adding or changing `hermes-busdriver-deliver --mode execute --operation pr-grind`:

- Validate the nested PR-grind loop decision status matches the envelope status before accepting a clean payload. A contradictory payload such as envelope `status=clean` with nested `decision.status=blocked` must fail closed.
- Timeout handlers must normalize `subprocess.TimeoutExpired.stdout` / `.stderr` through a bytes-safe tail/redaction helper before JSON serialization. Python can expose bytes here even when `subprocess.run(..., text=True)` was requested.
- `execute --operation verify` with no verifier commands should still write a Hermes-owned handoff artifact when in execute mode, so downstream operators/subagents have a durable blocked run envelope.
- `steps_for` / run-step labeling must be operation-aware. A `delivery_status_failed` preflight during PR-grind should mark the skipped step as `pr_grind`, not `verify`.
- Dead reason aliases in step mapping (for example a `pr_grind_clean` reason that production never emits) invite stale tests and should be removed unless a real producer exists.

## Regression coverage to add

Add contract tests for:

- clean PR-grind envelope with mismatched nested decision status is rejected;
- PR-grind loop timeout with bytes stdout/stderr remains JSON-safe;
- execute verify with no verifiers writes a blocked run artifact;
- PR-grind delivery-status failure labels the skipped operation as `pr_grind`;
- production dispatcher help/output does not expose loop script or fixture-result override knobs.

## Post-merge housekeeping

After a clean PR-grind and merge:

- verify GitHub PR state is `MERGED` and record the merge commit;
- fetch/prune and verify the remote feature branch is gone;
- delete the local feature branch if present;
- ensure the checkout is on the PR base branch and clean/synced;
- re-run the main contract/smoke checks and check main-branch CI;
- push a concise Hermes observation to claude-mem when configured/approved.
