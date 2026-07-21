> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR100 Skill-Source Sync Delivery Lessons

Use when continuing a tiny installed↔repo skill-source drift slice after `hermes-busdriver-relay-brief` reports `next_safe_slice=reconcile_skill_source_drift` and the only drift is `skills/busdriver-relay/SKILL.md`.

## Durable workflow lessons

1. **Keep the sync surgical, then compare the whole skill.**
   - Copy only the installed-skill paragraph/lines that are the reported source drift.
   - Run a whole installed↔repo skill comparison after patching, not only a targeted file diff.
   - `relay-brief --repo <repo>` may switch from `reconcile_skill_source_drift` to `inspect_and_reconcile_dirty_tree` while the intended repo file is dirty; that is expected after the sync draft. The acceptance condition is still `skill_sync.clean=true` plus a scoped dirty diff.

2. **Avoid shell-guard false positives in inline verifier snippets.**
   - Hermes terminal foreground commands can reject a multi-line shell script when the text contains `&`, even if it is inside a Python heredoc as a set-intersection operator.
   - Prefer `.intersection()` in embedded Python verifier snippets, or place the verifier in a temporary script file and invoke it. This preserves the same comparison while avoiding accidental backgrounding detection.

3. **Use phase-appropriate verification for a one-line skill drift.**
   - Dirty draft: `git diff --check`, whole-skill compare, focused `tests/contract/test_skill_references.py`, gate postflight, and `hermes-busdriver-deliver --mode execute --operation verify` with explicit verifiers.
   - Clean committed branch: rerun focused skill-reference tests, full contract tests, `compileall`, smoke, and deliver verify before PR finalization.

4. **PR-mode fast marker can be the right small-slice route when current Busdriver source supports it.**
   - For tiny safe diffs, current Busdriver `run-review-loop.sh --auto-pr-review` may run the Codex PR lead and emit a fresh `PASS-FAST-<diff_hash>-<epoch>` marker after a clean Codex PASS.
   - Before relying on it, verify the live `pre-pr-gate.sh` accepts `PASS-FAST` markers for the current branch diff and max-age. Treat this as a current Busdriver contract, not a generic bypass.
   - Probe pre-PR gate acceptance before `gh pr create`, then consume PR markers with the post-PR hook after PR creation succeeds.

5. **Branch-keyed lock release still matters after squash merge.**
   - If the PR merge or checkout leaves the repo on the base branch and the relay lock was acquired on the topic branch, a direct release from base can miss the lock.
   - Recreate/switch to the topic branch at the saved PR head SHA only long enough to release with the original token, then return to the saved base branch, delete the recreated local topic branch, fetch/prune, and verify remote topic ref absence.

## Minimal verification pattern

```text
Phase-0 clean main/open PR=0/locks=0 + drift summary
→ branch + lock + gate preflight
→ copy installed SKILL.md drift into repo SKILL.md
→ whole-skill compare clean
→ focused test_skill_references.py + git diff --check + postflight + deliver verify
→ full contract tests + compileall + smoke on clean committed branch
→ commit-mode litmus + post-commit marker consume
→ PR-mode Codex review / accepted current Busdriver marker path
→ pre-PR gate probe + PR create + post-PR marker consume
→ latest-head PR-grind clean
→ squash merge + branch-keyed lock release + branch/remote cleanup
→ final audit: clean synced base, open PRs=0, locks=0, skill-sync clean, smoke ok
```
