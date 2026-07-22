# Durable artifact truth and closed review lanes

Use this reference when a relay change validates, authenticates, stores, or retrieves run artifacts, signed envelopes, delivery-state files, or other durable state-machine records.

## 1. Define truth by production persistence, not code-shaped possibility

Partition every outcome into four classes before editing a validator:

1. **Production-persisted:** current production control flow can reach the writer and successfully replace the durable file.
2. **Production stdout-only:** production prints/returns the outcome but deliberately never creates a run identity or artifact path.
3. **Harness-only:** a non-installed test fixture removes a production blocker and can exercise dormant code, but those bytes are not production-valid durable state.
4. **Write-failure-only:** the producer constructs an envelope after the durable write has failed; those bytes may be printed but cannot exist on disk from that attempt.

The durable validator contract must contain **all and only class 1**. Do not admit an outcome merely because a helper can construct it, a dormant executor returns it, or a test harness can write it.

Common drift patterns:

- an early production blocker returns before run identity/artifact handling, while a harness bypasses it;
- an operation requires an argument and the missing-argument path never sets `write_artifact`;
- a write-failure envelope is treated as a persistable on-disk outcome even though atomic replace never happened;
- a producer emits a new blocked reason, but the validator truth table is not extended;
- validator tests enumerate the validator constant itself and therefore prove only internal consistency, not producer reachability.

## 2. Build producer/contract closure tests

Use several independent test shapes:

- **Production reachability tests:** execute the real production entrypoint, not the bypass harness. For stdout-only/early-blocked outcomes, assert no run identity, no artifact path, and no artifact directory.
- **Authenticated impossible-state negatives:** in one process, sign a structurally complete impossible envelope and prove both structural validation and durable lookup reject it. This prevents a missing key from making the test pass vacuously.
- **Authenticated positive control:** sign and retrieve a currently production-reachable envelope in the same test family.
- **Producer-reason closure:** derive producer literals independently (AST/source inspection or direct producer executions) and require them to be represented by the appropriate failure/completed/reconciliation sets. Guard the extractor against silently finding zero cases. Dynamic `error` variables and nested helpers need explicit coverage; a literal-only AST walk is not sufficient by itself.
- **Manifest closure:** after production bytes are green, update the derived executable digest in the same reviewed delta and rerun the dedicated pin test.

When an internal harness is still useful for redaction, dormant branches, or writer shape, label its artifacts as harness-only and never reuse them as a production-valid lookup positive control.

## 3. Preserve side-effect provenance on write failure

Treat artifact-write failure as two distinct outcomes:

- **Completed or uncertain side effect:** preserve the nested mutating run and original outcome; use a distinct post-side-effect sentinel at the outer level. The validator must reject recursive sentinel nesting and require the inner original outcome to be a known completed/reconciliation class.
- **No completed side effect:** clear the nested mutating run and emit the ordinary write-failure outcome.

Use a conservative producer-side completed-status superset if necessary to avoid erasing evidence. Keep the durable validator narrow. If a dormant operation is later unblocked without an atomic contract update, durable lookup should fail closed rather than silently grant authority.

## 4. Reconstruct RED when delegated transcripts are incomplete

If a delegated implementation ends at max turns or loses its RED transcript:

1. Start from the authenticated previous candidate/boundary.
2. Copy it to a runtime-only replay directory.
3. Overlay only the new test file(s).
4. Run the focused new tests against the previous production bytes.
5. Require semantic assertion failures, not collection, fixture, syntax, or environment errors.
6. Run the identical selector against the live candidate for GREEN.

Record both outputs outside the repository. This gives reproducible TDD evidence without trusting the delegate's narrative.

## 5. Close both live source and reviewer candidate

A valid review lane requires two independent identities at START and END:

- **Live-source closure:** branch, HEAD, index, dirty/untracked entry set, source digest, and reconstructed tree still match the authenticated boundary.
- **Candidate closure:** exact candidate path/type/mode/size/hash set still matches the boundary, with no extra or missing entry.

A live-source-only END check is insufficient. A reviewer may add `report.md`, caches, logs, or alter candidate bytes while the live source remains unchanged.

For reviewers that may ignore a read-only prompt:

1. Keep an official exact candidate for START/END candidate closure.
2. Make a separate byte-identical review view.
3. Verify the view against the original boundary **before** applying any immutability mechanism.
4. On macOS, prefer `chflags -R uchg <view>`: it blocks writes without changing the boundary's mode bits. Record and verify the immutable flag on a load-bearing file, and clear it explicitly before later cleanup.
5. Capture the model's final report through outer stdout redirection, outside the view.
6. At END, verify the official candidate exactly, re-run exact path/type/mode/size/hash closure on the immutable view, verify `uchg` is still present, and require no extras.
7. If the platform lacks a mode-preserving immutable flag and write bits must be removed, create and seal a **separate transformed-view boundary** after the permission change. Verify END against that transformed boundary; never compare intentionally changed modes to the original candidate boundary.

Changing permissions and then running an exact verifier built for the original modes is an expected closure failure, not evidence that the view is safe. Likewise, never count a report from a candidate-polluting lane as formally closed, even if its finding is useful diagnostic input.

### Pin verifier dependencies before formal START

A revision verifier must not dynamically read a mutable older verifier or helper after the boundary is sealed. Either make the revision verifier self-contained, or copy its base/helper into the review kit and pin its digest in the state. Before opening formal lanes:

1. compile/smoke the exact revision verifier;
2. run one disposable START/END lane and parse the actual JSON schema rather than assuming field names;
3. verify every helper path and helper digest the composite verifier will execute;
4. only then create formal lanes.

If a wrapper asserts replacement counts against a mutable base, a later base edit can make all lanes fail before candidate creation. Treat that as verifier-dependency drift: repair the kit and restart the affected START ceremony; do not interpret empty candidates or missing summary keys as source drift.

## 6. Validate reviewer output, not just process completion

A reviewer process exiting zero or creating the requested path is not a verdict. Formal acceptance requires all of the following:

- the report exists and is non-empty;
- it contains the required explicit verdict token/schema;
- runner metadata binds the expected model identity, prompt, immutable view, and report path;
- stderr and provider logs show no authentication failure, permission-confirmation dead end, silent truncation, or unapproved tool bypass;
- the lane still passes END source/candidate/view closure.

A zero-byte report with exit code zero is **incomplete**, not CLEAN. Likewise, provider smoke output such as a one-word response proves only provider reachability; it does not validate a formal review lane.

When a headless reviewer cannot safely read the immutable view, never solve that by disabling permission checks. A defensible no-tool fallback is an authenticated inline bundle:

1. Read only from the already-closed immutable view.
2. Before inclusion, verify every source file against the boundary's path/type/mode/size/hash ledger.
3. Include the complete ledger plus the exact prior-to-current diff and the current production/test spans needed for the review. State the scope honestly; other full-tree lanes still provide cumulative coverage.
4. Hash the canonical bundle, persist a sidecar, and make the runner verify that digest before launch.
5. Use strict/no-tool mode, capture stdout/stderr outside the view, and inspect provider logs to prove there were no tool calls or permission bypasses.
6. Bind the bundle path, byte count, digest, model identity, and `tool_bypass=false` in result metadata. Reject empty output even when the CLI exits zero.

This pattern preserves a reviewable chain from frozen source bytes to model evidence without granting a provider mutable filesystem access.

## 7. Review/freeze loop

- Any Medium+ finding blocks freeze.
- Finish every blocked revision's START/END and candidate closure before editing the live source; preserve it as immutable evidence.
- Apply the smallest next revision, refresh derived pins, rerun focused/full gates, build a new exact boundary, and create fresh independent lanes.
- Freeze only after all required pre-freeze lanes are clean and closed.
- Final frozen reviews must inspect the frozen package, not mutable live source or a previous candidate.
