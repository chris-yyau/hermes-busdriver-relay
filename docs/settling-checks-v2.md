# Relay v2 Settling Checks

This file maps the H1-H13 checklist to the current Hermes Busdriver Relay state after adding the Codex draft launcher, read-only PR-grind readiness checker, verify-only dispatcher, durable delivery run envelopes, read-only litmus/pre-PR marker freshness status, read-only finalization handoff envelope with machine-readable remaining finalization guardrails, dual-review readiness evidence, advisory pre-PR dual-review evidence classification, recursive fail-closed authority hardening, and embedded read-only finalization contract-status evidence, plus a read-only ADR 0005 finalization contract status/capability matrix.

## Current scope

Relay v2 supports:

- read-only Busdriver status/runtime probes, including optional Busdriver drift-baseline comparison;
- read-only litmus/pre-PR marker freshness status for current HEAD and branch diff hashes;
- read-only configurable relay-equivalent reviewer/voice/arbiter/backstop status roles under a separate relay config JSON;
- a read-only relay role resolver that turns one configured equivalent role into a fail-closed dispatcher-facing selection envelope;
- optional relay-role resolution and Busdriver drift-baseline evidence in delivery-status and finalization-readiness handoff envelopes;
- state-dir-aware, normalized/redacted read-only litmus/pre-PR marker freshness evidence in delivery-status and finalization-readiness handoff envelopes;
- advisory pre-PR dual-review evidence classification in finalization-readiness, derived only from sanitized delivery-status litmus summaries and never from raw marker contents;
- Hermes-owned single-flight locks;
- scoped Codex draft runs that stop at `needs_busdriver_review`;
- a read-only PR-grind readiness checker and bounded polling loop for explicit Hermes Delivery Mode;
- a verify/pr-grind delivery dispatcher that emits durable `hermes-busdriver-delivery-run/v0` run envelopes, forwards nested helper timeouts/state-dir inputs, writes Hermes-owned result artifacts, and supports read-only `--mode status --run-id <id>` artifact lookup;
- a read-only finalization readiness helper that emits a handoff envelope plus machine-readable remaining finalization guardrails, dual-review readiness evidence, advisory pre-PR dual-review evidence classification, embedded finalization contract-status evidence, and recursive authority-positive fail-closed checks but never finalizes;
- a read-only finalization contract status helper that emits `hermes-busdriver-finalization-contract-status/v0` with ADR 0005 unlock criteria for each policy-blocked remaining-work item without retiring any item;
- redacted verifier command/output tails in verify-only delivery artifacts.

The read-only/non-mutating relay surface is complete for the current policy scope. It still does **not** provide an autonomous finalization launcher. Commit/PR/merge remains an operator-level Delivery Mode path that must run litmus/pre-PR-equivalent checks and a latest-head pr-grind loop; any scripted mutating finalization executor/envelope, mutating PR-grind fix loop, or marker interop/write path remains intentionally policy-blocked.

## Checks

| Check | v2 status | Evidence |
|---|---|---|
| H1 standalone dispatcher check | Complete for non-mutating relay; finalization policy-blocked | `hermes-busdriver-agent-draft`, `hermes-busdriver-relay-role`, `hermes-busdriver-delivery-status --relay-role`, `hermes-busdriver-pr-grind-check`, and read-only `hermes-busdriver-pr-grind-loop` run standalone; no mutating finalization dispatcher is allowed in the current scope. |
| H2 final result envelope/schema | Complete for non-mutating relay; finalization policy-blocked | Draft launcher, relay role resolver, delivery-status relay-role and litmus/pre-PR freshness evidence, litmus/pre-PR marker freshness status, PR-grind checker/loop, delivery dispatcher with verify and read-only pr-grind execution plus durable `hermes-busdriver-delivery-run/v0` envelopes and read-only status lookup, finalization-readiness helper emits JSON schemas including read-only dual-review readiness and advisory pre-PR dual-review evidence classification with recursive authority fail-closed checks, and finalization-contract-status emits a read-only ADR 0005 capability matrix; no mutating final delivery result envelope is allowed in the current scope. |
| H3 dirty tree fail-closed | Implemented for draft | Gate preflight blocks dirty repos unless explicitly allowed; finalization still procedural. |
| H4 scope containment | Implemented for draft | Postflight blocks out-of-scope draft changes. |
| H5 gate bypass check | Partial | Draft launchers keep commit/push/PR/merge false; Delivery Mode requires litmus/pre-PR plus pr-grind-equivalent checks but is not yet a dedicated launcher. |
| H6 read-only status check | Implemented | Status/runtime/PR-grind readiness probes are read-only. |
| H7 drift invalidation | Improved | Status reports critical Busdriver file hashes and can read-only compare a status-style drift baseline, returning `busdriver_drift.finalization_compatible=false` for missing/invalid/unsupported-schema/drifted baselines while keeping all finalization flags false. Delivery-status and finalization-readiness accept `--drift-baseline`, include Phase-0 drift evidence, and block handoff fail-closed on incompatible baselines. No automatic restore/enable state machine yet. |
| H8 state-dir/plugin-root portability | Partial | Status/gate/smoke accept plugin root and state dir; delivery-status/finalization-readiness/deliver forward the Busdriver state dir to litmus-status; PR-grind checker can use live Busdriver `relevant-check-status.sh`. |
| H9 marker freshness | Improved | Status reports marker metadata; `hermes-busdriver-litmus-status` read-only checks commit litmus and pre-PR review marker freshness against current HEAD / branch diff hash; delivery-status/finalization-readiness include sanitized, normalized/redacted freshness evidence and warn on stale/missing markers only when helper evidence is available and schema-safe; unavailable/malformed/schema-invalid/repo-mismatched/authority-positive/subprocess-failed helper evidence blocks fail-closed; PR-grind checker avoids writing markers and evaluates latest PR HEAD comments/checks. |
| H10 concurrency | Improved | `hermes-busdriver-lock` supports per-repo operations; delivery-status/finalization-readiness now report and block on an active per-repo `finalization` lock without granting finalization authority. |
| H11 external side effects | Partial | Draft paths block side effects; Delivery Mode PR/merge side effects require explicit user intent and clean checks. |
| H12 sensitive payload | Improved | Verify-only delivery redacts common secret shapes from verifier commands, stdout/stderr tails, helper-error tails, persisted artifacts, and copied litmus summary primitives; finalization/status paths still avoid advisory/model payloads. |
| H13 hook-runtime equivalence | Partial | Runtime check proves Hermes is not inside Claude hooks; draft gate invokes explicit equivalents and refuses finalization; status reports configurable relay equivalents from relay config without claiming Busdriver-native Claude runtime authority, and finalization-readiness surfaces litmus/pre-PR dual-review role readiness as advisory evidence with dispatch/programmatic execution disabled. |

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
  --relay-role relay.pr.backstop \
  --relay-config /path/to/hermes-relay-config.json \
  --drift-baseline /path/to/busdriver-status-baseline.json \
  --pr 123 \
  --pretty
```

```bash
scripts/hermes-busdriver-finalization-contract-status --pretty
```

```bash
scripts/hermes-busdriver-delivery-status \
  --repo /path/to/repo \
  --plugin-root /path/to/busdriver \
  --relay-role relay.pr.backstop \
  --relay-config /path/to/hermes-relay-config.json \
  --drift-baseline /path/to/busdriver-status-baseline.json \
  --pretty
```

```bash
scripts/hermes-busdriver-relay-role \
  --role relay.pr.backstop \
  --relay-config /path/to/hermes-relay-config.json \
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

```bash
scripts/hermes-busdriver-deliver \
  --repo /path/to/repo \
  --plugin-root /path/to/busdriver \
  --mode execute \
  --operation verify \
  --run-id local-verify-001 \
  --verifier 'tests=uvx --from pytest pytest -q' \
  --pretty

scripts/hermes-busdriver-deliver \
  --repo /path/to/repo \
  --plugin-root /path/to/busdriver \
  --mode execute \
  --operation pr-grind \
  --pr 123 \
  --run-id pr-grind-001 \
  --max-wait-seconds 300 \
  --poll-interval 30 \
  --pretty

scripts/hermes-busdriver-deliver \
  --mode status \
  --run-id local-verify-001 \
  --pretty
```

`status` mode is read-only: it searches Hermes-owned delivery-run artifacts by `run_id`, returns the latest valid matching artifact path and sanitized metadata as `status_lookup` evidence, preserves that artifact's repo/PR identity in the status envelope, and does not probe or mutate the target repo. `execute --operation pr-grind` is also non-finalizing: it wraps the read-only bounded PR-grind loop, validates the loop envelope schema/version/read-only flag and nested fail-closed authority flags before accepting clean, embeds the loop result in a durable run artifact, returns nonzero unless the latest PR HEAD is clean by a safe loop envelope, and never fixes, pushes, writes Busdriver markers, or merges.

```bash
scripts/hermes-busdriver-litmus-status \
  --repo /path/to/repo \
  --base-ref origin/main \
  --state-dir-name .claude \
  --pretty
```

The litmus-status helper only reports whether existing Busdriver markers match current Busdriver gate semantics. It computes PR hashes with the same plain `git diff` semantics as Busdriver's PR gate, fails closed on ambient `GIT_DIFF_OPTS` instead of hashing a divergent diff, fails closed instead of executing external diff/textconv/diff-driver configuration or hashing through `.gitattributes`, `$GIT_DIR/info/attributes`, or `core.attributesFile` diff selection, refuses to follow state-dir symlink components or marker symlinks and refuses non-regular/oversized marker files, fingerprints marker text / summarizes JSON fields instead of echoing raw contents, requires fresh timestamped PR artifacts, treats empty PR diffs as unavailable, treats commit markers older than the current HEAD timestamp as stale, and keeps finalization, commit, push, PR, merge, and marker-write authority false.

## Policy-blocked finalization surfaces

`hermes-busdriver-finalization-readiness` exposes this list as `finalization_guardrails.remaining_work` with guardrail schema/version/read-only metadata and repeats it in the handoff envelope so downstream status tooling can distinguish read-only handoff readiness from unsupported mutating/raw-exec operations and intentionally unavailable finalization authority. `hermes-busdriver-finalization-contract-status` reports the same remaining-work IDs as `status=policy_blocked` and records the missing ADR 0005 unlock criteria (Busdriver-approved seams, mutating schemas, hook-runtime/equivalent proof, programmatic-review contracts, PR-grind mutation contracts, and marker ownership/atomicity/trust semantics) without retiring any item. These items are not the next safe mutating implementation slice; they require a stronger Busdriver-approved integration surface, explicit approval, and the ADR 0005 finalization authority integration contract before any mutating implementation work begins.

- `hermes-busdriver-deliver` commit/push/PR/merge executor mode, if ever approved;
- mutating final delivery result envelope;
- programmatic litmus/pre-PR dual-review equivalent;
- mutating pr-grind dispatcher loop with fix rounds and push/re-poll integration; the current read-only loop and delivery-dispatcher wrapper cover max-wait/max-polls, policy-gap bails, ack-ledger delegation, latest-head re-poll, and durable run artifacts without fixing or merging;
- safe Busdriver marker interop only if Busdriver defines an integration surface.
