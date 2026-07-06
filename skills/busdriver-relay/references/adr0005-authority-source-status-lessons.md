# ADR0005 authority-source status slice lessons

Session context: continuing `hermes-busdriver-relay` after a skill-source drift sync, the next safe big slice was a read-only ADR0005 follow-up: expose ADR authority sources as machine-readable rows in `scripts/hermes-busdriver-finalization-contract-status` while keeping every authority/finalization/mutation flag false.

## Durable lessons

1. **Authority-source rows are status rows too.** If docs or consumers describe “every row” as policy-blocked with lifecycle flags, new top-level `authority_sources` rows must carry the same lifecycle booleans as `remaining_work` rows (`retired: false`, `implemented: false`) in addition to `capability_allowed: false` and `safe_to_execute_by_this_helper: false`. Reviewer bots can correctly flag this as a row-normalization compatibility issue.

2. **Keep compatibility fields stable.** Preserve `required_authority_sources` exactly while adding richer `authority_sources`; tests should assert the IDs match one-for-one and in order.

3. **Recursive false-authority tests should include new rows.** When adding any status row list to finalization helpers, route it through the existing recursive unsafe-boolean assertion so new fields cannot accidentally grant `commit_allowed`, `pr_allowed`, `merge_allowed`, `marker_write_allowed`, `dispatch_allowed`, `programmatic_execution_allowed`, or similar authority.

4. **Do not fabricate live authority evidence.** For read-only ADR0005 status surfaces, `evidence_required` should be explicit and non-empty, but `current_evidence` should remain empty/unavailable unless a later approved helper actually verifies that evidence. A read-only contract-status helper must not inspect target repos, GitHub, Busdriver markers, or relay run artifacts to fill those fields.

5. **Pi-draft wrapper failures need scoped reconciliation, not blind discard.** A Pi `hermes-busdriver-agent-draft` run can return overall `blocked` if Pi fails to emit `pi-result.json`, while the wrapper’s postflight still proves the tracked diff is in-scope and verifiers passed. In that case main Hermes may reconcile the scoped diff as a draft artifact, but must record the Pi artifact failure honestly and rerun Hermes/operator verification before Delivery Mode finalization.

6. **PR-grind feedback can be schema consistency, not code behavior.** Even when checks are green and merge state is clean, latest-head PR-grind must treat inline review comments about machine-readable contract consistency as actionable until fixed or explicitly resolved after evidence.

7. **After resolving an addressed review thread, restart latest-head PR-grind.** For machine-readable contract feedback, it is not enough to push the fix and rely on green checks. Verify the output shape directly, resolve the specific GitHub review thread only after evidence shows the comment is addressed, then rerun the bounded PR-grind loop against the new PR HEAD before merge.

8. **Verify merge side effects before retrying a failed merge command.** In Delivery Mode, `gh pr merge` or its wrapper can report a nonzero exit after the PR has already been merged and the local checkout fast-forwarded. If merge output indicates action occurred, inspect `gh pr view <pr> --json state,mergedAt,mergeCommit,headRefName,baseRefName` and local `git status`/`rev-parse` before retrying. If the PR is `MERGED`, continue cleanup/final audit from the observed merge commit instead of issuing another merge command.

## Suggested focused tests

- top-level `authority_sources` IDs exactly match `required_authority_sources`;
- every authority-source row has `status == policy_blocked`, non-empty `evidence_required`, `current_evidence == []`, `retired is False`, `implemented is False`, `capability_allowed is False`, `safe_to_execute_by_this_helper is False`, and the all-false authority map;
- representative evidence assertions for `schema_authority` (versioned schemas + contract tests) and `fresh_gate_review_evidence` (litmus/pre-PR/PR-grind freshness);
- recursive no-positive-authority assertion covers both `remaining_work` and `authority_sources`.
