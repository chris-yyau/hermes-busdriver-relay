# PR-grind Delivery Mode Lessons — 2026-06-28

Context: End-to-end Hermes Delivery Mode run for `hermes-busdriver-relay` PR #14 and #15. PR #14 was clean and merged; PR #15 implemented marker freshness reporting, hit reviewer feedback, was fixed, re-grinded, merged, and cleaned up.

## Durable lessons

### 1. If a PR becomes `BEHIND`, update the branch and restart PR-grind

A read-only PR-grind loop may return `blocked` with `mergeStateStatus=BEHIND` even when checks are otherwise clean. In explicit Delivery Mode, use GitHub's branch update path, then treat the resulting head as a new head:

```bash
gh pr update-branch <PR_NUMBER>
git fetch origin <branch>
git merge --ff-only origin/<branch>
```

After this, restart the latest-head wait/check/review loop. Do not reuse earlier clean state.

### 2. Fix pushes invalidate all reviewer/check state

After fixing actionable bot comments, push and rerun the whole PR-grind loop against the new head. In this session the first loop after PR #15 branch update returned `needs_fix`; after the strict timestamp fix and test update, a second loop waited for pending checks and then returned `clean` for the new head.

### 3. Busdriver PR diff hashes intentionally strip command-substitution trailing newlines

`run-review-loop.sh` / pre-PR gate compute the PR diff hash as:

```bash
diff=$(git diff "${merge_base}...HEAD")
printf '%s' "$diff" | sha256sum
```

This strips trailing newlines because of shell command substitution. Do not compare it against a direct pipeline hash (`git diff ... | sha256sum`) when validating PR artifacts; the hashes can differ. Reproduce the gate hash with the same `diff=$(...) ; printf '%s' "$diff"` pattern.

### 4. Hermes Delivery Mode must emulate PostToolUse cleanup when outside Claude runtime

When Hermes directly performs `git commit` or `gh pr create` as an explicit operator finalizer, Claude Code PostToolUse hooks do not automatically consume Busdriver markers/artifacts. After successful commands, invoke the corresponding Busdriver post hook with synthetic hook JSON so state is not left stale:

- `hooks/gate-scripts/post-commit-consume-marker.sh` after successful `git commit`
- `hooks/gate-scripts/post-pr-consume-marker.sh` after successful `gh pr create`

Keep this narrow and only after the command actually succeeded.

### 5. Marker freshness reporting should be advisory and strict

For status probes that compare marker mtimes to repo HEAD commit time, use a strict comparison (`marker_mtime > repo_head_commit_time`) rather than `>=`. Equal integer-second timestamps are ambiguous and should not be reported as definitely after HEAD.

Tests should cover a committed repo and both sides of the boolean, not only an unborn repo where `head_commit_time` is `None`.

### 6. Post-merge housekeeping sequence that worked

After successful squash merge:

```bash
git fetch origin --prune
git switch main
git pull --ff-only origin main
git worktree remove <agent-worktree>   # if one exists
git worktree prune
git branch -D <feature-branch>         # if still local; tolerate already absent
git ls-remote --heads origin <feature-branch>  # expect empty
```

Then watch workflows on the merge SHA until required main workflows complete, and finish on clean `main...origin/main` with only the main worktree.
