# Deliver Run Envelope Lessons

Date: 2026-06-28

`hermes-busdriver-deliver` is the seam that should eventually become the durable delivery state machine, but this phase remains verify-only and fail-closed.

## Contract

Every delivery result should carry a nested `hermes-busdriver-delivery-run/v0` envelope with:

- `run_id` (caller-supplied via `--run-id` or generated);
- `phase` (`plan`, `verify`, `execute`, or `delivery_status`);
- `status` / `reason` copied from the delivery decision;
- repo root and PR number identity;
- authority flags that remain false for finalization, commit, push, PR, merge, deploy, release, and publish;
- Hermes-owned artifact references.

## Pitfalls

- Do not put run artifacts in the target repo or `.claude/`; use `~/.hermes/busdriver-relay/delivery-runs` or `HERMES_BUSDRIVER_DELIVERY_RUNS_DIR`.
- `--run-id` is an audit/handoff identifier, not authority. It may influence artifact filename tokens only after path-token sanitization; filenames still include timestamp/PID uniqueness and are not stable paths.
- If artifact publication fails after verifiers pass, the run status must be downgraded to `blocked` / `artifact_write_failed`, and artifact references must be cleared so consumers do not chase phantom paths.
- Keep `run.authority` in sync with the final decision. Until a later approved finalization slice, all authority flags stay false.
- Persisted artifacts should contain the same run envelope as stdout, including the artifact self-reference path, so main Hermes/subagents/cron/CLI can read back one canonical result.
