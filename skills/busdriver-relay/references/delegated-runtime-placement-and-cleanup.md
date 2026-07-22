# Delegated Runtime Placement and Cleanup

Use this checklist whenever Busdriver/Hermes delegates an exact-boundary review, reconstruction, probe, or isolated test run.

## Placement contract

"Outside the source repo" is not a complete path policy. Every delegation must supply absolute paths for:

- output/lane root
- reconstructed candidate
- helper scripts and probe fixtures
- isolated `HOME`, `TMPDIR`, and XDG/cache roots
- pytest `--basetemp`
- raw logs, reports, and SHA sidecars

All generated paths must be descendants of `/Volumes/Work/.hermes-runtime/` or another explicit user-approved runtime root. Never default to `$HOME`, the session cwd, or an unqualified `tempfile`/`mktemp` root.

## Interruption-safe lifecycle

1. Register generated roots before dispatch.
2. Preserve the exact candidate and evidence while their review is current.
3. On BLOCKED, provider refusal, timeout, or tool-call interruption, distinguish current evidence from abandoned reconstruction/probe residue.
4. Remove abandoned generated artifacts promptly; never remove repositories, worktrees, sessions, auth, databases, memories, plugins, or still-current evidence.
5. Verify the generated paths are absent from the home-directory top level after cleanup.

## Review prompt minimum

State both the write allowlist and the write denylist. Example policy:

- writes allowed only below the named lane root
- source repo/index/refs/remotes and installed skills are read-only
- `$HOME` and session cwd are not artifact roots
- tests use candidate-external basetemp/cache paths below the lane root
- report and sidecar paths are explicit

The orchestrator owns post-review cleanup; do not assume a leaf subagent will reach its finalizer after a blocked or interrupted run.
