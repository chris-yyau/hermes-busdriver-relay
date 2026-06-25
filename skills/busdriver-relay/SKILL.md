---
name: busdriver-relay
description: "Use when Hermes needs to relay work into the user's Busdriver/Claude Code workflow: idea intake, brainstorm→plan→grill, status checks, gate awareness, Codex handoff decisions, or Hermes↔Busdriver integration. Treat Busdriver as the canonical workflow/gate/runtime authority and Hermes as a thin intake/status/notifier unless a launcher has proven hook-runtime equivalence."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [busdriver, claude-code, codex, orchestration, gates, hermes-integration]
    related_skills: [hermes-agent, claude-code, codex, github-repo-management]
---

# Busdriver Relay

## Overview

Busdriver is the user's canonical coding pipeline/control plane. Hermes should be a Busdriver-aware second agent: intake, status, routing, Telegram/cron notification, and carefully bounded orchestration. Hermes must not become a shadow Busdriver and must not copy Busdriver's skills, hooks, MCP routes, plugins, marker logic, or gate implementations.

The durable split:

```text
Hermes = recognition, Phase 0 discovery, JIT source reads, read-only status, user interaction, notification
Busdriver/Claude Code = workflow authority, gates, reviews, MCP/plugin routing, coding execution, commits, PRs, merges
Codex = worker only through Busdriver-approved handoff paths, never raw for repo-changing work
```

Critical safety fact: Busdriver's most important gates are Claude Code hook-runtime behavior. A normal Hermes shell running a Busdriver script does not automatically fire Claude Code `PreToolUse`/`PostToolUse` hooks. Never assume “script exists” or “dispatcher ran” means “gate fired.”

## When to Use

Use this skill when the user:

- asks whether Hermes can follow Busdriver pipelines;
- gives a coding/product idea and expects brainstorm → plan → grill behavior;
- asks about syncing Claude/Busdriver setup into Hermes;
- asks Hermes to launch/coordinate Codex through Busdriver;
- asks for Busdriver status, routes, gates, MCP/plugin boundaries, or update strategy;
- asks to build Hermes-side Busdriver adapter/status/cron tooling.

Do **not** use this skill to:

- directly mutate repos, commit, push, create PRs, merge, deploy, or publish;
- recreate Busdriver's MCP/plugin graph inside Hermes;
- copy all Busdriver skills into Hermes;
- write or forge Busdriver PASS/bypass/review markers;
- call raw `codex exec` for repo-changing work.

## Phase 0 — Mandatory Runtime Discovery

Before any repo-affecting route, perform Phase 0. If required state cannot be read, fail closed for repo-changing work.

Resolve/read live:

1. repo root, cwd, branch, worktree identity;
2. dirty tree: staged, modified, untracked, merge/rebase/cherry-pick state;
3. active freeze/scope/careful markers under current Busdriver state dir;
4. Busdriver plugin root and package metadata;
5. Busdriver user config;
6. active hook map from `hooks/hooks.json`;
7. orchestrator source files;
8. supplement manifest;
9. relevant plan/design/review marker state;
10. PR/CI/check status when PR/merge is involved;
11. same-repo/worktree concurrency lock status;
12. external side-effect and data-egress classification.

Reads are JIT only. Do not rely on previous session summaries for current gate or route decisions.

## Runtime Variables

Use symbolic runtime values, not hardcoded local paths:

| Symbol | Meaning |
|---|---|
| `$BUSDRIVER_PLUGIN_ROOT` | Busdriver plugin root. |
| `$BUSDRIVER_STATE_DIR` | Harness state dir, default `.claude`; opencode may use `.opencode`. |
| `$BUSDRIVER_USER_CONFIG` | Usually `$HOME/$BUSDRIVER_STATE_DIR/busdriver.json`. |
| `$REPO_ROOT` | Canonical git repo root. |
| `$PROJECT_CWD` | Current project cwd. |
| `$HERMES_STATE_DIR` | Hermes-owned state under `~/.hermes/...`. |

Observed paths may appear in diagnostics, never as durable policy.

## Dynamic Gate Discovery

The remembered gate table is a minimum alerting map, not an exhaustive authority. At runtime:

1. Read live `hooks/hooks.json`.
2. Read `skills/orchestrator/SKILL.md` and `skills/orchestrator/references/hooks-reference.md`.
3. Identify hooks relevant to the intended operation.
4. Verify referenced gate scripts exist and are readable.
5. Warn/fail closed if expected hooks are missing, renamed, disabled, or unreadable.
6. Never assume a gate exists only because this skill mentions it.

If Busdriver changes `orchestrator`, `hooks/hooks.json`, dispatcher, schema, or gate scripts, disable mutating launchers until smoke tests pass again.

## Minimum Workflow Skeleton

```text
Phase 0 runtime discovery
  → Phase 1 brainstorming
  → Phase 2 writing-plans
  → Phase 3 worktree / baseline
  → Phase 4 execution
  → Phase 5 verification / review
  → Phase 6 finishing / PR / merge
```

Routing examples:

| User/task state | Busdriver source | Hermes action |
|---|---|---|
| Vague idea | `skills/brainstorming/SKILL.md` | Start intake; read source before detailed mirroring. |
| Clear requirements | `skills/writing-plans/SKILL.md` | Plan before implementation. |
| Existing plan | `using-git-worktrees`, `blueprint-review` | Verify plan/gates before execution. |
| Bug/failing test | `systematic-debugging` | Root cause before fix; freeze may apply. |
| Test-writing | TDD skills | Evidence-first route. |
| High-stakes decision | `grill-me`, `council`, UltraOracle if enabled | Challenge assumptions before implementation. |
| Unknown route | Orchestrator | Ask one clarifying question or JIT-read. |

## Minimum Gate / Discipline Skeleton

| Gate/discipline | Trigger | Enforced by | Hermes rule |
|---|---|---|---|
| Brainstorming hard gate | feature/creative/behavior change | prompt discipline | No implementation until design is presented and approved. |
| Blueprint Review | plan/design/architecture doc | hook + skill | Do not implement while design is unreviewed. |
| Pre-implementation | Write/Edit/MultiEdit/Bash while design unreviewed | hook | Never route around it. |
| Litmus pre-commit | commit/finalize | Claude hook + skill | Hermes bare shell cannot assume it fired. |
| Litmus pre-PR | `gh pr create` | Claude hook | PR creation needs current Busdriver review semantics. |
| PR grind/pre-merge | `gh pr merge` | Claude hook + skill | No merge unless Busdriver says clean. |
| Freeze/Guard | freeze marker active | hook | Do not edit outside scope; do not remove marker. |
| Careful/destructive guard | destructive/high-risk Bash | hook | Stop and require human-visible approval. |
| GateGuard | first edit/destructive action when enabled | opt-in hook | Treat active gateguard as a hard stop. |
| Block no-verify | git bypass flags | hook | Never use bypass flags. |
| Verification before completion | any done/success claim | prompt discipline | No completion claim without fresh evidence. |
| Code review | completed task/major feature/before merge | prompt + agents | Do not trust agent self-report. |
| Build failure resolver | build/test/lint failure | prompt + agents | Route to resolver/debugging, not guess-fix. |
| Security review | auth/input/API/payment/secrets | prompt + agents | Route to Busdriver security review/scan. |
| Worktree/baseline | nontrivial repo work | skill discipline | Isolated worktree/baseline unless user overrides. |
| Deploy/release/publish | external release | human + Busdriver route | Out of v1 unless explicit approved route + user approval. |

## Source-of-Truth Read Map

Always JIT-read for nontrivial routing/status:

```text
$BUSDRIVER_PLUGIN_ROOT/hooks/hooks.json
$BUSDRIVER_PLUGIN_ROOT/skills/orchestrator/SKILL.md
$BUSDRIVER_PLUGIN_ROOT/skills/orchestrator/tasks-catalog.md
$BUSDRIVER_PLUGIN_ROOT/skills/orchestrator/domain-supplements.md
$BUSDRIVER_PLUGIN_ROOT/skills/orchestrator/references/hooks-reference.md
$BUSDRIVER_PLUGIN_ROOT/skills/orchestrator/references/gate-recovery.md
$BUSDRIVER_PLUGIN_ROOT/skills/supplements/MANIFEST.md
$BUSDRIVER_USER_CONFIG
```

Phase reads:

| Concern | Read JIT |
|---|---|
| Idea/design intake | `skills/brainstorming/SKILL.md` |
| Stress decisions | `skills/grill-me/SKILL.md`, `skills/council/SKILL.md` |
| Plan writing | `skills/writing-plans/SKILL.md` |
| Plan/design gate | `skills/blueprint-review/SKILL.md` |
| Worktree | `skills/using-git-worktrees/SKILL.md` |
| Execution | `subagent-driven-development`, `executing-plans`, `dispatching-parallel-agents` |
| Debugging | `systematic-debugging`, optional `diagnose` |
| TDD | `test-driven-development`, `tdd-workflow` |
| Verification | `verification-before-completion`, `verification-loop` |
| Code review | `requesting-code-review`, `receiving-code-review`, domain reviewers; read `orchestrator/domain-supplements.md` live for newly added reviewers such as `vue-reviewer` / `php-reviewer` |
| Domain patterns | `orchestrator/domain-supplements.md`, domain skills such as `vue-patterns`, `kubernetes-patterns`, plus domain rule directories |
| Config/skill maintenance | `config-gc`, `skill-scout`, `agent-self-evaluation` when the user asks to audit/adopt/evaluate setup or skills |
| Finishing | `finishing-a-development-branch`; linked worktree cleanup must be detected and human-confirmed, never automatic |
| PR feedback/merge | `pr-grind`, `scripts/relevant-check-status.sh`, `scripts/ack-ledger.sh` |
| Codex handoff | `codex-goal-handover`, `scripts/codex/*` |
| MCP/plugin health | `mcp-health-check`, hook manifest, config/status scripts |

## Execution Seam Classification

Classify before use:

| Class | Meaning | Hermes v1 action |
|---|---|---|
| Standalone read-only shell seam | Safe status/read outside Claude runtime | Allowed after Phase 0. |
| Standalone mutating shell seam | Can change repo/external state outside Claude runtime | Not allowed until hook-runtime equivalence + settling checks pass. |
| Requires Claude Code session | Skill/agent/command/hook behavior | Route to user/Claude side unless explicitly approved later. |
| Requires MCP/plugin | Exists only through Claude/MCP/plugin | Do not synthesize/call; route to Busdriver/Claude. |

Known seams:

- `scripts/lib/resolve-cli.sh --json`: read-only status, but not full role resolution.
- `scripts/codex/codex-goal-dispatch.sh`: mutating primitive candidate, not v1-authorized as gate-safe.
- `scripts/codex/goal-result.schema.json`: Codex self-report schema, not full final result envelope.
- `scripts/lib/ultra-oracle.sh`: advisory shell adapter; requires data-boundary and standalone checks.
- `scripts/hermes-busdriver-runtime-check`: Hermes-owned read-only H13 checker; normal result blocks mutating launcher (`mutating_launcher_allowed=false`).
- `skills/*.md`: readable source; actual invocation requires a Busdriver/Claude-style skill runtime.

## Hook-Runtime Equivalence

Before Hermes can use any repo-changing launcher, the launcher must prove one of:

1. it enters the same Claude Code / Busdriver hook runtime;
2. it explicitly invokes Busdriver-equivalent gate checks;
3. it refuses gated operations and returns blocked status;
4. it is constrained to local-only work and cannot push/PR/merge/deploy/finalize.

Without this proof, Hermes may use the launcher only for read-only/non-mutating work.

## Direct Command Ban

Hermes must not directly run repo-mutating or external-side-effect commands except through a proven Busdriver-approved launcher.

Forbidden direct operations include:

- `git commit`, `git push`, `git reset`, `git rebase`, `git merge`, destructive checkout;
- `gh pr create`, `gh pr merge`, GitHub issue/comment mutation;
- raw `codex exec` for repo-changing work;
- direct Claude Code plugin commands;
- direct MCP mutation calls;
- deploy/release/publish commands;
- database/cloud/secrets/payment mutations.

Allowed read-only examples after Phase 0: `git status`, `git diff --name-only`, `git rev-parse`, `gh pr view`, check-status queries, `resolve-cli.sh --json`, and reading Busdriver files/logs/artifacts.

## Marker / Artifact Freshness

Do not treat any marker, approval, PASS file, bypass file, review artifact, or clean-status artifact as valid by filename presence alone.

Freshness must be tied to current Busdriver semantics and current state: HEAD/diff/commit SHA, design/plan digest, branch/worktree, PR number/head SHA, CI/check run, freeze scope, Busdriver config/gate semantics.

Hermes may read marker metadata to verify status. Hermes must never write, forge, delete, consume, or inspect single-use skip files in ways that consume them before retry. Gate recovery follows `gate-recovery.md` exactly.

## Dirty Tree and Reconciliation

Before approved repo-changing dispatch, check dirty tree. If dirty, fail closed unless Busdriver source says allowed and the dirty state is explicitly included in the handoff.

After dispatch, reconcile dispatcher-reported files, actual git status/diff, committed SHA, unclaimed/ignored changes, out-of-scope changes, verifier output, and exit code. Any mismatch is `blocked` / `needs review`, not success.

## Codex Result Contract

`goal-result.schema.json` validates Codex self-report:

```text
summary
self_assessed_status
blocker
files_changed
intended_commit_message
```

Dispatcher may inject final fields like `committed`, `commit_sha`, `unclaimed_changes`, `ignored_changes`. Hermes needs either a Busdriver final envelope schema or a narrow compatibility schema before it can trust final launcher results.

Until settled, `codex-goal-dispatch.sh + goal-result.schema.json` is an experiment target, not a complete execution contract.

## MCP / Plugin Boundary

Hermes must not:

- directly call Busdriver MCP servers;
- synthesize `mcp__*` tool names;
- infer MCP schemas;
- store MCP credentials;
- build fallback MCP routes;
- replicate plugin command routing;
- call third-party CLIs on Busdriver's behalf unless explicitly approved as a Busdriver seam.

If a capability exists only through Busdriver/Claude/MCP/plugin, route it to Busdriver/Claude side and report status/results.

## External Side Effects and Data Egress

Treat external side effects as gated operations: PRs, issues, comments, deploys, releases, package publishing, database/cloud/secrets/payment mutations, calendars/docs/tickets, and notifications beyond Hermes's own response channel.

Before sending code/context to Codex, UltraOracle, council, MCP, external reviewers, or Telegram summaries, classify for secrets, credentials, keys/tokens, PII, payment data, customer data, proprietary unreleased code, and production incident data. Minimize payloads. UltraOracle enablement must come from user config or explicit user request, not project config.

## Single-Flight Lock

Before any repo-changing Busdriver-approved operation, acquire a Hermes-owned per-repo/per-worktree lock. Key includes canonical repo root, branch/worktree path, and operation class. Lock/queue state lives under `~/.hermes/...`, not `.claude/`, unless Busdriver later defines `.claude/hermes` as an integration surface.

## Fail-Closed Conditions

Fail closed for repo-changing work if Busdriver root/config/version, `hooks/hooks.json`, relevant gate scripts, orchestrator/phase skill, repo root/worktree/branch, dirty-tree policy, freeze scope, marker freshness, reviewer route, dispatcher result, git/status reconciliation, drift state, lock state, MCP boundary, external side-effect approval, or data-egress classification is missing/unclear.

## Allowed First Slice

Allowed now:

1. read-only `hermes-busdriver-status --json`;
2. Hermes-owned lock/status scaffolding;
3. H1-H13 smoke/contract tests;
4. advisory/user-facing routing that tells the user when to continue in Claude Code / Busdriver.

Not allowed yet:

- mutating `hermes-busdriver-codex-goal` launcher;
- `.claude/hermes/jobs` queue;
- Busdriver `hermes-home` install target;
- commit/PR/merge/deploy automation;
- direct MCP/plugin routing;
- claim that Hermes-launched work is gate-safe without hook-runtime equivalence.

## Repo Guidance

A private GitHub repo for this integration is recommended, but it should contain only Hermes-owned adapter artifacts:

- the Hermes `busdriver-relay` skill;
- read-only status scripts;
- lock/status scaffolding;
- test fixtures and contract tests;
- documentation and ADRs.

It should not vendor Busdriver, Claude plugins, MCP configs, secrets, or private marker/state files. Treat Busdriver as an external source-of-truth path discovered at runtime.

Naming rule: avoid Hermes-side names that imply Busdriver authority, especially `orchestrator`, because Busdriver already has its own orchestrator. Prefer names like `relay` that imply handoff/status rather than ownership or gate enforcement.

Session-specific scaffold details live in `references/initial-relay-repo-scaffold.md`.

## Session Reference

For implementation details and pitfalls discovered while building the first private relay repo/status tooling, see `references/relay-v1-session-lessons.md`. Use it when updating `busdriver.json`, maintaining `hermes-busdriver-status`, changing the relay name, or adding locks/smoke checks.

## Verification Checklist

- [ ] JIT-read current Busdriver source before nontrivial routing.
- [ ] Phase 0 discovery completed before repo-changing decisions.
- [ ] `hooks/hooks.json` used as dynamic gate inventory.
- [ ] No repo-mutating direct git/gh/codex/deploy commands run by Hermes.
- [ ] Hook-runtime equivalence proven before any mutating launcher.
- [ ] Marker freshness tied to current state, not filename presence.
- [ ] MCP/plugin capabilities routed to Busdriver, not mirrored.
- [ ] External side effects explicitly approved and verified.
- [ ] Sensitive payloads minimized before external/advisory routes.
- [ ] Single-flight lock used for any future repo-changing operation.
- [ ] Success claims backed by fresh tool evidence.
