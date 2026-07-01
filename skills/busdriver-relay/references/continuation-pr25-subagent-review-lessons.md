# Continuation + PR-Grind Reviewer Fix Lessons (PR #25 pattern)

Use when the user says to continue relay work with subagents and the work is already inside an open PR branch.

## Lessons

- After subagents return, main Hermes must **verify self-reports against the live tree** before finalizing. Subagents can miss real blockers; re-read the diff, rerun focused/full tests, and inspect PR-grind output yourself.
- If the local branch and remote PR branch diverge, do **not** force-push over the PR head. Create a temporary worktree from `origin/<pr-head>`, apply the local hardening patch with `git format-patch` / `git am -3`, verify there, then fast-forward push that worktree head.
- Treat reviewer-bot comments as latest-head blockers even when CI checks pass. PR-grind may report `wait` with `actionable_comment_count > 0`; inspect those comments and fix them before merge.
- For delivery-status/litmus integrations, timeout budgets must compose end-to-end. If a wrapper invokes delivery-status, and delivery-status invokes PR-grind plus litmus helpers, the wrapper timeout must cover `pr_grind_timeout + litmus_status_timeout + margin`, and custom nested timeout args must be forwarded rather than only reflected in the wrapper budget.
- Sanitized evidence must sanitize **every allowlisted field**, including boolean-ish runtime identity fields. Do not echo untrusted values such as `decision.not_busdriver_native_claude_runtime`; coerce to a boolean (`is True`) or another safe representation before emitting handoff/status JSON.
- When the tool-call budget or context budget is almost exhausted, stop before risky finalization and leave a precise resume point: worktree path, PR number, head SHA, tests already run, reviewer findings, and remaining gated steps.

## Verification pattern

1. Work from a clean worktree based on the current PR head.
2. Apply only the minimal fix patch for actionable reviewer comments.
3. Run syntax checks and the full contract suite, not just focused tests, before pushing.
4. Push only if it fast-forwards the PR head.
5. Restart latest-head PR-grind after every push; previous clean/check/review state is stale.
6. Merge only after PR-grind is clean for the latest head, then do post-merge cleanup.
