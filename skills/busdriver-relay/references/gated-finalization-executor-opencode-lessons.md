> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Gated finalization executor + OpenCode fallback lessons

Use this when resuming or designing `hermes-busdriver-deliver` finalization work or OpenCode fallback adapter work.

## Durable lessons

- A mutating `hermes-busdriver-deliver` executor is safe only as a narrow, per-operation authority surface, not as standing finalization authority. Each operation must re-check fresh evidence immediately before the side effect and write a redacted side-effect transcript.
- Keep two authority layers distinct:
  - **operation-local authority** inside a mutating run envelope may say a single `commit`, `push`, `pr-create`, or `merge` was allowed and performed;
  - **reusable/legacy status authority** in persisted lookup/status envelopes should remain default-deny so old artifacts cannot become standing permission for later mutations.
- Do not raw-write `.claude/*` trusted markers from Hermes. If pre-PR review marker production is needed, invoke Busdriver-owned trusted writer commands (for example `run-review-loop.sh --write-backstop-verdict` followed by `--write-pr-marker`) and record that Hermes did not forge marker files.
- If an implementation slice unlocks a previously policy-blocked surface, update all status surfaces in the same slice: `finalization-contract-status`, finalization-readiness/guardrail evidence, README/CURRENT_STATUS, skill-source references, and contract tests. Leaving the status matrix as `policy_blocked` after adding executor code creates contradictory guidance.
- For PR-grind fix/push/re-poll: do not invent fixes inside the finalization executor. Route code changes through gated draft adapters (Pi by default; OpenCode only after its adapter proof/hardening is complete), then require fresh litmus/pre-PR evidence before commit/push/re-poll/merge.
- OpenCode fallback proof is not just “binary exists”. It needs a wrapper, a result schema, fake/contract smoke, postflight scope verification, and explicit authority-false checks in both top-level and nested `authority` fields.

## Implementation checklist

1. Create/use an isolated worktree for relay implementation WIP.
2. Add executor operations behind explicit `--mode execute --operation ...` choices and fail-closed argument requirements.
3. Acquire `hermes-busdriver-lock` with operation `finalization` before side effects; release it and verify release evidence is recorded.
4. Gate operations:
   - `commit`: staged changes + commit message + fresh litmus/pre-PR evidence;
   - `push`: clean worktree + explicit remote/ref;
   - `pr-create`: fresh pre-PR dual-review evidence;
   - `merge`: clean latest-head PR-grind loop immediately before merge;
   - marker production: Busdriver trusted writer command only, never raw marker file writes.
5. Add tests for both refusal and one safe happy path, including artifact schema, lock evidence, authority false/true separation, and side-effect transcript.
6. Update docs/status/skill references in the same change before PR.
7. Run the targeted tests first, then the full contract suite, smoke, `py_compile`, and `git diff --check` before commit/push/PR.
