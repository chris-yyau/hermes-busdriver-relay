> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR53–PR55 Skill-Sync Continuation Lessons

Session context: after PR52 merged, a late async reviewer result arrived with a non-blocking test-hardening suggestion. The user then said “繼續”, and Hermes continued through small follow-up slices PR53–PR55.

## What changed

- PR53: added row-level `contract_adrs` assertions for ADR 0006-related remaining-work rows after a late async reviewer suggested the extra guard.
- PR54: synced the late-async reviewer follow-up policy from the installed Hermes skill back into the repo skill source.
- PR55: synced remaining installed `busdriver-relay` skill drift back into the repo: PR49–PR52 reference files plus `SKILL.md` pointers, then verified repo skill and installed skill were identical with `diff -qr`.

## Durable workflow lessons

1. **Late async reviewer results are still actionable after merge.**
   - If a background reviewer finishes after the PR is merged, classify the result against the current merged state.
   - If the suggestion is cheap, test-only, and directly improves the just-merged slice, make it the next tiny follow-up PR instead of ignoring it or claiming it was already handled.
   - Keep the follow-up narrow; do not reopen broad product scope just because a reviewer returned late.

2. **Installed-skill edits must be synced back to the repo source.**
   - If Hermes patches the installed `busdriver-relay` skill during delivery, immediately check whether the repo copy under `skills/busdriver-relay/` has drifted.
   - A clean main plus repo-vs-installed skill drift is a valid next safe docs/reference slice.
   - After merge, verify `diff -qr <repo skill dir> <installed skill dir>` is clean; otherwise continue with another skill-source sync slice.

3. **Use a two-pass sync when new drift appears after the first sync.**
   - PR54 synced only the current continuation reference, but the post-merge diff revealed PR49–PR52 reference files and `SKILL.md` pointers were still installed-only.
   - Treat that as a new Phase-0 finding and continue, rather than leaving installed and repo skills divergent.

4. **Contract tests should make skill references durable.**
   - For skill-source sync PRs, add narrow tests that each new reference file exists and that `SKILL.md` points to it.
   - Tests should assert durable policy phrases, not local installed paths.

## Verification pattern

Use the normal relay Delivery Mode loop:

```text
1. Phase-0 repo/open-PR/lock/status and repo-vs-installed skill diff.
2. Scoped `hermes-busdriver-agent-draft --agent codex` with file scope limited to skill refs/tests.
3. Focused `test_skill_references.py`.
4. Static added-line scan and independent read-only review.
5. Full `tests/contract` and smoke.
6. Deliver verify when useful.
7. PR creation, latest-head PR-grind, merge readiness, squash merge.
8. Post-merge cleanup plus full tests/smoke and `diff -qr` clean against installed skill.
```

## Pitfalls

- Do not treat installed skill drift as harmless after a skill patch; future repo-based skill syncs will otherwise regress the installed lesson.
- Do not copy private local paths into reusable repo references unless they are explicitly parameterized or framed as live operator diagnostics.
- Do not let skill-reference sync wording imply new finalization, marker-write, or non-Codex mutating authority.
