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
implementation.primary.current            = Codex
tool_harness.primary_candidate            = Pi
implementation.secondary.future_candidate = OpenCode only after adapter/smoke/tests; otherwise generic lane only
read_only.fast_review                     = Grok
read_only.long_context_review             = Gemini
manual.sidecar                            = Cursor
finalization.operator_path                = Hermes Delivery Mode, only on explicit user request
finalization.authority_path               = ClaudeCode / Busdriver
```

Short form:

```text
Codex writes normal drafts.
Pi constrains tool access, once adapter exists.
OpenCode experiments or compares, but is not Busdriver-compatible now.
Grok/Gemini critique.
Cursor is human/manual editing surface.
Hermes routes/verifies/delivers.
ClaudeCode/Busdriver authorizes.
```

## Current vs target-state lanes

Never phrase target-state workflow as already enabled production capability.

```text
Codex lane = current implemented normal draft lane.
Pi lane    = target-state adapter candidate; blocked for production mutating draft use until schema + wrapper + smoke + contract tests pass.
OpenCode   = generic/opencode-go lane unless a Busdriver-compatible adapter/plugin is rebuilt and verified.
```

If a doc contains `hermes-busdriver-agent-draft --agent pi`, label it as target state unless the in-repo Pi adapter proof has passed.

## Trusted evidence

Trusted evidence is live/verifiable state:

```text
git status
git diff
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
{ "cmd": "git", "args": ["diff", "--name-only"] }
```

Do not expose free-form shell strings, `bash -c`, shell expansion, inherited cwd outside repo root, network commands by default, finalization commands, or marker writes.

Allowlist examples:

```text
git status / diff / diff --name-only / rev-parse / log --oneline
test runners
linters
typecheckers
format checkers
safe read-only project commands
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

OpenCode can be used for generic draft experiments or explicitly user-requested comparison work. It is not part of the trusted Busdriver-compatible mutating pipeline unless a new adapter/plugin, result schema, launcher wrapper, postflight contract tests, real-agent smoke, and authority-flag validation exist.

## Clockwork wording

If the user says `Clockwork` in this context, treat it as an informal/typo reference to the ClaudeCode/Busdriver authority workflow unless they explicitly define a separate tool. Do not create a formal Clockwork layer in docs.
