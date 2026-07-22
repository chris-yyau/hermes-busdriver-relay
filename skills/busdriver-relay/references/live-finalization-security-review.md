# Live finalization security review

Use this when independently reviewing Busdriver delivery/finalization code, especially while another worker may still be editing the worktree.

## Bind the review to a stable snapshot

1. Record branch, HEAD, changed files, untracked files, file kinds, and a hash of the complete cumulative base-to-worktree snapshot. Do not hash only `git diff` text: include current bytes of every tracked change plus every untracked file, sorted by path, and encode symlink/missing/special-file states explicitly.
2. Write down the canonical serialization algorithm with the expected digest before review. Reuse that exact implementation at the end; a different ad-hoc hash recipe is not comparable evidence.
3. Hash the snapshot repeatedly over a short interval. If it changes, treat all earlier line numbers, pin checks, and test results as stale.
4. Run tests only after the hash stabilizes, then hash again after the run. Pytest collects files at startup, so a passing run can describe the pre-edit snapshot even when the post-run worktree contains newly added failing tests.
5. Make the closing snapshot attestation the final repository-reading action. If it differs from the opening/expected digest, fail closed: report both hashes and inventory counts, label findings provisional/non-certified, and do not issue a security PASS.
6. Preserve a per-file opening manifest when practical. It lets the reviewer identify exactly which paths drifted instead of knowing only that the aggregate digest changed.
7. Never infer drift from mtimes alone and never silently combine evidence from different snapshots.

### Snapshot implementation pitfall

Do not hand-reconstruct a long one-line attestation command at the end of the audit. Quoting mistakes and subtly different JSON separators/prefix conventions can create a false mismatch. Prefer a checked-in/read-only verifier script or capture the exact opening command and canonical manifest for byte-for-byte reuse. A failed comparison caused by a different algorithm must be diagnosed before calling it repository drift.

## Mutation-boundary review model

For each commit, push, PR-create, and merge boundary, trace:

- immutable input identity before the command;
- immediate precondition revalidation;
- the exact command target;
- authoritative postcondition reconciliation;
- lock identity and release behavior;
- terminal status/reason consistency.

A command exit status is not an authoritative postcondition. Success can lack the requested effect, and failure/timeout can follow a completed remote mutation.

## Deterministic temporary-repository probes

Use temporary repositories and monkeypatch only the narrow command seam. Do not modify the reviewed worktree.

### Commit/index race

Inject a new staged file immediately after the reviewed `git write-tree`. Verify that a rejected commit does not commit, unstage, overwrite, or delete the concurrent file. Deriving cleanup paths from the live index after candidate capture is unsafe: rollback may classify concurrent data as reviewed and delete it.

Also move HEAD between candidate capture and the commit helper. A terminal `committed` status is valid only when the observed commit has the reviewed parent, tree, and message—not merely because `HEAD != before`.

### Push candidate ancestry

Create diverging candidate and remote histories. Verify ancestry against the immutable candidate SHA, never dynamic `HEAD`. An ABA race can make `merge-base --is-ancestor remote HEAD` pass even though the remote is not an ancestor of the SHA sent by `git push --force-with-lease`.

### Branch-keyed lock release

Acquire on one branch, switch branches, and release with the same token. If release recomputes a branch-derived key, it may report `not-found` and leave the original lock stale. Release by immutable acquisition identity/path, and ensure a branch change cannot permit a second repository finalizer.

### PR and merge reconciliation

Exercise at least:

- command success but no matching postcondition;
- command failure/timeout followed by one exact matching PR or merged PR;
- reconciliation query unavailable (outcome uncertain);
- wrong repository, PR number, head SHA, base ref, or base SHA;
- base retarget/base-SHA drift between precondition and mutation;
- duplicate, closed, or otherwise conflicting PR matches.

Bind clean PR-grind evidence to repository, PR number, head SHA, base ref, and base SHA. Schema validation must reject clean evidence missing those bindings.

## Terminal evidence consistency

Cross-check top-level decision, run metadata, mutating-run metadata, side effects, lock acquire/release, and reconciliation status. Completed-but-degraded operations may legitimately deny further authority, but impossible combinations—such as `committed` with no acquired lock and no commit side effect—must not validate.

When a failed command is authoritatively reconciled as completed, step summaries must say the operation completed and postflight reconciliation passed; they must not say the operation was blocked or postflight was skipped.

## Marker tamper coverage

Keep the gate's protected marker set mechanically aligned with the finalizer's complete authority-marker set. Negative tests should cover creation, rewrite, deletion, and symlink substitution for every marker in every supported state directory.

## Post-CAS ref ownership

After `commit-tree` and a successful `update-ref <ref> <candidate> <before>`, every postcondition must inspect the immutable candidate OID. First require the live ref to equal `<candidate>`. If another actor has advanced `<candidate>` to `X`, fail closed without moving the ref. A rollback is permitted only as `update-ref <ref> <before> <candidate>`; never use ambient `HEAD`/`X` as the expected-old value. Add a deterministic barrier immediately after the successful CAS and prove that a concurrent successor commit is never removed.

## Lock-domain and atomic-publication invariants

All worktree mutators—including draft agents and finalizers—must share one exclusive lock domain. Operation and branch are payload metadata, not lock-key material: separate operation keys allow draft/finalization overlap, while branch-derived keys orphan locks after branch switches. Release by immutable acquisition identity.

Directory creation followed by `lock.json` publication is not atomic. Another contender can observe the payload-free directory as stale, delete it, and create a replacement while the first actor still believes it acquired the lock. Likewise, token-check followed by path-based recursive deletion has an ABA window. Prefer `flock` or an `O_CREAT|O_EXCL` lock file with generation-bound compare-and-delete. Barrier tests must cover payload publication and token-check/delete replacement races.

## Postflight and child-process quiescence

Treat verifier commands as potential mutators. Run a full repository invariant snapshot after verifiers and use that final snapshot for the decision; checking scope/HEAD/hooks/markers/ignored files only before verifiers is fail-open. Test with a verifier that writes an out-of-scope file.

Agent timeout handling must terminate and reap the entire process group before postflight and lock release. A direct child timeout can leave grandchildren writing after the lock is released. Also bind success reporting to lock release: release/reconcile first, then atomically persist and print one final envelope. A release failure must override success and clear authority.

## PR-grind strict remote evidence

Require non-null, exact repository/PR/head/base bindings and remote state fields before `clean`. Conditional checks such as “if state exists, validate it” turn partial API payloads into clean evidence. Include target, head, and base repository identities plus expected head/base refs.

Paginate every REST collection, including legacy commit statuses, and reject missing per-item/head SHA. REST error objects, GraphQL `errors`, null repository/PR/connections, and malformed page shapes are unavailable evidence—not empty findings. The loop consuming checker output must validate exact schema, `ok`, PR, repository, head, base, status/clean consistency, and authority fields before emitting a clean envelope.

## No-op and unattributed-effect semantics

A no-op such as “remote already equals reviewed SHA” satisfies a postcondition but performs no new mutation; it must not mint positive mutation authority. Lock-release failure reconciliation applies even to no-op paths.

If an exact-lease push fails and a later query observes the desired SHA, another actor may have won the race. Record `postcondition_observed_unattributed` or `reconciliation_required`, not an attributable `pushed` effect, unless a server receipt proves this invocation caused the transition. Keep command outcome, attributable effect, observed postcondition, authority, lock release, and artifact persistence as separate state fields.