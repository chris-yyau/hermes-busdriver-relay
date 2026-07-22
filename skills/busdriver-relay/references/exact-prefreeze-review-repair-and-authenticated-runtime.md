# Exact pre-freeze repair and authenticated runtime closure

Use this reference when an exact pre-freeze review is blocked by executable trust, nested-runtime fallback, unauthenticated evidence artifacts, or semantic contract bypasses.

## Fail-closed adjudication

- A lane is `CLEAN` only when it independently reconstructs the candidate from the same immutable boundary, verifies START and END after all reads/tests/probes, emits a formal report, verifies its SHA-256 sidecar, and reports zero Critical/High/Medium findings.
- A completed opening or candidate rebuild is not a completed review. Missing END, report, sidecar, or severity accounting is `INCOMPLETE` even when no finding was reported.
- Consolidate exact lane counts mechanically. Preserve prior blocked boundaries as historical evidence; any source edit requires a new generation, source digest, candidate tree, boundary file, sidecar, and entirely new reviews.
- Keep the live source immutable from boundary creation through all lanes' closing ceremonies. Reviewers work from independently reconstructed candidates.

## Closing ceremony under tool budgets

Reserve the final calls before doing broad exploration. A safe order is:

1. Complete all candidate reads, tests, and hostile probes.
2. Draft the formal report with exact boundary identity, findings, and provisional disposition.
3. Perform END verification against the live boundary and reconstructed candidate.
4. Finalize the report without further candidate reads.
5. Write and verify the report SHA-256 sidecar.

If the report must record END details, collect them in the END verifier output and copy only that already-captured result; do not reopen the candidate after END.

### Preflight the bounded closing lane

Before START—and before spending the calls reserved for draft/END/report/sidecar—resolve the actual test runner and other required executables with a side-effect-free preflight. Do not assume that `python -m pytest` works merely because `python` exists; select the runner that owns the installed package (for example, the repository or agent virtualenv's `pytest`) and record its resolved path. Keep this preflight outside candidate reads/tests so the formal lane can still begin with a clean START.

A launch that fails before test collection is not a passing focused control and must not be counted as candidate evidence. Preserve it as an operational note, resolve the runner, and execute the intended small control exactly once. Do not rerun a full suite just to recover from runner selection.

### Require agreement between payload and process status

Closing evidence is valid only when the verifier payload, stderr expectations, and outer process/tool exit status agree. An `ok=true` JSON payload or `shasum: OK` line does not by itself neutralize a nonzero wrapper/process status.

Wrap every decisive invocation correctly on its **first** run so the shell and outer tool expose the real child status:

```bash
set -u
verifier ...
rc=$?
printf 'verifier_rc=%s\n' "$rc"
[ "$rc" -eq 0 ] || exit "$rc"
validator captured-output.json
validator_rc=$?
printf 'validator_rc=%s\n' "$validator_rc"
exit "$validator_rc"
```

Use `set -o pipefail` and `${PIPESTATUS[0]}` when `tee` is present. Do not rely on the last display or metadata command to preserve the decisive status; a later formatter, `stat`, or shell-exit behavior can make a successful-looking transcript and the outer result disagree.

If payload and outer status still conflict, spend the reserved slack call on a minimal verifier rerun that ends with an explicit zero exit after checking the artifact; otherwise classify the ceremony `INCOMPLETE`, not `CLEAN`. A standalone JSON payload validator is useful corroboration but does not replace missing verifier process status. In particular, do not perform a late replacement `START` after candidate reads/tests: it cannot retroactively establish opening order. Restart the lane if START process truth cannot be recovered safely. This applies independently to START, candidate-identity checks, END, and report-sidecar verification.

### Provider-filter and call-cap survival

A provider-filtered lane is `INCOMPLETE`, even if it performed useful checks before termination. A lane stopped by the tool-call cap before END/report/sidecar is also `INCOMPLETE`; preserve its findings as confirmed lower bounds, not as a formal CLEAN verdict.

For authorized local reviews, keep the brief narrow and explicitly local: software quality/reliability, no network, exact immutable boundary, fixed focused controls, and fixed output paths. Avoid spending the lane on broad reconnaissance. Prebuild and self-check a reusable boundary verifier outside the source so each reviewer can perform START and END with one call apiece.

Use a hard call budget:

- finish all candidate work and freeze a draft by roughly two-thirds of the allowance;
- reserve the final calls for cleanup, END, report write, sidecar write, and sidecar verification;
- do not rerun the full suite in each lane—verify the retained exact-source raw log and run only focused independent controls.

If any incomplete lane confirms a High or Medium finding, consolidate the generation as `BLOCKED / INCOMPLETE` before editing source. Do not re-dispatch the same known-bad generation merely to obtain prettier ceremony; repair it, create a new exact boundary, and run fresh reviews.

### Retain raw full-suite evidence

For the producer full suite, preserve command, exact-source identity, outer exit status, and the complete raw process log plus a verified SHA-256 sidecar outside the source. An `N passed` prose sentence without the raw log is traceability evidence only and must not be upgraded to reviewer-owned reproduction.

## Executable authenticity: verify, copy, execute

Hash-then-execute of the original executable is a TOCTOU defect. For every trusted Git/GH/jq edge:

1. Resolve an explicitly pinned source path.
2. Reject symlinks/non-regular files and verify the source digest.
3. Copy authenticated bytes into a retained private directory (`0700`) using exclusive/no-follow creation.
4. Set the private executable to `0500` and verify owner, link count, type, mode, and digest.
5. Execute the private path as `argv[0]`; never execute the mutable source or ambient `PATH` fallback.

Apply this to direct entrypoints as well as orchestrated execution. Typical missed edges are commit diff evidence, gate preflight, lock helpers, direct PR checkers, delivery-status descendants, and nested acknowledgement helpers.

## Marker propagation is necessary but insufficient

A private-runtime marker only states intent. It does not prove the child still has valid bytes, and `PATH=private-bin:/usr/bin` silently falls back when the private entry disappears.

- Every child that receives the marker must validate the private directory and every required entry at child startup.
- Probe directory/entry missing, directory/entry symlink, mode tamper, digest tamper, and replacement-byte sentinels.
- Nested re-bundles must propagate the marker and preserve the complete private bundle.
- For shell-based nested helpers, enter through a child-side guard that validates the bundle immediately before shell dispatch. A parent-only preflight leaves a mutation window.
- A failed private validation must return a structured `private_trusted_*` error; it must not continue with system tools.

## Writer-authenticated run artifacts

Schema validity, restrictive file modes, and false authority flags do not authenticate the writer. In particular, a disk HMAC key owned by the same UID is not a writer boundary: a same-UID child can read it and create an artifact that verifies.

Choose the authentication model explicitly:

### Process-scoped capability (fail-closed local model)

- Generate a random HMAC capability in the writer process and keep it only in process memory; never persist it or export it through an exec environment.
- Put only a random `key_id` and HMAC in the artifact. The verifier accepts an artifact only while the same process still holds the matching capability.
- Canonicalize the payload without its authentication envelope and bind the MAC to the target filename/run identity.
- Require secure file metadata plus a constant-time valid MAC before schema validation or selection.
- A fresh process cannot authenticate an earlier artifact. Expose that as a truthful fixed blocker such as `artifact_writer_authentication_unavailable`, not `run_not_found` and not a claim of durable status lookup.
- Active docs and rendered CLI help must state the process-scoped boundary and cross-process limitation.

### Durable cross-process status (brokered model)

If durable lookup is a product requirement, use an external broker or OS capability that an arbitrary same-UID child cannot read or mint. Do not reintroduce a filesystem key and describe it as writer authentication.

### Required controls

- Parent writes and self-verifies a legitimate artifact.
- A same-UID child replaces/removes it and writes attacker-selected fields using its own process-local capability; the original parent and a fresh CLI must reject it.
- Reject unsigned legacy files, content edits, copied/renamed artifacts, malformed envelopes, and insecure metadata.
- Fixed early blockers that promise no artifact/status side effects must return before any artifact/key lookup or creation.

## Semantic contradiction and inventory probes

Documentation tests must vary natural clause boundaries and capability synonyms, not only known keywords. Use two layers: a direct helper matrix and representative mutations injected across every active classified document and executed through the real contract target.

Cover at least:

- adversative/causal/temporal boundaries: `but`, `although`, `though`, `even though`, `while`, `despite`, `whereas`, `because`, `since`, `as`, `even as`, `so`, `when`;
- coordination and punctuation: comma, `and`, `yet`, em/en dash, colon, slash, and parentheses;
- direct capability families: launch/start/spawn/invoke/activate/dispatch/run/execute/perform plus unambiguous synonyms such as boot, fork, initiate, trigger, schedule, call, create, enable, kick off, fire up, bring up, and hand off.

Do not treat the noun `dispatch` in phrases such as “production dispatch authority” as a capability verb. Pair the mutant matrix with a clean corpus containing explicit `no`/`never`/`cannot`, blocked-state descriptions, fixture-only execution, historical/superseded language, non-dispatchable state, and future target-state claims. Require every active document to remain clean.

For Markdown inventory, compare production extraction with an independent CommonMark renderer and HTML parser. Inventory `href` on every valid rendered element, not only `<a>`; include `<area href>` and `<link href>` controls.

Avoid globally splitting every comma or `and`: that creates false positives in benign capability enumerations. Split or flag coordinated clauses only when one clause has a high-confidence production activation verb and another has an explicit blocker/negation.

## Dependency-ordered pin refresh

Runtime changes often cascade. Recompute and patch pins from leaves upward, then verify the manifest:

1. leaf executables/helper scripts;
2. checker;
3. loop;
4. gate/lock consumers such as agent entrypoints;
5. delivery-status runtime closure;
6. deliver;
7. trusted-runtime manifest and production entrypoint inventory.

After the final source edit, rerun focused hostile probes, affected modules, a fresh isolated full suite, diff checks, secret scan, JSON/AST validation, index-empty checks, and cache/bytecode residue checks. Create the new exact boundary only after all validations are complete.
