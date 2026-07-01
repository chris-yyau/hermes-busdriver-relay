# Reviewer Report and PR-Grind Lessons

Use this when Hermes is asked to save a PR-reviewer report into the `hermes-busdriver-relay` repo or when tuning the PR-grind readiness checker from live reviewer-bot feedback.

## Durable reviewer-report workflow

When the user asks to save a review report as project documentation/reference:

1. Use an isolated relay worktree/branch so concurrent PR-subagent work is not disturbed.
2. Save the report under `skills/busdriver-relay/references/<descriptive-report-name>.md` in the relay repo.
3. Add a one-line pointer from `skills/busdriver-relay/SKILL.md` so future agents can discover the reference.
4. If the report affects PR-grind semantics, update `references/pr-grind-delivery-discipline.md` or the relevant relay reference note.
5. Add/extend a contract test that proves the reference is durable/discoverable from the skill.
6. Run the relay contract suite and smoke script before claiming completion.
7. In Delivery Mode, open/update the PR and run `hermes-busdriver-pr-grind-check`; do not stop after pushing.

## Reviewer-bot signal policy lessons

These emerged while saving the June 2026 reviewer-quality report and grinding the resulting relay PR:

- Reviewer status/check completion means the bot ran; it is not a clean ack by itself.
- CodeRabbit rate-limit / no-review output means incomplete coverage, not clean.
- cubic `No issues found` review summaries are non-actionable completion summaries. They should not become `needs_fix` comments, but they also are not a substitute for current-head clean state.
- Devin `SUCCESS` means completion, not clean. Block on live unresolved inline `BUG` / `🚩` style findings, not on stale/outdated summaries.
- A review thread with GraphQL `isOutdated: true` is stale. Even if `isResolved: false`, it should not be treated as a live active blocker. Only unresolved **non-outdated** threads remain active blockers.
- If a checker currently treats a stale/outdated bot comment as actionable, write the failing fixture first, then patch the checker and rerun the full contract suite.

## Verification pattern

For relay documentation/reference changes that also affect PR-grind behavior, use at minimum:

```bash
uvx --from pytest pytest tests/contract/test_skill_references.py -q
uvx --from pytest pytest tests/contract/test_pr_grind_check.py::<new_regression_test> -q
uvx --from pytest pytest tests/contract -q
python3 -m py_compile scripts/hermes-busdriver-pr-grind-check scripts/hermes-busdriver-smoke scripts/hermes-busdriver-status scripts/hermes-busdriver-lock scripts/hermes-busdriver-runtime-check scripts/hermes-busdriver-gate scripts/hermes-busdriver-agent-draft scripts/hermes-busdriver-agent-smoke
git diff --check
scripts/hermes-busdriver-smoke --plugin-root ~/.claude/plugins/marketplaces/busdriver --pretty
```
