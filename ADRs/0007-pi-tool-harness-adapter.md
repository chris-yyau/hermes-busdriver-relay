# ADR 0007 — Pi Busdriver Tool-Harness Adapter

## Status

**Accepted as deferred adapter history and fixture proof; not a current route and not enabled for production dispatch.**

## Current production truth

Pi is deferred adapter history, not the current, default, or preferred implementation route. Production `hermes-busdriver-agent-draft`, the Pi wrapper, and role/status surfaces fail closed before worker, repository, HOME, or credential handling with:

```text
agent_containment_and_credential_broker_unavailable
```

Production metadata must therefore report:

```text
programmatic_dispatch_allowed=false
adapter_verified=false
dispatch_allowed=false
```

Historical fake-worker or real-model smoke proves adapter shape only. It does not prove enforceable process containment or least-privilege credential brokering.

## Authority map

```text
ClaudeCode / Busdriver = canonical authority
Hermes                 = relay / router / verifier / explicit Delivery Mode operator
Codex                  = implementation-primary metadata and PR lead; no production relay-role dispatcher
OpenCode + Go          = secondary/fallback draft-only metadata; production non-programmatic
Pi                     = deferred adapter history; production non-programmatic
```

## Target-state adapter design

The relay retains a non-installed proof surface comprising:

1. `adapters/pi/busdriver-tools.ts`, exposing only Busdriver-shaped `bd_*` tools;
2. `adapters/pi/pi-result.schema.json`, defining a fail-closed artifact;
3. a fixture form of `scripts/pi/run-pi-busdriver-draft`;
4. fixture integration through lock/preflight/postflight;
5. schema, scope, timeout, process-tree, and authority-negative contract tests.

The production wrapper remains blocked. The fixture seam lives under `tests/fixtures/**`, is loaded only by tests, and is not a production CLI or environment unlock.

## Target-state scope

In the proof harness, Pi may produce scoped draft edits only through relay-defined tools. A successful fixture result ends in:

```text
status=needs_busdriver_review
```

It authorizes no commit, push, PR creation, merge, marker write, deploy, release, publish, or finalization action.

## Authority invariants

Every Pi tool result, wrapper result, and final artifact must preserve:

```text
not_busdriver_native_claude_runtime=true
commit_allowed=false
push_allowed=false
pr_allowed=false
merge_allowed=false
marker_write_allowed=false
deploy_allowed=false
release_allowed=false
publish_allowed=false
finalization_allowed=false
```

Any worker self-report containing `done`, `complete`, `ready_to_merge`, or `merged` remains `worker_self_report_only` unless independently verified and separately authorized.

## Tool boundary

`bd_bash` is argv-only and allowlist-only. It exposes no shell strings, shell expansion, arbitrary `bash -c`, default network commands, finalization commands, or marker writes.

`bd_write_draft` writes only inside the repository and declared scope. It blocks `.git/**`, `.claude/**`, `.opencode/**`, trusted marker paths, and symlink escapes, and records normalized path, operation ID, `before_hash`, and `after_hash`.

## Failure modes

The harness fails closed when:

- the worker binary is missing or exits nonzero;
- the result artifact is missing, malformed, oversized, or inconsistent;
- any authority flag is true or missing;
- postflight sees out-of-scope writes;
- process-tree teardown cannot be demonstrated;
- gate evidence cannot be parsed.

Production fails earlier with `agent_containment_and_credential_broker_unavailable`.

## Promotion requirements

Adapter tests and smoke evidence are necessary but not sufficient. Production dispatch remains disabled until an independently reviewed design also proves:

1. enforceable containment for the worker and every descendant;
2. explicit, least-privilege credential brokering with no ambient-secret inheritance;
3. filesystem and network side-effect policy;
4. teardown and reconciliation under timeout and races;
5. no fixture, environment, or caller-command bypass;
6. status/docs/skill metadata updated atomically from false only after all proofs pass.

Until then, Pi and OpenCode remain non-programmatic production routes regardless of adapter quality.
