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

Workers produce draft evidence; Hermes verifies evidence; ClaudeCode/Busdriver owns canonical authority; Delivery Mode runs only when the user explicitly asks.

## Role map

```text
authority.canonical                       = ClaudeCode / Busdriver
operator.router                           = Hermes
operator.verifier                         = Hermes
implementation.primary.current            = Pi adapter contract verified in non-installed harnesses; production dispatch blocked by agent_containment_and_credential_broker_unavailable
implementation.fallback.current            = OpenCode adapter contract verified in non-installed harnesses; production dispatch blocked by agent_containment_and_credential_broker_unavailable
implementation.exception.explicit           = Codex only by explicit exception when Pi/OpenCode are blocked or unsuited
review.pr_lead_and_backstop                 = Codex / Claude Code per relay role config
read_only.fast_review                     = Grok
read_only.long_context_review             = Gemini
manual.sidecar                            = Zed
finalization.operator_path                = Hermes Delivery Mode, only on explicit user request
finalization.authority_path               = ClaudeCode / Busdriver
```

Short form:

```text
Pi is the default target adapter; its draft contract is verified only in non-installed harnesses and production launch is blocked.
OpenCode is the fallback/comparison target adapter; its contract is likewise verified only in non-installed harnesses and production launch is blocked.
Codex is PR lead / review / backstop-focused by default, with implementation only by explicit exception.
Grok/Gemini critique.
Zed is human/manual editing surface.
Hermes routes/verifies/delivers.
ClaudeCode/Busdriver authorizes.
```

## Current vs target-state lanes

Never phrase target-state workflow as already enabled production capability.

```text
Pi lane      = adapter contract verified in non-installed harnesses; production dispatch is policy-blocked.
OpenCode lane = adapter contract verified in non-installed harnesses; production dispatch is policy-blocked.
Codex lane    = PR lead / review / backstop-focused by default; implementation only by explicit exception.
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

## Pi adapter hardening rules

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

When the relay repo itself already has WIP, start new implementation slices in a separate git worktree/branch instead of reusing the dirty primary worktree. Record the selected worktree in artifacts/briefs. Only work in the existing relay worktree if the user explicitly accepts that scope.

This prevents Codex changing `A`, Zed/manual edits changing `B`, and Hermes accidentally committing `A+B` just because tests are green.

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

OpenCode is the fallback/comparison adapter contract proven in non-installed harnesses. Production dispatch is blocked by `agent_containment_and_credential_broker_unavailable`; no current route launches OpenCode or copies credentials. Commit/push/PR/merge/marker/deploy/release/publish flags remain false.

## Clockwork wording

If the user says `Clockwork` in this context, treat it as an informal/typo reference to the ClaudeCode/Busdriver authority workflow unless they explicitly define a separate tool. Do not create a formal Clockwork layer in docs.
