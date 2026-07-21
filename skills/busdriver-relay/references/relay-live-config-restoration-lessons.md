> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Relay live config restoration lessons

## Trigger

Use these notes when the user asks about the previously assigned Busdriver Relay role config, current backstop model/agent, or why resolver output does not match the intended role map.

## Lessons

1. **Separate target policy from live resolver state.**
   - A prior role-map discussion or repo documentation is not the same as the live relay config.
   - The resolver defaults may still report stale values when `~/.hermes/busdriver-relay/config.json` is missing.
   - Say this explicitly: “the target was assigned, but the live config file is missing/drifted, so the resolver fell back to defaults.”

2. **Check the live config before answering model/agent questions.**
   - Inspect `~/.hermes/busdriver-relay/config.json` (or the `--relay-config` path in use).
   - Then verify with `scripts/hermes-busdriver-relay-role --role relay.pr.backstop --pretty` from the relay repo.
   - If `relay_config.exists=false`, do not conclude “we never configured it”; classify it as missing live config / config drift.

3. **Current user target policy after the Pi/OpenCode/Codex correction.**
   - `coding_agent`: `pi` for implementation drafts.
   - `avoid_coding_agent_for_review`: `true` so review/backstop does not silently use the coding agent.
   - Resolver-known role map to restore in `routes`:
     - `relay.litmus.reviewer`: `codex`
     - `relay.blueprint.reviewer_1`: `agy`
     - `relay.blueprint.reviewer_2`: `claude-code`
     - `relay.blueprint.reviewer_3`: `grok`
     - `relay.blueprint.arbiter`: `codex` (fresh Codex conceptually)
     - `relay.pr.lead`: `codex` (fresh Codex conceptually)
     - `relay.pr.backstop`: `claude-code`
     - `relay.council.architect`: `inline`
     - `relay.council.pragmatist`: `agy`
     - `relay.council.critic`: `codex`
     - `relay.council.researcher`: `grok`
     - `relay.council.skeptic`: `claude-code`
   - Full role-map resolver state after PR #113: `relay.impl.primary=pi`, `relay.impl.secondary=opencode`, `relay.impl.fallback=opencode`, `relay.review.fast=grok`, `relay.review.long_context=gemini`, `relay.ide.manual=zed`, and `relay.expert_witness.ultraoracle=ultraoracle` are first-class resolver roles.
   - Dispatchability is still separate from resolver readiness: OpenCode fallback/comparison routes and the Zed manual sidecar must remain `programmatic_dispatch_allowed=false` / `dispatch_allowed=false` until a dedicated adapter or manual-programmatic proof exists.

4. **Respect the current config schema and resolver boundary.**
   - The live resolver currently supports root-level `coding_agent`, `avoid_coding_agent_for_review`, and `routes` keyed by known `relay.*` roles.
   - After PR #113, the resolver accepts the full 19-role map. Unknown route keys outside that inventory should still fail closed as `unknown_role`.
   - Do not add unsupported top-level keys such as `opencode_fallback`; represent fallback/comparison lanes as route metadata plus explicit non-dispatchable adapter status until a repo/schema follow-up proves a new adapter.

5. **Verification shape to report.**
   - Backstop is restored when resolver output shows:
     - `coding_agent = pi`
     - `avoid_coding_agent_for_review = true`
     - `relay.pr.backstop selected_agent = claude-code`
     - `source = relay_config`
     - `same_as_coding_agent = false`
     - `degraded = false`
   - Also verify the full 19-role resolver inventory exits 0 with `ok=true` and `degraded=false`; reserve `unknown_role` only for keys outside that inventory.

## Pitfall

If the user says “之前不是分配好 … config 嗎”, do not re-explain from defaults as if no prior allocation existed. Acknowledge the prior allocation, classify the issue as live-config drift/missing file, and restore/verify the live file when the user approves (e.g. “好”).
