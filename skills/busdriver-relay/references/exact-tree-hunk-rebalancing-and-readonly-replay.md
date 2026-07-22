# Exact-tree hunk rebalancing and read-only replay

Use this when an existing manifest-driven stack must be rebuilt for a newer dirty virtual tree, especially when the slice count must remain fixed while line/file caps tighten. Use it with `capability-sliced-doc-manifest-lessons.md` for classification and `bounded-slice-review-method.md` for immediate-base review discipline.

## Read-only exact-tree freeze without repository object writes

A temporary index alone avoids staging the source index but may still write new blobs/trees into the source repository object database. For stricter read-only work, isolate both index and object writes:

```bash
# Use the configured external Hermes runtime root. For this user's Busdriver
# work, keep all generated artifacts under /Volumes/Work/.hermes-runtime/;
# never put them in the repository, current working directory, home, or system /tmp.
runtime_root="${HERMES_RUNTIME_ROOT:?set an authorized external runtime root}"
mkdir -p "$runtime_root"
analysis_dir="$(mktemp -d "$runtime_root/exact-tree-replay.XXXXXX")"
mkdir -p "$analysis_dir/objects/info" "$analysis_dir/objects/pack"
(
  export GIT_INDEX_FILE="$analysis_dir/index"
  export GIT_OBJECT_DIRECTORY="$analysis_dir/objects"
  export GIT_ALTERNATE_OBJECT_DIRECTORIES="$(git rev-parse --git-common-dir)/objects"
  export GIT_OPTIONAL_LOCKS=0

  git read-tree HEAD
  git add -A -- .
  git write-tree
)
```

Resolve a relative `--git-common-dir` against the repository root before assigning the alternate. Keep all `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_DIR`, `GIT_WORK_TREE`, `TMPDIR`, and XDG overrides command-local or inside a subshell; do not bare-export them in a persistent Hermes terminal. A tracked background runner can finish after an earlier cleanup and reintroduce its launch environment into the persistent shell, so after every runner/process completion explicitly inspect and clear Git object/index/worktree overrides, then re-establish the authorized stable runtime TMP/cache roots before authoritative tests. If many otherwise unrelated Git fixtures suddenly report `not_a_git_repo`, treat environment contamination as the first diagnostic, reset it, and rerun the exact suite rather than editing source.

Record before/after HEAD, HEAD tree, source-index SHA-256, a hash of exact `status --porcelain=v1 -z --untracked-files=all` bytes, temporary-index SHA-256, and virtual tree. Recompute with a fresh temporary index at the end; equality of all source-side hashes is the no-mutation proof.

## Canonical latest-hunk inventory

Choose and record the exact diff representation. Context width changes patch bytes, so a default-context patch hash and a `--unified=1` hash are both valid but not interchangeable.

Recommended canonical command:

```bash
git diff --no-ext-diff --no-textconv --no-color --binary --unified=1 HEAD <target-tree>
```

For each hunk, derive a deterministic ID from canonical bytes such as:

```text
lh-<sha256(path NUL old-range NUL new-range NUL hunk-body)[:20]>
```

Reconcile hunk additions/deletions against `--numstat`, reject duplicate IDs, and include newly added paths. If every latest hunk on a path has one owner, keep the path whole; per-path patch application is simpler and avoids context drift during replay. Split a path only when capability boundaries genuinely require it.

### Coalesced-hunk, blame, and line-accounting caveats

A final context-free Git hunk can coalesce adjacent lines that originated in different stack slices. If planning needs finer ownership, divide it into deterministic contiguous ownership segments, but label those as **planning units**, not independently applyable Git hunks. The replay validator remains authoritative: it must materialize immediate-base deltas and reproduce the target tree.

### Accounting closure is not ownership closure

Treat a report that assigns one scalar `owner` field to every generated record as an accounting partition, not independent proof of correct ownership. Its own `unowned == 0` and `duplicate_ids == 0` counters can be true by construction. Acceptance requires an independently derived source inventory and fatal checks that prove every source hunk/planning unit appears exactly once. The builder must exit nonzero—not merely emit a JSON failure list—for duplicate IDs, unowned/ambiguous units, source-inventory mismatch, replay failure, or cap failure.

Do not make budget compliance by overwriting owners according to line position (for example, “newest test ranges first”). A budget move needs a capability-level justification, preserved production/test dependency order, and replayed immediate-base viability. Moving one- or two-line test segments to a later companion slice may satisfy arithmetic while splitting a test/function or leaving the production slice without its validating contract. Record every move with its semantic group and dependency rationale, then replay it.

A durable proposal must hash every authority-bearing input: source diff arguments and bytes, ownership manifest, prior transition/draft metadata, builder source, and any capability/remap table. Binding only the target tree and aggregate patch leaves owner semantics dependent on mutable external inputs.

`git blame --contents` is useful for mapping unchanged candidate lines back to stack commits, with two important exceptions:

- new remediation lines appear with the zero OID and need an explicit capability owner;
- moved-but-unchanged lines may retain an older main-ancestry commit rather than the slice that moved them. Map those OIDs through a reviewed capability table or the authoritative transition history; never silently default to the first path owner.

Rendered patch-prefix counts can differ from `--numstat` in adversarial files or special diff displays. Treat `--numstat` as the budget authority. Record any per-path reconciliation as explicit owned accounting units, then require replayed immediate-base Git stats to confirm the final budgets. A zero-ambiguity planning artifact without successful replay is a proposal, not a delivered stack.

## Rebalance a fixed-count stack

1. Evaluate the old manifest against the **new** caps and report only actual old oversubscriptions.
2. Separately compute latest-induced oversubscriptions; an old near-cap slice may become invalid only after remediation hunks are assigned.
3. Split oversubscribed temporal slices only at contiguous sealed-stage boundaries. Preserve per-path transition order.
4. Recover the fixed slice count by merging only same-capability or naturally coupled small slices. Good candidates are two halves of the same docs capability, two reference-availability slices, or readiness plus its smoke contract after prerequisites exist.
5. Keep final digest/pin changes after every covered production byte. Put global manifest tests after or with the manifest according to the available budget.
6. Recompute dependencies after split/merge; verify every semantic dependency points to an earlier ordinal.

### Dependency completeness is separate from DAG order

A declared `depends_on` graph can be acyclic and correctly ordered while still omitting real runtime edges. Treat these as separate validations:

1. **Declared-order validity:** every named dependency exists and has a lower ordinal.
2. **Semantic completeness:** independently derive producer/consumer edges from authenticated helper maps, embedded digest pins, subprocess/exec dispatch, generated runtime inventories, manifests, and test/import relationships.
3. **Intermediate closure:** for every replayed tree, compare each embedded digest to the producer bytes present in that same tree. Check both directions:
   - producer lands first while the consumer retains its old pin;
   - consumer/final pin lands first while the producer still has old bytes.
4. **Capability viability:** exercise or statically prove the owned capability at that intermediate tree. A digest mismatch that fails closed is safer than executing untrusted bytes, but it still means the slice is not a complete runnable capability.

Do not emit a generic `semantic_dependency_dag_and_order: true` constant. Derive separate booleans and retain structured failure records such as consumer path, pin name, expected digest, actual digest, producer path, consumer owner, producer owner, and replay ordinal. Exact final-tree replay, unique ownership, and cap compliance are necessary but do not imply semantic closure.

When a latest full-path patch was generated from `HEAD..<target>`, add another replay precondition: immediately before applying it, require the current index entry for that path to equal the `HEAD` mode/OID (or to be absent when the path is new). This distinguishes genuine context readiness from a patch that merely happens to apply.

Do not claim exact budgets from sums of historical transition costs. Replaying several transitions in one slice can revise the same lines, so additive costs are only conservative upper bounds. Materialize each proposed immediate-base delta and compute its actual `--numstat`.

## Artifact pinning and independent replay

Treat replay storage as two classes:

- **Durable evidence:** canonical hunk inventory, proposal/ownership JSON, builder source, end-state record, run log, and SHA-256 manifest. Pin these under the authorized external runtime root.
- **Rebuildable scratch:** temporary index, loose object directory, packs, and transient comparison copies. Keep these under the same external runtime while active, then delete them after hashes and validation records are sealed.

If a delegated worker writes useful artifacts under system `/tmp`, do not cite that transient location as final evidence. Copy only the durable files to the authorized runtime root, verify their reported hashes after copying, then remove the entire superseded temporary tree. Do not copy a replay object store merely to preserve it.

Replay builders must accept an analysis/output root by CLI or environment; never hard-code a one-run temporary directory into a durable builder. For an independent reproducibility check:

1. run the builder again in a different external runtime subdirectory;
2. require the same final tree, owner coverage, slice count, caps, and intermediate slice stats;
3. compare proposal JSON after normalizing **only declared runtime-path fields** such as temporary index/object paths and the relocated inventory path;
4. require canonical equality and matching normalized SHA-256;
5. recompute the source virtual tree, real-index diff count, and exact status fingerprint after the rerun;
6. seal a small independent-validation JSON, then delete the rerun object/index store.

### Verify replay after scratch objects are gone

A durable proposal may retain intermediate tree OIDs after its isolated loose-object store has correctly been deleted. Do not treat `git ls-tree <intermediate-oid>` failing in the source object database as a replay failure, and do not resurrect or copy the scratch object store merely to make those OIDs inspectable. Recompute them from the proposal's flat `(path, mode, blob-or-commit OID)` state instead:

1. Resolve a replay base that may be a **commit** with `<base>^{tree}` before comparing it to a tree OID. Never compare the commit OID itself to an in-memory tree hash.
2. Apply each old transition only after its declared old `(mode, OID)` matches the current path entry. Sort by authoritative stage and original inventory order.
3. Before applying a `HEAD..<target>` latest full-path update, require that path's current entry to equal the recorded HEAD entry; then install the target entry. This proves temporal readiness without needing patch scratch files.
4. Build a recursive tree from the flat map. Encode each entry as `mode SP name NUL raw-oid`; encode directories with mode `40000`; sort with Git tree ordering (`name + '/'` for directories, `name + NUL` for non-directories); hash `tree SP <byte-length> NUL <entries>` with the repository object hash. Require every recomputed slice tree OID and the final target OID to match the proposal.
5. Independently derive changed paths from consecutive flat maps. For modified text blobs, `git diff --numstat <old-blob> <new-blob>` works without intermediate tree objects. For additions/deletions, count lines directly from the one existing blob because the canonical empty blob may not exist in the source object database. Treat mode-only changes as zero added/deleted lines and keep binary/submodule cases explicit rather than guessing.

This post-scratch path is a second implementation, not a replacement for the original isolated-index replay. Use it to catch proposal/parser coupling and to verify retained evidence without writing any Git object. Preserve exact byte semantics in hunk IDs and tree encodings: use actual NUL/newline bytes, not over-escaped textual `\\0` or `\\n` sequences.

When a successful replay proposal supersedes a line-segment or accounting-only ownership artifact, retain one delivery authority. Archive or remove the weaker artifact, or mark it explicitly non-authoritative; two contradictory zero-failure artifacts invite restack drift. A base-to-target segment report may have perfect scalar coverage and 32 budget rows yet still be non-authoritative when it lacks temporal old-transition ownership, dependency edges, intermediate trees, and a final replay proof. Compare its abstraction explicitly with the rebuild proposal before retirement; similarly named “latest ownership” files may describe aggregate base-to-target segments rather than actual `HEAD..<target>` hunks.

## Turn replayed trees into a publishable commit chain

A replay proposal proves tree sequence and budgets, but publishing introduces another boundary. Build the commit chain in the same isolated object store before touching remote refs:

1. For each proposed slice tree in ordinal order, create one commit with `git commit-tree <tree> -p <previous-commit>`; the first parent is the freshly verified live base commit.
2. Require `git show -s --format=%T` to equal the proposal tree and `%P` to equal the intended parent for every commit.
3. Diff each parent/commit pair with the same `--numstat` classification used by the proposal and require exact equality with its immediate-slice stats and caps.
4. Seal a commit-plan artifact mapping ordinal, capability, PR number, head ref, base ref, expected old remote head, new commit, parent, tree, and stats.
5. Keep the commits/ref plan local to the isolated object store until final exact-tree reviews and an exact hosted-CI evidence lane pass.

Before publishing an existing Draft stack, query every live remote head again. Push with an explicit expected-old OID (`--force-with-lease=<ref>:<oid>` or equivalent API CAS), never with an unbounded force. Preserve the fixed PR count by mapping the new ordinal sequence onto the existing PR head refs, then update each PR base/title/body and verify immediate GitHub diff stats, top commit tree, check run commit binding, and Draft state.

When a workflow must be exercised before the real stack is updated, create a temporary Draft CI PR whose single commit has the exact candidate tree and the current live main commit as parent. Record commit/tree/base OIDs, close the PR, and delete its branch after evidence is sealed. Keep this lane separate from the 32 delivery PRs.

## Temporary-index replay validator

Start from the immutable stack base in a fresh temporary index/object directory.

For each proposed slice in topological order:

1. Sort owned old transition units by authoritative stage order.
2. Before each unit, require the current stage-0 index entry `(mode, oid)` to equal the unit's declared `old` entry. For a deletion, require the declared old entry and remove it; for an addition/update, install the declared `new` mode/OID with `git update-index --cacheinfo`.
3. Apply the latest full-path patches owned by that slice with `git apply --cached --binary`. A latest patch may land only after that path's old transitions have reached the old-final blob it was diffed against.
4. `git write-tree` and diff the previous slice tree to the new tree using `--numstat`.
5. Classify changed paths using the old transition category when available, with a documented fallback for newly introduced paths. Count production lines/files and non-doc files independently.
6. Enforce every cap and record the intermediate tree.

After all slices, require:

- every old transition unit has owner count exactly one;
- every latest hunk has owner count exactly one;
- dependencies are acyclic and topologically ordered;
- every immediate-base slice is within caps;
- replay final tree equals the requested exact target tree.

## Recommended proposal artifact

```json
{
  "schema": ".../v1",
  "read_only": true,
  "source": {
    "origin_main": "<oid>",
    "head": "<oid>",
    "head_tree": "<oid>",
    "target_tree": "<oid>",
    "canonical_latest_diff_args": [],
    "canonical_latest_diff_sha256": "<sha256>",
    "old_artifacts": {"path": "sha256"}
  },
  "budgets": {
    "production_lines": 2500,
    "total_lines": 4000,
    "production_files": 15,
    "non_doc_files": 25
  },
  "aggregate_base_to_target": {},
  "minimum_slice_lower_bounds": {},
  "old_oversubscribed": [],
  "moves": [],
  "slices": [
    {
      "ordinal": 1,
      "id": "slice-id",
      "capability": "...",
      "stack_predecessor": null,
      "depends_on": [],
      "old_components": [],
      "old_transition_unit_count": 0,
      "latest_hunk_count": 0,
      "latest_paths": [],
      "tree": "<oid>",
      "stats": {
        "add": 0,
        "delete": 0,
        "total_lines": 0,
        "production_lines": 0,
        "changed_files": 0,
        "production_files": 0,
        "non_doc_files": 0
      },
      "within_caps": {}
    }
  ],
  "old_transition_owner": {"tu-id": "slice-id"},
  "latest_hunk_owner": {"lh-id": "slice-id"},
  "latest_path_owner": {"path": "slice-id"},
  "validation": {}
}
```

Compute hard lower bounds from aggregate base-to-target `--numstat`, not from the sum of temporal bounded-slice diffs. The latter is expected to be larger because later transitions revise earlier lines.

## Pitfalls

- A temporary index is not sufficient for strict no-repository-write claims unless object writes are isolated too.
- `git status` can refresh the real index; use `GIT_OPTIONAL_LOCKS=0` and hash the source index before/after.
- Do not compare status hashes produced with different porcelain/options. Record the exact command and delimiter mode: newline-delimited `--porcelain=v1` and NUL-delimited `--porcelain=v1 -z` legitimately hash differently for the same status entries.
- A non-replayed segment artifact can undercount a merged immediate slice even when its aggregate coverage is exact. Directly diff the base tree to the replayed merged tree; if those actual cap metrics disagree with its `budget_pass`, retire the segment artifact rather than averaging or reconciling the two authorities.
- Retiring a demonstrably weaker artifact does not endorse its replacement. A replacement may be authoritative for byte replay/ownership/caps yet still remain blocked on semantic dependency closure.
- Do not report only old oversubscriptions; latest hunks can push a previously valid slice over production or total caps.
- Do not place a latest patch before the old path reaches the blob against which that patch was generated.
- Do not use a future digest manifest in an earlier slice to make local tests green.
- State how `production` and `non-doc` are classified; file-count conclusions are otherwise ambiguous.
- Keep analysis artifacts outside the repository, hash them, and disclose their paths. Do not run mutating tests during an analysis-only request.
