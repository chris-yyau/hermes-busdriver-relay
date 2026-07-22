# Frozen correctness review: policy ordering and truthful step evidence
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this when independently reviewing a frozen delivery/runtime candidate for correctness and state integrity.

## 1. Enumerate production-negative operations semantically

Do not infer the policy-blocked set only from the top-level blocker map. Search every production operation helper for unconditional blocked returns. An operation whose helper always returns a containment/credential/runtime blocker is already production-negative, even if `main()` still routes through ordinary discovery first.

For every production-negative operation, the fixed blocker must run before:

1. run-id/timestamp/state creation;
2. required-argument and repository-binding validation that cannot change the unconditional verdict (for example, a permanently blocked push must report its atomic blocker even when `--expected-repository` is absent);
3. repository, plugin, executable, `HOME`, credential, or SSH-agent discovery;
4. delivery-status or other credential-capable helpers;
5. lock acquisition;
6. worker/network launch;
7. artifact or tombstone writes.

A blocker inside the operation helper is too late if dispatch reaches credential-capable discovery or acquires state first. A generic prerequisite error is also too early when it hides a stronger unconditional operation blocker.

## 2. Use hard sentinels, not call-count assumptions

Load the production entrypoint without modifying it and replace each forbidden pre-block helper with a function that raises immediately:

- delivery-status/discovery;
- lock acquire;
- artifact writer;
- worker/network launcher.

Invoke the real `main()` argument path. A correct pre-side-effect blocker returns its documented reason without touching any sentinel. Also run direct entrypoints with a fake `PATH`, fresh `HOME`, and a FIFO at a likely credential-file path; require quick blocked return and an untouched ambient-executable sentinel.

Treat a nominally read-only status helper as credential-capable when any accepted argument can make it launch PR/GitHub checks or when its child environment retains `HOME`, `SSH_AUTH_SOCK`, or provider config. Probe the worst accepted argument combination (for example, a fixed-blocked operation plus `--pr`) rather than only the simplest invocation. A helper that is harmless without `--pr` does not justify running before an unconditional blocker.

For a fixed blocker buried in an operation helper, use two complementary traces:

1. make lock acquisition fail and prove status/lock/artifact routing happens before the blocker can be reached;
2. return a fully safe synthetic status and acquired lock, wrap the real fixed-blocker helper, then record the complete order through release and artifact writing.

This distinguishes an early policy return from a late blocked result that still mutates relay state.

## 3. Step telemetry must describe execution, not intention

For an operation blocked before lock acquisition:

- `finalization_lock: passed` is false;
- `finalization_lock: checked` is also false if the helper never ran;
- use `skipped` with a reason such as `policy_blocked_before_lock`, or omit the step;
- do not synthesize `run_id`, `created_at`, or persisted run/artifact state;
- if the caller explicitly supplied a correlation ID, it may be echoed as caller input, but it must not imply that a run was created; pair it with a null/absent creation timestamp and no artifact path.

Build early-blocked envelopes from observed transition facts, not merely `(operation, final_reason)`. Use one dedicated builder for all fixed blockers so pre-PR, push, PR-create, merge, verifier, and future negative operations cannot drift into different schemas. Test the JSON steps and run fields together with hard helper sentinels. Cover both missing optional/prerequisite arguments and explicit caller run IDs: neither may reorder or weaken an unconditional blocker.

## 4. Prove cleanup on success and failure

Large mutation probes can pass while leaving damaging state behind. Any test that copies a real package tree, repository, runtime, or credential fixture must register cleanup before the first assertion that can fail.

- Prefer a context manager or a pytest finalizer registered immediately after creation.
- Also clean explicitly on the success path and assert the root is absent.
- Exercise an intentional assertion/exception path and verify teardown removes the same root.
- Put shadows under an external test root, never inside the frozen candidate.
- After a deliberate RED run, remove and verify any residue before continuing; do not let repeated full/smoke runs accumulate recent pytest temp roots.

Count retained bytes and directory entries when assigning severity. A green functional assertion does not excuse hundreds of MiB or tens of thousands of retained entries per suite run.

## 5. Keep findings root-cause counted

A parameterized probe may fail once per operation. Count identical failures from one shared function as one blocker, while listing all affected operations. Preserve the raw check count separately.

## 6. End closure must really be last

Run the end verifier after all candidate reads, tests, probes, and code inspection. Writing the external report or checksum afterward is safe, but if the candidate is touched again—even read-only—rerun the end verifier so the recorded closure is genuinely final.

Compare all authoritative identity fields, not only the tree hash: manifest/diff/tar hashes, record counts, HEAD, base ref, branch, and candidate tree. Lane-specific rebuilt output paths may differ.

## 7. Preserve real test exit status portably

Do not use Bash `${PIPESTATUS[0]}` in a zsh wrapper. Prefer no pipeline:

```sh
set +e
python -m pytest ... >"$log" 2>&1
rc=$?
printf '\nPYTEST_INTERNAL_RC=%s\n' "$rc" >>"$log"
print -r -- "$(<"$log")"
exit "$rc"
```

If tee is essential, use the shell's native pipeline-status mechanism explicitly. Always distinguish a green test command from a later wrapper failure in the report.

## 8. Useful focused invariants

Alongside the full suite, probe:

- exact reconstructed candidate tree and staged/unstaged/untracked shape;
- previous-to-current frozen path accounting;
- segment-aware glob agreement across duplicated implementations;
- trusted runtime entrypoint hash closure;
- two-replacement compare-retire lock race (original, replacement A, replacement B all preserved appropriately);
- fixed blocker ordering with fake PATH/FIFO credential boundaries;
- truthful status/step semantics.

A green suite and clean start/end identity do not override a red custom correctness probe. `CLEAN` still requires zero critical/high/medium blockers.
