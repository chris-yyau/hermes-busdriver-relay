> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Relay Completion Sweep Lessons

Use when the user says to continue/finish the relay and complete all remaining safe slices after a recent merge.

## What happened

- After PR57, live Phase 0 showed clean `main`, no open PRs/locks, but `docs/CURRENT_STATUS.md` still contained stale PR49 verification evidence.
- A docs-only refresh became PR58. It updated `docs/CURRENT_STATUS.md` to the latest merged-main evidence without changing finalization policy.
- Post-merge audit then found installed-skill drift from a read-only review reference (`current-status-readonly-review-lessons.md`) that existed in the installed Hermes skill but not in the repo skill source. That became PR59.
- PR58 and PR59 both required full Delivery Mode discipline: gated draft/postflight, local verification, litmus/pre-PR, independent backstop verdict with `reviewed_diff_hash`, trusted Busdriver marker writers, PR creation, latest-head PR-grind, merge, branch cleanup, and final verification.

## Durable workflow

1. **Do a final Phase-0 sweep after every merged slice.** Check all of:
   - `git status --short --branch`
   - open PRs
   - relay locks
   - litmus/PR marker freshness
   - repo skill source vs installed Hermes skill byte-for-byte compare
   - stale docs evidence in `docs/CURRENT_STATUS.md`
2. **If docs/status evidence is stale, use a docs-only slice.** Keep it scoped to `docs/CURRENT_STATUS.md`; update PR/head/test/lock/marker/skill-sync evidence only, and preserve deferred/fail-closed finalization policy wording.
3. **After docs/status slices, re-check skill drift.** Read-only review work can still create a durable installed-skill reference that must be synced back into the repo source. Treat that as another small skill-reference sync slice instead of leaving drift behind.
4. **Malformed draft verifiers are recoverable only by re-running corrected postflight.** If the tracked diff is scoped but `agent-draft` postflight fails due shell quoting, run `hermes-busdriver-gate postflight` with the saved `baseline.json`, exact `--scope-include`, and a corrected verifier script. Proceed only if corrected postflight passes.
5. **PR-grind `BLOCKED` during early CI/reviewer startup is not permission to merge or to give up.** Inspect live PR checks/comments. If blockers are pending checks/reviewers or transient `mergeStateStatus=BLOCKED/UNSTABLE`, wait and rerun the latest-head PR-grind loop. Merge only after the latest PR head is clean.
6. **End with a completion audit, not just a merge.** Verify no open PRs, no locks, no topic branches, no fresh markers, skill source aligned with installed skill, stale docs evidence gone, full contract/smoke passing, and clean `main...origin/main`.

## Verification pattern

```text
Phase 0 sweep
→ choose smallest stale surface (docs/status, then skill-source drift if present)
→ gated draft with narrow scope
→ corrected postflight if verifier quoting was the only blocker
→ focused verifier + static added-line authority/path/token scan
→ full contract + py_compile + smoke
→ deliver verify
→ commit litmus
→ PR-mode Codex lead
→ independent read-only backstop
→ trusted --write-backstop-verdict + --write-pr-marker
→ push / PR create / post-PR marker cleanup
→ latest-head PR-grind loop; retry after pending checks/reviewers settle
→ finalization-readiness with raw PR-grind loop payload
→ verify PR head unchanged, merge
→ fetch/prune + topic branch checks + open PR/lock/marker/skill/docs audit
```

## Pitfalls

- Do not stop after a docs/status PR if the post-merge skill compare reports installed-only references.
- Do not treat `docs/CURRENT_STATUS.md` verification refreshes as authority changes. They are evidence updates only.
- Do not write verifier commands with brittle nested shell quoting inside `agent-draft`; use a small Python verifier file or corrected postflight when quoting becomes ambiguous.
- Do not keep retrying after a clean PR-grind result; if the latest-head loop returns clean, proceed to readiness/merge checks.
