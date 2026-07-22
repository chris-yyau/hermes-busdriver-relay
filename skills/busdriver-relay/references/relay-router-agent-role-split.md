# Relay router agent role split — July 2026

> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

**Current production status:** the role map below is resolver/routing metadata, not a production launcher. Every role keeps `programmatic_dispatch_allowed=false`, `adapter_verified=false`, and `dispatch_allowed=false`; no executable relay-role dispatcher exists. Pi/OpenCode adapter behavior exists only in non-installed fixture provenance.

## Durable decision

For Busdriver/Hermes relay work, do **not** add Codex, Pi, OpenCode, Grok, Gemini, Cursor, or UltraOracle as competing workflow authorities. The stable split is:

```text
Busdriver + Claude Code = canonical authority, hooks, gates, litmus, PR-grind, finalization
Hermes = relay/router/verifier/status/Phase 0/locks/handoff/explicit Delivery Mode operator
Codex = implementation-primary metadata and PR lead; no production relay-role dispatcher
OpenCode + Go = secondary/fallback draft-only metadata; production dispatch blocked by `agent_containment_and_credential_broker_unavailable`
Pi = deferred adapter history; not current, default, or preferred
Claude Code = authority / backstop path
Grok = Hermes-side relay.review.fast read-only reviewer / PR-comment triage
Gemini = Hermes-side relay.review.long_context read-only architecture/spec reviewer
Cursor = manual IDE sidecar; edits are treated as human/manual dirty tree
UltraOracle = optional expert-witness escalation
```

Hard rule: **Only Claude/Busdriver may claim done. All non-Claude agents produce draft/review evidence only.**

## Important distinction

Busdriver already has canonical multi-CLI skills/routes (e.g. blueprint, council, litmus, PR-grind, external review routes such as codex/agy/grok/droid). Pi/Hermes-side routing must not duplicate those as authority. If a Busdriver-native route exists for a gate, prefer Busdriver.

Hermes-side roles such as `relay.review.fast=grok` and `relay.review.long_context=gemini` are advisory relay/router roles, not Busdriver native roles. The same model/CLI can appear in two authority domains:

- Busdriver invokes Grok/Codex/Agy/Droid inside blueprint/council/litmus/PR-grind: Busdriver interprets the result under Busdriver workflow semantics.
- Hermes invokes Grok/Gemini as `relay.*` roles: advisory evidence only, read-only, no finalization authority.

## Resolver-ready role inventory

The relay-owned config lives under `~/.hermes/busdriver-relay/config.json` (never `~/.claude/busdriver.json`). The current `hermes-busdriver-status` / `hermes-busdriver-relay-role` inventory recognizes the full 19-role map:

```text
relay.impl.primary              = codex
relay.impl.secondary            = opencode
relay.impl.fallback             = opencode
relay.review.fast               = grok
relay.review.long_context       = gemini
relay.ide.manual                = cursor
relay.expert_witness.ultraoracle = ultraoracle
relay.litmus.reviewer           = codex
relay.blueprint.reviewer_1      = agy
relay.blueprint.reviewer_2      = claude-code
relay.blueprint.reviewer_3      = grok
relay.blueprint.arbiter         = codex
relay.pr.lead                   = codex
relay.pr.backstop               = claude-code
relay.council.architect         = inline
relay.council.pragmatist        = agy
relay.council.critic            = codex
relay.council.researcher        = grok
relay.council.skeptic           = claude-code
```

Copyable config example:

```json
{
  "coding_agent": "codex",
  "avoid_coding_agent_for_review": true,
  "routes": {
    "relay.impl.primary": ["codex"],
    "relay.impl.secondary": ["opencode"],
    "relay.impl.fallback": ["opencode"],
    "relay.review.fast": ["grok"],
    "relay.review.long_context": ["gemini"],
    "relay.ide.manual": ["cursor"],
    "relay.expert_witness.ultraoracle": ["ultraoracle"],
    "relay.litmus.reviewer": ["codex"],
    "relay.blueprint.reviewer_1": ["agy"],
    "relay.blueprint.reviewer_2": ["claude-code"],
    "relay.blueprint.reviewer_3": ["grok"],
    "relay.blueprint.arbiter": ["codex"],
    "relay.pr.lead": ["codex"],
    "relay.pr.backstop": ["claude-code"],
    "relay.council.architect": ["inline"],
    "relay.council.pragmatist": ["agy"],
    "relay.council.critic": ["codex"],
    "relay.council.researcher": ["grok"],
    "relay.council.skeptic": ["claude-code"]
  }
}
```

Authority constraints remain false for all router/status roles. Codex is implementation-primary metadata and PR lead by user policy; OpenCode + Go is secondary/fallback draft-only metadata; Pi is deferred history. `avoid_coding_agent_for_review=true` remains active, so Codex same-provider review requires a fresh independent-session contract and otherwise remains degraded/non-dispatchable. All paths return only routing or fixture evidence and require Busdriver/Claude canonical finalization.

## Purchasing / tool-selection implication

Do not solve Claude quota pressure by adding another primary-controller agent. Codex remains implementation-primary metadata only; implementation must use an independently authorized path. If Claude-side gate/review/finalization quota remains the bottleneck, consider Claude quota/plan before adding Cursor as a pipeline dependency. Cursor remains a manual IDE sidecar.
