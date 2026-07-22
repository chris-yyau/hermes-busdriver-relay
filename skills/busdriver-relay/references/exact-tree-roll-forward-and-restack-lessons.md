# Exact-tree roll-forward and stacked-restack lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference when an independently reviewed candidate rolls forward more than once, or when an evidence-only PR shares a branch with the final stacked delivery.

## 1. A stale review can contain a live finding

Tree-bound **PASS/evidence** becomes stale as soon as the target tree changes. A concrete content finding does not automatically disappear.

For every finding from an older target:

1. Identify the affected paths and blobs.
2. Compare those blobs between the reviewed target and the new target.
3. If the relevant content is unchanged, carry the finding forward and remediate it before finalizing.
4. If it changed, re-evaluate the finding against the new bytes; do not dismiss the whole review merely because its target hash is old.
5. Add a regression contract when the finding concerns shipped policy, security guidance, required-check semantics, or another durable invariant.

A useful verdict vocabulary is:

- **stale evidence** — cannot prove the new tree;
- **forward-applicable finding** — still applies because relevant bytes/invariant survived;
- **resolved finding** — changed bytes plus a focused regression prove closure.

## 2. Seal semantic authority separately from incidental metadata

The immutable authority is the exact commit/tree plus tracked bytes and modes. Source-close authority is a semantic CAS over the expected tracked entries, Git controls, and any explicitly protected evidence roots.

- Run tests in a private materialization, not in the exact authority checkout.
- Treat tracked-byte, mode, entry-set, ref, index, object-content, or semantic-tree drift as a blocker.
- Record directory/inode/mtime drift, but do not turn directory mtime alone into a content blocker unless the declared no-mutation contract explicitly makes that metadata authoritative.
- A test runner or traversal can change directory metadata without changing any tracked bytes. Avoid creating this ambiguity by keeping authority checkouts read-only and running probes elsewhere.
- Closing reports must state which layer drifted: bytes/tree, Git controls, object content, or metadata only.

## 3. Carry policy documentation with executable contracts

Security/runtime behavior and shipped operator guidance are one boundary. When production code changes an invariant, update all agent-facing guidance in the same target and add a contract that rejects the unsafe or stale wording.

Examples of invariants worth literal contracts:

- status observations keep submodule/gitlink drift visible (`--ignore-submodules=none`), and shipped guidance must not recommend hiding it;
- required scanners execute on every pull request;
- a skipped required scanner is not passing evidence;
- required checks remain literal `(context, app_id)` rows.

Use RED–GREEN: add the documentation contract first, observe the focused failure, patch the guidance, then run the complete affected contract files.

## 4. Latest-hunk ownership must respect historical replay order

A newly changed path may also appear in historical transition units. Do not assign its latest hunk solely by semantic category.

1. Find the last historical transition for that path in the 32-slice order.
2. Assign the latest hunk to that slice or a later slice.
3. Replay every historical unit with old-state CAS before applying the latest hunk.
4. If the builder reports an old-state mismatch, treat it as an ownership-order defect; move the latest owner later rather than weakening the CAS.
5. Re-run both independent proposal builders, exact three-field proposal comparison, chain construction, caps, and raw scanning.

This preserves temporal preconditions while keeping every old unit and latest hunk exactly once.

## 5. Evidence-branch updates and final atomic leases

An evidence-only top PR may already point at the exact final top commit before the rest of the stack is pushed. That makes a previously recorded `old_head_expected` stale for that one ref, but it is not authorization to accept arbitrary live state.

At final push time:

1. Fresh-read every PR and branch.
2. Require open Draft state, exact head/base branch names, expected repository, protected-base SHA, exact required-check protection, and zero self-hosted runners.
3. For each live head, accept only:
   - the plan's `old_head_expected`, or
   - that entry's exact `new_commit` (idempotent/already updated).
4. Reject every third value.
5. Use the freshly observed allowed SHA in `--force-with-lease`.
6. Send all 32 refspecs in one `git push --atomic`, including already-exact/no-op refs when Git permits it.
7. Re-read all PR heads and require exact convergence before updating bodies or waiting for CI.

The plan proves composition; the fresh lease gate proves rollout authority. Do not mutate the reviewed plan merely to hide an evidence-branch update.

## 6. CI truth must distinguish required execution from expected skips

Do not use `all(workflow_run.conclusion == "success")` over every pull-request workflow. Repositories may legitimately have non-required workflows or jobs that skip on ordinary PRs (for example, Dependabot-only automation or push-only compliance).

Instead:

- require the named core workflow runs (for example Tests and Security) to be `pull_request`, attempt 1, completed/success;
- require each locked check context from the expected app ID to be completed/success;
- inspect actual jobs and require every required job to have executed and succeeded on the trusted runner group;
- verify scanner steps were not skipped or aggregator-masked;
- list non-required skipped runs/jobs explicitly as expected, never as passing evidence;
- require the security aggregator/report only in addition to, never instead of, the scanner jobs;
- re-check branch protection and repository runners in the same closing collection.

If a collector fails only because it treated an expected non-required skip as failure, fix the predicate and perform a fresh direct collection; do not rerun already-successful CI merely to satisfy an incorrect collector.

## 7. Land an exact linear stack with one CAS, not per-PR merge machinery

When the reviewed top is already a strict linear descendant of the protected base and every stacked head is one commit in that exact chain, prefer one native fast-forward over synthesizing 32 merge commits, repeatedly restacking, or temporarily changing repository merge settings.

### Preconditions before any mutation

- Refuse optimized execution; security checks must not depend on removable `assert` statements.
- Require the exact ordered PR/head/ref set, unique entries, first parent equal to the sealed base, every next parent equal to the previous exact head, and last head equal to the sealed top.
- Verify remote commit parents/trees and independently run local `merge-base --is-ancestor`, exact `rev-list --reverse`, and top-tree checks from sealed object stores.
- Require immutable exact-head CI/review/grind authority and a fresh live main equal to the sealed base (or the exact top only for a recovery run).
- Use this path only when repository policy permits the authenticated delivery authority to fast-forward the protected ref; never treat admin bypass as a substitute for missing review or CI.

### Source mutation boundary

- Push only `TOP:main` with `--force-with-lease=main:SEALED_BASE`; the ancestry checks make this a true fast-forward even though the lease option can technically authorize non-fast-forward updates.
- Isolate Git in a scratch bare directory with root-owned executable, allowlisted environment, empty HOME/XDG config, `GIT_CONFIG_NOSYSTEM=1`, disabled hooks/credential helpers/proxies, fixed HTTPS destination, and process-local authentication.
- On timeout or any transport ambiguity, terminate the whole push process group and perform bounded stable observation. Do not mutate PR metadata until main has remained the exact top continuously for the declared stability window.
- If main is neither sealed base nor exact top, stop as UNKNOWN; never attempt compensating ref writes.

### Monotonic PR reconciliation and recovery

After main is the exact top, retarget still-open stacked PRs to `main` and let GitHub's reachable-head semantics mark them merged. Re-read after applied-but-error responses. Accept a merged PR only when its live base is `main`, its head is the exact planned SHA, and the exact head is in the sealed chain. Metadata reconciliation is monotonic: do not roll source refs backward.

A rerun must accept `main == TOP`, skip the source push, and resume from live PR state. This is essential when an API timeout occurs after the source ref landed.

### SUCCESS sealing

Cleanup comes before PASS. Remove scratch, verify it is absent, then fresh-read main/tree and the exact unique PR set. Persist `pass: true` only by atomic replace after all live invariants hold. Keep one runnable negative probe proving optimized/non-isolated execution fails before mutation and malicious global hooks or URL rewrites cannot affect the Git boundary.
