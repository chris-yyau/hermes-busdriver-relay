# Finalization executor status-sync lessons

Session context: implementing a gated `hermes-busdriver-deliver` executor plus OpenCode fallback proof exposed a class-level relay maintenance pitfall: code can unlock a previously policy-blocked surface while status/readiness/docs/skill text still describes the old all-blocked world.

## Durable lessons

- When a gated finalization executor lands, update every status surface in the same slice, not just the executor code:
  - `scripts/hermes-busdriver-finalization-contract-status`
  - `scripts/hermes-busdriver-finalization-readiness`
  - `scripts/hermes-busdriver-relay-brief`
  - README / `docs/CURRENT_STATUS.md` / `docs/settling-checks-v2.md`
  - skill source and durability tests
- Prefer explicit split states over binary all-allowed/all-blocked wording:
  - `implemented_gated` for executor/envelope rows that exist but are still runtime-evidence gated;
  - `partial_policy_blocked` for overall decisions when some surfaces are implemented and others remain blocked;
  - keep `capability_allowed=false` and all reusable authority flags false in read-only status helpers.
- Do not treat `implemented=true` / `retired=true` as authority-positive in recursive false-authority tests. Those are lifecycle metadata, not permissions. Keep tests focused on permission fields such as `commit_allowed`, `push_allowed`, `merge_allowed`, `marker_write_allowed`, `programmatic_execution_allowed`, `capability_allowed`, and `safe_to_execute_by_this_helper`.
- Contract/status helpers remain read-only even when they report `implemented_gated`. They should never run dispatchers, mutate repos, write markers, or make old artifacts reusable authority.
- Docs tests should assert the nuanced wording: ADR 0006 remains a design/spike for programmatic dual-review and marker-interop, while ADR 0008 / the executor slice can implement gated commit/push/PR/merge surfaces.
- `relay-brief` should give dirty tree / skill-sync drift precedence over “ready/idle” conclusions. A dirty WIP with passing tests is still `needs_local_reconciliation`, not delivered.
- After adding or patching installed skill references during relay work, expect repo-vs-installed skill drift. Reconcile that drift before claiming final relay completion.

## Verification pattern

Use a focused status/docs suite before the full contract suite:

```bash
uvx --from pytest pytest -q \
  tests/contract/test_skill_references.py \
  tests/contract/test_finalization_unlock_contract_docs.py \
  tests/contract/test_finalization_contract_status.py \
  tests/contract/test_finalization_readiness.py \
  tests/contract/test_relay_brief.py \
  tests/contract/test_smoke.py

uvx --from pytest pytest tests/contract -q -p no:cacheprovider
python3 -m compileall -q scripts tests
git diff --check
```
