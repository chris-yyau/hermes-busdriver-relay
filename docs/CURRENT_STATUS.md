# Current Status — Hermes Busdriver Relay

Last verified against the observed installed Busdriver marketplace plugin `1.91.2` used by smoke. The reviewed repository `trusted-runtime-manifest` separately pins Busdriver package version `1.90.0` and commit `835dc1784a7ae5c34a5f8f58d6731a482f64df0a`.

## Current candidate verification

Current candidate status: **BLOCKED / UNSEALED**. Sealing any active remediation tree requires a successful exact-tree full suite, complete independent reviews, and delivery authority. No historical run below is evidence for the current bytes.

## Locations

| Component | Path / URL |
|---|---|
| Relay repo | `<relay-repo>` |
| Relay GitHub | `https://github.com/chris-yyau/hermes-busdriver-relay` |
| Busdriver source path read during Phase 0 | `<busdriver-source>` |
| Installed Busdriver marketplace plugin used for smoke | `~/.claude/plugins/marketplaces/busdriver` |
| Hermes skill install path | `~/.hermes/skills/autonomous-ai-agents/busdriver-relay` |

## Completed scope

Relay v1 is complete as a **read-only/status + lock + smoke** integration. Relay v2 has a **Hermes-side production-blocked gate/state checker**, **Pi/OpenCode adapter contracts verified only in non-installed harnesses, with production dispatch blocked**, a **read-only balanced agent work planning envelope**, a **read-only PR-grind readiness checker**, a **read-only bounded PR-grind polling loop**, a **fail-closed delivery dispatcher whose caller-supplied verifier is blocked before delivery-status or credential-capable helpers, plus read-only `pr-grind` loop execution, durable `hermes-busdriver-delivery-run/v0` envelopes, process-scoped authenticated artifact writes whose cross-process `--mode status` lookup cannot establish a valid MAC and therefore returns `run_not_found`, identically to a forgery; unverifiable bytes are not evidence, authority-negative verifier blocker envelopes, nested helper timeout budgeting, and state-dir-aware litmus evidence forwarding**, a **read-only litmus/pre-PR marker freshness status helper**, a **read-only finalization readiness / handoff envelope with machine-readable finalization guardrails, dual-review readiness evidence, advisory pre-PR dual-review evidence classification, and recursive fail-closed authority hardening**, a **read-only finalization contract status / capability matrix for ADR 0005 remaining-work unlock criteria**, **read-only Busdriver drift-baseline compatibility reporting**, **read-only finalization lock/status blocking**, **configurable read-only relay equivalents with explicit default-deny permission/proof metadata for reviewer/voice/arbiter/backstop status roles**, a **read-only dispatcher-facing relay role resolver**, **optional relay-role resolution evidence inside delivery/finalization status envelopes**, and **delivery-status capability inventory entries for public relay helpers**. The non-mutating relay surface is complete for the current policy scope. Draft implementation remains non-finalizing; Delivery Mode finalization is still operator-level, but it now has deterministic checker/status/loop/plan/verify/pr-grind/handoff/contract-status/balance-plan envelopes for latest-HEAD checks/comments/mergeability, configured relay-role selection, normalized/redacted marker freshness evidence, explicit non-mutating guardrails, ADR 0005 contract-status rows showing the gated executor implemented and remaining surfaces policy-blocked, dual-review role-readiness evidence, advisory pre-PR dual-review freshness classification, recursive authority-positive fail-closed checks, and durable run identity/artifact handoff.

Implemented:

- `skills/busdriver-relay/SKILL.md`
- `skills/busdriver-relay/references/*.md` including PR-grind delivery discipline, June 2026 reviewer-quality policy, claude-mem push, and user-preference/profile notes
- `config/trusted-runtime-manifest.json`
- `adapters/pi/busdriver-fs-broker.py`
- `adapters/pi/busdriver-tools.ts`
- `scripts/check-required-checks.sh`
- `scripts/opencode/run-opencode-busdriver-draft`
- `scripts/hermes-busdriver-status` including optional read-only `--drift-baseline <json>` compatibility reporting and relay-namespaced configurable equivalent reviewer/voice/arbiter/backstop status roles from a separate relay config JSON, with every default role explicitly declaring boolean `programmatic_dispatch_allowed` and `adapter_verified` metadata and omission degrading fail-closed
- `scripts/hermes-busdriver-relay-role` for read-only fail-closed selection of one configured relay equivalent role
- `scripts/hermes-busdriver-lock` with token-only release, no force bypass, and atomic generation retirement to a non-active tombstone after quarantine-rename revalidation; release performs no recursive pathname deletion, so a non-cooperative replacement is restored or preserved
- `scripts/hermes-busdriver-runtime-check`
- `scripts/hermes-busdriver-gate`
- `scripts/hermes-busdriver-agent-draft` with preserved Pi/OpenCode schema/scope/result contracts, but every production agent/probe stops immediately after argument parsing—before repository, HOME/state, credential, lock, prompt, gate, run-directory, or worker handling—with `agent_containment_and_credential_broker_unavailable`; executable adapter behavior is exercised only by non-installed test harnesses
- `scripts/hermes-busdriver-agent-balance-plan` read-only planning envelope for one gated mutating draft lane plus parallel read-only review/status lanes
- `scripts/hermes-busdriver-agent-smoke` preserving parser/authority-negative coverage while production Pi/OpenCode smoke dispatch remains policy-blocked by `agent_containment_and_credential_broker_unavailable`; historical real-smoke results are not containment proof
- `scripts/hermes-busdriver-delivery-status` including a top-level `read_only: true` envelope marker, optional `--relay-role` / `--relay-config` resolver evidence, sanitized/normalized/redacted state-dir-aware read-only litmus/pre-PR freshness evidence, and metadata-only relay capability inventory entries for public helpers including agent-balance-plan, agent-smoke, deliver, smoke, finalization-readiness, and finalization-contract-status; litmus evidence fails closed on unavailable/malformed/schema-invalid/repo-mismatched/authority-positive/subprocess-failed helper output
- `scripts/hermes-busdriver-deliver` including nested delivery-status timeout budgeting, durable fail-closed result envelopes whose HMAC writer capability exists only in the writing process, and parser surfaces for `pre-pr-review`, `commit`, `push`, `pr-create`, and `merge`. A lookup outside the writing process cannot establish a valid MAC and returns `run_not_found`, identically to a forgery; unverifiable bytes, disk ownership, and mode are not writer identity. Operation availability is narrower than parser exposure: caller-supplied verifier execution is `policy_blocked` by `verifier_containment_unavailable`; pre-PR review by `isolated_review_runtime_unavailable` before delivery-status, repository/state/lock, artifact, credential, or trusted-writer paths, without synthesizing run identity/timestamp state; `push` by `atomic_push_base_binding_unavailable`; `pr-create` by `atomic_pr_create_binding_unavailable`; and `merge` by `atomic_merge_base_binding_unavailable`. No direct Git/GitHub command may bypass these blockers.
- `scripts/hermes-busdriver-litmus-status`
- `scripts/hermes-busdriver-finalization-readiness` including strict top-level delivery-status child envelope validation (`schema`, `read_only is True`, boolean `ok`) before readiness evidence can be trusted, advisory `hermes-busdriver-pre-pr-dual-review-evidence/v0` classification derived only from sanitized delivery-status litmus summaries, embedded read-only `finalization_contract_status` evidence for downstream consumers, and embedded validated read-only `agent_balance_plan` evidence that remains advisory and non-dispatching
- `scripts/hermes-busdriver-finalization-contract-status` read-only ADR 0005 contract/capability matrix with `deliver-mutating-executor` and `mutating-final-result-envelope` marked `implemented_gated`, while programmatic dual-review, PR-grind fix-loop, and marker interop rows remain policy-blocked, with `contract_adrs` / `related_design_adrs` surfacing ADR 0006 design evidence for programmatic dual-review and Busdriver marker interop
- `scripts/hermes-busdriver-relay-brief` compact read-only status/roadmap helper for Telegram-friendly local summaries, installed-skill drift detection, finalization contract status, and next-safe-slice guidance while keeping all authority flags false
- `scripts/hermes-busdriver-pr-grind-check`
- `scripts/hermes-busdriver-pr-grind-loop`
- `scripts/hermes-busdriver-smoke` including finalization-readiness smoke summaries that expose compact embedded `finalization_contract_status` schema/policy/summary/authority evidence
- `tests/contract/test_status_probe.py`
- `tests/contract/test_relay_role.py`
- `tests/contract/test_lock.py`
- `tests/contract/test_runtime_check.py`
- `tests/contract/test_gate.py`
- `tests/contract/test_agent_draft.py`
- `tests/contract/test_agent_smoke.py`
- `tests/contract/test_delivery_status.py`
- `tests/contract/test_deliver.py`
- `tests/contract/test_litmus_status.py`
- `tests/contract/test_required_checks.py`
- `tests/contract/test_trusted_runtime_manifest.py`
- `tests/contract/test_trusted_root_owned_execution.py`
- `tests/contract/test_git_observation_sandbox.py`
- `tests/contract/test_production_dispatch_surface.py`
- `tests/contract/test_finalization_readiness.py`
- `tests/contract/test_relay_brief.py`
- `tests/contract/test_pr_grind_check.py`
- `tests/contract/test_pr_grind_loop.py`
- `docs/hermes-busdriver-integration-contract-v2.md`
- `docs/settling-checks-v1.md`
- `docs/settling-checks-v2.md`
- ADRs and README boundary docs, including ADR 0005/0008 gated finalization authority boundaries

## Verification commands

```bash
cd <relay-repo>
uvx --from pytest pytest tests/contract -q -p no:cacheprovider
scripts/hermes-busdriver-smoke \
  --plugin-root ~/.claude/plugins/marketplaces/busdriver \
  --pretty
```

`hermes-busdriver-smoke` runs its contract check as `sys.executable -I -m pytest` — the active interpreter only. There is no PATH or `uvx` fallback: a `pytest`/`uvx` resolved from the caller's PATH is attacker-choosable, so when the active interpreter cannot import pytest the check fails closed with `error: "pytest_unavailable"` and returncode `127`, making overall smoke exit nonzero. Run smoke from an interpreter that has pytest installed; the `uvx` line above is for invoking the suite directly, not something smoke falls back to.

## Historical superseded evidence

Latest completed historical exact source validation is the v16-r9 run: `1895 passed in 282.20s (0:04:42)` from `/Volumes/Work/.hermes-runtime/v16-r9-evidence/full-pytest-final.log`, SHA-256 `8e68d7b8443117de4236398511a541541fe0bd78c6f3652b6dee1d021eadd8b1` with a verified adjacent sidecar. It is retained for provenance and is not evidence for the current candidate. Production agent-draft/Pi/OpenCode help rendered `policy_blocked`, `agent_containment_and_credential_broker_unavailable`, and production exited nonzero without dispatch. Delivery help enumerated its fixed verify/pre-PR/push/PR-create/merge blockers and stated that status authentication was process-scoped, with cross-process lookup returning `run_not_found` because unverifiable bytes cannot prove writer identity.

Exact r4 review remains `BLOCKED / INCOMPLETE`, not `CLEAN`. Exact r5 review is formally `BLOCKED` at 3 High + 2 Medium. Exact r6 review is formally `BLOCKED` at 1 High + 4 Medium. Exact r7 boundary `b2111df46a3b227bbe73243cc54b591ff4151460d14569c065941eb46324b25e` is `BLOCKED / INCOMPLETE`: two lanes were provider-filtered and the docs lane hit its tool cap before END/report/sidecar after confirming 1 High + 2 Medium + 1 Low. The r8 repair line closed all 33 independently supplied semantic mutants while preserving 10/10 clean controls and 27/27 active clean documents. Exact r9 boundary `e6847ed4e61ceeb2d967309c88d2d46dca8d8506550d954dfd2f5a0c38c4ab6a` completed all three START/END-closed lanes: private-runtime was CLEAN at C0/H0/M0/L0, tests/docs was CLEAN at C0/H0/M0/L2, and correctness was formally BLOCKED at C0/H0/M1/L0 because artifact validation did not yet enforce an operation-specific `(ok, status, reason)` outcome contract. The current repair line adds that exact fail-closed outcome contract and the complete auth-shape regression matrix; it is not frozen and still requires a fresh exact boundary plus three complete independent reviews.

Historical pre-containment smoke evidence (retained for provenance, superseded as production dispatch proof) with installed Busdriver marketplace plugin `1.91.0`:

```text
python3 scripts/hermes-busdriver-smoke --plugin-root <busdriver>: ok=true; 710 contract tests passed; compile/status/runtime/finalization-readiness checks passed
python3 scripts/hermes-busdriver-agent-smoke --plugin-root <busdriver> --agent pi --timeout 240 --pretty: ok=true; only src/pi_smoke.txt changed; status=needs_busdriver_review; commit/push/PR/merge/deploy=false
python3 scripts/hermes-busdriver-agent-smoke --plugin-root <busdriver> --agent opencode --timeout 300 --pretty: ok=true; only src/opencode_smoke.txt changed; status=needs_busdriver_review; commit/push/PR/merge/deploy=false
python3 -m compileall -q scripts tests/contract: passed
git diff --check: clean
```

## Still intentionally deferred

These are not missing safe relay work; they remain outside the approved executor or require a narrower future contract:

- raw `.claude/*` marker writes by Hermes, marker forging, marker deletion, or marker consumption as authority. Busdriver still owns its trusted writer commands, but the production relay does not invoke them: `pre-pr-review` is `policy_blocked` by `isolated_review_runtime_unavailable` before trusted-writer handling.
- production Pi/OpenCode dispatch until OS-enforced containment plus a parent-held credential broker exist (`agent_containment_and_credential_broker_unavailable`).
- caller-supplied verifier execution until an enforceable containment boundary exists (`verifier_containment_unavailable`).
- the push side effect, until a verified server-side conditional seam can atomically bind the reviewed base SHA; the exposed operation currently returns `atomic_push_base_binding_unavailable` and must not be bypassed with direct Git.
- PR creation until one atomic operation can bind creation to the reviewed post-commit head (`atomic_pr_create_binding_unavailable`).
- autonomous PR-grind fix/push/re-poll without a project-specific gated fix command/agent prompt and fresh litmus/pre-PR evidence for the resulting commit/PR head. The dispatcher has no autonomous `pr-grind-fix-loop` operation; actual fixes must route through gated draft adapters, fresh review evidence, and explicit commit/push/re-poll operations.
- `hermes-busdriver-codex-goal` or draft-agent launcher finalization with commit authority
- `.claude/hermes/jobs` queue
- deploy / release / publish automation
- direct MCP/plugin routing
- any claim that Hermes bare shell execution is Busdriver-gate-safe without the dispatcher’s explicit evidence checks and finalization lock

## Operational rule

Hermes may use this repo for:

1. Busdriver-aware intake and route recognition;
2. Phase 0 status discovery;
3. read-only route/gate/marker/lock reporting;
4. inspect preflight/postflight evidence and non-installed adapter fixtures without launching production draft agents: Pi remains the preferred route metadata and OpenCode the fallback/comparison route, but both are non-programmatic with `agent_containment_and_credential_broker_unavailable`;
5. generating read-only finalization readiness / handoff envelopes for Busdriver/Claude or explicit operator finalization;
6. warning the user when the next step still needs Busdriver/Claude or a stronger finalization gate;
7. maintaining read-only/status relay envelopes plus the gated Delivery Mode executor while leaving programmatic dual-review, raw marker interop/writes, autonomous PR-grind fix loops, and deploy/release/publish blocked.

Hermes must not use this repo to bypass Busdriver gates or duplicate Busdriver's source-of-truth.

If the user explicitly asks Hermes to complete the whole delivery, Hermes must use litmus/pre-PR-equivalent checks before commit/PR and a pr-grind-equivalent loop before any merge: check PR status, wait for reviewer bots with a bounded budget, inspect comments/reviews, fix actionable feedback, and merge only when clean. After merge, sync the PR base branch discovered from PR status rather than hard-coding `main`. GitHub issue/comment mutation remains separate and requires explicit user request for that side effect.
