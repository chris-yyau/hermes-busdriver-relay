# Delivery litmus-status integration lessons

Session lesson from adding `hermes-busdriver-litmus-status` evidence to Delivery Mode status/finalization readiness.

## What future relay work should preserve

- `hermes-busdriver-delivery-status` may include sanitized `litmus_status.summary` evidence and propagate it through `hermes-busdriver-finalization-readiness` handoff envelopes.
- This evidence is advisory/read-only only. It must never grant commit/push/PR/merge/deploy/release/publish/marker-write authority.
- Marker payloads and raw JSON payloads should not be echoed. Summaries should keep only structural fields, hashes, lengths, timestamps, freshness booleans, and decision metadata.

## Fail-closed pitfalls found by Busdriver PR-mode Codex lead

1. A valid litmus-status envelope with `decision.status == "blocked"` or top-level `ok == false` must not be downgraded to a warning-only state that still allows `ready_for_commit_or_pr_handoff`.
   - Delivery status/finalization readiness may still describe the evidence, but the handoff must be blocked or otherwise clearly not ready when litmus/pre-PR evidence is blocked.
   - Regression tests should cover dirty-draft delivery status and finalization-readiness handoff behavior for `blocked` litmus status and `ok == false`.

2. If the litmus-status subprocess exits nonzero, treat that as a subprocess failure even when stdout contains valid JSON.
   - Do not accept `returncode != 0` as a normal litmus result merely because parsed JSON has `ok: false`.
   - Regression tests should use a wrapper script that prints a valid litmus-status JSON envelope then exits nonzero; expected result is `litmus_status_subprocess_failed` and no finalization authority.

3. Validate nested authority flags completely and explicitly.
   - `finalization_allowed`, `commit_allowed`, `push_allowed`, `pr_allowed`, `merge_allowed`, `deploy_allowed`, `release_allowed`, `publish_allowed`, and `marker_write_allowed` must all be present/treated as false in accepted litmus evidence.
   - A litmus payload with any of those true (including deploy/release/publish) should fail closed with `litmus_status_authority_flags_unsafe` and block delivery/finalization. Do not sanitize away an unsafe true value and then accept the payload.
   - Keep the same complete false-authority set in `hermes-busdriver-litmus-status`, delivery-status validation, and all fixtures/assert helpers.

4. Treat “sanitized evidence” as an explicit allowlist, not a shallow copy.
   - Do not copy `repo`, `state_dir`, marker maps, or `decision.warnings` / `decision.blockers` wholesale from litmus-status output, especially when `--litmus-status-script` or fixture input can be custom.
   - Recommended allowlists: repo `{root, branch, head, head_timestamp, base_ref, branch_diff_hash}`; state_dir `{path, exists, is_symlink, has_symlink_component}`; marker names `{litmus_passed, pr_codex_lead, pr_backstop_verdict, pr_review_passed}`.
   - Marker values should pass through the marker-field sanitizer only; unknown marker keys and unknown marker fields must be dropped. Raw diagnostic warnings/blockers should be redacted, reason-code allowlisted, or omitted so sentinel secrets cannot propagate into finalization handoff evidence.
   - Add malicious-fixture tests asserting the sentinel is absent from the entire delivery-status JSON and finalization-readiness handoff JSON.

5. Validate the type of top-level `ok` before coercion.
   - Do not use `bool(result.get("ok"))` on untrusted JSON; `ok: "false"` becomes truthy in Python and can make malformed freshness evidence look passing.
   - Accepted litmus payloads should require `ok` to be a JSON boolean. Non-boolean `ok` should fail closed as malformed/schema-invalid and block delivery/finalization.

6. Budget wrapper timeouts around nested probes.
   - `hermes-busdriver-finalization-readiness` shells out to delivery-status, and delivery-status may run PR-grind plus litmus-status. The wrapper timeout must be at least `pr_grind_timeout + litmus_status_timeout + margin` (or otherwise computed from forwarded child budgets), not a fixed value that can expire before delivery-status emits structured fail-closed JSON.
   - Add tests that inspect/force the computed delivery-status timeout when PR-grind and litmus budgets are both present.

## Verification pattern

After fixes, run:

```bash
uvx --from pytest pytest tests/contract/test_delivery_status.py tests/contract/test_finalization_readiness.py -q
uvx --from pytest pytest tests/contract -q
scripts/hermes-busdriver-smoke --plugin-root ~/.claude/plugins/marketplaces/busdriver --pretty
git diff --check
```

Then rerun Busdriver PR-mode Codex lead before push/PR/merge:

```bash
export CLAUDE_PLUGIN_ROOT="$HOME/.claude/plugins/marketplaces/busdriver"
export BUSDRIVER_PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"
export BUSDRIVER_REVIEW_CLI=codex
export LITMUS_MODE=pr
export LITMUS_PR_BASE=origin/main
bash "$CLAUDE_PLUGIN_ROOT/skills/litmus/scripts/init-review-loop.sh" --force 10
bash "$CLAUDE_PLUGIN_ROOT/skills/litmus/scripts/run-review-loop.sh"
```

If Codex finds a valid blocker, dispatch the smallest mutating subagent with strict TDD, then have main Hermes verify/amend and rerun the review loop.

## PR-mode operator sequencing lessons

- Treat each async reviewer/subagent result as provisional until the parent re-reads the changed files and verifies the actual diff. Subagent self-reports can overlap or race; main Hermes owns final reconciliation, test/smoke evidence, and commit/amend.
- When multiple review streams identify overlapping blockers, avoid concurrent mutating edits to the same files unless the scopes are explicitly separated. Prefer one mutating TDD subagent for the active blockers and read-only validation for additional suspected blockers; then dispatch the next mutating subagent with the confirmed acceptance criteria.
- After amending a commit, recompute the PR diff hash and rerun PR-mode Codex lead. Prior Codex/backstop artifacts are bound to the old diff and must not be reused.
- Codex lead PASS is not the final PR marker. After PASS, dispatch exactly one read-only Security/Bugs backstop with an injected review packet (merge base, changed-file list, capped log, full `base...HEAD` diff, and the reviewed diff hash). Do not ask the backstop to infer from the worktree.
- Persist the backstop result only through Busdriver's trusted `run-review-loop.sh --write-backstop-verdict` writer with `BACKSTOP_MODEL` and the reviewed hash, then call `--write-pr-marker`; direct writes or hand-crafted marker files are not acceptable.
