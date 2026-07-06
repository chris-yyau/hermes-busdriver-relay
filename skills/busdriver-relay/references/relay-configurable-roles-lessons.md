# Relay Configurable Roles Lessons

## Context

User clarified the durable architecture split:

- Busdriver is Claude-side and should keep Claude-native workflow/control-plane semantics.
- `hermes-busdriver-relay` is Hermes/Pi-side by default and should provide equivalent status/gate/reporting paths without pretending to be Busdriver's native Claude runtime; Codex remains explicit fallback.
- Relay role routing should not live in `~/.claude/busdriver.json`; that file belongs to Claude-side Busdriver.

## Config Location

Relay-owned role config belongs in:

```text
~/.hermes/busdriver-relay/config.json
```

`hermes-busdriver-status` should support:

```bash
--relay-config <path>
```

Default when omitted:

```text
~/.hermes/busdriver-relay/config.json
```

Keep `--user-config` / `~/.claude/busdriver.json` for Busdriver-native routes only.

## Config Shape

Root-level object:

```json
{
  "coding_agent": "pi",
  "avoid_coding_agent_for_review": true,
  "routes": {
    "relay.pr.backstop": ["gpt-5.5", "codex"]
  }
}
```

Validation rules:

- `coding_agent`: non-empty string only; otherwise use default and report `coding_agent_config_error` with source `default`.
- `avoid_coding_agent_for_review`: boolean only; otherwise use default and report `avoid_coding_agent_for_review_config_error` with source `default`.
- `routes`: object only; malformed/non-object config must be degraded, not healthy defaults.
- route values: non-empty string or array of non-empty strings only.
- invalid/malformed config must fail closed: `selected_agent=null`, `degraded=true`, `config_error` set, `finalization_allowed=false`, `mutation_allowed=false`.

## Configurable Relay Anchors

Expose all relay-side reviewer/voice/decision anchors, not just the original Claude-specific anchors:

```text
relay.litmus.reviewer
relay.blueprint.reviewer_1
relay.blueprint.reviewer_2
relay.blueprint.reviewer_3
relay.blueprint.arbiter
relay.pr.lead
relay.pr.backstop
relay.council.architect
relay.council.pragmatist
relay.council.critic
relay.council.researcher
relay.council.skeptic
```

Rationale from user: Hermes can use different agents. When Codex is coding, the relay may use other agents for review; when another agent is coding, Codex may become reviewer/backstop/arbiter.

## PR-Grind Lessons

Reviewer feedback on this slice exposed durable pitfalls:

1. Do not stringify arbitrary route entries (`None`, `""`, objects) into agent names.
2. Do not coerce booleans with `bool(value)` for JSON config; strings like `"false"` become truthy.
3. Tests for missing default relay config must pass an explicit temp missing path, otherwise they may read the user's real `~/.hermes/busdriver-relay/config.json` and become non-hermetic.
4. Malformed JSON, valid JSON with invalid top-level shape (e.g. `[]`), invalid `routes` container, invalid route type, invalid route entries, and empty routes should all have contract tests.
5. After every fix push, rerun PR-mode lead/backstop hashes and latest-head PR-grind. Resolve old review threads only after evidence shows the current code addresses them.
