# Finalization large-diff split and review retry lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

When hardening Busdriver/Hermes Delivery Mode or other finalization paths, the review gate may reject an otherwise coherent staged diff because the raw changed-line ceiling is separate from the weighted-line override.

## Durable lessons

- Bind every litmus/review run to the exact current staged diff hash before trusting PASS evidence.
- `LITMUS_MAX_WEIGHTED_LINES` raises the weighted-line threshold, but it does **not** bypass the hard raw total changed-line ceiling (commonly `>2000`). If the review exits `2` / `TOO_LARGE` for raw total lines, split the staged diff into logical commits rather than repeatedly raising the weighted override.
- A practical split for script+test hardening is:
  1. unstage all,
  2. stage implementation file(s),
  3. run litmus review to PASS and commit,
  4. stage regression tests,
  5. run litmus review to PASS and commit,
  6. rerun the full contract suite on the resulting branch.
- If the review CLI fails transiently (for example `agy` exits non-zero with a `/dev/stdin` clarification instead of reviewing), retry once against the same staged hash. If retry passes, stop; do not keep looping or encode the transient failure as a durable tool limitation.
- After split commits, verify `git status --short` is clean and rerun the full relevant contract suite because the final branch state is now the composition of both reviewed commits.
- On macOS, backup archives created with BSD `tar` can silently add AppleDouble `._*` members. Build source/untracked backups with `COPYFILE_DISABLE=1`, list and validate the exact archive member set, reject symlinks/special files/path traversal, hash the archive, and rehearse restore/commit in an isolated clone before relying on the split plan.

## Regression patterns worth preserving

For Delivery Mode cleanup hardening, useful regression classes include:

- large unrelated pre-existing untracked files are allowed and not content-hashed;
- failed-commit rollback for reviewed deletions does not use combined `git restore --staged --worktree` on paths absent from the target tree;
- reviewed path cleanup batches pathspecs to avoid `ARG_MAX` failures;
- marker drift is classified before generic untracked-file identity checks;
- porcelain rename parsing handles both quoted destinations containing ` -> ` and unquoted sources containing ` -> `.
