# PR66 CURRENT_STATUS Refresh Delivery Lessons

Use when continuing relay completion after a merged skill/docs slice and the only stale surface is `docs/CURRENT_STATUS.md` verification evidence.

## What happened

- After PR65 merged, `docs/CURRENT_STATUS.md` still carried stale PR63 / plugin `1.76.1` evidence.
- A docs-only branch refreshed the status evidence to PR65 / plugin `1.77.0`, updated focused/full/smoke result text, and preserved the intentionally deferred finalization policy section.
- Verification initially exposed two operator pitfalls:
  - a durable verifier expected slightly different policy wording than the document actually used;
  - a smoke verifier passed a literal `$BUSDRIVER_PLUGIN_ROOT` through `hermes-busdriver-deliver --verifier`, causing the smoke preflight to inspect a literal path instead of the installed plugin root.
- The slice completed through PR-mode Codex lead, read-only Grok backstop, trusted Busdriver marker writers, PR create, latest-head PR-grind, merge, branch cleanup, lock release, and final audit.

## Durable workflow updates

1. **Keep CURRENT_STATUS refreshes evidence-only.** Update plugin version, PR/head SHA, test counts/timings, lock/marker state, skill sync state, and smoke summary. Do not broaden finalization authority or rewrite the deferred policy section except to preserve existing fail-closed wording.
2. **Write policy verifiers against the actual allowed wording.** If the docs say `` `hermes-busdriver-deliver` mutating commit/push/PR/merge executor mode`` rather than `mutating \`hermes-busdriver-deliver\` ...`, the verifier should accept the documented phrase. Avoid making verifier wording stricter than the policy contract.
3. **Do not rely on shell expansion inside `hermes-busdriver-deliver --verifier`.** Verifier commands are parsed/executed in a constrained way; a verifier like `smoke=scripts/hermes-busdriver-smoke --plugin-root "$BUSDRIVER_PLUGIN_ROOT" ...` can pass a literal `$BUSDRIVER_PLUGIN_ROOT`. Resolve the plugin root before constructing the verifier, or invoke through `env VAR=value ...` only when the target command actually expands it.
4. **Do not treat dirty-tree smoke failure as a docs/status regression.** `hermes-busdriver-smoke` includes a gate preflight that expects a clean repo and can fail while the only dirty file is the intended `docs/CURRENT_STATUS.md` refresh. For dirty docs-only drafts, run the docs freshness verifier, `git diff --check`, focused/full contract tests, compileall, and deliver-verify first; then commit and rerun smoke on the clean committed branch before PR/merge evidence.
5. **Treat `hermes-busdriver-litmus-status` JSON as diagnostic evidence, not a shell truthiness shortcut.** When delivery/finalization wrappers receive valid helper JSON and a nonzero helper exit, keep the wrapper fail-closed and surface the parsed JSON only to explain the blocker. Do not convert a nonzero helper return into warning-only success just because the payload contains `ok=true` / `status=stale_or_missing`.
6. **Finalization locks are branch-keyed.** Record the PR base branch before merge. If a squash merge deletes the topic branch before lock release, recreate the topic branch at the saved PR head SHA, release with the original token, switch back to the saved PR base branch, then delete the recreated branch. Verify `hermes-busdriver-lock status --pretty` returns `count: 0`.
7. **End with a final audit after docs/status refresh merges.** Verify the saved PR base branch is clean and synced with its upstream (for example `<base>...origin/<base>`), no open PRs, no topic refs, no relay locks, no fresh litmus/PR markers, installed skill diff clean, CURRENT_STATUS required evidence present and stale evidence absent, focused/full contract tests pass, py_compile passes, and smoke is `ok: true`.

## Verification pattern

```text
Phase-0 shows stale CURRENT_STATUS evidence only
→ docs-only branch / scoped draft or existing committed docs branch
→ verifier for required fresh evidence + stale-token absence + policy wording preservation
→ focused skill-reference tests
→ full contract suite
→ py_compile relay scripts
→ deliver verify on the dirty docs-only draft
→ commit once the scoped docs diff is verified
→ smoke with resolved absolute plugin root on the clean committed branch
→ PR-mode Codex lead
→ independent read-only backstop over base...HEAD diff
→ trusted --write-backstop-verdict + --write-pr-marker
→ gh pr create + post-pr marker cleanup
→ latest-head pr-grind loop until clean
→ readiness/status evidence checked
→ capture the PR base branch from live PR status
→ merge
→ release branch-keyed lock, recreating topic branch if needed and returning to the saved PR base branch
→ final audit against the saved PR base branch and upstream
```

## Pitfalls

- Do not bake one-off timings as the only acceptable current result; use them as evidence in the docs, but expect reruns to have different durations.
- Do not let an operator-held finalization lock appear as an unexplained blocker at the end. Either release it after merge or explicitly confirm it is the active operator lock before proceeding.
- Do not stop after PR-grind reports clean; merge, cleanup, and run the completion audit in the same continuation unless a real blocker appears.
