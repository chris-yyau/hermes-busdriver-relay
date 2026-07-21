> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR35 Finalization Contract Status + Tracked `.claude/CLAUDE.md` Lessons

Session context: after ADR 0005 established the future finalization authority integration contract, the next dogfood slice converted that textual contract into a read-only machine-readable capability matrix and included a user-requested tracked `.claude/CLAUDE.md` wording cleanup.

## Durable workflow lessons

- When the user says to push an existing tracked project-guide change (e.g. `.claude/CLAUDE.md`), include it in the active Delivery Mode PR rather than treating it as unrelated dirty state forever. Verify the diff is small, intentional, and in-scope, then stage it with the current slice.
- If a tracked `.claude/CLAUDE.md` descriptor changes, check matching public-facing docs such as `README.md` for wording consistency. Reviewer bots may flag diverging project descriptors; fix both before or during PR-grind.
- A safe dogfood follow-up to an ADR/integration-contract PR is a read-only status/capability helper that translates the ADR unlock criteria into machine-readable `policy_blocked` rows. This keeps progress concrete while preserving the non-mutating relay surface.
- The helper should report the same remaining-work IDs as `finalization_guardrails.remaining_work`, keep all authority/capability booleans false, and include summary counts (`remaining_work_count`, `policy_blocked_count`, `retired_count`, `capability_allowed_count`).
- Include new helper scripts in smoke `py_compile` coverage and add contract tests that recursively assert no authority/capability flag becomes true.
- After a squash/merge from a linked worktree, `gh pr merge --delete-branch` may fail locally because the base branch is checked out by another worktree even though the remote merge succeeded. Verify PR state with `gh pr view`; if merged, fetch/prune in the base checkout, compare any local dirty tracked file with `origin/main:<path>`, reset only when it exactly matches the merged version, then fast-forward and remove the linked worktree/branch.

## Verification pattern

Use the normal Delivery Mode sequence:

```text
subagent implementation/review
→ parent reads diff
→ focused tests / py_compile / full contract suite
→ smoke
→ deliver verify
→ branch/commit/push/PR
→ PR-grind latest-head loop
→ fix reviewer feedback
→ merge
→ cleanup linked worktree/branch
→ post-merge full contract + smoke + helper sample
```

For a finalization contract status helper, post-merge sample should show:

```text
schema hermes-busdriver-finalization-contract-status/v0
read_only True
remaining_work_count 5
policy_blocked_count 5
retired_count 0
capability_allowed_count 0
finalization_allowed False
marker_write_allowed False
```
