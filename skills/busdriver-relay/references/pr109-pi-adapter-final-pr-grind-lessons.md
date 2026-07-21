> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR109 Pi adapter final PR-grind lessons

Use this when finishing Pi adapter / constrained tool-harness PRs through the relay delivery loop.

## PR-grind loop discipline

- After every amend + force-with-lease push, treat all prior PR-grind/check/reviewer state as invalidated. Re-run latest-head PR-grind against the new head after checks and reviewer bots settle.
- If a reviewer thread was genuinely addressed by code + tests but remains active, resolve it only as part of explicit PR-grind finalization and only after recording evidence. Do not resolve to bypass unaddressed feedback.
- `hermes-busdriver-deliver --operation pr-grind` can disagree with a just-run checker if new reviewer comments arrive between calls. When this happens, inspect the deliver artifact’s nested `pr_grind.result.actionable_comments`, fix the latest comments, then restart the push/wait/grind loop.
- Smoke helpers that run preflight can fail while the worktree is intentionally dirty. Run full smoke after amend/clean state for final evidence; during dirty review-fix work, prefer focused/full contract tests plus `git diff --check` until the tree is committed.

## Pi adapter hardening lessons

- Forward `--scope-exclude` from `hermes-busdriver-agent-draft` into `scripts/pi/run-pi-busdriver-draft`, then into the TypeScript tool layer as `PI_BD_DENIED_WRITES`. Enforce excludes before any draft write (`pathDenied` / `path_excluded`) so postflight is not the first line of defense.
- Keep scope glob semantics explicit and covered by tests. The current Pi adapter contracts use segment-oriented globs (`*` → `[^/]*`, `?` → `[^/]`); do not document Python `fnmatch.fnmatchcase` slash-matching parity unless the adapter, gate, and contract tests are updated together. Enforce excludes in the adapter and re-check artifact `files_changed` against declared scope in the wrapper.
- Missing `--pi-bin` / unavailable Pi should return a structured blocked JSON envelope, not a Python traceback. Catch `OSError` around Pi launch, use a synthetic returncode such as `127`, keep authority false, and let missing artifact remain an artifact error.
- Startup failure helpers that always exit should be typed as `NoReturn` to make timeout/error control flow clear and avoid future refactors leaving unbound subprocess variables.
- Treat a valid Pi artifact with `status="blocked"` as schema-valid but wrapper-blocked. Keep schema validation errors separate from `artifact_blockers` so a legitimate blocked artifact is not conflated with malformed output.
- Keep `bd_write_draft` write-size caps symmetric with `bd_read` read-size caps; draft mutation should not be able to create arbitrarily large review/diff surfaces.
- Freeze gitignore semantics for the whole Pi run: block `.gitignore` edits in `safePath()` so Pi cannot remove an ignore rule and then read/write a formerly ignored file before postflight notices. Run `git check-ignore` with `-c core.fsmonitor=false` and strip dangerous `GIT_*` env vars for read/write checks as well as status/diff.
- Close write-time symlink races in `bd_write_draft`: re-check symlink components immediately before writing and open the final file with `O_NOFOLLOW` where available, then write through the fd. The initial `safePath()` check is not sufficient if the destination can be swapped between validation and write.
- Avoid putting the full adapter prompt in Pi argv. Write the prompt to the run directory and pass an `@prompt-file` argument plus a small instruction string, otherwise large prompts/diffs can exceed argv+env limits (`E2BIG`) before Pi starts.
- Cross-check the final artifact’s `files_changed` against the declared include/exclude scope in the wrapper as defense-in-depth. Tool-layer scope checks are necessary but not sufficient for future regressions or fake/malformed artifacts.
- Suppress project-local Pi system prompts explicitly (`--system-prompt` plus empty `--append-system-prompt`) in addition to `--no-context-files`; Pi may treat context-file suppression differently from trusted project system prompts.
- Make negative test fixtures schema-valid before asserting a specific failure reason. For example, a bad-authority fixture should include required fields such as `worker` and `ok`, so the test fails only when authority handling regresses, not on generic schema validation.
- Broaden cheap common-secret path heuristics beyond `.env` and key files (`.netrc`, `.aws/credentials`, `.ssh/*`, `.docker/config.json`, cloud SDK ADC files). This is defense-in-depth on top of scope allowlists and gitignore checks.
- Preserve exact scope strings across wrapper boundaries. The wrapper should join repeated include/exclude arguments with newlines, and the TypeScript tool layer should split only on newlines; do not split on comma or colon because Busdriver gate treats a CLI value such as `docs/a,b.txt` as one pattern.

## Review-thread cleanup and merged-state handling

- When reviewer comments are fixed in code and verified, unresolved GitHub review threads can continue to block `hermes-busdriver-pr-grind-check` even when CI and CodeRabbit are green. Use GraphQL `reviewThreads` to identify the exact `thread.id` for still-active comments, then `resolveReviewThread` only for comments whose finding is already addressed by code/tests. Resolve after evidence, never as a substitute for a fix.
- After resolving addressed threads, rerun `hermes-busdriver-pr-grind-check` and expect `actionable_comments: []`, `clean: true`, and `decision.merge_allowed: true` for the latest PR HEAD before final merge/hand-off.
- If `gh pr merge --squash --delete-branch` prints a local git/worktree error such as `fatal: 'main' is already used by worktree ...`, do not assume the GitHub merge failed. Immediately query `gh pr view <pr> --json state,mergedAt,mergeCommit`; if it is already `MERGED`, switch to post-merge cleanup from the canonical base worktree, fetch/prune, fast-forward the base, remove the helper worktree, delete the local branch, and verify the remote branch is gone.
- If `hermes-busdriver-pr-grind-loop` later reports `state=MERGED`, treat that as a terminal post-merge state, not a new fix blocker. Switch to post-merge verification from the base worktree/branch; the isolated delivery worktree may already have been removed by cleanup.

## Verification evidence pattern

For each fix push, collect at minimum:

```text
git diff --check
python3 -m py_compile scripts/pi/run-pi-busdriver-draft scripts/hermes-busdriver-agent-draft scripts/hermes-busdriver-agent-smoke tests/contract/test_pi_adapter.py
uvx --from pytest pytest tests/contract/test_skill_references.py tests/contract/test_pi_adapter.py -q -p no:cacheprovider
uvx --from pytest pytest tests/contract -q -p no:cacheprovider
scripts/hermes-busdriver-smoke --repo . --plugin-root <busdriver> --pretty   # after clean/amend
scripts/hermes-busdriver-pr-grind-check --repo . --pr <PR> --pretty           # latest head only
```
