# Hermes ↔ Busdriver Integration Contract v2

**Status:** Patched after Ultra Council review — suitable as source material for the Hermes `busdriver-relay` skill and read-only/narrow draft tooling, but **not** authorization for finalizing repo-changing launcher automation.  
**Observed snapshot:** Busdriver `1.71.0` at `/Users/vfrvndtt/.claude/plugins/marketplaces/busdriver` on 2026-06-25. Observed paths/counts are diagnostic only; durable instructions must use symbolic runtime variables.

## 0. Executive Position

Hermes should be a **Busdriver-aware relay/intake layer + read-only status/notifier + narrow draft launcher only after proof**, not a clone of Claude Code or Busdriver.

```text
User / Telegram / Cron
  → Hermes runtime discovery + intake classification
  → JIT-read current Busdriver source-of-truth
  → if repo-changing: only use a Busdriver-approved launcher that proves hook/runtime equivalence or refuses gated operations
  → Busdriver/Claude/Codex owns execution, gates, commits, PRs, MCP/plugin routes
  → Hermes reports verified artifacts and blockers back to the user
```

**Hard boundary:** Hermes owns recognition, runtime discovery, read-only status, user interaction, and notification. Busdriver owns coding workflow, gates, reviewer routing, MCP/plugin use, execution, commits, PR grind, and source-of-truth skill content.

**Critical correction from council:** Busdriver gates are primarily Claude Code hook runtime (`PreToolUse`, `PostToolUse`, etc.). A Hermes bare shell running `codex-goal-dispatch.sh` does **not** automatically execute Claude Code hooks. Therefore v1 must not assume “calling Busdriver scripts” means “Busdriver gates fired.”

## 1. Diagnostic Completeness Snapshot

This contract was drafted after reading/scanning:

- metadata: `package.json`, `.claude-plugin/plugin.json`;
- user config: `~/.claude/busdriver.json`;
- active hook manifest: `hooks/hooks.json`;
- orchestrator: `skills/orchestrator/SKILL.md`, `tasks-catalog.md`, `domain-supplements.md`, `references/hooks-reference.md`, `references/gate-recovery.md`;
- supplements: `skills/supplements/MANIFEST.md`;
- core skills: `brainstorming`, `writing-plans`, `blueprint-review`, `litmus`, `pr-grind`, `verification-before-completion`, `verification-loop`, `codex-goal-handover`, `council`, `grill-me`, `using-git-worktrees`, `systematic-debugging`, `requesting-code-review`, `receiving-code-review`, `gateguard`, `safety-guard`;
- execution scripts: `scripts/lib/resolve-cli.sh`, `scripts/codex/codex-goal-dispatch.sh`, `scripts/codex/goal-result.schema.json`, `scripts/lib/ultra-oracle.sh`, `scripts/doctor.js`, status/health scripts where present;
- programmatic inventory: hundreds of skills/commands/agents/scripts.

These counts and local paths are **not durable policy**. The durable policy is the dynamic discovery/read-on-demand model below.

## 2. Symbolic Runtime Variables

A Hermes skill or script must not bake in observed absolute paths. Use symbolic runtime values:

| Symbol | Meaning |
|---|---|
| `$BUSDRIVER_PLUGIN_ROOT` | Resolved Busdriver plugin root. Fallback may be `$CLAUDE_PLUGIN_ROOT` or known install discovery. |
| `$BUSDRIVER_STATE_DIR` | Harness state dir, default `.claude`; opencode may use `.opencode`. Must be sanitized exactly as Busdriver scripts do. |
| `$BUSDRIVER_USER_CONFIG` | Usually `$HOME/$BUSDRIVER_STATE_DIR/busdriver.json` for Busdriver user config. |
| `$REPO_ROOT` | Canonical current git repo root. |
| `$PROJECT_CWD` | Current working directory inside project/worktree. |
| `$HERMES_STATE_DIR` | Hermes-owned integration state, under `~/.hermes/...`, not `.claude/`. |

Observed paths may appear in diagnostics only.

## 3. Phase 0 — Mandatory Runtime State Discovery

Before any repo-changing route, Hermes must perform Phase 0. If any required item cannot be read, Hermes must **fail closed** for repo-changing work.

Hermes must resolve/read:

1. current repo root, cwd, branch, and worktree identity;
2. dirty tree state: staged, modified, untracked, merge/rebase/cherry-pick state, detectable stash/apply state;
3. active freeze/scope/careful markers under the current `$BUSDRIVER_STATE_DIR`;
4. current Busdriver plugin root and package metadata;
5. current Busdriver user config;
6. active hook map from `$BUSDRIVER_PLUGIN_ROOT/hooks/hooks.json`;
7. orchestrator source-of-truth files;
8. supplement manifest;
9. relevant plan/design/review marker state;
10. current PR/CI/check status when PR/merge is involved;
11. whether another Hermes/Busdriver run is active for the same repo/worktree/operation class;
12. whether the requested operation has external side effects or data egress.

Hermes must not rely on a previous-session summary of these files. Reads are **JIT only**.

## 4. Dynamic Gate Discovery Beats Static Skeleton

The built-in Hermes gate skeleton is a minimum alerting map, not an exhaustive authority.

At runtime, Hermes must:

- read live `hooks/hooks.json`;
- identify hooks relevant to the intended operation type;
- verify referenced gate scripts exist and are readable;
- read `orchestrator/SKILL.md` and `references/hooks-reference.md`;
- warn/fail closed if expected hooks are missing, renamed, disabled, or unreadable;
- never assume a gate exists merely because this Hermes contract mentions it.

If Busdriver adds/renames a gate, Hermes status must detect drift by comparing live `hooks/hooks.json` to its minimum remembered gate skeleton.

## 5. Workflow Skeleton Hermes May Remember

Hermes may remember the high-level routing skeleton:

```text
Phase 0 runtime discovery
  → Phase 1 brainstorming
  → Phase 2 writing-plans
  → Phase 3 worktree / baseline
  → Phase 4 execution
  → Phase 5 verification / review
  → Phase 6 finishing / PR / merge
```

Entry routing:

| User/task state | Busdriver entry | Hermes behavior |
|---|---|---|
| Vague idea/exploring | `brainstorming` | Run idea intake, JIT-read Busdriver brainstorming if proceeding. |
| Clear requirements/spec | `writing-plans` | Plan before implementation. |
| Existing plan | `using-git-worktrees` + design review | Verify plan/gates before execution. |
| Small specific task | Phase 4 only if genuinely small | Still apply Phase 0, verification, review, litmus/finalization rules. |
| Bug/test failure | `systematic-debugging` | Root cause before fix; freeze may apply. |
| Test-writing | `/tdd`, TDD skills | Test-specific route, still evidence-first. |
| Unclear route | Ask one clarifying question | Do not invent a route. |

Hermes must JIT-read the corresponding Busdriver skill before mirroring any detailed phase behavior.

## 6. Minimum Gate / Discipline Skeleton

Add column `Enforced by` because some are mechanical hooks and some are prompt-level disciplines.

| Gate/discipline | Trigger | Enforced by | Source-of-truth | Hermes rule |
|---|---|---|---|---|
| Brainstorming hard gate | creative/feature/behavior work | prompt discipline | `skills/brainstorming/SKILL.md` | No implementation until design is presented and approved. |
| Blueprint Review | plan/design/architecture doc | hook + skill | `blueprint-review`, `check-design-document.sh`, `pre-implementation-gate.sh` | Do not implement while design is unreviewed. |
| Pre-implementation | Write/Edit/MultiEdit/Bash while design unreviewed | hook | `pre-implementation-gate.sh` | Never route around it. |
| Litmus pre-commit | commit/finalize | hook in Claude runtime + skill loop | `litmus`, `pre-commit-gate.sh` | Every commit requires current Busdriver litmus semantics. Hermes bare shell cannot assume this fired. |
| Litmus pre-PR | `gh pr create` | hook in Claude runtime | `litmus`, `pre-pr-gate.sh` | PR creation requires current review marker semantics. |
| Pre-merge / PR grind | `gh pr merge` | hook in Claude runtime + skill loop | `pr-grind`, `pre-merge-gate.sh` | Do not merge unless Busdriver says clean. |
| Freeze/Guard | freeze marker active | hook | `freeze-guard.sh`, `safety-guard` | Do not edit outside scope; do not remove freeze marker. |
| Careful/destructive guard | destructive/high-risk Bash | hook | `careful-guard.sh`, `safety-guard` | Require human-visible stop. |
| GateGuard | first edit/write/destructive action when enabled | opt-in hook | `gateguard`, `gateguard-fact-force.js` | Treat as hard stop if active; gather concrete facts before action. |
| Block no-verify | git hook bypass flags | hook | `block-no-verify.js` | Never use bypass flags. |
| Verification before completion | success/done claims | prompt discipline | `verification-before-completion` | No completion claim without fresh evidence. |
| Code review after task | task completion/major feature/before merge | prompt discipline + agents | `requesting-code-review`, reviewers | Route to Busdriver review discipline; do not trust self-report. |
| Build failure resolver | build/test/lint failure | prompt discipline + agents | orchestrator build resolver rules | Dispatch resolver/systematic debugging; no guess-fix first. |
| Security review | auth/input/API/payments/secrets | prompt discipline + agents | orchestrator Phase 5 | Dispatch security review/scan as appropriate. |
| Worktree/baseline | nontrivial repo work | skill discipline | `using-git-worktrees`, `writing-plans` | Isolated worktree/baseline before execution unless user explicitly overrides. |
| PR feedback loop | open PR needing CI/comment resolution | skill discipline | `pr-grind` | No auto-merge; pr-grind owns grind/merge semantics. |
| Deploy/release/publish | external release/deploy | human + Busdriver route | deployment/release skills if any | Out of v1 unless explicit approved Busdriver entrypoint + user approval. |

## 7. Source-of-Truth Read Map

### Always read live for nontrivial routing/status

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

### Phase-specific reads

| Concern | Read JIT |
|---|---|
| Idea/design intake | `skills/brainstorming/SKILL.md` |
| Stress/adversarial decisions | `skills/grill-me/SKILL.md`, `skills/council/SKILL.md` |
| Plan writing | `skills/writing-plans/SKILL.md` |
| Plan/design gate | `skills/blueprint-review/SKILL.md` |
| Worktree | `skills/using-git-worktrees/SKILL.md` |
| Execution | `subagent-driven-development`, `executing-plans`, `dispatching-parallel-agents` |
| Debugging | `systematic-debugging`, optional `diagnose` |
| TDD | `test-driven-development`, `tdd-workflow` |
| Verification | `verification-before-completion`, `verification-loop` |
| Code review | `requesting-code-review`, `receiving-code-review`, domain reviewers |
| Commit/PR/deploy | `litmus` plus live hooks |
| Finishing | `finishing-a-development-branch` |
| PR feedback/merge | `pr-grind`, `scripts/relevant-check-status.sh`, `scripts/ack-ledger.sh` |
| Codex handoff | `codex-goal-handover`, `scripts/codex/*` |
| Gate recovery | `orchestrator/references/gate-recovery.md` |
| MCP/plugin health | `mcp-health-check.js`, hook manifest, Busdriver config/status |
| Status/doctor | `scripts/doctor.js`, status scripts if present, `resolve-cli.sh --json` |

Hermes may read marker existence/freshness only to verify status. Hermes must never write, forge, consume, or delete Busdriver markers unless a current Busdriver source explicitly instructs that exact operation as part of an approved flow.

## 8. Execution Seam Classification

Every Busdriver capability must be classified before Hermes tries to use it.

| Class | Meaning | Hermes v1 action |
|---|---|---|
| Standalone read-only shell seam | Safe status/read command outside Claude runtime | Allowed after Phase 0 and read-only classification. |
| Standalone mutating shell seam | Can change repo/external state outside Claude runtime | Not allowed until hook-runtime equivalence + settling checks pass. |
| Requires Claude Code session | Skill/agent/command/hook-dependent behavior | Hermes must route to user/Claude side or spawn a verified Claude session only if explicitly approved later. |
| Requires MCP/plugin | Tool exists only in Claude Code/MCP/plugin | Hermes must not synthesize/call it; route to Busdriver/Claude side. |

### Known seams

- `scripts/lib/resolve-cli.sh --json`: standalone read-only status, but it reports default review CLI + CLI availability; it does **not** fully resolve every role route. Status must separately inspect route keys such as `blueprint-review.reviewer_3` and `council.researcher`.
- `scripts/codex/codex-goal-dispatch.sh`: standalone mutating primitive candidate; not v1-authorized until it proves hook-runtime equivalence or is constrained local-only/no-finalization.
- `scripts/codex/goal-result.schema.json`: Codex self-report schema, not a complete final dispatcher envelope schema.
- `scripts/lib/ultra-oracle.sh`: advisory shell adapter; allowed only after standalone check and data-boundary approval. It is not equivalent to invoking the whole `council` skill.
- `skills/council/SKILL.md`, `skills/brainstorming/SKILL.md`, etc.: skill content requiring a live Busdriver/Claude-style skill runtime for actual invocation; Hermes may read them but not “invoke” them by reading alone.

## 9. Hook-Runtime Equivalence Requirement

Hermes must not assume Busdriver gates are enforced merely because gate scripts exist on disk.

Before Hermes can use any launcher for repo-changing work, the launcher must prove one of:

1. it enters the same Claude Code / Busdriver hook runtime that would enforce gates;
2. it explicitly invokes Busdriver-equivalent gate checks itself;
3. it refuses gated operations and returns a blocked status;
4. it is explicitly constrained to local-only work and cannot push/PR/merge/deploy/finalize.

If this cannot be proven, Hermes may use the launcher only for read-only or non-mutating operations.

For v1, Hermes must not directly run `git commit`, `git push`, `gh pr create`, `gh pr merge`, deploy, release, publish, or raw repo-mutating `codex exec`.

## 10. Direct Command Ban

Hermes must not directly run repo-mutating or external-side-effect commands except through a proven Busdriver-approved launcher.

Forbidden direct operations include at minimum:

- `git commit`, `git push`, `git reset`, `git rebase`, `git merge`, destructive checkout;
- `gh pr create`, `gh pr merge`, GitHub issue/comment mutation;
- raw `codex exec` for repo-changing work;
- direct Claude Code plugin commands;
- direct MCP mutation calls;
- deploy/release/publish commands;
- database/cloud/secrets/payment mutations.

Allowed read-only examples after Phase 0:

- `git status`, `git diff --name-only`, `git rev-parse`;
- `gh pr view`, `gh run/check status` queries;
- `resolve-cli.sh --json`;
- reading Busdriver files/logs/artifacts.

## 11. Marker / Artifact Freshness Rules

Hermes must not treat any marker, approval, PASS file, bypass file, review artifact, or clean-status artifact as valid by filename presence alone.

Freshness/provenance must be tied to current state according to Busdriver source-of-truth, such as:

- current HEAD / diff / commit SHA;
- current design/plan content or digest;
- current branch/worktree;
- current PR number and head SHA;
- current CI/check run;
- current freeze scope;
- current Busdriver config and gate semantics.

Hermes may read marker metadata only to verify status. It must not write, forge, delete, consume, or inspect single-use skip files in ways that consume them before retry. Gate recovery follows Busdriver `gate-recovery.md` exactly.

## 12. Dirty Tree and Post-Run Reconciliation

Before any repo-changing dispatch, Hermes must check dirty tree state. If dirty, fail closed unless current Busdriver source says the operation allows it and the dirty state is explicitly included in the handoff.

After any approved dispatch, Hermes must reconcile:

- dispatcher-reported `files_changed`;
- actual `git status` / diff;
- committed SHA if any;
- `unclaimed_changes`;
- `ignored_changes`;
- out-of-scope changes;
- verifier outputs;
- launcher exit code.

Any mismatch is `blocked` / `needs review`, not success.

## 13. Codex Result Contract Distinction

`goal-result.schema.json` validates Codex's **self-report**:

```text
summary
self_assessed_status
blocker
files_changed
intended_commit_message
```

The dispatcher may inject additional final fields, such as:

```text
committed
commit_sha
unclaimed_changes
ignored_changes
```

Hermes needs either a Busdriver-provided final result schema or a narrow Hermes compatibility schema for the final dispatcher envelope. The launcher contract must define noninteractive behavior, timeouts, cancellation, exit codes, output/log paths, cwd/env requirements, whether it may commit, and whether it may push/PR/merge/deploy/call MCP.

Until this is settled, `codex-goal-dispatch.sh + goal-result.schema.json` is an experiment target, not a complete execution contract.

## 14. MCP / Plugin Boundary

Hermes must not mirror or directly operate Busdriver-managed MCP/plugins.

Hermes must not:

- directly call Busdriver MCP servers;
- synthesize `mcp__*` tool names;
- infer MCP schemas;
- store MCP credentials;
- build fallback MCP routes;
- replicate plugin command routing;
- call third-party CLIs on Busdriver's behalf unless explicitly approved as a Busdriver seam.

If a requested capability exists only through Busdriver/Claude/MCP/plugin, Hermes routes it to Busdriver/Claude side and reports status/results. Hermes may only read status/config/logs, notify the user, schedule read-only checks, invoke a proven narrow launcher, and summarize verified artifacts.

## 15. External Side-Effect Gate

Hermes must treat external side effects as gated operations. External side effects include:

- creating/updating PRs/issues/comments;
- deployments/releases/package publishing;
- database/cloud/secrets/payment mutations;
- calendar/docs/ticket updates;
- sending user-visible notifications outside Hermes's response channel.

Hermes may not trigger such actions unless the user explicitly requested the side effect, Busdriver's current source permits the route, scope is stated, and the result is verified.

## 16. Data Egress / Privacy Gate

Before sending design/code/context to Codex, UltraOracle, council, MCP, external reviewers, or Telegram summaries, Hermes must classify the data boundary.

Sensitive categories include secrets, credentials, keys/tokens, PII, payment data, customer data, proprietary unreleased code, and production incident data.

Hermes must minimize payloads and must not send sensitive material through advisory/external routes unless Busdriver config enables the route and the user has explicitly allowed it or it is already part of Busdriver's configured workflow.

UltraOracle uses user-config-only enablement; repo/project config must not opt the user into browser/ChatGPT Pro data egress.

## 17. Single-Flight / Concurrency Gate

Before any repo-changing Busdriver-approved operation, Hermes must acquire a Hermes-owned per-repo/per-worktree lock.

Lock key must include:

- canonical repo root;
- branch or worktree path;
- operation class.

If active, Hermes may report status, refuse the second mutation, or ask the user to cancel/finish the active run. Do not run concurrent repo-changing dispatches in the same repo/worktree.

Locks and any future queue state must live under `~/.hermes/...`, not `.claude/`, unless Busdriver later defines `.claude/hermes` as an explicit integration surface.

## 18. Fail-Closed Conditions

Hermes must fail closed for repo-changing work if:

- Busdriver root/config/version cannot be resolved/read;
- `hooks/hooks.json` cannot be read;
- relevant gate scripts are missing/unreadable;
- orchestrator or required phase skill cannot be read;
- repo root/worktree/branch cannot be resolved;
- dirty tree policy is unclear;
- active freeze scope is present and unclear;
- marker freshness cannot be proven;
- reviewer route cannot be resolved;
- dispatcher result is missing/invalid;
- dispatcher reports success but git/status/verifiers disagree;
- Busdriver source files changed since last smoke test;
- concurrent mutation lock is active;
- MCP/plugin boundary is unclear;
- operation requires external side effects not explicitly approved;
- data egress classification is sensitive/unclear.

## 19. Status Tool Requirements

`hermes-busdriver-status --json` v1 may be read-only only. It should report:

- resolved plugin root, state dir, repo root;
- package/plugin version as diagnostic data;
- `hooks/hooks.json` parsed hook inventory;
- key gate scripts present;
- key non-gate hooks present (MCP health, config protection, quality gate, command log, state persistence);
- user config route keys;
- effective known role availability where possible, noting `resolve-cli.sh --json` is not full role resolution;
- presence of dispatcher/schema/ultra-oracle scripts;
- dirty tree / active freeze / marker summaries for a supplied repo;
- doctor/status script result, but not as sole health source;
- drift warning if orchestrator, hook manifest, dispatcher, schema, or gate scripts changed since last smoke test.

Status must write nothing under `.claude/` or the source repo.

## 20. Settling Checks Before Any Mutating Launcher

H1 — standalone dispatcher check: proves noninteractive execution or identifies session dependency.  
H2 — final result envelope/schema check: distinguishes Codex self-report vs dispatcher final fields.  
H3 — dirty tree fail-closed contract: assert dispatcher/source behavior and run fixture.  
H4 — scope containment: out-of-scope edits must block/surface.  
H5 — gate bypass check: Hermes must not commit/PR/merge without hook-runtime equivalence or explicit local-only constraint.  
H6 — read-only status check: status writes nowhere unsafe.  
H7 — drift invalidation: changes to orchestrator/hooks/dispatcher/schema/gates disable mutating launcher until smoke tests pass.  
H8 — state-dir/plugin-root portability: `$BUSDRIVER_PLUGIN_ROOT` and `$BUSDRIVER_STATE_DIR` route artifacts correctly.  
H9 — marker freshness: stale/foreign markers are rejected.  
H10 — concurrency: two same-repo mutations cannot run simultaneously.  
H11 — external side effects: PR/comment/deploy/publish needs explicit approval and route confirmation.  
H12 — sensitive payload: fake secrets are not leaked to Telegram/advisory/external routes.  
H13 — hook-runtime equivalence: launcher either triggers gates, invokes equivalents, refuses gated ops, or is local-only.

## 21. Allowed First Implementation Slice

Allowed now, after this contract:

1. maintain the Hermes `busdriver-relay` skill from v2 sections 0–20;
2. implement `hermes-busdriver-status --json` read-only;
3. implement Hermes-owned single-flight lock/status scaffolding;
4. run H1–H13 as smoke/contract tests.

Not allowed yet:

- repo-changing `hermes-busdriver-codex-goal` launcher;
- `.claude/hermes/jobs` queue;
- Busdriver `hermes-home` install target;
- commit/PR/merge/deploy automation;
- direct MCP/plugin routing;
- any claim that Hermes-launched work is gate-safe without H13 proof.

## 22. Ultimate V1 Rule

Until proven otherwise:

```text
Hermes can recognize Busdriver pipelines and report status.
Hermes can read Busdriver sources JIT.
Hermes can ask the user to continue in Claude Code / Busdriver.
Hermes cannot itself finalize repo-changing work.
```

This keeps Hermes useful as a second agent without making it a stale, gate-skipping shadow orchestrator.
