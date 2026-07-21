> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# CURRENT_STATUS Read-Only Review Lessons

Use when the user asks for a read-only review of `docs/CURRENT_STATUS.md` refresh requirements for the next relay slice, especially when another worker already has a docs/status branch or dirty file.

## Workflow

1. Treat the task as review/planning only: do not edit files, write markers, commit, push, create PRs, or mutate Busdriver/Hermes state.
2. Inspect the current repo branch, HEAD, `origin/main`, dirty tree, open PRs, relay locks, installed skill sync, and the existing `docs/CURRENT_STATUS.md` diff before recommending changes.
3. If `docs/CURRENT_STATUS.md` is already dirty, report it as existing WIP and avoid overwriting it. Review the diff and propose exact content/wording changes rather than applying them.
4. Separate two evidence classes:
   - evidence already present in the WIP docs refresh and plausibly copied from the completed delivery loop; and
   - evidence personally re-run during the read-only review.
   Do not imply a full-suite/smoke result was freshly re-run unless it actually was.
5. Prefer a narrow refresh: update stale PR number/head SHA/test counts/skill-sync/marker/lock evidence only. Do not mix in runtime helper changes or finalization policy expansion.
6. Run only read-only/focused checks that support the review, such as `git diff --check -- docs/CURRENT_STATUS.md`, focused skill-reference tests, lock/status probes, `litmus-status`, `finalization-contract-status`, and repo-vs-installed skill `diff -qr`. If a smoke or full suite is recommended but not run, label it as recommended follow-up.

## Evidence that should be refreshed

- Latest clean/synced base head and PR number after the last merged relay slice.
- Open PR status and relay lock count.
- Installed Busdriver marketplace plugin version used for smoke/status.
- Repo skill source vs installed Hermes skill sync status when recent slices touched `skills/busdriver-relay`.
- Litmus/PR marker sanity after merge: no fresh markers on clean main; empty main diff may report `stale_or_missing` as expected.
- Focused verifier results for the changed docs/skill-reference area, plus full contract suite and smoke evidence only when actually run.
- Finalization/contract status evidence showing read-only payloads and all authority flags false.

## Policy wording that must remain unchanged

Keep the intentionally deferred/fail-closed policy intact. A docs/status refresh must not imply any new authority for:

- mutating `hermes-busdriver-deliver` commit/push/PR/merge executor mode;
- draft-agent launcher finalization or `hermes-busdriver-codex-goal` commit authority;
- commit/PR/merge automation inside draft launchers or without litmus/pre-PR plus latest-head PR-grind-equivalent checks and ADR 0005 authority contract;
- programmatic litmus/pre-PR dual-review execution before Busdriver-approved role mappings, invocation seams, data-egress controls, schemas, and aggregation rules exist;
- Busdriver marker interop or marker writes before Busdriver defines a safe integration surface and marker ownership/provenance contract;
- deploy/release/publish automation;
- direct MCP/plugin routing;
- claims that Hermes bare shell execution is Busdriver-gate-safe.

ADR 0006 should be described only as non-mutating design evidence / future contract framing. It must not retire `policy_blocked` rows or unlock programmatic dual-review or marker interop.

## Reporting pattern

When replying to the user, distinguish:

- **Observed current state** (branch, dirty file, HEAD, open PRs, locks);
- **Recommended doc updates** (exact sections/phrases to change);
- **Policy wording to preserve**;
- **Checks actually run** with exact results;
- **Checks recommended but not run**.

This keeps the next mutating relay slice small and prevents accidental authority drift while giving the worker enough precise evidence to update the docs safely.
