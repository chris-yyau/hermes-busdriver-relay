# PR56 Skill-Sync Delivery Lessons

Session context: after PR55 merged, Phase 0 showed the repo was clean on `main`, no open PRs/relay locks, but the installed Hermes `busdriver-relay` skill still had drift: `references/pr53-pr55-skill-sync-lessons.md` plus a `SKILL.md` pointer that the repo source lacked. The next safe slice became PR56.

## What changed

- Synced the installed skill's PR53–PR55 lesson reference back into the repo source.
- Updated repo `skills/busdriver-relay/SKILL.md` to point at the new reference.
- Added a narrow durability test in `tests/contract/test_skill_references.py` asserting the reference exists, `SKILL.md` points to it, and the reference preserves key policy phrases.
- Squash-merged PR56 after latest-head PR-grind was clean.

## Durable workflow lessons

1. **Skill-source sync slices still need the full Delivery Mode loop.**
   - Treat repo-vs-installed skill drift as a valid tiny docs/reference slice.
   - Keep the diff scoped to the skill source plus narrow reference tests.
   - Verify `diff -qr <repo skill dir> <installed skill dir>` (or an equivalent byte-for-byte compare) before PR delivery and again after merge when possible.

2. **Local git commit signing can break throwaway test repos.**
   - Full contract/smoke tests create temporary git repos and commits.
   - If tests fail because global commit signing asks for an encrypted SSH key/passphrase, rerun verifiers with a scoped environment override instead of changing repo code:
     ```bash
     env \
       GIT_CONFIG_COUNT=1 \
       GIT_CONFIG_KEY_0=commit.gpgsign \
       GIT_CONFIG_VALUE_0=false \
       PYTHONDONTWRITEBYTECODE=1 \
       uvx --from pytest pytest tests/contract -q -p no:cacheprovider
     ```
   - Record this as verifier environment hygiene, not as a product failure.

3. **`hermes-busdriver-deliver --verifier` still needs argv-safe env prefixes.**
   - Use `env KEY=value ... command`, not shell assignment prefixes, because deliver splits verifier commands as argv.
   - This matters for both pytest and smoke verifiers when disabling commit signing or setting `PYTHONDONTWRITEBYTECODE`.

4. **PR-mode backstop verdicts must include the reviewed diff hash.**
   - A raw independent reviewer output of `{"status":"PASS","issues":[]}` is not enough for Busdriver's trusted writer.
   - Before piping to `run-review-loop.sh --write-backstop-verdict`, augment the verdict with:
     - `model` identifying the independent reviewer route; and
     - `reviewed_diff_hash` equal to the current `origin/main...HEAD` hash reported by `hermes-busdriver-litmus-status` / Busdriver PR-mode evidence.
   - The writer re-derives the current diff hash and rejects missing/stale/mismatched payloads fail-closed.

5. **Manual post-hook cleanup is required when Hermes finalizes outside Claude runtime.**
   - After a successful Hermes-run `git commit`, simulate or run the matching `post-commit-consume-marker.sh` with success evidence so stale commit litmus markers are consumed.
   - After successful `gh pr create`, run `post-pr-consume-marker.sh` with success evidence so `.claude/pr-review-passed.local`, `pr-codex-lead.local.json`, and `pr-backstop-verdict.local.json` are removed.
   - If a failed PR-litmus setup leaves `.claude/litmus-state.md` with `terminal_status: setup_error`, remove that stale state only after the successful PR review/marker/PR creation path has completed and the PR is merged/clean.

6. **PR-grind wrapper vs raw loop evidence.**
   - `hermes-busdriver-deliver --operation pr-grind` may report an initial nested delivery-status `blocked` snapshot while the wrapped raw `pr_grind_loop` is clean.
   - For finalization-readiness, pass a raw `hermes-busdriver-pr-grind-loop/v0` payload file, not the outer deliver wrapper.
   - Verify the PR head SHA is unchanged immediately before merge.

## Verification pattern

```text
Phase 0 repo/open-PR/lock/status + repo-vs-installed skill diff
→ scoped agent-draft for SKILL/reference/test files
→ focused skill reference test
→ static added-line authority/path/token scan
→ full contract suite with scoped commit-signing override if needed
→ smoke with same verifier env hygiene
→ deliver verify using argv-safe `env ...` verifiers
→ commit-mode litmus PASS
→ PR-mode Codex lead PASS
→ independent read-only backstop over origin/main...HEAD
→ augment backstop verdict with model + reviewed_diff_hash
→ trusted Busdriver writers: --write-backstop-verdict then --write-pr-marker
→ push / PR create
→ latest-head PR-grind loop clean
→ finalization-readiness with raw pr-grind-loop payload
→ verify PR head SHA, merge
→ manual post-hook cleanup, fetch/prune, branch cleanup, marker-status sanity
```

## Pitfalls

- Do not hardcode private local paths in reusable repo references; local operator diagnostics can mention observed paths, but procedure examples should use variables.
- Do not treat a clean Codex PR lead as sufficient for PR creation; the backstop artifact and dual-voice marker are still required.
- Do not forge Busdriver markers by direct file writes; use the trusted writers and let them compute/validate diff hashes.
- Do not leave stale PR artifacts or failed litmus state behind after Hermes-created PRs/merges outside Claude hooks.
