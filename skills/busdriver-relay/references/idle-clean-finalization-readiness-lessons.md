# Idle clean-main finalization-readiness lessons

When implementing the safe read-only/status slice for `hermes-busdriver-finalization-readiness`, distinguish **no candidate** from **blocked candidate**:

- If the repo is clean, no PR is supplied, and delivery-status reports `stage == "no_local_changes"` or `status == "no_local_delivery_candidate"`, readiness should report `status: "no_finalization_candidate"`, `ready: false`.
- In that idle state, stale/missing/blocked litmus evidence from delivery-status is not itself a readiness blocker; there is no commit/PR/merge candidate to finalize. Keep the stale-litmus detail in `delivery_status.decision.blockers` if delivery-status reported it, but filter `litmus_status_not_fresh` out of `readiness.blockers` for the idle no-candidate readiness layer.
- Do **not** broaden this to dirty trees, PR readiness, malformed child envelopes, unavailable helpers, drift incompatibility, contract-status failures, or unsafe authority flags. Those remain fail-closed blockers.
- Add a focused regression test that proves the idle clean repo reports `no_finalization_candidate`, while recursively asserting no finalization/commit/push/PR/merge/deploy/release/publish/marker-write authority is introduced.
- Use strict RED/GREEN: first run the new test and observe the stale `blocked` behavior, then make the minimal readiness-layer change, then run the full finalization-readiness contract file.
- Leave the dirty tree for main Hermes/operator verification/finalization when the user asks for a safe read-only/status slice; do not commit/push/PR/merge from the slice worker.

Verification pattern from the session:

```bash
pytest tests/contract/test_finalization_readiness.py::test_clean_idle_repo_reports_no_finalization_candidate_despite_stale_litmus -q
pytest tests/contract/test_finalization_readiness.py -q
git diff --check
git status --short --branch
```
