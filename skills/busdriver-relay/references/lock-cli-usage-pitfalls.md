> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Busdriver relay lock CLI usage pitfalls

Use when acquiring/releasing/checking Hermes-owned relay locks during Delivery Mode, skill-sync, or cleanup slices.

## Durable lessons

1. **Release is branch-keyed through the live repo identity.** `hermes-busdriver-lock acquire --repo . --operation <op>` stores the current branch/worktree identity. If a squash merge or cleanup moves the worktree back to the PR base before release, `release --repo . --operation <op> --token <token>` can look for the base-branch key and return `not-found` while the topic-branch lock is still active. `gh pr merge --squash --delete-branch` itself may fetch/fast-forward or leave the worktree on the PR base before your next scripted line, so do not assume a pre-merge branch check is still true after the merge command. Re-read `hermes-busdriver-lock status`, recreate/switch to the topic branch at the saved PR head only long enough to release the lock with the saved token, then return to the PR base and delete the temporary local branch.

2. **Do not assume all lock subcommands accept the same flags.** `acquire`/`release` accept `--repo` and `--operation`; `status` may be global-only in the current helper and reject those flags. For scoped checks, run `hermes-busdriver-lock status` and filter/read the returned JSON rather than retrying unsupported flags.

3. **Acquire output stores the token at the top level and inside `lock`.** The acquire payload shape is `{"acquired": true, "token": "...", "lock": {...}}`, not a flat status envelope with `ok/status/operation/branch`. Parse `token` directly (or `lock.token`) and use `lock.repo.branch` for branch-keyed cleanup decisions.

4. **Verify lock cleanup from the actual status payload.** A `release` result with `released=false` / `reason=not-found` is not a success, even if the PR is merged and branches are deleted. Finish with `hermes-busdriver-lock status` showing `count=0` before claiming cleanup complete.

## Minimal cleanup pattern

```text
save branch + PR head + token at acquire time
→ after merge, re-read live PR state, current branch, branch deletion state, and lock status
→ attempt release while still on topic branch if possible
→ if release misses after base checkout or `gh pr merge` moved the worktree, recreate topic branch at saved PR head
→ release with saved token
→ checkout live PR base, delete local temp branch, fetch --prune
→ require lock status count=0
```
