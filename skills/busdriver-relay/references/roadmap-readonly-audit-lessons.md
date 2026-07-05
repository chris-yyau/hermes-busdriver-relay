# Roadmap Read-only Audit Lessons

Context: a read-only audit of relay roadmap tasks (ADR0005 finalization contract, mutating PR-grind fix-loop design, marker interop contract, Pi adapter proof, and Status/UX/Telegram brief) while a separate WIP branch already contained a compact `hermes-busdriver-relay-brief` helper.

## Durable lessons

1. **Start by classifying roadmap tasks into completed contract, policy-blocked finalization, and smallest safe status slice.**
   - ADR0005 / finalization-contract-status can be complete as a non-mutating contract while still leaving all mutating finalization surfaces blocked.
   - Treat `deliver-mutating-executor`, `mutating-final-result-envelope`, `programmatic-litmus-pre-pr-dual-review`, `mutating-pr-grind-fix-push-loop`, and `busdriver-marker-interop` as policy-blocked unless a Busdriver-approved integration surface exists.
   - Do not convert a roadmap audit into finalization permission; report exact blocked IDs and missing authority sources.

2. **Use live helper output to ground the audit, but keep it read-only.**
   - `scripts/hermes-busdriver-finalization-contract-status` should show `remaining_work_count=5`, `policy_blocked_count=5`, and `capability_allowed_count=0` for the current policy surface.
   - `scripts/hermes-busdriver-agent-balance-plan` should show planning metadata only: no subprocess dispatch, no Codex/GitHub calls, no marker writes, no repo mutations.
   - `scripts/hermes-busdriver-relay-role --list-roles` is useful to verify whether future router roles such as `relay.impl.secondary`, `relay.review.fast`, `relay.review.long_context`, or `relay.ide.manual` are actually resolver-ready. If absent, keep those roles future-only/candidate metadata.

3. **If a Status/UX helper exists, audit it for count/schema drift and dirty-tree precedence.**
   - A compact brief helper should read `remaining_work`, not a stale/nonexistent `capability_matrix`, from `finalization-contract-status`; otherwise it may falsely report `remaining_work_count=0` and `policy_blocked_count=0`.
   - Preserve `git status --short` leading whitespace; avoid `.strip()` when the two-column porcelain status is semantically important.
   - If the target repo is dirty, a brief helper should normally report `needs_local_reconciliation` before `needs_skill_source_sync`. Tests that need skill-drift behavior should run against a clean temp repo or explicitly account for dirty-tree precedence.

4. **OpenCode remains a candidate/status slice, not a mutating adapter, until separately proven.**
   - Safe roadmap work may add metadata/status for `implementation.secondary = opencode`, but must keep `dispatch_allowed=false`, `mutation_allowed=false`, `non_codex_agent_enablement_allowed=false`, and finalization flags false.
   - Do not add `opencode` to `agent-draft --agent` choices or document it as executable until a separate gate/smoke/user-intent contract exists.

## Minimal safe follow-up slice template

When the repo already has WIP for a roadmap/status brief:

1. Inspect the dirty tree and untracked files; do not overwrite concurrent work.
2. Fix only the read-only helper and its contract tests.
3. Verify:
   - focused brief tests;
   - `finalization-contract-status` counts 5/5/0;
   - recursive authority flags remain false;
   - any existing smoke/status docs still say finalization is policy-blocked.
4. Update README/CURRENT_STATUS/settling docs only after the helper tests pass.
5. Do not commit/push/PR/merge unless explicit Delivery Mode is requested and litmus/pre-PR plus latest-head PR-grind evidence is current.
