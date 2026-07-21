> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Busdriver Relay Session Notes — Initial Repo Scaffold

Use this reference when continuing Hermes-side Busdriver integration work.

## Naming decision

- Hermes-side skill name: `busdriver-relay`.
- Private repo name: `hermes-busdriver-relay`.
- Avoid `busdriver-orchestrator`, `hermes-busdriver-orchestrator`, or similar names because Busdriver already has an `orchestrator` skill and the name falsely implies Hermes owns Busdriver's routing authority.
- `relay` was chosen because it communicates handoff/forwarding/status without implying execution, gate enforcement, or authority.

## Repository boundary

Private repo created:

```text
GitHub: https://github.com/chris-yyau/hermes-busdriver-relay
Local:  <relay-repo>
```

Repo is for Hermes-owned artifacts only:

- `skills/busdriver-relay/SKILL.md`
- read-only status tooling (`scripts/hermes-busdriver-status`)
- lock/smoke tooling (`scripts/hermes-busdriver-lock`, `scripts/hermes-busdriver-smoke`)
- contract tests
- ADRs / docs

Do not vendor/copy:

- Busdriver itself
- Claude plugins / MCP config
- runtime markers/state under `.claude` or `.opencode`
- credentials, browser cookies, secrets
- full Busdriver skill bodies

## First scaffold verification

Initial commit:

```text
3a609b0 feat: scaffold Hermes Busdriver relay
```

Validated:

- `scripts/hermes-busdriver-status` ran read-only against live Busdriver.
- It reported Busdriver `1.71.0`, hook events, key gate scripts, `resolve-cli.sh --json`, and dirty repo status.
- Contract test passed: `1 passed in 0.04s`.

## Retry lesson

When invoking UltraOracle/council-style expensive review, respect retry-on-failure semantics. If a retry returns `ok`, do not run additional attempts just to satisfy an earlier ambiguous “try twice” phrase unless the user explicitly says to run extra successful attempts.
