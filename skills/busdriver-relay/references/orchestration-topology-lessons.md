# Relay Orchestration Topology Lessons

Date: 2026-06-28

Use this when deciding whether Main Hermes, relay CLI, subagents, Codex, or cron should own a Busdriver-relay pipeline.

## Recommended topology

```text
User / Telegram
  -> Main Hermes session = orchestrator / operator / final verifier
    -> relay CLI = deterministic pipeline state machine + gates + artifacts
      -> Codex / subagents = bounded workers or reviewers
    <- artifacts / envelopes / PR-grind result
  -> Main Hermes reports, verifies side effects, and performs gated cleanup
```

## Roles

- **Main Hermes** owns user intent, scope changes, final verification, external side-effect decisions, PR-grind interpretation, merge cleanup, and user-visible reporting.
- **Relay CLI** should own deterministic state transitions, schemas, run IDs, gates, durable artifacts, resume/continue status, and fail-closed authority flags.
- **Subagents/Codex** are bounded workers/reviewers. They may implement, review, diagnose, or summarize a phase, but their self-report is not final evidence.
- **Cron/watchdogs** may call read-only/durable CLI status or continue operations once the CLI carries sufficient state, but should not become the hidden policy owner.

## Pitfalls

- Do not let a subagent own the whole delivery pipeline from the start. Subagents cannot clarify with the user, are not durable across session shutdown, and their success claims need read-back verification.
- Do not keep the pipeline as main-session hand steps forever. That leaves too much policy in the agent's transient context and makes restart/resume brittle.
- Do not encode authority based on caller type. Caller identity is audit/debug context; authority must come from gate/state envelopes.
- After any worker/subagent returns, main Hermes must read back artifacts, repo state, tests, PR checks, and review state before marking a phase complete.
- After every push/fix round, invalidate previous PR-grind cleanliness and restart collection against the latest PR head.

## CLI design direction

Grow `hermes-busdriver-deliver` toward a durable state machine with commands such as:

```bash
hermes-busdriver-deliver start ...
hermes-busdriver-deliver status --run-id ...
hermes-busdriver-deliver continue --run-id ...
hermes-busdriver-deliver finalize --run-id ...
```

Each result should expose a stable schema containing run id, phase, status, reason, authority flags, artifacts, and next action. Keep commit/push/PR/merge disabled until explicit finalization gates exist and pass.
