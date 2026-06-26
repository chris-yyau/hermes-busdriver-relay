# Current Status — Hermes Busdriver Relay

Last verified against Busdriver `1.71.0` source on `origin/main`.

## Locations

| Component | Path / URL |
|---|---|
| Relay repo | `/Volumes/work/projects/hermes-busdriver-relay` |
| Relay GitHub | `https://github.com/chris-yyau/hermes-busdriver-relay` |
| Busdriver source path read during Phase 0 | `/Volumes/work/projects/busdriver` |
| Installed Busdriver marketplace plugin used for smoke | `~/.claude/plugins/marketplaces/busdriver` |
| Hermes skill install path | `~/.hermes/skills/autonomous-ai-agents/busdriver-relay` |

## Completed scope

Relay v1 is complete as a **read-only/status + lock + smoke** integration. Relay v2 has a **Hermes-side equivalent gate runner**, a **Codex-only draft launcher**, and a **read-only PR-grind readiness checker**. Draft implementation remains non-finalizing; Delivery Mode finalization is still operator-level, but it now has a deterministic checker for latest-HEAD checks/comments/mergeability.

Implemented:

- `skills/busdriver-relay/SKILL.md`
- `skills/busdriver-relay/references/*.md` including claude-mem push and user-preference/profile notes
- `scripts/hermes-busdriver-status`
- `scripts/hermes-busdriver-lock`
- `scripts/hermes-busdriver-runtime-check`
- `scripts/hermes-busdriver-gate`
- `scripts/hermes-busdriver-agent-draft`
- `scripts/hermes-busdriver-agent-smoke`
- `scripts/hermes-busdriver-pr-grind-check`
- `scripts/hermes-busdriver-smoke`
- `tests/contract/test_status_probe.py`
- `tests/contract/test_lock.py`
- `tests/contract/test_runtime_check.py`
- `tests/contract/test_gate.py`
- `tests/contract/test_agent_draft.py`
- `tests/contract/test_agent_smoke.py`
- `tests/contract/test_pr_grind_check.py`
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

Most recent verified result:

```text
contract tests: 39 passed
smoke_ok True
package_version 1.71.0
hook_event_count 7
route_count 7
runtime_check.hook_manifest_available True
runtime_check.gate_hooks_declared True
runtime_check.inside_claude_code_hook_invocation False
runtime_check.mutating_launcher_allowed False
clean temp repo preflight.agent_implementation_draft_allowed True
clean temp repo preflight.commit_allowed False
clean temp repo preflight.push_allowed False
clean temp repo preflight.pr_allowed False
```

## Still intentionally deferred

These are not missing work; they are blocked by design until stronger equivalent finalization gates exist:

- `hermes-busdriver-codex-goal` with commit authority
- repo-mutating Codex (others temporarily deferred) launcher finalization
- `.claude/hermes/jobs` queue
- commit / PR / merge automation inside draft launchers or without litmus/pre-PR plus pr-grind-equivalent checks
- deploy / release / publish automation
- direct MCP/plugin routing
- any claim that Hermes bare shell execution is Busdriver-gate-safe

## Operational rule

Hermes may use this repo for:

1. Busdriver-aware intake and route recognition;
2. Phase 0 status discovery;
3. read-only route/gate/marker/lock reporting;
4. preflight/postflight gates around Hermes-launched draft agents such as Codex (others temporarily deferred);
5. warning the user when the next step still needs Busdriver/Claude or a stronger finalization gate;
6. future v2 work to add agent adapters and commit/PR-capable equivalent gates.

Hermes must not use this repo to bypass Busdriver gates or duplicate Busdriver's source-of-truth.

If the user explicitly asks Hermes to complete the whole delivery, Hermes must use litmus/pre-PR-equivalent checks before commit/PR and a pr-grind-equivalent loop before any merge: check PR status, wait for reviewer bots with a bounded budget, inspect comments/reviews, fix actionable feedback, and merge only when clean. After merge, sync the PR base branch discovered from PR status rather than hard-coding `main`. GitHub issue/comment mutation remains separate and requires explicit user request for that side effect.
