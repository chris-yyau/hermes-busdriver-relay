# ADR 0003 — Hermes Equivalent Gate Runner for Independent Agents

## Status

Accepted for the Hermes Busdriver Relay v2 direction.

## Context

The user wants Hermes to continue implementation work when Claude Code quota is unavailable. The active relay surface is Pi-default for draft implementation, with OpenCode configured as fallback/comparison route metadata that remains non-programmatic until adapter proof exists and Codex kept review/backstop-focused by default.

However, Hermes terminal commands do not automatically run inside Claude Code's Busdriver hook runtime. If Hermes launches agents directly and then commits/pushes/opens PRs, it can bypass Busdriver's strongest gates.

## Decision

Introduce a Hermes-side equivalent gate runner:

```text
hermes-busdriver-gate preflight
  → Pi implementation draft
  → hermes-busdriver-gate postflight
  → report / review / later finalization gate
```

This runner does not pretend to be Claude Code. It explicitly checks the subset of Busdriver-equivalent invariants Hermes can enforce outside Claude Code.

## v1 Capabilities

### Preflight

- resolves repo root, branch, HEAD, dirty tree, merge/rebase/cherry-pick state;
- reads Busdriver plugin root and `hooks/hooks.json`;
- verifies gate-like hook events are declared;
- records `.git/hooks` baseline;
- records gitignored file baseline;
- captures active freeze/careful/review marker summary;
- stores scope include/exclude patterns in a Hermes-owned baseline file.

### Postflight

- collects changed tracked/untracked paths without requiring commits;
- checks changed files against scope include/exclude patterns;
- detects `.git/hooks` add/change/remove tampering;
- detects new or changed gitignored files such as `.env`;
- runs optional verifier commands;
- emits an explicit decision object.

## Current Decision Contract

When checks pass:

```json
{
  "agent_implementation_draft_allowed": true,
  "commit_allowed": false,
  "push_allowed": false,
  "pr_allowed": false,
  "merge_allowed": false,
  "deploy_allowed": false
}
```

This means Hermes may call an implementation agent to produce a working-tree diff, but finalization remains blocked until a stronger commit/PR gate exists.

## Why Draft First

Draft mode is enough to satisfy the near-term quota-fallback goal:

```text
Claude quota exhausted
  → Hermes follows Busdriver routing
  → Hermes calls Pi to implement a draft (Codex only if Pi is blocked or unsuited)
  → Hermes runs postflight/verifiers
  → Hermes reports diff + evidence
  → Busdriver/Claude or a later equivalent finalization gate reviews/commits
```

It avoids the false claim that a Hermes-launched agent has passed Claude Code hooks.

## Future Work

1. `hermes-busdriver-agent-draft`: Pi-default launcher wrapper using this gate runner; OpenCode requires separate adapter proof before fallback use, and Codex remains review/backstop-focused by default.
2. Additional adapters only if the deferred scope is explicitly reopened.
3. Commit-capable gate:
   - litmus-equivalent review;
   - blueprint/design marker freshness;
   - freeze/scope binding;
   - secret/data-egress checks;
   - commit message + file contract;
   - lock ownership + reconciliation.
4. PR-capable gate:
   - CI status;
   - PR review/comment ack ledger;
   - merge policy;
   - external side-effect approvals.

## Non-goals

- Do not vendor Busdriver into this repo.
- Do not copy Claude Code plugins/MCP state into Hermes.
- Do not forge Busdriver markers.
- Do not claim hook-runtime equivalence where none exists.
