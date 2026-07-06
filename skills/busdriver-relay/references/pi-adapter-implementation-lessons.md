# Pi Adapter Implementation Lessons

Use this reference when continuing or reviewing the Pi Busdriver-shaped adapter work in `hermes-busdriver-relay`.

## Worktree and ownership

When the relay repo already has WIP, start a separate git worktree for the Pi adapter slice before making implementation changes. Do not edit the dirty primary relay worktree unless the user explicitly says to continue there. Record the worktree path in the run artifact/brief so later verification can identify ownership of the diff.

Implementation belongs in the Hermes relay repo, not Pi upstream/source. Treat Pi as an external runtime binary. Put relay-owned adapter code under paths such as:

```text
adapters/pi/
scripts/pi/
tests/contract/test_pi_adapter.py
docs/coding-workflow-authority-map.md
ADRs/0007-pi-tool-harness-adapter.md
skills/busdriver-relay/references/...
```

Do not patch Pi itself unless a later task explicitly scopes an upstream Pi SDK/extension fix.

## Target-state vs current-state wording

Avoid writing docs that make `--agent pi` look production-trusted before the in-repo proof passes. Use wording like:

```text
Pi lane    = current implemented constrained default draft lane after schema + wrapper + smoke + contract proof.
Codex lane = explicit fallback draft lane when Pi is blocked or unsuited.
OpenCode   = generic/opencode-go lane unless a Busdriver-compatible plugin/adapter is rebuilt and verified.
```

A successful Pi draft result should be `needs_busdriver_review`, never `done`, `complete`, `merged`, or `ready_to_merge`.

## Adapter hardening pattern

`bd_bash` should be argv-only and allowlist-only. Do not expose arbitrary shell strings, shell expansion, `bash -c`, network commands by default, finalization commands, or marker writes.

`bd_write_draft` should enforce repo-root containment, declared scope/include policy, protected path blocks (`.git/**`, `.claude/**`, `.opencode/**`, trusted-marker paths), symlink escape refusal, normalized path recording, `operation_id`, `before_hash`, and `after_hash`.

All non-authority worker artifacts must keep authority flags false:

```text
commit_allowed=false
push_allowed=false
pr_allowed=false
merge_allowed=false
marker_write_allowed=false
deploy_allowed=false
release_allowed=false
publish_allowed=false
finalization_allowed=false
```

## Useful contract-test pattern

Add fake-Pi tests before real Pi smoke. A fake Pi executable can read `BD_REPO_ROOT`, write the scoped draft file, emit `PI_BD_ARTIFACT_PATH`, and let the wrapper/agent-draft tests validate:

- schema/status parsing;
- authority flags false;
- postflight changed files in scope;
- commit history unchanged;
- `hermes-busdriver-agent-draft --agent pi` works through lock/preflight/postflight;
- `hermes-busdriver-agent-smoke --agent pi` accepts the adapter path.

Run targeted tests first, then broader relay contract tests. Real Pi smoke is optional/opt-in because it can consume provider/runtime quota; failure due to provider setup should be reported as a smoke blocker, not treated as contract failure.
