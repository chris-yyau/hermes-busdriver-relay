# Current Status — Hermes Busdriver Relay

Last verified against the installed Busdriver marketplace plugin `1.73.0` used by smoke.

## Locations

| Component | Path / URL |
|---|---|
| Relay repo | `/Volumes/work/projects/hermes-busdriver-relay` |
| Relay GitHub | `https://github.com/chris-yyau/hermes-busdriver-relay` |
| Busdriver source path read during Phase 0 | `/Volumes/work/projects/busdriver` |
| Installed Busdriver marketplace plugin used for smoke | `~/.claude/plugins/marketplaces/busdriver` |
| Hermes skill install path | `~/.hermes/skills/autonomous-ai-agents/busdriver-relay` |

## Completed scope

Relay v1 is complete as a **read-only/status + lock + smoke** integration. Relay v2 has a **Hermes-side equivalent gate runner**, a **Codex-only draft launcher**, a **read-only balanced agent work planning envelope**, a **read-only PR-grind readiness checker**, a **read-only bounded PR-grind polling loop**, a **fail-closed delivery dispatcher with verify-only local verifiers, read-only `pr-grind` loop execution, durable `hermes-busdriver-delivery-run/v0` envelopes, read-only `--mode status` run lookup, redacted verifier output artifacts, nested helper timeout budgeting, and state-dir-aware litmus evidence forwarding**, a **read-only litmus/pre-PR marker freshness status helper**, a **read-only finalization readiness / handoff envelope with machine-readable finalization guardrails, dual-review readiness evidence, advisory pre-PR dual-review evidence classification, and recursive fail-closed authority hardening**, a **read-only finalization contract status / capability matrix for ADR 0005 remaining-work unlock criteria**, **read-only Busdriver drift-baseline compatibility reporting**, **read-only finalization lock/status blocking**, **configurable read-only relay equivalents for reviewer/voice/arbiter/backstop status roles**, a **read-only dispatcher-facing relay role resolver**, **optional relay-role resolution evidence inside delivery/finalization status envelopes**, and **delivery-status capability inventory entries for public relay helpers**. The non-mutating relay surface is complete for the current policy scope. Draft implementation remains non-finalizing; Delivery Mode finalization is still operator-level, but it now has deterministic checker/status/loop/plan/verify/pr-grind/handoff/contract-status envelopes for latest-HEAD checks/comments/mergeability, configured relay-role selection, normalized/redacted marker freshness evidence, explicit non-mutating guardrails, policy-blocked ADR 0005 unlock criteria, dual-review role-readiness evidence, advisory pre-PR dual-review freshness classification, recursive authority-positive fail-closed checks, and durable run identity/artifact handoff.

Implemented:

- `skills/busdriver-relay/SKILL.md`
- `skills/busdriver-relay/references/*.md` including PR-grind delivery discipline, June 2026 reviewer-quality policy, claude-mem push, and user-preference/profile notes
- `scripts/hermes-busdriver-status` including optional read-only `--drift-baseline <json>` compatibility reporting and relay-namespaced configurable equivalent reviewer/voice/arbiter/backstop status roles from a separate relay config JSON
- `scripts/hermes-busdriver-relay-role` for read-only fail-closed selection of one configured relay equivalent role
- `scripts/hermes-busdriver-lock`
- `scripts/hermes-busdriver-runtime-check`
- `scripts/hermes-busdriver-gate`
- `scripts/hermes-busdriver-agent-draft`
- `scripts/hermes-busdriver-agent-balance-plan` read-only planning envelope for one gated mutating draft lane plus parallel read-only review/status lanes
- `scripts/hermes-busdriver-agent-smoke`
- `scripts/hermes-busdriver-delivery-status` including optional `--relay-role` / `--relay-config` resolver evidence, sanitized/normalized/redacted state-dir-aware read-only litmus/pre-PR freshness evidence, and metadata-only relay capability inventory entries for public helpers including agent-balance-plan, agent-smoke, deliver, smoke, finalization-readiness, and finalization-contract-status; litmus evidence fails closed on unavailable/malformed/schema-invalid/repo-mismatched/authority-positive/subprocess-failed helper output
- `scripts/hermes-busdriver-deliver` including nested delivery-status timeout budgeting and `--busdriver-state-dir-name` forwarding to litmus evidence checks
- `scripts/hermes-busdriver-litmus-status`
- `scripts/hermes-busdriver-finalization-readiness` including advisory `hermes-busdriver-pre-pr-dual-review-evidence/v0` classification derived only from sanitized delivery-status litmus summaries, plus embedded read-only `finalization_contract_status` evidence for downstream consumers
- `scripts/hermes-busdriver-finalization-contract-status` read-only ADR 0005 contract/capability matrix for policy-blocked remaining finalization work
- `scripts/hermes-busdriver-pr-grind-check`
- `scripts/hermes-busdriver-pr-grind-loop`
- `scripts/hermes-busdriver-smoke` including finalization-readiness smoke summaries that expose compact embedded `finalization_contract_status` schema/policy/summary/authority evidence
- `tests/contract/test_status_probe.py`
- `tests/contract/test_relay_role.py`
- `tests/contract/test_lock.py`
- `tests/contract/test_runtime_check.py`
- `tests/contract/test_gate.py`
- `tests/contract/test_agent_draft.py`
- `tests/contract/test_agent_smoke.py`
- `tests/contract/test_delivery_status.py`
- `tests/contract/test_deliver.py`
- `tests/contract/test_litmus_status.py`
- `tests/contract/test_finalization_readiness.py`
- `tests/contract/test_pr_grind_check.py`
- `tests/contract/test_pr_grind_loop.py`
- `docs/hermes-busdriver-integration-contract-v2.md`
- `docs/settling-checks-v1.md`
- `docs/settling-checks-v2.md`
- ADRs and README boundary docs, including ADR 0005's non-mutating finalization authority integration contract prerequisite

## Verification commands

```bash
cd /Volumes/work/projects/hermes-busdriver-relay
uvx --from pytest pytest tests/contract -q
scripts/hermes-busdriver-smoke \
  --plugin-root ~/.claude/plugins/marketplaces/busdriver \
  --pretty
```

`hermes-busdriver-smoke` now falls back to `uvx --from pytest pytest` when the active Python lacks pytest, so it works from the Hermes venv as well as developer shells.

Most recent local verification on `feat/balanced-agent-work-plan` based on `main` after PR #41 (`9a483ce4af44c6f2a06fc1c1b1ec2e527b693336`):

```text
focused balance/delivery/smoke tests: 67 passed
contract tests: 363 passed
py_compile: agent-balance-plan, delivery-status, and smoke passed
smoke_ok True
agent_balance_plan.schema hermes-busdriver-agent-balance-plan/v0
agent_balance_plan.policy single_mutating_worker_multi_readonly_reviewers
agent_balance_plan.max_mutating_draft_workers 1
agent_balance_plan.read_only_lanes_parallelizable True
agent_balance_plan.authority_any_true False
agent_balance_plan.lanes [('implementation_draft', 1, False, False), ('readonly_review', 3, True, False), ('readonly_status', 2, True, False)]
finalization_guardrails.remaining_work statuses ['policy_blocked']
finalization_contract_status.schema hermes-busdriver-finalization-contract-status/v0
finalization_contract_status.current_policy non_mutating_relay_only
finalization_contract_status.remaining_work_count 5
finalization_contract_status.policy_blocked_count 5
finalization_contract_status.retired_count 0
finalization_contract_status.capability_allowed_count 0
finalization_contract_status.finalization_allowed False
finalization_contract_status.marker_write_allowed False
finalization_contract_status.programmatic_execution_allowed False
finalization_readiness.handoff_envelope.finalization_contract_status.schema hermes-busdriver-finalization-contract-status/v0
finalization_guardrails.remaining_work IDs match finalization_contract_status.remaining_work IDs
base main after PR #41: clean/synced before this branch
```

## Still intentionally deferred

These are not missing safe non-mutating relay work; they are blocked by design/policy until a stronger finalization integration surface exists and is explicitly approved:

- `hermes-busdriver-deliver` mutating commit/push/PR/merge executor mode and any matching mutating final delivery result envelope
- `hermes-busdriver-codex-goal` or draft-agent launcher finalization with commit authority
- `.claude/hermes/jobs` queue
- commit / PR / merge automation inside draft launchers or without litmus/pre-PR plus pr-grind-equivalent checks and the ADR 0005 authority contract; `hermes-busdriver-pr-grind-loop` remains read-only and refuses mutating fix rounds / push / re-poll integration
- programmatic litmus/pre-PR dual-review execution until Busdriver-approved role mappings/invocation seams, data-egress controls, schemas, and aggregation rules exist
- Busdriver marker interop or marker writes unless Busdriver defines an explicit safe integration surface and the ADR 0005 marker ownership/provenance contract is satisfied
- deploy / release / publish automation
- direct MCP/plugin routing
- any claim that Hermes bare shell execution is Busdriver-gate-safe

## Operational rule

Hermes may use this repo for:

1. Busdriver-aware intake and route recognition;
2. Phase 0 status discovery;
3. read-only route/gate/marker/lock reporting;
4. preflight/postflight gates around Hermes-launched draft agents such as Codex (others temporarily deferred);
5. generating read-only finalization readiness / handoff envelopes for Busdriver/Claude or explicit operator finalization;
6. warning the user when the next step still needs Busdriver/Claude or a stronger finalization gate;
7. maintaining the current read-only/non-mutating relay envelopes while leaving finalization expansion policy-blocked.

Hermes must not use this repo to bypass Busdriver gates or duplicate Busdriver's source-of-truth.

If the user explicitly asks Hermes to complete the whole delivery, Hermes must use litmus/pre-PR-equivalent checks before commit/PR and a pr-grind-equivalent loop before any merge: check PR status, wait for reviewer bots with a bounded budget, inspect comments/reviews, fix actionable feedback, and merge only when clean. After merge, sync the PR base branch discovered from PR status rather than hard-coding `main`. GitHub issue/comment mutation remains separate and requires explicit user request for that side effect.
