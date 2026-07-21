# Pi Adapter Implementation Lessons

**Superseded for production execution.** This reference preserves target-state adapter-hardening and historical non-installed fixture lessons. Production Pi/OpenCode dispatch is blocked before repository, HOME/state, credential, lock, prompt, or worker handling by `agent_containment_and_credential_broker_unavailable`.

Use this reference only when reviewing fixture provenance or designing a separately reviewed future containment and parent-held credential-broker slice in `hermes-busdriver-relay`; it is not a current production procedure.

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

Avoid wording that makes `--agent pi` look production-trusted. Current wording must be:

```text
Pi lane    = preferred route metadata; contract proven only in non-installed fixtures; production dispatch blocked.
OpenCode   = fallback/comparison route metadata; contract proven only in non-installed fixtures; production dispatch blocked.
Codex lane = PR lead/review/backstop by default; implementation only by explicit exception.
```

Only a future independently reviewed OS-containment and parent-held credential-broker implementation could change those dispatchability fields. A future successful Pi draft result would still be `needs_busdriver_review`, never `done`, `complete`, `merged`, or `ready_to_merge`.

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

## Historical non-installed contract-test pattern

Fake-Pi tests remain useful only as fixture provenance. A fake Pi executable can read `BD_REPO_ROOT`, write the scoped draft file, emit `PI_BD_ARTIFACT_PATH`, and let a non-installed runpy harness validate:

- schema/status parsing;
- authority flags false;
- postflight changed files in scope;
- commit history unchanged;
- the fixture-only wrapper/lock/preflight/postflight shape;
- parser and authority-negative production responses.

These tests do not prove production descendant containment, credential brokering, or dispatch authority. Real-model smoke is historical/optional fixture evidence and must not be represented as a production command or production capability.
