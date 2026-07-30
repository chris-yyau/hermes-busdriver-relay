# Legacy dirty Relay worktree semantic audits

Use this reference for read-only audits of old Relay worktrees against the exact current `main`, especially when committed history, staged/unstaged edits, and untracked files are mixed together.

## Goal

Recover **intent**, not patches. Classify each meaningful semantic chunk as:

- **A — already present:** current `main` has the same behavior or a safer equivalent;
- **B — superseded/unsafe:** the old behavior conflicts with current policy, trust boundaries, or stronger implementation;
- **C — still valid and missing:** current `main` lacks the behavior and current policy still permits it.

Only C is implementation work. If C is empty, the smallest safe slice is no code.

## Read-only sequence

1. Pin the exact canonical `main` SHA and confirm its status.
2. For each legacy worktree record HEAD, branch, merge-base with current main, porcelain status including all untracked paths, committed range, committed diff, and dirty diff.
3. Use stable patch IDs to detect duplicate commit stacks across worktrees. Different commit hashes can represent byte-equivalent patches; do not count them twice.
4. Build one intent inventory from committed + staged + unstaged + untracked content. Group by behavior, not file or hunk.
5. Compare each intent chunk to current-main code, tests, policy docs, and trust inventory. Never infer applicability from age, branch name, or a clean patch apply.
6. Re-read the current authority map before classifying executor, credential, marker, verifier, push/PR/merge, or OpenCode/Pi behavior. Historical docs are evidence, not authority.
7. For every C item, cite a concrete missing current-main code/test surface and propose the smallest safe slice. No evidence means no C classification.
8. Re-run only read-only status/hash probes and prove all repositories ended unchanged.

## Efficient semantic comparison techniques

- **Definition inventory:** AST-compare top-level functions/classes in legacy files against current main. A legacy definition set that is a subset of a current implementation or non-installed fixture is strong A evidence, but not sufficient by itself.
- **Test-intent mapping:** For legacy-only test names, compare assertions and failure semantics to current tests. Renames often hide stronger replacements.
- **Intentional inversions matter:** A current test may deliberately assert the opposite of the legacy test because the old behavior crossed a trust boundary. Common examples:
  - automatic stale-lock reacquire → explicit manual recovery;
  - restoring/cleaning hook-mutated worktrees → preserve state for reconciliation to avoid data loss;
  - executing helpers from the requested target repo → execute authenticated helpers from the trusted Relay root;
  - accepting structurally valid old artifacts → require authenticated, identity-bound evidence;
  - production executor promotion → retain only authority-negative fixture provenance.
- **Split mixed patches:** One old patch can contain both reusable hardening (A) and policy-obsolete enablement (B). Do not classify the whole commit as one unit.
- **Untracked supersets:** Compare untracked fixture definitions, schemas, manifests, and tests to current tracked counterparts. If current main is a strict semantic superset, classify A rather than preserving the old file merely because it is untracked.

## High-confidence semantic accounting

Use two independent comparisons; neither substitutes for the other:

1. **Patch identity:** compute stable patch IDs for every legacy commit and compare them with current-main commits from the merge-base forward. Also seal the aggregate committed, staged, and unstaged layers separately. A missing patch-ID match means only “not byte-equivalent”; it does **not** imply C.
2. **Test intent:** inventory test definitions added by the effective legacy tree (committed + staged + unstaged), then check exact current-main test names and assertions. Account for every absent test as one of:
   - renamed or strengthened current coverage (A);
   - intentional policy inversion (B);
   - obsolete production route or capability (B);
   - genuinely missing current behavior, followed by source-level gap proof (candidate C).

A useful coverage summary is `legacy_added / exact_name_present / absent_or_renamed`, but the numbers are navigation evidence, not a verdict. Every absent test must be accounted for semantically. Do the same manually for untracked tests and fixtures, which normal Git diffs omit.

Split safety mechanism from route authority. For example, a retired adapter's scope checks, environment allowlist, artifact validation, and authority-false schema may be A as a non-installed historical fixture while promoting that adapter into a production route is B.

## Current gaps do not automatically create C

A current fail-closed blocker is not evidence that the legacy implementation fills the gap. Classify old code as C only when it independently satisfies the **current** missing trust boundary. In particular:

- a private same-UID executable copy does not solve process containment or credential brokering;
- an ordinary push or merge does not solve atomic reviewed-base binding;
- ambient postcondition satisfaction does not prove that the attempted process caused the effect;
- parser/envelope exposure does not establish dispatchability.

If legacy code bypasses a current blocker without implementing its required boundary, it is B, not C. Future architecture needed to retire the blocker is a new slice, not recovered legacy intent.

## Read-only opening and closing seals

For strict audits, inspect `.git` or the linked-worktree gitfile, common-dir config, any `config.worktree`, and every repository/info attributes source as plain files before invoking Git. Then follow `git-observation-sandbox-lessons.md`: dispatch an authenticated Git binary inside a no-child/no-network sandbox and fail closed if that boundary is unavailable. The settings below are defense in depth, not a substitute for containment—repository-selected filters, submodules, or lazy fetch can otherwise execute during nominally read-only status/diff calls:

```text
GIT_CONFIG_NOSYSTEM=1
GIT_CONFIG_GLOBAL=/dev/null
GIT_OPTIONAL_LOCKS=0
GIT_NO_LAZY_FETCH=1
GIT_ALLOW_PROTOCOL=
git -c core.fsmonitor=false -c core.hooksPath=/dev/null ...
git diff --no-ext-diff --no-textconv ...
```

Reject non-empty stderr and partial stdout even when Git exits zero.

Treat the opening seal as a hard gate: do not begin semantic inspection until it has completed successfully for every candidate. A closing-only hash cannot be relabeled as opening evidence; if the opening seal was not captured, report that limitation instead of claiming full-session no-drift proof.

For linked worktrees, resolve both paths before hashing anything:

- `git rev-parse --git-dir` owns that worktree's `HEAD` and index;
- `git rev-parse --git-common-dir` owns the shared object store and usually shared refs/config;
- never assume `$GIT_DIR/objects` exists for a linked worktree.

Seal repositories independently, or isolate errors per repository, so one bad linked-worktree path cannot discard otherwise valid opening output.

At both opening and closing record:

- HEAD, symbolic branch ref, branch-ref value, pinned main value, and merge-base;
- porcelain-v2 status with all untracked paths;
- index path, size, mtime, inode, and SHA-256;
- aggregate committed/staged/unstaged stable patch IDs (`EMPTY` explicitly for empty layers);
- an aggregate manifest over every untracked path, classified with `lstat` before opening it: record byte count and SHA-256 only for regular files without following symlinks; record symlinks by type plus link text, and FIFOs/sockets/devices by type without opening them.

Closing must reproduce the opening status, refs, index identity/hash, layer seals, and untracked hashes. This catches optional index refreshes and concurrent edits that a final clean/dirty sentence would miss. After the closing seal, perform no more candidate reads. Tool-managed result caching outside the protected repo/worktree/HOME scope may be reported separately; do not confuse it with project mutation.

## Worktree disposition

Decide separately from A/B/C:

- **Preserve live** only when unresolved C work still depends on exact dirty state.
- **Archive as a patch bundle** when there is forensic value, many untracked files, or exact dirty provenance may matter. Capture HEAD/branch/status, a binary tracked diff, every untracked file, and SHA-256 fingerprints; verify the capture before deletion.
- **Remove later after explicit discard/capture** when C is empty. Do not keep a dirty worktree alive only because it is dirty.
- When two worktrees share the same stable patch IDs, prefer one verified archive of the broader/superset dirty state rather than two redundant long-lived worktrees.

## Read-only pitfalls

- Do not run tests when the user prohibited all writes: test runners may create caches, temp state, artifacts, or HOME entries. Inspect test contracts statically instead.
- Do not create branches, patch files, stash entries, indexes, refs, or archive files during an audit unless explicitly authorized.
- Do not recommend cherry-picking a large legacy commit when only one semantic subchunk might be C.
- Do not treat an old real-agent smoke as current containment, credential-broker, or dispatch authority.
- Finish by comparing final status to the initial snapshot and report any tool-owned temporary output separately from project changes when relevant.

## Compact report shape

1. Exact current-main SHA and cleanliness.
2. One sentence on duplicate/unique legacy stacks.
3. Compact A/B/C table by semantic chunk.
4. C-only implementation recommendation; say `C = empty` when appropriate.
5. Per-worktree preserve/archive/remove recommendation.
6. Explicit no-change verification and any audit limitations.
