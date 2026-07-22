# Immutable review and runtime-closure lessons

Use this reference for long Busdriver relay hardening loops that repeatedly build exact candidates, run independent reviews, and update authenticated helper inventories.

## Keep review machinery outside the source tree

All boundary builders, verifier wrappers, candidates, immutable views, prompts, reports, logs, pytest basetemps, and tool caches belong under the approved runtime root, never the repository cwd.

Review helpers may interpret a relative lane as relative to cwd. Always pass an **absolute lane path**. Before creating all lanes, run one diagnostic START outside the repo and confirm:

- source closure is `ok`;
- candidate closure is `ok`;
- expected and actual entry counts match;
- no new repo status records appeared.

If a failed invocation wrote lane directories into the repo, remove only the exact directories created by that invocation, then re-check the live source against the already-built boundary before continuing.

## Generate verifier identity from the boundary

Do not hand-copy source digests, candidate trees, generation labels, or dirty/tracked counts into verifier wrappers. Parse the completed boundary and replace every template constant programmatically. Preserve the boundary's generation value exactly; a filename such as `r21` does not imply that the schema generation changed.

A wrapper may successfully persist closure JSON and then fail in a cosmetic summary-print step because the caller guessed a JSON key. Treat the persisted closure document—not terminal prose—as authority, but do not claim START until its top-level and nested source/candidate `ok` fields are verified.

## A completed process is not automatically a verdict

The shell wrapper PID and the model child lifetime can differ. Require all of the following before accepting a lane:

1. reviewer process has actually exited;
2. report exists and is non-empty;
3. report contains the required verdict;
4. START and END source/candidate closures pass;
5. immutable-view lanes also pass view closure at both ends.

Provider safety-filter responses, empty reports, max-turn exits, or narration without a verdict are `INCOMPLETE`, never CLEAN. Re-dispatch with a narrower authorized prompt or another approved local lane; do not infer findings or success.

## Authenticated runtime hashes form a dependency DAG

When a trusted child script changes, update in dependency order:

1. stabilize the child bytes and compute its digest;
2. update every embedded consumer pin;
3. compute each changed consumer's new digest;
4. repeat upward until no consumer changes;
5. update every manifest section containing each digest;
6. run the manifest contract and a programmatic embedded-inventory closure check;
7. only then compute the final boundary.

Updating only the manifest is insufficient when a dispatcher embeds a private-runtime inventory. Updating an embedded child pin changes the dispatcher bytes and therefore changes the dispatcher's own manifest digest.

## Review recurrent subprocess and side-effect truth

For manifest-listed or trusted entrypoints:

- never inherit ambient `PATH`, `PYTHONPATH`, `PYTHONHOME`, shell startup variables, `GIT_*`, or loader variables (`LD_*`/`DYLD_*`);
- pass an explicit allowlisted environment and fixed executable paths;
- invoke trusted Python children with isolated startup (`sys.executable -I`) when compatible;
- avoid PATH fallbacks such as bare `pytest`/`uvx` in a trusted verification surface;
- convert launch/cwd `OSError`, timeout, and integrity drift into distinct machine-readable outcomes rather than tracebacks or one misleading reason.

For irreversible Git operations, model **effect truth separately from command success**. If a publish CAS succeeded and later verification or rollback races, determine whether the candidate commit is reachable from the observed branch. A reachable landed commit must remain `committed` with nonzero reconciliation required; never downgrade it to `blocked`/no-side-effect. Do not reuse one reason literal for both landed and non-landed contracts.

## Round discipline

Any source-byte change invalidates the previous boundary and all reviews. After the final patch in a round, rerun focused regressions, complete relevant suites, manifest closure, syntax/JSON/diff checks, ignored-artifact cleanup, and secret scanning. Build the next boundary only from that final state.

At a tool-call cap, report the exact latest verified stage. A built boundary whose verifier was not exercised is not an opened review round; passing tests are not freeze; and no freeze means no delivery or merge authority.
