# Progressive bootstrap and stacked PR-grind lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference when a relay is building capabilities that it cannot yet execute itself, or when a long-running dirty worktree has grown too large for one PR/review closure.

## 1. Avoid the target-architecture deadlock

A configured route is not the same as an executable capability. A role may resolve to Pi/OpenCode while production dispatch still fails closed. Do not make either mistake:

- treating the final target architecture as if every capability already exists, which deadlocks all progress;
- silently bypassing the target architecture forever, which prevents dogfood and cutover.

Use a progressive bootstrap ladder:

```text
capability absent or explicitly blocked
→ Hermes/Codex bootstrap implementation for that capability only
→ focused RED → minimal implementation → GREEN
→ independent reviewers (the implementer is not the sole reviewer)
→ tests, gates, immutable closure
→ ship with the previous trusted delivery path
→ dogfood the new relay-native capability in iteration N+1
→ retire the corresponding Hermes/Codex fallback
```

The fallback record must name:

- the missing/blocked capability;
- why the configured native lane could not execute;
- the exact scope temporarily delegated to Hermes/Codex;
- the independent reviewers;
- the retirement condition.

Do not let a fallback become the undocumented permanent path merely because it is convenient.

## 2. N+1 cutover rule

A capability built in iteration N should normally be shipped and independently verified with the previous trusted path. Make it mandatory in iteration N+1. This avoids a new component implementing, authenticating, reviewing, and approving itself in one closure.

If N+1 dogfood fails:

1. preserve the failure evidence;
2. classify the native capability as `temporarily_blocked` rather than pretending it is authoritative;
3. use the fallback only for the blocked slice;
4. repair and retry the native path;
5. retire the fallback after the first verified real dogfood success.

Useful capability states:

```text
absent
bootstrap_fallback
candidate
shadow_verified
relay_native
authoritative
temporarily_blocked
```

## 3. Delivery questions require direct facts first

When the user asks or challenges whether work was delivered, answer the remote-delivery facts before policy discussion:

```text
PR count / PR URL
commit count / latest commit
push status
merge status
clean-main verification
```

Do not conflate any of the following with an actual PR:

- editing PR-grind tooling;
- running PR contract tests;
- creating a `deliver` todo;
- acquiring a finalization lock;
- building immutable review artifacts.

If the answer is zero PRs, say so immediately and own the delivery gap. Then explain blockers and next action. Do not reinterpret an irritated delivery question as an abstract policy question.

## 4. Do not accumulate an unbounded local-only worktree

Long-running relay work needs delivery-pressure checkpoints. Before WIP becomes unreviewable:

- report the exact dirty-entry and changed-line counts;
- distinguish committed branch delta from uncommitted working-tree delta;
- compare the complete candidate to the intended PR base, not only to `HEAD`;
- request explicit Delivery Mode before GitHub side effects;
- open bounded Draft/stacked PRs or create a verified rescue snapshot while awaiting authority.

A review `BLOCKED` seals one candidate but does not justify weeks of additional uncommitted accumulation. Roll to the next repair iteration while preserving reviewability and remote visibility.

## 5. Measure the real PR delta

For decomposition, gather all three scopes:

```text
git diff --shortstat origin/main..HEAD   # committed branch delta
git diff --shortstat origin/main        # working tree versus PR base
git status --porcelain=v1               # staged/unstaged/untracked inventory
```

A session exposed the risk clearly:

```text
committed branch delta: 31 files, +5,530/-213 across 8 commits
working tree vs main:   152 tracked files, +41,181/-2,491
status inventory:       180 entries
```

The smaller committed statistic would have badly understated the actual PR-grind closure.

## 6. Rescue before splitting

Do not reorganize a large dirty worktree in place. First build a lossless owner-only rescue under the runtime artifact root:

1. save `git diff --binary HEAD`;
2. save a NUL-delimited `git ls-files --others --exclude-standard` inventory;
3. clone the committed repository into the rescue root;
4. apply the tracked binary patch there;
5. copy only inventoried untracked paths;
6. create a local rescue commit that is never pushed;
7. create a Git bundle and SHA-256 sidecars;
8. compare path sets and content hashes against the source worktree.

Keep the original worktree read-only throughout decomposition. Never include credentials, private gate material, markers, caches, logs, or review runtime artifacts in the rescue commit.

## 7. Build a path/hunk ownership manifest

Every retained path and every mixed-purpose hunk must have exactly one capability owner, test pairing, dependency list, and proposed stack base. Fail the split if a path/hunk is unowned or assigned twice.

Typical capability groups include:

- lock/gate/trusted-runtime primitives;
- agent draft, adapters, and fs broker;
- delivery status, litmus, and finalization readiness;
- delivery executor and durable run envelope;
- PR-grind check/loop and authenticated helpers;
- relay status/brief/role/smoke;
- ADR/docs/skill sync.

Split mixed production files by coherent hunks rather than assigning the entire file to whichever slice is easiest.

## 8. PR-grind review budgets

Starting defaults for a security-sensitive relay PR delta against its immediate stack base:

```text
one capability
≤ 15 production files
≤ 25 total non-doc files
≤ 2,500 production changed lines
≤ 4,000 total changed lines including tests
```

A docs/skill-only PR may exceed the file-count limit when it remains under roughly 1,000 changed lines and contains no production behavior. Treat these as reviewability defaults, not universal laws: exceptions require an explicit rationale before review. If a slice exceeds its budget, split it before opening the PR.

## 9. Stacked PR semantics

Use the previous stack branch as each child PR's base so PR-grind sees only the intended slice. The PR body must name the parent PR/base branch and include slice-local evidence.

After a parent merges:

1. rebase or retarget the child;
2. confirm the child did not absorb parent content;
3. rerun affected tests and gates;
4. invalidate old immutable/latest-head review evidence;
5. rerun PR-grind against the new exact head/base pair.

Never merge a child using stale review evidence from before a parent merge/rebase. Do not delete parent branches until children have been safely retargeted.

## 10. Confusion recovery

If ownership, implementation routing, review iteration, and Delivery Mode become conflated:

1. stop mutations and agent dispatch;
2. release active mutation locks cleanly;
3. verify branch, HEAD, status counts, staging/merge state, active locks, PR list, and sealed artifact checksums;
4. reset inaccurate `in_progress` tasks to pending;
5. present one concise source-of-truth state;
6. choose one active phase and one mutation owner before resuming.

This is a workflow recovery, not permission to discard or reset dirty WIP.
