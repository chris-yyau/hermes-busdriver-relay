# Delivery executor split-litmus and marker semantics lessons

Use when a gated delivery-executor / finalization slice grows large enough that Busdriver litmus rejects the full staged diff or when litmus PASS marker semantics look inconsistent with Hermes-side hash checks.

## Split large delivery-executor candidates safely

- If `run-review-loop.sh` rejects the full staged candidate as too large, split by logical authority surface instead of raising ceilings blindly.
  - Prefer groups such as: executor script; tests; small helper/docs/ADR files.
  - Stage one group at a time, run litmus, then commit that group only after the group-specific evidence is valid.
- When isolating a staged group, use `git stash push --keep-index --include-untracked -- <paths...>` only as an isolation tool; immediately verify:
  - `git status --short --branch`
  - `git stash list --stat -1`
  - `git stash show --name-status stash@{0}`
- Treat pathspec warnings during stash as suspicious even if the working tree looks isolated; confirm untracked docs/ADRs are actually in the stash before proceeding.

## Litmus PASS is not automatically commit authority

- After a split-group litmus PASS, compare the current staged diff hash with any marker/hash evidence before invoking Delivery Mode commit.
- If `.claude/litmus-passed.local` content differs from Hermes' `staged_diff_hash()`, do not commit yet. Determine whether:
  - Busdriver commit marker semantics are timestamp-only / external-review format; or
  - Hermes litmus-status / commit gate should parse the marker as diff-bound evidence.
- Do not use targeted pytest or a PASS-looking marker filename as final authority when marker metadata cannot be tied to the exact staged group.

## Review-hardening patterns that should remain in executor code

- Revalidate backstop verdicts after running the Codex lead and before invoking Busdriver trusted writers; the candidate may drift during the lead review.
- Marker dirty allowlists must be exact and evidence-only. Allow only untracked (`??`) or unstaged-modified (` M`) known marker files; staged, deleted, renamed, or copied marker entries must block clean-candidate gates.
- Parse porcelain rename/copy records as multiple paths (`old -> new`) before allowlisting; never treat the whole arrow string as a single safe marker path.
- Git diff/hash helpers must fail closed on nonzero exit, timeout, or OSError even if stdout contains bytes. Never hash stdout from a failed `git diff` and compare it to evidence.
- Commit gates should distinguish “no staged changes” from “git/index status failed” with a separate blocker such as `staged_diff_status_failed`.
- Preserve unset/default PR-base semantics: no `--base` should let Busdriver resolve `origin/HEAD`; explicit bases should normalize to the same origin-qualified ref used by delivery-status/litmus-status and writer validation.
