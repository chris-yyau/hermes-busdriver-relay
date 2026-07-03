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

Reference: `references/blueprint-arbiter-route-simplification.md` captures the user's preferred Busdriver blueprint-review arbiter route shape: ZenMux/gateway fable first, then fresh subscription opus, with no subscription-fable, inherited-model, or inline-arbiter fallback. `references/pr-grind-fail-closed-review.md` captures fail-closed PR-grind review lessons for relay status envelopes, litmus evidence validation, data-egress sanitization, and rerunning diff-hash-bound gates after amendments. For the end-to-end delivery-status/finalization litmus PR-mode slice, including recognized status validation, allowlisted-value redaction, nested wrapper timeout budgets, diff-hash-bound trusted writer sequencing, and PR-grind actionable-comment cleanup, see `references/delivery-litmus-pr-mode-lessons.md`. For smoke-summary finalization-contract evidence, delivery-status capability inventory, strict-false authority summaries, and avoiding stale PR-grind result files after fix pushes, see `references/pr41-smoke-contract-capability-lessons.md`. For strict helper-evidence validation regression coverage, full authority assertions, pytest param ids, latest-head PR-grind after reviewer fixes, and manual post-hook marker cleanup when Hermes finalizes outside Claude runtime, see `references/pr44-strict-helper-evidence-validation-lessons.md`. For the follow-up top-level delivery-status child envelope bug in finalization-readiness, including requiring child schema/read_only/boolean-ok validation, adding top-level delivery-status `read_only`, and documenting duplicated schema literals instead of importing executable helpers, see `references/pr45-delivery-envelope-validation-lessons.md`. For the safe completion/docs refresh after PR45, including replacing stale verification evidence across README/CURRENT_STATUS/settling-checks, full smoke for docs-only PRs, latest-head PR-grind on docs PRs, and claude-mem boundary logging, see `references/pr46-docs-status-refresh-lessons.md`. For PR47 docs/status refresh delivery lessons — scoped docs-only Codex drafts, recovering from malformed draft verifier commands by rerunning corrected postflight, using deliver verify while the repo is intentionally dirty, then latest-head PR-grind/merge/cleanup — see `references/pr47-docs-refresh-delivery-lessons.md`. For PR48 skill-source sync lessons — repo-vs-installed skill drift, sanitizing copied reference lessons for current policy, reviewer-feedback cleanup, and syncing the reviewed repo copy back into the installed skill — see `references/pr48-skill-source-sync-lessons.md`. For PR49 skill-sync delivery lessons — parameterized private path examples, deliver verifier `env` argv usage, branch-sensitive finalization lock release, and passing raw PR-grind loop payloads into finalization-readiness — see `references/pr49-skill-sync-delivery-lessons.md`. For PR50 docs/status refresh lessons — replacing stale verification evidence after merged skill/docs slices, dirty-tree smoke caveats, preserving finalization policy wording, and post-merge cleanup verification — see `references/pr50-docs-status-refresh-lessons.md`. For PR51 finalization unlock ADR lessons — ADR-only non-mutating dual-review/marker-interop contracts, per-file docs-link assertions, required dual-review schema fields, branch-sensitive lock release, and avoiding Claude plugin clone/cache edits during relay delivery — see `references/pr51-finalization-unlock-adr-lessons.md`. For PR52 ADR 0006 contract-status lessons — machine-readable ADR follow-up evidence while preserving `contract_adr` compatibility and false authority flags, deliver-verifier glob pitfalls, surgical `.codegraph` cache cleanup, and reviewer-bot quota comment interpretation — see `references/pr52-adr0006-contract-status-lessons.md`. For PR53–PR55 skill-sync continuation lessons — late async reviewer follow-up PRs, installed-skill-to-repo sync discipline, durable skill-reference tests, and final `diff -qr` verification — see `references/pr53-pr55-skill-sync-lessons.md`. For PR56 skill-sync delivery lessons — scoped verifier env hygiene for local git commit signing, independent backstop verdict `reviewed_diff_hash` augmentation, raw PR-grind loop evidence, and manual post-hook cleanup after Hermes finalizes outside Claude runtime — see `references/pr56-skill-sync-delivery-lessons.md`. For balanced agent work planning, single-mutating-worker/multi-read-only-lane policy, `*_allowed` naming pitfalls, metadata-only inventory, and Python bootstrap rationale for relay helpers, see `references/balanced-agent-work-planning-lessons.md`. For read-only review of `docs/CURRENT_STATUS.md` refresh requirements, including which evidence to update, how to handle existing dirty WIP, and which finalization-policy wording must remain unchanged, see `references/current-status-readonly-review-lessons.md`. For finishing all remaining relay safe slices after a continuation request, including final Phase-0 sweeps, docs/status refreshes, installed-skill drift follow-up, corrected postflight after verifier quoting failures, PR-grind retry discipline, and final completion audit, see `references/relay-completion-sweep-lessons.md`. For PR60 skill-sync delivery lessons — exact installed-vs-repo `SKILL.md` byte alignment, explicit agent-draft `--repo`/`--plugin-root`, surgical verifier pycache cleanup and postflight rerun, evidence-bound verifier reruns, and post-PR marker cleanup before PR-grind — see `references/pr60-skill-sync-delivery-lessons.md`. For PR61–PR62 continuation lessons — post-merge skill-sync audit, exact CURRENT_STATUS evidence wording, live plugin-version correction, scoped docs postflight recovery, and resuming an interrupted docs refresh from dirty-branch state — see `references/pr61-pr62-continuation-lessons.md`. For PR63–PR64 skill-sync redaction lessons — sanitizing installed-skill references before repo sync, patching installed/repo copies together, adding private-path negative assertions, and following skill-sync merges with docs/status refreshes — see `references/pr63-pr64-skill-sync-redaction-lessons.md`. For post-delivery resource cleanup, distinguishing Hermes/Codex/Claude process families, safe temp/cache cleanup, and targeted relay-owned process-tree cleanup, see `references/relay-resource-cleanup-lessons.md`. For PR66 CURRENT_STATUS refresh lessons — evidence-only docs/status updates, verifier wording tolerance, avoiding literal `$BUSDRIVER_PLUGIN_ROOT` in `deliver --verifier`, branch-keyed lock release after squash merge, and final audit requirements — see `references/pr66-current-status-refresh-lessons.md`. For PR67 skill-sync reviewer-fix lessons — preserving fail-closed helper subprocess semantics in copied lessons, patching repo and installed skill copies together, recovering from accidental post-PR amend by turning it into a normal follow-up commit, and restarting latest-head PR evidence after a fix push — see `references/pr67-skill-sync-review-fix-lessons.md`. For PR68 late async follow-up lessons — classifying delayed subagent feedback against merged state, turning cheap still-applicable test hardening into a tiny follow-up PR, and treating already-deleted remote branches as cleanup-state checks — see `references/pr68-late-async-test-followup-lessons.md`. For read-only skill-sync audit/planning lanes after recent PR merges, including mid-audit WIP detection, installed-vs-repo drift classification, private-path redaction requirements, and CURRENT_STATUS follow-up scope, see `references/read-only-skill-sync-audit-lessons.md`. For continuing a relay slice through agent-draft timeouts, stale lock cleanup, ignored-cache postflight recovery, and readiness evidence embedding, see `references/agent-draft-readiness-evidence-lessons.md`.

## Overview

Busdriver is the user's canonical coding pipeline/control plane. Hermes should be a Busdriver-aware second agent: intake, status, routing, Telegram/cron notification, and carefully bounded orchestration. Hermes must not become a shadow Busdriver and must not copy Busdriver's skills, hooks, MCP routes, plugins, marker logic, or gate implementations.

The durable split:

```text
Hermes = recognition, Phase 0 discovery, JIT source reads, read-only status, user interaction, notification, verification/finalization under gates
Busdriver/Claude Code = workflow authority, gates, reviews, MCP/plugin routing, canonical pipeline semantics
Codex = active implementation worker through Busdriver-approved handoff paths, never raw for repo-changing work
Hermes Delivery Mode = user-explicit operator path for branch/commit/PR/merge only after litmus/pre-PR and pr-grind-equivalent checks pass
```

**User expectation for repo-changing work:** all ordinary repo implementation should use this split. Hermes should not become the primary coding agent that hand-edits repositories. It should coordinate the Busdriver-equivalent pipeline, send implementation/fix work to Codex as the worker, reconcile the resulting dirty tree, then verify/finalize. Direct Hermes edits are a temporary, explicitly named bootstrap/emergency exception only when building or repairing the relay/pipeline itself and the Codex-worker path is not yet available; do not let that exception become the default workflow.

Critical safety fact: Busdriver's most important gates are Claude Code hook-runtime behavior. A normal Hermes shell running a Busdriver script does not automatically fire Claude Code `PreToolUse`/`PostToolUse` hooks. Never assume “script exists” or “dispatcher ran” means “gate fired.”

## When to Use

Use this skill when the user:
- asks whether Hermes can follow Busdriver pipelines;
- gives a coding/product idea and expects brainstorm → plan → grill behavior;
- asks about syncing Claude/Busdriver setup into Hermes;
- asks Hermes to launch/coordinate **Codex** (currently the only active agent) through Busdriver;
- asks for Busdriver status, routes, gates, MCP/plugin boundaries, or update strategy;
- asks to build Hermes-side Busdriver adapter/status/cron tooling.

**Current User Scope Policy (embedded preference):** Busdriver itself is the Claude-side workflow/control plane; `hermes-busdriver-relay` is the Hermes/Codex-side bridge/equivalent layer. Draft implementation launchers are still Codex-first unless a specific adapter is proven, but all relay-side decision/review anchors and voices (blueprint reviewers/arbiter, PR lead/backstop, council architect/pragmatist/critic/researcher/skeptic) should be configurable from a relay-owned JSON so Hermes can avoid using the same agent as both coder and reviewer. Do not put relay role config in `~/.claude/busdriver.json`; use relay config (default `~/.hermes/busdriver-relay/config.json`). Do not make Busdriver itself Claude-free unless the user explicitly asks; implement Codex/Hermes-side equivalents in the relay and label them as equivalents, not Busdriver-native Claude runtime.

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

If Claude/Busdriver reports `Unknown skill` for `busdriver:<skill>` and SessionStart injected `orchestrator SKILL.md not found at ~/.claude/plugins/cache/busdriver/busdriver/<version>/...`, treat it as a plugin cache/install mismatch, not a valid gate bypass. Inspect `~/.claude/plugins/installed_plugins.json`, the reported cache path, and `~/.claude/plugins/marketplaces/busdriver` metadata; do not create `skip-litmus.local`. Once the cache path contains `skills/orchestrator/SKILL.md`, `skills/litmus/SKILL.md`, and relevant hooks, the affected Claude session may still need `/reload-plugins` or a fresh session because the skill index was built while the cache was missing.

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
| Freeze/Guard | freeze marker active | hook | Do not edit outside scope; do not remove freeze marker. |
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
| Finishing | `finishing-a-development-branch`; after a successful Hermes Delivery Mode merge, automatically clean up Hermes-created linked worktrees/local branches and verify clean synced base; do not leave cleanup as “next time”. Inspect separate installed/marketplace clones before touching them. After Hermes coding via this relay, proactively push summary to claude-mem using claude-mem-log only when claude-mem access is configured/approved. |
| PR feedback/merge | `pr-grind`, `scripts/relevant-check-status.sh`, `scripts/ack-ledger.sh` |
| Codex handoff | `codex-goal-handover`, `scripts/codex/*` |
| MCP/plugin health | `mcp-health-check`, hook manifest, config/status scripts |

## Hermes Delivery Mode and PR Grind

Recommended relay orchestration topology: Main Hermes should act as orchestrator/operator/final verifier; relay CLIs should become the deterministic durable state machine and source of run artifacts; Codex/subagents should be bounded workers or reviewers whose self-reports are verified by main Hermes before any phase is marked complete. Do not let subagents own the whole delivery pipeline from the start, and do not leave long-term pipeline policy as transient main-session hand steps. For balanced parallel work, prefer a planning-only envelope first: allow multiple read-only review/status/scanning lanes in parallel, but keep mutating draft work single-flight through the gated agent-draft path, and keep finalization in Delivery Mode. Avoid positive authority-like field names such as `*_allowed=true` for non-authority facts; use descriptive non-authority names like `read_only_lanes_parallelizable`. See `references/orchestration-topology-lessons.md` and `references/balanced-agent-work-planning-lessons.md`.

Keep the distinction explicit: **relay surface** remains read-only/non-mutating for finalization unless a stronger Busdriver-approved integration surface is added; **Hermes Delivery Mode** is a user-explicit external operator procedure where main Hermes may perform ordinary Git/GitHub finalization only after litmus/pre-PR-equivalent checks, verification, latest-head PR-grind clean, merge, and cleanup. When updating docs/status, remove stale wording that makes these sound contradictory. See `references/pr33-completion-status-lessons.md`. When the next dogfood slice is finalization expansion, start with an ADR/integration-contract PR (e.g. repo `ADRs/0005-finalization-authority-integration-contract.md`) that defines authority sources, schema/evidence, marker ownership, fail-closed conditions, and non-goals before any mutating executor code. A safe follow-up is a read-only contract-status/capability-matrix helper that maps ADR unlock criteria to `policy_blocked` remaining-work rows while keeping every authority/capability flag false; see `references/pr35-finalization-contract-status-lessons.md`.

Default relay draft mode still cannot finalize. For implementation work, prefer the Codex-worker gate pattern (`hermes-busdriver-gate preflight → Codex draft → postflight → Hermes reconcile`) before any finalization. When a relay slice is fully merged/clean and the user says “continue” / “繼續”, choose the next smallest safe read-only/status/integration slice from current repo docs and Phase-0 evidence, then proceed through the same gates; do not pause to ask for a next task unless the next slice has a real product/scope trade-off. When the user explicitly tells Hermes to **complete all work** (commit, PR, merge, or similar delivery language), Hermes must not stop at a dirty tree and must not skip Busdriver's litmus/pre-PR or PR feedback loop. If the user also says to **use subagents** or complains that Hermes is doing the work inline (for example “不是你叫 subagent 做嗎”), stop inline implementation immediately: dispatch the next blocker-fix/implementation slice to subagents and keep main Hermes as operator/verifier/finalizer. Use a split such as reviewer triage + scoped fixer + read-only PR/status checker; subagents must not commit/push/merge. Re-read files after they return, verify with tools, then run amend/push/litmus/backstop/PR-grind/merge steps yourself under Delivery Mode. In that delivery mode, Hermes may perform Git/GitHub finalization only if it runs litmus/pre-PR-equivalent checks plus a pr-grind-equivalent loop:

1. Before committing or opening a PR, verify the current Busdriver litmus/pre-commit/pre-PR semantics for the target repo. If the Claude hook runtime cannot be proven to fire, run an equivalent explicit litmus/pre-PR check when available; otherwise bail instead of committing or creating the PR.
2. Create a branch and commit only after litmus/pre-PR-equivalent checks and local tests/smoke pass.
3. Push and open a PR with a body listing verification evidence.
4. Run PR grind semantics before merge:
   - inspect `gh pr checks` / `statusCheckRollup`;
   - run live Busdriver `scripts/relevant-check-status.sh` when available; explicit plugin-root arguments outrank env fallback roots;
   - inspect all actionable feedback surfaces for the latest head: inline review comments, PR review bodies, and top-level PR/issue comments;
   - fail closed if live GitHub feedback fetches fail; only use cached/offline inputs when all required feedback surfaces are supplied explicitly or the tool has an explicit fixture mode;
   - when paginating GitHub API feedback, use `gh api --paginate --slurp` or an equivalent multi-array parser;
   - wait with a bounded budget for advisory reviewer bots such as CodeRabbit, Devin, Cubic, Cursor, or Codex;
   - treat reviewer-bot rate-limit / quota / “couldn't start review” comments as incomplete reviewer state even if the GitHub status context says `SUCCESS`; do not merge until a real completed review exists or the bounded-wait policy explicitly bails to the user;
   - fix and push additional commits if feedback is actionable;
   - after **every** push, treat the previous clean/check/review state as invalidated and start the next wait/collect/fix round against the new PR HEAD;
   - repeat until the **latest PR HEAD** is clean, not merely until one review batch was fixed;
   - bail to the user on policy gaps, design/scope questions, failing required checks, max-wait exhaustion, or unclear reviewer state.
5. Merge only after the latest PR HEAD is clean by current Busdriver/pr-grind semantics. Never enable GitHub auto-merge as a substitute for pr-grind, and never merge immediately after a fix push without waiting for the next round of checks/reviewer bots.
6. After merge, sync the PR base branch discovered from PR status (not hard-coded `main`), verify the final state, perform automatic post-merge housekeeping for Hermes-created branches/worktrees (fetch/prune, remove the agent worktree, delete the local branch after squash merge, verify the remote branch is gone, and end on clean base), and push a claude-mem summary only when claude-mem access is configured/approved; otherwise report the summary in Hermes and rely on Hindsight.

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
- `scripts/hermes-busdriver-runtime-check`: Hermes-owned read-only H13 checker; normal result blocks mutating launcher (`mutating_launcher_allowed=false`). It should report `runtime_equivalence.authorization_sources` to separate observed Claude-hook-shaped stdin, equivalent gate runner availability, and local draft routing while keeping every `authorized_here` / finalization flag false. See `references/h13-runtime-authorization-reporting-lessons.md`.
- `scripts/hermes-busdriver-gate`: Hermes-owned equivalent preflight/postflight gate runner for draft-mode agents; normal pass allows `agent_implementation_draft_allowed=true` while keeping commit/push/PR/merge false.
- `scripts/hermes-busdriver-status`: Also reports relay-owned configurable equivalents for all relay reviewer/voice anchors, including `relay.blueprint.*`, `relay.pr.*`, `relay.council.*`, and `relay.litmus.reviewer`. These are logical Hermes agent/model routes from a separate relay config JSON (default `~/.hermes/busdriver-relay/config.json`), not shell CLI names, and never grant Busdriver-native Claude runtime authority. Current relay policy is Codex-only: default routes are `["codex"]`, `avoid_coding_agent_for_review=false`, and status reports `role_policy=codex_only_relay_equivalents` plus `review_independence_policy=same_codex_agent_allowed_by_current_user_directive` so the temporary same-agent review posture is explicit rather than silent. Relay config shape is root-level `{ "coding_agent": "codex", "avoid_coding_agent_for_review": false, "routes": { "relay.pr.backstop": ["codex"] } }`; `coding_agent` must be a non-empty string, `avoid_coding_agent_for_review` must be boolean, `routes` must be an object, and each route value must be a non-empty string or an array of non-empty strings. Invalid/malformed config is reported as degraded/fail-closed (`selected_agent=null`) instead of silently falling back healthy; see `references/relay-configurable-roles-lessons.md`.
- `scripts/hermes-busdriver-relay-role`: Read-only dispatcher-facing resolver for a single relay equivalent role. It must invoke `scripts/hermes-busdriver-status` as a subprocess (not via `importlib`/`SourceFileLoader`) and parse its stdout JSON. It returns `schema=hermes-busdriver-relay-role/v0`, exits 0 only when the role has a non-degraded string `selected_agent`, the selected role entry shape is valid, and no top-level relay config errors exist; exits nonzero for unknown/degraded/malformed config, malformed status subprocess output, status timeout/failure, or invalid CLI invocations. Every exit path must keep JSON-on-stdout fail-closed authority markers at both root and nested `decision` (`dispatch_allowed=false` except the one safe resolved role, `mutation_allowed=false`, `finalization_allowed=false`, `not_busdriver_native_claude_runtime=true`). See `references/relay-role-resolver-lessons.md` for backstop-driven pitfalls: top-level config errors must block dispatch even if a selected role looks healthy, every payload shape including `--list-roles` needs root authority flags, invalid argparse paths and abbreviated long options (`allow_abbrev=False`) must not fall back to plain-text stderr/empty stdout, status subprocess timeouts must be longer than child probe timeouts, and all status JSON shapes must be revalidated before dispatch.
- `scripts/hermes-busdriver-agent-draft`: Launcher that acquires the Hermes lock, runs gate preflight, executes **Codex** (current proven mutating draft surface) or custom/noop test commands in draft mode under a best-effort PATH guard, runs postflight, and returns `needs_busdriver_review`.
- `scripts/hermes-busdriver-agent-balance-plan`: Read-only planning envelope for balanced agent work. It describes one gated mutating draft lane plus parallel read-only review/status lanes, keeps every dispatch/programmatic/finalization/commit/push/PR/merge/deploy/release/publish/marker-write/repo-mutation authority flag false, and does not call Codex/GitHub, launch subagents, mutate repos, or write markers.
- `scripts/hermes-busdriver-agent-smoke`: Optional real-agent adapter smoke; creates a throwaway repo and may consume provider quota/tokens. Codex has been verified with it; other mutating agents require explicit adapter validation.
- `scripts/hermes-busdriver-delivery-status`: Read-only Delivery Mode status envelope that combines repo state, Busdriver PR-grind source availability, relay capabilities, lock/run summaries, optional relay-role resolution evidence via `--relay-role` / `--relay-config`, optional sanitized litmus/pre-PR freshness evidence from `hermes-busdriver-litmus-status`, optional Busdriver drift-baseline evidence via Phase-0 `hermes-busdriver-status --drift-baseline`, and optional PR-grind readiness output; it never authorizes or performs finalization. A non-dispatchable optional relay role is reported as a warning, not as merge/commit authority. Treat litmus-status `decision.status=blocked`, unknown/unrecognized `decision.status`, top-level `ok=false`, non-boolean `ok`, malformed/read-only/schema-invalid payloads, unsafe authority flags (including deploy/release/publish/marker-write), stale result-file evidence not bound to the current repo/HEAD/diff identity, missing/unavailable helper evidence, helper subprocess timeouts, and nonzero subprocess exits as fail-closed blockers rather than warning-only evidence. Treat supplied drift baselines that are missing, invalid, unsupported-schema, drifted, or whose Phase-0 status output is malformed/unavailable as fail-closed handoff blockers; status-probe `ok=true` with `busdriver_drift.finalization_compatible=false` means evidence collection succeeded but finalization remains blocked. When invoking Phase-0 status for drift evidence, always pass the requested repo and preserve the caller cwd so relative `--drift-baseline` / `--plugin-root` paths keep caller semantics instead of silently inspecting/chdiring into the relay checkout. Sanitized litmus evidence must be allowlisted (repo/state_dir/known marker keys only), must redact allowlisted string values as well as raw diagnostic tails, must normalize copied top-level primitives (`schema` allowlist only, booleans only for `read_only`/`ok`) and decision flags before emitting delivery/finalization JSON, and must thread the Busdriver marker state dir through wrapper layers (`deliver` / `finalization-readiness` → `delivery-status --busdriver-state-dir-name` → `litmus-status --state-dir-name`) so `.opencode` or custom state dirs do not silently fall back to `.claude`; see `references/delivery-litmus-status-integration-lessons.md`, `references/delivery-litmus-pr-mode-lessons.md`, and `references/drift-baseline-delivery-guard-lessons.md`.
- `scripts/hermes-busdriver-deliver`: Fail-closed Delivery Mode dispatcher. Plan mode is read-only. Verify-only execution may run local verifier argv commands and write Hermes-owned run artifacts, and `execute --operation pr-grind` may wrap the read-only bounded PR-grind loop and write a Hermes-owned run artifact, but both still keep commit/push/PR/merge/deploy/release/publish/marker-write disabled. Every result carries a durable `hermes-busdriver-delivery-run/v0` envelope (`run_id`, phase, status, reason, repo/PR identity, authority flags, and artifact references); `--run-id` provides a stable run identity for operator/subagent/cron handoff while artifact filenames still add timestamp/PID uniqueness. `--mode status --run-id <id>` is a read-only lookup of the latest valid matching Hermes-owned run artifact; it validates versioned deliver/run envelopes plus fail-closed decision/authority metadata, preserves artifact repo/PR identity, returns artifact path plus sanitized metadata instead of verifier output tails, and does not run delivery-status, verifiers, PR-grind, or repo mutations. When deliver wraps delivery-status and forwards nested PR-grind/litmus/relay-role/Phase-0 drift-status timeouts, its own default/effective timeout must cover those nested budgets plus margin so delivery-status can emit structured fail-closed JSON instead of being killed by the wrapper; forward `--relay-role`/`--relay-config` with `--relay-role-timeout` only when relay-role evidence is requested, and `--drift-baseline` with `--phase0-status-timeout` only when drift evidence is requested. See `references/deliver-run-envelope-lessons.md` for status-lookup pitfalls including legacy v1 authority flags, latest failed artifacts, sanitized artifact refs, and stale-review-thread resolution during PR-grind, and `references/delivery-litmus-pr-mode-lessons.md` for nested timeout budget regressions.
- `scripts/hermes-busdriver-litmus-status`: Read-only litmus/pre-PR marker freshness helper. It computes the current HEAD and Busdriver-style branch diff hash with the same plain `git diff` semantics as Busdriver's PR gate, fails closed instead of executing external diff/textconv/diff-driver configuration or hashing through `.gitattributes`, `$GIT_DIR/info/attributes`, or `core.attributesFile` diff selection, reports whether `.claude/litmus-passed.local`, `.claude/pr-codex-lead.local.json`, `.claude/pr-backstop-verdict.local.json`, and `.claude/pr-review-passed.local` are fresh by current Busdriver gate semantics, fingerprints marker text / summarizes JSON fields instead of echoing raw contents, refuses state-dir symlink components or marker symlinks and refuses non-regular/oversized marker files, requires timestamp-fresh PR artifacts, treats empty PR diffs as unavailable, treats commit markers older than or equal to the current HEAD timestamp as stale, strips Git env vars that can alter pathspec semantics or write trace files, resolves default PR base from `origin/HEAD` before `origin/main`, and never writes markers or grants finalization/commit/push/PR/merge authority. See `references/litmus-status-helper-hardening-lessons.md` for hardening pitfalls discovered through litmus/backstop review, `references/litmus-status-pathspec-env-pr-grind-lessons.md` for the PR-grind blocker where inherited `GIT_*PATHSPECS` variables made nested `.gitattributes` probes unsafe unless stripped, and `references/litmus-status-codex-pr-review-hardening.md` for Codex PR-mode blocker lessons covering JSON argparse envelopes, no-follow state metadata, trace-env stripping, default-base parity, strict marker freshness, unsafe/default-global attributes, bounded Git subprocesses with fail-closed safety probes, parser no-leak invariants, and verification-doc version consistency.
- `scripts/hermes-busdriver-finalization-readiness`: Read-only finalization readiness helper that combines delivery status with Phase-0 status and emits a `hermes-busdriver-handoff/v0` envelope for Busdriver/Claude or an explicit operator finalizer. It must strictly validate the top-level delivery-status child envelope before using readiness evidence: expected schema, `read_only is True`, and boolean `ok`; invalid envelopes are blockers, not handoff-ready evidence. It can pass optional relay-role resolution, sanitized litmus evidence, Busdriver drift-baseline evidence, machine-readable `finalization_guardrails`, read-only `dual_review_readiness` evidence, and embedded read-only `finalization_contract_status` evidence into the handoff. Contract-status evidence should be validated as a nested helper payload (`schema=hermes-busdriver-finalization-contract-status/v0`, `read_only=true`, `ok=true`, recursive authority/capability booleans false) and surfaced at top-level plus `handoff_envelope.finalization_contract_status` and `handoff_envelope.evidence.finalization_contract_status`; downstream consumers should not need to call a second helper for the ADR 0005 capability matrix. The dual-review envelope surfaces `relay.litmus.reviewer`, `relay.pr.lead`, and `relay.pr.backstop` route readiness as advisory status only while keeping programmatic execution/dispatch disabled; it does not implement programmatic litmus/pre-PR dual review or remove that item from remaining work. The helper has no execute mode and keeps commit/push/PR/merge/deploy/release/publish/marker-write authority false. When it wraps delivery-status, its timeout budget must cover every nested delivery-status child budget (PR-grind, litmus-status, relay-role resolution, Phase-0 status/drift baseline, plus margin) so the child can return structured fail-closed JSON instead of being killed by the wrapper; forward matching timeout flags such as `--relay-role-timeout` with `--relay-role`, and `--phase0-status-timeout` alongside `--drift-baseline`. See `references/pr30-pr31-dual-review-readiness-lessons.md` for guardrail/dual-review envelope and PR-grind lessons, and `references/pr36-finalization-readiness-contract-status-lessons.md` for contract-status embedding and hash-binding pitfalls.
- `scripts/hermes-busdriver-pr-grind-check`: Read-only Delivery Mode helper that checks latest PR HEAD mergeability, relevant checks via Busdriver `scripts/relevant-check-status.sh` when available, and current-head review comments/reviews. It returns `clean` / `wait` / `needs_fix` / `blocked` and never writes Busdriver markers or merges. Treat `mergeStateStatus=UNSTABLE` and `UNKNOWN` as `wait` (never `clean`), fail closed on live feedback-fetch or relevant-check-script errors, use `gh api --paginate --slurp` for paginated review surfaces, and block if the PR head changes during collection. PR grind is a loop: after every fix push, wait for the next reviewer/check round before deciding. If relevant checks/reviewer bots are pending, classify as `wait` before acting on stale comments from prior heads. Active unresolved GitHub review threads remain blockers until fixed or explicitly resolved after evidence shows the finding is addressed; resolving review threads is a GitHub mutation and should happen only as part of an explicit PR-grind finalization path, never to bypass unaddressed feedback.
- `scripts/hermes-busdriver-pr-grind-loop`: Read-only bounded PR-grind polling loop that repeatedly invokes the checker until clean / needs-fix / blocked / max-wait, re-polls after latest-head drift, delegates ack-ledger interpretation to the checker, refuses fix rounds, and keeps all finalization authority false.
- `references/deliver-pr-grind-dispatcher-lessons.md`: implementation pitfalls for wrapping the read-only PR-grind loop inside `hermes-busdriver-deliver`: validate schema/version/read-only and nested authority flags before accepting clean, require subprocess exit `0` plus payload `ok=true`, never expose script/fixture override knobs in the production dispatcher, and write failed handoff artifacts only when `--pr` is present.
- `references/deliver-pr-grind-delivery-loop-lessons.md`: delivery-loop lessons from PR-grind execution work: recompute diff hashes after every amend/push, rerun PR-mode Codex lead plus read-only backstop before any trusted marker handoff, require latest-head PR-grind clean before merge, and cover reviewer-found pitfalls such as nested decision status mismatch, TimeoutExpired bytes, no-verifier artifacts, and operation-aware step labels.
- `references/deliver-pr-grind-reviewer-fix-loop-lessons.md`: delivery-loop lessons from PR-grind reviewer feedback: every amended commit needs a fresh diff hash, PR-mode Codex lead, read-only backstop, trusted marker handoff only through Busdriver/Claude runtime, normal follow-up commits for PR feedback, and latest-head PR-grind restart; also covers regression cases for nested decision status consistency, timeout bytes JSON safety, no-verifier artifacts, and operation-aware step labels.
- `references/delivery-litmus-status-integration-lessons.md`: delivery-status/finalization-readiness litmus evidence integration pitfalls: blocked/`ok=false` litmus status and nonzero helper subprocess exits must remain fail-closed blockers, never warning-only handoff evidence.
- `references/pr-grind-delivery-discipline.md`: captured user correction for end-to-end Hermes delivery expectations and exact Busdriver pr-grind latest-head loop semantics.

- `references/pr-grind-readiness-checker-lessons.md`: implementation pitfalls for the read-only readiness checker: latest-head binding, fixture-mode vs live fail-closed behavior, GitHub pagination, plugin-root precedence, unstable/unknown merge state handling, GraphQL resolved/outdated thread filtering, current-review-round filtering, narrow bot progress-comment suppression, literal advisory filtering, active unresolved review-thread handling, approved-with-caveat review-body handling, same-reviewer review supersession, bot prior-round inline-comment supersession, review-thread nested pagination, and issue-comment head activity cutoffs. For resolved/stale feedback, prefer GraphQL review-thread state (`isResolved`, `isOutdated`, `databaseId`); do not rely on REST `resolved` fields, commit timestamps, or `commit_id` alone. Active unresolved/non-outdated threads can remain actionable across pushes; outdated threads are stale and should not block even when unresolved; dismissed/pending parent reviews must still be ignored. Approved reviews are not automatically clean if their body contains actionable caveats, but harmless exact approval text (`Ship it`, `Great work`, etc.) and cubic `No issues found` summary reviews should not block. If checks or reviewer bots are pending, classify as `wait` before acting on stale comments; after a fix push, restart the whole wait/collect/fix loop against the new HEAD.
- `references/reviewer-report-and-pr-grind-lessons.md`: workflow for saving reviewer-quality reports as durable relay references plus live lessons from reviewer-bot signals (cubic no-issues summaries, Devin/CodeRabbit completion vs clean state, and outdated thread handling).
- `references/pr-grind-delivery-mode-lessons-2026-06-28.md`: delivery-mode lessons from merging relay PR #14/#15 end-to-end: handling `BEHIND` PR branches with `gh pr update-branch`, restarting latest-head PR-grind after every push, reproducing Busdriver PR diff hashes with command-substitution newline semantics, manually invoking post hooks when Hermes finalizes outside Claude runtime, strict marker freshness comparison, and post-merge cleanup/CI verification.
- `references/pr-grind-watcher-finalizer-guard-lessons.md`: read-only watcher/finalizer-guard pattern for waiting on a new PR, running bounded latest-head PR-grind if it appears, and re-verifying final branch/dirty state because another worker may drift the worktree during the watch.
- `references/h7-drift-schema-pr-gate-lessons.md`: H7 drift-baseline schema compatibility lesson plus Delivery Mode pitfall: PR-mode Codex lead PASS is not sufficient for `gh pr create`; if Hermes cannot dispatch/write the required read-only Opus backstop through Busdriver/Claude trusted writers, stop before push/PR and report a verified-draft blocker.
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

**Read-only marker-status helper pitfalls:** when building or reviewing relay helpers that report litmus/pre-PR marker freshness, JIT-read live Busdriver gate/writer semantics first and follow `references/litmus-marker-freshness-lessons.md`. In particular, do not follow marker symlinks or echo raw marker contents; PR review artifacts need `status == PASS`, matching `diff_hash`, and fresh integer `ts` within the current max-age; and `litmus-passed.local` must not be treated as fresh by an invented `HEAD`-equals-marker rule unless live `pre-commit-gate.sh` says so.

## Dirty Tree and Reconciliation

Before approved repo-changing dispatch, check dirty tree. If dirty, fail closed unless Busdriver source says allowed and the dirty state is explicitly included in the handoff. If the user explicitly says to include/push an already-tracked dirty project-guide change such as `.claude/CLAUDE.md`, verify the diff is intentional and small, include it in the active Delivery Mode PR, and check matching docs like `README.md` for descriptor consistency; do not keep calling it unrelated after the user has claimed it.

After dispatch, reconcile dispatcher-reported files, actual git status/diff, committed SHA, unclaimed/ignored changes, out-of-scope changes, verifier output, and exit code. Any mismatch is `blocked` / `needs review`, not success.

Ignored-file postflight checks can fail because of concurrent local daemons or caches (for example `.codegraph/*`) even when the tracked diff is scoped and tests pass. Treat that as a real gate blocker: do not delete or normalize unrelated ignored state blindly. Report the ignored-file blocker, or re-run a read-only/verify gate only after the ignored state is stable and the tracked diff remains exactly scoped.

Agent-draft PATH guards shadow finalization commands (`git commit`, `git push`, `gh pr create`, `gh pr merge`). Do not run full verifier suites inside the draft launcher if they create temp repos and commit as part of tests; those tests can fail because the guard is correctly blocking commits. Put a narrow scoped verifier inside the agent-draft run, then run full contract suites from Hermes/operator verification after the draft returns.

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
6. read-only `hermes-busdriver-agent-balance-plan` for planning one mutating draft lane plus parallel read-only review/status lanes without dispatch authority;
7. opt-in `hermes-busdriver-agent-smoke` for real Codex adapter smoke tests;
8. advisory/user-facing routing that tells the user when finalization still needs Claude Code / Busdriver or stronger equivalent gates.

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

See also `references/claude-mem-push.md` (Hermes→claude-mem push patterns after coding), `references/user-preferences-profiles-mcp-agents.md` (direct remote action preference, three-memory-system coordination), `references/june-2026-pr-reviewer-quality-evaluation.md` (reviewer-specific pr-grind policy from June 2026 PR review evaluation), `references/end-to-end-pr-grind-and-redaction-lessons.md` (Dependabot major-version PR-grind, linked-worktree merge cleanup, and delivery verifier redaction pitfalls), `references/pr-grind-delivery-mode-lessons-2026-06-28.md` (end-to-end PR #14/#15 delivery-mode lessons), `references/h13-runtime-authorization-reporting-lessons.md` (runtime authorization source reporting and H13 delivery lessons), `references/continuation-subagent-dispatch-lessons.md` (how to respond when the user says to continue completing relay with subagents: refresh Phase 0, choose the next narrow safe slice, dispatch immediately, and keep main Hermes as verifier/finalizer), `references/continuation-pr25-subagent-review-lessons.md` (continuation lessons for divergent PR branches, latest-head reviewer-bot blockers, nested timeout forwarding, sanitized boolean evidence, and precise resume points), `references/delivery-litmus-pr-mode-lessons.md` (end-to-end litmus evidence PR-mode lessons: fail-closed status validation, redacted allowlisted summary values, nested timeout budgets, trusted writer sequencing, and PR-grind actionable-comment cleanup), `references/pr25-pr26-delivery-lessons.md` (PR #25/#26 follow-through: use subagents when corrected, verify all wrapper forwarding layers, normalize copied litmus primitives, resolve addressed review threads only after evidence, and pick a small docs/status slice after merge), `references/drift-baseline-delivery-guard-lessons.md` (H7 drift-baseline evidence in delivery/finalization status, fail-closed compatibility handling, and timeout-forwarding pitfalls when adding nested Phase-0 subprocesses), `references/pr30-pr32-completion-loop-lessons.md` (continuing through PR #30–#32: body-file PR creation, latest-head PR-grind, resolved addressed threads, advisory evidence summaries, recursive raw litmus authority scanning, and completion audit boundaries), `references/pr33-completion-status-lessons.md` (docs/status completion pass: keep relay-surface policy-blocking distinct from user-explicit Hermes Delivery Mode, fix contradictory authority guidance, and verify final completion state), `references/pr35-finalization-contract-status-lessons.md` (ADR 0005 follow-up: read-only contract-status capability matrix, include user-claimed tracked `.claude/CLAUDE.md` changes in Delivery Mode PRs, descriptor consistency, and linked-worktree squash-merge cleanup), and `references/pr38-pr39-policy-blocked-status-lessons.md` (align readiness guardrail `remaining_work` statuses with ADR 0005 `policy_blocked` semantics, pair code/status slices with docs refreshes, recover accidental main commits safely, and handle reviewer quota comments explicitly).

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
- [ ] After a successful Delivery Mode merge, post-merge housekeeping is complete: base branch synced, post-merge verification passed, Hermes-created worktree removed, local branch deleted, remote branch absent, and final status clean.
- [ ] Respect current Codex-only active agent scope policy.
