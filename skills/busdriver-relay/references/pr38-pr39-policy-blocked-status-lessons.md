> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR38/PR39 Policy-Blocked Guardrail Status Lessons

Context: continuation after PR #36/#37. The next balanced relay slices were (1) code/test semantics: align finalization-readiness guardrail remaining-work rows with ADR 0005 `policy_blocked` contract-status semantics, and (2) docs/status refresh after merge.

## Durable lessons

- When `hermes-busdriver-finalization-contract-status` reports ADR 0005 remaining-work rows as `status=policy_blocked`, `hermes-busdriver-finalization-readiness.finalization_guardrails.remaining_work[*].status` should use the same `policy_blocked` vocabulary. Avoid split semantics where readiness says `not_implemented` while contract-status says `policy_blocked`; downstream status consumers should not have to reconcile two meanings for the same remaining-work IDs.
- Keep this alignment read-only: changing status vocabulary must not grant or imply commit/push/PR/merge/deploy/release/publish/marker-write authority. Regression checks should assert guardrail IDs match contract-status IDs and all authority flags remain false.
- After a code/status merge that intentionally changes published status semantics, immediately do a second small docs/status slice if README or `docs/CURRENT_STATUS.md` still references the previous PR or old verification evidence. Treat this as the “balanced” docs/tooling half, not as optional cleanup.

## Delivery-mode pitfalls confirmed

- Draft-agent postflight can return blocked because ignored files changed (`.codegraph`, `__pycache__`, `.pytest_cache`) even when tracked files and focused verifier pass. Do not delete unrelated ignored state blindly. Verify tracked diff and rerun tests from operator mode before finalization.
- Do not commit on `main` when creating a feature slice. If it happens, recover without rewriting remote history by creating a feature branch at the accidental commit, then moving local `main` back to `origin/main` before push/PR:

```bash
git switch -c <feature-branch>
git branch -f main origin/main
```

Then continue from the feature branch and verify `main` is clean/synced after merge.
- Some Busdriver scripts intentionally exit nonzero after a successful marker/review action or after printing next-step guidance. Read the structured output/marker files and run the status helper (`hermes-busdriver-litmus-status`) instead of treating every nonzero as a failed review when the visible output says PASS and the trusted marker exists.
- PR-grind helper output is necessary but not a substitute for manual inspection of reviewer comments when an advisory reviewer reports quota/rate-limit/incomplete-review state. If CodeRabbit or another advisory reviewer says a real review could not start, treat that as incomplete for non-trivial changes. For docs-only follow-up slices, report the situation explicitly and avoid claiming the bot reviewed the PR.

## Verification pattern for this slice class

```text
py_compile finalization-readiness + finalization-contract-status
→ focused readiness/contract tests
→ full contract tests
→ smoke
→ finalization-readiness sample: guardrail statuses == contract statuses == policy_blocked, IDs match, no authority true
→ commit litmus
→ PR-mode Codex lead + read-only backstop + trusted writers
→ latest-head PR-grind
→ merge only after clean, then post-merge CI + clean synced main
```
