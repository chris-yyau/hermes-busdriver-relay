# ADR 0007 — Pi Busdriver Tool-Harness Adapter

## Status

Accepted as a target-state adapter proof.

## Context

The relay needs a constrained way to evaluate Pi as a Busdriver-shaped draft worker without making Pi a Busdriver authority. Pi can run with built-in tools disabled and custom extensions enabled, which makes it a plausible tool-harness adapter candidate.

The authority boundary remains unchanged:

```text
ClaudeCode / Busdriver = canonical authority
Hermes                 = router / operator / verifier
Codex                  = current normal draft worker
Pi                     = constrained draft-only tool harness after adapter proof passes
OpenCode               = generic lane unless a Busdriver-compatible adapter/plugin is rebuilt
```

This ADR records the minimum proof required before `hermes-busdriver-agent-draft --agent pi` is treated as an enabled mutating draft lane.

## Decision

Add a relay-owned Pi adapter with:

1. `adapters/pi/busdriver-tools.ts` exposing only Busdriver-shaped `bd_*` tools;
2. `adapters/pi/pi-result.schema.json` defining the fail-closed result artifact;
3. `scripts/pi/run-pi-busdriver-draft` launching Pi with built-ins/extensions disabled;
4. `hermes-busdriver-agent-draft --agent pi` integration through the existing lock/preflight/postflight pattern;
5. `hermes-busdriver-agent-smoke --agent pi` opt-in real-agent smoke;
6. contract tests and docs proving all authority flags remain false.

## Scope

Pi may perform scoped draft edits only through relay-defined tools. A successful run ends in:

```text
status=needs_busdriver_review
```

It does not authorize commits, pushes, PR creation, merges, marker writes, deploys, releases, or any finalization claim.

## Non-goals

- Pi is not Busdriver-native Claude runtime.
- Pi is not a trusted marker writer.
- Pi does not run litmus/pre-PR/PR-grind finalization.
- Pi does not replace ClaudeCode/Busdriver authority.
- Pi does not replace Codex as the current normal draft lane in this ADR.
- OpenCode parity is not a prerequisite for this adapter proof; OpenCode remains generic unless rebuilt and verified separately.

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

Any Pi self-report containing `done`, `complete`, `ready_to_merge`, or `merged` is treated as `worker_self_report_only` unless independently verified by Hermes and authorized by ClaudeCode/Busdriver or explicit Hermes Delivery Mode.

## Tool boundary

`bd_bash` is argv-only and allowlist-only. It must not expose shell strings, shell expansion, arbitrary `bash -c`, network commands by default, finalization commands, or marker writes.

`bd_write_draft` writes only inside repo root and declared scope. It blocks `.git/**`, `.claude/**`, `.opencode/**`, trusted marker paths, and symlink escapes. It records normalized path, operation id, `before_hash`, and `after_hash`.

## Failure modes

The adapter fails closed when:

- Pi binary is missing or exits nonzero;
- Pi does not write `pi-result.json`;
- the result schema/status is invalid;
- any authority flag is true or missing;
- postflight sees out-of-scope writes;
- the event/artifact evidence cannot be parsed;
- gate preflight/postflight fails.

## Rollout gates

Pi becomes an enabled draft adapter only after all pass:

1. static contract tests for schema/tools;
2. fake-Pi wrapper tests;
3. `hermes-busdriver-agent-draft --agent pi` fake adapter gate test;
4. `hermes-busdriver-agent-smoke --agent pi` fake adapter test;
5. optional real Pi smoke when quota/runtime is available;
6. docs and skill references describing Pi as constrained draft-only, not authority.
