# Immutable review repair and complete-suite closure

Use this when a large dirty relay candidate must survive repeated security reviews, long test runs, and cross-cutting runtime hardening without losing evidence.

## 1. Treat worker claims as leads, not evidence

A coding worker may report tests that ran in a detached child. If the worker/session exits, its child may receive termination before pytest writes a summary. A partial progress stream, exit `-15`, a missing summary, or a process that was explicitly killed is **not a test result**.

Operator closure requires all of:

1. inspect the process table for surviving pytest/worker descendants;
2. read the actual log and require a terminal pytest summary plus exit `0`;
3. independently rerun changed surfaces;
4. never promote a candidate from tracker state or worker prose alone.

Keep long operator-owned test processes outside a model worker's lifecycle. Use tracked background processes with completion notification and preserved logs.

## 2. Partition long suites without weakening “full suite” evidence

When a monolithic suite exceeds the foreground/tool ceiling:

1. Run `pytest --collect-only -q` and preserve the node-id output.
2. Count node IDs by test file.
3. Create deterministic disjoint partitions (greedy by collected count is adequate).
4. Give every partition isolated `TMPDIR`, `PYTHONPYCACHEPREFIX`, and disabled pytest cache.
5. Run every partition to a terminal summary and exit `0`.
6. Verify:
   - union(partition files) equals all collected files;
   - intersection between partitions is empty;
   - summed passed + skipped equals collected node IDs;
   - no failed/error/aborted partition exists.

Report each partition's exact totals and logs, then the arithmetic total. Parallel partitions are acceptable only when tests use isolated runtime state and do not mutate shared source.

## 3. Migrate tests to an explicit hardened subprocess seam

When production moves from `subprocess.run` to a bounded/process-group helper, old tests that monkeypatch `subprocess.run` may fail without exposing a production defect.

Do **not** revert production containment. Instead, add a test adapter around the explicit bounded seam that preserves:

- `text=True` versus byte output;
- `TimeoutExpired` conversion;
- capture limits and overflow behavior;
- `CompletedProcess` return code/stdout/stderr shape;
- process-helper defaults rather than silently dropping `limit`.

Require dedicated contracts for process-group kill, bounded drain, reap, and descendant cleanup so adapter-based unit tests cannot make containment coverage vacuous.

## 4. Freeze active dirty trees into independently verifiable review views

Formal review must never inspect the active mutable worktree.

1. Build a canonical boundary containing HEAD, candidate tree, porcelain records, and every included path's type/mode/size/SHA-256.
2. Pin the canonical boundary hash in a self-contained verifier.
3. At lane START, reconstruct a candidate from the boundary and compare exact inventory/counts/tree.
4. Copy the candidate to a separate review-view and verify it before review.
5. On macOS, apply `uchg` recursively to the review-view when practical; keep reports outside it.
6. After review, run all three closures:
   - live source still matches the boundary;
   - official candidate still matches the boundary;
   - review-view still matches the boundary and immutable flags remain set.
7. Use a fresh lane/output path for every smoke or formal run. Exclusive evidence writers should reject an existing output; that is correct behavior, not a reason to overwrite evidence.

Source-byte changes invalidate every prior lane and require a new boundary/review round.

## 5. Root-owned executable dispatch on macOS

A digest-validated executable copied into a user-writable private directory is still pathname-ABA vulnerable between validation and `exec`. macOS does not provide a generally usable Python `fexecve`, and executing `/dev/fd/N` is not a portable replacement.

For credential-bearing or repo-authority dispatch:

- bind production to a fixed absolute source path;
- validate root-to-leaf ancestry: no symlink surprises, root ownership, and no group/world/user write access for the invoking user;
- open with no-follow semantics and revalidate opening/closing identity, metadata, path binding, and digest;
- execute the validated root-owned path directly, not a mutable copied pathname;
- reject caller/env/PATH source overrides;
- fail closed **before credential-environment construction or forwarding** if the required trusted source is unavailable.

Apple Command Line Tools executables may be SIP-restricted hard-linked multicall shims. In that case:

- path/`argv[0]` is part of executable identity; two tool paths can legitimately share inode and digest;
- a blanket `nlink == 1` rule is wrong for the shim; require trusted immutable ancestry/SIP metadata instead;
- explicitly remove or deny shim redirection variables such as `DEVELOPER_DIR`, `SDKROOT`, `XCODE_DEVELOPER_DIR_PATH`, `TOOLCHAINS`, and `XCRUN_CACHE_PATH` from every dispatch environment;
- do not copy the shim outside its trusted system path.

**Bootstrap ordering is part of the boundary.** If the validator itself runs through an Apple multicall shim (for example `/usr/bin/python3`), removing redirect variables inside Python is too late. Launch that pre-validator from an explicitly constructed minimal environment that contains no credentials or developer-tool redirect variables. Only after the credential-capable executable has passed root-owned ancestry, descriptor/name identity, metadata, and digest checks may a child environment acquire GitHub tokens or other capabilities. Add a dynamic test that plants every redirect variable plus sentinel credentials and proves no attacker shim starts and no sentinel reaches the pre-validator.

Migrate this contract atomically across every consumer and shared manifest pin. A partial migration with shared pins is incoherent.

## 6. Keep coverage non-vacuous during cross-cutting hardening

For each rewritten contract, inject one targeted regression and confirm that the intended test—not an earlier unrelated guard—goes red. Common vacuity traps:

- mutating the dictionary returned by `runpy.run_path` instead of a function's real `__globals__`;
- an ABA test rejected by an earlier path check before descriptor-bound dispatch is reached;
- allowlist intersection checks that only detect already-listed writers while missing new ones;
- stale tests that merely compare a frozen resolver with itself;
- deleting a direct-writer enumeration without proving the wrapper delegates exclusively to a separately covered authenticated primitive.

Restore production byte-identically after each mutation probe and rerun the real contract.

### Shell dispatch contracts must parse command positions, not known names

A regex table that searches only for today's known commands is not a complete dispatch contract. It can miss assignment-prefixed commands, command/process substitutions, pipelines, groups, subshells, wrappers, and arbitrary new tools. Use a conservative command-position scanner that:

- derives shell functions and builtins from syntax and treats every other command head as external;
- handles assignments, redirections, quoting, continuations, control-flow separators, `$()`/process substitutions, groups, and forwarding wrappers;
- understands forwarding builtins such as `command`, `builtin`, and `exec` by continuing to the executable argument after their options;
- treats `eval` or any construct it cannot prove as `ambiguous_shell_dispatch` and fails closed;
- feeds its generic derived result into a finite allowlist rather than using that allowlist as the detector;
- runs fixed `/bin/bash -n` over every installed production shell entrypoint and treats syntax/parser failure as a violation, never an empty result.

Mutation proof should include bare, assignment-prefixed, substituted, wrapped, grouped/pipelined, absolute-path, `command`, `exec`, and ambiguous `eval` dispatches, plus malformed quote/control-flow syntax. Keep a diagnostic-string control so the scanner does not flag non-executed text.

### Reviewer transport failures are not review evidence

A model process ending, an empty report, authentication failure, timeout, malformed final verdict, or a report produced by a different model is not a CLEAN lane. Preserve the raw failure artifact, but record the lane as incomplete. Before changing source, still run live-source, candidate, and immutable-view END closures so the failed attempt remains attributable to the exact boundary. Retry the same reviewer model through another authorized client only when model identity remains explicit; otherwise create a new named lane. Require a non-empty report with the exact verdict protocol before counting the lane.

## 7. Final pre-review checkpoint

Before building the next immutable boundary, require:

- all exact partitions green;
- fixed-point pin refresh twice with an unchanged diff digest;
- compile, JSON, shell syntax, and `git diff --check` green;
- zero repo-local cache/ignored artifacts;
- zero staged paths and no unexpected refs/stashes;
- no matching pytest/reviewer/mutator processes;
- credential scan classified without printing secret values.
