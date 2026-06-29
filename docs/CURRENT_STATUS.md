# Current Status — Hermes Busdriver Relay

Last verified against the installed Busdriver marketplace plugin `1.72.0` used by smoke.

## Locations

| Component | Path / URL |
|---|---|
| Relay repo | `/Volumes/work/projects/hermes-busdriver-relay` |
| Relay GitHub | `https://github.com/chris-yyau/hermes-busdriver-relay` |
| Busdriver source path read during Phase 0 | `/Volumes/work/projects/busdriver` |
| Installed Busdriver marketplace plugin used for smoke | `~/.claude/plugins/marketplaces/busdriver` |
| Hermes skill install path | `~/.hermes/skills/autonomous-ai-agents/busdriver-relay` |

## Completed scope

Relay v1 is complete as a **read-only/status + lock + smoke** integration. Relay v2 has a **Hermes-side equivalent gate runner**, a **Codex-only draft launcher**, a **read-only PR-grind readiness checker**, a **read-only bounded PR-grind polling loop**, a **fail-closed delivery dispatcher with verify-only local verifiers, read-only `pr-grind` loop execution, durable `hermes-busdriver-delivery-run/v0` envelopes, read-only `--mode status` run lookup, redacted verifier output artifacts, nested helper timeout budgeting, and state-dir-aware litmus evidence forwarding**, a **read-only litmus/pre-PR marker freshness status helper**, a **read-only finalization readiness / handoff envelope**, **read-only Busdriver drift-baseline compatibility reporting**, **read-only finalization lock/status blocking**, **configurable read-only relay equivalents for reviewer/voice/arbiter/backstop status roles**, a **read-only dispatcher-facing relay role resolver**, and **optional relay-role resolution evidence inside delivery/finalization status envelopes**. Draft implementation remains non-finalizing; Delivery Mode finalization is still operator-level, but it now has deterministic checker/status/loop/plan/verify/pr-grind/handoff envelopes for latest-HEAD checks/comments/mergeability, configured relay-role selection, normalized/redacted marker freshness evidence, and durable run identity/artifact handoff.

Implemented:

- `skills/busdriver-relay/SKILL.md`
- `skills/busdriver-relay/references/*.md` including PR-grind delivery discipline, June 2026 reviewer-quality policy, claude-mem push, and user-preference/profile notes
- `scripts/hermes-busdriver-status` including optional read-only `--drift-baseline <json>` compatibility reporting and relay-namespaced configurable equivalent reviewer/voice/arbiter/backstop status roles from a separate relay config JSON
- `scripts/hermes-busdriver-relay-role` for read-only fail-closed selection of one configured relay equivalent role
- `scripts/hermes-busdriver-lock`
- `scripts/hermes-busdriver-runtime-check`
- `scripts/hermes-busdriver-gate`
- `scripts/hermes-busdriver-agent-draft`
- `scripts/hermes-busdriver-agent-smoke`
- `scripts/hermes-busdriver-delivery-status` including optional `--relay-role` / `--relay-config` resolver evidence and sanitized, normalized/redacted, state-dir-aware read-only litmus/pre-PR freshness evidence that fails closed on unavailable/malformed/schema-invalid/repo-mismatched/authority-positive/subprocess-failed helper output
- `scripts/hermes-busdriver-deliver` including nested delivery-status timeout budgeting and `--busdriver-state-dir-name` forwarding to litmus evidence checks
- `scripts/hermes-busdriver-litmus-status`
- `scripts/hermes-busdriver-finalization-readiness`
- `scripts/hermes-busdriver-pr-grind-check`
- `scripts/hermes-busdriver-pr-grind-loop`
- `scripts/hermes-busdriver-smoke`
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
- ADRs and README boundary docs

## Verification commands

```bash
cd /Volumes/work/projects/hermes-busdriver-relay
uvx --from pytest pytest tests/contract -q
scripts/hermes-busdriver-smoke \
  --plugin-root ~/.claude/plugins/marketplaces/busdriver \
  --pretty
```

`hermes-busdriver-smoke` now falls back to `uvx --from pytest pytest` when the active Python lacks pytest, so it works from the Hermes venv as well as developer shells.

Most recent post-PR25 verified result:

```text
contract tests: 316 passed
py_compile: all relay scripts passed
smoke_ok True
package_version 1.72.0
hook_event_count 7
route_count 7
runtime_check.hook_manifest_available True
runtime_check.gate_hooks_declared True
runtime_check.inside_claude_code_hook_invocation False
runtime_check.mutating_launcher_allowed False
finalization_readiness.handoff_schema hermes-busdriver-handoff/v0
finalization_readiness.commit_allowed False
finalization_readiness.merge_allowed False
finalization_readiness.ready False
finalization_readiness.status blocked
clean temp repo preflight.agent_implementation_draft_allowed True
clean temp repo preflight.commit_allowed False
clean temp repo preflight.push_allowed False
clean temp repo preflight.pr_allowed False
```

## Still intentionally deferred

These are not missing work; they are blocked by design until stronger equivalent finalization gates exist:

- `hermes-busdriver-deliver` commit/push/PR/merge execution mode beyond verify-only local verifiers
- `hermes-busdriver-codex-goal` with commit authority
- repo-mutating Codex (others temporarily deferred) launcher finalization
- `.claude/hermes/jobs` queue
- commit / PR / merge automation inside draft launchers or without litmus/pre-PR plus pr-grind-equivalent checks; `hermes-busdriver-pr-grind-loop` remains read-only and refuses fix rounds
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
7. future v2 work to add agent adapters and commit/PR-capable equivalent gates.

Hermes must not use this repo to bypass Busdriver gates or duplicate Busdriver's source-of-truth.

If the user explicitly asks Hermes to complete the whole delivery, Hermes must use litmus/pre-PR-equivalent checks before commit/PR and a pr-grind-equivalent loop before any merge: check PR status, wait for reviewer bots with a bounded budget, inspect comments/reviews, fix actionable feedback, and merge only when clean. After merge, sync the PR base branch discovered from PR status rather than hard-coding `main`. GitHub issue/comment mutation remains separate and requires explicit user request for that side effect.
