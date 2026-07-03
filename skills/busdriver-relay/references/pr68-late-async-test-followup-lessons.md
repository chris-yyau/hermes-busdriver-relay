# PR68 Late Async Test Follow-up Lessons

Use when a background read-only reviewer/subagent result arrives after the PR it reviewed has already been fixed or merged.

## What happened

- Two read-only subagents reviewing PR67 returned after Hermes had already fixed the latest-head reviewer blocker, merged PR67, synced `main`, and completed the final audit.
- One subagent reported the already-handled latest-head blocker from the old PR67 head (`833b7f3`): the PR66 reference hard-coded `main` / `main...origin/main` in post-merge cleanup guidance. This had already been fixed in follow-up head `360f330` and merged.
- The other subagent had a small non-blocking suggestion that still applied after merge: tighten the PR66 temp-path redaction assertion from a narrow private-temp example to the broader private-temp path sentinel.
- Hermes treated that as a tiny test-only follow-up, opened PR68, verified it through focused/full contract tests, compileall, deliver verify, smoke, and latest-head PR-grind, then squash-merged and cleaned up.

## Durable workflow updates

1. **Classify late async results against current merged state.** Do not blindly act on a subagent's stale PR/head assessment. First compare the reported head/comment to the current PR/merge state and decide whether each item is already handled, still applicable, or obsolete.
2. **Convert cheap test-only non-blocking suggestions into tiny follow-up PRs.** If the previous PR is already merged and a late suggestion is low-risk, directly strengthens the just-merged contract, and requires only a scoped test change, it is appropriate to create a small follow-up PR instead of ignoring it.
3. **Keep follow-up scope minimal.** For late async suggestions, prefer one-file test/doc hardening changes. Avoid broad refactors or revisiting implementation unless the late result contains an unresolved correctness/security blocker.
4. **Run the normal delivery loop even for tiny follow-ups.** Focused test, full contract suite, py_compile, smoke, deliver verify, PR creation, latest-head PR-grind, merge, base sync, branch cleanup, lock audit, and clean final status still apply.
5. **Remote branch deletion can already be done by GitHub merge.** If `gh pr merge --delete-branch` already removed the remote branch, a later `git push origin --delete <branch>` may fail with `remote ref does not exist`. Treat that as a cleanup-state check, not a delivery failure: run `git fetch --prune`, then verify no local/remote topic refs remain.

## Verification pattern

```text
late async reviewer/subagent result arrives
→ inspect current PR/merge/head state
→ mark stale already-handled findings obsolete
→ if a small still-applicable suggestion remains, create a tiny follow-up branch
→ make the minimal test/doc change
→ focused test + full contract + py_compile + deliver verify + smoke
→ push + PR
→ latest-head PR-grind until clean
→ merge
→ fetch --prune and verify local/remote topic refs are gone
→ final clean synced base + no open PRs + no relay locks
```

## Pitfalls

- Do not reopen/rework a merged PR because a late subagent summary references an older head; compare SHAs first.
- Do not silently discard a cheap, high-signal test hardening suggestion just because it arrived late.
- Do not treat `remote ref does not exist` during branch deletion as a blocker when the PR merge path already deleted the remote branch; verify by pruning and listing refs.
