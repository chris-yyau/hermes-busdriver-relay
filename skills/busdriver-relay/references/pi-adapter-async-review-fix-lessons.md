# Pi adapter async-review fix lessons

Use this when a late async reviewer/subagent reports blockers against a Busdriver relay adapter proof or PR branch, especially Pi/tool-harness work.

## Workflow discipline

- Treat async subagent summaries as leads, not verified state. Immediately re-read the owning worktree/branch/status before patching; another worker may have committed, amended, or resolved conflicts since the subagent read the diff.
- If the primary checkout lacks the reviewed files, inspect `git worktree list --porcelain` and branch refs before assuming the report is stale. Pi adapter work commonly lives in a Hermes runtime worktree while the main checkout is clean.
- After any patch, re-check `git status --short --branch`, local/remote divergence, and PR head. A local amend can leave the branch `ahead/behind` relative to the PR head; before pushing, re-confirm the remote head and use `--force-with-lease` only for the same PR branch whose old head you verified.
- Watch for sibling/parallel modifications while patching. If a file changes after your last read, re-read the relevant section and run the focused tests again before amending.
- When updating `docs/CURRENT_STATUS.md`, only record commands actually run in the current branch state. If a final test count changes after new regression tests are added, update the evidence block before the final amend.
- If tool/time budget is nearly exhausted, do not start the push/merge leg. Leave a precise resume point: branch, PR number, local head, remote-head/divergence state, dirty-file list, tests already run, reviewer threads still open/pending, and the exact next verification/push/PR-grind steps.
- After amending or running verification helpers, check `git status` before declaring the verification final. Some relay helper runs legitimately block when the worktree is dirty, and a dirty tree after tests means you still need an amend/push cycle rather than PR-grind.
- `hermes-busdriver-deliver --operation verify` is useful as a final envelope only when supplied verifiers and a clean/expected repo state match the operation. If it returns `blocked` with `reason=no_verifiers` or reports dirty entries from post-review edits, treat that as a workflow-state blocker, not as failed code correctness.
- Reviewer-bot pending state remains part of delivery. If CodeRabbit/Cubic/Devin/Codex is pending or has unresolved current-head threads, do not mark PR-grind complete; either fix the actionable findings, resolve addressed threads only with evidence inside explicit PR-grind finalization, or stop with a precise pending-review state.

## Pi adapter hardening lessons

- Wrapper artifact validation must enforce the checked-in schema, including `additionalProperties=false`; a hand-written subset check is not enough. The schema-required list should include `schema`, `worker`, `status`, `ok`, `authority`, all top-level authority flags, and `files_changed`, while the nested `authority` object requires every authority flag as const-false.
- Treat a worker artifact with `status=blocked` as wrapper failure even when the Pi process exits 0. Prefer separating structural `artifact_errors` from semantic `artifact_blockers` so a valid blocked artifact remains parseable evidence while top-level `ok` is false and the wrapper exits nonzero.
- Clear stale `pi-result.json`, stdout/stderr, and event logs in the run directory before launching Pi so a missing-artifact run cannot inherit success from an earlier run.
- Convert `TimeoutExpired` and startup/git-root failures into structured blocked results with stable nonzero return codes and tails, instead of leaking exceptions or partial bytes.
- Sanitize Git environment for every Git subprocess reachable through Pi tools. Remove identity/path/diff/trace/pathspec/askpass/ssh/exec-path variables and require `git diff --no-ext-diff --no-textconv`; use `git -c core.fsmonitor=false status --porcelain=v1 --untracked-files=all` for status.
- `bd_read` must deny common secret paths, gitignored paths, protected marker/state paths, symlink escapes, and oversized reads before allocation. `bd_write_draft` should also cap content bytes before writing and record the byte count from the same precomputed value used in the audit envelope.
- `baseEnvelope()` and `authorityEnvelope()` must make fail-closed authority flags impossible to override: spread caller `extra` before the const-false authority flags, and construct nested authority from the shared `AUTHORITY_FLAGS` constant.
- `bd_bash` finalization/marker filters should inspect command/control arguments separately from pathspecs. Do not run broad finalization regexes over file paths after `--`, or legitimate read-only diffs under directories named `deploy`, `release`, `checkout`, etc. will be falsely blocked.
- Glob-to-regex write scopes must implement both `**/` (zero or more directories) and `?` (exactly one non-slash character); do not let `?` fall through as a regex quantifier.
- Fixture files introduced for Pi contracts must be consumed by tests or removed; reviewer bots will correctly flag orphan fixtures as maintenance surface.
- Regression tests should cover blocked artifacts, schema extra properties, stale artifact clearing, timeout/startup envelopes, sanitized Git hardening strings, relative repo path normalization, pathspec false-positive avoidance, glob `?` semantics, fixture consumption, and fake-Pi/optional-real-Pi behavior.

## Verification pattern

Run, at minimum:

```bash
python3 -m pytest tests/contract/test_pi_adapter.py tests/contract/test_skill_references.py -q
python3 -m pytest tests/contract -q
git diff --check && git diff --cached --check
python3 -m py_compile scripts/pi/run-pi-busdriver-draft scripts/hermes-busdriver-agent-draft scripts/hermes-busdriver-agent-smoke
python3 scripts/hermes-busdriver-smoke --plugin-root "$BUSDRIVER_PLUGIN_ROOT" --repo . --pretty
```

Then run a targeted static scan of staged and unstaged diffs for obvious secrets, shell execution, unsafe deserialization, private-path leakage, and authority-positive flags. Do not claim a real Pi smoke unless it actually ran; fake-Pi contracts are sufficient for default CI, while real Pi smoke is opt-in because it may consume runtime/provider quota. After any reviewer-fix amend, rerun at least the focused contracts, whole contract suite, smoke, status/dirty check, force-push with lease, and latest-head PR-grind loop; earlier green CI/reviewer state belongs to the previous head.
