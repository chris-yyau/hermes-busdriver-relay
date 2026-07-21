> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Idle finalization-readiness status audit lessons

Context: read-only audit of a proposed `hermes-busdriver-finalization-readiness` slice that changes clean idle/no-PR/no-dirty-worktree status from `blocked` to `no_finalization_candidate` even when child litmus evidence reports stale/not-fresh.

## Durable lesson

For finalization-readiness, distinguish **no finalization candidate exists** from **a candidate exists but is blocked**:

- Clean idle repo, no `--pr`, and no dirty worktree should not surface stale litmus/pre-PR evidence as top-level readiness blockers. Expected top-level readiness is `ready=false`, `status=no_finalization_candidate`, and all finalization authority flags false.
- Preserve child evidence: `delivery_status.decision.blockers` may still contain `litmus_status_not_fresh`; finalization-readiness can suppress only that blocker at the top level when there is no candidate to finalize.
- Do not broaden suppression to malformed/unavailable/helper-failed/schema-invalid/read_only-unsafe/authority-positive evidence, drift incompatibility, active locks, missing Phase-0 hooks/plugin/repo state, dirty worktrees, or PR paths.
- Dirty draft changes with stale/blocked litmus evidence must remain `blocked`, with `target=commit_or_pr` and all authority flags false.
- PR/merge paths with stale/non-clean evidence must remain blocked until latest-head PR-grind/litmus/pre-PR evidence is clean.

## Acceptance criteria for this slice class

1. Clean idle repo, no PR:
   - `readiness.ready is false`
   - `readiness.status == "no_finalization_candidate"`
   - `handoff_envelope.ready_for_handoff is false`
   - `handoff_envelope.readiness_status == "no_finalization_candidate"`
   - `litmus_status_not_fresh` remains allowed in `delivery_status.decision.blockers` as child evidence but is absent from `readiness.blockers`.
   - All commit/push/PR/merge/finalization/deploy/release/publish/marker-write flags are false recursively.
2. Dirty repo with same litmus state stays `blocked`.
3. `--pr` / merge target with same litmus or non-clean PR-grind state stays `blocked`.
4. Malformed, unavailable, nonzero, timeout, schema-invalid, read_only-unsafe, non-boolean-ok, repo-mismatched, or authority-positive child evidence stays fail-closed as top-level `blocked`.
5. Drift-baseline incompatibility, active finalization lock, and missing Phase-0 hooks/plugin/repo evidence stay top-level blockers.

## Verification pattern

Use focused tests plus the existing contract suites:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider \
  tests/contract/test_delivery_status.py \
  tests/contract/test_finalization_readiness.py
```

Also run targeted regressions when present:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider \
  tests/contract/test_finalization_readiness.py::test_clean_idle_repo_reports_no_finalization_candidate_despite_stale_litmus \
  tests/contract/test_finalization_readiness.py::test_readiness_handoff_blocks_when_litmus_status_is_blocked \
  tests/contract/test_delivery_status.py::test_blocked_litmus_status_blocks_delivery_handoff
```

When auditing live behavior, compare `delivery-status` and `finalization-readiness`: delivery-status may remain blocked due child litmus evidence, while finalization-readiness should convert only the clean idle/no-candidate case to `no_finalization_candidate` without granting handoff readiness or authority.
