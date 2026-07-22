# Delivery Mode review splitting and hardening lessons

Session-derived lessons for Hermes-driven Busdriver Relay finalization work.

## When Busdriver litmus/review says the diff is too large

- Do not force one giant commit through commit-mode litmus just because local tests pass.
- Busdriver `run-review-loop.sh` enforces both weighted-line and total-line ceilings in commit mode. `LITMUS_MAX_WEIGHTED_LINES` can raise the weighted threshold, but the total raw-line ceiling can still block; prefer splitting by logical commit.
- Use `git reset` + selective `git add` and preserve the remainder in a named stash or external patch artifact. Do not raw-drop the remainder stash later; re-apply it deliberately and verify it matches the intended remaining slice.
- After each split, rerun focused tests for the staged slice, then the Busdriver review loop until PASS before committing that slice.

## Review-loop blockers to proactively check in Delivery Mode code

- Any user-supplied verdict/evidence file must be read as a bounded, repo-local, regular file:
  - resolve relative paths under the target repo;
  - reject paths outside the repo;
  - reject symlinks and non-regular files;
  - enforce `BACKSTOP_VERDICT_MAX_BYTES` before/after reading;
  - decode explicitly as UTF-8;
  - return fail-closed structured reasons, not raw file contents.
- For PR creation, bind the base used by `gh pr create` to the reviewed/litmus-observed base when `--base` is omitted. Do not recompute a different default after review; use the same helper that validates review-base matching.
- Keep finalization authority fail-closed even for structured blockers (`commit_message_required`, `backstop_verdict_file_*`, `pr_review_base_mismatch`): emit artifacts for traceability but do not grant commit/push/PR/merge authority.

## Verification pattern

- Full contract tests can be affected by global Git signing config. For Hermes-run tests that create temporary commits, use a scoped env override such as:
  `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=commit.gpgsign GIT_CONFIG_VALUE_0=false python3 -m pytest ...`
- Still verify the actual Delivery Mode code with `py_compile`, focused tests, full contract tests, and Busdriver smoke/review; do not treat the signing override as a substitute for Busdriver litmus/review evidence.
