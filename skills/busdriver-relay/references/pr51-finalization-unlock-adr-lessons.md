# PR51 Finalization Unlock ADR Lessons

Session: relay PR #51 (`docs: add finalization unlock ADR`).

## What changed

- Added `ADRs/0006-programmatic-dual-review-marker-interop.md` as a **non-mutating design/spike contract** for:
  - `programmatic-litmus-pre-pr-dual-review`
  - `busdriver-marker-interop`
- Linked ADR 0006 from `README.md` and `docs/settling-checks-v2.md`.
- Added `tests/contract/test_finalization_unlock_contract_docs.py` to lock the contract wording without granting authority.

## Durable workflow lessons

1. **Do not touch Claude installed plugin clones/caches during relay delivery.**
   - Relay work belongs in `<relay-repo>`.
   - Busdriver source work belongs in `<busdriver-source>`.
   - Do not modify `~/.claude/plugins/marketplaces/busdriver` or `~/.claude/plugins/cache/busdriver/...` unless the user explicitly asks for plugin repair/install work.
   - If a Claude session reports `Unknown skill` and `orchestrator SKILL.md not found` under the plugin cache, treat it as plugin cache/index mismatch and recommend `/reload-plugins`, `/reload-skills`, or a fresh Claude session; do not create `skip-litmus.local`.

2. **ADR-only finalization unlock slices must keep authority false.**
   - Phrase the ADR as `non-mutating design/spike contract`.
   - Explicitly forbid executor, dispatcher, marker writer, commit, push, PR, merge, deploy, release, publish, and Busdriver marker writes.
   - Keep ADR 0005 policy-blocked surfaces intact; ADR 0006 only frames future evidence/interop contracts.

3. **Future dual-review evidence schema must include role mapping and aggregation decision.**
   - Reviewer feedback caught that `hermes-busdriver-dual-review-execution/v0` must mention at least:
     - input digest
     - reviewed diff hash
     - reviewer role mapping
     - reviewer verdicts/findings
     - aggregation decision
     - confidence/limitations
     - timestamps/freshness
     - data egress/redaction
     - artifact refs

4. **Docs-link contract tests should verify each document independently.**
   - Do not concatenate `README.md` and `docs/settling-checks-v2.md` into one `linked_text` assertion; that can hide a missing ADR link in one file.
   - Assert the required ADR pointer and policy wording per file.

5. **Branch-sensitive finalization locks recur.**
   - Lock release keys include branch/worktree identity.
   - If a merge switches to `main` and release returns `not-found`, recreate/switch to the branch identity recorded in the lock, release with the original token, then return to `main` and delete the local branch.

## Verification pattern used

- `python3 /tmp/check_pr51_finalization_unlock_docs.py`
- focused docs/finalization tests (`76 passed`)
- full `tests/contract` (`381 passed`)
- `python3 -m py_compile scripts/hermes-busdriver-*`
- `scripts/hermes-busdriver-smoke --plugin-root <busdriver-source> --repo . --pretty`
- `scripts/hermes-busdriver-deliver --mode execute --operation verify ...`
- latest-head PR-grind after every push

## Reviewer feedback handled

- CodeRabbit/Cubic requested per-file docs-link assertions.
- Cubic requested `reviewer role mapping` and `aggregation decision` in ADR 0006's future evidence schema list.

Keep this as a pattern for future ADR/design-contract relay slices: narrow docs+contract test first, no mutating implementation until the Busdriver-approved seam exists.
