# Final-review remediation patterns
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference when independent final-tree reviews discover findings after a candidate was already sealed. These patterns are class-level: apply them to delivery executors, trusted Git observers, host-sealed CI, and exact-tree evidence workflows.

## Invalidate evidence before fixing

A production or contract edit invalidates the named tree, patch/numstat hashes, full-suite log, ownership closure, and every review tied to them. Mark the old evidence stale immediately. After remediation:

1. rebuild the virtual tree with a fresh external index including all untracked files;
2. refresh runtime manifests and embedded digests to a fixed point;
3. run focused RED → GREEN contracts;
4. run the complete suite with cache suppression and external temp roots;
5. recompute tree, patch, numstat, cache count, index/status fingerprints, and evidence hashes;
6. dispatch new independent reviews against the new exact tree only.

Never carry a PASS from an earlier tree into a later candidate.

## Commit publication truth under concurrency

A changed authoritative `HEAD` is not proof that this invocation published its candidate. Another same-UID actor may win the race with an unrelated commit.

- Only a positive, authenticated `effect_completed is True` may establish that the candidate landed.
- `effect_outcome_unknown=True` must remain a distinct durable state such as `commit_outcome_unknown`; it is neither `committed` nor a retry-safe blocker.
- If lock release then fails, preserve the uncertainty in a distinct release-failed state. Do not turn the commit step into `passed`.
- Regression tests must cover both successful and failed lock release after an unknown publish outcome, and assert that mutation authority stays false.

## Non-reaping child-exit observation

Trusted Git observers may need to detect leader exit before reaping so they can terminate descendants that retained stdout/stderr descriptors. `os.waitid(..., WNOWAIT)` is not available in every production Python, notably some macOS system Python 3.9 builds.

Safe macOS fallback:

1. immediately after `Popen`, register a one-shot `kqueue` `EVFILT_PROC` watcher with `NOTE_EXIT`;
2. poll the watcher without reaping;
3. after leader exit or timeout, kill the process group while the original leader PID is still owned/unreaped;
4. call `wait()` exactly once;
5. close the watcher in all success/error paths.

Do not replace this with `poll()` followed by `killpg(pid, ...)`: `poll()` reaps and creates a PID-reuse window. Test the real production interpreter, not only the test venv.

## Portable versus host-sealed CI

Do not put host-attestation checks into a job merely because the test file also contains portable structural assertions. A test that validates macOS SIP flags or an absolute-tool SHA-256 is host-sealed even when written in Python.

- Give the hosted lane a dedicated portable contract file and explicit allowlist.
- Keep absolute binary hashes, SIP flags, sandbox profiles, and trusted-runner attestation in the host lane.
- Add a contract that parses the portable job command and rejects host-only paths/markers in selected files.
- A local macOS pass cannot clear an Ubuntu portability finding; run the exact command on the hosted OS before delivery.

## Cache-free smoke verification

`python -B` suppresses import bytecode but does **not** prevent explicit `python -m py_compile` from writing `.pyc`. For a read-only smoke syntax check, compile source bytes in memory:

```python
compile(pathlib.Path(path).read_bytes(), path, "exec")
```

Every Python child should use `-B -I`; pytest children should also use `-p no:cacheprovider`. Add a behavior test that runs the production command shape in a scratch tree and asserts that no `__pycache__`, `.pytest_cache`, or `.py[co]` appears.

## Finding classification

Review tables should distinguish:

- **current exploitable/truth defect** — can grant authority, report a false completion, or accept forged state now;
- **honest fail-closed blocker** — blocks availability but cannot produce false-clean/false-authorized state;
- **future capability** — intentionally absent durable broker, runner provisioning, or cross-process attestation.

Fix strict runtime blockers before declaring final runtime integrity even if policy currently makes the path unreachable. An unreachable latent failure becomes production debt as soon as the policy gate is removed.

## History-stable required CI

A required job that runs on every tip of a converted stack may reference only surfaces present from the first converted slice onward. Final-tree contracts are not automatically history-stable.

- Introduce one dedicated smoke in slice 1 and keep the required workflow command on an exact one-file allowlist.
- Make the smoke self-contained and stdlib-only. Parse the current tip's actual `*.py` files plus **every** suffixless Python-shebang entrypoint across the whole repository with `ast.parse`; test fixtures and harnesses are executable surfaces too. Scan the first shebang line repo-wide instead of hard-coding `scripts/` and `adapters/`. Do not import late helpers, fixtures, manifests, or docs contracts.
- Core-surface smoke must validate the smallest stable semantics, not mere existence: required workflow command/path allowlist, required-check lock JSON rows/app provenance, security job IDs/names, and non-empty executable gate/checker scripts. Add one private-copy negative probe that empties each core surface and one that corrupts an otherwise missed fixture entrypoint; every mutation must fail. Preserve the fixture's Python-classification signal (for example its shebang) while making its body syntactically invalid—removing the shebang can make discovery skip the mutation and produce a false pass.
- Independently recompute the complete Python inventory with a different traversal/classification implementation, then require exact set equality with the smoke discoverer—not only a minimum count or two matching totals. Report the expected exact count and useful top-level category counts so additions, omissions, and accidental scratch sources are diagnosable.
- If a final lock/schema field enforced by the smoke (for example `app_id`) did not exist in early tips, move that complete core surface into slice 1 with the smoke/workflow. Do not weaken the final invariant with `row.get(...)` merely to tolerate historical ordering.
- Keep authoritative CI documentation aligned: required `test` is the portable smoke, while the full exact suite remains separate delivery authority.
- Replay the real workflow-selected command at every tip. Also parse each tip's workflow command and assert the selected test paths are exactly the smoke path; running the smoke manually is insufficient proof of workflow stability. Delimit the named execution step or its `run:` block before extracting test paths—regexing the entire job can mistake documentary comments such as “see test_gate.py” for executed tests.
- Prefer `git archive <tip>` into one private scratch tree over checking out 32 tips in the protected worktree. Route `TMPDIR` into that scratch, disable bytecode/cache writes, run the exact workflow command, then remove and explicitly prove the scratch prefixes absent before the closing semantic seal.
- Keep a final-tree regression that parses the required job and rejects every late-slice test path. Prove the guard with one scratch-tree mutation that appends a late test and must fail.
- Search for older contracts that still assert the previous workflow selection. Update those assertions in the same minimal change and run both contract files together; otherwise the new regression can pass while the full suite remains contradictory.
- Keep smoke authority and full-suite authority separate in evidence and PR text.

## Exact-suite closure when a live host runtime drifts

Do not rewrite an unrelated candidate or temporarily replace the user's installed executable merely to make a host-bound test green. A transparent composite authority is admissible only when its candidate-tree coverage is complete:

1. prove the live failure is exactly a digest mismatch against the unchanged pinned runtime contract;
2. obtain official release bytes for the pinned version and independently verify their digest equals the tree's pin;
3. run the candidate's exact full complement with only that named host-bound node deselected;
4. exercise the omitted behavior against the verified pinned bytes through the same production function, including private-copy mode/digest assertions;
5. run focused tests for every changed surface and supported interpreter affected by the change;
6. record the deselected node, counts, exact tree/commit, logs and hashes explicitly.

A prior exact full PASS may support lineage but never substitutes for the candidate complement. The candidate complement plus the pinned-runtime probe must cover the full test set; if the pinned bytes cannot be authenticated or relevant production/runtime source changed, remain `BLOCKED`.

## Shared-head GitHub CI evidence

One commit can be the head of both an exact-top attestation PR and the top stacked PR. GitHub's `actions/runs?head_sha=...` is commit-scoped and returns runs for both PRs.

- Filter Actions runs by `pull_requests[].number` before requiring exactly the expected Tests/Security workflows and their jobs.
- Check runs are also commit-scoped and may legitimately be duplicated. Require the complete set of required names, trusted app IDs, and `completed/success` for every matching row; do not require exactly one GitGuardian row.
- Use the PR-specific status rollup for progress, then a direct REST collection for app provenance, runner group, run attempt/event, exact head/tree, branch protection, and zero self-hosted runners.

## External-scanner comments during stacked-base reconciliation

An atomic stacked push can transiently expose a new head against its old base before GitHub updates the base ref. External scanners may first report a finding, then edit an issue comment to “no secrets present anymore” after rescanning the reconciled PR. Do not silently discard that warning, and do not treat the edited success text alone as proof that no credential was exposed.

A narrow non-actionable adjudication is acceptable only when all of these hold:

1. the comment explicitly says the current PR no longer contains secrets and carries no current incident/path detail;
2. both the prior exact head and current exact head have `COMPLETED/SUCCESS` GitGuardian check runs from App `46505`, with zero annotations;
3. the independently replayed per-slice scanner reports zero findings across every unique blob;
4. current immutable-head CI is green and no human/current-thread/review feedback remains;
5. the raw PR-grind collection remains preserved as fail-closed evidence, while a separate digest-linked adjudication lists every comment ID, prior/current head, and check-run ID.

If any condition is missing, keep the comment actionable and investigate/revoke the credential. Never mutate the original feedback artifact to manufacture a clean result.

## Immutable action pins with linter-compatible annotations

When a workflow pinning linter rejects a legitimate release-specific comment, separate immutable identity from annotation syntax before changing anything:

1. prove the existing action SHA maps to the claimed upstream tag with authoritative Git refs or API metadata;
2. keep the SHA unchanged unless the task explicitly requests an upgrade;
3. replace only the comment with the linter's accepted stable form (for example a major tag such as `# v3` when the tool rejects a bundle tag);
4. run the exact production linter version against a scratch copy that preserves the complete repository-relative `.github/workflows/` layout—single-file scratch checks can fail for root-discovery reasons unrelated to the workflow;
5. keep this hygiene change in its own PR when it is unrelated to the delivery candidate, even if the failing check is non-required.

Record the upstream tag proof and linter version, but do not turn a tool-specific annotation quirk into a new workflow or dependency.

## Bounded independent-review closure

A reviewer that exhausts its tool budget before the closing seal or scratch removal must return `NO PASS`, even when all content probes passed. Design focused review lanes so cleanup cannot be stranded:

1. wait for producers such as pytest/tee to finish before sealing protected evidence roots, or explicitly exclude only named append-only logs until they freeze;
2. create the opening semantic seal first and prepare the close/cleanup command immediately;
3. review only the changed delta plus previously authenticated unchanged lineage—do not recompute a broad 800-unit history when the lane owns a two-file blocker fix;
4. reserve the final calls for opening=closing comparison, scratch deletion, and an explicit absent check;
5. if a reviewer still times out, the coordinator removes the named reviewer-owned scratch before re-dispatching a narrower lane.

Treat leftover reviewer scratch and a missing close seal as admissibility failures, not candidate-content defects.

## Distributed replay-object closure handoff

An exact checkout can be clean while the restack commit graph is unreadable from the replay store alone. Before dispatching an independent reviewer, enumerate the complete immutable object closure explicitly:

- the primary replay object directory that owns the generated commits;
- the candidate object directory that owns the final target tree/latest blobs;
- the base/common object directory that owns inherited history.

The reviewer must opening-seal and byte-copy all three stores, expose only those private copies through a scratch bare repository, and prove `top commit → target tree → base commit` before replay or `fsck`. Do not make the reviewer rediscover alternates under a bounded call budget. If a lane already timed out on object discovery, discard that generation, remove its scratch, and re-dispatch a narrow fresh closure with the three paths named in the handoff.
