# Hook-preserving Delivery Mode mutation hardening
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this when implementing or reviewing Busdriver Delivery Mode helpers that perform `commit`, `push`, PR creation, or merge operations. These are class-level pitfalls learned from hardening `hermes-busdriver-deliver` after review flagged hook bypasses and cleanup data-loss risks.

## Commit helpers

- Do not replace `git commit` with `commit-tree`/manual `update-ref` for normal commits. That bypasses commit hooks and weakens runtime authority. Prefer `git -c commit.gpgsign=false commit --cleanup=verbatim -m <message>` and then verify the result.
- Bind the operation to the reviewed index before mutation:
  - `expected_tree = git write-tree`
  - `reviewed_paths = git diff --cached --name-only -z --no-renames <before> --`
  - parse NUL-delimited output; do not parse newline-delimited path lists for cleanup-critical paths.
- After commit, verify all of:
  - `HEAD` advanced from `before`
  - `HEAD^{tree}` equals `expected_tree`
  - `git rev-list --parents -n 1 HEAD` is exactly `<after> <before>`
  - commit message equals the requested message using unredacted/full `git_output`, not a redacted/tail-only helper
- If hook drift created an unwanted commit, rollback must be compare-and-swap style: `git update-ref <branch_ref> <before> <after>`. Do not plain reset a branch to an old SHA without proving current ref is the hook-created SHA.
- For reviewed deletion paths, `git restore --source <tree> -- path` can fail when the target tree lacks the path. Verify final index/worktree against `expected_tree`; do not equate restore command success with cleanup success.
- It is safe to `git clean` hook-created untracked files only when the path is in `reviewed_paths` and was not a pre-existing untracked replacement. Never clean arbitrary untracked paths as part of commit cleanup.
- Pre-existing untracked files require content/fingerprint baselining, not path-only baselining. If a staged deletion has a pre-existing untracked replacement at the same reviewed path, fail closed before committing or preserve it and fail; do not clean it after commit.
- Pre-existing unstaged changes on reviewed paths should fail closed before committing. Otherwise post-commit cleanup can overwrite user worktree edits that existed before the helper started.
- Non-reviewed tracked dirty drift after hooks should fail closed and be left for the operator; do not restore it to `before` or `after` unless it is proven to be part of the reviewed mutation.

## Marker evidence snapshots

- Allowed marker files (`.claude/*`, `.opencode/*`, configured state dir) should be compared by content fingerprint, not just `git status --porcelain` text. Porcelain text can stay ` M path` while content changes.
- Do not follow symlinks when fingerprinting marker evidence. Use `lstat` and treat symlink/non-regular/oversized/unreadable markers as invalid marker evidence, not as trusted harmless dirty state.
- Marker snapshots must detect deletion as well as modification. A marker present in the pre-snapshot but absent later is drift.
- For repo-local absolute `BUSDRIVER_STATE_DIR`, normalize relative to repo root; ignore absolute state dirs outside the repo instead of converting them to bogus relative paths.

## Push helpers

- Do not use `git push --no-verify`; preserve pre-push hooks.
- Resolve and push the exact reviewed local SHA, not symbolic `HEAD`: `git push ... <push_head>:<branch>`.
- Pre-push status snapshot is a gate, not just a baseline. If non-marker dirty entries appear between an earlier clean-worktree check and this snapshot, fail before pushing.
- Post-push verification must check:
  - remote branch head equals `push_head`
  - local `HEAD` still equals `push_head`
  - full status/marker snapshot did not drift
- If `git push` returns nonzero, recheck the remote for both newly-created and existing branches. A connection drop can leave the remote updated even though the client failed. If remote is verified at `push_head` and local state did not drift, report a verified pushed result; if remote is unchanged, keep `git_push_failed`.

## Porcelain/path parsing

- Prefer NUL-delimited Git output (`-z`) for path lists used in cleanup.
- For porcelain-v1 status, decode C-quoted paths and UTF-8 octal escapes correctly. Rename/copy entries can contain literal ` -> ` inside quoted filenames; do not split blindly on the first separator.
- Add example and property-style tests for quoted paths, spaces, backslashes, tabs/newlines, UTF-8 octal escapes, and rename/copy paths with separators in old and new names.

## Review-loop tactics

- If Busdriver reports `TOO_LARGE` and suggests an explicit `LITMUS_MAX_WEIGHTED_LINES=<n>` override, it is acceptable to rerun the same staged hash with that suggested ceiling. Keep the hash binding unchanged.
- Repeated review findings are signal: encode each accepted finding as a regression test before rerunning the review loop.
