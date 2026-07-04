# Final-Audit Skill-Maintenance Recursion Lessons

Use when a Busdriver-relay delivery is in the convergence/final-audit phase and skill maintenance itself keeps creating repo-vs-installed skill drift.

## Durable lessons

1. **Treat final-audit skill drift as a blocker, but avoid infinite skill-sync recursion.** If the audit finds useful installed-only skill content, sync it to repo source and add durability assertions. After that, stop adding more installed-only lessons until the merged base has passed the final audit, unless a real correctness/safety issue appears.
2. **Batch skill-maintenance lessons before the final status refresh whenever possible.** Repeatedly patching the installed skill during PR delivery creates new drift and forces additional tiny skill-sync PRs. Prefer one consolidated class-level reference plus tests before `CURRENT_STATUS` becomes the last slice.
3. **Separate two kinds of learning.** Session-specific PR/head/test evidence belongs in `docs/CURRENT_STATUS.md` or PR bodies; reusable process lessons belong in a class-level reference under `references/` and should be synced installed↔repo exactly once per convergence loop.
4. **Do not update skills while merely reporting a pending async backstop unless the lesson is already stable.** Extra installed-skill edits after a fresh backstop invalidate the final-audit clean-skill condition and can also invalidate already-collected evidence if committed later.
5. **Final audit pass criteria include no newly-created skill drift.** The completion audit should verify: clean synced base, open PRs `[]`, relay locks `0`, no topic refs, no fresh markers, installed↔repo skill compare clean, `CURRENT_STATUS` required tokens present/stale tokens absent, focused/full tests pass, compileall passes, smoke `ok=true`, and finalization policy remains fail-closed.
6. **Handle explicit skill-library review requests as a single consolidated maintenance step.** If the user asks to “review the conversation above and update the skill library” while relay delivery is still converging, make at most one class-level installed-skill update unless a real safety/correctness issue requires more. Prefer patching this umbrella/reference over creating another narrow PR/session reference. Do not create a new one-session skill. Then resume delivery with a planned repo↔installed sync if the project requires clean skill compare.
7. **Treat meta skill-review prompts as part of the current convergence loop.** The skill update itself is not completion: after updating the installed skill, the relay repo must still regain clean installed↔repo skill compare before final `CURRENT_STATUS` / completion audit can pass. Mention the new drift explicitly in the next delivery update instead of burying it.
8. **During an explicit skill-library review turn, only mutate the skill library.** If the user asks to review the conversation and update skills mid-delivery, treat it as an interrupt: do not continue GitHub/repo/PR actions, dispatch agents, or touch PR markers in that same turn when they scope tools to memory/skill management. Make one consolidated installed-skill update under the relevant class-level umbrella, then stop with a concise report of what changed and any resulting repo↔installed drift as pending Delivery Mode work for the next turn.
9. **Re-check installed↔repo skill state before consuming a fresh backstop.** In long convergence loops, a skill-library interrupt or installed-skill refinement can land after a backstop is dispatched. Before writing trusted backstop/PR markers or opening the PR, compare the installed skill against repo source again. If any useful installed refinement appeared, absorb it first, rerun verification, recompute the diff hash, and dispatch a new backstop; never use a PASS bound to the pre-refinement diff.
10. **Honor tool-scope limits during explicit memory/skill reviews.** If the user says the turn can only use memory and skill-management tools, treat that as a hard interrupt boundary: do not call repository, GitHub, terminal, search/read, delegation, marker, or PR tools in that turn. Apply at most the durable memory update and a class-level skill patch, then stop with a concise report and leave any repo↔installed sync or Delivery Mode continuation as pending work for the next turn.
11. **Do not consume pending Delivery Mode events during a skill-only interrupt.** If an async backstop/delegation result, PR-grind state, marker-ready state, or final-audit continuation is pending when the user asks for a skill-library review scoped to memory/skill tools, leave it pending. Record the durable skill lesson only, then report that Delivery Mode work must resume in a later turn; do not acknowledge, validate, dispatch around, write verdicts, or advance PR state in the same skill-only turn.

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
