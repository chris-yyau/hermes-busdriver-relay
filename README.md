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
scripts/hermes-busdriver-runtime-check     H13 hook-runtime equivalence checker
scripts/hermes-busdriver-smoke             Safe smoke runner
tests/contract/                            Smoke/contract tests
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
5. document decisions in ADRs.

Not allowed yet:

- repo-mutating `hermes-busdriver-codex-goal` launcher;
- `.claude/hermes/jobs` queue;
- Busdriver `hermes-home` install target;
- commit/PR/merge/deploy automation;
- direct MCP/plugin routing;
- claims that Hermes shell execution is Busdriver-gate-safe.
