# Hermes Busdriver Relay

Private Hermes-side relay for the user's Busdriver / Claude Code workflow.

This repository contains **Hermes-owned integration artifacts only**:

- the `busdriver-relay` Hermes skill;
- the Hermes ↔ Busdriver integration contract;
- read-only status tooling;
- contract/smoke tests;
- ADRs for integration decisions.

It is **not** a Busdriver clone and must not vendor Claude plugins, MCP configs, runtime markers, credentials, or Busdriver skill bodies.

## Boundary

```text
Hermes = intake, Phase 0 discovery, JIT source reads, read-only status, notification
Busdriver/Claude Code = workflow authority, gates, reviews, MCP/plugin routing, execution, commits, PRs, merges
```

Important: Busdriver gates are largely Claude Code hook-runtime behavior. A Hermes bare shell running a Busdriver script does not automatically fire Claude Code hooks.

## Contents

```text
ADRs/                                      Lightweight architecture decisions
docs/CURRENT_STATUS.md                     Current completion/verification state
docs/hermes-busdriver-integration-contract-v2.md
docs/settling-checks-v1.md                 H1-H13 v1 status map
skills/busdriver-relay/SKILL.md            Hermes skill source
skills/busdriver-relay/references/         Skill reference notes
scripts/hermes-busdriver-status            Read-only status probe
scripts/hermes-busdriver-lock              Hermes-owned single-flight lock
scripts/hermes-busdriver-runtime-check     H13 hook-runtime checker
scripts/hermes-busdriver-gate              Equivalent preflight/postflight gate runner
scripts/hermes-busdriver-agent-draft       Generic draft agent launcher
scripts/hermes-busdriver-agent-smoke       Optional real-agent adapter smoke
scripts/hermes-busdriver-smoke             Safe smoke runner
tests/contract/                            Contract tests
```

## Commands

### Read-only status

```bash
scripts/hermes-busdriver-status \
  --plugin-root /path/to/busdriver \
  --repo /path/to/repo \
  --pretty
```

The status probe is read-only. It reports Busdriver root/config/hook/entrypoint health, effective routes, critical file hashes, active marker summaries, relay lock state, and repo dirty state. It never writes `.claude/`, `.opencode/`, Busdriver, or the target repo.

### Hermes-owned single-flight lock

```bash
scripts/hermes-busdriver-lock acquire --repo /path/to/repo --operation repo-mutation
scripts/hermes-busdriver-lock status --pretty
scripts/hermes-busdriver-lock release --repo /path/to/repo --operation repo-mutation --token <token>
```

Locks live under `~/.hermes/busdriver-relay/locks` by default, not inside `.claude/` or the target repo.

### Hook-runtime equivalence check

```bash
scripts/hermes-busdriver-runtime-check \
  --plugin-root /path/to/busdriver \
  --repo /path/to/repo \
  --pretty
```

This is a read-only H13 checker. Normal Hermes execution should report `mutating_launcher_allowed: false`; that is the safe expected result until a future v2 proves hook-runtime equivalence.

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
  --verifier 'tests=pytest -q'
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
  --verifier 'tests=pytest -q' \
  --pretty
```

Currently only `--agent codex` is supported (others temporarily deferred). `noop` and `custom` are for tests.

A successful run means `status=needs_busdriver_review`. It may leave a working-tree diff, but it does not allow commit/push/PR/merge/deploy. It acquires a Hermes-owned `agent-draft` lock, runs gate preflight, runs the agent under a best-effort PATH guard, runs gate postflight, releases the lock, and writes artifacts under `~/.hermes/busdriver-relay/agent-runs/`.

### Optional real-agent smoke

```bash
scripts/hermes-busdriver-agent-smoke \
  --plugin-root /path/to/busdriver \
  --agent codex \
  --pretty
```

This creates a throwaway git repo and calls the selected real agent through `hermes-busdriver-agent-draft`. It may consume provider quota/tokens, so it is not part of the default contract test suite. The Codex adapter has been verified with this pattern against a temp repo: Codex created `src/codex_smoke.txt`, postflight scope/verifier passed, and status remained `needs_busdriver_review`.

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
- commit/PR/merge/deploy automation inside draft launchers or without pr-grind-equivalent checks;
- direct MCP/plugin routing;
- claims that Hermes shell execution is Busdriver-gate-safe.

## Delivery mode

Draft launchers still stop at `needs_busdriver_review`. When the user explicitly asks Hermes to finish the whole job, Hermes may create a branch, commit, open a PR, and merge only through a pr-grind-equivalent loop: local verification, PR checks/status rollup, Busdriver `relevant-check-status.sh` when available, PR reviews/comments, bounded wait for advisory reviewer bots, fix rounds for actionable feedback, and merge only after the PR is clean.
