# Deliver / Finalization / PR-grind Read-only Audit Lessons

Context: read-only audit of `hermes-busdriver-relay` current deliver, finalization-contract-status, PR-grind checker/loop code and focused contract tests. No repo mutations were made. Target repo was clean on `main`; focused tests for deliver/finalization-contract/pr-grind passed (`134 passed`).

## Durable lessons

1. **Do not treat a read-only PR-grind clean signal as merge authority.**
   - `hermes-busdriver-pr-grind-check` may determine `status=clean`, but that evidence should be named as evidence (`pr_grind_clean`, `latest_head_clean`) rather than authority (`merge_allowed=true`).
   - Any future checker/loop status envelope should include `read_only=true`, a version, and all finalization/mutation/marker authority flags false.
   - Regression tests should assert clean PR-grind evidence never sets `merge_allowed`, `finalization_allowed`, `commit_allowed`, `push_allowed`, `pr_allowed`, or `marker_write_allowed` true.

2. **Validate child checker payloads before accepting loop clean.**
   - `hermes-busdriver-pr-grind-loop` should only accept checker clean evidence after validating schema/version/read_only/ok, recognized status, `clean == (status == "clean")`, and nested decision authority safety.
   - Malformed checker payloads, status/clean mismatches, authority-positive child decisions, or unrecognized statuses should become `blocked`/`policy_gap`, never clean.
   - Fixture/offline checker payloads must stay explicit test fixtures and must not be confused with live PR-grind evidence.

3. **Keep `deliver` non-finalizing until Busdriver authority exists.**
   - `hermes-busdriver-deliver` may wrap verify-only commands and the read-only PR-grind loop, but it must not grow commit/push/PR/merge operations without satisfying ADR 0005 authority sources.
   - Even when a child loop says clean, the deliver wrapper decision/run authority remains all false and the result is only a handoff/status artifact.
   - Tests should reject nested loop/checker payloads with positive authority and verify deliver still fails closed.

4. **Finalization-contract-status remains a policy-blocked capability matrix, not an unlock.**
   - Current healthy output is `remaining_work_count=5`, `policy_blocked_count=5`, `capability_allowed_count=0`, and every authority/capability flag false.
   - Safe follow-up work can add read-only metadata such as `next_required_authority_sources`, `busdriver_approval_required`, or `safe_next_slice`, but must keep `implemented=false`, `retired=false`, `capability_allowed=false`, and `current_evidence=[]` unless an approved helper actually verifies live evidence.
   - The five remaining-work IDs (`deliver-mutating-executor`, `mutating-final-result-envelope`, `programmatic-litmus-pre-pr-dual-review`, `mutating-pr-grind-fix-push-loop`, `busdriver-marker-interop`) stay policy-blocked without Busdriver source-of-truth approval, hook/equivalent proof, fresh repo/PR evidence, fresh gate/review evidence, lock authority, data-boundary authority, and schema authority.

## Minimal safe implementation path after this audit

1. Harden `hermes-busdriver-pr-grind-check` output shape: add version/read_only/all-false authority and rename clean evidence away from `merge_allowed`.
2. Add focused checker tests for clean evidence with all authority false.
3. Harden `hermes-busdriver-pr-grind-loop` child validation before accepting clean.
4. Add loop tests for malformed child evidence, clean/status mismatch, and authority-positive child decisions.
5. Keep `hermes-busdriver-deliver` operation choices non-mutating and add wrapper tests that unsafe nested PR-grind evidence fails closed.
6. Only after those hardening slices should any ADR 0005 implementation work be considered, and only if Busdriver authority is proven rather than inferred.
