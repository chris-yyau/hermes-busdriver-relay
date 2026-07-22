# ADR 0008 — Gated Delivery Executor and OpenCode Fallback Adapter

## Status

Accepted implementation slice.

## Context

ADR 0005 identified five policy-blocked finalization surfaces: mutating delivery execution, mutating result envelopes, programmatic dual review, PR-grind fix/push/re-poll, and marker interop. The safe unlock is not to make Hermes a standing Busdriver authority. The safe unlock is to give Hermes a narrow executor that re-checks Busdriver-equivalent evidence immediately before each side effect and fails closed when evidence is stale, missing, malformed, or outside scope.

The user also wants OpenCode + Go to be a secondary/fallback draft-only metadata lane, but only with adapter proof and authority flags false.

## Decision

Add a narrow `hermes-busdriver-deliver execute` side-effect surface:

- production Pi/OpenCode execution is `policy_blocked` by `agent_containment_and_credential_broker_unavailable`; adapter execution tests use explicit non-installed harnesses and grant no production dispatch authority.
- caller-supplied verifier execution is `policy_blocked` by `verifier_containment_unavailable`; production gate/deliver surfaces fail before launching a verifier.
- `pre-pr-review` is `policy_blocked` by `isolated_review_runtime_unavailable` before delivery-status, repository/state/lock, artifact, credential, or trusted-writer handling. The dormant Busdriver-writer adapter is not executed. Hermes does **not** raw-write `.claude/*` marker files.
- `commit` requires staged changes, a commit message, and fresh litmus/pre-PR evidence from `hermes-busdriver-litmus-status`.
- `push` has a gated CLI/result-envelope surface, but the side effect is `policy_blocked` and non-dispatchable. Ordinary Git omits an unchanged base refspec from the receive transaction, so it cannot atomically bind the reviewed base SHA while updating the topic branch; execution therefore fails closed with `atomic_push_base_binding_unavailable` until a verified conditional server-side seam exists.
- `pr-create` has a validated parser/result-envelope surface but is `policy_blocked` by `atomic_pr_create_binding_unavailable` because the current `gh pr create` adapter cannot atomically bind creation to the reviewed post-commit head.
- `merge` requires a clean latest-head PR-grind loop result and an atomic server-side precondition that binds both the reviewed head SHA and reviewed base SHA. GitHub CLI direct merge currently exposes only `--match-head-commit`, so the executor fails closed with `atomic_merge_base_binding_unavailable`; a verified merge queue or future conditional API is required before this operation may mutate.

Only an operation that passes its fixed early policy blocker may acquire the Hermes `finalization` single-flight lock or record a redacted `hermes-busdriver-mutating-delivery-run/v0` side-effect transcript. Early-blocked operations truthfully report the lock as skipped, do not synthesize run identity/timestamp state, and do not persist artifacts. All paths keep the legacy reusable authority flags default-deny so persisted artifacts cannot become standing authority for later operations.

Add an OpenCode fallback adapter proof:

- `scripts/opencode/run-opencode-busdriver-draft` launches OpenCode in a generic gated draft lane.
- `adapters/opencode/opencode-result.schema.json` requires `needs_busdriver_review | blocked` status and all commit/push/PR/merge/marker/deploy/release/publish/finalization flags false.
- The non-installed test harness validates `opencode-result.json`, preflight/postflight contracts, schema/authority, scope reconciliation, timeout/missing/malformed/oversized artifacts, and fake-binary behavior. Historical real-smoke evidence does not supply OS-enforced containment or a parent-held credential broker, so production programmatic dispatch remains blocked.

## Marker ownership

Hermes is not a trusted marker writer by filename convention. The trusted writer identity for PR review markers remains the Busdriver script surface itself (`run-review-loop.sh --write-backstop-verdict` and `--write-pr-marker`) under Busdriver plugin root, with Busdriver validation and marker semantics. The production relay does not invoke that surface: `pre-pr-review` stops at `isolated_review_runtime_unavailable`, and Hermes must not raw-write markers.

## PR-grind fix loops

This slice deliberately does **not** add an autonomous `pr-grind-fix-loop` mutating entrypoint. Production Pi/OpenCode fixes remain blocked by `agent_containment_and_credential_broker_unavailable`; functional test harnesses are not a production routing seam. Push and PR creation remain blocked by `atomic_push_base_binding_unavailable` and `atomic_pr_create_binding_unavailable`; no workflow may bypass those guards with direct Git/GitHub commands.

## Consequences

This retires only the broad “no parser/result-envelope surface exists” gap while preserving Busdriver as the trust authority. Production agent dispatch, verifier execution, pre-PR review, push, PR creation, and merge remain `policy_blocked` under their explicit blockers. Other unsafe surfaces include raw marker writes, deploy/release/publish, and autonomous fix loops.
