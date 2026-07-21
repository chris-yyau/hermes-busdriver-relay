# Relay v2 Settling Checks

This file maps the H1-H13 checklist to the current Hermes Busdriver Relay state after adding the Pi/OpenCode draft adapters, read-only PR-grind readiness checker, gated Delivery Mode dispatcher, durable delivery and mutating-run envelopes, read-only litmus/pre-PR marker freshness status, read-only finalization handoff envelope with machine-readable guardrails, dual-review readiness evidence, advisory pre-PR dual-review evidence classification, embedded read-only agent balance-plan evidence, recursive fail-closed authority hardening, embedded read-only finalization contract-status evidence, and strict delivery-status child-envelope validation in finalization-readiness, plus a read-only ADR 0005/0008 finalization contract status/capability matrix.

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
- Pi/OpenCode adapter contracts exercised only through non-installed test harnesses; production dispatch is `policy_blocked` by `agent_containment_and_credential_broker_unavailable`;
- a read-only PR-grind readiness checker and bounded polling loop for explicit Hermes Delivery Mode;
- a gated delivery dispatcher that emits durable result envelopes for the operations that reach artifact handling, and exposes explicit parser surfaces; operation status is narrower than parser exposure: verifier commands are `policy_blocked` by `verifier_containment_unavailable` before run identity/delivery-status/artifact handling, pre-PR review by `isolated_review_runtime_unavailable` before delivery-status/lock handling, push by `atomic_push_base_binding_unavailable`, PR creation by `atomic_pr_create_binding_unavailable`, and merge by `atomic_merge_base_binding_unavailable`;
- a read-only finalization readiness helper that emits a handoff envelope plus machine-readable remaining finalization guardrails, dual-review readiness evidence, advisory pre-PR dual-review evidence classification, embedded read-only agent balance-plan evidence, embedded finalization contract-status evidence, strict delivery-status child-envelope validation, and recursive authority-positive fail-closed checks but never finalizes or dispatches agents;
- a read-only finalization contract status helper that emits `hermes-busdriver-finalization-contract-status/v0` with `implemented_gated` rows for the deliver executor and mutating run envelope, plus policy-blocked ADR 0005/0006 criteria for programmatic dual-review, marker interop, and autonomous PR-grind fix loops;
- a fixed-blocked production `verify` operation: it returns `verifier_containment_unavailable` immediately after argument parsing — before run identity, delivery-status, and artifact handling — so it launches no caller-supplied verifier and writes no artifact.

The read-only/status relay surface remains complete. Parser/result-envelope surfaces are not dispatchability: production agents, verifier commands, pre-PR review, push, PR creation, and merge remain blocked by `agent_containment_and_credential_broker_unavailable`, `verifier_containment_unavailable`, `isolated_review_runtime_unavailable`, `atomic_push_base_binding_unavailable`, `atomic_pr_create_binding_unavailable`, and `atomic_merge_base_binding_unavailable`. Raw marker writes, deploy/release/publish, and autonomous PR-grind fix loops remain intentionally blocked.

## Checks

| Check | v2 status | Evidence |
|---|---|---|
| H1 standalone dispatcher check | Complete with gated Delivery Mode executor | `hermes-busdriver-agent-draft`, `hermes-busdriver-relay-role`, `hermes-busdriver-delivery-status --relay-role`, `hermes-busdriver-pr-grind-check`, read-only `hermes-busdriver-pr-grind-loop`, and gated `hermes-busdriver-deliver execute` operations run standalone; mutating operations remain per-operation evidence-gated, not standing authority. |
| H2 final result envelope/schema | Complete with gated mutating run envelope | Draft launcher, relay role resolver, delivery-status relay-role and litmus/pre-PR freshness evidence, litmus/pre-PR marker freshness status, PR-grind checker/loop, delivery dispatcher with read-only pr-grind execution plus durable `hermes-busdriver-delivery-run/v0` envelopes and read-only status lookup for the operations that reach artifact handling (production `verify` is fixed-blocked before that point and produces no artifact), gated mutating operations with redacted `hermes-busdriver-mutating-delivery-run/v0` transcripts, delivery-status top-level `read_only: true`, finalization-readiness helper emits JSON schemas including read-only dual-review readiness and advisory pre-PR dual-review evidence classification with recursive authority fail-closed checks plus strict delivery-status child-envelope validation, and finalization-contract-status emits a read-only ADR 0005 capability matrix with ADR 0006 design evidence for the dual-review and marker-interop rows. |
| H3 dirty tree fail-closed | Implemented for draft | Gate preflight blocks dirty repos unless explicitly allowed; finalization still procedural. |
| H4 scope containment | Implemented for draft | Postflight blocks out-of-scope draft changes. |
| H5 gate bypass check | Improved | Draft launchers keep commit/push/PR/merge false. Production agent/verifier dispatch and push/PR-create/merge are fail-closed under the explicit blockers above; no direct-command bypass is allowed. |
| H6 read-only status check | Implemented | Status/runtime/PR-grind readiness probes are read-only; delivery-status advertises the read-only contract at top level for downstream validation. |
| H7 drift invalidation | Improved | Status reports critical Busdriver file hashes and can read-only compare a status-style drift baseline, returning `busdriver_drift.finalization_compatible=false` for missing/invalid/unsupported-schema/drifted baselines while keeping all finalization flags false. Delivery-status and finalization-readiness accept `--drift-baseline`, include Phase-0 drift evidence, and block handoff fail-closed on incompatible baselines. No automatic restore/enable state machine yet. |
| H8 state-dir/plugin-root portability | Partial | Status/gate/smoke accept plugin root and state dir; delivery-status/finalization-readiness/deliver forward the Busdriver state dir to litmus-status; PR-grind checker can use live Busdriver `relevant-check-status.sh`. |
| H9 marker freshness | Improved | Status reports marker metadata; `hermes-busdriver-litmus-status` read-only checks commit litmus and pre-PR review marker freshness against current HEAD / branch diff hash; delivery-status/finalization-readiness include sanitized, normalized/redacted freshness evidence and warn on stale/missing markers only when helper evidence is available and schema-safe; unavailable/malformed/schema-invalid/repo-mismatched/authority-positive/subprocess-failed helper evidence blocks fail-closed; PR-grind checker avoids writing markers and evaluates latest PR HEAD comments/checks. |
| H10 concurrency | Improved | `hermes-busdriver-lock` supports per-repo operations; delivery-status/finalization-readiness now report and block on an active per-repo `finalization` lock without granting finalization authority. |
| H11 external side effects | Partial | Production agent/verifier execution and push/PR-create/merge side effects are policy-blocked; explicit user intent and clean checks do not override the blockers. |
| H12 sensitive payload | Improved | Delivery redacts common secret shapes from helper-error tails, persisted artifacts, and copied litmus summary primitives; finalization/status paths still avoid advisory/model payloads. Redaction of verifier commands and verifier stdout/stderr tails is exercised only through the non-installed contract harness, which injects verifier dispatch: production `verify` is fixed-blocked before any verifier runs, so it emits no verifier output and no artifact. |
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

The `verify` invocation below is a **parser surface only**. It returns the early blocked result
(`status: blocked`, `reason: verifier_containment_unavailable`, exit code 2) immediately after
argument parsing: the `--verifier` command is never launched, `repo`/`delivery_status` are never
probed, and `run_artifact_path` is `null` because no artifact is written. A later `--mode status`
lookup for `local-verify-001` therefore finds nothing to return — the `status` example below uses
the artifact-producing `pr-grind` run id instead.

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
  --run-id pr-grind-001 \
  --pretty
```

`status` mode is read-only and currently fixed-blocked across processes. Its durable-envelope and
artifact-lookup semantics apply only to operations that actually reach artifact handling — a run id
from a fixed early-blocked operation such as production `verify` has no artifact to look up at all.
Result artifacts use a process-scoped HMAC writer capability that is never written to disk or inherited by exec children. Outside the writing process no valid MAC can be established over the artifact bytes, so a later CLI process cannot distinguish an authentic artifact from same-UID filesystem data it did not write: unverifiable bytes therefore select only `run_not_found`, never a writer-authenticated result. `--mode status` accepts only same-process artifacts authenticated by a still-live capability. The failed lookup does not probe or mutate the target repo. Delivery-status emits a top-level `read_only: true` marker, and finalization-readiness refuses malformed delivery-status child envelopes with `delivery_status_schema_invalid` before using their readiness evidence. `execute --operation pr-grind` is also non-finalizing: it wraps the read-only bounded PR-grind loop, validates the loop envelope schema/version/read-only flag and nested fail-closed authority flags before accepting clean, embeds the loop result in a durable run artifact, returns nonzero unless the latest PR HEAD is clean by a safe loop envelope, and never fixes, pushes, writes Busdriver markers, or merges.

```bash
scripts/hermes-busdriver-litmus-status \
  --repo /path/to/repo \
  --base-ref origin/main \
  --state-dir-name .claude \
  --pretty
```

The litmus-status helper only reports whether existing Busdriver markers match current Busdriver gate semantics. It computes PR hashes with the same plain `git diff` semantics as Busdriver's PR gate, fails closed on ambient `GIT_DIFF_OPTS` instead of hashing a divergent diff, fails closed instead of executing external diff/textconv/diff-driver configuration or hashing through `.gitattributes`, `$GIT_DIR/info/attributes`, or `core.attributesFile` diff selection, refuses to follow state-dir symlink components or marker symlinks and refuses non-regular/oversized marker files, fingerprints marker text / summarizes JSON fields instead of echoing raw contents, requires fresh timestamped PR artifacts, treats empty PR diffs as unavailable, treats commit markers older than the current HEAD timestamp as stale, and keeps finalization, commit, push, PR, merge, and marker-write authority false.

## Finalization contract posture

`hermes-busdriver-finalization-readiness` exposes `finalization_guardrails.remaining_work` with guardrail schema/version/read-only metadata and repeats it in the handoff envelope. `hermes-busdriver-finalization-contract-status` reports the same IDs while distinguishing implemented gated surfaces from still-blocked ones: `deliver-mutating-executor` and `mutating-final-result-envelope` are `implemented_gated`; programmatic dual-review execution, autonomous PR-grind fix/push/re-poll, and Busdriver marker interop/writes remain `policy_blocked`. ADR 0006 remains a non-mutating design/spike pointer for dual-review and marker-interop contracts only; it does not implement reviewer dispatch or marker trust semantics.

- implemented gated aggregate surface: `hermes-busdriver-deliver` exposes explicit `pre-pr-review`/`commit`/`push`/`pr-create`/`merge` parser/result-envelope operations; only an operation that passes its early blocker may reach finalization lock, fresh evidence, and redacted side-effect transcripts. Operation-specific status marks pre-PR review `policy_blocked:isolated_review_runtime_unavailable`, push `policy_blocked:atomic_push_base_binding_unavailable`, and merge `policy_blocked:atomic_merge_base_binding_unavailable`;
- implemented gated: durable `hermes-busdriver-mutating-delivery-run/v0` transcript envelope;
- still blocked: programmatic litmus/pre-PR dual-review execution;
- still blocked: autonomous PR-grind dispatcher loop that invents fixes or bypasses gated draft adapters;
- still blocked: raw Busdriver marker interop/writes. The production `pre-pr-review` path does not invoke the dormant Busdriver-owned trusted-writer adapter.
