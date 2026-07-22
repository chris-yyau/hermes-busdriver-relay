# Operation dispatchability and active-document consistency

Use this when a gated delivery dispatcher exposes an operation in its parser or aggregate capability matrix, but runtime policy still blocks that operation.

## Core invariant

**Parser/executor surface is not dispatchability.** An aggregate row such as `implemented_gated` must not imply that every listed operation can run. Publish operation-specific status and preserve the runtime blocker verbatim, for example:

- `push: policy_blocked:atomic_push_base_binding_unavailable`
- `merge: policy_blocked:atomic_merge_base_binding_unavailable`

Never route around the blocker with direct `git push` or `gh pr merge`.

## TDD consistency pass

1. Add or expand a contract test first; demonstrate RED against the stale surfaces.
2. Audit all active authority surfaces, not only the README:
   - README and current-status page;
   - governing ADRs;
   - integration contract and settling checks;
   - authority map and its skill-reference copy;
   - repository skill and installed/live skill copy;
   - every adapter README for symmetric lanes (for example, audit Pi whenever an OpenCode claim is corrected, and vice versa);
   - machine-readable finalization-contract status output.
3. Rewrite claims such as “executor can perform commit/push/PR/merge” into operation-specific language. Explicitly distinguish exposed parser surfaces from currently dispatchable operations. Likewise distinguish a non-installed harness adapter proof from production worker launch, credential handling, or real-agent smoke proof.
4. Add negative documentation contracts that reject known enabled/verified wording in active docs. Presence-only assertions for blocker tokens are insufficient because the same file can contain both the correct blocker and a contradictory launch instruction.
5. Make status output carry an `operation_statuses` map while retaining any aggregate row needed for schema compatibility.
6. Run the targeted contract to GREEN, then the full contract suite and smoke gate.
7. Any source or documentation edit invalidates the prior frozen digest; create a fresh snapshot and rerun every independent reviewer against that same digest.

### Authority-negative role migrations must close downstream consumers

When a role changes from dispatchable to metadata-only, do not stop at the resolver/status table. Trace every consumer that ingests or republishes the role envelope—delivery status, finalization readiness, briefing/status aggregation, handoff evidence, and their contract fixtures.

- Search production code and tests for positive behavioral claims such as `dispatch_allowed is True` and `programmatic_dispatch_allowed: True`. Keep deliberately hostile/tampering inputs, but require their rejection explicitly.
- Invert the shared ingestion validator at the trust boundary: the accepted production envelope must carry dispatch, mutation, and finalization flags as exact `false` values in both top-level and nested decision objects. A positive dispatch claim is unsafe even when mutation/finalization are false.
- Keep selected-agent/route data as metadata while returning the established non-dispatchable status, blocker, and warning. Do not turn a successfully parsed negative envelope into execution authority.
- Update downstream delivery/readiness tests in the same RED→GREEN slice. Resolver-only focused tests can be green while the full suite still encodes—and production consumers still accept—the old authority contract.
- Fix the shared validator once rather than patching each caller, then reseal the transitive digest graph and rerun the complete affected contract files before the full suite.

## Git-signing-independent test fixtures

Synthetic repositories and production smoke helpers must not inherit a user's global commit-signing requirement. For fixture/setup commits, use an explicit local command override such as:

```text
git -c commit.gpgsign=false commit -m init
```

For a whole test invocation, prefer a temporary `GIT_CONFIG_GLOBAL` containing only `commit.gpgsign=false` and `tag.gpgsign=false`; do not modify the user's global Git configuration. Keep runtime security tests that deliberately scrub `GIT_CONFIG_*` explicit and separate.

## Verification evidence

Record the targeted RED/GREEN result, full-suite count, current operation-status output, frozen manifest hash, binary-diff hash, source-tar hash, candidate tree, and split-commit rehearsal tree. Reviewers must echo and reverify the same hashes at both boundaries.
