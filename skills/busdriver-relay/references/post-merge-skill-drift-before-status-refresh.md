# Post-Merge Skill Drift Before CURRENT_STATUS Refresh

Use when a relay skill-sync PR has just merged and the next intended slice is the final `docs/CURRENT_STATUS.md` refresh.

## Durable lesson

A post-merge audit can reveal fresh installed-vs-repo skill drift caused by the delivery work itself (for example, a skill maintenance patch made while closing reviewer feedback). Do not rush into `CURRENT_STATUS` while the skill library is dirty.

Correct sequence:

1. After every skill-sync PR merge, return to the synced base branch and run the whole-skill installed-vs-repo comparison again.
2. If the diff is useful class-level skill content, keep it: sync the installed reference/SKILL pointer back into repo source, add durability assertions, and run a tiny follow-up skill-sync PR.
3. Only after installed skill and repo source compare clean should `docs/CURRENT_STATUS.md` become the last evidence-only refresh slice.
4. Treat reviewer-bot actionable comments as PR-grind blockers even when the bot labels them trivial/low severity; make the minimal fix unless evidence shows the comment is stale, outdated, or non-actionable.
5. For completion audits on clean `main`, `hermes-busdriver-litmus-status` may report `branch_diff_hash_unavailable: empty diff`; this is expected diagnostic evidence when there is no PR diff, not a code regression. Pair it with marker cleanup/staleness checks rather than treating it as a fresh PR-review requirement.
6. `hermes-busdriver-finalization-contract-status` is currently a repo-cwd helper with no `--repo` option; run it from the target repo instead of passing `--repo` during final audit/status evidence collection.

## Pitfalls

- Do not delete useful installed-only lessons just to make the compare clean.
- Do not refresh `CURRENT_STATUS` between two skill-sync PRs; the second skill-sync merge will immediately stale the status evidence.
- Do not use a broad private-path scan over test files that intentionally contain negative assertions for private path tokens; scan the reference/docs payload itself, or make the test assert absence in the reference text.
