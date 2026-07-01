# PR #30–#32 relay completion-loop lessons

Use when continuing `hermes-busdriver-relay` after a clean/merged slice, especially when adding read-only finalization evidence, running latest-head PR-grind, or proving no safe non-mutating work remains.

## Continue after merge, but stop at policy boundaries

- After a relay slice merges cleanly, refresh Phase 0 and choose the next smallest safe non-mutating slice instead of asking for a task.
- When remaining items are only mutating finalization surfaces (`commit/push/PR/merge` executor/envelope, mutating PR-grind fix loop, Busdriver marker interop), do **not** implement them as “completion” unless stronger gate/runtime authority exists and the user explicitly approves that risk.
- A good final safe slice is docs/status refresh + completion audit: state that the non-mutating relay surface is complete and the residual items are intentionally blocked by design.

## PR body and shell quoting

- Do not pass Markdown containing backticks directly inside a double-quoted `gh pr create --body "..."`; the shell can command-substitute identifiers such as ``programmatic_execution_allowed``.
- Prefer writing `/tmp/pr-body.md` with `write_file`, then use `gh pr create --body-file /tmp/pr-body.md` or `gh pr edit --body-file /tmp/pr-body.md`.

## Latest-head PR-grind discipline

- Every amend/force-push invalidates the previous clean state. Rerun latest-head PR-grind after each push.
- If PR-grind reports current-head actionable review threads, verify the code/test evidence first. If the finding is addressed and the thread remains active/non-outdated, resolving the thread is an allowed PR-grind finalization mutation; then rerun PR-grind and require `actionable_comment_count: 0`.
- Required checks passing is not enough; wait for reviewer-bot state and collect review threads/comments against the current PR head.

## Read-only evidence summaries

- Adding advisory evidence (finalization guardrails, dual-review readiness, pre-PR dual-review evidence) must not remove the corresponding `finalization_guardrails.remaining_work` entry. The evidence improves handoff status; it does not implement programmatic review or finalization.
- If docs show fields as smoke output, update the smoke summary to actually emit those fields, or clearly label the snippet as manually curated from another helper.

## Sanitized litmus evidence hardening

- When deriving freshness from `delivery_status.litmus_status.summary`, validate the raw litmus helper payload **before** sanitization and expose a sanitized `authority_safe` boolean.
- Authority validation must scan the raw payload recursively for unsafe booleans, not only `decision`: `finalization_allowed`, `commit_allowed`, `push_allowed`, `pr_allowed`, `merge_allowed`, `deploy_allowed`, `release_allowed`, `publish_allowed`, `marker_write_allowed`, plus dispatch/programmatic flags if present.
- Implement recursive scans iteratively with an explicit stack and depth/node caps. Deep/malformed nesting should return unsafe (`False`), not raise `RecursionError`.
- Regression tests must include top-level, nested dict, and nested list authority-positive payloads. Nested-recursion tests should not also set a top-level unsafe flag, or the test can pass without proving nested traversal.

## Verification pattern

- Run focused tests for the changed helper/tests, then full `tests/contract`.
- Run `hermes-busdriver-smoke --plugin-root ~/.claude/plugins/marketplaces/busdriver --pretty`.
- Run `hermes-busdriver-deliver --mode execute --operation verify --verifier 'contracts=uvx --from pytest pytest tests/contract -q'` for a Delivery Mode run artifact before PR creation/amend.
- After merge: fetch/prune, ensure local branch is `main`, HEAD equals `origin/main`, remote feature branch is gone, worktree clean, full contract suite and smoke pass, and no open PR remains.
