# Frozen security-review blocker workflow

Use this reference when a frozen Busdriver/relay candidate has several security blockers spanning gates, delivery, adapters, locks, rollback, status contracts, docs, and authenticated runtime pins.

## Preserve the candidate and prove the starting tree

- Work only in the designated worker clone; never repair the source WIP in place.
- Record `HEAD`, status, and the diff against the named candidate commit before editing.
- Remember that tracked files can match the candidate while candidate-added files appear untracked because the worker's index/HEAD is older. Include untracked files when proving tree equivalence; do not reset or clean them away.

## Vertical RED→GREEN ledger

For each behavior, complete one narrow slice before starting the next:

1. Add the smallest regression reaching the production surface.
2. Run only that test and record the expected behavioral failure, not a syntax/setup error.
3. Make the minimum production change.
4. Re-run the exact test GREEN plus one adjacent compatibility test.
5. Keep the exact command/result for the final report.

Do not batch all regressions and all implementation horizontally. If execution is interrupted by a tool ceiling, report the completed slices and unresolved list explicitly; never call the candidate complete.

## Fail-closed containment rules

A process group, PATH guard, environment scrub, path check, post-hoc snapshot, or drift detector is not an OS sandbox.

- If arbitrary verifier commands would run in the target repo without an OS containment domain, production dispatch must block before launch with an exact policy reason such as `verifier_containment_unavailable`.
- If an untrusted agent would receive copied credentials without an OS containment domain and parent-held credential broker, production Pi/OpenCode dispatch must block before credential read/copy and before worker launch.
- Preserve useful low-level execution tests only through clearly non-installed fixture harnesses using dependency injection. Never add a production parser flag or ambient environment bypass.
- Add sentinel tests proving the command/agent was never launched, credential files were not copied, success was not reported, and every authority flag remained false.

## Scope matching contract

Use one segment-aware behavior everywhere:

- `*` and `?` never cross `/`.
- `**` may cross `/`.
- `**/` may represent zero or more directory segments, so `src/**/*.txt` matches both `src/a.txt` and `src/nested/a.txt`.

Add nested-path RED cases at gate and adapter seams. Python `fnmatch.fnmatchcase` is unsuitable for this contract because `*` can cross separators.

## Relay metadata validation

Never default missing dispatch metadata to permissive values.

- `programmatic_dispatch_allowed` must be present and bool.
- Applicable adapter metadata must include bool `adapter_verified`.
- dispatch=true requires `adapter_verified=true` and a null/absent blocker.
- dispatch=false requires a present, non-empty string blocker.
- Missing fields, wrong types, and contradictions must force root `dispatch_allowed=false`.

Test every malformed shape directly against the root resolver envelope, not only a nested helper.

## Ownership and lock review checks

- After a candidate ref was published and then CAS-rolled back, ownership is relinquished. Do not perform pathname-based restore, rm, or clean; preserve the current index/worktree and report `reconciliation_required` or completed-with-warning.
- Reject non-positive lock TTLs.
- Expiration by wall clock alone does not prove owner death. If liveness is unproven, retain the lock and return a stale/manual-recovery blocker.
- Keep token compare-delete on release.

## Capability/docs consistency

Parser exposure is not availability. Capability matrices, README, CURRENT_STATUS, ADRs, skill docs, help, and status JSON must use the same exact blockers. In particular, unsupported atomic bindings and policy-blocked verifier/agent lanes must not be described as dispatchable.

## Integrity cascade

After all production bytes settle:

1. Compute actual SHA-256 values from disk; never guess.
2. Update leaf consumer pins first.
3. Update parents that authenticate those consumers.
4. Update `config/trusted-runtime-manifest.json` last.
5. Extend/run the manifest contract so every manifest script digest equals actual bytes and every embedded pin equals its manifest entry.
6. Any subsequent byte edit invalidates the evidence and requires repeating the cascade.

Finish with the required focused modules, `git diff --check`, and status. Do not run the very large full suite until focused tests are green.
