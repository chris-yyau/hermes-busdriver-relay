# Relay v1 Session Lessons

Use this reference when maintaining Hermes-side Busdriver relay/status tooling.

## Naming

Avoid names that imply Hermes owns Busdriver orchestration. In this session, `busdriver-orchestrator` and `hermes-busdriver-bridge` were rejected/renamed because they blur the authority boundary. Prefer `busdriver-relay` for the Hermes skill and `hermes-busdriver-relay` for the private repo: relay means Hermes forwards/statuses/coordinates without becoming the Busdriver orchestrator.

## UltraOracle retry discipline

When an UltraOracle call fails but a full-prompt retry succeeds with `status=ok`, stop. Do not run more retries just because a prior instruction said “try twice”; the durable rule is retry-on-failure, not fixed-count retries after success. If an unnecessary retry has already started, kill it rather than waste tokens.

## busdriver.json route drift

Do not assume `~/.claude/busdriver.json` is complete. Compare live Busdriver source-of-truth before reporting effective routes. In this session, source files showed two route keys that the user config had not caught up with:

```json
"blueprint-review.reviewer_3": ["grok", "droid"],
"council.researcher": ["grok", "droid"]
```

Evidence sources used:

- `skills/blueprint-review/SKILL.md`
- `skills/council/SKILL.md`
- `scripts/lib/resolve-cli.sh`
- `docs/examples/busdriver.json`
- `README.md`

Patch user config only after backing it up and validating JSON. Then verify with `resolve_role_cli` for every role, not just by reading the file.

## Relay v1 artifact boundary

The private repo `hermes-busdriver-relay` should remain Hermes-owned only:

- `skills/busdriver-relay/SKILL.md`
- `scripts/hermes-busdriver-status`
- `scripts/hermes-busdriver-lock`
- `scripts/hermes-busdriver-smoke`
- contract tests and ADRs

Do not vendor Busdriver, Claude plugins, MCP config, runtime markers, cookies, or secrets. Keep locks in `~/.hermes/busdriver-relay/locks`, not `.claude/`.

## Status probe lessons

`hermes-busdriver-status` should be read-only and report:

- live `hooks/hooks.json` inventory;
- critical file hashes for drift detection;
- user/default/effective route resolution;
- active marker summaries without treating marker presence as approval;
- relay lock state;
- repo dirty state.

Treat `resolve-cli.sh --json` as useful but not sufficient: it reports CLI availability and default reviewer metadata, not full per-role resolution. A relay status tool should model default route chains and/or verify with `resolve_role_cli` where possible.

## Lock lessons

The single-flight lock is Hermes-owned state. When checking staleness, prefer the lock's recorded `ttl_seconds` over the current command's TTL; otherwise a later acquire with a longer TTL can incorrectly keep an older zero-TTL lock alive.

## Busdriver 1.71.0 surface updates

When pulling Busdriver source after PR #240/#241, remember source worktrees may diverge from installed marketplace plugins. Prefer a clean `main` worktree for source-of-truth comparison; do not reset a deleted PR branch with local commits just to make versions match.

1.71.0 replaced `oracle-max` with `ultra-oracle`:

- scripts: `scripts/lib/ultra-oracle.sh`, `scripts/lib/ultra-oracle-config.sh`
- config block: `ultraOracle`
- opt-out marker: `skip-ultra-oracle.local`
- artifact dir: `$BUSDRIVER_STATE_DIR/ultra-oracle/`

1.71.0 also added routing/domain surface that Hermes should discover JIT instead of hardcoding: `vue-reviewer`, `php-reviewer`, `vue-patterns`, `kubernetes-patterns`, `config-gc`, `skill-scout`, and `agent-self-evaluation`. Always read `skills/orchestrator/domain-supplements.md` and `skills/orchestrator/tasks-catalog.md` live before deciding a route.

`finishing-a-development-branch` now explicitly requires linked worktree detection and human-confirmed cleanup. Hermes must not auto-remove worktrees, especially harness-managed `.claude/worktrees/*` / `${BUSDRIVER_STATE_DIR}/worktrees/*` worktrees.
