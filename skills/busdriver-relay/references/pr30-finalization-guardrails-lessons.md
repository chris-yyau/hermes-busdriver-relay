> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR #30 finalization guardrails + smoke-summary lessons

Session lessons from continuing `hermes-busdriver-relay` after PR #29 and merging PR #30.

## Machine-readable guardrails are a safe non-mutating completion slice

When the remaining relay work is intentionally unsafe/mutating (commit/push/PR/merge executor, mutating final delivery envelope, marker interop, raw agent execution), a good next safe slice is to expose **machine-readable guardrails** rather than implement the mutating path.

Pattern used:

- Add a self-describing guardrail envelope with:
  - `schema`, `version`, `read_only: true`;
  - stable `status` such as `non_mutating_relay_only`;
  - exact `unsupported_mutating_operations` including `commit`, `push`, `pr_create`, `merge`, `deploy`, `release`, `publish`, `busdriver_marker_write`, `gate_bypass`, `raw_codex_exec`, `non_codex_agent_enablement`, and `autonomous_git_github_mutation`;
  - stable `remaining_work[]` entries with `id`, `status: not_implemented`, and `safe_to_execute_by_this_helper: false`.
- Mirror the same guardrail payload into the handoff envelope.
- Make any handoff/readiness convenience field point back to the guardrail source of truth, e.g. `readiness.finalization_guardrail_status == finalization_guardrails.status`.
- Keep every authority flag false at every nesting level; add a recursive test that no known finalization authority key is ever true.

## Docs and smoke summaries must match real machine output

If docs show fields as smoke evidence, the smoke script must actually summarize those fields. Reviewer bots correctly flagged docs that listed `finalization_guardrails.schema/read_only` before `hermes-busdriver-smoke` surfaced them.

Verification pattern:

```bash
scripts/hermes-busdriver-smoke --plugin-root ~/.claude/plugins/marketplaces/busdriver --pretty > /tmp/smoke.json
python3 - <<'PY'
import json
d=json.load(open('/tmp/smoke.json'))
for c in d['checks']:
    s=c.get('summary')
    if isinstance(s, dict) and 'finalization_guardrails' in s:
        print(s['finalization_guardrails'])
PY
```

If the docs are manually curated from a direct helper run instead of smoke, say that explicitly. Otherwise add a focused smoke contract test for the summary shape.

## PR-grind latest-head loop details

After every amend/force-with-lease push:

1. Re-run PR-grind against the latest PR head; previous clean/reviewer state is invalidated.
2. Inspect actionable comments from `hermes-busdriver-pr-grind-check` and current unresolved, non-outdated GraphQL review threads.
3. Fix valid comments minimally.
4. If a remaining active thread is genuinely addressed by latest code and verified with smoke/tests, resolving that thread is an allowed PR-grind finalization mutation under explicit Delivery Mode.
5. Re-run PR-grind after resolving threads; require `status=clean`, `actionable_comment_count=0`, no pending required checks, and matching latest head before merge.

Useful GraphQL shape (do not rely on REST `resolved` fields):

```bash
gh api graphql \
  -f owner=OWNER -f repo=REPO -F number=PR \
  -f query='query($owner:String!, $repo:String!, $number:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$number) {
        reviewThreads(first:100) {
          nodes {
            id isResolved isOutdated path line
            comments(first:20) { nodes { databaseId author { login } body createdAt url } }
          }
        }
      }
    }
  }'
```

## Continue after merge

When the user says to finish the entire relay, do not stop after one clean merge. After post-merge cleanup and verification, refresh Phase 0 and dispatch the next smallest safe non-mutating slice to subagents. Good defaults after guardrail work are read-only readiness/evidence envelopes for the next intentionally blocked area (for example dual-review readiness), not implementing the blocked mutating operation itself.
