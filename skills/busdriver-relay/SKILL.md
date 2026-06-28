---
name: busdriver-relay
description: "Use when Hermes needs to relay work into the user's Busdriver/Claude Code workflow: idea intake, brainstorm→plan→grill, status checks, gate awareness, Codex handoff decisions, or Hermes↔Busdriver integration. Treat Busdriver as the canonical workflow/gate/runtime authority and Hermes as a thin intake/status/notifier unless a launcher has proven hook-runtime equivalence."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [busdriver, claude-code, codex, orchestration, gates, hermes-integration]
    related_skills: [hermes-agent, claude-code, codex, github-repo-management, claude-mem-log]
---

# Busdriver Relay

## Overview

Busdriver is the user's canonical coding pipeline/control plane. Hermes should be a Busdriver-aware second agent: intake, status, routing, Telegram/cron notification, and carefully bounded orchestration. Hermes must not become a shadow Busdriver and must not copy Busdriver's skills, hooks, MCP routes, plugins, marker logic, or gate implementations.

The durable split:

```text
Hermes = recognition, Phase 0 discovery, JIT source reads, read-only status, user interaction, notification
Busdriver/Claude Code = workflow authority, gates, reviews, MCP/plugin routing, coding execution, commits, PRs, merges
Codex = worker only through Busdriver-approved handoff paths, never raw for repo-changing work
Hermes Delivery Mode = user-explicit operator path for branch/commit/PR/merge only after litmus/pre-PR and pr-grind-equivalent checks pass
```

Critical safety fact: Busdriver's most important gates are Claude Code hook-runtime behavior. A normal Hermes shell running a Busdriver script does not automatically fire Claude Code `PreToolUse`/`PostToolUse` hooks. Never assume “script exists” or “dispatcher ran” means “gate fired.”

## When to Use

Use this skill when the user:
- asks whether Hermes can follow Busdriver pipelines;
- gives a coding/product idea and expects brainstorm → plan → grill behavior;
- asks about syncing Claude/Busdriver setup into Hermes;
- asks Hermes to launch/coordinate **Codex** (currently the only active agent) through Busdriver;
- asks for Busdriver status, routes, gates, MCP/plugin boundaries, or update strategy;
- asks to build Hermes-side Busdriver adapter/status/cron tooling.

**Current User Scope Policy (embedded preference):** Busdriver itself is the Claude-side workflow/control plane; `hermes-busdriver-relay` is the Hermes/Codex-side bridge/equivalent layer. Draft implementation launchers are still Codex-first unless a specific adapter is proven, but all relay-side decision/review anchors and voices (blueprint reviewers/arbiter, PR lead/backstop, council architect/pragmatist/critic/researcher/skeptic) should be configurable from a relay-owned JSON so Hermes can avoid using the same agent as both coder and reviewer. Do not make Busdriver itself Claude-free unless the user explicitly asks; implement Codex/Hermes-side equivalents in the relay and label them as equivalents, not Busdriver-native Claude runtime.

**Hermes Profile vs Skill Clarification (user preference):** `busdriver-relay` is a thin relay **skill**, not a Hermes profile. It runs under the user's main/default Hermes profile. No new "coding profile" is required for relay work. Treat it as an additional capability loaded into the existing profile (similar to other autonomous-ai-agents skills). Only create a dedicated profile if the user explicitly needs complete isolation (separate config, memory, plugins, model routing) for the relay layer. When asked "is busdriver relay the main profile?", answer clearly: no — it is a skill layer on top of the main profile.

Do **not** use this skill to:
- directly mutate repos, commit, push, create PRs, or merge outside explicit Hermes Delivery Mode;
- deploy, release, publish, or mutate external systems;
- recreate Busdriver's MCP/plugin graph inside Hermes;
- copy all Busdriver skills into Hermes;
- write or forge Busdriver PASS/bypass/review markers;
- call raw `codex exec` for repo-changing work;
- enable additional mutating agent adapters (OpenCode etc.) without a proven relay gate/smoke path and fresh user intent.

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
  → claude-mem push (via claude-mem-log) when configured/approved, otherwise Hermes/Hindsight summary only
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
| PR grind/pre-merge | `gh pr merge` | Claude hook + skill or explicit Hermes pr-grind-equivalent loop | No merge unless Busdriver/pr-grind semantics say clean. Never merge while required checks, reviewer bots, or actionable comments are pending. |
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
| Finishing | `finishing-a-development-branch`; linked worktree cleanup must be detected and human-confirmed, never automatic; after Hermes coding via this relay, proactively push summary to claude-mem using claude-mem-log only when claude-mem access is configured/approved. |
| PR feedback/merge | `pr-grind`, `scripts/relevant-check-status.sh`, `scripts/ack-ledger.sh` |
| Codex handoff | `codex-goal-handover`, `scripts/codex/*` |
| MCP/plugin health | `mcp-health-check`, hook manifest, config/status scripts |

## Hermes Delivery Mode and PR Grind

Default relay draft mode still cannot finalize. But when the user explicitly tells Hermes to **complete all work** (commit, PR, merge, or similar delivery language), Hermes must not stop at a dirty tree and must not skip Busdriver's litmus/pre-PR or PR feedback loop. In that delivery mode, Hermes may perform Git/GitHub finalization only if it runs litmus/pre-PR-equivalent checks plus a pr-grind-equivalent loop:

1. Before committing or opening a PR, verify the current Busdriver litmus/pre-commit/pre-PR semantics for the target repo. If the Claude hook runtime cannot be proven to fire, run an equivalent explicit litmus/pre-PR check when available; otherwise bail instead of committing or creating the PR.
2. Create a branch and commit only after litmus/pre-PR-equivalent checks and local tests/smoke pass.
3. Push and open a PR with a body listing verification evidence.
4. Run PR grind semantics before merge:
   - inspect `gh pr checks` / `statusCheckRollup`;
   - run live Busdriver `scripts/relevant-check-status.sh` when available;
   - inspect PR reviews and comments for actionable findings on changed lines;
   - wait with a bounded budget for advisory reviewer bots such as CodeRabbit, Devin, Cubic, Cursor, or Codex;
   - fix and push additional commits if feedback is actionable;
   - bail to the user on policy gaps, design/scope questions, failing required checks, max-wait exhaustion, or unclear reviewer state.
5. Merge only after the PR is clean by current Busdriver/pr-grind semantics. Never enable GitHub auto-merge as a substitute for pr-grind.
6. After merge, sync the PR base branch discovered from PR status (not hard-coded `main`), verify the final state, and push a claude-mem summary only when claude-mem access is configured/approved; otherwise report the summary in Hermes and rely on Hindsight.

This does not grant commit/PR/merge authority to draft agent launchers. It is an operator-level Hermes delivery path used only when the user explicitly asks Hermes to finish the whole job. Until a dedicated script/gate exists, these are mandatory operator steps: if any check/review/comment state cannot be verified clean, Hermes must bail instead of merging.

## Execution Seam Classification

Classify before use:

| Class | Meaning | Hermes v1 action |
|---|---|---|
| Standalone read-only shell seam | Safe status/read outside Claude runtime | Allowed after Phase 0. |
| Standalone mutating shell seam | Can change repo/external state outside Claude runtime | Not allowed until hook-runtime equivalence or equivalent finalization gates pass. |
| Draft agent implementation seam | Agent may modify working tree but cannot finalize | Allowed only inside `hermes-busdriver-gate preflight → agent → postflight`; result remains draft. Currently restricted to Codex. |
| Requires Claude Code session | Skill/agent/command/hook behavior | Route to user/Claude side unless explicitly approved later. |
| Requires MCP/plugin | Exists only through Claude/MCP/plugin | Do not synthesize/call; route to Busdriver/Claude. |

Known seams:

- `scripts/lib/resolve-cli.sh --json`: read-only status, but not full role resolution.
- `scripts/codex/codex-goal-dispatch.sh`: mutating primitive candidate, not v1-authorized as gate-safe.
- `scripts/codex/goal-result.schema.json`: Codex self-report schema, not full final result envelope.
- `scripts/lib/ultra-oracle.sh`: advisory shell adapter; requires data-boundary and standalone checks.
- `scripts/hermes-busdriver-runtime-check`: Hermes-owned read-only H13 checker; normal result blocks mutating launcher (`mutating_launcher_allowed=false`).
- `scripts/hermes-busdriver-gate`: Hermes-owned equivalent preflight/postflight gate runner for draft-mode agents; normal pass allows `agent_implementation_draft_allowed=true` while keeping commit/push/PR/merge false.
- `scripts/hermes-busdriver-status`: Also reports relay-owned configurable equivalents for all relay reviewer/voice anchors, including `relay.blueprint.*`, `relay.pr.*`, `relay.council.*`, and `relay.litmus.reviewer`. These are logical Hermes agent/model routes from a separate relay config JSON (default `~/.hermes/busdriver-relay/config.json`), not shell CLI names, and never grant Busdriver-native Claude runtime authority. Relay config shape is root-level `{ "coding_agent": "codex", "avoid_coding_agent_for_review": true, "routes": { "relay.pr.backstop": ["gpt-5.5", "codex"] } }`; `coding_agent` must be a non-empty string, `avoid_coding_agent_for_review` must be boolean, `routes` must be an object, and each route value must be a non-empty string or an array of non-empty strings. Invalid/malformed config is reported as degraded/fail-closed (`selected_agent=null`) instead of silently falling back healthy; see `references/relay-configurable-roles-lessons.md`.
- `scripts/hermes-busdriver-relay-role`: Read-only dispatcher-facing resolver for a single relay equivalent role. It reuses relay config validation from status, returns `schema=hermes-busdriver-relay-role/v0`, exits 0 only when the role has a non-degraded `selected_agent`, and exits nonzero for unknown/degraded/malformed config while keeping `dispatch_allowed=false`, `mutation_allowed=false`, and `finalization_allowed=false`.
- `scripts/hermes-busdriver-agent-draft`: Launcher that acquires the Hermes lock, runs gate preflight, executes **Codex** (current proven mutating draft surface) or custom/noop test commands in draft mode under a best-effort PATH guard, runs postflight, and returns `needs_busdriver_review`.
- `scripts/hermes-busdriver-agent-smoke`: Optional real-agent adapter smoke; creates a throwaway repo and may consume provider quota/tokens. Codex has been verified with it; other mutating agents require explicit adapter validation.
- `scripts/hermes-busdriver-delivery-status`: Read-only Delivery Mode status envelope that combines repo state, Busdriver PR-grind source availability, relay capabilities, lock/run summaries, and optional PR-grind readiness output; it never authorizes or performs finalization.
- `scripts/hermes-busdriver-finalization-readiness`: Read-only finalization readiness helper that combines delivery status with Phase-0 status and emits a `hermes-busdriver-handoff/v0` envelope for Busdriver/Claude or an explicit operator finalizer. It has no execute mode and keeps commit/push/PR/merge/deploy/marker-write authority false.
- `scripts/hermes-busdriver-pr-grind-check`: Read-only Delivery Mode helper that checks latest PR HEAD mergeability, relevant checks via Busdriver `scripts/relevant-check-status.sh` when available, and current-head review comments. It returns `clean` / `wait` / `needs_fix` / `blocked` and never writes Busdriver markers or merges.
- `scripts/hermes-busdriver-pr-grind-loop`: Read-only bounded PR-grind polling loop that repeatedly invokes the checker until clean / needs-fix / blocked / max-wait, re-polls after latest-head drift, delegates ack-ledger interpretation to the checker, refuses fix rounds, and keeps all finalization authority false.
- `references/pr-grind-delivery-discipline.md`: captured user correction for end-to-end Hermes delivery expectations and exact Busdriver pr-grind latest-head loop semantics.
- `references/june-2026-pr-reviewer-quality-evaluation.md`: durable June 2026 reviewer-quality report and relay policy for CodeRabbit/cubic/Codex/Cursor/Devin signals; blocker source-of-truth is live unresolved non-outdated review threads, not reviewer status completion alone.
- `skills/*.md`: readable source; actual invocation requires a Busdriver/Claude-style skill runtime.

## Hook-Runtime Equivalence

Before Hermes can use any repo-changing launcher, the launcher must prove one of:
1. it enters the same Claude Code / Busdriver hook runtime;
2. it explicitly invokes Busdriver-equivalent gate checks;
3. it refuses gated operations and returns blocked status;
4. it is constrained to local-only work and cannot push/PR/merge/deploy/finalize.

Without this proof, Hermes may use the launcher only for read-only/non-mutating work.

## Hermes Equivalent Gate Runner

When Claude Code quota is unavailable, Hermes may independently call coding agents **(currently Codex only)** only through the draft gate pattern:

```text
hermes-busdriver-gate preflight
  → scoped agent implementation draft
  → hermes-busdriver-gate postflight
  → report / review / later finalization gate
```

The v1 gate runner checks repo identity, dirty tree, Busdriver hook visibility, active blocking markers, `.git/hooks` tamper, gitignored file tamper, scope include/exclude, and optional verifier commands. A passing v1 gate allows working-tree draft implementation only. It does not allow commit, push, PR, merge, deploy, or Busdriver marker writes.

Use `hermes-busdriver-agent-draft` for the actual executable wrapper. It performs lock acquire/release, runs the gate pattern, launches Codex (or noop/custom for tests), and saves run artifacts under Hermes-owned state. Use `hermes-busdriver-agent-smoke --agent codex` only as an opt-in real adapter smoke because it consumes provider quota/tokens.

**Scope rule:** Although the underlying launcher code is written generically, respect the active Codex-only policy. Do not enable, default to, or document other agents (opencode, droid, agy, grok) until the user lifts the temporary restriction. This avoids duplicating work already present in OpenCode's Busdriver plugin and keeps the Hermes relay focused.

Use this pattern to continue implementation when Claude Code quota is exhausted while preserving Busdriver as the canonical finalization authority.

## Direct Command Ban

Hermes must not directly run repo-mutating or external-side-effect commands except through a proven Busdriver-approved launcher or the explicit operator-level Hermes Delivery Mode above.

Delivery Mode is the only narrow exception for ordinary Git/GitHub finalization commands (`git commit`, `git push`, `gh pr create`, `gh pr merge`). It requires user intent to complete the whole delivery, litmus/pre-PR-equivalent checks before commit/PR, local verification, a PR, pr-grind-equivalent checks, bounded reviewer-bot wait/fix rounds, and a clean PR before merge. It does **not** permit destructive git operations, deploy/release/publish, MCP mutation, marker writes, or database/cloud/secrets/payment mutations.

Forbidden direct operations include:
- destructive `git reset`, `git rebase`, `git merge`, destructive checkout, or bypass/force operations;
- `git commit`, `git push`, `gh pr create`, or `gh pr merge` outside explicit Delivery Mode;
- GitHub issue/comment mutation unless the user explicitly requested that specific comment/issue side effect;
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

**claude-mem MCP Integration (when granted by user):** When the user explicitly grants access to claude-mem MCP, treat it as a shared memory surface with the Claude/OpenCode side. Use it to query observations, sessions, and context for busdriver-relay work (in addition to Hermes native memory). This enables cross-agent continuity without duplicating Busdriver state. The MCP provides `claude_mem_search`-style access and a chroma backend at `~/.claude-mem/chroma`. Prefer it for historical project memory that should be visible to both Hermes and Claude Code sessions.

**Hermes-side access:** Confirm with `hermes mcp list` (expect `claude-mem ✓ enabled`). Hermes can directly invoke claude-mem tools for queries even when using a different external memory provider (e.g. hindsight or honcho). This is query-on-demand via tools, not automatic full ingestion into the Hermes provider.

**Pushing Hermes work into claude-mem (explicit write after coding):**
**busdriver-relay integration (proactive when configured/approved):** When using busdriver-relay for coding work, at the end of execution or finishing phases (or when user signals completion with 'finish' / 'done' / '這段結束了'), proactively load and use the related claude-mem-log skill if claude-mem access is configured/approved. Summarize Hermes work (hindsight for narrative, files touched, decisions), push as observation with agent_type='hermes'. If claude-mem access is unavailable or not approved, report the same summary in Hermes and rely on Hindsight instead of failing the delivery. claude-mem is populated by Claude Code hooks + explicit writes. Hermes coding (terminal, edits, decisions) does **not** automatically appear. When the user wants Claude Code to see Hermes actions ("要的", "push to claude-mem", "讓 claude code 記得 Hermes 做了什麼"):

- At natural task boundaries (end of a coding block), summarize the work (Hindsight recall can help).
- Log a structured observation (type: change | discovery | decision, agent_type="hermes").
- Full recipe, schema notes, discovery of memory_session_id, and Python insert pattern: see `references/claude-mem-push.md`.

Example trigger: after Hermes completes edits or a design decision relevant to the Claude-side project, explicitly log so it surfaces in Claude Code observations.

**User command style (direct action preference):** When the user says variants of "你拿key去呀", "你去改呀", "just go fix the .env on M5", or "I already filled the key in Hermes", immediately perform the remote edit (SSH + sed / python write / restart) without leaving placeholders or re-explaining separation. Repeated "I need the actual key" or placeholder explanations after such commands cause frustration. Pull from Hermes config (e.g. custom_providers ZenMux key) and apply directly. This pattern applies to remote Honcho .env, config updates, and similar relay actions.

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
4. `hermes-busdriver-gate` preflight/postflight around scoped draft-mode agents (Codex focus);
5. `hermes-busdriver-agent-draft` for lock+gate+Codex draft runs that return `needs_busdriver_review`;
6. opt-in `hermes-busdriver-agent-smoke` for real Codex adapter smoke tests;
7. advisory/user-facing routing that tells the user when finalization still needs Claude Code / Busdriver or stronger equivalent gates.

Not allowed yet:
- mutating `hermes-busdriver-codex-goal` finalizing launcher;
- `.claude/hermes/jobs` queue;
- Busdriver `hermes-home` install target;
- commit/PR/merge automation inside draft launchers or without litmus/pre-PR plus pr-grind-equivalent checks;
- deploy/release/publish automation;
- direct MCP/plugin routing;
- claim that Hermes-launched work is gate-safe without hook-runtime equivalence;
- activating support for non-Codex agents.

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

See also `references/claude-mem-push.md` (Hermes→claude-mem push patterns after coding), `references/user-preferences-profiles-mcp-agents.md` (direct remote action preference, three-memory-system coordination), and `references/june-2026-pr-reviewer-quality-evaluation.md` (June 2026 reviewer-quality report and reviewer-specific PR-grind policy).

## Verification Checklist

- [ ] JIT-read current Busdriver source before nontrivial routing.
- [ ] Phase 0 discovery completed before repo-changing decisions.
- [ ] `hooks/hooks.json` used as dynamic gate inventory.
- [ ] No repo-mutating direct git/gh/codex/deploy commands run by Hermes outside explicit Delivery Mode; Delivery Mode requires litmus/pre-PR-equivalent checks plus a clean pr-grind-equivalent loop and still forbids raw repo-mutating `codex exec` and deploy/release/publish.
- [ ] Hook-runtime equivalence proven before any mutating launcher.
- [ ] Marker freshness tied to current state, not filename presence.
- [ ] MCP/plugin capabilities routed to Busdriver, not mirrored.
- [ ] External side effects explicitly approved and verified.
- [ ] Sensitive payloads minimized before external/advisory routes.
- [ ] Single-flight lock used for any future repo-changing operation.
- [ ] Success claims backed by fresh tool evidence.
- [ ] Respect current Codex-only active agent scope policy.
