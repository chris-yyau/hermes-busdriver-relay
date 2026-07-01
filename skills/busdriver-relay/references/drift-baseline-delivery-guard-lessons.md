# Drift-baseline delivery guard lessons

Use when extending `hermes-busdriver-delivery-status` / `hermes-busdriver-finalization-readiness` with Busdriver drift-baseline evidence.

## Durable lessons

- Treat Busdriver drift baseline evidence as a Phase-0 finalization guard, not as a delivery authorization source.
- `hermes-busdriver-status --drift-baseline <json>` is the source of drift evidence. It can return success while `busdriver_drift.finalization_compatible=false`; that means the probe succeeded but handoff/finalization must be blocked.
- Missing, invalid, unsupported-schema, or drifted baselines should fail closed in delivery/finalization readiness when a baseline was supplied.
- Keep probe execution success separate from readiness: `ok=true` + `busdriver_drift.status=drifted` is a valid status result and still a blocker.
- When wrapping delivery-status from finalization-readiness, every nested child timeout added to delivery-status must be forwarded and included in the wrapper budget. If delivery-status runs PR-grind, litmus-status, and Phase-0 status, the wrapper budget must cover `pr_grind_timeout + litmus_status_timeout + phase0_status_timeout + margin`.
- Forward `--phase0-status-timeout` from finalization-readiness to delivery-status whenever drift baseline evidence can make delivery-status run Phase-0 status.
- Expose drift evidence in handoff envelopes as read-only evidence only; never set commit/push/PR/merge/deploy/release/publish/marker-write authority true.

## Test pattern

- Build a compatible baseline by first running `hermes-busdriver-status --plugin-root <fake>` and saving `package.version` plus `critical_file_hashes`.
- Compatible baseline: no drift blocker, all authority flags false.
- Drifted baseline: mutate a covered critical file or package version and assert `busdriver_drift_incompatible`.
- Missing/invalid/unsupported baseline: assert fail-closed blocker and false authority flags.
- Finalization readiness needs tests for both direct Phase-0 status and nested delivery-status forwarding:
  - `--drift-baseline` forwarded to delivery-status and direct status probe.
  - `--phase0-status-timeout` forwarded to delivery-status.
  - effective delivery-status timeout includes the phase0 timeout plus margin.

## PR-grind pitfall

Reviewer bots will flag timeout budget regressions quickly. After adding any nested subprocess to delivery-status, update wrapper timeout budget tests before pushing.