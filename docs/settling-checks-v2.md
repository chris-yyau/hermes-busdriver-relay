# Relay v2 Settling Checks

This file maps the H1-H13 checklist to the current Hermes Busdriver Relay state after adding the Codex draft launcher, read-only PR-grind readiness checker, verify-only dispatcher, and read-only finalization handoff envelope.

## Current scope

Relay v2 supports:

- read-only Busdriver status/runtime probes, including optional Busdriver drift-baseline comparison;
- Hermes-owned single-flight locks;
- scoped Codex draft runs that stop at `needs_busdriver_review`;
- a read-only PR-grind readiness checker and bounded polling loop for explicit Hermes Delivery Mode;
- a read-only finalization readiness helper that emits a handoff envelope but never finalizes;
- redacted verifier command/output tails in verify-only delivery artifacts.

It still does **not** provide an autonomous finalization launcher. Commit/PR/merge remains an operator-level Delivery Mode path that must run litmus/pre-PR-equivalent checks and a latest-head pr-grind loop.

## Checks

| Check | v2 status | Evidence |
|---|---|---|
| H1 standalone dispatcher check | Partial | `hermes-busdriver-agent-draft`, `hermes-busdriver-pr-grind-check`, and read-only `hermes-busdriver-pr-grind-loop` run standalone; no mutating finalization dispatcher yet. |
| H2 final result envelope/schema | Partial | Draft launcher, PR-grind checker/loop, verify-only dispatcher, and finalization-readiness helper emit JSON schemas; no mutating final delivery result envelope yet. |
| H3 dirty tree fail-closed | Implemented for draft | Gate preflight blocks dirty repos unless explicitly allowed; finalization still procedural. |
| H4 scope containment | Implemented for draft | Postflight blocks out-of-scope draft changes. |
| H5 gate bypass check | Partial | Draft launchers keep commit/push/PR/merge false; Delivery Mode requires litmus/pre-PR plus pr-grind-equivalent checks but is not yet a dedicated launcher. |
| H6 read-only status check | Implemented | Status/runtime/PR-grind readiness probes are read-only. |
| H7 drift invalidation | Improved | Status reports critical Busdriver file hashes and can read-only compare a status-style drift baseline, returning `busdriver_drift.finalization_compatible=false` for missing/invalid/unsupported-schema/drifted baselines while keeping all finalization flags false. No automatic restore/enable state machine yet. |
| H8 state-dir/plugin-root portability | Partial | Status/gate/smoke accept plugin root and state dir; PR-grind checker can use live Busdriver `relevant-check-status.sh`. |
| H9 marker freshness | Partial | Status reports marker metadata; PR-grind checker avoids writing markers and evaluates latest PR HEAD comments/checks. |
| H10 concurrency | Improved | `hermes-busdriver-lock` supports per-repo operations; delivery-status/finalization-readiness now report and block on an active per-repo `finalization` lock without granting finalization authority. |
| H11 external side effects | Partial | Draft paths block side effects; Delivery Mode PR/merge side effects require explicit user intent and clean checks. |
| H12 sensitive payload | Improved | Verify-only delivery redacts common secret shapes from verifier commands, stdout/stderr tails, helper-error tails, and persisted artifacts; finalization/status paths still avoid advisory/model payloads. |
| H13 hook-runtime equivalence | Partial | Runtime check proves Hermes is not inside Claude hooks; draft gate invokes explicit equivalents and refuses finalization. |

## Commands

```bash
uvx --from pytest pytest tests/contract -q
```

```bash
scripts/hermes-busdriver-smoke \
  --plugin-root /path/to/busdriver \
  --pretty
```

```bash
scripts/hermes-busdriver-finalization-readiness \
  --repo /path/to/repo \
  --plugin-root /path/to/busdriver \
  --relay-state-dir /path/to/hermes-relay-state \
  --pr 123 \
  --pretty
```

```bash
scripts/hermes-busdriver-pr-grind-check \
  --repo /path/to/repo \
  --pr 123 \
  --plugin-root /path/to/busdriver \
  --pretty
```

```bash
scripts/hermes-busdriver-pr-grind-loop \
  --repo /path/to/repo \
  --pr 123 \
  --plugin-root /path/to/busdriver \
  --max-wait-seconds 300 \
  --poll-interval 30 \
  --pretty
```

## Remaining finalization work

- `hermes-busdriver-deliver` commit/push/PR/merge executor mode, if ever approved;
- mutating final delivery result envelope;
- programmatic litmus/pre-PR dual-review equivalent;
- mutating pr-grind dispatcher loop with fix rounds and push/re-poll integration; the current read-only loop covers max-wait/max-polls, policy-gap bails, ack-ledger delegation, and latest-head re-poll without fixing or merging;
- safe Busdriver marker interop only if Busdriver defines an integration surface.
