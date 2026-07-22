> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Deliver Verify PR-Grind Follow-up Lessons

Session context: while grinding `hermes-busdriver-deliver` verify-only delivery envelope feedback on PR #7, multiple reviewer rounds surfaced small but durable envelope-hardening lessons. Apply these to future changes in delivery/verification helpers, not just this PR.

## Verifier execution envelope pitfalls

- Catch verifier launch `OSError` subclasses (`FileNotFoundError`, `PermissionError`) around `subprocess.run(..., shell=False, ...)` and report them as structured verifier failures instead of allowing a traceback to escape. Keep stdout empty, stderr bounded, and decision fail-closed.
- `shell=False` removes shell metacharacter injection but does **not** mean verifier argv is safe for untrusted input. CLI help/docs should state that verifier commands are trusted local execution inputs. Do not add a speculative allowlist unless the design explicitly calls for it.
- For timeout error fields that prepend text before a bounded stderr tail, subtract the prefix length from the tail budget. Otherwise `"timeout after Ns\n" + tail(stderr)` can exceed the cap.
- Make the generic `tail(value, limit)` helper define `limit <= 0` as `""`; Python `text[-0:]` returns the whole string.
- If verifier parsing fails after a user-supplied label prefix (`label=` with an empty or malformed command), preserve the user label in the structured error record so operators can identify which verifier failed.
- Add `argparse` choices for operation enums where possible so arbitrary operation strings do not flow into result JSON/artifacts.

## Artifact-writing discipline

- If the artifact itself should contain its own final path, set `run_artifact_path` before serializing the artifact content. But on any write failure, clear it before printing stdout so no phantom final path is published.
- Write run artifacts atomically: serialize to a temp file in the target directory, then `os.replace(temp, final)`. If writing/replacing fails, remove the temp file best-effort and fail closed.
- Test both stdout/artifact path parity on success and phantom/temp cleanup on failure.

## Draft-agent/postflight gotcha

- Running full pytest from inside `hermes-busdriver-agent-draft` can create ignored `.pytest_cache` / `__pycache__` files that make postflight fail `no_new_or_changed_ignored_files`, even when scoped source changes and focused verifiers pass. Clean caches before postflight when possible, or run broad verification outside the draft launcher before final commit/push.

## PR-grind loop reminders

- After every push, previous reviewer/check state is stale. Wait for the new head's CodeRabbit/Devin/Cubic/GitGuardian round, then re-run `scripts/hermes-busdriver-pr-grind-check` against the local repo path (`--repo /path/to/worktree`, not `owner/repo`).
- Treat each new actionable reviewer comment, even small P3/test-assertion items, as part of the latest-head loop. Fix, verify, push, wait, re-check until the latest head is clean.
