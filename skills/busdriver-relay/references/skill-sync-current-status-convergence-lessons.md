# Skill-Sync / CURRENT_STATUS Convergence Lessons

Use when a relay continuation alternates between installed-skill drift fixes and `docs/CURRENT_STATUS.md` evidence refreshes.

## Pattern

A final audit can legitimately reveal a loop:

1. skill-source sync PR merges and makes `docs/CURRENT_STATUS.md` stale;
2. CURRENT_STATUS refresh PR merges and may reveal installed-skill reference drift created by the workflow itself;
3. another tiny skill-sync PR may be needed;
4. a final CURRENT_STATUS refresh may be needed after that.

Do not stop at the first clean PR if either of these surfaces is still stale:

- repo source vs installed Hermes skill comparison is not clean;
- CURRENT_STATUS still points at an older merged PR/head or stale verification evidence.

## Rules

- Treat repo-vs-installed skill drift and CURRENT_STATUS freshness as separate convergence conditions. Both must be clean before claiming the continuation is complete.
- Run a whole-skill installed-vs-repo comparison, not only the file targeted by the current slice.
- If useful installed-only lesson drift is class-level and sanitized, sync it to repo with durability assertions rather than deleting it to force alignment.
- If a docs/status refresh is dirty, do not interpret `hermes-busdriver-smoke` dirty-tree preflight failure as a docs regression. Run docs freshness checks, `git diff --check`, focused/full tests, compileall, and deliver-verify first; commit, then run smoke on the clean branch.
- After every merged skill-sync PR, re-check whether CURRENT_STATUS needs another evidence-only refresh.
- After every merged CURRENT_STATUS PR, re-check whole-skill installed-vs-repo drift before finalizing.
- If final-audit skill maintenance creates a new installed-only class-level reference while closing reviewer feedback, treat that as another tiny skill-sync slice before the docs refresh. Do not delete the useful installed reference just to force alignment; sync it to repo with durability assertions, then refresh CURRENT_STATUS against the latest merged head.
- For a user-explicit safe continuation slice that says to leave the working tree dirty for main Hermes, stop at a verified draft: add/update the durable contract assertion first, watch the focused test fail against the stale repo source, sync only the scoped reference drift, rerun focused tests and `git diff --check`, compare the synced repo reference against the installed skill copy, and report the exact dirty files. Do not commit, push, open a PR, merge, or touch `docs/CURRENT_STATUS.md` unless the user explicitly changes scope.
- Keep each convergence step tiny and explicit: one skill-sync PR or one docs-only evidence refresh PR, then PR-grind, merge, cleanup, and final audit.
- Make `docs/CURRENT_STATUS.md` the last convergence slice whenever possible, because it records the latest merged PR/head and verification evidence; any skill-sync PR merged after it will make it stale again.
- Run `git fetch --prune` during merge cleanup before the completion audit so stale remote-tracking topic branches are observable as state, not hidden inside a checklist item.

## Completion audit

End only when all are true:

- base branch equals its upstream and `base...origin/base` diff is empty;
- worktree is clean;
- no open PRs, relay topic branches, or stale remote-tracking topic branches remain;
- relay lock count is zero;
- installed Hermes skill and repo skill source have no missing/extra/different references;
- CURRENT_STATUS required fresh tokens are present and stale tokens are absent;
- focused skill-reference tests, full contract tests, compileall, and smoke pass on the final clean branch;
- claude-mem is updated when configured/approved.
