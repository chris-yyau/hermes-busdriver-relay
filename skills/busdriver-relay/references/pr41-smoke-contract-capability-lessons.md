> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR41 Smoke Contract Capability Evidence Lessons

Context: continuation after PR #38–#40. The safe slice exposed embedded finalization contract evidence in smoke summaries and added finalization-readiness / finalization-contract-status helpers to delivery-status capability inventory.

## Durable lessons

- Smoke summaries that expose authority or capability flags must remain fail-closed even when nested helper evidence is missing or malformed. When copying compact authority fields from nested status payloads, coerce with strict boolean checks such as `value is True`; never pass through `None` for permission-looking fields. A missing authority value should summarize as `False`, not `null`.
- Add regression coverage for both the happy path and missing/malformed authority path. The test should prove compact summary authority remains exactly false when `finalization_contract_status.authority` is absent.
- Delivery-status capability inventory can list helper availability without invoking the helpers or granting authority. Adding `finalization_readiness` and `finalization_contract_status` to `relay_capabilities` is inventory-only and should leave commit/push/PR/merge/deploy/release/publish/marker-write false.

## PR-grind / delivery-status pitfall

- After any fix push, previous PR-grind checker output is stale even if it was saved in `/tmp` or a delivery artifact. Do not pass stale `--pr-grind-result-file` data into `hermes-busdriver-delivery-status` after a new commit. Regenerate the checker/loop output for the latest PR head first, then feed that fresh result into delivery-status if needed.
- If `pr-grind-loop` says the latest head is clean but a later delivery-status invocation says `actionable_pr_feedback_present`, check whether delivery-status was given an old fixture/result file before treating that as a live blocker.

## Verification pattern for this slice class

```text
py_compile smoke + delivery-status
→ focused smoke/delivery-status tests
→ full tests/contract
→ smoke sample confirming contract summary schema/policy/counts/authority false
→ delivery-status sample confirming capability inventory entries and authority false
→ commit litmus
→ PR-mode Codex lead + read-only backstop + trusted PR marker
→ latest-head PR-grind after every push (fresh result only)
→ merge only after latest-head clean
```
