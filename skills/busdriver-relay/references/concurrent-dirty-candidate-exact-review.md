# Concurrent dirty-candidate exact review

Use this when an exact review is bound to a dirty virtual tree while another process may still reseal, reformat, commit, or refresh refs.

## Durable protocol

1. **Seal before execution.** Record canonical worktree, linked-worktree Git dir, common Git dir/object store, `HEAD`, `HEAD^{tree}`, refs, real-index hash, porcelain-v2 bytes, staged/unstaged diff hashes, and a framed opening digest. Run Git with `GIT_OPTIONAL_LOCKS=0`, disabled fsmonitor/hooks, and no ambient global config.
2. **Reconstruct without writing the protected object store.** Put the temporary index and `GIT_OBJECT_DIRECTORY` under one owner-only scratch root; use the protected object store only through `GIT_ALTERNATE_OBJECT_DIRECTORIES`. `read-tree <base>`, overlay the dirty source once, and require `write-tree == expected_virtual_tree`.
3. **Stop using the live worktree after sealing.** A read-only test can still observe mixed bytes if another process reseals during collection. Materialize the sealed tree into a scratch repository, give it a synthetic detached commit only when tests require `HEAD`/`git ls-files`, keep it remote-free, and run every semantic/source-auth test there with isolated HOME/TMP/cache roots.
4. **Separate candidate correctness from review admissibility.** The immutable scratch tree may pass while the live source, branch, refs, or common object store changes. Report the candidate-content result, but the overall binary verdict remains `BLOCKER` when the closing seal differs.
5. **Treat evidence serialization narrowly.** A supplied patch can be redacted or newline-normalized while its self-hash is valid. Generate and hash the canonical raw Git patch inside the scratch process before it crosses any tool-output or report-serialization boundary; compare added/removed lines and numstat framing, and bind source truth to the exact tree. Do not call a non-canonical report-shaped patch a replay artifact.
6. **Close atomically.** Before optional exploration consumes the remaining budget: verify the scratch view is still clean and at the expected tree, reconstruct the current live virtual tree in scratch, compare it with the sealed tree, recompute the opening payload byte-for-byte, print the close result, remove only the declared scratch root, and prove it is absent.

### Digest-only reseal invariant

For a pin refresh, preserve the base file layout and substitute only the expected digest literals. Verify that replacing every digest token with one placeholder makes base and candidate bytes identical. Avoid pretty-printers or whole-file reserialization: formatting-only churn creates new producer bytes, expands the closure DAG, and invalidates tests or reviews already bound to the earlier tree.

## Adjudication

- A live test failure caused by mid-run source drift is not a defect in the sealed candidate; rerun the same command on the immutable scratch tree.
- Do not restore or amend a drifting protected worktree during an independent review, and do not attribute the writer without evidence.
- Any new commit/ref update during the lane invalidates a PASS even when it incorporates an apparently equivalent fixed-point refresh. Re-dispatch against the new exact `(head, tree, parent, evidence)` tuple.
- Keep known prerequisite drift (for example, an unchanged optional-tool pin) in a separate ledger; prove it predates the candidate before excluding it.

## Minimal evidence rows

Record: expected tree, reconstructed tree, raw/evidence patch hashes and relation, changed-path/mode set, manifest producer-versus-cascade classification, closure-test command/count/log hash, focused source-auth positive and negative results, opening/closing seal hashes, exact drifted paths, scratch cleanup result, and whether protected repo/refs/HOME/PR were written by the reviewer.
