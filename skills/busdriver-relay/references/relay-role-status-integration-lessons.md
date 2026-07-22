# Relay Role Status Integration Lessons

> **CURRENT AUTHORITY-NEGATIVE — NON-PRODUCTION-DISPATCH.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; all relay roles are metadata-only and production dispatch is blocked by `agent_containment_and_credential_broker_unavailable`.

Date: 2026-06-28

Use this when wiring `hermes-busdriver-relay-role` into read-only status or finalization-readiness surfaces.

## Core lesson

A role resolver output is external evidence, not authority. Resolver exit `0` and `ok=true` validate resolved metadata only; they never grant dispatch. Status consumers must revalidate it before labeling optional role evidence as safe. Any `dispatch_allowed=true` claim must be rejected and production dispatch must remain blocked.

## Required validation for resolved metadata

For a requested role such as `relay.pr.backstop`, require all of:

- resolver process exit code is `0`;
- payload is an object;
- `schema == "hermes-busdriver-relay-role/v0"`;
- payload `role` exactly equals the requested role (prevents stale/miswired resolver evidence for a different role);
- root `read_only is true`;
- root `ok is true`;
- root `dispatch_allowed is false`;
- root `mutation_allowed is false`;
- root `finalization_allowed is false`;
- root `not_busdriver_native_claude_runtime is true`;
- nested `decision` is an object;
- nested `decision.dispatch_allowed is false`;
- nested `decision.mutation_allowed is false`;
- nested `decision.finalization_allowed is false`;
- nested `decision.not_busdriver_native_claude_runtime is true`.

Root and nested `decision` `dispatch_allowed=false` are mandatory. Delivery-status keeps the structured result as warning-bearing, non-dispatchable evidence with `relay_role_not_dispatchable`; a true claim is rejected as `relay_role_authority_flags_unsafe`. Never convert role evidence into commit/push/PR/merge/finalization/marker-write authority.

## Contract tests to add when touching this area

Add or keep tests for:

1. resolved metadata-only route -> resolver exit `0`/`ok=true`, root/nested dispatch false, delivery-status warning;
2. empty/degraded route -> warning path and no finalization authority;
3. fake resolver with root or nested `decision` `dispatch_allowed=true` -> must be blocked as unsafe;
4. fake resolver with `mutation_allowed=true` or `finalization_allowed=true` -> must be rejected as unsafe;
5. fake resolver returning a different role than requested -> rejected as unsafe;
6. finalization-readiness handoff includes non-dispatchable warning evidence while `commit_allowed`, `push_allowed`, `pr_allowed`, `merge_allowed`, and `finalization_allowed` remain false.

## PR-grind/reviewer handling

- Reviewer comments on stale commits may stay unresolved even after a fix push. Verify the latest HEAD contains the fix, then resolve the exact review thread as part of explicit PR-grind finalization; do not resolve unaddressed feedback.
- Broken reference links in `skills/busdriver-relay/SKILL.md` are real bugs. If SKILL.md points to a `references/*.md`, create the file in both the repo skill and installed Hermes skill, or remove the pointer.
- After every fix push, rerun latest-head PR-grind; prior clean state is invalid.
