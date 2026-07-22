> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Deliver Verify Envelope Lessons

Session: continuing `hermes-busdriver-relay` after PR #6 to add the next conservative delivery slice (`hermes-busdriver-deliver --mode execute --operation verify`).

## Durable implementation lessons

When adding a verify-only execution envelope to `hermes-busdriver-deliver` or similar relay dispatchers:

1. **Keep finalization disabled even on verifier success.** `commit_allowed`, `push_allowed`, `pr_allowed`, `merge_allowed`, `deploy_allowed`, `release_allowed`, and `publish_allowed` remain `false`; status may be `verified` / `verified_local_only`, not delivery-clean.
2. **Run verifiers without shell expansion.** Avoid `shell=True`. Parse verifier commands into argv with `shlex.split()` or a stricter argv/list format. Treat verifier execution as explicit local command execution, not a shell-script surface.
3. **Verifier label parsing must be narrow.** Only treat `NAME=COMMAND` as a label when `NAME` matches a label regex at the start (e.g. `^[A-Za-z0-9_.-]+=`). Commands containing `=` elsewhere, such as test selectors, must not be split.
4. **Reject empty verifier commands.** Inputs like `empty=` or whitespace must return a structured verifier failure, not succeed via an empty shell command.
5. **Handle missing verifier binaries structurally.** Catch `FileNotFoundError` / `OSError` around `subprocess.run(argv, ...)` and return a verifier result such as `ok:false`, `returncode:127`, bounded `stderr_tail`; never crash or emit non-JSON.
6. **Bound every diagnostic path.** Invalid JSON, timeout, nonzero helper exit, verifier stdout/stderr, and OSError messages should all use the same bounded-tail helper.
7. **Artifact path consistency matters.** If writing a Hermes-owned run artifact, the artifact JSON on disk and stdout envelope should agree on `run_artifact_path`. But on write failure, do not publish a phantom path; reset/leave `run_artifact_path:null`, set `decision.reason=artifact_write_failed`, and rebuild `steps` so consumers do not see contradictory state.
8. **Add `argparse` choices for narrow operation surfaces.** If only `plan` and `verify` are supported, constrain `--operation` accordingly or document/handle unsupported operations consistently before verifier execution.

## Contract tests to keep

Useful regression tests for this class of slice:

- default plan mode is read-only and non-mutating;
- `execute --operation verify` runs a harmless verifier and writes a Hermes-owned artifact outside the target repo;
- failing verifier returns nonzero with bounded diagnostics and all finalization flags false;
- invalid delivery-status JSON and timeout paths are bounded and fail closed;
- unsupported operation does not run verifier commands;
- delivery-status failure prevents verifier execution;
- verifier command with `=` outside a leading label is not split;
- `empty=` verifier fails closed;
- artifact write failure does not publish a phantom artifact path;
- missing verifier binary returns structured JSON rather than crashing.

## PR-grind reminder

After every fix push, invalidate the previous clean state and rerun latest-head PR-grind. Reviewer bot completion (`SUCCESS`, no-issues summaries, or advisory statuses) is not enough; require no pending relevant checks and no current-head actionable comments/unresolved non-outdated review threads.
