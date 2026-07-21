> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Litmus Status Helper — Codex PR-Review Hardening Lessons

Session context: while finishing the `hermes-busdriver-litmus-status` helper through Busdriver Delivery Mode, PR-mode Codex lead review found additional blockers after local tests/smoke were green. These lessons apply to future read-only marker/status helpers and PR-grind blocker fixes.

## Workflow lesson: delegate implementation, keep Hermes as operator/verifier

When the user explicitly says to use subagents or complains that Hermes is doing inline implementation, stop inline coding and dispatch the next blocker-fix slice to a subagent immediately. Main Hermes should then:

1. Provide the subagent with exact repo/branch/PR, loaded-skill constraints, current dirty-tree state, failing test names, reviewer findings, and allowed/prohibited side effects.
2. Allow the subagent to mutate local files only when fixing code; prohibit commit/push/PR/merge/marker writes.
3. Re-read files after the subagent returns before editing or finalizing.
4. Main Hermes performs operator verification, amend/push, Busdriver PR-mode review/backstop/marker writing, PR-grind, merge, and cleanup.

## Hardening lessons for read-only Git helpers

### 1. JSON fail-closed must include argparse paths

Stock `argparse.ArgumentParser` exits with usage text on stderr and empty stdout. For relay status helpers that promise JSON-on-stdout, invalid CLI paths (missing required args, bad integer values, etc.) must also emit a fail-closed JSON envelope with authority flags false. Use a custom `ArgumentParser.error()` or equivalent, and test both missing required args and bad typed args.

### 2. Strip or fail closed on Git environment that can change semantics or write files

A read-only helper that shells out to `git` should sanitize more than repository identity variables. Strip at least:

- identity/worktree overrides: `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_COMMON_DIR`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`
- pathspec semantics: `GIT_LITERAL_PATHSPECS`, `GIT_GLOB_PATHSPECS`, `GIT_NOGLOB_PATHSPECS`, `GIT_ICASE_PATHSPECS`
- tracing/output side effects: `GIT_TRACE`, `GIT_TRACE2`, `GIT_TRACE_PERFORMANCE`, and related `GIT_TRACE2_*` variables that can write trace files

For diff-hash helpers, sanitizing the environment is not always sufficient. If native Busdriver gate semantics use plain `git diff`, ambient variables that native Git would honor can make a sanitized helper compute a hash that does **not** match the real gate. Treat ambient `GIT_DIFF_OPTS` as unsafe and fail closed before hashing (while still removing it from the actual subprocess env after reporting the blocker). Add a regression with PR marker state present and `GIT_DIFF_OPTS=--unified=0`; expected output is valid JSON, `ok=false`, `branch_diff_hash=null`, `decision.status=blocked`, blocker mentions `GIT_DIFF_OPTS`, raw marker payloads do not leak, and all authority flags remain false.

Regression probes: run the helper with `GIT_LITERAL_PATHSPECS=1` and a nested `.gitattributes`; it must still detect/block attributes. Run with `GIT_TRACE=/tmp/sentinel` and assert the sentinel file is not created.

### 3. Do not follow state-dir symlink components, even for metadata

If `.claude` or any parent component of a supplied state-dir path is a symlink, marker reads should already be refused. Also avoid `Path.exists()` on the full path for metadata because it follows parent symlinks and probes outside the repo. Build state-dir metadata via component-by-component `lstat`/`is_symlink` and report `exists=false` once a parent symlink is detected.

### 4. Match Busdriver default PR base resolution

When `--base-ref` is omitted, match Busdriver PR-mode semantics:

1. read `refs/remotes/origin/HEAD` and strip `refs/remotes/`
2. fallback to `origin/main`
3. explicit caller-supplied base ref still overrides the default

Add a fixture where `refs/remotes/origin/HEAD` points at `origin/trunk`; the helper should report `base_ref: origin/trunk` and hash against that ref.

### 5. Commit-marker freshness needs sub-second/same-second conservatism

If a helper compares marker `mtime` against `git log -1 --format=%ct`, remember commit timestamps are second-resolution. `mtime >= head_timestamp` can falsely accept a marker written before a new HEAD commit in the same second. Prefer a strict comparison (`mtime > head_timestamp`) or a more precise gate-compatible token; add a regression where marker mtime equals HEAD timestamp and freshness is false.

### 6. Git attributes must fail closed across repo, git-dir, explicit, and default global sources

Do not only block `info/attributes` when `stat().st_size > 0`. A FIFO, device, symlink, or other non-regular file may have size 0 but can still hang or influence a later `git diff`. Treat any existing `info/attributes` path as unsafe and fail closed; use `lstat()` rather than following symlinks. Also remember Git loads more than repo `.gitattributes` and explicit `core.attributesFile`: when `core.attributesFile` is unset it may read the default global attributes file at `$XDG_CONFIG_HOME/git/attributes` or `~/.config/git/attributes`. Read-only diff-hash helpers must detect those default global attributes paths via the *same sanitized environment mapping* passed to the Git subprocesses, not by rereading ambient `os.environ`; otherwise a caller can make the helper fail closed because ambient `HOME`/`XDG_CONFIG_HOME` contains attributes even when the Git invocation would not see that environment. Fail closed on existence, including empty files, symlinks, FIFOs, or lstat errors. Add tests with temporary `HOME`/`XDG_CONFIG_HOME` so the helper blocks when Git would see default global attributes, plus a regression where `sanitized_git_env()` removes those variables and default-global detection does not read the ambient values.

### 7. Bound every Git subprocess and treat safety-probe failures as unavailable, not safe

A read-only status helper should never hang forever in `git rev-parse`, `merge-base`, `config`, `ls-files`, or raw `git diff`. Add a finite default timeout to the shared `git()` wrapper and to any explicit `subprocess.run(["git", ...])`; use a test-only env override that can only shorten the timeout. On `TimeoutExpired`, return/report a nonzero result whose stderr contains `git command timed out`, then emit a JSON fail-closed envelope with authority flags false.

Pitfall: simply adding timeouts to boolean safety helpers can still fail open. If `git config --get diff.external`, `git config --get-regexp diff.*.textconv`, `git ls-files .gitattributes`, `git rev-parse --git-dir`, or `core.attributesFile` probes time out or fail unexpectedly, do **not** interpret the nonzero exit as "not configured". Use a tri-state shape such as `(configured: bool, error: str | None)` and make `branch_diff_hash()` return `(None, "safety probe unavailable: ...")` on timeout/unavailable safety probes. Add a regression with a fake `git` that sleeps only on one safety probe while delegating other commands to real git; with PR marker state present, expected output is valid JSON, `ok=false`, `branch_diff_hash=null`, `decision.status=blocked`, blocker includes `git command timed out`, and all authority flags remain false.

### 8. Parser/freshness invariants need lightweight property-style coverage

For marker text and PR JSON artifact parsers, fixed golden examples are not enough. Add deterministic parametrized/property-style tests (no new dependency required) over arbitrary/unrecognized marker strings and malformed/random-ish JSON payloads. Invariants: raw payload strings must never appear in the helper JSON, freshness must remain false unless the exact gate-compatible PASS/diff-hash/fresh-integer-ts shape is present, malformed/non-object JSON must not crash, and authority flags must always be false. This catches accidental raw-field echoing or over-broad parser acceptance before PR-mode review finds it.

Commit-marker parsers must be especially fail-closed: do not treat arbitrary non-empty marker text as an external review pass. Accept only formats that live Busdriver gates explicitly recognize (for example `external-review-pass`, `SKIPPED-NONE*`, `BUILTIN-*`, `PASS-<ts>`, `PASS-MERGE-<ts>`, or a raw 64-hex token when confirmed by source). Unknown strings such as `FAILED` or corrupted payloads should set `recognized_format="unrecognized"`, keep `accepted_by_commit_gate=false`, and remain `stale_or_missing` even when their mtime is newer than HEAD. Add a regression for a newer corrupted marker plus positive controls for every known accepted format.

### 9. Keep status docs consistent with the actual Busdriver artifact under test

When smoke output records `package_version`, update every nearby "last verified against Busdriver" statement to the same artifact/version actually used (for example marketplace plugin `1.72.0` vs a local source checkout `1.71.5`). If both a local checkout and installed marketplace plugin exist, state which one the verification command used instead of leaving contradictory transcript text.

## Verification pattern

For each reviewer blocker:

1. Add/confirm a focused RED regression test.
2. Make the minimal GREEN change.
3. Run focused tests, full `tests/contract/test_litmus_status.py`, full `tests/contract`, smoke, `git diff --check`, and added-line static scan.
4. Amend only after main Hermes re-reads the subagent's files and verifies with real tool output.
5. After every amend/push, rerun Busdriver PR-mode Codex lead because every commit changes the diff hash and invalidates PR review markers.
6. Run a fresh independent read-only Security/Bugs backstop for the **current** diff hash after the lead PASS; do not reuse an older PASS artifact after any amend.
7. Persist the backstop only through `run-review-loop.sh --write-backstop-verdict` with a payload containing `status`, `model`, `reviewed_diff_hash`, and `issues`; then write the final PR marker only through `run-review-loop.sh --write-pr-marker`. Verify the helper reports fresh markers before push/PR-grind.

Operational pitfall: PR-mode Codex lead can exceed a foreground tool timeout even when it will eventually return. Prefer a tracked background process or subagent runner with a transcript log, then wait/poll for completion; do not treat the foreground timeout itself as a review result.
