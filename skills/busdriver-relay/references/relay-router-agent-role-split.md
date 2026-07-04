# Relay router agent role split — July 2026

## Durable decision

For Busdriver/Hermes relay work, do **not** add Pi or Cursor/OpenCode/Grok/Gemini as competing workflow authorities. The stable split is:

```text
Busdriver + Claude Code = canonical authority, hooks, gates, litmus, PR-grind, finalization
Hermes = relay/router/status/Phase 0/locks/handoff/Delivery Mode support
Codex = primary fallback implementation draft worker
OpenCode + Go = secondary draft-adapter/sidecar candidate, initially read-only/candidate
Grok = Hermes-side relay.review.fast read-only reviewer / PR-comment triage
Gemini = Hermes-side relay.review.long_context read-only architecture/spec reviewer
Cursor = manual IDE sidecar; edits are treated as human/manual dirty tree
Pi = deferred; not part of the current pipeline unless a future capability gap appears
```

Hard rule: **Only Claude/Busdriver may claim done. All non-Claude agents produce draft/review evidence only.**

## Important distinction

Busdriver already has canonical multi-CLI skills/routes (e.g. blueprint, council, litmus, PR-grind, external review routes such as codex/agy/grok/droid). Pi/Hermes-side routing must not duplicate those as authority. If a Busdriver-native route exists for a gate, prefer Busdriver.

Hermes-side roles such as `relay.review.fast=grok` and `relay.review.long_context=gemini` are advisory relay/router roles, not Busdriver native roles. The same model/CLI can appear in two authority domains:

- Busdriver invokes Grok/Codex/Agy/Droid inside blueprint/council/litmus/PR-grind: Busdriver interprets the result under Busdriver workflow semantics.
- Hermes invokes Grok/Gemini as `relay.*` roles: advisory evidence only, read-only, no finalization authority.

## Router work items

The next safe relay build is a read-only Hermes router/status expansion, not Pi:

1. ADR for relay router agent roles.
2. Relay-owned sample config under `~/.hermes/busdriver-relay/config.json` (never `~/.claude/busdriver.json`).
3. Extend role inventory/resolver/status for:
   - `relay.impl.primary = codex`
   - `relay.impl.secondary = opencode`
   - `relay.review.fast = grok`
   - `relay.review.long_context = gemini`
   - `relay.ide.manual = cursor`
4. Add a read-only `hermes-busdriver-router` helper that recommends routes from task kind/quota state without dispatching agents or granting authority.
5. Dogfood Codex draft path through existing `hermes-busdriver-agent-draft --agent codex`.
6. Treat OpenCode+Go as a candidate only after read-only smoke and isolated draft smoke.
7. Keep Grok/Gemini read-only until data-egress and invocation contracts exist.

## Suggested config shape

Stay compatible with the current relay-owned config contract:

```json
{
  "coding_agent": "codex",
  "avoid_coding_agent_for_review": true,
  "routes": {
    "relay.impl.primary": ["codex"],
    "relay.impl.secondary": ["opencode"],
    "relay.review.fast": ["grok"],
    "relay.review.long_context": ["gemini"],
    "relay.ide.manual": ["cursor"],
    "relay.pr.backstop": ["codex"]
  }
}
```

Authority constraints remain false for all router/status roles. Only the separately gated Codex draft launcher may mutate the draft working tree, and it still returns `needs_busdriver_review`.

## Purchasing / tool-selection implication

Do not solve Claude quota pressure by adding another主控 agent. Use Codex as the primary fallback implementation worker; if Claude-side gate/review/finalization quota remains the bottleneck, consider Claude quota/plan before adding Cursor as a pipeline dependency. Cursor can remain a manual IDE sidecar.