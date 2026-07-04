# PR78 Skill-Sync / Pre-PR Delivery Lessons

Use when continuing relay completion through a small skill-sync/reference slice after subagents have produced a dirty-tree draft and main Hermes must verify/finalize.

## What happened

- The initial Phase-0 sweep found clean synced `main`, no open PRs, no relay locks, and one installed-vs-repo skill reference drift.
- A mutating subagent synced the targeted convergence lesson and added durability assertions, while a read-only audit confirmed `docs/CURRENT_STATUS.md` should remain a separate last slice.
- Main Hermes re-ran a whole-skill compare and found additional installed-only drift in `read-only-skill-sync-audit-lessons.md` that appeared during the audit itself. The correct action was to include that class-level, sanitized drift in the same skill-sync PR, not proceed with a known mismatch.
- The live Busdriver source checkout and the installed marketplace plugin can report different versions; smoke/status evidence should use the installed marketplace plugin path actually passed to the verifier.
- Delivery advanced through commit-mode litmus, smoke on the clean committed branch, and PR-mode Codex lead. Before PR creation, the branch still needed the independent backstop verdict and trusted PR marker writer.

## Durable workflow updates

1. **Do a final whole-skill compare after subagents return and after any main-Hermes patch.** Do not rely on the subagent's target-file compare. If another installed-only class-level lesson appeared during the read-only audit, either sync it with durability assertions in the same PR or explicitly stop and report scope drift.
2. **Keep `CURRENT_STATUS` last.** If a skill-sync PR is still being finalized, do not refresh `docs/CURRENT_STATUS.md` in the same slice unless the user explicitly changes scope; the skill-sync merge will make status evidence stale again.
3. **Use the installed plugin version for smoke/status evidence.** If the live Busdriver source checkout and the installed marketplace plugin report different versions, report both if useful, but status docs should cite the installed marketplace plugin used by `hermes-busdriver-smoke --plugin-root`.
4. **For small skill-reference slices, verify before commit with:** whole-skill compare, private-path scan over changed references/tests, focused `test_skill_references.py`, full contract tests, compileall, and deliver verify. Run full smoke only after the branch is clean/committed when dirty-tree preflight would be noisy.
5. **Pre-PR dual-voice sequence is still mandatory after commit.** PR-mode Codex lead writes only `pr-codex-lead.local.json`; it is not enough for `gh pr create`. Wait for/read the independent backstop, persist it with `run-review-loop.sh --write-backstop-verdict`, then run `--write-pr-marker` before pushing/opening the PR.
6. **Do not claim delivery complete at PR-mode Codex lead.** The exact resume point should name the PR diff hash, lead artifact freshness, missing backstop/marker files, and the next gate command class.
7. **After PR reviewer fixes, restart latest-head evidence.** A follow-up commit invalidates the old branch diff hash; rerun focused/full verification, smoke, commit-mode litmus, PR-mode Codex lead, independent backstop, trusted marker writing, push, and latest-head PR-grind before merge.

## Pitfalls

- Subagent summaries are evidence, not proof. Re-read diffs and rerun the final whole-skill compare yourself.
- A clean focused test does not prove installed-vs-repo skill alignment; the byte-for-byte compare is a separate acceptance condition.
- `hermes-busdriver-litmus-status` can report `branch_diff_hash_unavailable` before commit because the branch equals `origin/main`; that is expected for an uncommitted draft and should not be misreported as a code/test failure.
- Do not overwrite richer installed lessons with stale repo text just to make the compare clean.
