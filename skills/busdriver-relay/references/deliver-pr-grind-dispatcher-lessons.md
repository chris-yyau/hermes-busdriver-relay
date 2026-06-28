# Deliver PR-Grind Dispatcher Lessons

When `scripts/hermes-busdriver-deliver` wraps `scripts/hermes-busdriver-pr-grind-loop` for `execute --operation pr-grind`, keep the wrapper fail-closed and non-finalizing.

## Rules

- Accept a clean PR-grind loop result only when all are true:
  - subprocess exit code is `0`;
  - payload `ok` is `true`;
  - payload `schema` is `hermes-busdriver-pr-grind-loop/v0`;
  - payload `version` is `1`;
  - payload `read_only` is `true`;
  - payload status/clean are consistent (`status=clean` iff `clean=true`);
  - nested `decision` exists and has string `status` / `reason`;
  - nested `decision` keeps `finalization_allowed`, `commit_allowed`, `push_allowed`, `pr_allowed`, `merge_allowed`, `deploy_allowed`, `release_allowed`, `publish_allowed`, `marker_write_allowed`, and `fixing_allowed` all exactly `false`.
- Do not expose any dispatcher option that can replace or fixture the PR-grind loop. The wrapper cannot preserve a read-only/live-PR guarantee after accepting caller-supplied helper output; tests should monkeypatch the wrapper seam in-process instead of adding production CLI bypasses.
- If loop output is malformed, wrong schema/version, not read-only, or carries unsafe authority flags, classify as `pr_grind_loop_failed` and return nonzero.
- If delivery-status fails before the loop can run, still write a Hermes-owned handoff artifact for `execute --operation pr-grind` when `--pr` is present so `--mode status --run-id` can report the failed handoff.
- Do not write artifacts for missing-PR scope errors; those are local invocation errors, not durable PR-grind handoffs.
- The wrapper may persist the child loop envelope under `pr_grind_loop`, but the wrapper decision/run authority must stay fail-closed regardless of child content.

## Regression tests

Keep tests for:

- clean safe loop payload writes an artifact and returns dispatcher `pr_grind_clean` with no finalization authority;
- `needs_fix` writes an artifact and returns nonzero;
- missing `--pr` returns nonzero without writing an artifact;
- clean payload with nonzero child exit fails closed;
- unsafe nested authority in a clean child payload fails closed;
- delivery-status failure before loop execution writes a handoff artifact when `--pr` is present.
