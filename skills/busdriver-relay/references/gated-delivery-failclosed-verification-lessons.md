# Gated Delivery Fail-Closed Verification Lessons

Use these lessons when implementing or delivering Hermes Busdriver Relay finalization surfaces.

## Durable lessons

1. **Treat read-only reviewer blockers as ground truth before delivery.** If async/read-only reviewers flag safety issues in `hermes-busdriver-deliver`, pause PR delivery and fix the contract first. Important blockers include pre-lock evidence reuse, accepting summary strings without validating helper envelopes, unsafe authority flags, stale/malformed litmus payloads, and OpenCode route metadata being promoted too early.

2. **Mutating Delivery Mode must re-check evidence inside the lock.** For `commit`, `push`, `pr-create`, `merge`, and trusted pre-PR marker production, acquire the finalization lock first, then re-run/validate delivery-status and operation-specific litmus/pre-PR/PR-grind evidence while the lock is held. Pre-lock status output is advisory only and must not authorize side effects.

3. **Validate child helper envelopes, not just status strings.** Before accepting litmus/pre-PR/PR-grind evidence, require the expected schema, `read_only=true`, boolean `ok`, recognized decision status, empty/acceptable blockers for the specific operation, and recursive false authority flags. A `summary.decision.status` that looks fresh is not sufficient if the helper also reports unsafe authority, malformed fields, unknown status, or stale markers.

4. **OpenCode fallback stays non-dispatchable until the proof bundle is complete.** A raw `opencode` binary, wrapper scaffold, or successful fake smoke is not enough. Keep `relay.impl.secondary` / `relay.impl.fallback` as resolver/status metadata with `programmatic_dispatch_allowed=false`, `adapter_verified=false`, and `dispatch_blocker=opencode_adapter_not_verified` until wrapper hardening, schema validation, stale-artifact rejection, Git-env stripping, scope enforcement, negative contract tests, and optional real smoke are all present.

5. **Phase-appropriate smoke matters.** Full smoke with `--repo <dirty worktree>` may correctly fail because gate preflight requires a clean repo. While WIP is intentionally dirty, run full contract tests, compile/diff checks, read-only status helpers, relay brief, and smoke without a dirty target repo. Treat dirty-target smoke failure as expected only if the failing check is explicitly `repo_clean=false`/preflight blocked.

6. **Do not stage/commit merely to satisfy a gate.** If `deliver execute commit` returns `staged_changes_required`, that is only one blocker. Also inspect delivery/litmus evidence. If litmus/pre-PR markers are `stale_or_missing`, stop at the fail-closed boundary rather than staging and retrying. Hermes must not raw-write `.claude/*` trusted markers.

7. **Skill-source sync is part of the delivery contract.** When repo skill sources and installed skill copies drift, reconcile them before claiming completion. Use a whole-tree byte compare (`only_repo`, `only_inst`, `diff`) and align both directions deliberately: preserve installed-only durable references when they are valid, but normalize current-policy wording in both repo and installed copies.

8. **Evidence wrappers should not hide shell mistakes.** If a verifier snippet fails because of local shell composition (for example heredoc consuming stdin that a pipe was expected to provide), classify that as harness error and rerun with a simpler subprocess/JSON parse. Do not turn a wrapper typo into a helper failure claim.

## Verification pattern

Before finalizing a gated delivery slice, collect and report at least:

```text
uvx --from pytest pytest tests/contract -q -p no:cacheprovider
python3 -m compileall -q scripts tests
git diff --check
scripts/hermes-busdriver-relay-brief --pretty
scripts/hermes-busdriver-finalization-contract-status --pretty
scripts/hermes-busdriver-finalization-readiness --pretty
repo-vs-installed skill whole-tree byte compare
phase-appropriate smoke (dirty-target smoke only after commit/clean state)
```

Then attempt `hermes-busdriver-deliver --mode execute --operation <op>` only when fresh operation-specific evidence exists. A blocked result with lock acquire/release and false authority flags is a successful safety outcome, not a failed delivery to paper over.