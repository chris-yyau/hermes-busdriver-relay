# OpenCode fallback proof audit lessons — July 2026

Use this note when auditing OpenCode as relay fallback/comparison route metadata or testing its non-installed adapter fixture.

## Current safe interpretation

OpenCode is a configured fallback/comparison **route**, not a production programmatic lane. Production status and role resolution must report:

```text
selected_agent=opencode
adapter_verified=false
programmatic_dispatch_allowed=false
dispatch_allowed=false
dispatch_blocker=agent_containment_and_credential_broker_unavailable
mutation_allowed=false
finalization_allowed=false
```

A historical adapter-shape proof included fake-binary negative contracts and a real-model smoke. That evidence remains useful fixture provenance, but it does not prove enforceable containment or least-privilege credential brokering and cannot authorize production launch.

## Read-only audit pattern

Check all of these surfaces before accepting the current default-deny status:

1. `scripts/hermes-busdriver-status` metadata for `relay.impl.secondary` and `relay.impl.fallback`;
2. `scripts/hermes-busdriver-relay-role` default-deny semantics;
3. production `scripts/hermes-busdriver-agent-draft` blocker ordering;
4. production `scripts/hermes-busdriver-agent-smoke` parser-negative wording;
5. fixture-only adapter seams under `tests/fixtures/**`;
6. contract tests that keep dispatch, mutation, and finalization authority false;
7. README, CURRENT_STATUS, ADRs, authority maps, and skill references.

The production wrapper must return `agent_containment_and_credential_broker_unavailable` before executable lookup, repository access, HOME/config access, credential handling, or worker launch. There must be no CLI, environment, fixture-path, or caller-command unlock seam.

## What the historical proof bundle establishes

The retained adapter fixture may demonstrate:

- a draft-only result schema;
- isolated synthetic OpenCode config and auth;
- scope include/exclude validation against actual git changes;
- risky git environment stripping;
- artifact size and timeout handling;
- malformed, missing, blocked, authority-positive, and file-mismatched artifact rejection;
- process-tree teardown and `needs_busdriver_review` output.

These are necessary adapter tests, not a production containment proof. A model run through a wrapper does not by itself establish credential isolation, descendant containment, network control, or rollback of external side effects.

## Production authority rule

OpenCode remains non-programmatic and keeps every reusable authority flag false:

```text
programmatic_dispatch_allowed=false
adapter_verified=false
dispatch_allowed=false
mutation_allowed=false
finalization_allowed=false
commit_allowed=false
push_allowed=false
pr_allowed=false
merge_allowed=false
marker_write_allowed=false
deploy_allowed=false
release_allowed=false
publish_allowed=false
```

Any finalization belongs to Busdriver/Claude authority or to an independently gated Hermes Delivery Mode operation whose own policy blocker has been removed by reviewed evidence. OpenCode never inherits finalization authority from route selection or adapter quality.

## Requirements before any future promotion

Do not change production dispatch metadata unless one reviewed change proves all of:

1. enforceable process/container containment for every descendant;
2. explicit least-privilege credential brokering with no ambient-secret inheritance;
3. filesystem and network side-effect policy;
4. reliable timeout teardown and reconciliation;
5. no production fixture or caller-command unlock seam;
6. mutation-resistant tests and executable sentinels;
7. synchronized status, docs, skill references, and trusted-runtime ownership pins.

Until then the correct production blocker is `agent_containment_and_credential_broker_unavailable`.
