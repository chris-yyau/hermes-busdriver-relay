> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR-grind watcher / finalizer guard lessons

Use this when Hermes is asked to continue as a PR-grind watcher/finalizer guard for `hermes-busdriver-relay` or another Busdriver-relay repo.

## Read-only guard pattern

- Start with Phase 0 discovery even if the prior session claimed the repo was ready: repo root, branch/HEAD, dirty tree, worktrees, Busdriver plugin/config/hooks, relay scripts, lock/finalization-lock state, markers, and current open PR list.
- Treat the watch as read-only unless the parent/user later grants explicit merge or finalization authority. Do not comment, push, enable auto-merge, resolve threads, or merge from a watcher turn.
- Use the repo's own read-only helpers when available:
  - `scripts/hermes-busdriver-delivery-status --repo <repo> --plugin-root <plugin-root> --pretty`
  - `scripts/hermes-busdriver-pr-grind-loop --repo <repo> --pr <n> --plugin-root <plugin-root> --max-wait-seconds <budget> --poll-interval <seconds> --max-polls <n> --pretty`
- If no PR exists at baseline, bounded-watch open PRs with a clear budget and stop when the budget expires. Report `blocked/no_pr` rather than inventing a PR-grind result.

## Important pitfall: concurrent repo drift during watch

A watcher may run while another worker is modifying the same worktree. After the bounded watch exits, re-run final read-only verification before reporting:

- `git status --short --branch`
- current branch and HEAD
- open PRs, especially matching the current branch
- delivery/lock summary

If the branch or dirty tree changed during the watch but no PR appeared, report that as the final blocker: draft changes exist but there is no PR to grind. Do not silently reuse the initial clean/main Phase 0 state.

Specific drift pattern seen in practice: the watch can start clean on `main` immediately after a merged PR, then another worker may switch the same worktree to a new local feature branch with a clean tree and one or more local commits, while no remote branch/open PR exists yet. Classify this as `blocked/no_pr_timeout + branch_drift` (not `clean` and not `needs_fix`), include branch/HEAD/ahead count plus `gh pr list --head <branch>` evidence, and wait for the parent/worker to push/open the PR before running PR-grind.

## Reporting shape

Use a compact status classification:

- `clean`: only after the latest PR HEAD has passed the read-only PR-grind loop with evidence.
- `needs_fix`: latest-head feedback/checks are actionable and fixing is outside watcher authority.
- `blocked`: no PR appeared, GitHub feedback surfaces failed, branch/head drifted, repo became dirty without a PR, or policy/authority is missing.

Include evidence: watch start/end UTC, poll count/budget, final open PR list, final branch/HEAD/dirty paths, lock/marker status, and the exact no-mutation policy followed.
