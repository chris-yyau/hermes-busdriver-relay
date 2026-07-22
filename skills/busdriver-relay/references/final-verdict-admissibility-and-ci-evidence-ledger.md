# Final-verdict admissibility and CI evidence ledger

Use this reference for final independent delivery/CI trust reviews. It exists to prevent a plausible narrative from outrunning the evidence actually completed.

## Non-negotiable verdict gate

`PASS` is permitted only when **every mandatory claim** has a completed evidence row and the closing checker/seal itself exits successfully.

- A script that validates several early assertions and then exits nonzero has not produced a partial PASS. The unchecked tail remains unknown.
- If the intended seal file was not written, is empty, cannot be parsed, has the wrong schema, or was produced before the last mutable-authority refresh, there is no closing seal.
- Never conclude PASS and then disclose that the mandatory aggregator failed. Either complete the missing proof through another successful, equally explicit path or return concrete findings/`NO PASS`.
- Historical summaries and filenames are discovery aids, not authority. Open and validate the actual artifact before citing it.
- Reserve the last interactions for: collect background results, refresh mutable authority, run the close checker, validate its output, compare opening/closing footprints, and report. Optional exploration stops before this reserve.

## Evidence-ledger shape

Create the ledger before broad investigation. One row per mandatory claim:

| Claim | Authority endpoint/artifact | Freshness rule | Required fields | Completion |
|---|---|---|---|---|
| PR identity | live PR API | refresh at close | number, state, Draft, head SHA | pending/pass/fail |
| Tree identity | immutable commit API + local object | immutable after binding | commit SHA, tree SHA | pending/pass/fail |
| Required policy | branch protection + exact-tree lock | refresh at close | exact `(context, app_id)` sets, strict flag | pending/pass/fail |
| Required execution | check-run + run + job + log | immutable IDs; verify at close | app, head SHA, event, attempt, job conclusion, non-skipped steps | pending/pass/fail |
| Runner reality | job API | immutable job | requested labels, observed labels, runner group/name | pending/pass/fail |
| Test evidence | exact command, log, exit status | bind after run | interpreter, command, summary, exit, log hash | pending/pass/fail |
| Semantic tree | independent replay/index/materialization | recompute at close | paths, Git modes, blob bytes, tree ID | pending/pass/fail |
| Delivery truth | implementation + targeted contracts | exact tree | publish CAS, rollback CAS, unknown-outcome behavior | pending/pass/fail |
| Manifest/DAG | manifest + proposal + independent replay | exact tree/artifact | path bases, digests, dependencies, topology | pending/pass/fail |

The final checker must fail closed if any row is not `pass`. Print failed/pending rows instead of a verdict-shaped success summary.

## GitHub Actions execution proof

A successful check-run with the expected app proves reporter identity and conclusion, but not by itself that useful work executed.

For every required context:

1. Match exactly one check-run on the reviewed SHA.
2. Verify `app.id`, status, conclusion, and details URL/job ID.
3. Resolve the underlying workflow run and job.
4. Verify run `event`, `run_attempt`, `head_sha`, status, and conclusion.
5. Verify the required job itself is not skipped and its substantive steps completed successfully.
6. Capture observed runner labels/group/name and inspect the relevant job log.

Keep these categories distinct:

- **required execution:** must be real `COMPLETED/SUCCESS`, never skipped/neutral;
- **expected actor-gated skip:** for example a Dependabot-only workflow on a human-authored PR; prove the actor guard from exact-tree workflow bytes;
- **expected event absence:** a workflow limited to `workflow_dispatch` or main-branch push produces no PR run at all—call this absence, not a skipped PR job;
- **unexpected missing/skip:** a required context with no underlying successful execution is a finding even if branch protection appears satisfied.

## Safe API artifact capture

Do not let a failed refresh destroy the last valid snapshot.

- Download to a unique temporary pathname, verify HTTP success, nonzero size, parseable JSON, expected top-level shape, repository/SHA/ID binding, and capture time; only then atomically promote it to the ledger pathname.
- Shell redirection creates/truncates the destination before `curl`/`gh` succeeds. A 401/404 can therefore leave a zero-byte file that looks like a fresh artifact by name alone.
- Prefer one endpoint per checked command while diagnosing. Large `set -e` batches obscure which endpoint failed and which earlier files are valid.
- Immutable run/job artifacts may be reused only after their exact IDs, SHA binding, completeness, and capture provenance are revalidated. Mutable PR/protection state must be refreshed at close.
- Discover filenames or pass an explicit artifact manifest to the checker. Do not hard-code aliases without a preflight that lists every required input and validates it before substantive assertions.

## Semantic seal without mutating evidence

- Never run `write-tree`, test tooling, or cache-producing commands against the evidence checkout/object store when immutability is part of the contract.
- Make private byte copies of replay indexes/object stores under scratch, then compute trees there.
- Compare normalized entry maps `(raw path bytes, Git mode, blob OID)` across the reviewed commit and each replay index.
- For an independent semantic digest, hash a framed stream of raw path bytes, Git mode, and blob content. Require all digests and Git tree IDs to agree.
- Directory mtime is not semantic authority; paths, modes, bytes, and resulting tree identity are.

## Ambient Git-state preflight

Hermes terminal exports can persist between calls. Before clone/status/test/replay operations, unset `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, and process-local Git config overrides. Scope special Git variables to one command or subshell. Verify the scratch repository with `rev-parse --show-toplevel`, `rev-parse HEAD`, and a tracked-file count before trusting further Git output.

## Strict local evidence-admissibility protocol

For a binary `PASS`/blocker review of a sealed local delivery tree:

1. **Opening seal first.** Before scratch or tests, record canonical path, `HEAD`, `HEAD^{tree}`, porcelain-v2 status including untracked files, staged/unstaged binary diffs, and one SHA-256 over an explicitly framed byte payload. Set `GIT_OPTIONAL_LOCKS=0`.
2. **Follow the hash closure.** Recompute every file hash referenced by the top authority, then follow nested references such as negative logs, prior full authority, prior closing authority, CI snapshots, and atomic-push records. Report `N/N`; a digest without a locatable artifact remains an unverified claim.
3. **Keep authority classes separate.** Prior full exact, final complement, focused checks, per-tip portable smoke, expected-negative mutation tests, and host-runtime adjudication are different rows. Portable smoke is not full authority. Expected exit 1 proves rejection only when the intended reason is visible; it is never positive success.
4. **Validate every stack row.** Check commit existence, recorded tree versus `%T`, parent continuity, test exit 0, caps, syntax/scanner results, and aggregate counts. Do not trust only `all_pass`.
5. **Bind focused results fully.** A test count alone is not evidence. Require exact command, interpreter, candidate tree, exit status, and log hash. Never reuse a same-count log from another command or older tree.
6. **Close byte-for-byte.** Recompute the opening payload with identical newline/framing rules and require the same digest, expected commit/tree, zero status records, and empty diffs. Remove only review-owned scratch and prove its patterns absent before verdict.

### Read-only comparison of disjoint object stores

Rebuilt trees may live in separate replay object directories and be unreachable from the evidence checkout. Do not fetch or import objects merely to compare them. Use the source repository for Git plumbing, point `GIT_OBJECT_DIRECTORY` at one replay, provide source/candidate stores through `GIT_ALTERNATE_OBJECT_DIRECTORIES`, obtain each `git ls-tree -r` map independently, and compare `(path, mode, type, OID)` maps in memory.

### Isolated-interpreter focused tests

If a focused test recursively invokes `sys.executable -I -m pytest`, `PYTHONPATH` and `pip --target` do not survive `-I`. Create a temporary venv under the approved scratch root, install the compatible pytest into that venv, run the narrow test, and remove the venv. Preserve only the command/version/exit/count/log digest needed by the ledger.

### Host-runtime drift adjudication

A live pinned-binary mismatch must remain a failed host-bound row, not be rewritten into success. Independently verify the live version/digest and exact failure reason; fetch immutable official release bytes into scratch, verify their digest against the pin *before execution*, then run the narrow semantic/private-copy probe against those pinned bytes. The final ledger may pass only when the complement succeeded without that named host test and the pinned-runtime row has its own positive authority.
