# ADR 0004 — Draft Agent Launcher

## Status

**Superseded for production agent execution.** Retained as historical target-state launcher design and fixture provenance.

## Current production truth

`scripts/hermes-busdriver-agent-draft` is a fail-closed production launcher/parser surface. For Pi and OpenCode it returns, before worker, repository, HOME, or credential handling:

```text
agent_containment_and_credential_broker_unavailable
```

It has no Codex or custom production mutation route. Therefore production dispatch, mutation, and all finalization authority remain false. `scripts/hermes-busdriver-agent-smoke` is a parser/authority-negative smoke surface; it does not provide a production real-agent launch path.

## Historical target-state design

The original proposal described this sequence:

```text
hermes-busdriver-lock acquire --operation agent-draft
  → hermes-busdriver-gate preflight
  → guarded agent command
  → hermes-busdriver-gate postflight
  → hermes-busdriver-lock release
  → JSON report
```

That sequence survives only in non-installed test fixtures used to test schema, scope, process-tree, and authority-negative behavior. A successful fixture run ends in `status=needs_busdriver_review`; it never authorizes a production run.

## Authority contract

All production and fixture envelopes must keep these flags false:

```json
{
  "programmatic_dispatch_allowed": false,
  "adapter_verified": false,
  "commit_allowed": false,
  "push_allowed": false,
  "pr_allowed": false,
  "merge_allowed": false,
  "deploy_allowed": false,
  "release_allowed": false,
  "publish_allowed": false,
  "marker_write_allowed": false,
  "finalization_allowed": false
}
```

Fixture adapter tests may validate a working-tree diff and `needs_busdriver_review` artifact, but they are not installed routes and are not proof of production containment or credential brokering.

## Why the historical PATH guard was insufficient

The historical target relied on a best-effort PATH shadow for finalization commands. An absolute binary path, alternate interpreter, inherited credential, descendant process, or external side effect can bypass a PATH-only guard. Postflight detects some local effects after the fact but cannot prevent or roll back every external effect.

Production therefore remains blocked with `agent_containment_and_credential_broker_unavailable` until an enforceable containment and credential-broker architecture exists.

## Future promotion requirements

Any future executable launcher must add and independently verify:

1. process/container containment that covers descendants;
2. least-privilege credential brokering;
3. filesystem and network controls;
4. atomic ownership and reconciliation;
5. no production test-fixture or caller-command unlock seam;
6. docs, status, and role metadata that remain default-deny until every proof passes.
