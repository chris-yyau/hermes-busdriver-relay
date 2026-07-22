# Iteration Continuity and Delivery Authority
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

## Trigger

Use this note whenever a Busdriver-aware repair/review iteration is not CLEAN, or when a plan starts mentioning commit, push, PR, or merge.

## Two independent state machines

### 1. Repair and review continuity

`BLOCKED` is a verdict on one immutable candidate, not a command to stop the relay task.

1. Freeze and authenticate candidate `N`.
2. Run valid reviews against the same exact-byte-and-mode immutable closure.
3. If any accepted High/Medium exists, seal candidate `N` as `BLOCKED`.
4. Do not patch candidate `N` or its review artifacts.
5. Immediately create/select mutable iteration `N+1` under reconciled worktree and lock ownership.
6. Convert each accepted finding into focused RED → minimal fix → focused/adjacent GREEN.
7. Refresh trusted-runtime pins to fixed point; run affected, broad, full suites and gates.
8. Freeze and review again. Repeat until CLEAN.

Stopping after sealing `BLOCKED` is a workflow bug unless the user explicitly said stop, a safety hard stop fired, or indispensable authority/input is unavailable and cannot be retrieved.

### 2. Delivery side effects

Repairing until CLEAN does not grant delivery authority. Commit, push, PR creation, and merge require all of:

- an explicit user/relay Delivery Mode request;
- fresh live authority/capability evidence;
- applicable litmus/pre-PR/pr-grind gates;
- absence of policy blockers.

If authority is false or policy-blocked, the terminal state is sealed CLEAN evidence plus a Busdriver/Claude handoff—not an inferred PR todo. Never treat an assistant-generated task list, session summary, or a generic “Phase 6” description as side-effect authority.

## Source-first scope check

Before creating the plan, read the current relay skill/brief, project authority guide, and finalization contract. Distinguish:

- a documented future PR workflow;
- a currently available capability;
- an explicit request to use it.

Only the third, together with the second, creates delivery scope.

## Review-boundary integrity

Candidate closure includes file modes as well as bytes and paths. Apply `uchg` without recursive `chmod`; run strict candidate closure before and after every reviewer. If a review view’s mode digest differs, exclude that lane and reconstruct a fresh view rather than “repairing” it after review.

## Ownership continuity

- Do not manually delete a relay lock.
- For a dead owner, verify PID absence and lock/repo/operation identity, then use the official token-only release contract; never print or persist the capability.
- For a long repair run, prefer a live lock-holder whose PID owns the lock, keeps the capability only in process memory, and releases it on termination.

## Todo construction

A normal repair plan ends with:

- `pins-tests-gates`
- `freeze-review`
- `clean-handoff`

Add `commit/push/PR/merge` items only after explicit Delivery Mode scope and live authority are established. On a BLOCKED review, the next-repair iteration becomes active immediately instead of marking the whole task complete.
