> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR50 Docs/Status Refresh Lessons

Use when continuing `hermes-busdriver-relay` after a merged docs/skill-reference PR and live docs still report stale verification evidence.

## What happened

- After PR #49 synced the PR48 skill-source-sync lesson, the repo was clean and the installed Hermes skill had been synced, but `docs/CURRENT_STATUS.md` still advertised an older verified head (`affea80...`).
- The next safe slice was a docs/status-only refresh, not new runtime capability: update the verification block to the current clean/synced main head and keep all finalization-policy wording unchanged.
- Codex agent-draft was scoped to `docs/CURRENT_STATUS.md`; tracked changes were in scope and targeted verification passed. The draft postflight still reported unrelated `.codegraph/*` ignored-file churn, so main Hermes treated the draft as needing operator verification rather than claiming the gate fully passed.
- Delivery Mode then opened PR #50, ran read-only PR-grind to latest-head clean, merged, cleaned the topic branch/lock, verified clean main, and logged to claude-mem.

## Durable workflow

1. After any merged skill/reference/docs PR, check `docs/CURRENT_STATUS.md` for stale verification head, test timing, PR count, lock state, and skill-sync evidence.
2. If stale, prefer a tiny docs/status slice scoped to `docs/CURRENT_STATUS.md` only. Do not mix in runtime helper changes or policy expansion.
3. Preserve policy guardrails verbatim: non-mutating/read-only relay surface complete for current scope; mutating finalization executor, marker interop/writes, programmatic dual review, and direct MCP/plugin routing remain policy-blocked.
4. In verification evidence, use symbolic parameters (for example `$BUSDRIVER_PLUGIN_ROOT`) rather than private hardcoded paths when the command is meant as reusable documentation.
5. If `hermes-busdriver-smoke` is run while the repo is intentionally dirty, expect the gate-preflight portion to fail on `repo_clean`; use focused verifiers plus `deliver execute --operation verify` for dirty-tree evidence, then rerun full smoke after commit/merge on a clean tree.
6. For merge readiness, pass the raw `hermes-busdriver-pr-grind-loop/v0` payload (not the outer `hermes-busdriver-deliver` wrapper) to `hermes-busdriver-finalization-readiness --pr-grind-result-file`.
7. After merge, fetch/prune, fast-forward base, remove local/remote topic branch state, verify locks are empty, rerun full contract tests + py_compile + smoke, and sync any reviewed skill source back to the installed skill path only when the PR touched skill files.

## Useful verification pattern

```bash
python3 /tmp/check_pr50_status_refresh.py
git diff --check -- docs/CURRENT_STATUS.md
PYTHONDONTWRITEBYTECODE=1 uvx --from pytest pytest tests/contract/test_smoke.py -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 uvx --from pytest pytest tests/contract -q -p no:cacheprovider
python3 -m py_compile scripts/hermes-busdriver-*
scripts/hermes-busdriver-smoke --plugin-root "$BUSDRIVER_PLUGIN_ROOT" --repo . --pretty
scripts/hermes-busdriver-deliver --mode execute --operation verify --run-id <run-id> ...
scripts/hermes-busdriver-deliver --mode execute --operation pr-grind --pr <n> --run-id <run-id> ...
```

## Pitfalls

- Do not leave docs/status evidence stale after merging a relay slice; stale evidence makes the next continuation choose the same cleanup again.
- Do not interpret a dirty-tree smoke failure as a runtime regression when the only dirty file is the intended docs/status file; verify dirty drafts with scoped checks, then rerun smoke after commit/merge.
- Do not update `docs/CURRENT_STATUS.md` in a way that implies new finalization authority. A verification refresh is status evidence only.
