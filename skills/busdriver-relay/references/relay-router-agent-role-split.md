# Relay router agent role split — July 2026

**Current production status:** the role map below is resolver/routing metadata, not a production launcher. Pi and OpenCode remain non-programmatic with `programmatic_dispatch_allowed=false`, `adapter_verified=false`, and `dispatch_allowed=false` under `agent_containment_and_credential_broker_unavailable`. Adapter behavior exists only in non-installed fixture provenance.

## Durable decision

For Busdriver/Hermes relay work, do **not** add Pi, OpenCode, Grok, Gemini, Zed, or UltraOracle as competing workflow authorities. The stable split is:

```text
Busdriver + Claude Code = canonical authority, hooks, gates, litmus, PR-grind, finalization
Hermes = relay/router/status/Phase 0/locks/handoff/Delivery Mode support
Pi = default constrained implementation draft worker
OpenCode + Go = Pi fallback / China-model comparison candidate; repo-changing fallback requires adapter/plugin proof
Codex = PR lead / review analysis; not the normal implementation fallback
Claude Code = authority / backstop path
Grok = Hermes-side relay.review.fast read-only reviewer / PR-comment triage
Gemini = Hermes-side relay.review.long_context read-only architecture/spec reviewer
Zed = manual IDE sidecar; edits are treated as human/manual dirty tree
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
relay.impl.primary              = pi
relay.impl.secondary            = opencode
relay.impl.fallback             = opencode
relay.review.fast               = grok
relay.review.long_context       = gemini
relay.ide.manual                = zed
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
  "coding_agent": "pi",
  "avoid_coding_agent_for_review": true,
  "routes": {
    "relay.impl.primary": ["pi"],
    "relay.impl.secondary": ["opencode"],
    "relay.impl.fallback": ["opencode"],
    "relay.review.fast": ["grok"],
    "relay.review.long_context": ["gemini"],
    "relay.ide.manual": ["zed"],
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

Authority constraints remain false for all router/status roles. Pi is preferred implementation route metadata and OpenCode is fallback/comparison route metadata, but neither may mutate a production draft tree while the containment/credential-broker blocker is active. Historical non-installed harnesses may exercise fixture-only mutation contracts; Codex remains a review/backstop lane by default. All paths return only routing or fixture evidence and require Busdriver/Claude finalization.

## Purchasing / tool-selection implication

Do not solve Claude quota pressure by adding another primary-controller agent. Pi remains the preferred future implementation route, but production dispatch is currently blocked; implementation must route through Busdriver/Claude or an explicitly approved bootstrap path. If Claude-side gate/review/finalization quota remains the bottleneck, consider Claude quota/plan before adding Zed as a pipeline dependency. Zed can remain a manual IDE sidecar.
