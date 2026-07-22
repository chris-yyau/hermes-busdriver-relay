# Authority-Gated Finalization Review Checklist

Use this reference when reviewing a Busdriver-equivalent executor that turns review/litmus evidence into commit, push, PR creation, or merge. The core invariant is: **the exact reviewed object must be the exact object mutated, and the exact resulting side effect must be reconciled afterward.**

## Immutable-candidate sequence

For every consequential action:

1. Capture an immutable candidate identity (`HEAD` SHA, Git tree, staged diff digest, PR head OID).
2. Validate all authority evidence against that exact identity.
3. Execute the side effect with the same immutable identity, never a later read of `HEAD` or a mutable branch name.
4. Query authoritative postflight state and verify the expected result.
5. If postflight or cleanup fails, preserve the factual side-effect status but return `ok=false`/nonzero.

A Hermes-owned finalization lock does not stop normal Git clients, hooks, users, or CI from changing repository state, so it does not close repository-level TOCTOU gaps.

## Race audit by operation

### Commit

Check whether the litmus staged-diff hash is validated before a later helper captures its own tree. A concurrent index update in that gap can become the helper's new “expected tree” and be committed as if reviewed.

Safe design:

- capture expected parent and expected tree/digest together inside the commit boundary;
- compare that tree/digest to litmus evidence there;
- ensure hooks cannot change the resulting tree/parent unnoticed;
- use compare-and-swap ref updates for rollback.

Required regression test: mutate the temp repo index after the authority predicate returns but before tree capture; assert no commit and fail-closed authority.

### Push

Check for a review validation followed by a later `rev-parse HEAD`. If the later SHA is used in the refspec without equality to the reviewed SHA, a concurrent local commit can be pushed. `--force-with-lease` protects remote state, not local review binding.

Required regression test: advance local HEAD immediately after review validation; assert the new SHA is never pushed.

### PR creation

`gh pr create --head owner:branch` names a mutable remote branch. Comparing remote and reviewed heads before invocation is not enough. Query the resulting PR and require its `headRefOid` and base to match the reviewed identities.

Required regression test: change the simulated remote branch after preflight but before PR creation; assert failure or postflight rejection.

### Merge

A head-match option protects the invocation, but CLI exit status alone is not postflight proof. Query PR state, head OID, base, and merge commit. Distinguish accepted/queued requests from completed merges.

Required regression test: command returns zero while authoritative PR state is not merged; result must not say `merged`.

## Cleanup and rollback semantics

If a commit/push happened but cleanup or reconciliation fails:

- do not erase unrelated external changes;
- record that the side effect occurred or may have occurred;
- return `ok=false` and nonzero;
- surface exact recovery information;
- never return success while the emitted postflight step is `failed`.

A warning-only success for dirty post-commit state is fail-open reporting even when leaving the external changes untouched is the correct cleanup policy.

## Durable authority artifacts

Artifact selection must validate every persisted envelope, including newly added mutating-run structures and nested evidence. Validate schema/version, immutable candidate identity, operation, authority consistency, and malformed/contradictory success fields. Add negative retrieval tests; success-only serialization tests are insufficient.

## Read-only deterministic probes

During branch review, reproduce races without modifying the reviewed worktree:

1. Create a temporary Git repo.
2. Load/invoke the executor against that repo.
3. Stub only external boundaries such as lock, network, or status providers.
4. Mutate temp state at the exact seam: update index, advance HEAD, or move a simulated remote OID.
5. Keep the real candidate-selection and result-classification logic under test.
6. Report reviewed identity, mutated identity, return code, top-level `ok`, and status.

Watch for suites that repeatedly mock authority predicates to `True`: high line coverage can still miss sequencing and latest-head-binding defects.
