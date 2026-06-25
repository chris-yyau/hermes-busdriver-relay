# ADR 0004 — Draft Agent Launcher

## Status

Accepted as the first executable Hermes-side agent runner.

## Context

The user wants Hermes to keep implementation moving when Claude Code quota is unavailable. The previous ADR introduced `hermes-busdriver-gate` as the equivalent preflight/postflight layer, but a human still had to manually run an agent between the two gate commands.

## Decision

Add `scripts/hermes-busdriver-agent-draft` as the first generic executable wrapper:

```text
hermes-busdriver-lock acquire --operation agent-draft
  → hermes-busdriver-gate preflight
  → guarded agent command
  → hermes-busdriver-gate postflight
  → hermes-busdriver-lock release
  → JSON report
```

The launcher supports named agents (`codex`, `opencode`, `droid`, `agy`, `grok`, `noop`) plus a `custom` shell command mode for tests and advanced/manual adapters.

## Safety Contract

A successful run returns `status=needs_busdriver_review`, not `done`.

The launcher may leave working-tree changes, but it does not finalize them. The postflight decision continues to keep these false:

```json
{
  "commit_allowed": false,
  "push_allowed": false,
  "pr_allowed": false,
  "merge_allowed": false,
  "deploy_allowed": false
}
```

## Guards

The launcher layers the following controls:

1. Hermes-owned single-flight lock under `~/.hermes/busdriver-relay/locks`.
2. Gate preflight before the agent starts.
3. A best-effort PATH guard that shadows common finalization commands:
   - blocks `git commit`, `git push`, `git merge`, `git rebase`, `git reset`, `git tag`;
   - blocks `gh pr create`, `gh pr merge`, `gh pr close`, release mutations, repo delete, and issue create/comment.
4. Gate postflight after the agent exits.
5. JSON report and saved run artifacts under `~/.hermes/busdriver-relay/agent-runs/`.

## Known Limits

The PATH guard is defense in depth, not a complete sandbox. An agent that deliberately calls an absolute binary path may bypass it. The postflight gate still detects local commit changes through `same_head_as_baseline`, scope violations, `.git/hooks` tampering, and ignored-file tampering. External side effects remain prohibited by policy and must not be requested in prompts.

## Future Work

- Stronger sandboxing / command broker if finalization authority is ever added.
- Structured per-agent adapters for Codex/OpenCode/Droid/Agy/Grok output schemas.
- Commit-capable finalization gates after litmus/review/secret/CI policies are modeled.

## Real-Agent Smoke

`hermes-busdriver-agent-smoke` is an opt-in smoke runner for real model-backed adapters. It creates a throwaway git repo and calls `hermes-busdriver-agent-draft` with the selected agent. It is not part of the default contract suite because it can consume provider quota/tokens.

The Codex and OpenCode adapters have been verified against temporary repos: Codex added `src/codex_smoke.txt`, OpenCode added `src/opencode_smoke.txt`, postflight reported only the scoped file, the verifier passed, HEAD remained unchanged, and the final status was `needs_busdriver_review`.

OpenCode requires one extra environment detail: `hermes-busdriver-agent-draft` exports `BUSDRIVER_PLUGIN_ROOT` and `BUSDRIVER_STATE_DIR=.opencode` to the agent process. Without this, the user's OpenCode Busdriver plugin may fall back to `~/.config/opencode` and fail closed on missing gate scripts.
