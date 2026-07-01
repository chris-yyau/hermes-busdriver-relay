# ADR 0006 - Programmatic Dual-Review Marker Interop

## Status

Accepted non-mutating design/spike contract. This ADR does not grant finalization authority and adds no executor, dispatcher, marker writer, commit, push, PR, merge, deploy, release, or publish path.

Current status has no finalization, dispatch, marker-write, commit, push, PR, merge, deploy, release, or publish authority. All authority false until a later Busdriver-approved implementation is separately contracted and tested.

## Context

ADR 0005 leaves `programmatic-litmus-pre-pr-dual-review` and `busdriver-marker-interop` as `policy_blocked`. Hermes can observe read-only litmus/pre-PR status today, but it cannot satisfy Busdriver gates by forging review output or marker files.

This ADR frames the safe contract for a future spike: Hermes may request and observe Busdriver-native litmus PR mode, a Codex lead review lane, and a read-only backstop without bypassing Claude/Busdriver trusted writers.

## Decision

Hermes may design a read-only invocation seam that records requests, observations, and artifacts for:

- `relay.litmus.reviewer`;
- `relay.pr.lead`;
- `relay.pr.backstop`.

Reviewer independence must be explicit. The same-agent policy must prevent one model/provider/session from satisfying independent roles unless Busdriver defines that as acceptable. Evidence must record model/provider/session separation, conflict rules, and any reason independence is unavailable.

The evidence schema for `hermes-busdriver-dual-review-execution/v0` must include input digest, reviewed diff hash, reviewer verdicts, findings, confidence/limitations, timestamps/freshness, data egress/redaction, and artifact refs.

Aggregation must distinguish pass, actionable findings, unavailable, stale, malformed, and policy_blocked. Any missing, ambiguous, contradictory, stale, malformed, or untrusted evidence keeps all authority false.

## Busdriver 1.74.0 Evidence

Busdriver `pre-pr-gate.sh` blocks `gh pr create` unless `pr-review-passed.local` equals the current `base...HEAD` diff hash and both `pr-codex-lead.local.json` and `pr-backstop-verdict.local.json` carry `status: PASS` for that hash. `litmus-passed.local` is intentionally not accepted for PR creation.

Busdriver `run-review-loop.sh` writes Codex lead evidence only inline on real Codex PASS, with marker writes behind explicit `--write-backstop-verdict` and `--write-pr-marker` paths. `pr-security-backstop` is read-only and emits strict JSON; `pr-backstop-verdict.schema.json` uses `additionalProperties=false`. This evidence does not grant Hermes authority to write markers or execute finalization.

## Marker Writer and Provenance

Hermes must not write `pr-review-passed.local` or any Busdriver marker. Marker interop requires `hermes-busdriver-marker-interop/v0` and an explicit Busdriver-owned contract for:

- Busdriver-approved writer identity;
- Busdriver trusted writer commands;
- atomicity and fsync/rename behavior;
- path/symlink safety;
- audit records;
- freshness windows;
- trust semantics for which gates may consume the marker.

Until Busdriver defines that surface, Hermes may only report normalized marker status. It must not create, update, delete, consume-as-authority, or forge marker files.

## Non-Goals

- no mutating executor;
- no raw codex exec;
- no marker forging;
- no MCP/plugin graph replication;
- no deploy/release/publish automation;
- no non-Codex mutating adapter enablement.

## Staged Unlock Plan

1. read-only probe: capture request/observation artifacts and keep every authority flag false.
2. Busdriver-approved invocation seam: only invoke a Busdriver-defined surface and prove role independence, data boundaries, freshness, and fail-closed aggregation in contract tests.
3. marker interop only if Busdriver defines it: implement the approved writer/provenance contract and keep authority false until the corresponding contract is implemented and tested.

This ADR only frames the contract/spike. It does not implement the seam.
