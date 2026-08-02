# Current Status — Hermes Busdriver Relay

Last observed installed Busdriver marketplace plugin: version `1.100.8`, commit `bde3f0ea45c15f7342569ed0a53d9c671173950c`. The reviewed repository `trusted-runtime-manifest` separately pins Busdriver package version `1.90.0` and commit `835dc1784a7ae5c34a5f8f58d6731a482f64df0a`.

## Current verification

Historical sealed main immediately before PR #157: commit `1dc6bbf4eaa91341ecda31d4e8e2a05f80c5de96`, tree `2b4de738d04283ebf1d945db63bbbf64d2dfdc1f`, with 32-stack authority result `4090 passed, 14 skipped, 1 deselected`. It is retained only as provenance and is not current main/top.

The sealed baseline is main commit `f62cd73fd0ba668372e96f6cc18adb3334010a3a`, tree `570268a7e16755091627783ecfd33b3d0f3d6515`, after PR #173 added the locked Cursor candidate lane. The 2026-08-02 promotion attempt for that lane was adjudicated `PROMOTION_BLOCKED_FAIL_CLOSED`; production dispatch stays fail-closed and the lane's hardening is retained as candidate/test-lane groundwork only. The prior chronology point was squash-merged Pi-only policy PR #168 and executor-retirement skill-source PR #169 at commit `0853d513fb2c7fc35b143e0b71d669b788ffe0d6`, tree `1422232f6635c9d60c8f83869dd2e64f5cfdf42e`; local `main` and `origin/main` are synchronized and clean. The observed squash tree exactly matches the tree of PR #169's reviewed head commit `5a8a70182ad88fc256a08fd9d1164ee03fc8c918`. All seven push-to-main checks—Tests, Compliance, Dependency CVEs, Code Security, IaC Misconfig, Actions Security, and Reports—completed successfully.

PR #168 established the current Pi-only executor policy: Pi is the sole implementation route; Codex remains non-dispatchable fallback-coder/PR-lead metadata; OpenCode is parser-rejected and retained only as historical fixture evidence. Its final exact candidate passed `4046 passed, 13 skipped`, its focused policy/runtime/docs/manifest closure passed `1206 passed`, and immutable review returned `PASS — 0 Blocker / 0 Major / 0 Minor`.

PR #169 synchronized the executor-retirement and PR-grind lessons into canonical repository skill source and hardened exact-candidate review against stale bases, ambient Git attributes/filters/fsmonitor, index flags, ignored or untracked state, submodule drift, path-scope omission, binary-patch blind spots, aggregate review bodies, and head changes. Its final frozen diff SHA-256 was `38258382636ea0027833c312a59df522fe7ba84dce23cf8a76a3bd80fd9fd1df`; focused closure passed `1230 passed`, the final full contract suite passed `4125 passed, 13 skipped in 1025.54s`, and immutable review returned `PASS — 0 Blocker / 0 Major / 0 Minor`.

Live post-merge evidence captured before this docs-only refresh branch was opened reported zero open PRs and issues, a clean `223`-file installed/repository skill comparison with no differences, missing files, or extras, and a clean live config with `coding_agent=pi`, Pi primary/secondary routes, and Codex fallback metadata. All dispatch, mutation, marker-write, non-Pi executor enablement, and finalization authority flags are observed false and remain fail-closed; Pi production dispatch remains blocked by `agent_containment_and_credential_broker_unavailable`. Pi/Cursor `cursor/auto` candidate hardening exists — pinned adapter/runtime digests, private-runtime retention, least-privilege credential brokering, and write intent/audit reconciliation — but it is candidate/test-lane groundwork, not production containment or production dispatch capability. Production agent-draft and relay-role dispatch remain blocked until OS-enforced worker and descendant containment plus parent-held write/audit provenance exist; a functional dogfood run is not containment proof. This status evidence grants no standing side-effect authority.

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

PR #168's final exact pre-merge candidate completed `4046 passed, 13 skipped`; its affected focused closure completed `1206 passed`. Earlier historical evidence remains PR #160's `4060 passed, 14 skipped, 1 deselected` and PR #161's `4061 passed, 14 skipped, 1 deselected`. Those earlier results predate OpenCode retirement: at that time Pi and OpenCode production drafts were policy-blocked and a live OpenCode digest mismatch remained. Current production instead rejects OpenCode at the parser, retains it only as historical fixture evidence, and has no OpenCode production executable or runtime pin. Pi is now the sole executor route and remains blocked by `agent_containment_and_credential_broker_unavailable`; none of this historical evidence grants runtime authority.

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
