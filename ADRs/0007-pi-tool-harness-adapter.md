# ADR 0007 — Pi Busdriver Tool-Harness Adapter

## Status

**Accepted as the sole executor route contract; not enabled for production dispatch.**

## Current production truth

Pi is the sole current executor route. Production `hermes-busdriver-agent-draft`, the Pi wrapper, and role/status surfaces still fail closed before worker, repository, HOME, or credential handling with:

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

The target provider/model default is `cursor/auto`. This is route metadata for the blocked production surface and non-installed harnesses, not production enablement.

## Authority map

```text
ClaudeCode / Busdriver = canonical authority
Hermes                 = relay / router / verifier / explicit Delivery Mode operator
Pi                     = sole executor route metadata; production non-programmatic
Codex                  = fallback coder metadata and PR lead; no production relay-role dispatcher
OpenCode               = non-executor historical/comparison evidence only
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

`bd_write_draft` writes only inside the repository and declared scope. It blocks `.git/**`, `.claude/**`, `.opencode/**`, trusted marker paths, hardlinks, the opened credential-source inode, and symlink escapes, and records a pre-write intent plus normalized path, operation ID, `before_hash`, and `after_hash`. The candidate lane requires every intent to have an audit, reconciles audited paths against `files_changed`, and re-hashes final bytes through the descriptor-bound broker. That reconciliation reads the worker's own writable `$HOME`, so it is self-attested provenance, not parent-held provenance.

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

1. enforceable OS-level containment for the worker and every descendant;
2. explicit, least-privilege credential brokering with no ambient-secret inheritance;
3. filesystem and network side-effect policy;
4. teardown and reconciliation under timeout and races, with write/audit provenance held by the parent rather than read back from the worker's writable `$HOME`;
5. no fixture, environment, or caller-command bypass;
6. status/docs/skill metadata updated atomically from false only after all proofs pass.

Until then, Pi remains non-programmatic regardless of adapter quality. OpenCode is not an executor route.

### Candidate-lane state (2026-08-02)

The locked `cursor/auto` candidate lane delivers requirement 2 to a reviewed standard — enumerated child environment, private `HOME`, single-provider auth projection with the refresh token stripped, refusal of refreshable credentials, and descriptor-bound scrub-on-exit — plus pinned adapter/runtime digests and private-runtime retention of the child wrapper and its dependencies.

Requirements 1 and 4 are not delivered. The worker launch has no `sandbox-exec`, `setrlimit`, or network restriction, and the write reconciliation reads evidence from inside the worker's own writable `$HOME`. `agent_containment_and_credential_broker_unavailable` is a conjunction and is not cleared by satisfying one conjunct, so the 2026-08-02 promotion attempt for this lane was adjudicated `PROMOTION_BLOCKED_FAIL_CLOSED` and the hardening is retained as candidate/test-lane groundwork only. A successful functional dogfood exercises the cooperative path and is not containment proof.
