# ADR 0005 — Finalization Authority Integration Contract

## Status

Accepted as a non-mutating integration contract and prerequisite checklist. This ADR does **not** grant finalization authority, add an executor, approve marker writes, or change the current read-only relay surface.

## Context

The relay currently provides Busdriver-aware discovery, status, draft gating, verify-only delivery runs, read-only PR-grind checks/loops, read-only litmus/pre-PR marker freshness checks, and a finalization-readiness handoff envelope. Those helpers intentionally keep all commit/push/PR/merge/deploy/publish/marker-write authority flags false.

Hermes Delivery Mode is currently an external operator procedure: when the user explicitly asks Hermes to finish delivery, the operator may perform ordinary Git/GitHub actions only after litmus/pre-PR-equivalent checks, local verification, latest-head PR checks/reviews/comments, bounded reviewer-bot waits, actionable fix rounds, and a clean PR-grind-equivalent result. That procedure is not a relay executor API and does not authorize draft launchers or status helpers to mutate repositories.

`hermes-busdriver-finalization-readiness` exposes `finalization_guardrails.remaining_work` for deliberately missing mutating capabilities:

- `deliver-mutating-executor`;
- `mutating-final-result-envelope`;
- `programmatic-litmus-pre-pr-dual-review`;
- `mutating-pr-grind-fix-push-loop`;
- `busdriver-marker-interop`.

Before any of those can move from policy-blocked to implementable, Busdriver must define and approve an integration surface that Hermes can verify fail-closed.

## Decision

Define a future **Busdriver-approved finalization authority contract**. Until an implementation proves this contract with tests, schemas, and live-source evidence, the relay remains read-only/non-mutating for finalization:

```json
{
  "finalization_allowed": false,
  "commit_allowed": false,
  "push_allowed": false,
  "pr_allowed": false,
  "merge_allowed": false,
  "deploy_allowed": false,
  "release_allowed": false,
  "publish_allowed": false,
  "marker_write_allowed": false
}
```

A future mutating finalization surface must be built around explicit, versioned authority evidence. It must never infer authority from marker filename presence, an agent self-report, a clean local test run, a stale README/ADR, or the mere availability of `git`, `gh`, Busdriver scripts, Codex, Claude Code, MCP tools, or relay role config.

## Authority Sources

A mutating finalization action may be considered only when all applicable authority sources are present and current:

1. **User intent:** an explicit user request for the exact side effect class, such as commit, push, PR creation, merge, or a specific GitHub comment/issue mutation.
2. **Busdriver source-of-truth approval:** live Busdriver source/config/hook documentation identifies the operation as an approved integration seam for Hermes or for a Busdriver-controlled launcher that Hermes invokes.
3. **Hook/runtime or equivalent proof:** the operation either runs inside the Busdriver/Claude hook runtime, invokes approved equivalent gates with matching semantics, or is refused.
4. **Fresh repo/PR evidence:** current repo root, branch/worktree identity, HEAD SHA, diff hash, dirty-state policy, PR number, PR head SHA, mergeability, required checks, reviews, comments, and base branch are known and match the intended operation.
5. **Fresh gate/review evidence:** litmus/pre-commit/pre-PR/dual-review/PR-grind evidence is tied to the current HEAD/diff/PR head and satisfies Busdriver freshness semantics.
6. **Concurrency authority:** a Hermes-owned single-flight lock for the repo/worktree/operation is acquired, active, and released/recorded correctly.
7. **Data-boundary authority:** data egress for verifiers, reviewers, external agents, summaries, and logs is classified and allowed by user intent plus Busdriver/relay policy.
8. **Schema authority:** the executor and all nested evidence use versioned schemas accepted by the relay contract tests.

Relay-owned role configuration may select advisory Hermes/model equivalents for status or review readiness. It is not Busdriver-native authority unless Busdriver explicitly approves that role mapping for the relevant gate.

## Required Unlock Criteria by Surface

### 1. Mutating commit/push/PR/merge executor and envelope

Before `hermes-busdriver-deliver` or a successor can expose mutating `commit`, `push`, `pr_create`, or `merge` operations, the implementation must provide:

- a versioned mutating run envelope distinct from the current verify/read-only `hermes-busdriver-delivery-run/v0` evidence;
- per-operation authority flags and denial reasons, defaulting false/missing-deny;
- current Busdriver seam approval and hook-runtime/equivalent-gate proof;
- preflight evidence for repo identity, clean/allowed dirty state, scope, freeze/careful/gateguard state, branch policy, and active lock;
- fresh litmus/pre-commit evidence before commit and fresh pre-PR dual-review evidence before PR creation;
- local verifier evidence with redacted command/output tails and explicit pass/fail status;
- exact Git/GitHub side-effect transcript: command class, sanitized args, before/after HEAD, commit SHA, push ref, PR URL/number, merge SHA/base branch as applicable;
- latest-head PR checks/reviews/comments evidence before merge;
- postflight reconciliation proving the executor result matches git/GitHub state;
- contract tests for dirty tree fail-closed, stale marker rejection, failed checks, review comments, head drift, lock conflict, schema invalidity, and missing Busdriver approval.

A clean status or successful verifier alone cannot unlock this surface.

### 2. Mutating PR-grind fix/push/re-poll loop

Before the read-only PR-grind loop can become a fix/push/re-poll loop, the implementation must provide:

- a Busdriver-approved PR-grind integration seam or hook-runtime proof;
- latest PR head SHA tracking for every poll, fix, push, and re-poll;
- bounded wait, poll, and fix-round budgets with visible stop reasons;
- actionable-comment/review classification tied to changed lines/current PR head;
- required-check/relevant-check evidence using live Busdriver semantics when available;
- explicit handoff to a gated draft/fix executor that cannot bypass scope, litmus, or verifier requirements;
- push evidence and post-push re-poll evidence for the new PR head;
- fail-closed behavior on mergeability unknown, stale reviews, unresolved actionable comments, check ambiguity, policy gaps, max-wait/max-fix exhaustion, or PR head drift that cannot be reconciled.

The loop must not merge merely because no comments are found or because advisory bots are still pending beyond budget; it must produce a blocked/wait handoff instead.

### 3. Programmatic litmus/pre-PR dual-review execution

Before Hermes can programmatically execute litmus/pre-PR dual reviews, the implementation must provide:

- Busdriver-approved reviewer role mappings for `relay.litmus.reviewer`, `relay.pr.lead`, and `relay.pr.backstop`, or a Busdriver-native reviewer invocation seam;
- independence/conflict rules for dual reviewers, including whether the same model/provider/session may satisfy more than one role;
- prompt/data egress policy, redaction rules, and artifact retention rules;
- reviewer input schema tied to current HEAD/diff/PR head and allowed file scope;
- reviewer output schema with verdict, blocking findings, confidence/limitations, evidence references, and no raw secret leakage;
- aggregation semantics that distinguish pass, actionable findings, unavailable, stale, malformed, and policy-blocked results;
- proof that programmatic reviews cannot write Busdriver markers directly unless marker interop is separately approved.

Configured relay roles remain readiness evidence only until these criteria are satisfied.

### 4. Marker interop and marker writes

Before Hermes can write, update, consume, delete, or otherwise interoperate with Busdriver markers, Busdriver must define a safe marker integration surface. The surface must specify:

- marker ownership and writer identity;
- allowed marker paths under the Busdriver state dir and path/symlink safety rules;
- exact schemas, required fields, size limits, timestamps, repo/worktree/branch/HEAD/diff/PR-head binding, and freshness windows;
- atomic write/rename/fsync requirements and collision/concurrency behavior;
- whether markers are single-use, append-only, replaceable, or consumable;
- how marker writes are audited and how forged/stale/foreign markers are detected;
- which Busdriver gates may trust Hermes-authored markers and under what conditions.

Until then, Hermes may only report normalized/redacted marker status and must never forge marker files to satisfy Busdriver gates.

## Fail-Closed Conditions

Future finalization authority must fail closed if any required authority source is missing, stale, malformed, unreadable, contradictory, or positive without provenance. It must also fail closed on:

- unresolved Busdriver plugin root, hook manifest, user config, gate script, or drift-baseline incompatibility;
- missing hook-runtime/equivalent-gate proof for the requested mutating action;
- repo identity mismatch, dirty tree ambiguity, active merge/rebase/cherry-pick state, or scope/freeze conflict;
- marker/review evidence that is stale, foreign, oversized, symlinked, schema-invalid, or tied to a different HEAD/diff/PR head;
- PR head drift, mergeability unknown, failing/pending required checks, unresolved actionable reviews/comments, or unavailable relevant-check semantics;
- active same-repo finalization lock or inconsistent lock ownership;
- verifier failure, missing verifier evidence, or postflight mismatch between claimed and actual git/GitHub state;
- missing explicit user approval for the exact external side effect;
- unclear data egress, sensitive payload risk, or raw reviewer/model output that cannot be safely persisted;
- any request to deploy, release, publish, bypass gates, use raw repo-mutating Codex execution, or enable non-Codex mutating adapters without a separate approved contract.

## Schemas and Evidence Required

A future implementation must introduce contract-tested schemas before any mutating path is enabled. At minimum:

- `hermes-busdriver-finalization-authority/v0`: authority decision, requested operation, source approvals, operation flags, denial reasons, and freshness timestamps;
- `hermes-busdriver-mutating-delivery-run/v0`: durable executor run envelope with authority evidence, lock evidence, preflight/postflight state, side-effect transcript, verifier evidence, artifact references, and redaction metadata;
- `hermes-busdriver-pr-grind-mutation-loop/v0`: latest-head polling/fix/push/re-poll evidence, budgets, comments/reviews/checks summaries, and loop stop reason;
- `hermes-busdriver-dual-review-execution/v0`: reviewer role mapping, input digest, verdicts, findings, aggregation decision, data-egress classification, and artifact references;
- `hermes-busdriver-marker-interop/v0`: only if Busdriver approves marker writes, with marker schemas/provenance/atomicity/audit fields.

All schemas must be machine-readable, include `schema`, `version`, `ok`/`status`, and default-deny authority fields, and be covered by fixtures that prove malformed or authority-positive nested evidence is rejected.

## Data Egress, Reviewer Ownership, and Marker Ownership

Busdriver owns Busdriver gates, marker semantics, native reviewer routing, and any trust decision that allows markers or reviews to satisfy Busdriver gates. Hermes owns only relay artifacts under `~/.hermes/busdriver-relay/`, sanitized summaries, locks, and notification/status envelopes.

A future finalization path must minimize data egress and record who/what received code, diffs, prompts, review payloads, verifier output, and summaries. Secrets, credentials, PII, customer data, production incident data, and proprietary unreleased context must be redacted or blocked unless the user and Busdriver policy explicitly allow that route.

Review artifacts must identify the reviewer role, invocation seam, model/tool/provider class where safe to record, input digest, output digest, and retention location. Marker artifacts must identify the Busdriver-approved writer and must never be created solely from Hermes inference.

## Non-Goals

This ADR does not approve or implement:

- raw repo-mutating `codex exec`;
- marker forging or marker writes by filename convention;
- deploy, release, publish, package, cloud, database, payment, or production mutations;
- direct MCP/plugin graph replication inside Hermes;
- non-Codex mutating adapter enablement;
- bypassing Busdriver hooks, `--no-verify`, force-push/unsafe git flows, or GitHub auto-merge as a PR-grind substitute;
- changes to Busdriver source, Claude plugins, `.claude/` runtime state, or user credentials.

## Retiring `finalization_guardrails.remaining_work`

Each remaining-work item may be retired only by a later, explicit implementation slice that satisfies this ADR for that item and updates tests/docs in the same change:

- `deliver-mutating-executor`: retire only after a Busdriver-approved mutating executor exists with authority, lock, preflight, side-effect transcript, postflight, and fail-closed contract tests.
- `mutating-final-result-envelope`: retire only after the mutating delivery run schema is versioned, durable, redacted, and rejected on malformed or authority-positive nested evidence.
- `programmatic-litmus-pre-pr-dual-review`: retire only after Busdriver-approved role mappings/invocation seams, independence rules, data-egress controls, review schemas, and aggregation tests exist.
- `mutating-pr-grind-fix-push-loop`: retire only after fix/push/re-poll integration proves latest-head tracking, bounded budgets, actionable feedback handling, required-check semantics, and post-push reconciliation.
- `busdriver-marker-interop`: retire only after Busdriver defines marker write ownership, schemas, atomicity, audit, freshness, and trust semantics, and Hermes implements only that approved surface.

Retiring any one item does not imply the others are approved. Until the relevant item is retired, `hermes-busdriver-finalization-readiness` must continue to expose it as remaining work and all finalization/marker-write flags must remain false.

## Consequences

This ADR gives future work a concrete unlock contract while preserving the current safe state. The next safe dogfood work remains documentation, status, fixtures, and fail-closed evidence. Mutating finalization must wait for a separate approved implementation slice with Busdriver authority and contract tests.
