> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Delivery Litmus PR-Mode Lessons

Use this reference when taking a Hermes Busdriver Relay delivery-status/finalization slice through commit, PR, PR-grind, and merge.

## Fail-closed litmus evidence rules

When `hermes-busdriver-delivery-status` consumes `hermes-busdriver-litmus-status` output, validate before treating it as evidence:

- `schema` must match the litmus-status schema.
- `read_only` must be exactly `true`.
- top-level `ok` must be a real boolean, not a truthy string such as `"false"`.
- nested `decision.status` must be from the recognized vocabulary (`stale_or_missing`, `blocked`, `commit_litmus_fresh`, `pr_review_fresh`, or whatever the live helper/tests define at the time). Unknown statuses must fail closed, typically `litmus_status_schema_invalid`.
- unsafe authority flags must block, including `deploy_allowed`, `release_allowed`, `publish_allowed`, and `marker_write_allowed`, not only commit/push/PR/merge/finalization.
- nonzero litmus-status subprocess exits must block even if stdout is parseable JSON.
- litmus-status subprocess timeouts must be caught and converted to a structured fail-closed status (for example `litmus_status_subprocess_failed` with returncode/timeout metadata), not allowed to bubble as a traceback/non-JSON response.
- result-file / fixture inputs must be bound to the current repo identity. A status file from another repo, branch, HEAD, or branch-diff identity must fail closed rather than being accepted as fresh evidence.
- missing/unavailable litmus-status helpers are blockers for delivery/finalization evidence paths, not warnings; proceeding without freshness evidence defeats the purpose of the integration.
- sanitized booleans should stay booleans. For fields like `decision.not_busdriver_native_claude_runtime`, do not echo untrusted non-boolean values; coerce to `True` / `False` in the summary.

Regression tests should cover delivery-status and finalization-readiness handoff, because a warning-only delivery decision can otherwise become apparently ready handoff evidence.

## Data-egress sanitization

Sanitizing by dropping unknown fields is not enough. Allowlisted string values can still carry secrets. Redact and bound all untrusted strings before emitting them in delivery/finalization JSON:

- litmus subprocess `stderr`;
- parse-error `stdout_tail`;
- allowlisted litmus summary fields such as `repo.root`, `state_dir.path`, marker `path`, `read_error`, `stat_error`, and any diagnostic string that survives marker sanitization;
- any allowlisted decision string if future schemas add one.

Redact before tail-bounding so a truncated secret cannot bypass pattern matching. Tests should inject sentinel values into both raw helper stdout/stderr and allowlisted summary fields, then assert the full emitted JSON lacks the sentinel. Also assert the decision allowlist exactly, so unknown keys are stripped even when their sentinel strings happen to be absent.

## Nested timeout budgets

When a wrapper launches delivery-status and forwards child timeout knobs, the wrapper default timeout must cover the sum of nested budgets plus margin. In this slice both wrappers needed attention:

- `hermes-busdriver-finalization-readiness` wraps delivery-status and forwards PR-grind plus litmus timeouts.
- `hermes-busdriver-deliver --pr` can also wrap delivery-status, which can spend the PR-grind timeout and then the litmus timeout.

Use an effective timeout like `max(existing_default, pr_grind_timeout + litmus_status_timeout + 30s margin)` when the user did not explicitly override the wrapper timeout. Tests should assert the exact documented margin, not merely `>= budget + smaller_margin`.

Also catch the inner litmus helper's own timeout separately. A correct outer wrapper budget is not sufficient if the child helper timeout raises and terminates delivery-status before JSON is emitted.

## PR-mode review loop discipline

After any amend that changes the diff hash:

1. Rerun local/focused/full contract tests and smoke.
2. Rerun PR-mode Codex lead.
3. Recompute the Busdriver PR diff hash using the same `printf '%s' "$(git diff base...HEAD)" | shasum -a 256` semantics expected by the trusted writer.
4. Rerun a read-only backstop against the new diff material.
5. If Busdriver marker persistence is required, route it only through a Busdriver/Claude trusted-writer runtime; otherwise stop and report a blocker. Hermes must not write Busdriver markers directly.
6. Prefer normal follow-up commits for PR feedback after those artifacts bind to the current diff hash.
7. After PR creation or every push, run PR-grind against the latest PR head; do not merge while actionable comments exist.

If a delegated backstop crashes or times out without a valid JSON object, do not treat it as PASS. Retry with another valid read-only backstop route (for example Claude Code CLI with only the prepared diff in the prompt and no write/bash tools) and record the model/tool identity accurately for the trusted-writer handoff.

## PR-grind comments to take seriously

Even when required checks pass and a review bot reports success, `hermes-busdriver-pr-grind-check` may still return `clean=false` because of actionable comments. Fix still-valid comments rather than relying on green GitHub checks. Common actionable classes from this slice:

- wrapper timeout budget gaps;
- inner subprocess timeout paths that produce tracebacks/non-JSON instead of structured fail-closed envelopes;
- stale fixture/result files not bound to current repo/HEAD/diff identity;
- missing helper/status evidence downgraded to warning;
- sanitizer allowlist values still leaking secrets;
- tests that manually assert only a subset of authority flags;
- missing `marker_write_allowed` in unsafe-authority parameterization;
- sanitization tests that check sentinel absence but not the complete decision allowlist;
- timeout tests that assert a weaker margin than the production contract.

Keep these as TDD fixes: add a focused failing regression, implement minimal production/test hardening, then run focused and full contract suites.

## Stopping condition

Do not claim the relay slice is ready to merge merely because CI and Codex lead are green. The stop condition is: latest pushed PR head, required checks green, reviewer/advisory state no longer actionable according to `hermes-busdriver-pr-grind-check`, fresh diff-hash-bound Codex lead and backstop artifacts, and no dirty local changes. If tool-call or time limits interrupt mid-fix, explicitly report the dirty files and last failing test rather than merging or implying completion.
