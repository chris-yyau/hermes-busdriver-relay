# Deterministic private-runtime packaging review probes
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference for exact-boundary reviews of authenticated runtime bundles, especially transitive launcher chains such as parent → loop → checker and Python guard → shell helpers.

## Exact START/reconstruction/END pattern

1. Before START, read only the boundary and its verifier implementation.
2. Use an external reviewer-owned verifier with two modes:
   - `START`: validate boundary SHA/sidecar and every authoritative live field, then reconstruct a reviewer-only candidate from verified entry bytes.
   - `END`: rerun the same live-boundary checks only; do not inspect the reconstructed candidate.
3. Recompute candidate trees without writing source objects: use a temporary index and temporary object directory, with the source object directory only as an alternate.
4. Run every candidate read, focused test, and benign fixture probe between START and END.
5. Draft the report before END. After END, only finalize the external report and checksum; never reopen candidate or source bytes.
6. Report missing END, report sealing, or sidecar verification as `INCOMPLETE`, even if no finding was observed.

## Probe the materializer, not only resolver helpers

Contract tests often prove that resolvers reject missing/symlink/mode/digest mutations but never assert how the production parent actually packages its children. Add a production-shaped benign fixture probe that invokes the real materializer/launcher while intercepting only final subprocess dispatch. Record:

- every copied script and executable path;
- directory and entry modes;
- marker value in the exact child environment;
- resolved `argv[0]` and whether it is inside the expected private runtime;
- whether returned executable paths equal the pinned mutable source;
- child-side validation coverage before any shell/interpreter dispatch.

A passing resolver test does not prove the parent used `0500`, copied the full closure, or propagated the marker.

## Script bytes are part of the transitive closure

Do not validate only `git`/`gh`/`jq`. If a guarded child enters `/bin/bash` and then sources or executes authenticated helper scripts, those scripts are required private-runtime entries too.

Require the child-side guard, immediately before shell dispatch, to verify every reachable helper script and executable for:

- expected relative path and complete manifest membership;
- regular-file type, no symlink, correct owner, `nlink == 1`;
- private parent directory mode `0700`;
- entry mode `0500`;
- pinned digest.

Parent-side hash/copy plus a child guard that checks tools only leaves an unverified script edge. Treat writable/executable `0700` script copies as a formal packaging defect when the contract requires reviewed immutable-exec `0500` copies.

## Agent and sibling entrypoint closure

Audit every production-inventory entrypoint even when a current fixed blocker lowers reachability. For each one:

- reject hash-then-return-source patterns; the executed path must be a retained private copy;
- propagate the private-runtime marker through gate/lock/helper launches;
- ensure a child validates the parent-provided complete bundle instead of silently creating an unrelated direct-runtime path;
- keep blocker reachability explicit in severity, but do not call the closure `CLEAN` while a production-inventory edge violates the packaging contract.

## Focused test accounting

Keep raw parameterized test counts separate from root-cause finding counts. A useful focused set includes:

- missing bin and entry;
- bin and entry symlink;
- mode and digest tamper;
- ambient PATH sentinel non-execution;
- source replacement after authentication;
- marker propagation across every subprocess boundary;
- exact mode assertions for scripts and tools;
- nested helper-script mutation before shell dispatch;
- trusted runtime manifest consistency.

Passing focused tests do not override a production-shaped materializer probe failure. Consolidate repeated symptoms into root-cause findings and report Critical/High/Medium counts mechanically.
