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
Hermes = intake, Phase 0 discovery, JIT source reads, read-only status, non-finalizing draft/gate/handoff envelopes, notification, explicit gated Delivery Mode execution
Busdriver/Claude Code = sole canonical workflow/finalization authority, gates, reviews, MCP/plugin routing, trusted marker semantics
```

Important: Busdriver gates are largely Claude Code hook-runtime behavior. A Hermes bare shell running a Busdriver script does not automatically fire Claude Code hooks.

Current status: Hermes remains a relay/router/verifier and explicit Delivery Mode operator only. Relay route resolution is metadata, never dispatch authority: Codex is implementation-primary metadata and PR lead, OpenCode + Go is secondary/fallback draft-only metadata, Pi is deferred adapter history, and Cursor is the manual IDE sidecar. Every relay role reports programmatic dispatch and adapter verification false because no production relay-role dispatcher exists. `avoid_coding_agent_for_review=true` remains active, so Codex same-provider review is non-dispatchable without a fresh independent-session contract. Production Pi/OpenCode draft dispatch is separately `policy_blocked` by `agent_containment_and_credential_broker_unavailable`; functional adapter execution remains available only through non-installed test harnesses. Caller-supplied verifier execution is `policy_blocked` by `verifier_containment_unavailable`. `pre-pr-review` is `policy_blocked` by `isolated_review_runtime_unavailable`; `push` by `atomic_push_base_binding_unavailable`, `pr-create` by `atomic_pr_create_binding_unavailable`, and `merge` by `atomic_merge_base_binding_unavailable`. Busdriver/Claude Code remains the sole canonical finalization authority.

## Contents

Current policy authority: [coding workflow authority map](docs/coding-workflow-authority-map.md).

```text
ADRs/                                      Lightweight architecture decisions
ADRs/0005-finalization-authority-integration-contract.md
                                           Future authority/marker interop prerequisite contract
ADRs/0006-programmatic-dual-review-marker-interop.md
                                           Non-mutating programmatic dual-review / marker-interop design spike
ADRs/0007-pi-tool-harness-adapter.md       Deferred Pi draft-only tool-harness history and boundary
ADRs/0008-gated-delivery-executor-and-opencode-adapter.md
                                           Gated Delivery Mode executor and OpenCode adapter proof
docs/coding-workflow-authority-map.md      Cross-agent authority boundary map v0.1
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
scripts/hermes-busdriver-gate              State checker; production agent/verifier dispatch blocked
scripts/hermes-busdriver-agent-draft       Fail-closed draft parser; production agent dispatch blocked
scripts/pi/run-pi-busdriver-draft          Pi adapter contract wrapper; production launch blocked
scripts/opencode/run-opencode-busdriver-draft
                                           OpenCode adapter contract wrapper; production launch blocked
adapters/pi/                               Pi Busdriver-shaped tools and result schema
scripts/hermes-busdriver-agent-balance-plan
                                           Read-only balanced agent lane planning envelope
scripts/hermes-busdriver-agent-smoke       Parser/authority-negative agent smoke
scripts/hermes-busdriver-delivery-status   Read-only Delivery Mode status envelope
scripts/hermes-busdriver-deliver           Operation-specific dispatcher; verifier/push/PR-create/merge blocked
scripts/hermes-busdriver-litmus-status     Read-only litmus / pre-PR marker freshness status
scripts/hermes-busdriver-finalization-readiness
                                           Read-only finalization handoff envelope
scripts/hermes-busdriver-finalization-contract-status
                                           Read-only ADR 0005 finalization contract/capability matrix
scripts/hermes-busdriver-relay-brief      Read-only compact roadmap/status briefing for Telegram
scripts/hermes-busdriver-pr-grind-check    Read-only PR-grind readiness checker
scripts/hermes-busdriver-pr-grind-loop     Read-only bounded PR-grind polling loop
scripts/hermes-busdriver-smoke             Safe smoke runner
scripts/check-required-checks.sh           Required-check lock verifier
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

This helper is read-only and selects one configured logical Hermes/model agent as routing metadata. No relay role currently has a production dispatcher, so every valid role keeps `dispatch_allowed=false`, `mutation_allowed=false`, and `finalization_allowed=false`; unknown/degraded/malformed config also exits nonzero. Use `--list-roles` to inspect supported role names.

### Hermes-owned single-flight lock

```bash
scripts/hermes-busdriver-lock acquire --repo /path/to/repo --operation repo-mutation
scripts/hermes-busdriver-lock status --pretty
scripts/hermes-busdriver-lock release --repo /path/to/repo --operation repo-mutation --token <token>
```

Locks live under `~/.hermes/busdriver-relay/locks` by default, not inside `.claude/` or the target repo. Release always requires the original token; there is no force bypass. Release atomically retires the current pathname to a non-active tombstone, revalidates the moved token/generation, and guarantees no recursive pathname deletion; a non-cooperative replacement is restored or preserved. Use operation `finalization` for explicit finalization handoff/Delivery Mode single-flight coordination; read-only delivery-status/finalization-readiness report an active per-repo `finalization` lock as a blocker and still keep all finalization authority false.

### Hook-runtime equivalence check

```bash
scripts/hermes-busdriver-runtime-check \
  --plugin-root /path/to/busdriver \
  --repo /path/to/repo \
  --pretty
```

This is a read-only H13 checker. Normal Hermes execution should report `mutating_launcher_allowed: false`; that is the safe expected result for the current relay. Bare-shell mutating finalization remains blocked; explicit mutating work must use the gated Delivery Mode executor or Busdriver/Claude.

### Equivalent gate runner production status

```bash
BASELINE="$HOME/.hermes/busdriver-relay/gates/example.baseline.json"

# Expected production result: nonzero / blocked. This is a state-policy probe,
# not authorization to launch a worker.
scripts/hermes-busdriver-gate preflight \
  --plugin-root /path/to/busdriver \
  --repo /path/to/repo \
  --baseline-file "$BASELINE" \
  --scope-include 'src/**'
```

The production gate performs state checks but deliberately returns a blocked agent decision with `agent_containment_and_credential_broker_unavailable`; it does not authorize or launch Pi/OpenCode. Production caller-supplied verifier execution is likewise non-dispatchable under `verifier_containment_unavailable`. Non-installed test harnesses exercise the adapter and verifier contracts without creating a production unlock. Commit, push, PR, merge, and deploy authority remains false.

### Draft agent launcher production status

```bash
# Expected production result: nonzero / blocked before worker or credential handling.
scripts/hermes-busdriver-agent-draft \
  --plugin-root /path/to/busdriver \
  --repo /path/to/repo \
  --agent pi \
  --prompt-file /path/to/task.md \
  --scope-include 'src/**' \
  --pretty
```

The Pi and OpenCode adapter contracts are implemented and exercised only through non-installed test harnesses. Production defaults safely to `--agent noop`; `--agent pi` and `--agent opencode` remain explicit compatibility probes. All stop immediately after argument parsing—before repository, HOME/state, credential, lock, prompt, gate, run-directory, or worker handling—with `agent_containment_and_credential_broker_unavailable`. Schema, scope, authority-negative, executable-pin, and reconciliation tests therefore prove adapter behavior, not production containment or dispatch capability. Codex/custom mutation routes are absent.

If production containment and credential brokering are implemented in a future slice, a successful draft would still have to end at `status=needs_busdriver_review` with all finalization authority false. That is target-state wording, not a current production capability.

`config/trusted-runtime-manifest.json` is the reviewed trust inventory: it currently pins Busdriver package version **`1.90.0`** and the corresponding commit, independently of any newer plugin bytes observed in a local smoke environment. It also binds authenticated external executables/plugin scripts, embedded helper pins, and every side-effect-capable or agent-facing production entrypoint under `production_entrypoints`. `tests/contract/test_trusted_runtime_manifest.py` rejects identity or entrypoint digest drift; update the manifest and all embedded consumers in the same reviewed change.

### Balanced agent work plan

```bash
scripts/hermes-busdriver-agent-balance-plan --pretty
```

This read-only helper emits `hermes-busdriver-agent-balance-plan/v0`: a deterministic planning-only envelope selecting Codex as implementation-primary metadata plus parallel read-only review/status lanes. It reports no agent calls and does not dispatch, mutate repos, write markers, or grant commit/push/PR/merge/deploy/release/publish authority.

### Agent smoke status

`hermes-busdriver-agent-smoke` is currently a parser/authority-negative surface and requires an explicit supported `--agent pi|opencode`. Production dispatch is policy-blocked, so historical real-agent smoke is superseded provenance only and does not prove current containment, credential brokering, or production launch capability.

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

# Parser surface only: verify returns `verifier_containment_unavailable` immediately after
# argument parsing — before run identity, delivery-status, and artifact handling — so the
# verifier never runs, no run identity is synthesized, and no artifact is written. A later
# `--mode status --run-id local-verify-001` therefore has nothing to find.
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

# This status invocation is a fail-closed CROSS-PROCESS demonstration, not a successful
# retrieval. The pr-grind run above persists an artifact, but it signs it with a writer key held
# only in that process's memory; this second shell command is a new process with an empty key
# table, so no MAC can authenticate and the lookup truthfully returns run_not_found rather than
# treating unverifiable bytes as evidence. Only a lookup inside the SAME process, while the writer key is still
# live, can authenticate a persisted artifact. If that process has more than one valid artifact
# for the same run id, the winner is the largest HMAC-covered process-local artifact_sequence;
# mutable mtime/ctime and filename order carry no freshness authority. Until a trusted external key
# broker exists there is no supported cross-process retrieval. Early-blocked
# operations (verify, pre-PR review, push, PR create, merge) persist no artifact at all, so status
# has no semantics for their run ids.
scripts/hermes-busdriver-deliver \
  --mode status \
  --run-id pr-grind-001 \
  --pretty
```

This is the first fail-closed dispatcher envelope for executable Delivery Mode. Default `plan` still only calls the read-only delivery-status probe and keeps standing finalization authority disabled. Every result carries a nested durable `hermes-busdriver-delivery-run/v0` envelope with `run_id`, `phase`, `status`, `reason`, repo/PR identity, authority flags, and artifact references. `execute --operation verify` refuses with `verifier_containment_unavailable` immediately after argument parsing — before run identity, delivery-status, artifact handling, PR-grind, GitHub auth, repo helper, or caller-command paths — so it launches no caller-supplied verifier and writes no run artifact; executable-verifier behavior exists only in a non-installed test harness. Delivery wrappers forward nested helper timeouts and `--busdriver-state-dir-name` to delivery-status / litmus-status. `execute --operation pr-grind` requires `--pr`, invokes the read-only bounded PR-grind loop, validates the loop envelope schema/version/read-only flag and fail-closed nested authority flags before accepting `clean`, embeds the loop envelope under `pr_grind_loop`, writes the same Hermes-owned run artifact, and returns nonzero for unsafe loop output / `needs_fix` / `wait` / `blocked`; even a clean loop result only sets dispatcher status `pr_grind_clean` and keeps reusable commit/push/PR/merge/marker-write authority false. `execute --operation pre-pr-review` is non-dispatchable and returns `isolated_review_runtime_unavailable` before delivery-status, repository/state/lock, artifact, credential, or trusted-writer handling. The dormant Busdriver-writer adapter is not executed; Hermes does not raw-write `.claude/*` markers. Fixed early blockers do not synthesize `run_id`/`created_at` state and do not persist a run artifact. `execute --operation commit` is a gated side-effect executor. `push`, `pr-create`, and `merge` are non-dispatchable and fail closed with `atomic_push_base_binding_unavailable`, `atomic_pr_create_binding_unavailable`, and `atomic_merge_base_binding_unavailable`; parser/envelope code for those operations does not constitute production capability. `--run-id` may be supplied to give operator/subagent/cron handoff a stable run identity; artifact filenames include that token plus timestamp/PID discoverability fields and a random UUID for collision resistance. `--mode status --run-id <id>` is a read-only SAME-process lookup: it returns the freshest valid artifact only when the current process still holds the writer key and the full path-bound MAC authenticates; freshness among authenticated matches is the HMAC-covered process-local `artifact_sequence`. Unverifiable, forged, and cross-process bytes all produce `run_not_found`, and mtime/ctime/filename order are never authority. A successful same-process lookup returns the artifact path plus sanitized metadata (`artifact_run`, decision, schema, ok flag) as `status_lookup` evidence without writing a new artifact or probing the target repo; it does not echo verifier output tails from the persisted artifact. Matching artifacts must carry versioned deliver and nested delivery-run envelopes with fail-closed decision/authority metadata, so malformed, authority-positive, schema-spoofed, non-JSON, wrong-run, or stale artifacts are ignored.

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

This read-only helper emits `hermes-busdriver-finalization-contract-status/v0`: a machine-readable ADR 0005 status/capability matrix for the same `finalization_guardrails.remaining_work` IDs surfaced by finalization-readiness. It keeps legacy `contract_adr` compatibility while also exposing `contract_adrs` and `related_design_adrs`, including ADR 0006 design/spike evidence for programmatic dual-review and marker-interop rows, and includes top-level read-only ADR0005 `authority_sources` rows. The deliver executor and mutating run envelope rows now report `status=implemented_gated` with `implemented=true`, while programmatic dual-review execution, autonomous PR-grind fix/push/re-poll, and marker interop/write rows remain `policy_blocked`. All rows keep `safe_to_execute_by_this_helper=false`, `capability_allowed=false`, and authority flags false: this helper does not inspect or mutate target repos, write markers, run dispatchers, or grant standing finalization authority.

### Compact relay brief

```bash
scripts/hermes-busdriver-relay-brief --pretty
scripts/hermes-busdriver-relay-brief --brief
```

This read-only helper emits `hermes-busdriver-relay-brief/v0`: a compact local status/roadmap envelope suitable for Telegram summaries. It reports repo dirty/sync state, installed-skill drift, finalization contract status, Codex-primary metadata, retained Pi/OpenCode adapter-proof history, and the blocked dispatch posture. The helper is intentionally non-authoritative: every commit/push/PR/merge/finalization/marker-write/programmatic-execution/non-Codex-adapter authority flag remains false.

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
5. run production gate/agent commands only as fail-closed policy probes; use non-installed harnesses for Pi/OpenCode adapter contracts;
6. use `hermes-busdriver-deliver execute --operation commit` only through its evidence checks and finalization lock; use `pre-pr-review` only as a fail-closed policy probe before evidence/status/lock;
7. use read-only Delivery Mode status and PR-grind surfaces;
8. document decisions in ADRs.

Not allowed yet:

- production Pi/OpenCode dispatch or credential copying while `agent_containment_and_credential_broker_unavailable` is active;
- caller-supplied verifier execution while `verifier_containment_unavailable` is active;
- push while `atomic_push_base_binding_unavailable` is active;
- PR creation while `atomic_pr_create_binding_unavailable` is active;
- merge while `atomic_merge_base_binding_unavailable` is active;
- repo-mutating `hermes-busdriver-codex-goal` launcher;
- `.claude/hermes/jobs` queue;
- Busdriver `hermes-home` install target;
- raw marker writes/forging/deletion by Hermes; marker trust remains Busdriver-owned writer commands only;
- autonomous PR-grind fix/push/re-poll that invents fixes or bypasses draft-gate + litmus/pre-PR evidence;
- deploy/release/publish automation;
- direct MCP/plugin routing;
- claims that Hermes shell execution is Busdriver-gate-safe outside the dispatcher’s explicit evidence checks.

## Delivery mode

Production draft launchers currently stop before worker launch with `agent_containment_and_credential_broker_unavailable`; `needs_busdriver_review` describes the future successful-draft state, not an enabled production path. Delivery Mode availability is operation-specific: `commit` is the only mutating operation that may reach gated evidence/lock handling. `pre-pr-review` is `policy_blocked` by `isolated_review_runtime_unavailable` before those paths, while `push`, `pr-create`, and `merge` are `policy_blocked` by `atomic_push_base_binding_unavailable`, `atomic_pr_create_binding_unavailable`, and `atomic_merge_base_binding_unavailable`. The dormant Busdriver-owned marker-writer adapter is not invoked by production `pre-pr-review`, and Hermes must not raw-write `.claude/*` trusted markers. No blocked operation may be advertised as dispatchable.
