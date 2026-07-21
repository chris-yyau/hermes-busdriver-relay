> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR-grind Delivery Discipline

User correction captured for Hermes Busdriver Relay work:

- When the user asks Hermes to do Busdriver-relay coding work, the expected outcome is end-to-end delivery, not a dirty tree or handoff.
- Delivery still must follow Busdriver discipline. Hermes must not treat "can merge" as "merge immediately".
- Correct pr-grind loop:

```text
PR opened
→ wait for CI / reviewer bots / required checks
→ collect actionable feedback on current PR HEAD
→ fix feedback
→ commit + push
→ new HEAD triggers the next CI / reviewer-bot round
→ wait again
→ collect feedback again
→ repeat until the latest PR HEAD is clean
→ merge only when clean
```

Clean means, for the latest PR HEAD:

- required checks are green;
- `relevant-check-status` has no pending/failing blocker;
- reviewer bots are complete or bounded-wait rules allow progress;
- CodeRabbit / Devin / Cubic / Codex / similar bots have no new actionable findings;
- comments/reviews on changed lines are fixed or explicitly justified within Busdriver discipline rails;
- unclear policy/design/scope state bails instead of merging.

## Reviewer Signal Interpretation

Source from `origin/main`: blockers come from live unresolved, non-outdated review threads and current-head actionable review bodies/comments. Reviewer status completion is not clean by itself; CodeRabbit rate-limit means incomplete coverage; Cubic no-issues is advisory; Devin `SUCCESS` completion is not clean. Stale, outdated, resolved, addressed-by-design, or factually incorrect findings should not block once that classification is established.

A fix push invalidates the previous clean state. Start a new wait/collect/fix round for the new HEAD.
