# Exact stacked PR delivery with one CAS fast-forward
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this when a reviewed stack is already a linear descendant of the live base and every immutable PR head has exact-tree CI/review authority. Prefer one native fast-forward over synthesizing per-PR merge commits or repeatedly restacking.

## Preconditions

1. Bind the live base ref to the sealed base SHA.
2. Prove the candidate is a true fast-forward: `merge-base --is-ancestor BASE TOP`.
3. Prove the ordered range exactly matches the expected stack: unique PRs/refs/commits, first parent = `BASE`, each next parent = prior commit, final commit = `TOP`, and `rev-list --reverse BASE..TOP` equals the plan.
4. Rehash every commit/tree and require the final tree to match exact-tree full-suite/review/CI authority.
5. Confirm each open PR still has its expected immutable head/base and no unresolved actionable review state.

`--force-with-lease` is only a ref CAS; it can still permit a non-fast-forward. Never use it as the ancestry proof.

## Minimal delivery path

1. Push `TOP:main` once with `--force-with-lease=main:BASE`. The update is a normal fast-forward, preserves the exact commit chain, and the lease rejects unknown base drift.
2. Do not mutate PR metadata before the push outcome is known.
3. For timeout/transport ambiguity, terminate and reap the whole process group, then require a bounded *continuous* observation window on `TOP`. One transient `TOP` read is insufficient.
4. Once `main == TOP` is stable, retarget any still-open stacked PRs to `main`. GitHub marks a PR merged when its exact head becomes reachable from the base; branch-deletion fallback may retarget descendants automatically.
5. Re-read before every PR mutation. Immediately before PATCH, bind both live `main == TOP` and `head == exact_head`; after success or response loss, re-read and accept only the intended state. Remove unnecessary Ready-for-review mutations.
6. Support resume when opening `main` is already exactly `TOP`; run the same continuous-stability gate before PR reconciliation.

## Isolation and failure semantics

- Use trusted fixed executables, isolated Python, stdlib HTTPS against a fixed GitHub host, disabled proxies, and process-only credentials.
- Resolve the token from the auth provider's current configured source, verify owner/mode when reading a credential file, and prove it with an authenticated read before mutation; do not assume a raw generic-keychain payload is the active token.
- Run Git from a scratch bare repo with empty HOME/XDG config, `GIT_CONFIG_NOSYSTEM=1`, disabled hooks/credential helpers/proxies, a fixed remote URL, and `--no-verify`.
- A transport error is `UNKNOWN` until stable observation resolves it. Never roll back or issue a second mutation while the first may still complete.
- Metadata reconciliation is monotonic after source delivery: exact head/base only; unexpected merged base or head drift fails closed.
- Persist progress atomically, but write `PASS` only after scratch cleanup, a final live refresh, exact main/top/tree identity, and the exact unique PR set all merged into the intended base.

## Small required probes

- Optimized or non-isolated Python exits before any API call.
- Malicious global hook/URL rewrite cannot execute or redirect the Git push.
- Timeout cleanup removes descendants and reaps the leader on macOS.
- Inject head drift between the first PR read and the mutation-boundary read; PATCH count must stay zero.
- Inject applied-but-response-lost; reconciliation accepts only the exact intended live state.

## Post-merge closeout

1. Re-read live `main`; require exact `TOP`, exact tree, and the sealed commit count/ancestry before any housekeeping.
2. Derive required contexts from live branch protection. Require the newest `push` run/check provenance for the exact main SHA to be `completed/success`. Keep non-required workflow failures in a separate disclosed ledger; never call them green or let them replace required evidence. Do not move `main` beyond the sealed tree merely to clean up an advisory failure unless that follow-up is explicitly authorized.
3. Reconcile every expected stack PR and evidence PR against exact head, base `main`, closed state, and merge time. The list-pulls API may omit or null the individual `merged` boolean: use non-null `merged_at` plus closed state and exact head/base, or fetch each PR individually.
4. When repository auto-delete is enabled, first prove every expected stack/evidence ref is absent. Skip deletion when already absent; otherwise delete only with exact expected-head leases so unknown branch drift survives.
5. Prune remote-tracking refs, then fast-forward a clean local `main` with `--ff-only`; verify local HEAD/tree and clean status.
6. Seal SUCCESS only after exact main identity, required CI, all PRs, expected branch absence, no unexpected open PRs, local sync, and scratch cleanup are all live-verified. Digest-link the merge progress, prior closing authority, and post-merge snapshot; disclose advisory failures without weakening the success predicate.
