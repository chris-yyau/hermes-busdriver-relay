# Docs/skill policy consistency review

Use this for an independent, read-only review of a dirty policy-convergence worktree where README/docs/ADRs, a repository skill, historical references, runtime metadata, and contract tests must tell one story.

## Review order

1. Record the exact worktree, HEAD, tree, branch, dirty paths, untracked paths, and diff stat without changing the repo.
2. Write the intended **current** authority matrix in one compact ledger before reading prose: canonical authority, operator/router/verifier, implementation-primary metadata, secondary/fallback metadata, deferred agents, manual sidecar, review-independence rule, and production dispatchability.
3. Verify any prior sealed-main statement separately from the dirty follow-up. Check the named commit, tree, and claimed linear-slice count from Git; ensure the document says unmerged bytes cannot borrow that seal. Do not treat a test that merely repeats the same literals as independent proof.
   - Also compare the candidate's exact parent chain with the claimed seal. If a prerequisite or runtime-pin PR landed after the last sealed commit, the old commit may remain valid historical authority but must not still be called `main/top`, and wording about only “unmerged follow-ups” is incomplete. Require three explicit states: historical sealed commit/tree, merged-but-unsealed prerequisite commit/tree, and current unsealed candidate commit/tree.
   - Fail closed when a candidate test hard-codes the historical seal as current `main/top` or asserts that the current `BLOCKED / UNSEALED` marker is absent. A passing test can fossilize authority drift; derive current/parent truth independently from Git first, then judge the prose and test expectations against it.
4. Review current surfaces first: root README, current-status doc, authority map, ADR status/current-truth sections, adapter READMEs, top-level repository `SKILL.md`, and runtime/status inventory descriptions.
5. Review historical references second. Old agent assignments are acceptable only when the file begins with an unmistakable historical/superseded banner pointing to the current authority document. Put the Markdown H1 first and the banner immediately after it so both document structure and policy classification remain clear. A banner that supersedes only production execution is insufficient when the body still says an old role map is “current”.
6. Inspect long `SKILL.md` inventory lines programmatically or in bounded segments. Normal search snippets can hide stale summaries such as old primary/fallback assignments, a former manual IDE, an obsolete dispatch exception, or an old roadmap item. Tests for these catalog clauses should find a stable semantic marker and validate the matching clause, not index a fixed line number that breaks when headings/notices move.
7. Compare every local `references/*.md` file with references named by `SKILL.md`. Report unindexed files and missing targets. For references that intentionally preserve old policy, require both the banner and an inventory summary that calls them historical.
8. Check tests for semantic closure, not only positive phrase presence. Add/expect assertions that active surfaces exclude stale policy phrases, historical files carry the required banner, the reference inventory is closed, and all current relay roles remain non-dispatchable when no production dispatcher exists.
9. Run focused docs/skill tests with cache and bytecode writes disabled. Keep host-bound runtime failures separate: record the live pin mismatch or setup blocker, but do not turn an environment-specific digest into a durable policy lesson.
10. For a final docs-only blocker repair, review the named immutable `(commit, tree, parent)` and the final delta from the rejected predecessor—not whichever branch happens to be checked out. Corroborate chronology claims independently: prove candidate/merge tree equality from Git, hash the cited full-suite log against its authority record, recompute any recorded diff digest, and query immutable postmerge run IDs plus the live PR state read-only. A test repeating those literals is a regression guard, not authority.
11. Prove the chronology guard has teeth in a disposable exact-tree materialization: run the focused docs/inventory/digest tests green, replace only `CURRENT_STATUS` with the prior defective bytes, and require the chronology selector to fail for the intended missing three-state narrative. Keep scratch Git metadata, HOME, caches, and bytecode outside the reviewed repository; remove scratch afterward.
12. When the repair is limited to prose plus its contract test, compare the authoritative doc inventory, trusted-runtime manifest, top-level skill inventory, and executable/digest surfaces byte-for-byte against the predecessor. Unchanged closure authorities plus passing closure tests show that no unrelated digest refresh was needed; do not infer this from the two-path diff alone.
13. Close with the same opening seal over worktree bytes/modes/timestamps and linked-worktree/common-Git metadata, then require clean porcelain, `diff --check`, opening = closing, and absent scratch before `PASS`.

## Frequent blockers

- The canonical authority map is updated, but the active top-level skill still summarizes an old Pi/Codex/OpenCode/Cursor-or-Zed split.
- A resolver description says every role is non-dispatchable in one paragraph and allows one “safe resolved role” to dispatch in another.
- A roadmap helper marks an adapter proof historical while the skill still calls it an active task.
- Historical reference tests deliberately assert old Pi/Zed text but never assert the superseded banner.
- Reference tests check selected filenames only, allowing unindexed files to escape classification.
- `CURRENT_STATUS` still calls the last sealed ancestor `main/top` after a prerequisite/runtime-pin PR has landed, or mentions only unmerged follow-ups without naming the merged-but-unsealed parent.

## Verdict

Return `PASS` only when current docs, active skill guidance, runtime metadata, historical classification, and tests agree. Otherwise return exact file/line blockers plus the smallest repair class; do not edit during a strict read-only review.
