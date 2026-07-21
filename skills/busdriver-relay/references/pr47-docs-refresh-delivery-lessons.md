> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR47 Docs Refresh Delivery Lessons

Use when continuing relay after a clean merged main and the next safe slice is a docs/status verification refresh.

## What happened

- The repo was clean on `main` and open PRs were empty.
- The smallest safe slice was a docs-only refresh of `docs/CURRENT_STATUS.md` to replace stale verification evidence with the current Busdriver marketplace plugin/status/smoke evidence.
- Codex draft mode successfully made a single-file docs change, but the first agent-draft verifier string was malformed (`current bash ...`) and postflight reported blocked even though the change was scoped.
- Main Hermes reran `hermes-busdriver-gate postflight` directly with a corrected verifier, confirmed only `docs/CURRENT_STATUS.md` changed, then used Delivery Mode to commit, open PR, run latest-head PR-grind, merge, clean up branches/locks, and verify clean `main`.

## Durable workflow

1. For docs/status refresh slices, keep the implementation scope narrow (`docs/CURRENT_STATUS.md` or the exact docs file list).
2. In draft verifier arguments, pass `name=command` where the command starts with the actual executable, e.g.:
   ```bash
   --verifier 'docs=bash -lc "files=\"$(git diff --name-only)\"; test \"$files\" = \"docs/CURRENT_STATUS.md\""'
   ```
   Do **not** insert prose tokens like `current` before `bash`; the gate executes the command literally.
3. If agent-draft returns `blocked` solely because of a malformed verifier, do not discard a scoped diff automatically. Re-run the read-only/equivalent postflight gate manually with the same baseline, corrected verifier, and exact `--scope-include`; proceed only if postflight passes and the diff is still scoped.
4. Full `hermes-busdriver-smoke` includes a clean-repo draft preflight. It is appropriate before a docs draft or after merge on clean `main`; while a docs diff is intentionally dirty, prefer `hermes-busdriver-deliver --mode execute --operation verify` with local verifiers instead of treating smoke preflight failure as a code regression.
5. For explicit Delivery Mode docs PRs, still run latest-head PR-grind, inspect reviewer bots/comments, merge only after clean latest HEAD, then fetch/prune, sync the PR base, delete the local topic branch, release the finalization lock, and verify clean `main`.

## Verification pattern

Useful commands from this slice:

```bash
uvx --from pytest pytest tests/contract -q
python3 -m py_compile scripts/hermes-busdriver-*
scripts/hermes-busdriver-deliver \
  --repo . \
  --plugin-root ~/.claude/plugins/marketplaces/busdriver \
  --mode execute \
  --operation verify \
  --run-id <run-id> \
  --verifier 'contract=uvx --from pytest pytest tests/contract -q' \
  --verifier 'py_compile=python3 -m py_compile scripts/hermes-busdriver-status scripts/hermes-busdriver-relay-role scripts/hermes-busdriver-lock scripts/hermes-busdriver-runtime-check scripts/hermes-busdriver-gate scripts/hermes-busdriver-agent-draft scripts/hermes-busdriver-agent-balance-plan scripts/hermes-busdriver-agent-smoke scripts/hermes-busdriver-delivery-status scripts/hermes-busdriver-finalization-readiness scripts/hermes-busdriver-finalization-contract-status scripts/hermes-busdriver-deliver scripts/hermes-busdriver-litmus-status scripts/hermes-busdriver-pr-grind-check scripts/hermes-busdriver-pr-grind-loop scripts/hermes-busdriver-smoke' \
  --pretty
```
