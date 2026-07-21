> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# End-to-end PR-grind and delivery-redaction lessons

Session lessons from Hermes Busdriver Relay dogfooding on Dependabot PR-grind and the delivery verifier redaction slice.

## Dependabot / major-version PR-grind

- A Dependabot major-version PR can be `mergeStateStatus=CLEAN` and have all required checks green while still being non-clean by PR-grind because reviewer/manual-review comments remain actionable.
- When Dependabot auto-merge/manual-review comments are used as PR-grind blockers, normalize GitHub bot author names. `gh pr view --json comments` may expose `github-actions` rather than `github-actions[bot]`; dedupe/filter logic should accept both spellings when the semantics are the same.
- For major-version action bumps, do not handwave reviewer comments away. Verify actual release notes/action metadata and workflow usage before resolving/blocking:
  - check whether repo inputs/defaults are affected;
  - check whether the workflow uses risky event contexts such as `pull_request_target` / `workflow_run`;
  - verify relevant action inputs still exist and behavior used by the repo did not change;
  - only then resolve/comment as part of an explicit PR-grind finalization path.
- `gh pr update-branch` may leave the immediate PR view at the old head/`UNKNOWN`; rerun the read-only PR-grind loop after GitHub observes the new head. Treat the new head as invalidating all previous clean state.

## Reviewer-thread handling

- Resolving reviewer threads is a GitHub mutation and belongs only inside explicit PR-grind finalization, after evidence shows the finding is addressed or not applicable.
- A reviewer status context succeeding is not enough: inspect latest-head review bodies, inline threads, and top-level comments. Conversely, stale pre-fix CodeRabbit/Cubic bodies should not block once latest-head checker semantics report no actionable comments.

## Merge and cleanup pitfalls

- `gh pr merge --squash --delete-branch` can successfully merge and delete the remote branch but still exit nonzero because it cannot delete a local branch that is checked out by a linked worktree. Do not assume merge failed from that error alone; immediately verify `gh pr view <n> --json state,mergedAt,mergeCommit`.
- After a successful squash merge from a linked worktree:
  1. `git fetch --prune origin`
  2. sync the PR base branch (`git switch <base>; git pull --ff-only origin <base>`)
  3. remove the linked worktree
  4. delete the local PR branch; `git branch -d` may refuse after squash because the branch tip is not ancestrally merged, so `git branch -D` is acceptable after verifying the PR is merged and remote branch is absent
  5. verify only the main worktree remains and base is clean/synced.

## Delivery verifier redaction slice

- H12 sensitive-payload hardening should redact both stored artifacts and returned JSON envelopes, including verifier command strings, stdout/stderr tails, delivery-status helper error tails, and persisted Hermes-owned run artifacts.
- Redaction coverage should include token prefixes (`ghp_`, `sk-`), headers (`Authorization: Bearer ...`), assignment forms (`api_key=...`, `token: ...`, `secret=...`), and CLI flag forms (`--token <value>`, `--api-key <value>`). Tests must use a plain CLI token value so the flag path is actually exercised, not accidentally covered by a token-prefix regex.
- Redaction improvements must not grant finalization authority; keep `commit_allowed`, `push_allowed`, `pr_allowed`, `merge_allowed`, `deploy_allowed`, `release_allowed`, and `publish_allowed` false.
