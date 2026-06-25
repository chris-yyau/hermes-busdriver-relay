# Current Status — Hermes Busdriver Relay

Last verified against Busdriver `1.71.0` source on `origin/main`.

## Locations

| Component | Path / URL |
|---|---|
| Relay repo | `/Volumes/work/projects/hermes-busdriver-relay` |
| Relay GitHub | `https://github.com/chris-yyau/hermes-busdriver-relay` |
| Busdriver source main worktree used for verification | `/Volumes/Work/Projects/busdriver/.claude/worktrees/devin-reviewer` |
| Installed Busdriver marketplace plugin | `~/.claude/plugins/marketplaces/busdriver` |
| Hermes skill install path | `~/.hermes/skills/autonomous-ai-agents/busdriver-relay` |

## Completed scope

Relay v1 is complete as a **read-only/status + lock + smoke** integration. Relay v2 has started with a **Hermes-side equivalent gate runner** that allows draft-mode agent implementation while keeping commit/push/PR/merge/deploy blocked.

Implemented:

- `skills/busdriver-relay/SKILL.md`
- `skills/busdriver-relay/references/*.md`
- `scripts/hermes-busdriver-status`
- `scripts/hermes-busdriver-lock`
- `scripts/hermes-busdriver-runtime-check`
- `scripts/hermes-busdriver-gate`
- `scripts/hermes-busdriver-smoke`
- `tests/contract/test_status_probe.py`
- `tests/contract/test_lock.py`
- `tests/contract/test_runtime_check.py`
- `tests/contract/test_gate.py`
- `docs/hermes-busdriver-integration-contract-v2.md`
- `docs/settling-checks-v1.md`
- ADRs and README boundary docs

## Verification commands

```bash
cd /Volumes/work/projects/hermes-busdriver-relay
python3 -m pytest tests/contract -q
scripts/hermes-busdriver-smoke \
  --plugin-root /Volumes/Work/Projects/busdriver/.claude/worktrees/devin-reviewer \
  --repo /Volumes/Work/Projects/busdriver/.claude/worktrees/devin-reviewer \
  --pretty
```

Most recent verified result:

```text
12 passed
smoke_ok True
returncodes [0, 0, 0, 0, 0]
package_version 1.71.0
hook_event_count 7
route_count 7
repo_dirty False
runtime_check.mutating_launcher_allowed False
gate.agent_implementation_draft_allowed True
gate.commit_allowed False
gate.push_allowed False
gate.pr_allowed False
```

## Still intentionally deferred

These are not missing work; they are blocked by design until stronger equivalent finalization gates exist:

- `hermes-busdriver-codex-goal` with commit authority
- repo-mutating Codex/OpenCode/Droid/Agy/Grok launcher finalization
- `.claude/hermes/jobs` queue
- commit / PR / merge / deploy automation
- direct MCP/plugin routing
- any claim that Hermes bare shell execution is Busdriver-gate-safe

## Operational rule

Hermes may use this repo for:

1. Busdriver-aware intake and route recognition;
2. Phase 0 status discovery;
3. read-only route/gate/marker/lock reporting;
4. preflight/postflight gates around Hermes-launched draft agents such as Codex/OpenCode/Droid/Agy/Grok;
5. warning the user when the next step still needs Busdriver/Claude or a stronger finalization gate;
6. future v2 work to add agent adapters and commit/PR-capable equivalent gates.

Hermes must not use this repo to bypass Busdriver gates or duplicate Busdriver's source-of-truth.
