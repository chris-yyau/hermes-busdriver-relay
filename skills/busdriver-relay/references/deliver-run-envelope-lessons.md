> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Deliver Run Envelope Lessons

Date: 2026-06-28

`hermes-busdriver-deliver` is the seam that should eventually become the durable delivery state machine, but this phase remains verify-only and fail-closed.

## Contract

Every delivery result should carry a nested `hermes-busdriver-delivery-run/v0` envelope with:

- `run_id` (caller-supplied via `--run-id` or generated);
- `phase` (`plan`, `verify`, `status`, `execute`, or `delivery_status`);
- `status` / `reason` copied from the delivery decision;
- repo root and PR number identity;
- authority flags that remain false for finalization, commit, push, PR, merge, deploy, release, publish, and marker writes;
- Hermes-owned artifact references.

## Pitfalls

- Do not put run artifacts in the target repo or `.claude/`; use `~/.hermes/busdriver-relay/delivery-runs` or `HERMES_BUSDRIVER_DELIVERY_RUNS_DIR`.
- `--run-id` is an audit/handoff identifier, not authority. It may influence artifact filename tokens only after path-token sanitization; filenames still include timestamp/PID uniqueness and are not stable paths.
- If artifact publication fails after verifiers pass, the run status must be downgraded to `blocked` / `artifact_write_failed`, and artifact references must be cleared so consumers do not chase phantom paths.
- Keep `run.authority` in sync with the final decision. Until a later approved finalization slice, all authority flags stay false.
- Persisted artifacts should contain the same run envelope as stdout, including the artifact self-reference path, so main Hermes/subagents/cron/CLI can read back one canonical result.
- `--mode status --run-id <id>` is a read-only lookup path for that handoff: it should not call delivery-status, run verifiers, write a fresh artifact, or mutate the repo. It should return the latest valid matching Hermes-owned artifact path plus sanitized metadata (`artifact_run`, artifact decision, schema, ok flag), preserve that artifact's repo/PR identity in the status envelope, and keep all authority flags false. Do not echo persisted verifier command/output tails in status lookup stdout; callers that need the full artifact can separately read the Hermes-owned path.
- Status lookup must validate versioned top-level deliver and nested delivery-run envelopes with fail-closed decision/authority metadata before treating an artifact as found; ignore spoofed/malformed/undecodable JSON even when `run.run_id` happens to match. For v1 artifacts written before the `marker_write_allowed` flag existed, treat that missing flag as false while still requiring every older authority flag to be explicitly false.
- Status lookup output should derive repo/PR identity from the validated nested `run` metadata, not from unvalidated top-level persisted `repo` / `pr` fields.
- In PR-grind delivery, stale-but-unresolved review threads can keep the checker in `needs_fix` even after code has fixed the issue. Only resolve a thread after live evidence shows the current head satisfies the finding; resolving review threads is a GitHub mutation and belongs inside explicit PR-grind finalization, never as a bypass.
- Do not narrow status lookup to successful verifier artifacts only. A later failed artifact for the same `run_id` (for example `run.phase=delivery_status`, `status=blocked`, `reason=delivery_status_failed`) is still the latest durable run state and must be eligible for lookup; otherwise status mode can incorrectly report an older success.
- Status lookup output must sanitize nested artifact metadata, not merely validate it. Rebuild artifact references as minimal `{kind, path}` entries before returning `status_lookup.artifact_run.artifacts`, so extra persisted fields such as verifier tails or diagnostic blobs are never echoed in the lookup envelope.
- Keep `marker_write_allowed=false` in the same blocked-authority set as commit/push/PR/merge/deploy/release/publish, and assert it on success and fail-closed paths. Reviewer bots treat marker-write authority as part of the read-only contract, not an optional extra.
