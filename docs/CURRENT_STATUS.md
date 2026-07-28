# Current Status — Hermes Busdriver Relay

Last verified against the observed installed Busdriver marketplace plugin `1.91.2` used by smoke. The reviewed repository `trusted-runtime-manifest` separately pins Busdriver package version `1.90.0` and commit `835dc1784a7ae5c34a5f8f58d6731a482f64df0a`.

## Current verification

Historical sealed main immediately before PR #157: commit `1dc6bbf4eaa91341ecda31d4e8e2a05f80c5de96`, tree `2b4de738d04283ebf1d945db63bbbf64d2dfdc1f`, with 32-stack authority result `4090 passed, 14 skipped, 1 deselected`. It is retained only as provenance and is not current main/top.

Current main after squash-merged skill-source sync PR #160 and terminal-newline follow-up PR #161 is commit `f3d35f3774e9da878c780be4f55ada873955feca`, tree `76b1cf47023c2fc0e48eece4099670aae67eedb2`; local `main` and `origin/main` are synchronized and clean. PR #160's immutable pre-squash candidate passed `4060 passed, 14 skipped, 1 deselected`, independent exact policy/inventory/content review, and all app-bound PR required checks. Its main-push Tests run `29933434604` succeeded; Security did not trigger because that workflow's main-push path filter excludes the Markdown/JSON-only scope.

A late exact security review then found 13 newly synced Markdown references without terminal LF. PR #161 rolled that finding forward without rewriting #160: each blob changed only by one LF, and a recursive whole-reference-tree regression contract was added. Its focused docs/skill contracts passed `1138 passed`; the full contract lane passed `4061 passed, 14 skipped, 1 deselected` with only the inherited live-runtime OpenCode digest test explicitly deselected. The ordinary local full lane remains environment-blocked at `trusted_executable_integrity_failed:opencode`; the affected runtime source/test blobs were parent-identical and PR CI passed. Independent exact Claude review returned `PASS`; Greptile's nested-reference P2 was fixed and its final review passed; main-push Tests `29937408699` and Security `29937409723` both succeeded.

Live post-merge relay evidence captured before this docs-only refresh branch was opened reported zero open PRs, a clean `220`-file installed/repo skill comparison, no skill reference missing terminal LF, and `idle_clean_partial_policy_blocked_finalization`. All dispatch, mutation, marker-write, and finalization authority remains fail-closed; this status evidence grants no standing side-effect authority.

## Locations

| Component | Path / URL |
|---|---|
| Relay repo | `<relay-repo>` |
| Relay GitHub | `https://github.com/chris-yyau/hermes-busdriver-relay` |
| Busdriver source path read during Phase 0 | `<busdriver-source>` |
| Installed Busdriver marketplace plugin used for smoke | `~/.claude/plugins/marketplaces/busdriver` |
| Hermes skill install path | `~/.hermes/skills/autonomous-ai-agents/busdriver-relay` |

## Completed scope

Relay v1 is complete as a **read-only/status + lock + smoke** integration. Relay v2 retains the **Pi executor adapter contract plus historical OpenCode fixture evidence, with production dispatch blocked**, plus the existing read-only status, planning, PR-grind, litmus, readiness, contract-status, lock, and delivery envelopes. Current routing policy is metadata only: Pi is the sole executor route; Codex is fallback coder metadata and PR lead; OpenCode is non-executor historical/comparison evidence; Cursor is the manual IDE sidecar. Every relay role reports `programmatic_dispatch_allowed=false`, `adapter_verified=false`, and `dispatch_allowed=false` because no production relay-role dispatcher exists. Busdriver/Claude Code remains the sole canonical finalization authority; Hermes is the relay/router/verifier and explicit Delivery Mode operator only.

Implemented:

- `skills/busdriver-relay/SKILL.md`
- `skills/busdriver-relay/references/*.md` including PR-grind delivery discipline, June 2026 reviewer-quality policy, claude-mem push, and user-preference/profile notes
- `config/trusted-runtime-manifest.json`
- `adapters/pi/busdriver-fs-broker.py`
- `adapters/pi/busdriver-tools.ts`
- `scripts/check-required-checks.sh`
- `tests/fixtures/opencode/run-opencode-busdriver-draft` as historical test-only fixture source
- `scripts/hermes-busdriver-status` including optional read-only `--drift-baseline <json>` compatibility reporting, fixed Pi-only implementation routes, Codex fallback/PR-lead metadata, OpenCode rejected from every current relay route, and configurable non-implementation role metadata including the Cursor manual sidecar; every role is non-dispatchable and unverified, with precise blockers and omission degrading fail-closed
- `scripts/hermes-busdriver-relay-role` for read-only fail-closed selection of one configured relay equivalent role
- `scripts/hermes-busdriver-lock` with token-only release, no force bypass, and atomic generation retirement to a non-active tombstone after quarantine-rename revalidation; release performs no recursive pathname deletion, so a non-cooperative replacement is restored or preserved
- `scripts/hermes-busdriver-runtime-check`
- `scripts/hermes-busdriver-gate`
- `scripts/hermes-busdriver-agent-draft` with safe `noop` production default and Pi as the sole executor route; every Pi production probe stops immediately with `agent_containment_and_credential_broker_unavailable`, while parser validation rejects OpenCode
- `scripts/hermes-busdriver-agent-balance-plan` read-only planning envelope selecting Pi as the sole executor route metadata and reporting no agent calls
- `scripts/hermes-busdriver-agent-smoke` requiring the sole explicit Pi parser choice with the fixed production blocker; parser validation rejects OpenCode and historical real-smoke results are not containment proof
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

PR #168's final exact pre-merge candidate completed `4042 passed, 13 skipped`; its affected focused closure completed `1206 passed`. This is candidate evidence, not merged-main provenance. Earlier historical evidence remains PR #160's `4060 passed, 14 skipped, 1 deselected` and PR #161's `4061 passed, 14 skipped, 1 deselected`. Those earlier results predate OpenCode retirement: at that time Pi and OpenCode production drafts were policy-blocked and a live OpenCode digest mismatch remained. Current production instead rejects OpenCode at the parser, retains it only as historical fixture evidence, and has no OpenCode production executable or runtime pin. Pi is now the sole executor route and remains blocked by `agent_containment_and_credential_broker_unavailable`; none of this historical evidence grants runtime authority.

Exact r4 review remains `BLOCKED / INCOMPLETE`, not `CLEAN`. Exact r5 review is formally `BLOCKED` at 3 High + 2 Medium. Exact r6 review is formally `BLOCKED` at 1 High + 4 Medium. Exact r7 boundary `b2111df46a3b227bbe73243cc54b591ff4151460d14569c065941eb46324b25e` is `BLOCKED / INCOMPLETE`: two lanes were provider-filtered and the docs lane hit its tool cap before END/report/sidecar after confirming 1 High + 2 Medium + 1 Low. The r8 repair line closed all 33 independently supplied semantic mutants while preserving 10/10 clean controls and 27/27 active clean documents. Exact r9 boundary `e6847ed4e61ceeb2d967309c88d2d46dca8d8506550d954dfd2f5a0c38c4ab6a` completed all three START/END-closed lanes: private-runtime was CLEAN at C0/H0/M0/L0, tests/docs was CLEAN at C0/H0/M0/L2, and correctness was formally BLOCKED at C0/H0/M1/L0 because artifact validation did not yet enforce an operation-specific `(ok, status, reason)` outcome contract. The r4-r9 review boundaries remain historical and superseded; none may be treated as current authorization or override the fail-closed live evidence above.

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
- production Pi dispatch until OS-enforced containment plus a parent-held credential broker exist (`agent_containment_and_credential_broker_unavailable`); OpenCode is not an executor route.
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
4. inspect preflight/postflight evidence and non-installed adapter fixtures without launching production draft agents: Pi is the sole executor route metadata, Codex is fallback coder metadata and PR lead, and OpenCode is retained only as non-executor historical/comparison evidence;
5. generating read-only finalization readiness / handoff envelopes for Busdriver/Claude or explicit operator finalization;
6. warning the user when the next step still needs Busdriver/Claude or a stronger finalization gate;
7. maintaining read-only/status relay envelopes plus the gated Delivery Mode executor while leaving programmatic dual-review, raw marker interop/writes, autonomous PR-grind fix loops, and deploy/release/publish blocked.

Hermes must not use this repo to bypass Busdriver gates or duplicate Busdriver's source-of-truth.

If the user explicitly asks Hermes to complete the whole delivery, Hermes must use litmus/pre-PR-equivalent checks before commit/PR and a pr-grind-equivalent loop before any merge: check PR status, wait for reviewer bots with a bounded budget, inspect comments/reviews, fix actionable feedback, and merge only when clean. After merge, sync the PR base branch discovered from PR status rather than hard-coding `main`. GitHub issue/comment mutation remains separate and requires explicit user request for that side effect.
