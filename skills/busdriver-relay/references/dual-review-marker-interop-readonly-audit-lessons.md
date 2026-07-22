# Dual-Review / Marker-Interop Read-Only Audit Lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Session context: read-only audit of programmatic dual-review and marker-interop surfaces across `hermes-busdriver-relay` and the live Busdriver plugin. No files were modified during the audit.

## Live surface observed

- Relay repo was clean on `main`; live Busdriver marketplace plugin was `package.json` version `1.81.1` and had pre-existing local state (`ahead` and one modified file) unrelated to the audit.
- Relevant relay surfaces:
  - `ADRs/0006-programmatic-dual-review-marker-interop.md`
  - `scripts/hermes-busdriver-litmus-status`
  - `scripts/hermes-busdriver-finalization-readiness`
  - `scripts/hermes-busdriver-finalization-contract-status`
  - `scripts/hermes-busdriver-delivery-status`
  - `tests/contract/test_litmus_status.py`
  - `tests/contract/test_finalization_readiness.py`
  - `tests/contract/test_finalization_contract_status.py`
- Relevant live Busdriver surfaces:
  - `hooks/hooks.json`
  - `hooks/gate-scripts/pre-pr-gate.sh`
  - `hooks/gate-scripts/pre-implementation-gate.sh`
  - `hooks/gate-scripts/post-pr-consume-marker.sh`
  - `skills/litmus/scripts/run-review-loop.sh`
  - `skills/litmus/references/pr-review-mode.md`
  - `tests/test-pr-dual-voice.sh`
  - `tests/test-pr-excluded-only-autopass.sh`

## Current safe relay posture

Relay can safely implement / maintain **read-only observation and classification** only:

1. marker freshness reading through `hermes-busdriver-litmus-status`;
2. sanitized delivery-status litmus summaries;
3. finalization-readiness advisory envelopes (`dual_review_readiness`, `pre_pr_dual_review_evidence`);
4. finalization-contract-status rows for ADR 0005/0006 policy-blocked work;
5. docs/status updates explaining the current contract.

These surfaces must keep all authority false: commit/push/PR/merge/finalization, `marker_write_allowed`, `programmatic_execution_allowed`, `dispatch_allowed`, `marker_interop_allowed`, and `safe_to_execute_by_this_helper`.

## Busdriver 1.81.1 marker modes matter

Live Busdriver `pre-pr-gate.sh` accepts more than the original ADR 0006 normal dual-review marker:

- **Normal dual-voice path**: `pr-review-passed.local` is a bare 64-hex branch diff hash, and both `pr-codex-lead.local.json` and `pr-backstop-verdict.local.json` are fresh `status: PASS` for that hash.
- **Fast bypass path**: `PASS-FAST-<diff_hash>-<epoch>` is accepted when hash and max-age match. It means the Codex PR lead ran and the backstop was explicitly skipped as an audited Busdriver-native bypass.
- **Excluded-only path**: `PASS-EXCLUDED-<diff_hash>-<epoch>` is accepted when hash and max-age match. It means the entire diff was review-excluded and no reviewer ran.

Do **not** collapse these three states into one `dual_review_fresh` concept. `PASS-FAST` and `PASS-EXCLUDED` may be current Busdriver pre-PR gate-fresh evidence, but they are not full programmatic dual-review evidence.

## Safe follow-up slice pattern

A good next small implementation slice is still non-mutating:

1. Update ADR/docs from stale “Busdriver 1.74.0 evidence” wording to the current observed Busdriver version/semantics.
2. Extend `hermes-busdriver-litmus-status` and contract tests with positive coverage for:
   - `dual_voice_hash` + lead/backstop artifacts;
   - `pass_fast`;
   - `pass_excluded`;
   - wrong hash / stale age / malformed markers staying stale or blocked.
3. In finalization-readiness, separate pre-PR gate freshness from full dual-review freshness, for example:
   - `dual_review_fresh_read_only`;
   - `fast_bypass_fresh_read_only`;
   - `excluded_only_fresh_read_only`;
   - `stale_or_missing` / `blocked` / `unavailable`.
4. Update contract-status missing criteria to explicitly include the distinction between Busdriver-native bypass markers and full dual-review authority.
5. Keep `programmatic-litmus-pre-pr-dual-review` and `busdriver-marker-interop` `policy_blocked`, `implemented=false`, `retired=false`, `capability_allowed=false`.

## Still Busdriver-policy blocked

Do not implement any of these in relay without a later explicit Busdriver-approved integration surface:

- launching programmatic Codex lead or Opus/Claude backstop as Busdriver-native evidence;
- executing Busdriver trusted marker writers from Hermes relay (`run-review-loop.sh --write-backstop-verdict`, `--write-pr-marker`, `--auto-pr-review`);
- writing, updating, deleting, or consuming `.claude/*` Busdriver markers or artifacts;
- treating relay role resolution (`selected_agent`) as Busdriver-native Claude runtime authority;
- retiring ADR 0005 remaining-work rows based on advisory/read-only evidence alone.

## Verification notes

Use read-only probes first: git status, file reads, and `hermes-busdriver-finalization-contract-status`. A successful contract-status probe should report the dual-review and marker-interop rows as `policy_blocked` with `capability_allowed=false` and `safe_to_execute_by_this_helper=false`.
