# PR118 skill-sync delivery lessons

Use when `hermes-busdriver-relay-brief` reports `next_safe_slice=reconcile_skill_source_drift` because an installed `busdriver-relay` skill reference or `SKILL.md` wording is ahead of the repo source.

## Durable lessons

1. **Durability tests must pin the intended SKILL entry, not only path presence.** When adding a new reference file, do not only assert `references/<file>.md in skill_text`; that can pass if the path is copied into the wrong section. Also assert the distinctive entry wording or concept that should co-locate with the path (for example the ADR0005 authority-source entry wording) so the test fails if the canonical reference block drifts.

2. **Whole-skill compare comes before and after repo sync.** Copy installed → repo for the reported drift, then verify installed and repo skill trees match exactly (`missing=[]`, `extra=[]`, `mismatches=[]`) before claiming the drift is reconciled. After merge/cleanup, rerun the same compare through `relay-brief` or a verifier and require `skill_sync.clean=true`.

3. **Dirty-branch smoke can be phase-inappropriate.** Full smoke may include a clean-repo preflight and fail while the intended skill-sync diff is still dirty. Treat that as expected only when scoped postflight, focused skill-reference tests, and whole-skill compare have already passed; rerun full smoke on the clean committed branch before PR finalization.

4. **Use normal follow-up commits for PR-grind reviewer fixes.** If reviewer feedback asks for a tiny durability-test strengthening, fix it in a follow-up commit, rerun focused + full contract tests, push, wait for the new head checks/reviewer state, then restart latest-head PR-grind. Do not merge based on the pre-fix clean state.

5. **Branch-keyed locks may need temporary branch recreation after squash merge.** If squash merge switches the worktree to the base branch and `hermes-busdriver-lock release` misses a topic-branch-keyed lock, recreate/switch to the topic branch at the saved PR head SHA only long enough to release the lock with the original branch identity, then return to the base branch, delete the local branch, fetch/prune, and verify remote branch absence.

6. **Re-read live PR state before mutating around reviewer-bot rate limits.** A CodeRabbit rate-limit comment may later be edited into a completed “no actionable comments” review after checks/reviewers catch up. Do not post `@coderabbitai review` or push a no-op commit without explicit user approval; first rerun live `gh pr view` / PR-grind evidence and inspect whether another reviewer (for example Codex) has the real actionable blocker.

7. **Reusable checklist wording must not hard-code `main`.** Skill-sync delivery references and verification checklists should say “clean synced PR base” / saved live PR base branch rather than `main`, because the same pattern can apply to repositories whose PR base is not `main`. Add a durability assertion that rejects the old hard-coded wording when this pitfall is fixed.

## Minimal verification pattern

```text
Phase-0 clean synced PR base/open PR=0/locks=0 + relay-brief skill drift
→ branch + lock + gate preflight
→ copy installed skill source/reference into repo
→ add/strengthen durability test that pins the intended SKILL entry wording
→ whole installed↔repo skill compare clean
→ focused test_skill_references + full contract suite
→ postflight or equivalent scoped verification
→ commit, rerun full smoke + deliver verify on clean committed branch
→ PR create + wait checks/reviewer + latest-head PR-grind
→ fix reviewer feedback with follow-up commits, then restart latest-head PR-grind
→ squash merge + branch-keyed lock release + branch/remote cleanup
→ final audit: clean synced base, open PRs=0, locks=0, skill_sync.clean=true, post-merge checks green
```
