# Focused stacked replay and ownership closure
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this when a prior review already established the historical transition inventory and the remaining task is an independent final check of the rebuilt stack, latest delta, early CI surfaces, and closing attestation.

## Minimal complete workflow

1. **Seal the whole object closure before substantive reads.** Include the exact materialization, its Git admin/common directory, build/evidence directory, replay objects, candidate/reseal objects, refs/config/index inputs, and any transitive alternates. If a required store is discovered later, mark the generation exploratory, delete its scratch, and start a fresh complete generation.
2. **Copy object stores byte-for-byte into scratch and compare source/copy manifests.** Use a scratch bare repository plus only scratch alternates. Inspect copied `objects/info/alternates`: an absolute protected-source path silently breaks hermeticity. Omit empty pointer-only stores or rewrite alternates to verified private copies.
3. **Preflight transitive availability.** `git cat-file -e <commit>^{commit}` proves only the commit object exists. Also resolve `<commit>^{tree}` and traverse every planned tip/tree/blob through the private closure before relying on it.
4. **Use one independent verifier.** Rehash commit objects; require one exact parent, exact tree, capability subject/trailers, immediate numstat, category-derived caps, `diff --check`, changed-Python parsing, and cumulative scanner cleanliness at every tip. Compare the recomputed rows to the supplied per-tip evidence rather than trusting its aggregate boolean.
5. **Recompute the latest inventory.** Use the exact `--no-ext-diff --no-textconv --no-color --binary --unified=1` patch shape; rebuild IDs, payload hashes, path totals, patch digest, and exact-once hunk/path ownership. Deep-compare independent proposals and permit only declared runtime-path differences.
6. **Prove early CI stability by identity.** For the required workflow, portable smoke, and required-check lock, compare `(mode, kind, oid)` from the first tip through every later tip and the final exact tree. First/final equality alone can miss a temporary regression.
7. **Replay the named workflow step at all tips.** Parse the run step, require the exact selected path set, materialize each tip from private objects, run the exact cache-suppressed command, require the claimed result, scan for cache artifacts, and remove that tip immediately.
8. **Prove final documentation ownership.** Require every correction hunk and whole-path owner to be the declared final docs slice, and require those paths in that slice's immediate changed-path set.
9. **Bind the top independently.** Recompute the exact materialization's blob/tree IDs in memory, compare its full `(path, mode, oid)` map with the top commit, and verify the exact checkout HEAD when in scope.
10. **Close atomically.** From a working directory outside scratch, run one final harness that reseals all protected roots, compares semantic and temporal row manifests, validates the evidence ledger, deletes all review scratch (including itself), verifies absence, and emits the verdict to stdout. Perform no later candidate operation.

## Verdict

`PASS` requires all verifier rows, all-tip smoke, exact top binding, opening/closing equality, and scratch absence. A late-discovered object store, inherited protected alternate, missing all-tip execution, or failed close is a concrete blocker until a fresh generation succeeds.
