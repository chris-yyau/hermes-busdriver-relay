# Iterative freeze/review/repair loops
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this for long-lived Busdriver relay work that accumulates several immutable-review rounds and repair candidates.

## Safe continuation checkpoint

1. **Check the active worker before touching source.** If a delegated mutator PID/session is still live, wait for it. Never start a second mutator, test against a moving tree, or infer success from elapsed time.
2. Capture branch, HEAD, index/dirty/untracked/ignored state, lock/marker status, open PRs, and the previous boundary/review closures. Treat missing output as missing evidence, not as success.
3. If a worker ended by timeout/max-turns, its result is **incomplete even when files changed**. Compare the live source against the last immutable boundary, remove only known rebuildable hook/test caches, run the smallest failing tests, then issue a continuation task that preserves the partial work.
4. Never persist or print lock tokens, credentials, authenticated URLs, or raw provider output while reconstructing state.

## Reconcile latest main correctly

Do not infer that the candidate is behind main by comparing SHA strings or seeing a different HEAD.

- Fetch the current base ref, then prove ancestry with `git merge-base --is-ancestor origin/main HEAD` and compute ahead/behind counts.
- If `origin/main` is already an ancestor of the worker HEAD, the branch is reconciled even when HEAD contains additional commits. Do **not** transplant the dirty tree into a fresh `origin/main` worktree; that can omit committed branch changes and create false conflicts.
- Only create a fresh reconciliation worktree when the graph actually diverged or the base is not an ancestor. Preserve the original dirty worktree as recovery evidence until the replacement is byte-verified.
- If an attempted reconciliation is superseded before source mutation, release its lock and remove its clean worktree/branch/runtime immediately.

## Boundary-driven repair attribution

After each review round:

1. Finish every reviewer lane and run its END verifier **before** allowing another source mutation.
2. Use the previous boundary manifest to identify exactly which files changed in the repair round; `git diff HEAD` alone is insufficient when the branch already contains committed cumulative work.
3. Clean only known ignored residues (`.pytest_cache`, bytecode caches, agent hook caches/logs), then require zero unexpected ignored files.
4. Run focused exploit tests first. Once the failed test passes, stop retrying that test and proceed to the broader affected suite.
5. Run the full suite with isolated TMP/PYTHONPYCACHEPREFIX, disabled pytest cache provider, and an isolated Git config where required.
6. Refresh literal/transitive runtime digests **only after source settles**. A later source edit invalidates parent consumer pins and the manifest, even if manifest tests were green one step earlier.
7. Build a new immutable boundary, verify source count/index/dirty/untracked invariants and non-fixture credential scan, then create three independent candidates from that exact boundary.

## Review verdict discipline

- Codex correctness, Claude security, and Gemini long-context must review the same immutable bytes. A CLEAN from one lane does not overrule an **adjudicated reachable** High/Medium from another.
- Treat runner validity, snapshot closure, and finding correctness as separate proofs. Exit `0`, a non-empty report, and END closure make a lane valid; they do not make every factual premise true.
- Before marking a candidate BLOCKED, independently trace the reported production caller, helper defaults/conversions, attacker control, and current reachability. Use the smallest safe production-path probe when type or return-code behavior is disputed. See `references/reviewer-finding-adjudication-and-process-lifecycle.md`.
- If the finding is accepted, END-close all lanes and use one mutating worker for the next repair round. If rejected, record the evidence in the disposition; do not silently discard the valid lane.
- If an immutable BLOCKED disposition was already created before a finding was disproved, preserve it and create a proof-only successor with a regression plus fresh gates/reviews.
- Keep reviewer prompts explicit about the cumulative tree and require an exact current caller/dataflow. Otherwise narrow evidence, stale comments, dormant fixture code, or hypothetical future callsites can be mistaken for a production blocker.
- A reviewer authentication/permission failure is an incomplete lane, not a verdict. Retry only after that failure with the smallest permission adjustment that preserves immutable/read-only review.

## Security-sensitive relay checklist

These patterns repeatedly produce real blockers in agent relays:

- **Digest then execute path is not retention.** Authenticate bytes, copy those exact bytes to a private runtime, re-stat/re-digest, and execute only the retained copy. Include extensions, child wrappers, interpreters, fixed helper executables, and transitive sibling-script edges.
- **Manifest refresh order matters.** Avoid digest cycles; enumerate every consumer; refresh leaves before parents and run no-bypass tests after the final edit.
- **Git is an execution and observation-integrity surface.** Read-only Git calls need an OS-enforced no-child/no-network boundary plus inert config/protocol/submodule/lazy-fetch settings; PATH pinning or a finite config denylist alone is insufficient. A denied filter can still make Git exit `0` with incomplete stdout, so bounded stderr denial evidence must force nonzero and discard stdout. Use the concrete reproduction and full checklist in `references/git-observation-sandbox-lessons.md`.
- **Path containment is end-to-end.** Component-wise `openat`/`O_NOFOLLOW` must include the root anchor and retain enough ancestry descriptors to revalidate the live root/parent chain after the final content hash. Leaf-only no-follow and prechecks are TOCTOU-prone.
- **Final binding must be truly final.** Revalidate descriptor metadata, exact size/content identity, and directory-entry-to-inode binding after hashing/writing; coordinate concurrent append size checks with a lock.
- **Bound before redaction/parsing.** `capture_output=True`, unbounded `communicate()`, `read_text()`, or raw report persistence can exhaust memory or leak secrets before tail/redaction logic runs. Concurrently drain pipes to a hard bound, fail closed on overflow/timeout, and recursively strip capability keys/redact before persistence or stdout.
- **Complete-write loops must reject zero progress.** Every private-copy/write loop must handle short writes and treat `os.write() <= 0` as failure.
- **Fixture authority must be source-separated.** Production CLIs must not expose a `fixture-mode` switch that enables caller-selected helpers; use dedicated test harness entrypoints.

## Delivery transition

Do not move to commit/PR because one broad test run passed. Require, in order:

1. latest-main ancestry proof;
2. full suite and hygiene green on settled bytes;
3. new immutable boundary;
4. all three reviews CLEAN with END closures;
5. frozen final review if the delivery branch/head changes afterward;
6. Busdriver litmus/delivery/finalization gates;
7. commit, push, PR, latest-head PR grind, merge;
8. cleanup and verification of clean main, zero open PRs, no live processes/locks/markers, and no docs/skill drift.
