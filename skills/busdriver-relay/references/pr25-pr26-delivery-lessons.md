> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR #25/#26 delivery lessons — litmus evidence and doc-refresh follow-through

Session lessons from finishing the litmus evidence delivery slice and the immediate post-merge docs/status refresh.

## User workflow correction: subagents mean subagents

When the user says the relay work should be done by subagents, or pushes back with wording like “不是你叫 subagent 做嗎”, do not continue fixing inline as main Hermes. Immediately dispatch the next implementation/review/triage slice to subagents and keep main Hermes as operator/verifier/finalizer only.

Recommended split:

- reviewer subagent: classify latest-head PR feedback as real/stale/duplicate/noise;
- fixer subagent: make minimal edits only in scoped files, no commit/push/merge;
- PR/status subagent: read-only GitHub/PR-grind/CI state and next-step plan.

Main Hermes then re-reads the dirty tree, verifies with tools, commits/pushes/reruns latest-head PR-grind, and merges only after clean.

## Layered wrapper forwarding pitfall

For delivery-status helper inputs, fixing the innermost script is not enough. Verify every wrapper layer that can call it:

```text
deliver
  -> delivery-status
     -> litmus-status

finalization-readiness
  -> delivery-status
     -> litmus-status
```

The Busdriver marker state dir must be forwarded through all applicable layers:

- `deliver --busdriver-state-dir-name X` -> `delivery-status --busdriver-state-dir-name X`
- `finalization-readiness --state-dir X` -> `delivery-status --busdriver-state-dir-name X`
- `delivery-status --busdriver-state-dir-name X` -> `litmus-status --state-dir-name X`

Regression tests should cover direct `delivery-status` forwarding and at least one wrapper path.

## Sanitized summaries: normalize primitives, not just strings

When exposing helper evidence from untrusted scripts/fixtures, avoid raw copying even “primitive-looking” fields. For litmus summary evidence:

- `schema`: preserve only the exact expected schema string; otherwise `None`;
- `read_only`: `result.get("read_only") is True`;
- `ok`: preserve only if the source is a boolean; otherwise `False`;
- decision flags: output booleans only, especially `not_busdriver_native_claude_runtime`.

Add tests where malicious `schema`, `read_only`, `ok`, and nested decision flags contain token-shaped strings/objects and assert the serialized delivery/finalization payload does not contain the sentinel.

## PR-grind comments after a fix push

After a fix push, unresolved review threads may still block PR-grind even when the code is fixed. Do not resolve threads until evidence shows the finding is addressed. Once verified:

1. Use GraphQL review threads (`isResolved`, `isOutdated`, `databaseId`) to distinguish stale/resolved/outdated from active blockers.
2. If an active thread is genuinely addressed by the latest head, resolving that review thread is an allowed PR-grind finalization mutation under explicit Delivery Mode.
3. Re-run latest-head PR-grind after resolving; require `actionable_comments: []`, checks clean, and matching head SHA before merge.

## After merge: choose the next smallest safe slice

When the user asks “然後呢” / “繼續” after a merge, do not stop at the merged PR. Refresh Phase 0 and choose the next smallest safe slice. A good default is a docs/status refresh if project docs now lag the verified state.

For docs-only refreshes:

- update current status counts and smoke evidence;
- avoid overclaiming autonomous finalization authority;
- verify with `git diff --check` and existing contract tests;
- still run PR-grind before merge, even for docs-only PRs.
