# Independent exact-authority review lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

For a sealed postmerge `SUCCESS` authority that must be reconciled with live GitHub PR/CI/branch state and a clean local `main`, use `postmerge-success-only-live-closeout.md`.

Use this for an independent, read-only review that must end in `PASS` or a concrete blocker. It complements the broader exact-tree security/runtime closure checklist.

For docs/ADR/repository-skill policy convergence reviews, also use `docs-skill-policy-consistency-review.md`; it covers current-vs-historical classification, long-line skill inventories, reference closure, semantic tests, and read-only closing checks.

## Critical-path ordering

1. Define the protected roots and the allowed scratch root before running Git or tests.
2. Capture the opening semantic snapshot before any probe. Include the exact worktree, linked-worktree administrative Git directory, common object store, and every alternate object-store dependency used by the replay/build.
3. Run mandatory identity, clean-tree, coverage, drift, security/DAG, negative, and cache checks.
4. **Reserve the closing seal and scratch cleanup as mandatory work, not optional epilogue.** When tool/time budget gets tight, stop extra exploration and execute the closer first.
5. The closer must compare opening and closing bytes, modes, paths, and timestamps for every protected root, then remove only the declared scratch root and verify it is absent.
6. Emit `PASS` only after the closer succeeds. Missing closing evidence or residual scratch is a blocker even when every test passed.
7. Treat every background runner as an unfinished evidence node until its terminal state, exit code, complete log, and coverage cardinality are captured. A process-start acknowledgement is never test evidence.

A useful implementation is one atomic close command/script that captures, compares, prints the result, removes scratch, checks absence, and exits nonzero on any discrepancy. Test that closer early with a disposable miniature tree rather than discovering output/cleanup defects at the end.

### Tool-budget and background-process cutoff

Do not launch a mandatory full suite in the background unless enough tool budget remains to wait for it and execute the closer. Track every process session ID in the review ledger. If a tool-budget warning arrives, stop exploration immediately: obtain the runner's terminal result, then run the closer. If either result cannot be obtained, return `BLOCKED`/`INCOMPLETE`; never infer success from earlier focused tests, claim scratch cleanup without closer output, or emit `PASS` while a mandatory runner is still active.

## Exact bytes and modes

Do not rely only on `git status` or `diff --check`.

- Parse `git ls-files --stage -z`.
- For each stage-0 entry, compare filesystem type and executable mode to the index mode.
- Recompute the Git blob OID from exact bytes (`SHA1("blob " + decimal_length + NUL + bytes)`) and compare it to the index OID.
- Compare the complete filesystem path set, excluding only the worktree `.git` indirection, to the tracked path set.
- Separately require empty porcelain status with all untracked files visible and submodule drift visible.

For a linked worktree, worktree cleanliness is not object closure. Resolve `.git`, `commondir`, common objects, worktree administration, and alternates explicitly.

## Full coverage versus smoke

Build a cardinality ledger from independently collected node IDs:

- exact command and interpreter;
- exact commit/tree;
- collected count;
- passed, skipped, failed, and deselected counts;
- every deselected node and its adjudication;
- exit status and log digest.

Require `passed + skipped + failed + deselected == collected` for the same collection scope. A per-tip portable smoke may prove replay portability or core-surface presence, but it is never full-suite authority. Keep smoke, changed-surface focused tests, host-runtime probes, and full complement as separate rows.

A saved runner script can supply missing command provenance only when its bytes and relationship to the log are themselves sealed. Prefer recording command/runtime/tree metadata adjacent to the log at run time.

## Host-runtime drift adjudication

A host mismatch may justify one narrow deselection only when all three links are independently proven:

1. The exact host-bound test fails with the expected integrity/version mismatch and no unrelated failure.
2. Official pinned release bytes are authenticated. For GitHub releases, bind the release API tag/asset metadata, release asset digest and size, extracted binary digest and size, and reported version.
3. The pinned bytes pass the **same production function and command-construction path** the deselected test exercises, including private-copy mode, parent mode, link count, ownership, and closing digest.

An earlier fixed policy blocker is useful fail-closed evidence, but it does **not** adjudicate a later dormant-path test: returning before executable authentication proves that production dispatch is blocked, not that the command-construction or private-copy path would pass with the pinned runtime. Keep the host-bound test failed/deselected until the same-path pinned-byte probe above succeeds.

When loading an executable script with `runpy.run_path`, mutating the returned dictionary may not update a function's live globals. Patch `function.__globals__` explicitly for a pinned-snapshot probe, then clear the production cache/runtime globals and verify cleanup. Run under isolated `HOME`, `TMPDIR`, cache roots, `PYTHONDONTWRITEBYTECODE=1`, and cache-disabled pytest.

Never rewrite a live host binary to make the test pass. Keep the current-host failure, official pinned-byte probe, and scope-limited adjudication as separate evidence.

## Replay/object-store closure pitfall

An object directory that contains the top commit but cannot resolve its referenced tree is not a complete rebuild closure. If a replay artifact is not a valid Git directory, a scratch bare reader plus `GIT_OBJECT_DIRECTORY` can probe it without modifying the artifact. Verify the commit, candidate tree, all referenced parents/trees/blobs, and every alternates edge with networking/lazy fetch disabled. Missing or unresolved alternates is a blocker, not a reason to fall back silently to the main repository's object store.

## Metadata-only resolver policy convergence

When policy says a resolver is metadata-only and no production dispatcher exists, review the full semantic chain rather than checking only current defaults:

1. Write the invariant explicitly: valid configuration evidence may be `status=resolved` / `ok=true`, but every dispatch, mutation, and finalization flag must remain false.
2. Probe the producer with a **clean positive tuple** (`programmatic_dispatch_allowed=true`, `adapter_verified=true`, no blocker). A latent branch that turns this into `dispatch_allowed=true` is a blocker even when current default metadata is false.
3. Inspect every downstream validator. A consumer that still treats `dispatch_allowed=true` as the only safe result preserves the old authority contract and will reject the new metadata-only result.
4. Inspect policy knobs, not only defaults. If review independence is mandatory, a config value that disables `avoid_coding_agent_for_review` must be rejected or fail closed; otherwise same-provider review can appear non-degraded.
5. Search unchanged tests and durable references for positive authority assertions. Producer code, consumers, tests, docs, ADRs, and skill references must converge in the same patch; historical material must be clearly marked superseded.
6. Use direct pure-function probes for semantic branches when a host-bound executable-integrity gate prevents representative end-to-end execution. Keep that evidence separate from full-suite authority and do not convert a host mismatch into a durable product rule.

For each blocker, report the producer/consumer lines, the exact triggering input, the observed output, and the smallest shared-boundary fix. Before closing, verify the target worktree still has exactly its opening dirty/untracked scope.

## Stacked policy-commit scope discipline

When the prompt explicitly asks for blockers **introduced by the policy commit itself** and says the commit will be rebased onto a prerequisite/runtime-pin change, keep two ledgers:

- **candidate-local policy defects** — changed behavior, unchanged consumers/docs/tests that the policy migration needed to converge, and direct semantic probes of the reviewed commit;
- **prerequisite/baseline drift** — host-pin mismatches or failures owned by the dependency rather than the policy delta.

Do not promote prerequisite drift into a candidate-local finding merely because it makes a broad suite red. Run the smallest policy-focused selectors that avoid the unrelated boundary, plus direct pure-function probes for the changed invariant, and report the broad failure separately. Conversely, do not let dependency drift excuse a policy defect: a downstream validator that upgrades a clean positive tuple, a caller-configurable independence bypass, or an active skill sentence contradicting the new invariant belongs to the policy commit even when the line itself was unchanged. A final exact-tree `PASS` still requires the prerequisite to be rebased and the complete mandated suite rerun on the resulting tree.

## Review-process environment isolation

Strict read-only review includes the operator shell environment. Never export review `HOME`, `XDG_CONFIG_HOME`, `GH_CONFIG_DIR`, `TMPDIR`, Git overrides, or signing settings into a shared/persistent shell. Pass them only to the individual subprocess (for example through a command-local environment map), and restore/verify the operator environment before any GitHub mutation. This prevents an exact reviewer from silently hiding the authenticated `gh` config or changing later delivery semantics.

Keep semantic and temporal seals separate. A byte/mode/path/ref change is a candidate-integrity blocker. Directory-mtime-only drift with identical semantic hashes is review-integrity noise that must be attributed and rerun for a strict close, but it is not itself a code-security defect. Never relabel one class as the other.

## Async exact-review supersession and PR-feedback repair

Bind every review verdict to the immutable `(commit, tree, parent)` tuple before acting on it. An asynchronously returned `BLOCK` for a superseded candidate stays historical evidence: verify that its findings were fixed, but neither relabel it `PASS` nor treat it as the verdict for the current tree. Dispatch fresh read-only reviews whenever the exact candidate changes.

Reviewer remediation is a new candidate even when it changes only Markdown or a contract test. Invalidate the prior full-suite/CI/review seal, run the narrow semantic guards first, amend or replace the candidate, publish with a lease bound to the old remote head, rerun the complete exact-tree suite, and re-dispatch exact reviewers. Preserve prior results only as lineage.

Adjudicate bot suggestions against the real CLI and policy contract before editing. A required explicit CLI option can be intentional fail-closed behavior rather than a regression. Conversely, documentation examples that literally show `dispatch_allowed=true` can violate active-policy semantic guards unless the same statement says the value is blocked/refused/false. Run the semantic docs suite after every docs-only reviewer fix instead of assuming prose cannot affect policy tests.

Reply to each actionable thread with the fixing commit and focused evidence, resolve it only after the fix is published, then re-query unresolved threads, exact PR head/base, mergeability, and current-head checks. A green prior-head review or an empty thread list captured before the push is stale.

## Authority chronology and Git self-reference

A canonical current-status document must distinguish three states instead of calling the last broadly sealed ancestor `main/top` forever:

1. the historical sealed main before a prerequisite;
2. the actual current base main after that prerequisite, with its own seal evidence if one exists; and
3. the current unmerged candidate, which cannot borrow either earlier seal.

Verify the prerequisite evidence before labeling it `merged-but-unsealed`: a squash merge can preserve the reviewed candidate tree exactly, and exact-tree suite/review plus postmerge CI may already provide a separate seal. The no-borrow rule means each state cites its own authority, not that a later prerequisite is necessarily unsealed.

Do not embed the current candidate commit SHA in a tracked document that is still being amended—the edit changes the SHA and creates an impossible self-reference loop. Keep stable base/history identities in the document, describe the candidate state generically, and bind the exact `(commit, tree, parent, diff digest)` in an external candidate-authority artifact. Contract tests should enforce chronology and no-borrow semantics without hardcoding a self-invalidating candidate SHA.

A chronology-only documentation or contract-test repair still creates a new exact candidate: rerun focused semantic guards, complete exact-tree coverage, current-head CI, and independent exact reviews before sealing.

## SUCCESS-only rule

Authority JSON booleans are claims, not proof. Recompute every referenced digest and require evidence-node closure. `PASS` additionally requires exact identity, bytes/modes, clean tree, complete coverage accounting, narrow drift adjudication, unchanged production/security/digest surface or fresh coverage, negative-path success, cache hygiene, equal opening/closing seals, and absent scratch. Any missing mandatory edge yields a concrete blocker.
