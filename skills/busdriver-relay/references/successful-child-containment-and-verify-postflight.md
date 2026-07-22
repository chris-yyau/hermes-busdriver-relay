# Successful-child containment and verify-only postflight probes
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use these probes when reviewing Relay launchers, gates, or verifier dispatchers. Timeout-only process-group tests are insufficient.

## Normal-success descendant escape

A direct worker can spawn a descendant that:

1. creates a new session (`setsid` / `start_new_session=True`),
2. redirects stdin/stdout/stderr to `/dev/null`,
3. waits until postflight is likely complete,
4. writes to the repo or an authority marker,
5. lets the direct child exit `0` immediately.

If the launcher accepts the direct child's success, runs postflight, and releases its shared lock before the delayed write, its final snapshot is not stable. Killing only the original process group does not contain a descendant that created a new session.

### Required invariant

Do not publish success or release the mutation/draft lock until the entire worker containment domain is terminated and a fresh repository snapshot is stable. Prefer an OS containment primitive that survives session/group changes, or run untrusted work in a disposable private worktree and apply reviewed bytes only from the parent after teardown.

A useful lower-level regression still targets a same-process-group descendant: have the direct child wait for a TERM-ignoring grandchild to become ready, then exit `0`; the grandchild closes inherited pipes and schedules a delayed write. The wrapper must detect the live group on the normal-success path, TERM/KILL/drain it before returning, suppress the delayed write, and fail closed rather than letting postflight report success. Keep this test separate from the timeout case and rerun it to expose readiness races. Passing it hardens a fixture lifecycle primitive only—it does **not** prove production containment against `setsid()` escape, so production dispatch must remain blocked until a stronger OS boundary exists.

### Regression shape

Exercise both worker and postflight-verifier paths:

- direct child exits `0` quickly;
- escaped descendant closes inherited pipes and performs a delayed write;
- command must block or contain/reap the descendant;
- no write may appear after the final report or lock release;
- test normal success separately from timeout/termination paths.

### Evidence and repetition discipline

Keep the claim no broader than the probe. `start_new_session=True` on the direct worker creates a process-group/session boundary for that worker; a grandchild that merely inherits that group proves TERM/KILL/drain behavior for the original group. It does **not** exercise a grandchild calling `setsid()` and must never be reported as production containment against session escape.

For repeated race probes:

1. Discover or collect the exact pytest node ID before building the repetition driver. A misspelled or renamed node returning pytest exit `4` is harness failure, not product evidence.
2. Prefer a small external Python driver that runs the exact node in fresh isolated `HOME`, `TMPDIR`, XDG, and Git-config environments, records every subprocess return code, and asserts the expected pass marker. This avoids ambiguous shell-wrapper status and leaves the frozen candidate untouched.
3. Repeat the normal-success lingering-descendant case enough times to expose readiness races, and run the timeout case separately. Record the expected wrapper semantics (for example, fail-closed `125` after direct-child `0`, versus timeout `124`) in the evidence summary.
4. For the complete suite, print and preserve an explicit internal pytest return code in addition to the pass count. Do not infer exit `0` from a summary line alone.
5. If a repetition harness fails before executing the test, correct it and rerun before closure. Never carry an unexecuted or partially executed probe into a `CLEAN` verdict.

Reserve tool/call budget for the repeated probe, end verifier, immutable-identity comparison, final report write, and report checksum. Passing the full suite does not compensate for missing end-closure evidence.

## Verify-only dispatchers

A command named `verify` must not derive `verified` solely from verifier exit codes when verifiers run in the target repository. A verifier can exit `0` after immediately changing tracked files, index, HEAD, hooks, ignored files, or markers, or after launching a delayed descendant.

Choose one safe contract:

- execute verifiers in an isolated/disposable worktree or read-only sandbox; or
- acquire the same repository-wide shared lock used by draft/finalization operations, contain all descendants, then recompute HEAD/index/tracked/untracked/hooks/markers/ignored state before deciding.

Any unexplained drift or surviving process makes the result blocked, even if every direct verifier returned zero.

### Verify-only regressions

Add zero-exit verifiers that:

- mutate a tracked file immediately;
- change index or HEAD;
- rewrite an authority marker;
- spawn a detached delayed writer with closed pipes.

All must return nonzero/blocked, leave no surviving descendant, and accurately report whether any side effect already occurred.
