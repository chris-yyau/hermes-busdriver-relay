> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR67 Skill-Sync Review Fix Lessons

Use when continuing a relay skill-source sync PR after reviewer feedback lands post-PR creation, especially when the PR branch has already been pushed and checks/reviewer bots are running.

## What happened

- A skill-source sync slice copied an installed `busdriver-relay` PR66 reference back into the repo skill source and added a durability test.
- Local verification passed and PR67 was opened, but latest-head PR-grind found an actionable reviewer comment: the copied lesson wording could imply that `hermes-busdriver-litmus-status` subprocess nonzero exits may be downgraded to warning-only success when the helper emits valid JSON.
- The fix clarified that valid helper JSON is diagnostic evidence only; delivery/finalization wrappers must remain fail-closed on nonzero helper exits.
- A local amend after PR creation rewrote the already-pushed PR commit and created a divergent local branch. The safe recovery was to save the reviewer-fix patch, create a follow-up local branch from `origin/<pr-branch>`, apply the patch as a normal follow-up commit, and push that commit to the PR branch.

## Durable workflow updates

1. **For copied installed-skill references, fix installed and repo copies together.** If reviewer feedback changes the reference wording, patch both the repo source and installed Hermes skill so post-merge `diff -qr` remains clean.
2. **Do not weaken fail-closed helper semantics in lessons.** If a helper such as `hermes-busdriver-litmus-status` emits valid JSON but exits nonzero, wrappers may parse the JSON to explain the blocker, but they must still treat the subprocess failure as blocking unless the wrapper contract explicitly says otherwise.
3. **After PR creation, prefer follow-up commits over amend.** If the PR branch is already pushed and reviewer/check state exists, make a normal follow-up commit. If an accidental local amend already happened, recover without force-push: save the amend-vs-remote patch, branch from `origin/<pr-branch>`, apply the patch, commit, and push `HEAD:<pr-branch>`.
4. **Restart all latest-head evidence after a follow-up push.** Re-run committed-scope verifier, focused/full contract, py_compile, smoke, deliver verify, PR-mode Codex lead, independent backstop, trusted marker writing, then latest-head PR-grind. Do not reuse pre-fix PR-mode markers or backstop artifacts after the head changes.
5. **Carry the live PR base branch through cleanup lessons.** Reviewer feedback can apply to durable workflow text, not only code. If a reference says to return to `main` or audit `main...origin/main`, patch it to record the PR base from live PR status and audit the saved base branch against its upstream. Add negative durability assertions so the hard-coded base wording cannot regress.
6. **Clean up dead agent-draft locks after timeout evidence.** If `hermes-busdriver-agent-draft` times out without changes, inspect the lock payload and owner PID. When the owner PID is gone and the repo diff is empty, release the stale Hermes lock with the recorded token before continuing; do not leave an unexplained active lock blocking delivery.
7. **If tool/turn limits interrupt mid-delivery, hand off exact resume state.** Include PR number, pushed head SHA, local branch, whether PR-mode lead/backstop/marker are fresh for that head, and the next required command class. Do not claim the PR is delivered until merge, cleanup, and final audit actually complete.

## Verification pattern

```text
PR-grind reports actionable feedback
→ patch repo + installed skill copies when syncing skill refs
→ focused durability test
→ if reviewer flags hard-coded base-branch cleanup text, replace it with saved-PR-base wording and add negative assertions
→ if an agent-draft timeout leaves a lock, verify owner PID is gone and diff is empty, then release the lock with its token
→ if PR already exists: normal follow-up commit (or recover accidental amend via patch from remote PR head)
→ push to the existing PR branch
→ wait for new-head checks/reviewer bots
→ rerun committed-scope verifier + full contract + smoke + deliver verify
→ rerun PR-mode Codex lead and independent backstop for the new diff hash
→ trusted --write-backstop-verdict + --write-pr-marker for the new head
→ latest-head PR-grind until clean
→ readiness, merge, branch/worktree cleanup, final audit
```

## Pitfalls

- Do not force-push an amended PR branch just to clean local history after reviewer feedback; it invalidates reviewer/check state and is unnecessary for a small fix.
- Do not let a lesson say “parse JSON and only block if unavailable/malformed” for a helper whose wrapper contract intentionally treats nonzero subprocess exits as fail-closed.
- Do not hard-code `main` or `main...origin/main` in reusable cleanup/final-audit guidance; use the live PR base branch and its upstream.
- Do not leave a stale Hermes agent-draft lock after a timeout when the owner process is gone and no repo changes were made; release it with the recorded token before rerunning gates.
- Do not preserve or report raw marker contents, tokens, or credential material in handoff summaries; use hashes/statuses only.
