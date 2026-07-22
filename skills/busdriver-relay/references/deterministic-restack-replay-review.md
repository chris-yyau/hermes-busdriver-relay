# Deterministic restack replay review
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference for strict read-only reviews of a bounded stacked commit chain built from historical transition units plus a latest-delta inventory.

When historical-unit closure is already established and the remaining task is a focused final replay, continue with `focused-stack-replay-ownership-closure.md` for private-alternate preflight, first-tip CI identity stability, all-tip workflow execution, final-doc ownership, and self-deleting close details.

## Evidence generations and seals

1. Before candidate reads, seal every protected root: source/worktree, common and worktree Git metadata, refs/config/index, all transitively referenced object stores, exact materialization, build artifacts, and ownership/transition inputs. Store row manifests plus separate semantic and temporal digests.
2. If an opening copy differs because a concurrent process is still appending a log or summary, classify that generation as exploratory. Wait for the writer to exit, then start a **new complete evidence generation** with a fresh opening seal and fresh private copies. Do not use a later stable close to bless an earlier moving open.
3. Byte-copy protected inputs into scratch; never hardlink. Compare the copy's semantic rows with the opening rows before using it.
4. Give Git only private object stores. A copied Git directory can retain absolute alternates or worktree pointers, so prefer a new scratch bare repository with a scratch object directory and private-copy alternates.
5. Build and dry-run one close harness at opening time. Its final invocation must: reseal all protected roots, compare semantic and temporal rows, print localized drift, validate every ledger row, delete the entire authorized scratch generation, verify absence, and emit the verdict data to stdout. Reserve the last tool interaction for this invocation; a successful review body without this close is `NO PASS`.

### Discovery-expanded roots and concurrent exact-tree executors

- Treat any seal made before the full authority closure is known as exploratory. If a proposal, closing-authority artifact, `.git` pointer, `commondir`, or alternates file reveals another source root, Git-admin area, object store, ownership input, or exact materialization, start a **fresh complete generation** covering the expanded root set; do not append roots to the old manifest and retain its results.
- A concurrent test process can create and remove temporary files inside an exact materialization, restore every tracked byte, yet leave only a directory `mtime`/`ctime` change. Under a strict semantic+temporal contract, semantic equality does not waive that drift. Localize it, identify any active command whose cwd/arguments name the protected tree, wait for it to exit, then restart the complete generation. Never normalize timestamps or bless the older generation retroactively.
- Close the snapshot-to-copy race in this order: seal all protected originals, make fresh byte copies of every input/object store, compare each copy with its source, then immediately compare the protected originals with the opening seal **before** using the copies. Any drift makes those copies exploratory too.
- After a concurrent-writer restart, rerun all tree-bound checks from the fresh copies, including inventory reconstruction, ownership/CAS replay, stack validation, and executable smoke. Reusing earlier PASS rows defeats generation binding even when semantic digests happen to match.
- A self-deleting close harness is valid when it loads the opening manifest and ledger into memory, performs the final reseal and ledger validation, removes only the pre-authorized scratch root, verifies `lexists(scratch) == false`, and prints the complete close result to stdout. Perform no further candidate tool calls after that invocation.

## Independent inventories and payload replay

- Recompute the latest inventory from the private object closure using the exact diff shape (`--no-ext-diff --no-textconv --no-color --binary --unified=1`). Rebuild deterministic hunk IDs, payload digests, path totals, and patch digest; compare both inventory bytes when two builders are supplied.
- For historical stage/path payloads, replay each declared parent→commit diff with `--full-index --binary --unified=1`. `--full-index` matters: abbreviated `index` lines change the patch SHA even when payload bytes are identical.
- Verify each stage commit's sole parent, old/new `(mode, oid, type)` entries, per-path full patch digest, hunk header/body digest, numstat, changed-path set, and parent chaining. A useful transition-hunk digest includes the `@@ ... @@` header plus its body; latest-inventory payload digests may intentionally cover only the body, so honor each schema rather than assuming one framing.
- Recompute object IDs from `"<type> <len>\0<payload>"` after Git decompresses packed objects. Parse raw trees, preserve raw path bytes and modes, and rebuild intermediate tree IDs in memory instead of writing them to an index.

## Exact-once ownership and temporal CAS

1. Require ownership key sets to equal the historical-unit and latest-hunk key sets exactly; require unique slice IDs and known owners.
2. Sort historical units by declared stage order and original inventory order.
3. Starting from the authority base tree, require the current path entry to equal each unit's declared old state before applying its new state.
4. Apply latest whole-path ownership only when the current entry equals the latest-delta base entry. This catches a latest hunk assigned before the path's last historical transition.
5. Rebuild the tree after every slice and compare it with the proposal. Require the final entry map and root tree to equal the target exactly.
6. Deep-compare independent proposals and require the differing leaf-path set to equal the declared runtime-only exception set exactly—neither fewer silently ignored fields nor extra differences.

## Commit, scanner, and portable-tip closure

- Parse and rehash every commit object. Require exact parent, tree, trailers, immediate numstat, category-derived caps, `diff --check`, and cumulative scanner cleanliness at every tip—not only at the top. Count unique scanned blobs as a cross-check.
- Verify designated early slices carry workflow bytes and the portable smoke file at the first tip where CI needs them. Verify late regression files land in their declared owner slice and are unchanged afterward.
- Extract selected test paths from the named workflow **run step**, not from the whole job: comments can mention unrelated test files and create false path selections. Require the selected set to be exact, ensure every selected blob resolves at all tips, and run the exact cache-suppressed command in private materializations when execution is required.
- Independently inventory every regular `*.py` file plus every suffixless regular file whose first line starts with `#!` and contains `python` case-insensitively. Compare that union with the smoke's discovery scope at every tip; record source-count growth so an unexpectedly empty or narrowed scan cannot false-pass.
- Confirm a claimed stdlib-only smoke from its AST import nodes, not from dependency metadata alone. Run all tips on the oldest supported interpreter and a current/CI-adjacent interpreter when available. Remember that `ast.parse` proves syntax only—it does not prove import-time annotation evaluation or runtime compatibility.
- Do not accept existence/mode/shebang checks as the only evidence for core CI/gate surfaces. On the final exact tree, also invoke read-only required-check validation and representative positive/fail-closed gate probes.
- Prove detection with scratch-only negative mutations: invalid syntax in a suffixless shebang fixture, invalid syntax in a late-slice Python file, one mutation for every asserted workflow/lock/gate surface, and contradictory required-CI guidance text. Require failure in the intended test; collection/setup failure is not detection evidence.
- A supplied `rebuild-*` path may be an evidence/replay directory rather than a materialized candidate tree. Bind its ledgers to the expected top/tree, but do not compare its filesystem manifest to the Git tree unless its schema explicitly says it is a checkout.
- After tip execution, scan for `__pycache__`, `.pytest_cache`, `.pyc`, and `.pyo`; command-shape correctness and clean postconditions are separate assertions.
- Report the portable smoke as stack-portability evidence only. Never promote a tiny per-tip smoke to full-suite or exact-tree delivery authority; list those authorities separately in the verdict.

## Verdict rule

All content checks can pass while the verdict remains `NO PASS`. Missing final reseal comparison, an unvalidated close ledger, or residual scratch is a concrete evidence-admissibility finding, not a minor caveat.
