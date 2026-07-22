# Exact-tree review concurrency and live-CI reconciliation
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this note during final read-only delivery and CI-trust reviews of a named Git tree.

## Immutable evidence phases

1. Seal the source repository by plain filesystem observation before using repository-aware tools. Record HEAD/ref bytes, index identity/hash, tracked and untracked footprint, and repository-local cache/lock files.
2. Reconstruct the named tree with a fresh external index and external object store. Materialize outside the source repository and independently recompute the Git tree hash from filesystem bytes and modes.
3. Keep source review and test execution in separate phases. A test checkout is **mutable evidence** while any test process is alive: tests may deliberately rewrite production files and restore them in `finally` cleanup.
4. Never read candidate source, assign `file:line` findings, or compare workflow policy from a materialization while a suite is running. Wait for every child to exit first.
5. After each test batch, recompute the materialized tree hash while excluding only the scratch `.git` directory. If the suite was interrupted, timed out, killed, or the hash drifted, discard the materialization and rebuild it from the sealed tree before further review.
6. Before reporting, collect the background process result, run a second fresh-index reseal, and compare source HEAD/index/footprint/cache evidence with the opening seal. Outstanding background work or a missing close seal means `INCONCLUSIVE`, never `PASS`.

## Live required-check reconciliation

Treat the exact tree and live repository policy as different evidence domains:

- Normalize live branch-protection `required_status_checks` to unique `(context, app_id)` pairs. Account for both legacy `contexts` and modern app-bound `checks` without double-counting.
- Normalize lock entries to the same pair shape. A matching context string with a different or missing `app_id` is drift.
- Verify each locked context maps to the workflow's effective job name and that the workflow is triggered for the protected change class. A job that exists only on `push` cannot satisfy a pull-request gate.
- Compare the complete sets. Never infer “match” from one expected name, a prose statement of intent, or partial API output.
- Query live policy before concluding what production requires. Remote policy can drift independently from the tree; timestamp and label this as live external evidence.
- If the repository's own checker cannot run because of local setup, do not convert that setup fact into a repository defect. Use an independent read-only API query when available, clearly state that the production checker itself was not exercised, and still perform the exact normalized comparison.
- Classify provider APIs by required authority before the final refresh. Public repository endpoints may be enough for PR metadata, immutable commit/tree binding, check runs, workflow runs, and job steps, while branch-protection and runner-inventory endpoints commonly require authenticated admin scope. Preflight that scope immediately before the reserved endgame and capture the current PR/check/job/policy/runner generation together. If authentication disappears after opening, a public refresh of CI plus stale opening-only policy/runner rows is not a fresh whole-generation proof; label the older rows by capture time and withhold any conclusion that specifically requires current policy or runner state.
- Never redirect a final API response directly over the last good snapshot. A failed or unauthenticated client can truncate the destination before reporting its error. Write under the authorized scratch root to a new temporary file, require a successful request plus non-empty parseable JSON with the expected top-level shape, then atomically promote it.

## Comparing a source worktree with an exact checkout

When checking whether an opening or closing source worktree equals a sealed materialization, compare tracked **leaf semantics**, not directory inode/size rows. Exclude the materialization-only `.git` marker, then compare the complete path set plus every file/symlink type, Git mode, content digest, and symlink target in both directions. A root directory containing `.git` can have a different size or mtime even when every tracked byte is exact. Use a canonical in-memory Git tree rehash for the identity claim; keep directory metadata only for the separate temporal-footprint seal.

## Reporting guardrails

- Take final `file:line` references only from a pristine, hash-verified materialization after all tests finish.
- Separate code findings, deployment/policy drift, and incomplete review evidence.
- Never claim a full suite passed until its terminal result was observed.
- Never claim branch-protection and lock agreement without showing or retaining the exact normalized pair sets.
- When tool budget forces an early stop, report only completed evidence and explicitly withhold `PASS`; do not fill gaps with intended state or historical results.
