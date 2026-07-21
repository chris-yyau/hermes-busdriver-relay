# Untrusted Git Observation Sandbox Lessons

Read-only Git commands against an untrusted repository are executable and network-capable operations. Repository config, attributes, submodule config, and promisor/lazy-fetch state can select programs or transports.

## Required boundary

1. Dispatch an authenticated real Git binary through an authenticated OS sandbox that denies descendant execution and all network access. A finite config-key denylist is defense in depth, not the boundary.
2. Pin fixed executable settings at command scope: `core.fsmonitor`, hooks, signature programs, diff/textconv, editor/askpass, credentials, recursion, and protocols.
3. Set `GIT_NO_LAZY_FETCH=1`, empty `GIT_ALLOW_PROTOCOL`, `--ignore-submodules=none` for status so gitlink/submodule drift remains visible, and `--no-ext-diff --no-textconv` for diff.
4. In the Pi filesystem broker, audit effective local and worktree dynamic `filter.*.{clean,smudge,process}` and `diff.*.{command,textconv}` keys through the descriptor-bound `.git` anchor before every allowed Git verb. Keep the sandbox to close rename/ABA races.
5. Fail closed if the sandbox or real Git source cannot be authenticated; never fall back to PATH, a user-writable copy, or an unsandboxed probe.
6. Treat **any non-empty stderr from a sandboxed Git observation** as an invalid observation, even when Git exits zero. Do not pattern-match localized denial prose and do not force a locale merely to recognize one error string. Preserve the caller's legitimate locale semantics, discard all partial stdout, suppress repository-controlled stderr behind a fixed token such as `git_observation_stderr`, and return a distinct nonzero result (for example `126`). Apply this at every production observer and at the broker boundary; higher-level clean/dirty or delivery logic must never consume partial Git output. Enforce this at every real dispatch seam, including bytes-mode/NUL-framed helpers: a text-mode `git()` wrapper is not coverage for a sibling `run(..., text=False)` path that bypasses it.
7. In bounded brokers, drain stdout and stderr concurrently under the same deadline. Bound both streams, kill/reap the whole process group on timeout or inherited-pipe stalls, preserve output-overflow precedence when overflow is already proven, and never relay repository-controlled Git prose.
8. Enumerate observations from the **production call graph**, not from a hand-maintained list of standalone status helpers. Canonical commit/push/delivery executors often perform preflight and postflight `status` and `diff` reads through nested pathspec batching helpers; every one of those dispatches requires the same sandbox, stderr refusal, bounded capture, and authenticated Git path. A central top-level wrapper is not coverage when a nested helper still calls an ambient `git_raw()` or `run_safe(["git", "diff", ...])` seam. Conversely, reject a review claim about a helper that is provably cut off by a production blocker before it can run; reachability is part of severity.

## False-clean regression recipe

A sandbox can successfully prevent side effects while Git still fails open at the semantic layer:

1. Commit a file whose index and worktree bytes are `x`.
2. Add a repository-selected clean filter that emits `y` and arrange for the file to be rechecked.
3. Prove the control: ordinary Git executes the filter and reports the file modified.
4. Run the production sandboxed observer. Git may be unable to execute the filter, emit diagnostic stderr, exit `0`, and omit the modified path from stdout. The test may assert that a denial occurred, but production must not depend on one locale-specific phrase such as `Operation not permitted`.
5. The regression passes only if the production wrapper returns the fixed failure code/token, emits no usable stdout, and leaves the filter sentinel absent.

This test catches the important distinction between **side-effect containment** and **observation integrity**. A no-exec sandbox alone proves only the first.

## Verification discipline

Add hostile filter/signature/submodule/lazy-fetch regressions first and verify RED for the intended production reason rather than a broken fixture. Implement the boundary, refresh every transitive executable/script pin to a fixed point, and rerun the exact-byte full contract suite before freezing review evidence. When containment changes child environment construction, retain and rerun explicit legitimate-semantics checks for locale, `HOME`, and `TMPDIR`; fail-closed recognition should not require rewriting those values.

Any source-tree edit after a boundary is frozen—including a new regression or skill-source update—invalidates that boundary's reviews. Start a new repair round and obtain fresh closure on one immutable tree; never carry an earlier CLEAN verdict forward.
