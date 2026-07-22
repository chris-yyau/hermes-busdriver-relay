# Reviewer finding adjudication and process-lifecycle containment
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference when immutable reviewers disagree, when a report's premise may be wrong, or when relay code launches bounded child processes.

## Separate four independent questions

A review lane is not a single boolean. Establish each layer independently:

1. **Runner validity** — process exit, non-empty report, expected model identity, stderr/permission state, and no tool/write bypass.
2. **Snapshot validity** — START and END closures authenticate the same immutable source bytes.
3. **Finding validity** — independently reproduce or trace the exact premise, production caller, data type, return-code contract, and reachability.
4. **Candidate disposition** — only an adjudicated reachable High/Medium blocks; a valid lane can still contain a false positive.

Do not equate a successful END closure with a correct conclusion. Closures prove what bytes were reviewed, not that the reviewer reasoned correctly.

## Adjudicate before freezing BLOCKED

For every reported High/Medium:

1. Quote the exact invariant and claimed caller/dataflow.
2. Read the complete helper chain, including defaults and conversion helpers. Do not infer a value type from `subprocess.Popen` alone if a downstream wrapper decodes it.
3. Enumerate all production callers. Distinguish installed production from non-installed test harnesses, fixtures, dormant helpers, stale comments, and hypothetical future callsites.
4. Execute the smallest production-path probe when safe. Prefer a live type/return-code/OS-primitive assertion over prose-level inference.
5. Check whether the claimed attacker input can actually control the argument at that caller.
6. For fd/cwd/type claims, inspect `finally` cleanup, inheritable defaults/toggles, the exact assignment and return type of similarly named variables, and whether the process is one-request-and-exit or a long-lived daemon. A global-state change is not automatically a cross-request leak.
7. Record the result as accepted, rejected, or incomplete, with evidence.

A reviewer prompt should require an exact reachable production caller/dataflow. “The helper could be called this way later” and a stale comment are not current High/Medium findings.

If a candidate was already immutably marked BLOCKED before a premise was disproved, do not rewrite its disposition. Create a proof-only successor candidate, add a regression that demonstrates the real contract, and run fresh gates/reviews.

## Binary/text output tracing

When a finding depends on bytes versus text, trace the whole path:

- launcher pipe mode;
- bounded drain representation;
- wrapper default such as `text=True` or `text=False`;
- decode/replace behavior;
- `stdout` versus `stdout_tail` construction;
- the exact caller consuming the result.

Different wrappers can intentionally have different contracts. For example, a binary archive caller may use a bytes-preserving bounded launcher while a JSON/OID caller uses a text-decoding wrapper. A comment mentioning a binary operation does not prove that operation uses the same wrapper.

Add a live production-path regression that asserts both the output type and semantic shape. This catches a future default change without introducing speculative compatibility code.

## Descriptor identity is not byte immutability

An authenticated regular-file descriptor pins an inode, not a snapshot of its contents. `O_NOFOLLOW`, `lstat`/`fstat`, a digest, an identity recheck, and `lseek(fd, 0)` still permit a same-UID writer to chmod/truncate/rewrite the same inode after authentication and before a later `/dev/fd/<n>` source/exec reads it.

- If authenticated bytes will be consumed after the final check, transfer the verified bytes into an immutable-use channel: a pipe read end populated from the already-verified bytes, a sealed memfd where supported, or another mechanism whose producer is closed before credential-bearing execution. Do not call an ordinary retained file fd “immutable bytes.”
- Put the helper-specific size cap in the final guard that reads/materializes the object. A large generic executable cap is not a substitute. Reject oversized `fstat` metadata before allocation, then read at most cap-plus-one and recheck descriptor/name identity.
- The strongest RED mutates the same inode after the last digest and immediately before the real consumer reads it. Path replacement alone proves a weaker race.
- When an end-to-end regression unexpectedly passes despite the primitive remaining suspect, run a tiny OS-level descriptor probe outside the repo: hash/read an open fd, truncate/write the same inode through a second fd, then read the first fd. Use that result to distinguish a real primitive guarantee from incidental shell/test behavior.

When adjudicating a reported fd leak, separately check lifetime and inheritance: inspect every `finally: os.close(fd)`, explicit inheritable toggle, `close_fds`, and the runtime's default non-inheritable-fd contract. A reviewer omitting one of these facts has not established a leak.

## Canonical credential aliases

Credential handling is both a confidentiality boundary and a functional reachability contract. Define the approved aliases once, then derive every child-environment allowlist, authentication-presence predicate, redaction value set, loop/delivery forwarding set, and focused test parameterization from that canonical tuple. A credential name listed for redaction but omitted from forwarding or auth detection is an inconsistent contract, not harmless fail-closed behavior.

Test each supported alias at the actual `Popen(env=...)` or `execve` boundary using presence booleans or placeholders only—never preserve live credential values in logs, fixtures, review prompts, or skill references.

## Process-group lifecycle ownership

A bounded subprocess stack must have exactly one lifecycle owner.

- Enter the cleanup `try` immediately after `Popen` succeeds. Initialize pipe/thread references defensively and construct/start drain threads inside that scope; cleanup must tolerate zero, one, or two successfully started threads. Otherwise `Thread.start()`, `KeyboardInterrupt`, `MemoryError`, or another `BaseException` can escape before timeout/group ownership exists.
- The layer that detects timeout/overflow should terminate and reap.
- Outer wrappers must not signal the process or process group again after that layer returns a terminal result.
- Signaling a numeric PID/PGID after reaping creates a PID-reuse race.
- `process.poll()` may reap the leader. Any later `killpg(process.pid, ...)` must account for that fact; do not assume the numeric PGID remains bound to the original job.
- Tests should cover an exception during each startup edge, not only during the later polling loop, and inject terminal timeout/overflow results with a canary that fails if an outer layer signals again.

### Process groups are not hostile-code containment

`start_new_session=True` and `killpg` contain cooperative descendants, not adversarial code. A child can call `setsid()`, leave the original group, retain a pipe, and outlive group cleanup. Never claim “all descendants are contained” solely from process-group management.

If the host lacks a stable kernel-owned containment primitive suitable for arbitrary verifier code, fail closed by construction:

1. block the operation before run identity, status, credentials, artifacts, or side effects;
2. remove the installed arbitrary-command executor, not merely the public CLI flag;
3. remove dormant unlock branches and parser/helper functions that could reopen execution;
4. keep any executor needed by tests in a source-separated, non-installed harness;
5. add an AST regression proving installed production contains no executor definition or callsite and that the operation is in the fixed early-blocker map.

A runtime function that always returns a blocker is weaker than eliminating the executor branch: monkeypatching, refactoring, or a future return-value change can reopen dormant code.

## Review disagreement policy

- Claude security remains the security authority, but its factual premises still require verification.
- Codex correctness and Gemini long-context findings are neither automatically accepted nor automatically discounted.
- One accepted High/Medium blocks even when the other two lanes are CLEAN.
- One rejected finding does not make the lane invalid; document the adjudication in the CLEAN disposition.
- If reviewers identify different layers of the same process primitive, fix the deepest reachable invariant rather than repeatedly patching symptoms.

## Minimal evidence bundle for process findings

Include:

- complete lifecycle functions, not excerpts that omit helper defaults;
- every production caller and command-head constructor;
- exact diff from the previous candidate;
- timeout/overflow/descendant tests;
- installed-production versus fixture/harness boundary;
- trusted executable table and scanner provenance when dispatch is involved.

This reduces reviewer hallucinations caused by missing reachability or type context while preserving strict read-only review.
