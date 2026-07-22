# Final-tree contract and documentation completeness review

Use this when independently triaging security/completeness findings against a sealed or candidate Busdriver relay tree. The objective is to distinguish an exploitable reachable defect from a proof gap, misleading test claim, historical slice issue, or closure artifact that necessarily lives outside the reviewed tree.

## 1. Freeze the audit boundary

1. Record exact `HEAD`, branch, and porcelain status before reading evidence.
2. Treat the named commit/tree as authoritative. A clean worktree is convenient, not a substitute for a commit boundary.
3. Recheck status at the end. If unrelated edits appear concurrently, do not revert them. Read affected baseline files from the frozen Git object (`git show HEAD:path`) and report the drift separately.
4. Do not let later test results silently redefine the audited tree; state whether each run used the clean frozen tree or a subsequently dirty worktree.

## 2. Classify each claim at the right level

Use one primary classification and, where needed, a separate runtime-impact qualifier:

- `CONFIRMED_FINAL`: the final tree still contains the implementation, contract, or documentation defect.
- `RESOLVED_LATER`: true in the reviewed slice, absent from the final tree because a later change closes it.
- `FALSE_POSITIVE`: the alleged behavior is not reachable or the cited evidence does not prove it.
- `TEMPORAL_PACKAGING_ONLY`: the mismatch depends on packaging/review evidence created after the source tree was sealed; it is not a source/runtime defect.

A contract-test gap can be `CONFIRMED_FINAL` even when the current manifest happens to be complete. Conversely, a misleading security test can be confirmed as a claim defect while the alleged production exploit is false because production blocks the path.

For every item, report separately:

1. present-tree defect;
2. production reachability/installability;
3. current exploitability;
4. regression-proof completeness;
5. bounded fix.

## 3. Trusted-runtime closure

Never prove a manifest complete using values derived from that same manifest or from a runtime helper's self-reported capability list.

Derive and compare at least these independent sets:

- actual installed entrypoints from the installer/package definition;
- if no installer exists, tracked executable scripts (`git ls-files --stage`, mode `100755`) plus documented adapter runtime;
- production-reachable subprocess/dynamic-dispatch consumers;
- repo-local child targets reached transitively;
- embedded digest literals and their owning consumers.

Require exact set equality where appropriate, not only `consumers <= manifest`. Add mutants for:

- a new executable that performs no subprocess dispatch;
- a new helper reached through an existing parent but omitted from a self-reported capability list;
- a new digest literal in either quote style;
- a nested/dynamic child target.

## 4. Retained private runtime and same-UID claims

`0700` directories, `0500` files, digest checks, and copying into a private runtime do not stop the owner UID from unlinking/renaming/replacing a pathname before `exec`. Distinguish:

- source-anchor replacement before/during authentication;
- retained-path replacement after materialization but immediately before child launch;
- execution of retained in-memory bytes through a fixed interpreter loader;
- dormant path-exec code that production rejects before lookup/materialization/dispatch.

A valid same-UID regression deterministically swaps the retained pathname at the final `Popen`/bounded-run seam. It must prove either that attacker bytes did not run because execution identity is retained bytes/descriptor-backed state, or that a non-overridable production blocker fired first.

Do not name a test as proving "safe retained execution" if it only proves that the original source path is not reopened. Mark dormant wrapper tests as future-unblock preconditions rather than present production safety evidence.

## 5. Git observation call-surface closure

A tuple named `OBSERVERS` is not proof of every observer. Derive all Git subprocesses from installed/reachable files and require each to have one explicit class:

- observation through authenticated no-exec/no-network sandbox;
- mutation through the approved hardened mutation boundary;
- production-blocked path;
- narrowly reviewed metadata-only exception, with behavior tests and written rationale.

Include nested helpers, bytes/NUL variants, pathspec batching, brokers, lock metadata probes, and helper scripts. Keep dynamic hostile filter/signature/submodule/lazy-fetch tests, but also add a completeness mutant where a new raw Git observation is inserted outside the central helper. Universal test names must match the derived surface they actually cover.

## 6. Documentation inventory and closure

A doc-policy scanner should discover repository-local Markdown targets in:

- inline links;
- reference definitions;
- HTML `href` attributes;
- single-backtick code spans whose entire content is a local `*.md` path, optionally with a fragment.

Reachability must start only from declared roots (plus any explicitly defined ADR roots). Do **not** seed traversal with every already-classified active document; that makes orphan detection tautological. Assert both:

- every discovered current doc is classified;
- every classified current doc intended to be reachable is discovered from roots.

Use mutants for backtick paths and orphaned active docs. Replace machine-specific evidence paths with symbolic artifact identifiers while retaining hashes and provenance.

Exact-review closure is often temporal: a source commit cannot contain attestations produced only after that commit was frozen. Put authoritative closure in a sidecar keyed by commit/tree hash, or revise and reseal once. The source status should state its snapshot scope rather than claiming post-seal review completion.

### Operational command truth

Do not validate command documentation by reading prose alone. Load the final implementation without executing its main entrypoint and inspect or invoke the command-construction helpers under the documented launch method. Compare at least:

- the actual executable path versus claims such as `sys.executable`, “active interpreter,” or PATH selection;
- isolation and cache flags (`-B`, `-I`, disabled pytest cache provider, external base temp);
- whether an environment capable of importing a dependency as the caller is relevant when the child executable is separately pinned;
- the exact fail-closed status and remediation guidance when a trusted child lacks a dependency.

A fixed trusted interpreter returning `pytest_unavailable` can be an intentional fail-closed capability rather than a runtime-security defect. Documentation that tells operators to use a different caller interpreter is still a present-tree truth defect if that cannot change the pinned child. Add a contract assertion over the documented argv/remediation, not merely a runtime test that blesses the fail-closed branch.

## 7. Verification and report shape

Run existing focused tests, then run independent read-only probes and negative mutants. A large green suite does not invalidate a demonstrated completeness omission.

For each finding provide:

- classification and severity;
- exact `file:function/test:line` evidence;
- actual runtime/install reachability;
- whether the current behavior is exploitable, merely unproved, or only misleadingly named;
- one minimal regression test;
- one bounded remediation that avoids unrelated refactoring.

Finish with exact test counts and any boundary drift. Do not modify the audited source tree during independent triage.