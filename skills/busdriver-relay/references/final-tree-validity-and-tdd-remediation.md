# Final-tree validity triage and TDD remediation
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this when reviewing security or delivery findings produced from a stacked series of commits. The unit of truth is the immutable final candidate, while intermediate commits remain relevant for attribution and packaging quality.

## 1. Anchor the review

1. Record the exact target SHA and initial `git status --short` before tests or inspection.
2. Map each named slice to its SHA, parent, changed paths, and claimed capability.
3. Read final-tree source first. Use slice diffs and blame only to determine when a defect appeared or was repaired.
4. If unrelated concurrent edits appear later, do not revert them. Record that the tree changed, prove the reviewed paths still match the target, and qualify any tests that could have observed the concurrent files.

## 2. Classify each finding

Use one mutually exclusive primary status:

- `CONFIRMED_FINAL`: the final candidate still has the behavior or contract defect.
- `RESOLVED_LATER`: the defect was real in an earlier slice and a later commit changed production behavior.
- `FALSE_POSITIVE`: the alleged failure mode is inconsistent with the actual control flow or platform semantics.
- `TEMPORAL_PACKAGING_ONLY`: the aggregate is safe, but an intermediate slice was not independently green/deployable because code, closure tests, or policy docs were split across commits.

For every row include:

- exact final-tree `file:function:line` evidence;
- exploit/failure preconditions;
- introduction and repair commit when applicable;
- the contract test proving the repair, or the smallest missing RED test;
- the minimal GREEN behavior, without unrelated refactoring.

Do not call a finding fixed merely because a test exists. Trace the final control flow and verify the test exercises the active production path rather than dormant code behind an early blocker.

## 3. Important semantic checks

### Command completion is not effect completion

A timeout or nonzero wrapper result does not prove a mutation failed. For compare-and-swap publication, classify the authoritative postcondition:

- target equals candidate: effect completed, possibly unattributed or command-unconfirmed;
- target equals expected old value: no effect;
- target is another value: concurrent drift/reconciliation;
- target cannot be read: outcome unknown, never fabricate the old value.

The RED test should make the effect land and then make the command wrapper report failure. GREEN is a postcondition state machine, not a broader retry mechanism.

### Fail-closed authentication is not durable retrieval

A process-scoped HMAC key can correctly reject forged or cross-process bytes while still failing a claimed durable handoff. Classify these separately:

- no MAC bypass may be a valid fail-closed security result;
- inability of a fresh process to authenticate a genuine prior artifact is a capability/contract defect if the interface claims durable status or run-id handoff.

A real durable design needs a trusted signer/broker or non-exportable private key plus authenticated monotonic freshness. A same-UID readable key file does not solve a same-UID forgery threat.

### Process-group lifecycle claims need reap-order proof

Before reporting PID reuse, reconstruct the exact order of exit observation, group signals, and `waitpid`/`Popen.wait`:

- an exit watcher that observes without reaping keeps the numeric PID reserved;
- `TimeoutExpired` means the child was not reaped by that wait;
- signaling before the first successful reap does not create a PID-reuse window;
- a `returncode is None` guard in exception cleanup prevents post-reap signaling.

Require a deterministic contract that fails if any numeric PGID is signaled after the leader is reaped.

### Required-check inventory has transport and identity dimensions

Review both:

1. **Transport boundary:** invoke trusted `gh` with an allowlisted environment, explicit repository binding, bounded stdout/stderr, timeout, and kill/reap. Ambient `GH_HOST`, `GH_REPO`, config, proxy/CA, and loader variables can redirect or instrument the request.
2. **Policy identity:** GitHub branch protection may expose legacy `contexts[]` and app-bound `checks[]` entries. Canonical comparison must preserve `(context, app_id)` when app identity is part of the lock; comparing names alone can report clean after an app binding changes.

## 4. TDD remediation slices

Prefer vertical trust-boundary slices:

1. transport isolation and bounded capture;
2. policy schema/identity migration;
3. local publication effect reconciliation;
4. durable artifact signer/broker;
5. remote base/ref/PR/merge atomicity.

Do not combine unrelated trust boundaries merely because they share one large file. Conversely, when runtime code, authenticated-boundary closure, global contracts, and policy documentation jointly define one capability, keep internal review commits if useful but ship them through one atomic merge/release gate.

## 5. Verification and report shape

- Run narrow contracts for every resolved or confirmed theme, then the relevant aggregate suite.
- Report passed/skipped/failed counts and whether tests ran against an unchanged target tree.
- Keep the executive result compact: counts by classification, confirmed-final blockers first, then a concise later-resolution table and safe slice grouping.
- Never expose credential values encountered during review; use `[REDACTED]`.
