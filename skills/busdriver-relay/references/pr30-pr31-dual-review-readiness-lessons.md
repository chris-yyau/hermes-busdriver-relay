# PR #30/#31 guardrails + dual-review readiness lessons

Use when continuing `hermes-busdriver-relay` after the finalization-status / dual-review readiness slices, especially when the user says to keep using subagents until relay work is complete.

## Durable workflow lessons

- After each merged slice, do not stop at the merge if the user asked to complete the relay. Refresh Phase 0 on clean `main`, pick the next smallest safe non-mutating/status slice from live docs, and dispatch subagents immediately.
- Keep main Hermes as operator/finalizer: subagents may edit the worktree, but main Hermes must re-read the diff, run focused/full contract tests, smoke, deliver verify, PR-grind, merge, and post-merge cleanup.
- Treat read-only envelopes as evidence only. `finalization_guardrails`, `dual_review_readiness`, and future pre-PR evidence summaries must never imply commit/push/PR/merge/marker-write authority.

## Finalization guardrails slice pattern

- Add self-describing status payloads with `schema`, `version`, and `read_only: true` so downstream readers can fail closed on unknown shapes.
- Mirror top-level guardrails into the handoff envelope exactly; tests should assert the mirror.
- Explicitly list unsupported high-risk operations: `raw_codex_exec`, `non_codex_agent_enablement`, and `autonomous_git_github_mutation`, in addition to git/GitHub finalization and Busdriver marker writes.
- Test recursively that every finalization/mutation/dispatch/programmatic-execution authority key is false. Include keys beyond the traditional finalization flags (`dispatch_allowed`, `mutation_allowed`, `programmatic_execution_allowed`).

## Dual-review readiness slice pattern

- A safe intermediate step is a **read-only** `dual_review_readiness` envelope that reports programmatic litmus/pre-PR dual-review execution as unsupported while surfacing needed relay roles (`relay.litmus.reviewer`, `relay.pr.lead`, `relay.pr.backstop`) as advisory evidence.
- Forward `--relay-config` into Phase-0 status from finalization-readiness when the envelope needs configured relay role evidence.
- Keep `ok: false`, `programmatic_execution_supported: false`, `programmatic_execution_allowed: false`, `dispatch_allowed: false`, and all authority flags false.
- Do not remove `programmatic-litmus-pre-pr-dual-review` from `finalization_guardrails.remaining_work`; role-readiness evidence is not an implementation of programmatic review.

## Pre-PR dual-review evidence summary next slice

A safe follow-up slice is a read-only evidence summary derived **only** from already-sanitized `litmus_status.summary`:

- `fresh_read_only` only if `litmus_status.summary.decision.status == "pr_review_fresh"` and `pr_codex_lead`, `pr_backstop_verdict`, and `pr_review_passed` are all fresh for the branch diff.
- `commit_litmus_only` when only commit litmus is fresh.
- `stale_or_missing`, `blocked`, or `unavailable` otherwise.
- Missing, malformed, unsafe, authority-positive, or unavailable litmus evidence must never classify as fresh.
- Do not invoke reviewers, read raw marker contents, write markers, or grant finalization authority.

## PR-grind reviewer lessons

- Reviewer comments about docs/smoke consistency can be real blockers. If docs quote smoke output, update the smoke summary extractor and add a contract test; do not merely change docs.
- If a reviewer thread is still active after a fix push but evidence proves the issue is addressed, resolving the review thread is allowed as part of explicit Delivery Mode PR-grind finalization. Re-run latest-head PR-grind after resolving.
- When writing `gh pr create --body` shell strings, avoid unescaped backticks: they trigger shell command substitution. Prefer a temporary body file plus `gh pr edit/create --body-file` for bodies containing code identifiers.

## Verification checklist for these slices

- `git diff --check`
- focused contract tests for changed helpers
- full `tests/contract`
- `scripts/hermes-busdriver-smoke --plugin-root ~/.claude/plugins/marketplaces/busdriver --pretty`
- `scripts/hermes-busdriver-deliver --mode execute --operation verify ...`
- latest-head `execute --operation pr-grind` before merge
- post-merge: sync base, prune/delete branch, verify clean `main`, rerun tests/smoke
