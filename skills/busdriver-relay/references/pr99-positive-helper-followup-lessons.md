# PR99 Positive Requested-Repo Helper Follow-up Lessons

Context: after PR98 merged, a late independent reviewer suggested adding a non-blocking positive regression test for `hermes-busdriver-relay-brief` contract-status evidence. The follow-up also surfaced installed-skill drift caused by skill-library updates made during the PR98 finalization.

## Durable lessons

1. **Late non-blocking reviewer suggestions can become tiny follow-up PRs.**
   - If the main PR already merged cleanly, do not reopen or churn the completed delivery unless there is a correctness blocker.
   - For a cheap still-applicable test hardening suggestion, create a narrow follow-up branch/PR with only the regression test and any required skill-source sync.
   - Keep the PR body explicit that the change is test/skill-source sync only and grants no new relay authority.

2. **Positive helper-binding tests should complement missing-helper fail-closed tests.**
   - A missing requested-repo helper test proves the helper does not silently fall back to the relay checkout.
   - Add a fake requested-repo helper positive case when reviewer feedback asks for stronger evidence: create `scripts/hermes-busdriver-finalization-contract-status` inside a temp repo, have it emit `current_policy = Path.cwd()`, run `relay-brief --repo <temp-repo>`, and assert the summarized contract evidence reflects that repo root/cwd.
   - Keep the fake helper output minimal but canonical: use `schema=hermes-busdriver-finalization-contract-status/v0`, `read_only=true`, `ok=true`, and policy-blocked/zero-capability summary fields. Never make an unknown helper schema part of a positive contract.

3. **Skill-library updates made during delivery can create immediate repo↔installed drift.**
   - After using `skill_manage` to improve an installed skill during PR finalization, run a repo↔installed skill compare before starting the next follow-up slice.
   - If the relay repo is the source copy for that skill, include the installed-skill drift sync in the next tiny PR before adding new tests. Do not leave `relay-brief` reporting `reconcile_skill_source_drift` on clean main.

4. **Use phase-appropriate waiting and PR-grind tooling.**
   - Do not wrap reviewer/check waiting in a custom foreground shell `while sleep` loop; it can be interpreted as an unapproved long-running command and block the workflow.
   - Prefer the relay-owned bounded `hermes-busdriver-pr-grind-loop` as the polling surface. If additional waiting is needed, use short status probes between turns or a tracked background process with completion notification rather than an ad hoc foreground sleeper.

5. **Delivery checklist for this class of follow-up.**
   - Phase 0 clean-main/open-PR/lock/skill-drift sweep.
   - Sync installed↔repo skill drift first if present.
   - Add the positive fake-helper regression test.
   - Run targeted test, `test_relay_brief.py`, focused skill+brief tests, full contract tests, `compileall`, `git diff --check`, and `deliver --operation verify` while dirty.
   - Commit/push/open PR, then run latest-head PR-grind after required checks/reviewer bots settle.
   - Merge only after latest-head PR-grind is clean, then post-merge audit clean main/open PR=0/locks=0/skill sync clean/full smoke pass.
