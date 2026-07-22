# Coding Workflow Authority Map v0.1

Use this reference when routing repo-changing work across ClaudeCode/Busdriver, Hermes, Codex, Pi, OpenCode, and read-only reviewer lanes.

## First principle

This document defines **authority boundaries**, not agent quality rankings.

```text
A stronger model does not get more authority.
A faster model does not get more authority.
A paid subscription does not get more authority.
```

Authority comes only from:

1. ClaudeCode / Busdriver trusted runtime;
2. explicitly implemented Hermes-equivalent gates; or
3. explicit Hermes Delivery Mode with required evidence.

Workers produce draft evidence; Hermes routes and verifies evidence and may operate explicit Delivery Mode only when the user asks; ClaudeCode/Busdriver remains the sole canonical finalization authority.

## Role map

```text
authority.canonical                       = ClaudeCode / Busdriver
operator.router                           = Hermes
operator.verifier                         = Hermes
implementation.primary.current            = Codex metadata only; no production dispatcher; relay_role_dispatcher_unavailable
implementation.secondary.current          = OpenCode + Go fallback draft-only metadata; production dispatch blocked by agent_containment_and_credential_broker_unavailable
implementation.deferred.history           = Pi adapter harness/schema history retained; not current or preferred
review.pr_lead                            = Codex metadata; same-provider review requires a fresh independent-session contract
review.backstop                           = Claude Code / Busdriver authority path
read_only.fast_review                     = Grok
read_only.long_context_review             = Gemini
manual.sidecar                            = Cursor
finalization.operator_path                = Hermes Delivery Mode, only on explicit user request
finalization.authority_path               = ClaudeCode / Busdriver
```

Short form:

```text
Codex is implementation-primary metadata and PR lead by user policy; no relay-role entry dispatches it.
OpenCode + Go is secondary/fallback draft-only metadata; its contract is verified only in non-installed harnesses and production launch is blocked.
Pi is deferred. Its explicit harness/adapter history remains useful evidence, but it is not the current, default, or preferred route.
Codex PR-lead metadata does not prove review independence; with `avoid_coding_agent_for_review=true`, same-provider review remains non-dispatchable without a fresh independent-session contract.
Grok/Gemini critique.
Cursor is the human/manual editing surface.
Hermes routes/verifies/delivers.
ClaudeCode/Busdriver authorizes.
```

## Current vs target-state lanes

Never phrase target-state workflow as already enabled production capability.

```text
Codex lane    = implementation-primary and PR-lead metadata only; production relay-role dispatch is unavailable.
OpenCode + Go lane = secondary/fallback draft-only metadata; adapter contract verified in non-installed harnesses; production dispatch is policy-blocked.
Pi lane       = deferred adapter history, not a current route.
```

A doc may show `hermes-busdriver-agent-draft --agent pi` only as an expected blocked production probe while `agent_containment_and_credential_broker_unavailable` is active. In-repo schema, wrapper, contract tests, and fake-adapter smoke prove the non-installed adapter contract; they do not prove production dispatch.

## Trusted evidence

Trusted evidence is live/verifiable state:

```text
git -c core.fsmonitor=false status --porcelain=v1 --untracked-files=all
git -c core.fsmonitor=false diff --no-ext-diff --no-textconv
git log
test output
postflight report
worker artifact
event log
lock status
PR checks
review comments
```

Do not trust worker prose like `done`, `complete`, `ready_to_merge`, or `merged`. Treat it as `worker_self_report_only` unless backed by live evidence and authority.

## Common worker envelope

All non-authority workers should normalize to a minimum envelope like:

```json
{
  "schema": "hermes-worker-result/v0",
  "worker": "codex|pi|opencode|grok|gemini",
  "mode": "mutating_draft|read_only_review|generic_draft",
  "ok": false,
  "status": "needs_busdriver_review",
  "repo": "...",
  "branch": "...",
  "base_head": "...",
  "post_head": "...",
  "changed_files": [],
  "tests_run": [],
  "review_findings": [],
  "blockers": [],
  "authority": {
    "commit_allowed": false,
    "push_allowed": false,
    "pr_allowed": false,
    "merge_allowed": false,
    "marker_write_allowed": false,
    "deploy_allowed": false,
    "finalization_allowed": false
  },
  "artifacts": [],
  "event_log": []
}
```

Hard rule: every non-authority worker result must keep all authority flags false.

## Retained Pi adapter hardening history

Pi's value is not that it can write code; Pi's value is that it can only write through the tool boundary we define.

### `bd_bash`

Use argv-only, allowlist-only command execution:

```json
{ "cmd": "git", "args": ["-c", "core.fsmonitor=false", "diff", "--no-ext-diff", "--no-textconv", "--name-only"] }
```

Any `git diff` form exposed through `bd_bash` must inject `-c core.fsmonitor=false` and include `--no-ext-diff` plus `--no-textconv` so repo/user-configured fsmonitor hooks and external diff drivers/textconv filters cannot execute.

Any `git status` form exposed through `bd_bash` must inject `-c core.fsmonitor=false` before `status` so repo/user-configured fsmonitor hook commands cannot execute.

Do not expose free-form shell strings, `bash -c`, shell expansion, inherited cwd outside repo root, network commands by default, finalization commands, or marker writes.

Current implemented allowlist examples are intentionally git-only:

```text
git -c core.fsmonitor=false status --porcelain=v1 --untracked-files=all
git -c core.fsmonitor=false diff --no-ext-diff --no-textconv
git -c core.fsmonitor=false diff --no-ext-diff --no-textconv --name-only
git -c core.fsmonitor=false diff --no-ext-diff --no-textconv --stat
git rev-parse HEAD
git log --oneline
```

Always forbid:

```text
git commit / push / merge / rebase / reset / destructive checkout
gh pr create / merge
gh issue/comment mutation
rm -rf
broad chmod/chown
curl/wget unless explicitly approved
deploy/release/publish
trusted marker writes
```

### `bd_write_draft`

Require:

```text
repo-root containment
scope.include only
no .git/**
no .claude/**
no .opencode/**
no trusted marker paths
symlink escape refusal
normalized path recording
operation_id
before_hash
after_hash
```

## Delivery Mode dirty-tree ownership

Hermes must not commit a dirty tree unless every dirty path is classified as:

1. produced by the current run;
2. explicitly included in the delivery scope; or
3. explicitly accepted by the user as preexisting work to include.

This prevents Codex changing `A`, Cursor/manual edits changing `B`, and Hermes accidentally committing `A+B` just because tests are green.

## Reviewer data-egress gate

Before sending code/diff/spec to Grok/Gemini or other external reviewers:

```text
classify secrets / credentials / customer data / proprietary code
minimize context
redact env/secrets/logs
prefer diff slices over whole repo dumps
record what was sent
```

Long-context review is powerful but should not become a reason to dump whole repositories blindly.

## OpenCode lane

OpenCode + Go is the secondary/fallback draft-only adapter contract proven in non-installed harnesses. Production dispatch is blocked by `agent_containment_and_credential_broker_unavailable`; no current route launches OpenCode or copies credentials. Commit/push/PR/merge/marker/deploy/release/publish flags remain false.

## Clockwork wording

If the user says `Clockwork` in this context, treat it as an informal/typo reference to the ClaudeCode/Busdriver authority workflow unless they explicitly define a separate tool. Do not create a formal Clockwork layer in docs.
