# Final-Audit Skill-Maintenance Recursion Lessons

Use when a Busdriver-relay delivery is in the convergence/final-audit phase and skill maintenance itself keeps creating repo-vs-installed skill drift.

## Durable lessons

1. **Treat final-audit skill drift as a blocker, but avoid infinite skill-sync recursion.** If the audit finds useful installed-only skill content, sync it to repo source and add durability assertions. After that, stop adding more installed-only lessons until the merged base has passed the final audit, unless a real correctness/safety issue appears.
2. **Batch skill-maintenance lessons before the final status refresh whenever possible.** Repeatedly patching the installed skill during PR delivery creates new drift and forces additional tiny skill-sync PRs. Prefer one consolidated class-level reference plus tests before `CURRENT_STATUS` becomes the last slice.
3. **Separate two kinds of learning.** Session-specific PR/head/test evidence belongs in `docs/CURRENT_STATUS.md` or PR bodies; reusable process lessons belong in a class-level reference under `references/` and should be synced installed↔repo exactly once per convergence loop.
4. **Do not update skills while merely reporting a pending async backstop unless the lesson is already stable.** Extra installed-skill edits after a fresh backstop invalidate the final-audit clean-skill condition and can also invalidate already-collected evidence if committed later.
5. **Final audit pass criteria include no newly-created skill drift.** The completion audit should verify: clean synced base, open PRs `[]`, relay locks `0`, no topic refs, no fresh markers, installed↔repo skill compare clean, `CURRENT_STATUS` required tokens present/stale tokens absent, focused/full tests pass, compileall passes, smoke `ok=true`, and finalization policy remains fail-closed.

## Safe convergence pattern

```text
skill drift found during final audit
→ classify useful vs accidental
→ if useful: sync installed reference to repo source + add/extend durability assertions
→ verify whole-skill compare + focused/full tests + compileall + smoke
→ Delivery Mode PR + latest-head PR-grind + merge/cleanup
→ do not add more skill lessons unless safety/correctness requires it
→ final docs-only CURRENT_STATUS refresh
→ final completion audit
```

## Pitfalls

- Do not record every PR number or transient branch as a new skill lesson; capture the reusable class-level rule.
- Do not let a meta “save what we learned” request during an active delivery create another repo drift loop unless the task is explicitly about skill maintenance.
- Do not declare completion while installed skill and repo source differ, even if all tests/smoke pass.
