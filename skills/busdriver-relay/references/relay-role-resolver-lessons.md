> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Relay Role Resolver Lessons

Date: 2026-06-28

`hermes-busdriver-relay-role` is a read-only, dispatcher-facing resolver for one configured relay equivalent role. Keep it fail-closed and distinct from Busdriver-native Claude runtime authority.

## Contract

- Invoke `scripts/hermes-busdriver-status` as a subprocess; do not import executable scripts with `importlib` or `SourceFileLoader`.
- Resolve only one requested role, or list known roles with `--list-roles`.
- Exit `0` only when the requested role exists, the selected role entry shape is valid, `selected_agent` is a string, `degraded` is boolean `false`, and top-level relay config has no parse/shape/routes/coding_agent/avoid_coding_agent errors.
- Unknown roles exit nonzero with `dispatch_allowed=false`.
- Degraded roles, malformed selected role entries, invalid selected_agent/degraded shapes, malformed status output, status subprocess failure, status timeout, and invalid CLI invocations all fail closed.
- Every stdout payload, including invalid invocations and `--list-roles`, carries root authority flags:
  - `read_only=true`
  - `dispatch_allowed=<true only for safe resolved role>`
  - `mutation_allowed=false`
  - `finalization_allowed=false`
  - `not_busdriver_native_claude_runtime=true`
- Role-resolution payloads also carry the same authority flags in nested `decision` for nested consumers.

## Backstop-driven pitfalls

1. **Top-level config errors must block dispatch.** A selected role can look healthy while global relay config is malformed (for example empty `coding_agent`). Treat top-level parse/shape/routes/coding_agent/avoid_coding_agent errors as fail-closed.
2. **Root authority flags matter.** Some consumers read only the root envelope, not nested `decision`; root must include `dispatch_allowed`, `mutation_allowed`, `finalization_allowed`, and runtime identity flags.
3. **Invalid CLI invocations must return JSON.** Avoid argparse plain-text stderr/empty stdout paths. Use `exit_on_error=False`, catch parse errors, disable abbreviated long options with `allow_abbrev=False`, and emit JSON fail-closed payloads on stdout.
4. **Subprocess output must be revalidated.** Validate top-level status JSON shape, `relay_config`, `relay_equivalent_roles`, `roles`, selected role entry, `selected_agent`, and `degraded` before considering dispatch.
5. **Wrapper timeout should exceed child timeout.** The resolver wrapper timeout must be longer than the status probe's own timeout so the child can produce structured timeout/error JSON first when possible.
6. **Downstream status consumers must re-check authority flags.** If delivery/finalization status accepts a resolver output, it should require the resolver schema plus root/nested authority invariants (`mutation_allowed=false`, `finalization_allowed=false`, `not_busdriver_native_claude_runtime=true`) before marking the optional role evidence OK.

## Delivery-status integration

`hermes-busdriver-delivery-status --relay-role ... --relay-config ...` may include resolver output as evidence, but it must remain advisory. A non-dispatchable or authority-unsafe role result becomes a warning such as `relay_role_not_dispatchable`; it never grants commit, push, PR, merge, marker-write, deploy, release, or publish authority.
