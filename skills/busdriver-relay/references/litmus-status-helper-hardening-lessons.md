> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Litmus Status Helper Hardening Lessons

Context: building `scripts/hermes-busdriver-litmus-status`, a read-only helper that reports Busdriver commit/pre-PR marker freshness without granting finalization or writing markers.

## Durable implementation lessons

1. **Never echo marker contents.** Marker text and JSON artifact fields are repo-controlled and may contain secrets or log-injection payloads. Report fingerprints, lengths, booleans, enums, and bounded metadata instead of raw `status`, `diff_hash`, `ts`, or marker text.

2. **Read marker files with a symlink-safe file descriptor.** `lstat()` followed by `Path.read_text()` is TOCTOU-prone. Use `os.open(..., O_NOFOLLOW | O_NONBLOCK)` where available, validate `fstat()` is a regular file, enforce a small max byte limit, then read from the fd. Refuse symlink, FIFO/device, and oversized markers.

3. **Check the whole state-dir path for symlink components.** It is not enough to test only `.claude` itself. A path such as `state-link/.claude` can traverse through a symlinked parent. Resolve this before reading child markers and fail closed for unsafe components.

4. **Separate commit-marker and PR-marker freshness.** PR diff hash failures should block only when PR marker state is present. If only a commit marker is being reported, unavailable PR base/diff information can be a warning while commit freshness remains tied to HEAD/marker timestamp. Conversely, PR marker state with missing/empty base...HEAD diff must be blocked.

5. **Align PR hash semantics with Busdriver, but fail closed around diff mechanisms.** Busdriver PR gates hash shell-captured plain `git diff` output (command substitution strips trailing newlines before `printf '%s'`). Document this explicitly. If external diff/textconv/diff-driver config or attributes could affect output, fail closed instead of executing or computing a divergent hash.

6. **Treat all attribute sources as unsafe for a generic read-only helper.** Check repo/worktree `.gitattributes` including ignored files, `$GIT_DIR/info/attributes`, `--git-common-dir` for linked worktrees, and `core.attributesFile`. Any present diff selection should block PR freshness calculation unless a future trusted Busdriver API provides an exact safe hash.

7. **Sanitize Git identity environment for all git calls.** Remove `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_COMMON_DIR`, object-directory overrides, `GIT_EXTERNAL_DIFF`, and `GIT_DIFF_OPTS` where appropriate so `git -C <repo>` cannot be redirected to a different repo/index or execute external diff logic.

8. **Validate HEAD explicitly.** `git rev-parse --show-toplevel` can succeed in an empty repo. Also require `git rev-parse HEAD` to succeed and return a non-empty value; otherwise emit a blocked status with no authority.

## Review workflow lesson

For relay helpers near Busdriver gate semantics, expect multiple rounds of litmus/backstop findings. Keep each finding in TDD form: add a regression test that fails, make the smallest fix, rerun helper tests, full contract tests, smoke, Busdriver litmus, and only then re-dispatch read-only backstop. Do not commit/push until both Busdriver litmus and independent backstop pass on the current staged diff hash.
