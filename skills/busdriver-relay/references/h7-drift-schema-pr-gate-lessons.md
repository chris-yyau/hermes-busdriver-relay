> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# H7 Drift Schema + PR Gate Lessons (2026-06-28)

## Context

During a minimal H7 drift-invalidation hardening slice after PR #16, Codex was launched through `hermes-busdriver-agent-draft` and made a small read-only/status-only change:

- `scripts/hermes-busdriver-status --drift-baseline` now rejects explicit unsupported baseline schemas fail-closed.
- Existing minimal baselines with no schema declaration remain compatible.
- Supported declarations: `status_schema: hermes-busdriver-status/v0` and `schema: hermes-busdriver-drift/v0`.

## Durable workflow lessons

1. **Codex draft postflight can be blocked by ignored-file churn even when the tracked diff is correct.**
   - In this run, `.codegraph/*` changed between preflight and postflight, causing `no_new_or_changed_ignored_files=false`.
   - Treat this as a real draft-gate blocker, not as success. Continue only via operator verification/Delivery Mode if the tracked diff is scoped and fresh checks pass.
   - Do not delete or normalize unrelated ignored daemon/cache state just to satisfy the gate.

2. **Commit litmus and PR litmus are separate.**
   - Commit-mode litmus can pass and allow a local commit.
   - Before `gh pr create`, PR-mode litmus still requires the deeper PR review path.

3. **PR-mode Codex lead PASS is not sufficient for PR creation.**
   - Busdriver `pre-pr-gate.sh` requires both:
     - fresh diff-bound `pr-codex-lead.local.json` from Codex lead; and
     - fresh diff-bound `pr-backstop-verdict.local.json` from the read-only Opus `pr-security-backstop`, followed by trusted `--write-pr-marker`.
   - If Hermes cannot dispatch the backstop through the Busdriver/Claude agent runtime, fail closed: do not push or open the PR, and report a verified-draft blocker.

4. **Never forge PR markers/artifacts from Hermes.**
   - Hermes may read/report marker state.
   - The backstop artifact and `pr-review-passed.local` must be produced by Busdriver’s trusted workflow/writers, not hand-written by Hermes.

## Verification pattern used

After Codex draft returned, operator verification ran:

```bash
PYTHONDONTWRITEBYTECODE=1 uvx --from pytest pytest -p no:cacheprovider tests/contract/test_status_probe.py -q
PYTHONDONTWRITEBYTECODE=1 uvx --from pytest pytest -p no:cacheprovider tests/contract -q
scripts/hermes-busdriver-smoke --plugin-root ~/.claude/plugins/marketplaces/busdriver --pretty
```

Then:

```bash
git add <scoped files>
BUSDRIVER_PLUGIN_ROOT=~/.claude/plugins/marketplaces/busdriver \
CLAUDE_PLUGIN_ROOT=~/.claude/plugins/marketplaces/busdriver \
bash "$BUSDRIVER_PLUGIN_ROOT/skills/litmus/scripts/init-review-loop.sh"
BUSDRIVER_PLUGIN_ROOT=~/.claude/plugins/marketplaces/busdriver \
CLAUDE_PLUGIN_ROOT=~/.claude/plugins/marketplaces/busdriver \
bash "$BUSDRIVER_PLUGIN_ROOT/skills/litmus/scripts/run-review-loop.sh"
```

For PR readiness, also run PR mode:

```bash
LITMUS_MODE=pr bash "$BUSDRIVER_PLUGIN_ROOT/skills/litmus/scripts/init-review-loop.sh"
LITMUS_MODE=pr bash "$BUSDRIVER_PLUGIN_ROOT/skills/litmus/scripts/run-review-loop.sh"
```

If this produces only the Codex lead artifact and `pre-pr-gate.sh` still blocks due to missing backstop, stop before push/PR and report the blocker.
