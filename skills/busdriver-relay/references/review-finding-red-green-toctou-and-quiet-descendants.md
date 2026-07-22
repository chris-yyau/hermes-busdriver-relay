# Reviewer finding RED→GREEN: retained runtime bytes and quiet descendants

Use this when a frozen Busdriver review returns substantive findings after gates appeared green. The goal is to adjudicate findings with concrete regressions in the next mutable iteration, without editing the frozen review view or claiming the blocked iteration is clean.

## Sequence

1. **Seal the reviewed iteration first.** If any reviewer returns a substantive finding, create a BLOCKED disposition with source identity, reviewer verdicts, and checksum, then make the disposition immutable. Do not repair inside the reviewed snapshot.
2. **Reproduce each finding as RED.** Add a focused contract test that exercises the exact reachable dataflow, then run that single test before touching production code. If the first reproduction is too mocked to prove exploitability, tighten it until the attacker-controlled effect is observable.
3. **Repair only after RED.** Make the smallest production change that removes the attacker effect, then re-run the RED tests and adjacent contracts. Refresh trusted-runtime pins after any script copy changes.
4. **Treat fixed-point separately.** A successful pin refresh is not enough; rerun the refresh until it reports no script or manifest changes.

## Materialized Python runtime TOCTOU pattern

Risk shape: parent authenticates reviewed script bytes, materializes them under a private `tempfile` directory, and later executes the materialized pathname. A `0700` directory and `0500` file do not stop the same UID from unlinking/replacing that pathname between authentication and `exec`.

Good RED regression:

- Use a minimal trusted delivery-status source whose digest matches the trusted table.
- Patch the launch seam so, immediately before the real bounded launcher executes, it replaces `scripts/hermes-busdriver-delivery-status` with an attacker script.
- Let the original bounded launcher run; do not merely return forged JSON from a fake launcher.
- Assert the attacker side effect is absent and the forged clean status cannot pass `delivery_status_mutation_blocker`.

Good fix:

- Retain authenticated entrypoint bytes in memory.
- Launch trusted Python with a tiny stdin loader, e.g. `python3 -I -c <loader> <virtual-entrypoint>`.
- Feed retained program bytes via stdin.
- Set `__file__`/`sys.argv[0]` to the materialized virtual path so ROOT-relative reads still work, but Python never re-opens that pathname for the entrypoint code.
- Leave materialized sibling files only as read-only support data for the retained entrypoint.

## Nested authenticated helper TOCTOU pattern

Risk shape: the reviewed entrypoint is fixed to retained stdin bytes, but it authenticates and materializes default helper scripts that are later launched by pathname. That leaves a second-order pathname-substitution race: the same UID can replace the private helper path between digest verification and the nested Python launch. Cover every default-helper edge, not only the top-level entrypoint (for example: delivery-status → pr-grind-check, finalization-readiness → default status/plan helpers, deliver → pr-grind-loop, and pr-grind-loop → pr-grind-check).

Good RED regression:

- Exercise the real nested dataflow and the real bounded launcher; do not satisfy the parent by returning forged JSON from a fake launcher.
- Immediately before the nested helper launch, replace the materialized/private helper pathname with an attacker script that writes a marker and emits plausible JSON.
- Assert both that the parent still receives valid trusted-helper output and that the attacker marker is absent. If the attacker marker appears, the finding is material.
- Locate the virtual helper path by basename in argv rather than hard-coding `cmd[2]`; stdin-loader launches use `python3 -I -c <loader> <virtual-path> ...`.

Good fix:

- Carry authenticated helper bytes alongside the virtual path all the way to the launch seam. A simple shape is `(virtual_path, retained_bytes)` or a list subclass/command carrier with `stdin_bytes` attached.
- Launch trusted Python with a retained-stdin loader and pass `stdin_bytes` through the bounded primitive (`stdin_bytes=getattr(cmd, "stdin_bytes", None)` or equivalent).
- Preserve the virtual path for `__file__`/`sys.argv[0]`/ROOT-relative reads, but make the program bytes come only from the retained buffer.
- Update non-installed harnesses to unwrap tuple/carrier values only for routing decisions, then delegate the original value to production `python_child`; otherwise the harness proves only its own path handling.
- After a helper fix, look one level deeper: if `pr-grind-loop` launches `pr-grind-check`, that inner edge also needs its own RED and retained-stdin fix.

## BaseException / interrupted bounded-cleanup pattern

Risk shape: timeout/overflow and normal-exit paths clean the process group, but `KeyboardInterrupt`/`BaseException` can arrive after the child is spawned and before the direct child is reaped. If cleanup lives only in ordinary return/exception branches, descendants survive user interrupts.

Good RED regression:

- Parameterize across every production module defining the bounded primitive.
- Start a leader that records a quiet descendant PID, then monkeypatch the non-reaping exit-watch/coordination seam to raise `KeyboardInterrupt` after the child group exists.
- Assert the bounded call re-raises, but the descendant process group is gone by a short deadline.

Good fix:

- Wrap the child lifecycle in a `BaseException` cleanup path that signals the process group before any direct-child reap, closes pipes, performs bounded wait/join cleanup, and then re-raises.
- Keep bounded cleanup idempotent; do not add post-reap PID/PGID probing in outer callers.

## Quiet descendant process-group pattern

Risk shape: prior lifecycle tests killed descendants that kept inherited pipes open. A quieter child can spawn `sleep 300 </dev/null >/dev/null 2>/dev/null &`, record its PID, and have the leader exit `0`; drains finish normally, so no lingering-pipe cleanup triggers and the descendant survives.

Good RED regression:

- Parameterize across every production module defining the bounded primitive.
- Run `/bin/sh -c "sleep 300 </dev/null >/dev/null 2>/dev/null & echo $! > marker; exit 0"`.
- Assert the bounded call returns normally, then require the descendant PID to disappear by a short deadline.

Good fix:

- When the non-reaping child-exit watch observes leader exit, signal the process group before `wait()` reaps the leader, even if drains have finished and no timeout/overflow occurred.
- Keep the existing timeout/overflow/lingering-pipe pre-reap signaling checks; this is an additional successful-exit cleanup path, not a replacement.

## Verification checklist

- The two RED regressions fail before the fix and pass after it.
- The earlier lingering-pipe canary still passes; no code path reintroduced `poll()` as an exit observer before cleanup.
- Dispatch-surface AST contracts are updated only for the exact approved function hash and still reject ambiguous ambient dispatch. Compute those hashes with the contract's own canonicalizer (`_canonical_ast_bytes` from `test_production_dispatch_surface.py`), not raw `ast.dump`, or the allowlist update will be wrong.
- Run `py_compile`/`compileall` with `PYTHONDONTWRITEBYTECODE=1` and a repo-external `PYTHONPYCACHEPREFIX`; if a compile step accidentally creates repo `__pycache__`, clean it before dispatch discovery because pyc files can be misclassified as production consumers.
- Non-installed test harnesses that substitute materialized runtimes return or forward the new `(virtual_path, retained_bytes)` / retained-command shape rather than collapsing it back to a bare `Path`.
- Trusted-runtime pins and manifest reach fixed point after script edits.

## Second-order review follow-up

If a later fresh review still blocks after the obvious retained-stdin/BaseException fixes, load `references/r90-second-order-helper-and-bounded-ownership-review-lessons.md` before starting the next iteration. It covers the follow-on classes that r90 exposed: remaining executable support files, shell helpers, subprocess owners not named `run_bounded`, post-reap BaseException PGID signalling, unbounded pre-digest reads, and credential-propagation invariants.
