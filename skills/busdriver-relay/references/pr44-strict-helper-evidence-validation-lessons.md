> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR44 Strict Helper Evidence Validation Lessons

Context: continuation after PR #43, where the remaining gap was regression coverage for helper evidence validation rather than production behavior. The slice merged as PR #44.

## Durable lessons

- If production already fails closed, the smallest safe continuation slice can be **tests-only**. Add focused regression coverage instead of touching production code.
- For delivery/finalization helper evidence, cover all malformed top-level cases explicitly:
  - invalid JSON / parse failure;
  - parsed JSON that is not an object;
  - `read_only` not exactly `true`;
  - `ok` not a strict boolean.
- Invalid helper evidence should block the outer decision/readiness envelope and keep every authority/finalization flag false. Use the existing full authority assertion helper instead of hand-asserting a partial subset, so `deploy_allowed`, `release_allowed`, and `publish_allowed` are not accidentally omitted.
- When parametrizing tests with lambdas or opaque cases, provide explicit pytest `ids=[...]`; reviewer bots may otherwise flag unreadable generated test IDs.
- Finalization-readiness should be checked through the delivery-status nested payload, not by assuming helper evidence has already been normalized. Assert both the nested reason and the outer blocked/readiness status.

## Delivery / PR-grind lessons

- After any amend/force-with-lease push, treat all prior PR-mode evidence as stale: rerun PR-mode Codex lead, rerun/read-only backstop, rewrite the trusted PR marker, wait for checks/reviewer bots again, then rerun latest-head PR-grind.
- Reviewer-bot findings that seem minor can still be actionable for the PR-grind loop when they point to stated PR objectives (e.g. “all authority flags”). Fix them before merge.
- `gh pr checks --watch` can show all checks passing while reviewer-thread/comment surfaces still need a fresh PR-grind check. Always run the project PR-grind checker/loop after the final push.
- When Hermes creates PR markers outside Claude Code hook runtime, manually run the matching Busdriver post-hook cleanup path after PR creation/merge so stale `.claude/pr-*.local*` artifacts and commit litmus markers do not remain in the repo state.

## Verification pattern for this slice class

```text
focused new tests
→ focused helper suites
→ full contract suite
→ relay smoke
→ commit-mode litmus before commit/amend
→ PR-mode Codex lead + read-only backstop + trusted marker
→ push / PR
→ wait for checks and reviewer bots
→ latest-head PR-grind; fix actionable feedback; repeat after every push
→ finalization-readiness merge handoff
→ merge
→ post-merge full contract + smoke + clean synced base
→ post-hook marker cleanup when outside Claude runtime
```
