# Final-tree review triage and temporal slicing

Use this when a bounded-stack reviewer reports findings against individual immediate-base diffs, but the delivery decision concerns the final candidate tree.

Related foundations: `sealed-transition-slicing-and-tree-verification.md`, `stacked-ci-and-host-attestation-models.md`, and `r90-second-order-helper-and-bounded-ownership-review-lessons.md`. Those cover sealed transitions, verification planes, and ownership review; this note covers final-tree-versus-slice classification and TDD re-slicing.

## Two independent questions

For every finding, answer both:

1. **Does the alleged code path or defect exist in the exact final tree?**
2. **Was the bounded slice independently valid when materialized against its immediate base?**

Do not collapse these questions. A forward pin can make one slice deterministically broken even when the next slice makes the final tree correct; conversely, later tests do not repair a production defect whose code is unchanged.

## Classification vocabulary

Split compound findings into atomic claims, then classify each:

- `CONFIRMED_FINAL`: the vulnerable or incorrect path remains in final HEAD.
- `RESOLVED_LATER`: the defect existed in the reviewed slice and later production changes repaired it.
- `FALSE_POSITIVE`: the alleged function, call semantics, trust requirement, or failure condition is absent or materially misstated.
- `TEMPORAL_PACKAGING_ONLY`: final behavior is correct, but slice ordering, a forward reference, or tests landing later made the bounded slice invalid or unreviewable.

A single ordinal may legitimately have several classifications. Examples:

- An inner broker may have no lock deadline while its outer worker has a process-group deadline: inner gap is confirmed, “the whole run is unbounded” is false or overstated.
- An untrusted report reader may need coherent bounded reads, while `st_uid` alone does not turn untrusted bytes into authenticated evidence.
- A wrapper launch-semantics allegation can be false while the same slice’s missing behavior tests are temporal packaging debt.

## Evidence workflow

1. Freeze and record final HEAD, parents, tree, index state, tracked worktree diff, untracked paths, and ignored generated artifacts. Report tracked-patch counts and exact-working-tree counts separately: `git diff --shortstat` excludes untracked files, so a “34-file / 1750-line” patch can still be a 35-path candidate whose omitted untracked test is required for closure. Do not call the tree clean merely because ignored `.pytest_cache`, `__pycache__`, or `.pyc` files are absent from `git status`.
2. Map each ordinal to its commit and immediate base.
3. Record the last-touch commit for every implicated production file and test file. If production has not changed since the reported slice, later tests cannot be called a production fix.
4. Inspect exact final functions and line ranges. Verify named functions actually exist.
5. For subprocess claims, inspect the AST or exact call keywords; do not infer `shell=True` from a reviewer paraphrase.
6. For digest/pin claims, hash bytes from both the historical commit and final tree. Compare the embedded pin to each, not merely to the manifest.
7. Search final tests for the exact hostile condition, not adjacent happy-path coverage.
8. When allowed, run focused tests with bytecode, plugin autoload, and repository cache writes disabled, then re-check worktree and ignored-artifact state. Use the intended interpreter explicitly; a launcher resolving to a different Python without pytest is an environment result, not a repository failure.
9. Inspect `.pytest_cache/v/cache/lastfailed` only as historical diagnostic context. A cached node id that is now `not found`—especially after a test rename—is stale snapshot/test drift; locate and run the current replacement before classifying production. Never use stale cache state as final-tree evidence.
10. For background or long-running suites, collect the terminal exit status and final summary before reporting. If the result is still pending, label it an evidence gap rather than extrapolating a focused pass to the full suite.
11. Use deterministic in-memory probes for semantic gaps where possible. Example: replace an untrusted reader’s `os.read` with a short-read fake and prove it accepts fewer bytes than `st_size` without creating a race fixture.

Report exact `file:function:line`, exploit/failure preconditions, current mitigations, and whether production is policy-blocked. A dormant or policy-blocked path can still be a confirmed capability defect, but its current exploitability must be stated accurately.

## Temporal packaging and re-slicing

Prefer vertical slices: production behavior plus the test that first fails for that behavior.

Mandatory coalescing/reordering patterns:

- **Implementation in N, behavior tests in N+1:** move the tests back or coalesce N+N+1.
- **Forward pin in N to bytes introduced in N+1:** reorder producer before consumer or coalesce atomically. Never accept a deterministically unusable intermediate commit as a valid bounded capability.
- **Integration tests several unrelated slices later:** move only the relevant test hunks back; do not coalesce unrelated middle capabilities merely to reach their tests.
- **Digest closure/fixed-point contracts:** land the manifest, every consumer pin, and the closure test in one reviewed transition.

For a final-tree defect, propose a new bounded RED→GREEN slice rather than hiding it in re-slicing language.

## Security-boundary TDD patterns

### Pathname-to-descriptor races

Write deterministic tests that inject the swap precisely between lookup and open/revalidation. The fix should anchor traversal at a trusted directory fd, use no-follow/nonblocking opens, bound reads, compare pre/post `fstat`, and revalidate the directory entry through its parent fd.

Cover:

- regular → symlink/FIFO substitution;
- ancestor-directory swap, not only final-component symlinks;
- hardlink/link-count and identity drift;
- oversized inputs and short reads;
- cleanup that unlinks only the inode created by the operation.

### Authenticated bytes versus executed bytes

A private `0700` directory and `0500` file do not isolate a same-UID adversary. Re-authenticating a retained pathname and then executing that pathname still re-resolves the name.

For Python helpers, prefer a fixed root-owned interpreter with an isolated stdin loader that compiles the already-authenticated bytes; use the path only as a virtual `__file__`. Test a deterministic post-authentication pathname substitution and assert that only authenticated bytes execute.

### Lock deadlines

Advisory `flock(LOCK_EX)` is not bounded merely because cooperating holders are expected to be brief. Use nonblocking lock attempts plus a monotonic deadline and a structured timeout result. Keep any immediate caller timeout below the outer worker budget and test both layers.

### Symlink runtime closure

Hashing only a symlink target string does not bind the bytes reached at runtime. Reject absolute and parent-escaping targets, validate complete link chains remain inside the private runtime, and ensure all reached bytes/types are covered by the digest. State separately when production dispatch is currently policy-blocked.

### Ambiguous side-effect completion

A timeout, transport error, or nonzero wrapper result does not prove a mutating command had no effect. For compare-and-swap ref updates and similar operations, reconcile against authoritative live state before choosing retry semantics:

- live state equals the proposed candidate: the effect completed, but command completion is unconfirmed; return a reconciliation-required completed result;
- live state still equals the exact pre-operation value: the effect is authoritatively absent and a no-effect failure is truthful;
- live state is a third value or cannot be read authoritatively: outcome is unknown; mark that the effect may have completed, require reconciliation, and prohibit automatic retry.

Never delete or reset a third-party state merely to make the result look like the pre-operation state. TDD all three branches: apply the real mutation and then synthesize a timeout; fail before mutation while preserving the old value; and move state concurrently to a third value. Keep completion truth/retry authority separate from whether the candidate object itself was constructed and verified.

## Common pitfalls

- Treating a later passing suite as proof that a final production flaw was repaired.
- Repeating a reviewer’s nonexistent function name without inspecting the AST/source.
- Calling a local wait unbounded when an outer process-group timeout exists, or ignoring the local denial-of-service because the outer timeout exists.
- Treating ownership checks as authentication for explicitly untrusted evidence.
- Reporting only ordinal-level verdicts when one ordinal contains true, false, and temporal subclaims.
- Conflating “path ownership matches the manifest” with “capability/test pairing is valid.”
