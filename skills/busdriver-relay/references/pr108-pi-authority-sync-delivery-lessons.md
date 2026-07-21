> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR108 Pi authority-sync delivery lessons

Use this note for Busdriver relay delivery slices that combine skill-source sync, target-state agent-routing docs, PR-grind reviewer fixes, and helper worktree cleanup.

## Scope and authority lessons

- If the user confirms Pi as the chosen Busdriver-compatible tool-harness direction, update both repo and installed skill sources in the same slice, but keep wording as target-state until schema, wrapper, smoke, and contract tests pass.
- Treat OpenCode wording as generic/opencode-go or future comparison lane unless a Busdriver-compatible adapter/plugin is rebuilt and verified.
- Every new reference file in the relay skill needs a same-PR durability test and a SKILL.md pointer.

## `bd_bash` hardening lessons

`bd_bash` being argv-only and no-shell is not enough for Git subcommands. Git can still execute external helpers through repo/user configuration.

Require these forms in Pi adapter guidance and tests:

```text
git -c core.fsmonitor=false status --porcelain=v1 --untracked-files=all
git diff --no-ext-diff --no-textconv
git diff --no-ext-diff --no-textconv --name-only
```

Rationale:

- `core.fsmonitor` can make `git status` execute a configured fsmonitor hook command.
- external diff drivers and textconv filters can make `git diff` execute configured commands.
- Hardening belongs in both the reference docs and durability assertions so reviewer-bot feedback cannot regress silently.

## PR-grind discipline

- A clean `gh pr checks` / mergeable PR is not enough. Run latest-head `hermes-busdriver-pr-grind-check` immediately before merge and require `clean=true`, zero actionable comments, no pending/failed relevant checks, and `decision.merge_allowed=true` for the exact PR head.
- After every reviewer-fix push, rerun PR-mode litmus/review and restart latest-head PR-grind against the new head. Do not merge based on a clean result from the prior head.
- Reviewer comments can arrive between a clean poll and merge. Re-check PR-grind immediately before mutating merge; if a new actionable comment appears, stop and fix it.

## Squash-merge and cleanup pitfalls

- `gh pr merge --squash --delete-branch` can perform the remote squash merge successfully but still exit nonzero when it cannot delete a local branch that is checked out by another worktree. If that happens, verify PR state/merge commit before treating it as a failed merge.
- After a successful squash merge, fast-forward the saved PR base branch to its upstream (for example, `origin/<base>`), then delete Hermes-created PR branches/worktrees. Local branch deletion may require `git branch -D` because squash merge does not make the feature branch an ancestor of the base branch.
- If a helper worktree performed the final PR fixes, remove that helper worktree and delete its helper branch after the base branch is synced.
- Lock release helpers may key by repo root/worktree/branch/operation. If the branch was deleted or switched before release, a normal release command can look for a different lock key. Before manual cleanup, read the lock payload and only remove it if schema, operation, note, token, and expected PR/slice identity match.

## Final audit expectations

A PR108-class delivery is complete only after verifying:

```text
saved PR base branch clean and synced with its upstream
PR merged at the expected merge commit
repo-vs-installed skill compare clean
focused contract tests pass
full contract tests pass
compileall passes
smoke passes
relay brief reports idle_clean_policy_blocked_finalization
remaining_work_count == policy_blocked_count == 5
capability_allowed_count == 0
all authority flags false
lock count == 0
Hermes-created PR branches/worktrees removed
claude-mem observation logged when configured/approved
```

If another session owns a separate Pi adapter worktree/PR, report it but do not clean or mutate it as part of the skill-sync PR cleanup.
