# Hermes Busdriver Relay

Hermes-side relay for the user's Busdriver / Claude Code workflow.

This repository contains **Hermes-owned integration artifacts only**:

- the `busdriver-relay` Hermes skill;
- the Hermes ↔ Busdriver integration contract;
- read-only status tooling;
- contract/smoke tests;
- ADRs for integration decisions.

It is **not** a Busdriver clone and must not vendor Claude plugins, MCP configs, runtime markers, credentials, or Busdriver skill bodies.

## Boundary

```text
Hermes = intake, Phase 0 discovery, JIT source reads, read-only status, non-mutating draft/gate/handoff envelopes, notification
Busdriver/Claude Code = workflow authority, gates, reviews, MCP/plugin routing, execution, commits, PRs, merges
```

Important: Busdriver gates are largely Claude Code hook-runtime behavior. A Hermes bare shell running a Busdriver script does not automatically fire Claude Code hooks.

Current status: the read-only/non-mutating relay surface is complete for the current policy scope, including advisory pre-PR dual-review evidence classification, recursive fail-closed authority checks, machine-readable finalization guardrails whose remaining-work rows report `status=policy_blocked`, a machine-readable finalization contract status/capability matrix, embedded contract-status evidence inside finalization-readiness so downstream consumers do not need a second helper call, a read-only balanced agent work planning envelope for one gated mutating draft lane plus parallel read-only review/status lanes, and strict delivery-status child-envelope validation before finalization-readiness can produce handoff-ready evidence. Delivery-status now emits a top-level `read_only: true` contract marker, and finalization-readiness fails closed with `delivery_status_schema_invalid` when the child envelope has the wrong schema, is not read-only, or carries a non-boolean `ok`. Finalization-readiness embeds balance-plan output as validated advisory evidence only; it still does not dispatch agents or grant programmatic execution authority. Remaining finalization surfaces (mutating commit/push/PR/merge executor/envelope, mutating PR-grind fix loop, programmatic dual review, and marker interop/writes) are intentionally policy-blocked unless a stronger Busdriver-approved integration surface is explicitly added later. ADR 0005 documents the future finalization authority integration contract required before any of those surfaces can be implemented; ADR 0006 is a non-mutating design/spike pointer for programmatic dual-review and marker-interop contracts only.

## Contents

```text
ADRs/                                      Lightweight architecture decisions
ADRs/0005-finalization-authority-integration-contract.md
                                           Future authority/marker interop prerequisite contract
ADRs/0006-programmatic-dual-review-marker-interop.md
                                           Non-mutating programmatic dual-review / marker-interop design spike
docs/CURRENT_STATUS.md                     Current completion/verification state
docs/hermes-busdriver-integration-contract-v2.md
docs/settling-checks-v1.md                 H1-H13 v1 status map
docs/settling-checks-v2.md                 H1-H13 v2 status map
skills/busdriver-relay/SKILL.md            Hermes skill source
skills/busdriver-relay/references/         Skill reference notes
scripts/hermes-busdriver-status            Read-only status probe
scripts/hermes-busdriver-relay-role        Read-only relay equivalent role resolver
scripts/hermes-busdriver-lock              Hermes-owned single-flight lock
scripts/hermes-busdriver-runtime-check     H13 hook-runtime checker
scripts/hermes-busdriver-gate              Equivalent preflight/postflight gate runner
scripts/hermes-busdriver-agent-draft       Generic draft agent launcher
scripts/hermes-busdriver-agent-balance-plan
                                           Read-only balanced agent lane planning envelope
scripts/hermes-busdriver-agent-smoke       Optional real-agent adapter smoke
scripts/hermes-busdriver-delivery-status   Read-only Delivery Mode status envelope
scripts/hermes-busdriver-deliver           Fail-closed verify-only Delivery Mode dispatcher + run status lookup
scripts/hermes-busdriver-litmus-status     Read-only litmus / pre-PR marker freshness status
scripts/hermes-busdriver-finalization-readiness
                                           Read-only finalization handoff envelope
scripts/hermes-busdriver-finalization-contract-status
                                           Read-only ADR 0005 finalization contract/capability matrix
scripts/hermes-busdriver-pr-grind-check    Read-only PR-grind readiness checker
scripts/hermes-busdriver-pr-grind-loop     Read-only bounded PR-grind polling loop
scripts/hermes-busdriver-smoke             Safe smoke runner
tests/contract/                            Contract tests
```

## Commands

### Read-only status

```bash
scripts/hermes-busdriver-status \
  --plugin-root /path/to/busdriver \
  --repo /path/to/repo \
  --drift-baseline /path/to/busdriver-status-baseline.json \
  --pretty
```

The status probe is read-only. It reports Busdriver root/config/hook/entrypoint health, effective routes, critical file hashes, optional Busdriver drift-baseline compatibility, active marker summaries, relay lock state, repo dirty state, and relay-equivalent roles from a separate relay config JSON. It never writes `.claude/`, `.opencode/`, Busdriver, or the target repo. `--drift-baseline` only reads an existing status-style JSON baseline and marks finalization compatibility false on missing/invalid/drifted baselines; it does not create or update baselines.

### Relay equivalent role resolver

```bash
scripts/hermes-busdriver-relay-role \
  --role relay.pr.backstop \
  --relay-config ~/.hermes/busdriver-relay/config.json \
  --pretty
```

This helper is read-only and selects one configured logical Hermes/model agent for a relay role. It is the dispatcher-facing version of the status probe's `relay_equivalent_roles` block: a valid role exits `0` with `status=resolved`, while unknown/degraded/malformed config exits nonzero and keeps `dispatch_allowed=false`, `mutation_allowed=false`, and `finalization_allowed=false`. Use `--list-roles` to inspect supported role names.

### Hermes-owned single-flight lock

```bash
scripts/hermes-busdriver-lock acquire --repo /path/to/repo --operation repo-mutation
scripts/hermes-busdriver-lock status --pretty
scripts/hermes-busdriver-lock release --repo /path/to/repo --operation repo-mutation --token <token>
```

Locks live under `~/.hermes/busdriver-relay/locks` by default, not inside `.claude/` or the target repo. Use operation `finalization` for explicit finalization handoff/Delivery Mode single-flight coordination; read-only delivery-status/finalization-readiness report an active per-repo `finalization` lock as a blocker and still keep all finalization authority false.

### Hook-runtime equivalence check

```bash
scripts/hermes-busdriver-runtime-check \
  --plugin-root /path/to/busdriver \
  --repo /path/to/repo \
  --pretty
```

This is a read-only H13 checker. Normal Hermes execution should report `mutating_launcher_allowed: false`; that is the safe expected result for the current relay. Bare-shell mutating finalization remains policy-blocked unless a stronger Busdriver-approved equivalence/finalization surface is explicitly added later.

### Equivalent gate runner

```bash
BASELINE="$HOME/.hermes/busdriver-relay/gates/example.baseline.json"

scripts/hermes-busdriver-gate preflight \
  --plugin-root /path/to/busdriver \
  --repo /path/to/repo \
  --baseline-file "$BASELINE" \
  --scope-include 'src/**'

# Run Codex in draft mode here. Other agents are intentionally deferred.

scripts/hermes-busdriver-gate postflight \
  --repo /path/to/repo \
  --baseline-file "$BASELINE" \
  --verifier 'tests=uvx --from pytest pytest -q'
```

The gate runner is the first Hermes-side equivalent gate layer. Passing v1 gates allows agent implementation draft work only. It explicitly keeps `commit_allowed`, `push_allowed`, `pr_allowed`, `merge_allowed`, and `deploy_allowed` false.

### Draft agent launcher

```bash
scripts/hermes-busdriver-agent-draft \
  --plugin-root /path/to/busdriver \
  --repo /path/to/repo \
  --agent codex \
  --prompt-file /path/to/task.md \
  --scope-include 'src/**' \
  --verifier 'tests=uvx --from pytest pytest -q' \
  --pretty
```

Currently only `--agent codex` is supported (others temporarily deferred). `noop` and `custom` are for tests.

A successful run means `status=needs_busdriver_review`. It may leave a working-tree diff, but it does not allow commit/push/PR/merge/deploy. It acquires a Hermes-owned `agent-draft` lock, runs gate preflight, runs the agent under a best-effort PATH guard, runs gate postflight, releases the lock, and writes artifacts under `~/.hermes/busdriver-relay/agent-runs/`.

### Balanced agent work plan

```bash
scripts/hermes-busdriver-agent-balance-plan --pretty
```

This read-only helper emits `hermes-busdriver-agent-balance-plan/v0`: a deterministic planning-only envelope for one gated mutating draft implementation lane and parallel read-only review/status lanes. It does not dispatch agents, call Codex or GitHub, mutate repos, write markers, or grant commit/push/PR/merge/deploy/release/publish authority.

### Optional real-agent smoke

```bash
scripts/hermes-busdriver-agent-smoke \
  --plugin-root /path/to/busdriver \
  --agent codex \
  --pretty
```

This creates a throwaway git repo and calls the selected real agent through `hermes-busdriver-agent-draft`. It may consume provider quota/tokens, so it is not part of the default contract test suite. The Codex adapter has been verified with this pattern against a temp repo: Codex created `src/codex_smoke.txt`, postflight scope/verifier passed, and status remained `needs_busdriver_review`.

### Delivery status

```bash
scripts/hermes-busdriver-delivery-status \
  --repo /path/to/repo \
  --plugin-root /path/to/busdriver \
  --relay-role relay.pr.backstop \
  --relay-config ~/.hermes/busdriver-relay/config.json \
  --pr 123 \
  --pretty
```

This read-only Delivery Mode status envelope combines repo state, Busdriver PR-grind source availability, relay capabilities, lock/run summaries, finalization-lock blocking state, optional PR-grind readiness output, sanitized, normalized/redacted, state-dir-aware read-only litmus/pre-PR freshness evidence from `hermes-busdriver-litmus-status` (including sanitized safety booleans for downstream fail-closed summaries), and optional relay-role resolution from `hermes-busdriver-relay-role`. Its top-level envelope includes `read_only: true` so downstream helpers can validate the child contract before trusting any readiness evidence. Stale or missing litmus/pre-PR markers are surfaced as warnings for dirty draft work only when the helper evidence is available and schema-safe; missing helper output, malformed/schema-invalid/read-only-unsafe output, repo identity mismatch, authority-positive flags, or litmus-status subprocess failure all fail closed as blockers. Relay-role resolution is advisory status only, and the envelope still never authorizes or performs commit, push, PR creation, merge, marker writes, or deploy/release actions.

### Delivery dispatcher

```bash
scripts/hermes-busdriver-deliver \
  --repo /path/to/repo \
  --plugin-root /path/to/busdriver \
  --pr 123 \
  --pretty

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

This is the first fail-closed dispatcher envelope for executable Delivery Mode. Default `plan` still only calls the read-only delivery-status probe and keeps finalization disabled. Every result now carries a nested durable `hermes-busdriver-delivery-run/v0` envelope with `run_id`, `phase`, `status`, `reason`, repo/PR identity, authority flags, and artifact references. `execute --operation verify` runs local verifier commands in the target repo without shell expansion, captures bounded/redacted output tails, writes a Hermes-owned JSON artifact under `~/.hermes/busdriver-relay/delivery-runs/` (or `HERMES_BUSDRIVER_DELIVERY_RUNS_DIR`), and returns nonzero if delivery-status or any verifier fails. Delivery wrappers forward nested helper timeouts and `--busdriver-state-dir-name` to delivery-status / litmus-status. `execute --operation pr-grind` requires `--pr`, invokes the read-only bounded PR-grind loop, validates the loop envelope schema/version/read-only flag and fail-closed nested authority flags before accepting `clean`, embeds the loop envelope under `pr_grind_loop`, writes the same Hermes-owned run artifact, and returns nonzero for unsafe loop output / `needs_fix` / `wait` / `blocked`; even a clean loop result only sets dispatcher status `pr_grind_clean` and keeps commit/push/PR/merge/marker-write authority false. `--run-id` may be supplied to give operator/subagent/cron handoff a stable run identity; artifact filenames include that token plus a timestamp/PID for uniqueness. `--mode status --run-id <id>` is a read-only lookup that finds the latest valid persisted artifact with the same run identity and returns its path plus sanitized metadata (`artifact_run`, decision, schema, ok flag) as `status_lookup` evidence without writing a new artifact or probing the target repo; it does not echo verifier output tails from the persisted artifact. Matching artifacts must carry versioned deliver and nested delivery-run envelopes with fail-closed decision/authority metadata, and the returned status envelope preserves the artifact's repo/PR identity. Commit, push, PR creation, merge, marker write, deploy, release, and publish authority remain false in every mode.

### Litmus / pre-PR marker freshness status

```bash
scripts/hermes-busdriver-litmus-status \
  --repo /path/to/repo \
  --base-ref origin/main \
  --state-dir-name .claude \
  --pretty
```

This helper is read-only. It computes the current HEAD and Busdriver-style branch diff hash with the same plain `git diff` semantics as Busdriver's PR gate, then reports whether `.claude/litmus-passed.local`, `.claude/pr-codex-lead.local.json`, `.claude/pr-backstop-verdict.local.json`, and `.claude/pr-review-passed.local` are fresh for that state. If ambient `GIT_DIFF_OPTS`, external diff/textconv/diff-driver configuration, `.gitattributes`, `$GIT_DIR/info/attributes`, or `core.attributesFile` diff selection is present, it fails closed instead of executing or computing a divergent hash. PR artifacts must carry a fresh integer `ts` within the same max-age window as Busdriver's PR gate, empty PR diffs fail closed, state-dir symlink components or marker symlinks are not followed, non-regular or oversized marker files are refused, commit markers must be newer than the current HEAD timestamp, and marker contents / JSON fields are normalized, fingerprinted, or summarized rather than echoed. It never writes markers and never grants commit/push/PR/merge/marker-write authority; stale or missing historical markers are reported as status only.

### Finalization readiness handoff

```bash
scripts/hermes-busdriver-finalization-readiness \
  --repo /path/to/repo \
  --plugin-root /path/to/busdriver \
  --relay-state-dir ~/.hermes/busdriver-relay \
  --relay-role relay.pr.backstop \
  --relay-config ~/.hermes/busdriver-relay/config.json \
  --pr 123 \
  --pretty
```

This helper is read-only and has no execute mode. It combines `hermes-busdriver-delivery-status` with Phase-0 `hermes-busdriver-status` discovery, then emits a `hermes-busdriver-handoff/v0` envelope for Busdriver/Claude or an explicit operator finalizer. Before using the delivery-status child, it strictly validates the child envelope schema, `read_only is True`, and boolean `ok`; invalid child envelopes block readiness with `delivery_status_schema_invalid` instead of producing handoff-ready evidence. The handoff evidence includes delivery-status litmus/pre-PR freshness evidence and a derived `hermes-busdriver-pre-pr-dual-review-evidence/v0` summary. That summary is advisory-only, is computed only from the already-sanitized `delivery_status.litmus_status.summary`, reports `fresh_read_only` only when the sanitized litmus decision is `pr_review_fresh` and all three pre-PR review freshness booleans are true, otherwise reports `commit_litmus_only`, `stale_or_missing`, `blocked`, or `unavailable`, and still keeps dispatch/finalization/marker-write authority false. When `--relay-role` is supplied, the handoff also includes the same fail-closed resolver output from delivery status. It embeds both `finalization_contract_status` and `agent_balance_plan` at the top level and in the handoff evidence: contract-status uses `hermes-busdriver-finalization-contract-status/v0`, while balance-plan uses `hermes-busdriver-agent-balance-plan/v0` as validated advisory lane-policy evidence only. Invalid, non-read-only, authority-positive, timed-out, or subprocess-failed balance-plan evidence blocks readiness fail-closed rather than granting dispatch authority. It also includes a `hermes-busdriver-dual-review-readiness/v0` status envelope for the litmus/pre-PR dual-review gap: programmatic execution remains unsupported here, the needed relay roles are `relay.litmus.reviewer`, `relay.pr.lead`, and `relay.pr.backstop`, configured role routes are surfaced as evidence only, and all dispatch/finalization authority flags remain false. It may report `ready_for_commit_or_pr_handoff` or `ready_for_merge_handoff`, but all commit/push/PR/merge/deploy/marker-write authority remains false.

### Finalization contract status

```bash
scripts/hermes-busdriver-finalization-contract-status --pretty
```

This read-only helper emits `hermes-busdriver-finalization-contract-status/v0`: a machine-readable ADR 0005 status/capability matrix for the same `finalization_guardrails.remaining_work` IDs surfaced by finalization-readiness. It keeps legacy `contract_adr` compatibility while also exposing `contract_adrs` and `related_design_adrs`, including ADR 0006 as the non-mutating design/spike pointer for `programmatic-litmus-pre-pr-dual-review` and `busdriver-marker-interop`. Each row remains `status=policy_blocked`, `retired=false`, and `capability_allowed=false`, with missing unlock criteria such as Busdriver-approved seams, mutating schemas, hook-runtime/equivalent proof, programmatic-review contracts, reviewer independence/freshness/egress-redaction evidence, PR-grind mutation contracts, and marker ownership/atomicity/fsync-rename/path-symlink/trust semantics. It does not inspect or mutate target repos, write markers, run dispatchers, retire remaining work, or grant finalization authority.

### PR-grind readiness check

```bash
scripts/hermes-busdriver-pr-grind-check \
  --repo /path/to/repo \
  --pr 123 \
  --plugin-root /path/to/busdriver \
  --pretty
```

This is a read-only Delivery Mode helper. It checks the latest PR HEAD, mergeability, relevant `gh pr checks` output using Busdriver `scripts/relevant-check-status.sh` when available, and current-head review comments. It returns `clean`, `wait`, `needs_fix`, or `blocked`; it does **not** write `pr-grind-clean.local`, create commits, push, merge, or replace Busdriver's dispatcher-owned `pr-grind` loop.

### PR-grind bounded loop

```bash
scripts/hermes-busdriver-pr-grind-loop \
  --repo /path/to/repo \
  --pr 123 \
  --plugin-root /path/to/busdriver \
  --max-wait-seconds 300 \
  --poll-interval 30 \
  --pretty
```

This read-only loop repeatedly invokes `hermes-busdriver-pr-grind-check` until the latest PR HEAD is clean, needs a fix, is blocked, or the wait/poll budget expires. It re-polls after latest-head drift, records the ack-ledger policy as delegated to the checker, and refuses fix rounds (`--max-fix-rounds` must remain `0`). It never commits, pushes, writes Busdriver markers, or merges; even a clean result keeps finalization authority false for explicit operator finalization.

### Safe smoke checks

```bash
scripts/hermes-busdriver-smoke \
  --plugin-root /path/to/busdriver \
  --repo /path/to/repo \
  --pretty
```

## Relay v1 scope

Allowed now:

1. maintain `busdriver-relay` skill;
2. maintain read-only `hermes-busdriver-status`;
3. maintain Hermes-owned single-flight lock/status scaffolding;
4. maintain safe smoke/contract tests;
5. run `hermes-busdriver-gate` preflight/postflight around draft-mode agents;
6. run `hermes-busdriver-agent-draft` and optional `hermes-busdriver-agent-smoke` for draft implementation/adapters;
7. document decisions in ADRs.

Not allowed yet:

- repo-mutating `hermes-busdriver-codex-goal` launcher;
- `.claude/hermes/jobs` queue;
- Busdriver `hermes-home` install target;
- commit/PR/merge automation inside draft launchers or without litmus/pre-PR plus pr-grind-equivalent checks;
- deploy/release/publish automation;
- direct MCP/plugin routing;
- claims that Hermes shell execution is Busdriver-gate-safe.

## Delivery mode

Draft launchers still stop at `needs_busdriver_review`; this repo does not provide an autonomous mutating finalization launcher. Explicit operator-level Hermes Delivery Mode remains a narrow external procedure: when the user explicitly asks Hermes to finish the whole job, Hermes may perform ordinary Git/GitHub finalization only after litmus/pre-PR-equivalent checks, local verification, PR checks/status rollup, Busdriver `relevant-check-status.sh` when available, PR reviews/comments, bounded wait for advisory reviewer bots, fix rounds for actionable feedback, and a clean latest-head PR-grind result. That does **not** make mutating commit/push/PR/merge executor code, draft-launcher finalization, marker writes, deploy/release/publish, or direct MCP/plugin routing part of the relay surface. After merge, sync the PR base branch discovered from PR status rather than hard-coding `main`. GitHub issue/comment mutation remains separate and requires explicit user request for that side effect.
