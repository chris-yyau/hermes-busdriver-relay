# Read-only exact merge-executor review

Use this reference for scripts that fast-forward a protected branch and then reconcile stacked pull requests. The review must remain independent and non-mutating.

## Review protocol

1. **Bind the target.** Record SHA-256, size, and mtime before inspection; re-hash before the verdict. Probe artifacts count only when their embedded script hash matches.
2. **Never run the entry point.** It may push refs, mutate PR metadata, or write authority files. For Python, use trusted `python -I -B` with `ast.parse()`; do not use `py_compile` because it can create bytecode. If behavior needs a dynamic check, extract only the function under test and mock every external effect in memory.
3. **Inventory every mutation.** Structurally enumerate non-GET API methods, git pushes, file replacements, subprocesses, and cleanup calls. Confirm removed mutation mechanisms are absent and that the claimed replacement is the sole PR mutation surface.
4. **Prove control-flow dominance.** The safety gate must lie on the common path for fresh push and exact-tip resume, before the first PR mutation. A timer that resets on any wrong or unreadable observation establishes continuous stability; a cumulative counter does not.
5. **Probe mutation-boundary races.** Separate:
   - preflight read,
   - final live read at the mutation boundary,
   - mutation call,
   - response-lost reconciliation read.

   A cached preflight head SHA is not a live boundary guard. Inject head/main drift after preflight but before the mutation call. The required result is zero mutation. A post-mutation assertion can detect damage but cannot satisfy a zero-mutation guarantee.
6. **Review response-lost semantics.** If a mutation raises after being applied, read back both the protected ref and exact PR head and converge only when the intended state is visible. If it was not applied, re-raise; do not retry blindly and risk duplicate or broadened mutation.
7. **Review process-group shutdown.** Require a new session/process group, TERM to the group, bounded wait/reap of the leader, KILL only on timeout, then a bounded absence check for descendants. Evidence should cover both normal leader exit with a descendant and a TERM-resistant timeout; record the timeout return code.
8. **Keep the review read-only.** Prefer in-memory checks. Track reviewer-created scratch separately from the target's runtime scratch and remove only reviewer scratch when cleanup was explicitly authorized.

## Evidence contract

A `pass: true` JSON is supporting evidence, not proof by itself. It should include:

- schema/version;
- exact script SHA-256;
- scenario names and mutation counts;
- state after response-lost reconciliation;
- descendant/group absence and timeout return code;
- enough detail to show *when* drift was injected.

Reject a probe that says only `bad_head: mutation_count=0` when it does not distinguish initial bad state from drift at the final mutation boundary.

## Concrete lesson from the reviewed executor

The reviewed script hash was `fe74594a6ec410c6e2210ed676b6f93a98823315747963a061c5d5860e5060b1`. It removed GraphQL/`mark_ready`, had one PR `PATCH`, placed the 120-second exact-tip gate on the common push/resume path, and had hash-matched process-group evidence.

It still failed the live-binding claim: the function read and validated the PR head during preflight, later revalidated only the protected branch at the PATCH boundary, then issued PATCH. A head change in that gap still caused one mutation; the later read merely detected it. The minimal closure is a fresh boundary `pull()` with exact-head validation immediately before PATCH, plus a probe that injects drift specifically between the first pull and PATCH.

## Verdict style

Return `PASS` only if every named blocker is closed. Otherwise return one precise blocker: file/line, failing interleaving or branch, why existing evidence misses it, and the smallest guard plus probe that closes it. Do not re-review unrelated sections already accepted and unchanged.
