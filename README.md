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
docs/hermes-busdriver-integration-contract-v2.md
skills/busdriver-relay/SKILL.md            Hermes skill source
scripts/hermes-busdriver-status            Read-only status probe
tests/contract/                            Smoke/contract tests
```

## Quick status probe

```bash
scripts/hermes-busdriver-status --repo /path/to/repo --pretty
```

The status probe is read-only. It reports Busdriver root/config/hook/entrypoint health and repo dirty state, but it never writes `.claude/`, `.opencode/`, or the target repo.

## First allowed slice

Allowed now:

1. maintain `busdriver-relay` skill;
2. maintain read-only `hermes-busdriver-status`;
3. add H1-H13 contract tests;
4. document decisions in ADRs.

Not allowed yet:

- repo-mutating `hermes-busdriver-codex-goal` launcher;
- `.claude/hermes/jobs` queue;
- Busdriver `hermes-home` install target;
- commit/PR/merge/deploy automation;
- direct MCP/plugin routing.
