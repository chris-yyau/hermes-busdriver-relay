# Finalization authority hardening: immutable candidates and trusted worker boundaries

Use this reference when a relay can commit, push, create/merge PRs, consume review markers, or launch mutating draft workers.

## 1. Bind review to an immutable commit candidate

A staged-diff hash checked before `git commit` is insufficient: another Git process can change the index after validation.

For commit authority:

1. Snapshot the expected parent HEAD and index tree OID before validating review evidence.
2. Compute the reviewed diff hash from immutable objects (`parent SHA -> tree OID`), not from a later dynamic `--cached` read.
3. Pass both expected values into the commit executor.
4. Inside the executor, re-read HEAD and `git write-tree`; fail before commit if either differs.
5. Keep hooks enabled. After hooks, verify committed parent/tree/message against the expected values; roll back the ref/index/worktree on mismatch.
6. Treat any post-commit tracked or untracked drift as non-success even if a commit object/ref was created. Report the completed side effect separately from `ok=false`.

Required negative tests include index drift after review, parent drift after review, hook-modified index, hook-rewritten message, failed-hook cleanup, deleted-path restoration, and post-commit dirty state.

## 2. Push exactly the reviewed SHA

Never validate review evidence and then dynamically re-read HEAD as the push source.

1. Snapshot the reviewed HEAD before the review/base/hash check.
2. Make the review validator accept and compare that exact SHA; compute branch diff evidence from immutable refs.
3. Re-read local HEAD immediately before the push side effect and block if it changed.
4. Push an explicit `<reviewed-sha>:refs/heads/<branch>` refspec with an exact remote lease.
5. Verify the remote branch equals the reviewed SHA and the local HEAD remains unchanged after push.
6. Preserve a non-success status for post-push dirty or marker drift.

Required negative test: mutate local HEAD after review validation but before `run_safe(git push ...)`; prove the push function was never called.

## 3. Reconcile GitHub side effects

CLI exit 0 is not sufficient, and timeout/nonzero may still hide a completed remote operation.

- PR create: snapshot expected remote head/base, recheck immediately before creation, then query GitHub and verify PR number/state/head SHA/base. On timeout or nonzero, query before classifying the outcome.
- Merge: bind to the latest PR head, then postflight `gh pr view` to require `state=MERGED`, matching head/base, and a merge timestamp/commit. Reconcile on timeout or nonzero.
- Scope every GitHub command to the expected repository slug; do not rely on ambient `GH_REPO` or current-directory inference.

## 4. PATH shims are not a security boundary

A guard that inspects only `git $1` or `gh $1 $2` is bypassable with option-prefixed forms such as `git -C`, `git -c`, `git --git-dir`, `gh -R`, or absolute executable paths. Postflight cannot undo remote effects.

Production mutating workers must therefore use one of:

- a constrained tool harness with built-ins/extensions disabled and exact argv allowlists (for example Pi with only `bd_*` tools);
- an OS/process sandbox with filesystem, network, and credential isolation;
- a trusted command broker that exposes only scoped draft mutations.

Generic OpenCode/Codex/custom shell lanes remain non-dispatchable until the adapter/plugin proves this boundary. A successful model smoke or authority-false JSON artifact proves schema compatibility only, not absence of side effects.

## 5. Marker evidence needs writer provenance

Hash, content, and mtime validation of repo-local PASS/skip markers does not prove who wrote them.

At minimum, draft preflight/postflight must fingerprint all authority markers, reject symlinks/non-regular files, and block added/changed/removed markers. Finalization authority additionally needs a Busdriver-owned writer seam or an operator-issued/signed attestation bound to repo root, operation, HEAD/tree/diff, base, review session, and freshness. Hermes must not raw-write or forge Busdriver markers.

## 6. Validate nested delivery artifacts

Artifact lookup must validate nested mutating envelopes, not just the outer default-deny decision. Check schema/version/run identity, operation, status/reason, repo/PR identity, lock acquire/release shapes, side-effect list, and authority consistency. When `allowed=false`, every authority flag must be false; when true, only the operation-specific flag plus finalization may be true.

## Delivery rule

A review with any medium/high authority, TOCTOU, credential, marker-provenance, or remote-reconciliation finding is NOT PASS. Fix it, add the reproducing negative contract, rerun full contracts, and obtain fresh review on the final head before push/PR/merge.
