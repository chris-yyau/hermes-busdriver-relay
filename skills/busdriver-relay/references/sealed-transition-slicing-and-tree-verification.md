# Sealed transition slicing and tree-addressed verification

Use this when a Busdriver/relay candidate is a large dirty worktree that accumulated through many reviewed iterations, and the final aggregate diff is too large or too coupled to flatten safely into one PR.

## Safety invariant: freeze first, decompose elsewhere

- Treat the dirty source worktree as read-only. Do not stage, commit, reset, checkout, clean, rebase, or refresh it as part of decomposition.
- Build an owner-only rescue outside the source before classifying hunks. Preserve the candidate tree/commit, a self-contained bundle and clone, tracked and untracked bytes, executable modes, symlink targets, exact status bytes, and SHA-256 sidecars.
- Record the exact status command and flags with the status hash. Different porcelain options can produce different byte streams without any worktree mutation; compare like with like.
- Keep rescue and decomposition repositories free of external remotes. Delivery later pushes only explicitly named slice refs, never `--all` or rescue/round refs.

## Reconstruct sealed boundary history

Historical review boundaries are useful only if each claimed tree is cryptographically reproducible.

1. Start a private bare history repository from the verified rescue bundle so the candidate head and its base history are self-contained.
2. For every sealed boundary, record the expected candidate tree OID and source/base commit.
3. Prefer a read-only candidate view when present. Reconstruct its tree with a temporary index initialized from the base tree, overlaying tracked modifications, deletions, modes, symlinks, and expanded untracked files.
4. If the candidate tree is absent from the view but survives in an identity object store, import only the required objects into the private repository. Never mutate the identity store.
5. Require the reconstructed `write-tree` result to equal the sealed expected tree OID exactly. Reject that boundary on mismatch.
6. Create synthetic linear commits/refs only after exact tree equality. Synthetic commit OIDs are bookkeeping; tree OIDs are the authenticity boundary.
7. Verify the private history with `git fsck`, no remotes, owner-only permissions, and final-tree equality with the rescue commit.

A closure sidecar does not imply that its candidate clone still has the root tree object. Candidate worktree bytes plus base objects can still reconstruct the exact tree; verify rather than assuming.

## Build a lossless transition inventory

Do not flatten dozens of hardening rounds into one aggregate hunk inventory when intermediate boundaries exist.

- Build a sequence from the original source commits and every sealed boundary transition.
- Define a transition path unit with stage ID, path, old/new blob OIDs, old/new modes, exact patch SHA-256, and hunk SHA-256 values.
- Use at least one context line (`--unified=1` or more) and reconcile additions/deletions against `--numstat`. Zero-context output can render adjacent insertion/deletion changes incompletely for inventory purposes.
- Include mode-only and deletion units, not only text hunks.
- Assign every transition unit to exactly one slice. Validate owner count `== 1`, acyclic dependencies, per-slice budgets, and replay closure to the final sealed tree.
- Distinguish path ownership from transition ownership: a large mixed path may have several ordered slices, but each transition unit still has exactly one owner.

## Independent bounded-slice review discipline

When reviewing a pre-built stack or ownership manifest, each slice is its own security boundary. Do not review a branch tip once and project that verdict backward.

1. Parse the authoritative manifest once and record, per slice: ordinal/ID, capability, exact `stack_base_commit`, exact `commit`, materialized paths, and declared tests/harnesses.
2. For that slice, inspect only `stack_base_commit..commit`. Do not substitute a neighboring commit, merge base, final aggregate, branch tip, or reconstructed “equivalent” range.
3. Make Git failure visible. If diff output is piped through a formatter, enable `set -o pipefail` or capture Git and formatter statuses separately; an empty formatter exit 0 must never launder `git diff` exit 128 into a successful inspection.
4. Require the changed-path set to equal the manifest path set exactly. Then classify each changed path as production, contract test, fixture/harness, manifest/config, or documentation and verify that the set actually implements the named capability.
5. Treat a test-only integration slice as potentially valid when its capability explicitly says “contracts” or “integration” and the tests prove production/fixture authority separation. Do not demand a production edit from every slice.
6. Review temporal production slices against their immediate base. A defect fixed by a later slice still fails the earlier slice. Later patches are useful clues, but cite the vulnerable function/hunk in the earlier bounded diff as the finding evidence.
7. Separate evidence collection from adjudication. Diff retrieval success, byte count, line count, or exit 0 proves only that inspection succeeded—not that the slice passed.
8. Emit compact, durable evidence while inspecting: range, changed paths, key function/hunk names, and candidate findings. Avoid relying on huge transient tool output whose actual lines may disappear after context compaction.

For mutation/finalization slices, apply these mandatory lenses per checkpoint:

- executable identity at the actual exec boundary, not merely before copying or pathname lookup;
- credential-bearing environment allowlists, including host/repository and loader/toolchain overrides;
- hook execution and repository-local config as untrusted code paths;
- output and authenticated-ingress bounds before allocation/digesting;
- pre-reap-only PID/process-group signalling;
- completed-effect truth under timeout, ambiguous exit, failed postcondition, and concurrent actors;
- atomic binding (or an explicit fixed blocker) between reviewed identity/base/destination and the side effect;
- cross-process durability claims: a persisted artifact without a durable verifier is closed storage, not durable status lookup.

A useful final report is per-slice and machine-readable in shape: `id`, `passed`, `security_concerns`, `logic_errors`, `nonblocking_suggestions`, and `verdict`, followed by an aggregate pass/fail count and an explicit read-only/no-mutation statement.

## Slice compatibility is stricter than path pairing

A production file and a similarly named test are not necessarily a valid intermediate slice.

### Coalesce incomplete capability transitions

A temporal stack may expose historical checkpoints only when each checkpoint is independently safe. Coalesce adjacent transitions into one capability slice when any of these is true:

- production becomes reachable before its containment, timeout, credential, integrity, or completed-effect fix lands;
- an embedded digest points to bytes that do not exist until the next transition, making the checkpoint deterministically unusable;
- the only behavioral tests for a large production surface arrive later, so the earlier slice cannot substantiate its capability claim;
- a later patch is required to make the earlier implementation fail closed rather than merely improve it.

Do not call the earlier slice valid because the final tree is safe. A later fix cannot retroactively authorize an earlier PR. Keeping implementation and contract slices separate is acceptable only when the earlier production path is already securely policy-blocked/unreachable, or when its own focused tests prove the claimed boundary and the later slice is explicitly cross-surface integration. If coalescing exceeds the normal budget, record the reason as an indivisible security/capability unit rather than preserving a smaller but unsafe checkpoint.

- Final integration tests often import shared fixtures or exercise helpers that land later. Treat module import/collection, fixture imports, manifests, schemas, and parity enumerators as explicit dependency edges.
- Separate a production implementation slice from a later integration-contract slice when the final test file requires delivery-status, litmus, PR-grind, adapter, or other downstream surfaces. The integration slice lands only after every tested dependency exists.
- Move shared test helpers before the first consumer that imports them.
- A historical production checkpoint must run with compatible checkpoint manifests and helpers. Never combine an old checkpoint executable with final-tree digest manifests or final helper behavior and call the resulting failures candidate defects.
- If an intermediate historical test file is intentionally used, run representative tests that are valid at that boundary, and retain the full final file/suite for final-tree closure. State this distinction explicitly.
- Documentation tests that read a policy inventory during collection require that inventory in the same slice or its base.

### Global closure artifacts land after their referents

A digest manifest, policy inventory, or parity enumerator describes a globally consistent set of bytes or paths; it is not ordinary config.

- Materialize a final executable-digest manifest only after every covered production byte has reached its final version. Do not place future digests in an early slice merely to satisfy one local test.
- If an early capability test has a few manifest-dependent assertions, run the manifest-independent subset there and rerun the complete file in the runtime-closure slice.
- Materialize a documentation/policy inventory only after every active and historical reference it enumerates is present. Reference-availability slices therefore precede the inventory and its collection-time contract test.
- Put the inventory and the test that imports it in the same closure slice. A final aggregate pass does not excuse an earlier collection failure.

## Structural verification before tests

For every planned slice, before invoking tests:

1. create an isolated detached worktree at the immutable slice commit;
2. verify HEAD and tree OIDs against the manifest;
3. verify clean status before the test;
4. run `git diff --check` against the immediate base;
5. verify the exact immediate-base changed path set and budget;
6. run the declared slice-local command with private `TMPDIR`, disabled bytecode/cache writes, and a pinned interpreter whose required runtime capabilities were probed;
7. verify clean status afterward and save a per-slice log.

A failed test may be retried once only after failure, with a fresh private `TMPDIR`, and both attempts must be recorded. Stop after success. Do not globally retry deterministic dependency or assertion failures.

## Full-suite closure by final tree

When a full suite exceeds a monolithic timeout, shard by discovered `test_*.py` files (bounded parallelism, per-file timeout, per-file logs) and require every discovered file to pass.

Seal the result to:

- exact final tree OID;
- discovered/pass/failed/timeout file counts;
- aggregate passed/skipped/failed test counts;
- interpreter identity/capability probe;
- per-file logs;
- result SHA-256 sidecar.

The evidence may be reused after stack-only commit reparenting or ownership metadata changes only when the final tree OID is byte-for-byte identical and the evidence sidecar verifies. Never reuse it for a different tree.

### Finalization errors must not erase completed tests

Treat test execution and result publication as two transactions.

1. Write immutable per-slice/per-shard logs and attempt metadata as each command completes.
2. Unit-test the result/summary finalizer with synthetic rows before an expensive full run; undefined summary variables are not a reason to rerun thousands of tests.
3. Build `RESULT.json`, summaries, and sidecars in staging, validate their schema and hashes, then atomically publish them.
4. On postprocessing failure, preserve completed logs and immutable test metadata. Remove disposable worktrees, but do not fail-clean by deleting expensive evidence that can be freshly structurally revalidated and finalized idempotently.
5. A repaired finalizer must recheck manifest/verifier hashes, commit/tree identities, worktree cleanliness, and every recorded return code before publishing. It may not infer PASS from log existence alone.

## Delivery gate

Do not publish the stack merely because the final tree passes. Require:

- all transition units exactly once;
- every slice structural check passing;
- every slice-local command passing (including any recorded one-time retry);
- final-tree full-suite evidence passing;
- live remote base still equal to the planned base;
- no pre-existing conflicting slice refs/PRs.

Then push only explicit slice branch refs atomically and open Draft PRs with each PR based on its immediate predecessor. Verify remote changed-file/addition/deletion counts against the manifest before PR-grind or merge. Merge only in dependency order, refreshing latest-head evidence after reviewer fixes.

## Common traps

- Hashing a status representation produced by different porcelain flags and misreporting source mutation.
- Treating a missing dangling tree object as proof that the sealed candidate cannot be reconstructed.
- Using `--unified=0` as the only hunk source.
- Adding final digest manifests before covered executables have reached the matching bytes.
- Landing final cross-surface tests before their shared fixtures or downstream helpers.
- Hiding an over-budget file behind a capability label instead of splitting ordered transitions.
- Letting a long full suite time out as one process when deterministic per-file sharding can produce complete evidence.
- Opening remote refs before local exactly-once, immediate-base, and final-tree closures pass.
