# Relay Role Status Integration Lessons

Date: 2026-06-28

Use this when wiring `hermes-busdriver-relay-role` into read-only status or finalization-readiness surfaces.

## Core lesson

A role resolver output is external evidence, not authority. Status consumers must revalidate it before labeling optional role evidence as OK. Do not trust `returncode == 0`, `ok=true`, or `dispatch_allowed=true` by themselves.

## Required validation before `relay_role_resolution.ok=true`

For a requested role such as `relay.pr.backstop`, require all of:

- resolver process exit code is `0`;
- payload is an object;
- `schema == "hermes-busdriver-relay-role/v0"`;
- payload `role` exactly equals the requested role (prevents stale/miswired resolver evidence for a different role);
- root `read_only is true`;
- root `ok is true`;
- root `dispatch_allowed is true`;
- root `mutation_allowed is false`;
- root `finalization_allowed is false`;
- root `not_busdriver_native_claude_runtime is true`;
- nested `decision` is an object;
- nested `decision.dispatch_allowed is true`;
- nested `decision.mutation_allowed is false`;
- nested `decision.finalization_allowed is false`;
- nested `decision.not_busdriver_native_claude_runtime is true`.

If any check fails, keep structured evidence but set `ok=false` and report a warning such as `relay_role_not_dispatchable` or `relay_role_resolver_unavailable`. Never convert role evidence into commit/push/PR/merge/finalization/marker-write authority.

## Contract tests to add when touching this area

Add or keep tests for:

1. dispatchable route -> evidence `ok=true`, dispatch allowed, mutation/finalization false;
2. empty/degraded route -> warning path and no finalization authority;
3. fake resolver returning authority-positive fields (`mutation_allowed=true` or `finalization_allowed=true`) -> rejected as unsafe;
4. fake resolver returning a different role than requested -> rejected as unsafe;
5. finalization-readiness handoff includes both dispatchable evidence and non-dispatchable warning evidence while `commit_allowed`, `push_allowed`, `pr_allowed`, `merge_allowed`, and `finalization_allowed` remain false.

## PR-grind/reviewer handling

- Reviewer comments on stale commits may stay unresolved even after a fix push. Verify the latest HEAD contains the fix, then resolve the exact review thread as part of explicit PR-grind finalization; do not resolve unaddressed feedback.
- Broken reference links in `skills/busdriver-relay/SKILL.md` are real bugs. If SKILL.md points to a `references/*.md`, create the file in both the repo skill and installed Hermes skill, or remove the pointer.
- After every fix push, rerun latest-head PR-grind; prior clean state is invalid.
