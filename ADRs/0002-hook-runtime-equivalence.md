# ADR 0002 — Hook Runtime Equivalence Before Mutating Launcher

## Status

Accepted for Relay v1/v2 boundary.

## Context

Busdriver's strongest safety guarantees come from Claude Code harness hooks (`PreToolUse`, `PostToolUse`, `SessionStart`, `Stop`, etc.) registered in `hooks/hooks.json`. These hooks intercept tool calls at the harness level and can block operations such as `git commit`, `gh pr create`, `gh pr merge`, file writes while design review is pending, hook bypass flags, destructive Bash, and scope violations.

Hermes can run shell commands and read Busdriver files, but a normal Hermes-launched shell process is not itself a Claude Code tool invocation. Running a Busdriver script from Hermes does not automatically cause Claude Code's `PreToolUse`/`PostToolUse` hooks to intercept inner shell commands executed by that script.

## Decision

Relay v1 remains read-only/status-only. A repo-mutating launcher such as `hermes-busdriver-codex-goal` MUST NOT be implemented or used until hook-runtime equivalence is proven.

The repository provides `scripts/hermes-busdriver-runtime-check` to make the current boundary explicit. In normal Hermes execution it reports:

- hook manifest is visible;
- gate hooks are declared;
- the current process is not the Claude Code hook runtime;
- Claude hooks will not intercept inner shell commands of this process;
- mutating launcher is not allowed.

## Equivalence options for a future v2

At least one of these must be true before a mutating launcher can exist:

1. **Enter same runtime** — the launcher runs as/through a Claude Code tool invocation such that Busdriver hooks really intercept the gated action.
2. **Explicit equivalent checks** — the launcher directly invokes Busdriver-equivalent gate checks, validates their JSON decisions, and fails closed on missing/blocked/parse-error/timeout results.
3. **Refuse gated operations** — the launcher can dispatch planning/read-only work but refuses commit, push, PR, merge, deploy, marker writes, and finalization.
4. **Local-only sandbox** — the launcher is technically constrained so it cannot push/PR/merge/deploy/finalize and cannot forge markers; outputs require later Busdriver/Claude review before external side effects.

## Consequences

- `hermes-busdriver-status`, `hermes-busdriver-lock`, `hermes-busdriver-smoke`, and `hermes-busdriver-runtime-check` are allowed.
- `hermes-busdriver-codex-goal` remains deferred.
- Relay smoke includes runtime-check so the blocked status is continuously visible.
- Passing smoke does **not** mean mutating work is safe; it means the relay correctly reports that mutating work is blocked.

## Verification

```bash
scripts/hermes-busdriver-runtime-check \
  --plugin-root /path/to/busdriver \
  --repo /path/to/repo \
  --pretty
```

Expected normal Hermes result:

```json
{
  "runtime_equivalence": {
    "hook_manifest_available": true,
    "gate_hooks_declared": true,
    "inside_claude_code_hook_invocation": false,
    "hermes_shell_is_claude_hook_runtime": false,
    "claude_hooks_will_intercept_inner_shell_commands": false,
    "mutating_launcher_allowed": false
  }
}
```
