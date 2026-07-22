# Delivery Mode hook-preserving mutation lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use when adding or reviewing Hermes Delivery Mode `commit`, `push`, or PR finalization code that must remain Busdriver-equivalent while invoking normal Git/GitHub side effects.

## Lessons from finalization hardening

- **Do not bypass Busdriver hook surfaces.** `git commit-tree`/`git update-ref` and `git push --no-verify` can make evidence look successful while bypassing the same hooks ADRs forbid bypassing. Prefer normal `git commit` and hook-enabled `git push`, then add explicit post-condition checks.
- **Bind side effects to reviewed objects, not symbolic refs.** Before push, resolve the reviewed local commit SHA and push `<sha>:<branch>` rather than `HEAD:<branch>`; then verify the remote branch head equals that SHA and the local branch did not move.
- **Exact leases still matter.** Keeping hooks enabled does not mean dropping race protection. Use an exact `--force-with-lease=refs/heads/<branch>:<previous-head-or-empty>` when the flow has already validated the previous remote head.
- **Hook-enabled commit needs tree/parent postconditions.** After `git commit`, verify the new commit tree equals the reviewed staged tree and the new commit's parent is exactly the pre-commit HEAD. A hook can otherwise create/reset to another commit with the same tree or mutate the index/worktree.
- **Rollback/cleanup must be non-destructive and race-aware.** Never blindly `reset --hard` or restore/clean the whole repo after a hook drift. Restore only reviewed paths using literal pathspecs, preserve pre-existing allowed marker state, and fail closed rather than deleting unrelated untracked files created during the hook window.
- **Marker evidence allowlists must be exact.** Treat only known Busdriver marker filenames under the configured state dirs as marker evidence; do not allow arbitrary `.claude/` or `.opencode/` files. For absolute `BUSDRIVER_STATE_DIR`, convert only repo-contained paths to repo-relative marker dirs; repo-external absolute paths should not authorize repo porcelain entries.
- **Status baselines matter.** Record pre-operation porcelain status and compare post-operation status for push hooks. A hook can write marker files or clean-looking tracked changes while the remote head verification still passes.
- **Path parsing must be literal.** Use NUL-delimited git output (`-z`) for path lists where possible, disable rename detection when the cleanup must know both source and destination paths, and pass paths back to Git as `:(literal)<path>` pathspecs.

## Review checklist

When Busdriver review flags hook-preserving mutation code, check these seams before retrying the review loop:

1. No `--no-verify`, raw `commit-tree`, or direct branch `update-ref` in the normal success path.
2. Commit success proves tree equality, parent equality, and no unauthorized post-commit dirty state.
3. Failed commit/hook-drift recovery does not erase unrelated tracked or untracked work and reports incomplete cleanup as failure.
4. Push uses a concrete reviewed SHA as source, has an exact lease, verifies remote head, verifies local head, and verifies the whole status baseline did not change.
5. Marker dirty allowances are based on exact marker files and pre-existing status entries, not broad directories.
6. Tests cover failing hooks, hook-modified index/worktree, marker preservation, absolute repo-local state dirs, push hook dirty state, and source-SHA-bound push commands.
