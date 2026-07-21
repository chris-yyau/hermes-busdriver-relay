# ADR 0003 — Hermes Equivalent Gate Runner for Independent Agents

## Status

**Superseded for production agent execution.** Retained as historical target-state design for preflight/postflight state checks.

## Current production truth

The production relay does not launch Pi, OpenCode, Codex, custom workers, or caller-provided verifier commands. Agent execution is policy-blocked before worker, repository, HOME, or credential handling with:

```text
agent_containment_and_credential_broker_unavailable
```

Local verifier execution is independently policy-blocked with:

```text
verifier_containment_unavailable
```

Accordingly, production status and role envelopes must keep:

```json
{
  "programmatic_dispatch_allowed": false,
  "adapter_verified": false,
  "dispatch_allowed": false,
  "agent_implementation_draft_allowed": false,
  "commit_allowed": false,
  "push_allowed": false,
  "pr_allowed": false,
  "merge_allowed": false,
  "deploy_allowed": false
}
```

A prior adapter proof or historical smoke is not containment or credential-broker evidence and cannot change these flags.

## Historical target-state design

The original proposal was an equivalent state-checking sequence:

```text
hermes-busdriver-gate preflight
  → constrained draft worker
  → hermes-busdriver-gate postflight
  → report / review / later finalization gate
```

The implemented gate still provides useful non-authorizing checks:

### Preflight

- resolves repo root, branch, HEAD, dirty tree, and in-progress git operations;
- reads the Busdriver plugin manifest and records hook declarations;
- records `.git/hooks`, ignored-file, marker, and scope baselines.

### Postflight

- collects tracked and untracked changes;
- checks scope and ignored-file policy;
- detects hook tampering;
- emits a fail-closed decision object.

These checks are evidence surfaces only. They do not sandbox an agent, broker credentials, authorize dispatch, or prove Claude Code hook-runtime equivalence. Optional verifier execution described by the original design is available only in non-installed test fixtures; production refuses it with `verifier_containment_unavailable`.

## Requirements before any future promotion

A future ADR may supersede the production block only after all of the following are implemented and independently reviewed:

1. enforceable process/container containment;
2. explicit credential brokering with no ambient-secret inheritance;
3. scoped filesystem and network policy;
4. complete process-tree teardown and side-effect reconciliation;
5. mutation-resistant contracts and real negative sentinels;
6. truthful status, docs, and role metadata updated in the same change.

Preflight/postflight alone are insufficient.

## Non-goals

- Do not vendor Busdriver into this repo.
- Do not copy Claude Code plugins, MCP state, or credentials into Hermes.
- Do not forge Busdriver markers.
- Do not claim hook-runtime equivalence where none exists.
- Do not treat route preference or adapter proof as production dispatch authority.
