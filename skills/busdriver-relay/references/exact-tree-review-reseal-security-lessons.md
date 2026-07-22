# Exact-tree review-reseal security lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this when an independently reviewed Busdriver-relay remediation candidate must be resealed after reviewer findings.

## Reseal loop

1. Freeze the candidate with a temporary Git index that includes untracked files:
   `GIT_INDEX_FILE=<tmp> git read-tree HEAD && GIT_INDEX_FILE=<tmp> git add -A && GIT_INDEX_FILE=<tmp> git write-tree`.
2. Treat any source change, test change, manifest refresh, or docs correction as a new exact tree. Old full-suite logs and old independent reviews no longer bind.
3. Before a full suite, clear rebuildable caches (`__pycache__`, `.pytest_cache`) and run with `PYTHONDONTWRITEBYTECODE=1` plus `-p no:cacheprovider` where possible.
4. After the full suite, recompute the same temporary-index tree, run `git diff --check`, verify cache count is zero, and hash the log, exact patch, and numstat.
5. Use a Bash wrapper when relying on `PIPESTATUS`; a zsh-launched command can leave `exit=` blank even when pytest succeeded or failed.

## Review findings: reproduce before fixing

- Do not accept truncated delegation summaries as proof. Read the full finding table when available and independently reproduce high-risk claims before changing production code.
- Add a RED contract for each exploitable claim, then make it GREEN. For false-clean/fail-open review findings, assert both nonzero exit and absence of the clean marker.

## Required-checks hardening patterns

- Exported Bash functions can shadow bare commands, absolute slash commands, and even `builtin`/`command`/`unset` in an already-imported shell. Shell-local scrubbing after import is not a trust boundary.
- Prefer an executable `#!/bin/bash -p` entrypoint and test the executable path, not `bash script`, for exported-function injection. Keep scanner/tests aware that `#!/bin/bash -p` is a shell entrypoint.
- Validate remote owner/repo before resolving credential-capable `gh`; do not infer it from mutable local Git metadata.
- Credential-bearing calls should preserve only explicit GitHub token variables and scrub proxies, shell loaders, language loaders, Git config, and GH context variables.
- Bound both stdout and stderr before writing to files. Use `limit+1` capture so overflow is detectable, and fail closed on overflow.
- Branch-protection 404 with a nonempty lock is drift, not clean. Only an empty lock may be clean with absent required checks.
- Normalize branch-protection legacy contexts and app-bound checks as `(context, app_id)` tuples; an app-bound check should suppress the same legacy context rather than producing a false duplicate.

## Git observation sandbox hardening

- Allowing only a trusted `git-real` path for process exec is insufficient: Git can be tricked through repo-local filters/aliases into self-dispatching a mutating subcommand under an allowed basename.
- The macOS sandbox profile for read-only Git observation should deny `file-write*` and allow only unavoidable benign writes such as `/dev/null`.
- Regression tests should compare `.git/index` bytes before/after a production observer under a hostile clean-filter fixture with a symlink-to-`git-real` alias.

## Child-process deadline ordering

- For nested process wrappers, an outer timeout must not expire before the inner owner reaches its child-process deadline and completes process-group cleanup. Killing the broker first can orphan the Git process even when the broker's own timeout path is correct.
- Preserve short outer deadlines for operations that cannot spawn children, but give Git/process-spawning operations a distinct outer deadline greater than `inner deadline + bounded reap/cleanup`.
- Contract-test the numeric ordering against the production constants, and separately exercise the inner timeout, successful-leader, and overflow paths with descendants to prove each kills/reaps the owned process group.

## Runtime manifest and CI portability

- After changing broker/wrapper/helper/runtime bytes, refresh embedded digest constants and `config/trusted-runtime-manifest.json` to a fixed point. Expect cascades such as broker -> Pi wrapper -> agent-draft -> deliver.
- Then run `test_trusted_runtime_manifest.py`; it is the closure oracle, not a suggestion.
- If contracts depend on macOS host primitives (`sandbox-exec`, root-owned Apple paths, descriptor semantics), Ubuntu CI must not be the only required lane. Split portable CI from a required self-hosted macOS host-runtime lane, and make `check-required-checks.sh --local-only` prove the workflow/lock names match.

## Review gate

Do not proceed to restack, PR updates, or merge after a reseal until fresh independent reviews explicitly bind to the latest exact tree and the latest full-suite evidence.
