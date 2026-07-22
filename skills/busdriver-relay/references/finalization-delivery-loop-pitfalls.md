# Busdriver Relay Finalization / Delivery Loop Pitfalls

Use this reference when Hermes is operating a Busdriver-relay worktree through verification, review, Delivery Mode commit, push/PR, pr-grind, merge, and cleanup.

## Do not stop at a partial gate

When the user says “全部做好才停止” / “繼續完成”, treat summaries like “cannot PASS yet” as interim status only. Continue using tools until the next durable gate is reached or a true blocker requires user input. A final answer is only appropriate when:

- all requested delivery stages are complete, or
- tool limits/user instruction explicitly forbid more tools, or
- a non-recoverable blocker remains after trying the safe next step.

## Staged diff hash is the review identity

- Every review PASS is scoped to the exact staged diff hash it reviewed.
- If staged files or hash drift after dispatching a reviewer/subagent, that review cannot certify the current candidate.
- Before relying on review evidence, recompute and record:
  - `git diff --cached --no-ext-diff --no-textconv --no-color | shasum -a 256`
  - staged file list/stat
- If hash drifts, re-run review on the new hash rather than reusing stale PASS/FAIL.

## Review loop state can be consumed by prior runs

Busdriver litmus `run-review-loop.sh` may remove `.claude/litmus-state.md` after a PASS. If a later staged change invalidates the PASS, reinitialize before rerunning:

```bash
LITMUS_SCRIPTS="${CLAUDE_PLUGIN_ROOT}/skills/litmus/scripts"
bash "$LITMUS_SCRIPTS/init-review-loop.sh"
BUSDRIVER_PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT" \
CLAUDE_PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT" \
LITMUS_MAX_WEIGHTED_LINES=<current_weighted_lines_or_policy_override> \
LITMUS_TIMEOUT=1200 \
bash "$LITMUS_SCRIPTS/run-review-loop.sh"
```

A PASS before later staged edits is not enough; init + review again for the final hash.

## Delivery Mode commit gate needs marker hash support

`hermes-busdriver-deliver commit` may fail with `commit_litmus_staged_diff_hash_missing` when the litmus status surface accepts a marker as fresh but does not expose a diff hash for the commit gate. The safe fix pattern is:

1. make the litmus status script expose `markers.litmus_passed.diff_hash` for 64-hex external review markers;
2. cover it with contract tests;
3. rerun targeted + full contract tests;
4. rerun fresh Busdriver review for the new staged hash;
5. retry Delivery Mode commit.

Do not bypass the hash check.

## Finalization trust-boundary hardening checklist

For PR/pre-PR verdict files, gate inputs as untrusted:

- repo-confine the path;
- reject symlinks and symlink path components;
- require regular files;
- use bounded reads and enforce max bytes;
- decode UTF-8 fail-closed;
- require explicit `reviewed_diff_hash` rather than accepting generic `diff_hash` aliases;
- trusted-writer payloads should use the validated hash, not caller-provided fallbacks.

For PR create / pr-grind authority surfaces:

- default omitted PR base to the observed/reviewed base, not an implicit default;
- use owner-qualified PR head (`owner:branch`) and fail closed if the origin owner cannot be derived;
- scrub ambient `GH_REPO` unless explicitly allowed and validated;
- recursively reject nested authority flags (`commit_allowed`, `push_allowed`, `merge_allowed`, etc.) inside pr-grind loop payloads.

## Stashes during split commits

When splitting a large finalization candidate for review-size limits, stashes are delivery state, not trash:

- name split stashes clearly;
- never raw-drop a stash just because it was applied once;
- only drop after the corresponding content is committed and cleanly verified;
- keep `git status --short --branch`, staged stat, unstaged stat, and stash list in the handoff summary.
