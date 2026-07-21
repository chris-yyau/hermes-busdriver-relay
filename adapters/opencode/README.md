# OpenCode Busdriver Draft Adapter

This directory contains the relay-owned OpenCode fallback adapter proof. It is not an OpenCode plugin install and it does not make OpenCode a Busdriver authority.

## Role

OpenCode is the Pi fallback / China-model comparison **adapter contract**. That contract may produce scoped draft changes only in non-installed test harnesses; every production agent/probe blocks immediately after argument parsing—before repository, HOME/state, credential, lock, prompt, gate, run-directory, or worker handling—with `agent_containment_and_credential_broker_unavailable`.

```text
OpenCode result status = needs_busdriver_review | blocked
commit/push/PR/merge/marker/deploy/release/publish/finalization authority = false
```

The non-installed harness proves the generic adapter mechanics: `--pure`, private HOME/XDG layout, scoped external control directory, bounded result parsing, schema/authority validation, Git reconciliation, and include/exclude scope. Production code retains those mechanics but does not enter them while the blocker is active, and it must not copy auth material or launch OpenCode. If future containment and credential brokering are implemented, the same result schema remains authority-negative.

## Files

```text
opencode-result.schema.json    Fail-closed result artifact contract
```

## Launcher

The production wrapper is an internal component of the relay draft parser and always fails closed before starting OpenCode. No PATH guard, environment variable, direct invocation, or outer launcher currently unlocks production dispatch.

The following command is a negative capability probe and is expected to return blocked:

```bash
scripts/hermes-busdriver-agent-draft --agent opencode ...
```

It must report `agent_containment_and_credential_broker_unavailable` and must not launch OpenCode, copy credentials, or leave a draft diff. Functional `needs_busdriver_review` results belong only to the non-installed harness until a future production containment design is implemented and reviewed.
