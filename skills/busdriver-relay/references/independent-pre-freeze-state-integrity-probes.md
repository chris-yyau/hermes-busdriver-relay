# Independent pre-freeze state-integrity probes

Use this when reviewing a mutable or worker-produced Busdriver candidate without trusting its own evidence and without writing to the candidate.

## Bind the review to bytes

1. Copy the candidate into an external test root; exclude caches, not source.
2. Run with isolated `HOME`, `TMPDIR`, XDG paths, `PYTHONDONTWRITEBYTECODE=1`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, and pytest cache disabled. For every Git command against the immutable source (including `status`, `diff`, and metadata queries), also set `GIT_OPTIONAL_LOCKS=0` command-scoped so nominally read-only inspection cannot refresh/write the source index. Use a separate copied repository or external `GIT_INDEX_FILE` for any operation that intentionally writes an index or objects.
3. Compute a canonical tree digest for source and test copy, including relative path, file type/mode, symlink target, and file SHA-256; exclude only `.git`, caches, `__pycache__`, and `.pyc`.
4. Compare source and copy again after tests. A worker can change bytes during review. If they differ, identify the changed files, resync them, rerun every affected probe/test, and recompute the digest.
5. Before verdict, require source stability over a short second observation and record the final digest. Never apply a finding or CLEAN verdict from tests run against older bytes.

## Early fixed-blocker probe

A passing stock suite is insufficient. Load the dispatcher in-process and replace every forbidden downstream seam with a hard-fail sentinel:

- run-identity generation;
- delivery/status discovery;
- repository/state resolution;
- lock acquire/release;
- artifact persistence;
- mutating or verifier dispatch.

Exercise every fixed blocker both with and without caller-supplied identity. Also invoke the real CLI in a fresh `HOME` with hostile `git`/`gh` sentinels and an external artifact directory. Assert:

- the documented blocker wins before every forbidden seam;
- no home/state/artifact/repository sentinel appears;
- absent identity remains absent when policy says no identity may be synthesized;
- supplied identity is preserved exactly and is not silently promoted to persisted/durable state;
- steps mention only work actually attempted, or explicitly mark skipped work with the real blocker reason.

Treat one operation that reaches identity generation while peers return earlier as a branch-ordering bug even if no artifact is written.

Before calling nullable early telemetry schema-invalid, distinguish a generic public schema validator from a persisted-artifact validator. Report only when the contract really requires the rejected shape; intentional non-persisted nullable correlation fields are not automatically a finding.

## Cleanup failure-window probe

For large shadow/resource fixtures, `request.addfinalizer()` is exception-safe only after it has been registered. Register cleanup before copying/materializing the resource.

Test three paths independently:

1. normal completion;
2. assertion after finalizer registration;
3. copy/materialization creates data and then raises before returning.

The third probe catches the common bug `copy(); addfinalizer(cleanup)`. Force the real copy helper to materialize the resource and then raise; after pytest exits, search the basetemp for residue and record file count/logical bytes. Clean only the external evidence root after recording it. The minimal safe pattern is `define cleanup; addfinalizer(cleanup); copy()` or a `try/finally` covering copy itself.

## Trusted-runtime closure

Independently hash every manifest production entrypoint and private runtime entry. Then load each consumer and compare embedded digest maps/constants to the manifest. Stock manifest tests can pass on stale review bytes, so bind this result to the final tree digest.

## Verdict discipline

- Full-suite green does not erase a red focused negative probe.
- Count findings by root cause, not by parameterized operation.
- Report only reproducible Critical/High/Medium issues, with exact source lines, one-command repro, actual output, impact, and smallest root-cause fix.
- If no such issue survives final-byte replay, state `CLEAN` explicitly.
