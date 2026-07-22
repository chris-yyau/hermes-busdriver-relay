# Delivery Mode finalization pitfalls

Use this when finalizing `hermes-busdriver-relay` or similar Busdriver-gated delivery work.

## Review evidence and hash binding

- Bind Busdriver review to the exact current staged diff hash before every mutating Delivery Mode step.
- Use the same canonical hash as the review loop: full `git diff --cached --no-ext-diff --no-textconv --no-color` bytes. Do not trim trailing newlines unless the Busdriver marker writer also does.
- If a commit gate reports `commit_litmus_staged_diff_mismatch`, compare the marker value with the exact staged hash command and inspect any helper function that normalizes diff bytes.

## Busdriver review line ceilings

- Check both raw and weighted diff size before launching review. Busdriver can reject or stall near the configured threshold even when tests pass.
- If a slice is near the ceiling, split by responsibility or compress tests before review; do not try to force unrelated changes through one reviewed hash.
- A staged candidate should stay comfortably under the active `LITMUS_MAX_WEIGHTED_LINES` override. If Busdriver itself suggests a safe override, bind the same staged hash and rerun the same review.

## Stashes and overlapping finalization slices

- Treat old stashes from split/rebase/finalization work as historical candidates, not as authoritative work to `pop` wholesale.
- First compare `stash@{n}` against `HEAD` by file and content. Many stashes can be older versions of code that has since been hardened; applying them wholesale can silently revert reviewed fixes.
- Prefer selective checkout of remaining files from a stash, avoiding files already committed in the hardened slice.
- When a stash contains untracked files, `git checkout stash@{n} -- path` may fail because those files live in the stash's third parent. Inspect parents (`git cat-file -p stash@{n}`) and recover untracked paths with `git checkout 'stash@{n}^3' -- path`. Do this only for specific intended files, then stage/verify them like any other slice.
- If a combined stash remainder exceeds Busdriver review file limits, split by logical responsibility (for example docs/status vs skill/reference) rather than raising limits blindly. After splitting with `git reset` + selective `git add`, stash the remainder with `--keep-index`, but verify the new stash actually contains any untracked support files before dropping it.
- After each slice commit, re-evaluate remaining stashes against the new `HEAD`; drop only after confirming the content is absorbed or intentionally superseded.

## Skill/docs status sync during finalization

- When pulling documentation or skill-source remainders from an old stash, check for newly referenced skill support files before review. A stale `SKILL.md` can introduce dead `references/*.md` links even when tests only cover a subset. Either recover the missing reference files from the stash (including untracked files from `stash^3`) or remove the stale links in the same slice.
- Keep documented helper commands aligned with actual argparse choices. For example, do not document `hermes-busdriver-agent-smoke --agent opencode` unless the smoke script really accepts `opencode`; describe OpenCode as scaffold/contract-only until a real smoke entrypoint exists.
- For Delivery Mode docs, do not invent future operation names such as `pr-grind-fix-loop`. If the dispatcher only exposes explicit operations, say autonomous fix loops are still absent and must route through gated draft adapters plus fresh review evidence.

## Delivery Mode side-effect safety

See also `references/hook-preserving-delivery-mutations.md` for detailed commit/push helper hardening patterns: preserve Git hooks, bind mutation to the reviewed index/HEAD, verify tree/parent/message/remote, and avoid cleanup that can overwrite user data.

- Mutating helpers must preserve completed side-effect status even when postflight artifact writing or lock release fails. Do not rewrite a successful commit/push/PR/merge into a generic `blocked` result.
- Delivery commit helpers must preserve real Git hook execution. Avoid `commit-tree`/manual ref updates for normal commit creation; use `git commit` with post-commit verification of tree, parent, message, and cleanup state.
- Delivery push helpers must preserve pre-push hooks. Avoid `--no-verify`, push the exact reviewed SHA rather than symbolic `HEAD`, and verify both local and remote heads after the push, including nonzero push exits.
- Push refspecs from raw SHAs must use a fully-qualified destination (`<sha>:refs/heads/<branch>`). A bare `<sha>:<branch>` can fail first-push/new-branch cases because Git cannot infer the destination namespace from an unqualified SHA source.
- Cleanup after hook drift must be fail-closed and path-scoped: restore/clean only paths proven to be in the reviewed staged diff. Never silently restore non-reviewed tracked dirty drift or delete arbitrary/pre-existing untracked files.
- Before cleaning reviewed untracked drift, block if the same path was already an untracked file at commit start. A staged deletion plus pre-existing untracked replacement at the same path is user data, not hook-created drift.
- If a commit/push side effect has completed and HEAD/remote verification proves it, preserve the completed status (`committed`/`pushed`) and surface later dirty-state problems as an explicit reason/warning (for example `post_commit_external_dirty_drift`, `post_commit_status_failed`, `local_head_post_push_mismatch`, `pushed_with_post_push_dirty_worktree`, or `post_push_local_drift_after_failed_push`), not as a generic `blocked` mutation. The top-level `ok`/return code may still be false when reconciliation failed; completed status records the side effect, not a green postflight. In Delivery Mode commit wrappers, determine `status=committed` from HEAD advancement (`after != before`) even when `commit_staged_index().ok` is false because a post-commit verification failed. Do not reuse completed-warning reasons for blocked mutations; if failed-push local postflight drift occurs but remote recheck does not prove `push_head`, use a distinct blocked reason (for example `post_push_local_drift_after_failed_push_unverified`) so `steps_for()` cannot mark an unpushed operation as passed.
- Never convert a nonzero `git push` into `ok=True` merely because a remote recheck observes `push_head`. That can bypass a failing pre-push hook when the remote was already at the SHA or another actor moved it there. If the remote is verified at `push_head`, report `status=pushed` but keep `ok=False`/nonzero rc unless the original push command itself succeeded and postflight is clean.
- If post-commit or post-push `git status` itself fails, fail closed; unverifiable local state is not a warning. For failed-push recovery, remote completion (`recheck_head == push_head`) should still be represented as `status=pushed` even when the local post-failure check is dirty/unavailable, with postflight marked failed.
- Ensure top-level decisions and `steps_for()` agree with completed-side-effect warning reasons such as `pushed_after_failed_push_remote_verified` and `post_push_local_drift_after_failed_push`; otherwise APIs can say success while steps say blocked, or hide a completed side effect behind `blocked`.
- Marker/evidence fingerprints must be TOCTOU-safe: after `lstat`, open with `O_NOFOLLOW` when available, `fstat` the opened fd, and verify regular file + `(st_dev, st_ino)`/size still match before hashing. Do not rely on `Path.open()` after a symlink/non-regular check. Treat sentinel fingerprints like `<missing>`, `<read-error>`, `<stat-error>`, `<too-large:...>`, `<symlink>:...`, and `<non-regular:...>` as invalid marker evidence.
- Do not content-hash arbitrary unrelated pre-existing untracked files while protecting user data. For non-marker untracked snapshots, prefer a lightweight identity (mode/dev/ino/size/timestamps or equivalent no-read metadata token) so large unrelated untracked files do not permanently block commit finalization. Still fail closed for reviewed deletion replacement at the same path.
- Marker dirty detection must not let known marker paths fall through to generic untracked handling. If a marker path is present but invalid/mutated, classify it as drift/dirty immediately; metadata-only identity checks can miss content changes with preserved size/timestamps.
- Path-scoped cleanup for reviewed paths must be ARG_MAX-safe. Avoid expanding huge `*literal_pathspecs(paths)` lists into a single subprocess call for `git diff`, `restore`, `rm`, `clean`, `ls-tree`, or `status`; batch reviewed pathspecs or use Git `--pathspec-from-file`/`--pathspec-file-nul` where the subcommand supports it.
- Porcelain rename parsing needs tests for both quoted and unquoted path edge cases. A naive first split fixes quoted destinations containing ` -> ` but breaks unquoted sources containing ` -> `; a naive last split does the reverse. Prefer a parser that understands quoted segments and delimiter position.
- Include release-failed variants (for example `committed_release_failed`) in side-effect-preserving artifact-failure paths.
- `git status --porcelain` output must preserve leading XY columns; helper stdout trimming should use trailing-newline trimming, not `.strip()`.
- Staged marker blocking must cover known marker dirs (`.claude`, `.opencode`, configured state dir) and marker rename sources. Disable rename detection for the marker scan so a marker renamed out of the state dir cannot evade the block.
- Remote preflight lookups should preserve normal credential environment (for example `SSH_AUTH_SOCK`) while still forcing hardened Git config (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`).
