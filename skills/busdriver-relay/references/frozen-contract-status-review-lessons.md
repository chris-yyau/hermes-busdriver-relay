# Frozen tests/contracts/docs/status review lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference for an independent, read-only review of a dirty frozen snapshot, especially when adapter promotion, trusted runtimes, role metadata, and documentation claims changed together.

## Snapshot boundary protocol

1. Read the snapshot descriptor and identify its exact canonicalization algorithm before reviewing.
2. At the start, independently verify every component: branch, HEAD, base ref, binary diff byte size/hash, the complete untracked-file set, and every untracked file size/hash.
3. Recompute the descriptor digest from canonical compact JSON (`sort_keys=True`, separators `(',', ':')`) with the `snapshot_sha256` field omitted when the descriptor uses `hermes-dirty-snapshot/v0`.
4. Run all reproductions in temporary directories outside the reviewed worktree. Disable bytecode/cache writes and optional Git locks.
5. Recompute the same component and canonical descriptor hashes at the end. If anything changed, stop and report drift rather than publishing findings against a mixed snapshot.
6. If a tool ceiling prevents the ending recomputation, label the review incomplete; do not claim frozen-snapshot PASS.

## Build a behavior-to-contract matrix

For each added or modified behavior, record:

- production entrypoint and exact branch;
- positive test proving the intended success path;
- negative tests for malformed, missing, timeout, digest mismatch, symlink, authority-positive, scope mismatch, stale artifact, and boundary-size cases as applicable;
- whether the test executes production code or swaps out the security boundary;
- documentation/status claims that depend on that proof.

A green full suite does not fill a missing row. Test names and historical pass counts are not proof of the uncovered branch.

## Fake-harness fidelity checks

Inspect dependency injection before trusting adapter tests. A harness that replaces `trusted_*_executable`, package-tree hashing, private-home construction, or child-environment creation proves artifact/gate semantics only; it does not prove production startup integrity.

Require direct production negative tests for:

- exact executable path and digest mismatch;
- executable/package symlinks and added symlink tree entries;
- empty, unreadable, or partially replaced package trees;
- child process not starting after authentication failure;
- private auth/config copying through symlinked parents;
- stale artifacts and malformed/oversized result files.

Label fixture-only proof explicitly so it cannot be promoted into a production-ready claim.

## Trusted-runtime consumer audit

Do not stop at checking that manifest values equal embedded constants. Search every subprocess consumer.

- Every trusted executable invocation must use the authenticated absolute path, not a bare command name.
- Compare the manifest path with what the supposedly safe `PATH` resolves. A fixed PATH can still select a different binary than the manifest pin.
- Include read-only decision inputs such as remote-head lookup, config inspection, plugin archive/materialization, and scope reconciliation; untrusted reads can authorize later mutations.
- A promoted adapter must itself appear in the trusted-runtime contract, or status must remain non-dispatchable.

Suggested contract: intercept subprocess argv for every security-sensitive helper and assert the first element is the digest-verified absolute path; on mismatch, assert no subprocess starts.

## Status and relay-role fail-closed rules

Resolver-ready is not dispatchable. For implementation roles, dispatch requires explicit, correctly typed, mutually consistent metadata:

- `programmatic_dispatch_allowed=true`;
- `adapter_verified=true`;
- present proof identity/digest;
- no `dispatch_blocker`;
- non-degraded selected agent.

Never default missing dispatch metadata to true. Reject missing, false, or malformed `adapter_verified`, and reject combinations such as `adapter_verified=false` with `programmatic_dispatch_allowed=true`. Add fake-status tests for every inconsistent combination and require `dispatch_allowed=false`.

Static prose such as “real smoke verified” is not live proof. If the wrapper or authenticated runtime is missing/tampered, status must demote the role automatically or expose that the field is historical rather than runtime-verified.

## Boundary tests that catch real loopholes

### Capped ignored-file baselines

Any scan limit must be authenticated in the baseline and fail closed on truncation. Test `limit + 1` ignored files, mutate the omitted file, and add a lexically late ignored file. A postflight pass in either case is a security bug. Prefer hashing all entries or storing count plus an explicit truncation blocker.

### Glob semantics

Use one shared segment-aware matcher across the outer gate and every adapter. Contract-test a shared matrix:

- `src/*` rejects `src/nested/file`;
- `src/**` accepts nested files;
- `?` never crosses `/`;
- include/exclude precedence is identical;
- absolute paths, `..`, backslashes, and root-level files behave identically.

Python `fnmatch` permits `*` to cross `/`; do not mix it with a matcher where `*` is single-segment.

## Hostile artifact ingestion

Treat every agent-written result as a hostile filesystem object, not merely hostile JSON. `exists() -> stat() -> read_text()` is insufficient: it follows symlinks, can block on FIFOs/devices, permits unbounded reads, and has replacement races. Open once with `O_NOFOLLOW` (plus nonblocking behavior where needed), require a regular file via `fstat`, enforce the byte limit while reading the same fd, and parse only the captured bytes. Repeat this check at the parent launcher; a hardened adapter is defeated if its caller reopens the artifact unsafely. Never overwrite an invalid child-controlled result pathname during error handling.

Probe symlink-to-valid-JSON, symlink-to-sensitive JSON, FIFO, oversized content, replacement races, and parent-report redaction for every promoted adapter.

## Hermetic Git test execution

Run contract tests first under the ordinary caller environment, then isolate global/system Git configuration when failures indicate inherited signing, hooks, helpers, or aliases. A sanitized rerun can distinguish production regressions from harness contamination, but it does not erase the original failure: report both totals and require test fixtures to use isolated `HOME`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, and explicit signing disablement. Compare base/candidate test inventories and map removed test functions to replacement contracts; a larger final count alone does not prove no deletion-to-green.

## Docs and executable-contract consistency

Cross-check README, CURRENT_STATUS, ADR status/context, repo SKILL.md, current references, CLI parser choices, and tests. Dispatchability is an implementation fact: if production categorically returns an atomic-binding or capability-unavailable blocker for push, PR creation, or merge, every operator-facing source must call that surface present-but-non-dispatchable. Fresh evidence cannot unlock a primitive the implementation does not possess.

Actionable stale-claim patterns include:

- one paragraph says an adapter is verified while a later operational section still calls it a scaffold;
- a reference says both programmatic and non-programmatic;
- docs recommend a CLI mode that the downstream production parser rejects;
- a fixture supports modes that production removed, masking an unreachable public option;
- historical evidence is presented without a date or `superseded` label.

Prefer one machine-readable adapter-status source and docs consistency tests. Keep historical lessons, but move them under dated/superseded headings so they are not mistaken for current instructions.

## Reporting

Report only actionable findings, ordered by severity. Each finding should include:

- production `file:line` evidence;
- missing or weak test `file:line` evidence;
- a concrete negative/positive test to add;
- a reproduction result when it can be obtained outside the frozen worktree.

If clean, state PASS explicitly. Otherwise do not bury the findings under a long activity narrative.
