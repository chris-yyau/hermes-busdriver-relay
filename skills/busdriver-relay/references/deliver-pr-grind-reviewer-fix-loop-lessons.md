> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Deliver PR-grind reviewer-fix loop lessons

Use this reference when Hermes is delivering a relay PR and `hermes-busdriver-pr-grind-loop` returns `needs_fix` after reviewer bots comment on the latest PR head.

## Durable workflow lessons

1. **Every amended commit invalidates all PR-review proof.** After fixing reviewer feedback and amending/recommitting, recompute the `base...HEAD` diff hash, rerun PR-mode Codex lead, redispatch the read-only security/bugs backstop over the new full diff, and rewrite the Busdriver backstop verdict + PR marker for that exact hash before pushing/merging.
2. **Do not force-push the amended commit before fresh dual-voice proof is ready.** Keep the amended commit local until Codex lead + backstop PASS for the new hash, then write markers and `git push --force-with-lease`.
3. **PR-grind `needs_fix` comments can target small correctness issues in result envelopes, not only security.** Treat them as real blockers when they affect operator-facing artifacts or handoff semantics.
4. **After every push, restart latest-head PR-grind.** Previous clean/wait/review state is stale once the PR head changes.

## Concrete fixes that should stay covered by regression tests

- `pr_grind_loop_envelope_safe()` should reject contradictory loop output: nested `decision.status` must match the loop envelope `status` before a clean loop result is accepted.
- Timeout handling for subprocess wrappers must normalize `subprocess.TimeoutExpired.stdout/stderr` through the same redaction/tail path as normal output; these fields may be `bytes` even when `subprocess.run(..., text=True)` was requested, and the result envelope must remain JSON-serializable.
- `execute --operation verify` with no verifier commands should fail closed **and** write a Hermes-owned handoff artifact when a run id/artifact dir is present, so later status lookup can explain the blocked result.
- Step summaries need operation context. A `delivery_status_failed` preflight during `--operation pr-grind` should skip/report `pr_grind`, not `verify`.

## Verification pattern

After reviewer-fix changes:

```bash
python3 -m py_compile scripts/hermes-busdriver-deliver scripts/hermes-busdriver-pr-grind-loop
uvx --from pytest pytest tests/contract/test_deliver.py -q
uvx --from pytest pytest tests/contract -q
./scripts/hermes-busdriver-smoke --plugin-root ~/.claude/plugins/marketplaces/busdriver --pretty
```

Then run Busdriver litmus in both commit/staged mode for the incremental fix and PR mode for the full `base...HEAD` diff. Persist the backstop verdict only through `run-review-loop.sh --write-backstop-verdict`, then write the PR marker through `--write-pr-marker`.
