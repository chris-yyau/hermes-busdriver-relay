# Real-agent smoke diagnostics and retained temporary repositories

Use this when an optional real Pi/OpenCode/Codex smoke fails before producing a draft, especially when the top-level envelope only reports `blocked` and a return code.

## Diagnostic sequence

1. Treat a fail-closed result with no changed files as **safe failure, not successful proof**.
2. Retry only after the first failure, with the tool's repository-retention option enabled.
3. Verify the reported retained path exists **after the smoke subprocess exits** before relying on it for diagnostics.
4. Inspect bounded/redacted gate, adapter, and artifact output from that retained repository. Do not expose credentials or unrestricted stdout/stderr.
5. Fix the root cause, then rerun the real adapter smoke. Fake harness contracts do not replace this positive execution proof.

## Python `TemporaryDirectory` pitfall

Do not try to implement `--keep-repo` with:

```python
tmp = tempfile.TemporaryDirectory(...)
tmp.cleanup = lambda: None
```

The finalizer callback is registered when the object is created; replacing the instance method does not reliably detach that callback, so the directory can still disappear at interpreter shutdown.

Use explicit ownership instead:

```python
if keep_repo:
    repo = Path(tempfile.mkdtemp(prefix="agent-smoke-"))
    tmp = None
else:
    tmp = tempfile.TemporaryDirectory(prefix="agent-smoke-")
    repo = Path(tmp.name)

try:
    run_smoke(repo)
finally:
    if tmp is not None:
        tmp.cleanup()
```

## Regression contract

Exercise the smoke as a subprocess, request retention, parse the reported path, and assert after subprocess exit that:

- `kept_repo` is true;
- the path is still a directory;
- its `.git` directory exists;
- the test removes the retained directory in `finally`.

First run this test against the old implementation and preserve the RED evidence; then patch production code and rerun GREEN.

## Frozen-review discipline

Any production or test edit after a hash-bound review snapshot invalidates that snapshot and all in-flight verdicts. Mark those reviews obsolete, rerun the complete gates, recompute the cumulative base-to-worktree snapshot including untracked files, and dispatch fresh independent reviews. Never reuse a verdict bound to the old hash.
