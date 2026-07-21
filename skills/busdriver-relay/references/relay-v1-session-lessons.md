> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Relay v1 Session Lessons

> **HISTORICAL / SUPERSEDED / NON-PRODUCTION.** This v1 session record is context only,
> not current operating guidance or dispatch proof. Current production agent dispatch is
> fixed `policy_blocked` by `agent_containment_and_credential_broker_unavailable`; runnable
> agent-draft and agent-smoke behavior exists only in non-installed test fixtures.

Use current project guidance and policy tests when maintaining Hermes-side Busdriver
relay/status tooling. The statements below describe the historical v1 design session.

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

## H13 runtime-check lesson

`hermes-busdriver-runtime-check` is a read-only checker, not a gate runner. Its normal Hermes result should be:

```text
hook_manifest_available=true
gate_hooks_declared=true
inside_claude_code_hook_invocation=false
mutating_launcher_allowed=false
```

That is a PASS for the relay boundary: Hermes can see Busdriver hooks but is not inside the Claude Code hook runtime. Do not interpret this as permission to launch mutating finalization work; it proves the opposite until a future v2 supplies a real runtime-equivalence mechanism.

## Equivalent gate-runner lesson

The v1 design proposed this generic gate sequence:

```text
hermes-busdriver-gate preflight
  → scoped agent implementation draft
  → hermes-busdriver-gate postflight
```

That sequence is historical design context, not a production capability. Current production
dispatch does not enable Codex or any other agent and cannot be unlocked by user approval,
CLI flags, or environment variables.

The old runnable `hermes-busdriver-agent-draft` sequence survived only as a non-installed
contract fixture for schema/scope/cleanup tests. The installed production entrypoint stops
after parsing with `agent_containment_and_credential_broker_unavailable` before repository,
HOME, credential, lock, gate, run-directory, or worker handling.

Historical real-adapter smoke results were fixture evidence only and never proved production
containment or dispatchability. The installed `hermes-busdriver-agent-smoke` now returns the
same fixed blocker immediately after parsing and never creates a repository or invokes Git.
