# r90 blocked-review lessons: second-order helpers and bounded ownership
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this as a session-specific companion to `review-finding-red-green-toctou-and-quiet-descendants.md` when a Busdriver iteration has already fixed the obvious retained-bytes/runtime races but fresh review still returns material findings.

## What happened in r90

r90 successfully closed the accepted r89 issues with RED→GREEN evidence:

- BaseException/KeyboardInterrupt cleanup was added to the shared bounded subprocess primitives.
- Several nested Python helper edges switched from private pathname execution to retained authenticated bytes via a stdin loader:
  - deliver → delivery-status entrypoint
  - delivery-status → pr-grind-check
  - finalization-readiness → balance-plan / delivery-status helpers
  - deliver → pr-grind-loop
  - pr-grind-loop → pr-grind-check

Gates were strong (`3928 passed + 14 skipped = 3942 collected`, targeted `1056 passed + 14 skipped`, fixed-point pins, compile/hygiene/secret scan), and the r90 boundary/review views/START+END closures were complete. Fresh review still correctly ended BLOCKED because the enumeration was incomplete.

## Findings that escaped the first repair

Treat these as classes, not one-off filenames:

1. **Every executed support file must be enumerated, not just Python entrypoints.**
   - Remaining delivery-status auxiliary scripts such as lock, litmus/phase0 status, relay-role, and relay-brief can still matter if the authenticated runtime materializes them and later reopens their private paths.
   - Fix pattern: build an inventory of every subprocess edge reachable from the retained entrypoint, then bind each executable support file to retained bytes or another byte-backed descriptor mechanism.

2. **Python stdin loaders do not cover shell helpers.**
   - `pr-grind-check` still wrote/read helpers such as a private runtime guard and `relevant-check-status.sh`; a Bash helper reopened by pathname needs its own byte-backed execution strategy (e.g. verified inherited descriptor / here-doc-like bounded stdin, with argv/diagnostic semantics preserved).
   - RED tests should swap the final private shell path immediately before dispatch and prove forged clean output cannot affect classification.

3. **Do not enumerate only functions named `run_bounded`.**
   - A process-lifetime invariant applies to all subprocess wrappers, including adapter/broker helpers such as `run_git`.
   - Discovery should search for every `Popen`/`run`-like subprocess owner and ask whether BaseException cleanup, pre-reap kill ordering, and bounded wait/join semantics apply.

4. **BaseException cleanup needs an ownership-ended flag.**
   - Even after a pre-reap kill, an interrupt after the main path has called `wait()` can make an outer `except BaseException` try to signal the numeric PGID again.
   - Fix pattern: track whether group cleanup was issued and whether the direct child has been reaped; after ownership ends, skip further PID/PGID signalling and only do bounded local cleanup.
   - Add a regression that injects an interrupt after fake `wait()` sets `returncode`.

5. **Authentication reads must be bounded before digesting.**
   - A same-UID replacement can force a large allocation if code calls `read_bytes()` before checking size/digest.
   - Use the bounded descriptor-reader pattern: lstat/open/no-follow, size cap, bounded read, closing metadata/name validation, then digest comparison.

6. **Credential propagation is a reviewed invariant, not just a security hazard.**
   - If production policy requires live PR-grind checks in token-only environments, stripping the approved GitHub credential variables from a nested checker may make the system fail closed even when it should be able to verify.
   - Review the expected credential model (root-owned `gh` vs token-only) and encode it in focused tests instead of silently treating either behavior as acceptable.

## Read-only adjudication probes that settle reviewer disagreement

When one reviewer calls these paths CLEAN, do not resolve the disagreement from prose. Run temporary/read-only probes against the frozen bytes and report sanitized booleans only.

### Broker `run_git`: split BaseException, quiet-success, and stale-PGID REDs

`run_git` is not discovered by an enumeration limited to functions named `run_bounded`. Give it three focused contracts:

1. **BaseException ownership:** launch a real shell leader plus a quiet descendant, proxy the first `wait()` to raise `KeyboardInterrupt` after both PID markers exist, require reraising, and require both PIDs to disappear. Always kill/reap in the test's `finally` so a RED cannot leak a 300-second process.
2. **Quiet successful descendant:** have the leader run `sleep 300 </dev/null >/dev/null 2>/dev/null &`, record the PID, and exit `0`. Require the ordinary return plus descendant death. A drain-based test alone misses this because every pipe is already closed.
3. **Pre-reap signal canary:** on overflow/lingering-drain paths, record `proc.returncode` at every group signal and require it to still be `None`. A signal after `wait()` publishes a return code is a recycled-PGID window.

Do not replace `run_git` wholesale with a generic wrapper if that loses its descriptor-bound cwd, bytes return type, stderr-refusal semantics, or Git-specific deadline. Reuse/adapt the non-reaping exit-watch lifecycle while preserving those contracts.

### Shared bounded runner: interrupt after reaping, not only during polling

The existing pre-reap BaseException regression is insufficient. Parameterize over every shared copy, fake an observed exit, let `wait()` set `returncode = 0`, then inject `KeyboardInterrupt` from `_bounded_result` (or a post-wait drain join). Record `returncode` at each `_kill_bounded_group` call. The expected signal phases are only `[None]`; `[None, 0]` proves the outer BaseException handler re-signalled after ownership ended.

The repair needs explicit lifecycle state (group cleanup issued / leader reaped / ownership ended). After ownership ends, continue bounded local pipe/thread cleanup but never signal the numeric PID/PGID again. The fact that the original group was already killed reduces orphan risk; it does not make a later signal to an unrelated recycled identity safe.

### Authenticated ingress: enumerate consumers, not helper names

A contract that discovers only `_read_authenticated*` definitions can pass while differently named consumers still call `Path.read_bytes()` before digesting. Include the reachable consumers themselves, such as delivery-runtime materialization, PR-grind bundle construction, plugin helper validation, and status resolver validation.

For each consumer, use a sparse file one byte over the established `MAX_AUTHENTICATED_HELPER_BYTES` limit and make `Path.read_bytes()` on that path a fail sentinel. Require the consumer's native refusal channel before the sentinel. Pair this with the existing descriptor-reader tests for exact-limit success, growth, replacement, link count, closing metadata/name validation, and digest. A static inventory should reject new direct read-all calls in digest-bearing production consumers, while separately classifying helpers proven unreachable behind a fixed production blocker.

### Token-only PR-grind: test the real retained child boundary

If token-only GitHub authentication is supported by the parent and checker, execute minimal authenticated retained loop bytes through the real bounded child. Emit only presence booleans for `GH_TOKEN`, `GITHUB_TOKEN`, and `GH_ENTERPRISE_TOKEN`; also assert unrelated secrets and non-approved credential spellings remain absent. Capturing an environment-builder return is weaker because `Popen(env=...)` is the boundary that replaces the child's environment.

Keep ordinary `safe_git_env()` credential-free. If the behavior is accepted, use a dedicated PR-grind environment that adds only the approved GitHub variables after loop/checker authentication. This broadens the credential-bearing trusted Python surface, so retain exact-byte execution, closure authentication, output bounds, and redaction. If policy instead mandates disk-backed/root-owned `gh` auth only, remove contradictory token-support behavior and tests rather than silently stripping tokens at one nested hop.

## r91-style adjudication checklist

Before patching the next iteration:

- From the frozen report, create one RED per accepted edge:
  - remaining delivery-status auxiliary support-file substitution;
  - `pr-grind-check` private runtime guard substitution;
  - `pr-grind-check` shell relevant-status substitution;
  - broker/adapter `run_git` BaseException, quiet-success, and pre-reap behavior;
  - post-reap BaseException PGID reuse guard across every shared copy;
  - unbounded authenticated reads at both named readers and differently named consumers;
  - token-only PR-grind credential propagation if accepted as required behavior.
- Ensure each RED observes a real attacker effect (marker, forged clean JSON/counts, surviving process group, attempted read-all allocation, or missing credential at the actual child), not a mocked success return.
- Run REDs with cache/bytecode disabled and keep all probe artifacts in temporary directories outside the repository.
- Only after RED, apply minimal fixes and refresh trusted-runtime pins to fixed point.
- Run broad gates again, then create a new immutable boundary; never repair the already-reviewed BLOCKED boundary.

## Review-process lesson

A complete gate pass and immutable closure chain do not imply deliverability. If any fresh reviewer reports material findings, seal that exact iteration BLOCKED with the review reports and closures, then move the findings into the next mutable iteration. One CLEAN reviewer does not override BLOCKED findings from another lane.
