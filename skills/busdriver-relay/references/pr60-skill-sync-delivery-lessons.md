> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR60 Skill-Sync Delivery Lessons

Use when a relay continuation finds that the installed Hermes `busdriver-relay` skill has a reference or `SKILL.md` pointer that the repo source lacks.

## What happened

- Phase 0 showed clean `main`, no open PRs/locks, and finalization surfaces still `policy_blocked`, but repo skill source drifted from the installed Hermes skill.
- The drift was one installed-only reference, `references/relay-completion-sweep-lessons.md`, plus a `SKILL.md` pointer.
- A scoped Codex draft synced the reference, updated repo `SKILL.md`, and added a durability test.
- Initial postflight was blocked only by a pytest-created ignored `__pycache__` artifact. Removing that exact generated artifact and rerunning `hermes-busdriver-gate postflight` with the saved baseline passed.
- After committing, `diff -qr` still showed `SKILL.md` wording drift because the draft had paraphrased the installed pointer. The fix was to sync the installed `SKILL.md` wording exactly, then amend.
- `hermes-busdriver-deliver --operation verify` had one transient full-suite failure in an unrelated timeout-sensitive test; the specific test passed on focused rerun and the full deliver verify passed on rerun. Treat the rerun pattern as verification hygiene, not a product change.
- PR-mode review required the full dual-voice path: Codex lead PASS, independent read-only backstop PASS, augmenting the backstop verdict with the current `reviewed_diff_hash`, trusted `--write-backstop-verdict`, trusted `--write-pr-marker`, and post-PR marker cleanup after `gh pr create`.
- PR-grind reviewer bots flagged a real durability-test weakness: checking only `Path.name` in `SKILL.md` lets a bare filename mention pass while the reference path is stale or mis-pointed. The fix was to assert the full relative path (`references/<file>.md`) in the test.
- During the PR60 delivery loop, updating the installed skill itself created another installed-only reference (`pr60-skill-sync-delivery-lessons.md`). Because it was discovered before merge, it was folded into the same skill-sync PR with a `SKILL.md` pointer and narrow durability coverage, followed by a fresh PR-mode lead/backstop and latest-head PR-grind.
- `gh pr merge --squash --delete-branch` fast-forwarded local `main` and deleted the topic branch before the finalization lock was released. Because relay lock keys include branch identity, the release initially returned `not-found`; recreating the topic branch at the saved PR head SHA allowed release with the original token, then the branch was deleted again.

## Durable workflow updates

1. **For installed-skill sync, byte-compare both file sets before finalizing.** A reference file can be byte-identical while `SKILL.md` still has paraphrased pointer drift. Require `diff -qr skills/busdriver-relay $INSTALLED_SKILL_DIR` to be clean before commit/merge and again after reviewer fixes.
2. **Agent-draft invocations need explicit repo/plugin root.** Current `hermes-busdriver-agent-draft` requires `--repo "$REPO"` and `--plugin-root "$BUSDRIVER_PLUGIN_ROOT"`; do not rely on cwd defaults.
3. **Recover generated ignored-cache postflight blockers surgically.** If postflight fails only because a verifier created a scoped pytest pycache such as `tests/contract/__pycache__/...pyc`, remove only that generated artifact and rerun `hermes-busdriver-gate postflight` with the saved `baseline.json`, exact scopes, and verifier. Do not delete unrelated ignored state.
4. **Deliver verifier flakes require evidence-bound rerun.** When a full-suite verifier fails in a timeout-sensitive unrelated test, run the failing test focused. If it passes and a subsequent full `deliver verify` passes on the unchanged commit, record the transient and continue; do not patch product code for an unreproduced flake.
5. **Durability tests should assert relative reference paths, not only basenames.** For new skill references, assert `references/<reference>.md` appears in `SKILL.md` so a stale/mis-pointed link cannot pass by mentioning the bare filename elsewhere.
6. **If installed-skill drift appears during the PR, fold it into the same skill-sync slice before merge.** Sync the new installed reference, add a `SKILL.md` pointer and narrow assertions, rerun byte-diff/focused/full/smoke/deliver verification, then rerun PR-mode lead/backstop and latest-head PR-grind for the amended head.
7. **After PR creation outside Claude runtime, run post-PR marker cleanup manually.** Feed hook-shaped JSON for the successful `gh pr create` command to `post-pr-consume-marker.sh` so `pr-codex-lead.local.json`, `pr-backstop-verdict.local.json`, and `pr-review-passed.local` are consumed. Then verify litmus status no longer reports fresh PR markers.
8. **If tool-call limits interrupt after PR creation, resume from PR-grind.** Do not imply merge happened. Re-check PR head/checks/reviewer state, run latest-head PR-grind, fix feedback if any, then readiness/merge/cleanup/final audit.
9. **Release finalization locks with the same branch identity used at acquire time.** If merge/delete-branch moved the worktree to `main`, recreate the deleted topic branch at the saved PR head SHA just long enough to release the lock, then switch back to clean `main` and delete the local branch.

## Verification pattern

```text
Phase 0 repo/open-PR/lock/status + installed-vs-repo skill byte diff
→ scoped agent-draft with explicit --repo and --plugin-root
→ remove only verifier-generated ignored cache if postflight identifies it, then rerun postflight with saved baseline
→ custom skill-sync verifier + focused skill reference test
→ full contract + py_compile + smoke
→ diff -qr repo skill vs installed skill (must be clean, including SKILL.md wording)
→ deliver verify; if an unrelated timeout-sensitive test flakes, focused rerun + unchanged full rerun must both pass
→ commit/amend only after byte diff clean
→ PR-mode Codex lead PASS
→ independent read-only backstop PASS, augmented with current reviewed_diff_hash
→ trusted --write-backstop-verdict + --write-pr-marker
→ push / PR create
→ post-pr-consume-marker cleanup
→ latest-head PR-grind loop; wait for pending checks/reviewers rather than merging early
→ finalization-readiness with raw PR-grind result
→ verify PR head unchanged, merge, post-merge cleanup and final audit
```

## Pitfalls

- Do not accept a paraphrased `SKILL.md` pointer if the task is source sync; byte-for-byte alignment is the invariant.
- Do not let generated pycache from verifier runs become a reason to widen scope or edit tests.
- Do not treat Codex lead PASS as enough for PR creation; backstop verdict and dual-voice PR marker are still required.
- Do not stop after opening the PR; PR-grind, merge, cleanup, and post-merge verification remain unfinished until proven by live evidence.
