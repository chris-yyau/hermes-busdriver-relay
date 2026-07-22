# Finalization contract matrix review lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this when updating `hermes-busdriver-finalization-contract-status`, `hermes-busdriver-finalization-readiness`, ADR 0005, or relay brief/status surfaces after Delivery Mode executor work.

## Keep machine-readable status aligned with actual deliver operations

- Audit `scripts/hermes-busdriver-deliver --operation` choices before marking a finalization surface `implemented_gated`.
- If `pre-pr-review` is available and side-effecting (for example it invokes Busdriver trusted marker/backstop writers or emits a mutating delivery-run envelope), the contract matrix must either include it in the implemented executor surface or add a separate row/policy note for it. Do not model only commit/push/PR-create/merge while the executable exposes pre-PR review as a gated side-effect path.
- Wording in ADR 0005, policy strings, `operations`, tests, and brief next-step text must describe the same surface. If ADR text says the executor covers only commit/push/PR-create/merge while code exposes pre-pr-review, Busdriver review should block.

## Implemented does not mean standing authority

- `implemented_gated: true` is implementation evidence only; it must not clear runtime authority requirements.
- Keep `capability_allowed` and all authority flags false in status/readiness helpers.
- For implemented-but-not-retired rows, preserve missing runtime criteria such as user intent, fresh repo/PR evidence, fresh gate/review evidence, lock authority, data-boundary policy, and postflight reconciliation.
- Do not clear `missing_authority_sources` solely because a row is implemented; consumers may interpret that as full authority proof.

## Relay brief decision guard

- `relay-brief` should recommend gated delivery only when the contract summary reports both `implemented_count > 0` and remaining `policy_blocked_count > 0`.
- If a fixture or external helper reports only fully `policy_blocked` contract status, keep the older blocked next step (`none_stop_cleanup_loop_until_busdriver_approves_new_surface`) instead of steering operators toward gated delivery.
- When rendering brief text, copy through `implemented_count`; otherwise text can show `implemented=None` and hide the contract state.

## Verification pattern

1. Update implementation, ADR/docs, and contract tests together.
2. Run focused contract tests for finalization status/readiness/brief/docs.
3. Run full `tests/contract` with scoped signing override.
4. Recompute the exact staged diff hash.
5. Reinitialize Busdriver litmus state with that hash in the prompt and rerun review until PASS before Delivery Mode commit.
