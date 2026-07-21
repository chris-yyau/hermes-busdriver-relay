> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Post-PR100 Tasklist and PR101 Convergence Lessons

Use when a relay delivery has already been reported complete and the user asks for the follow-up work as a task list, or when a final audit after a skill-source PR reveals newly-created installed↔repo skill drift.

## Lessons

1. **Respect task-list-only requests after a completed PR.**
   - If the user says variants of “把之後的寫成 task list” / “write the rest as a task list” while replying to an already-completed delivery report, do not start executing the list.
   - Produce the requested checklist only. Treat it as planning/output formatting, not Delivery Mode authorization.
   - If the user later says “完成吧” / “do it”, then execute the checklist and verify the result.

2. **Post-merge final audits can create a tiny follow-up sync even after a prior skill-sync PR.**
   - A skill-library update made during PR100 delivery created an installed-only reference plus a `SKILL.md` pointer drift.
   - The next safe slice was a narrow PR101-style sync: copy the installed-only reference file into repo source and align the repo `SKILL.md` pointer, without touching unrelated docs/status.
   - Acceptance is a whole installed↔repo skill compare with `missing=[]`, `extra=[]`, and `diffs=[]`, not just a clean targeted file diff.

3. **Keep verifier environment overrides scoped to the verifier command.**
   - Full contract tests may create temporary git repos and commits. If local git config signs commits with an SSH/GPG key, use scoped `GIT_CONFIG_COUNT` overrides for `user.name`, `user.email`, `commit.gpgsign=false`, and `tag.gpgSign=false` inside the verifier process.
   - Do not mutate global git config to make tests pass.

4. **PR-mode fast path still needs explicit evidence and cleanup.**
   - For tiny skill-source syncs, a current Busdriver `PASS-FAST` PR marker can be acceptable only after verifying current pre-PR gate support and seeing a fresh `hermes-busdriver-litmus-status` `pr_review_fresh` result for the current branch diff.
   - After merge, verify branch deletion, remote branch absence, lock release, open PR count zero, clean synced `main`, skill-sync clean, and relay brief `next` no longer points to skill-source reconciliation.

## Minimal pattern

```text
If user asked for task list only → output checklist and stop.
If user then says complete it → Phase-0 audit → if installed-only drift remains, sync installed reference + SKILL pointer → whole-skill compare → focused + contract verification with scoped git signing overrides → commit litmus → PR-mode fast marker evidence → PR create → latest-head PR-grind clean → squash merge → cleanup → final relay brief clean/idle.
```
