# Nested private-runtime re-bundles and marker-closure probes

Related hardening references: `private-runtime-closure-and-policy-inventory-hardening.md`, `independent-pre-freeze-state-integrity-probes.md`, `nested-private-runtime-and-doc-closure.md`, and `pre-freeze-mode-operation-and-executable-closure-probes.md`.

Use this when a frozen candidate materializes scripts or executables into a private runtime and any child later creates another temporary bundle.

## Core invariant

Private-runtime closure is transitive, not inherited by intention:

1. Enumerate every authenticated script reachable from the private entrypoint.
2. Inspect those scripts for bare executable edges (`git`, `gh`, `jq`, etc.), including sourced shell helpers.
3. At **every** re-bundle boundary, copy the complete executable set needed by the reachable helpers. A parent bundle containing `git/gh/jq` does not protect a nested helper directory containing only `gh/jq`.
4. Build the exact child environment and resolve every executable under it (`command -v` or equivalent). Manifest equality and source hash checks do not prove the actual exec path.
5. Require each resolved path to be inside that child’s authenticated private bin. A system-path resolution is a closure failure even when the bytes happen to be trusted elsewhere.

## Explicit private-mode marker

Every private-runtime launcher must set and propagate an explicit marker such as `HERMES_BUSDRIVER_PRIVATE_RUNTIME=1`. Do not infer private mode only from `trusted-bin.exists()`.

Without the marker, removal or replacement of the private directory can make a nested resolver silently fall back to an original/system executable. The marker must make all of these fail closed:

- private bin missing;
- private bin is a symlink or dangling symlink;
- required entry missing;
- required entry is a symlink;
- required entry hash mismatch.

The marker must survive loop-to-checker, status-to-role-to-status, and any other nested subprocess boundary. Each reachable resolver must honor it; propagation alone is insufficient if a helper still invokes bare tools against a fallback PATH.

## Production-shaped negative probes

Run probes only in the isolated review lane.

### Re-bundle executable probe

1. Materialize the real parent bundle with the candidate’s production function.
2. Load the real nested checker from that bundle.
3. Reproduce the exact nested `tool_bin` construction.
4. Construct the exact child environment.
5. Resolve all required tools without making network calls.
6. Record `resolved_path`, `inside_expected_private_bin`, and the transitive script edge that requires the tool.

This catches the common defect where the nested bundle copies `gh` and `jq`, while a sourced helper still runs bare `git` and resolves `/usr/bin/git`.

### Missing-bin marker probe

1. Invoke the production materializer.
2. Intercept only its final child launch while the temporary runtime exists.
3. Record whether the private marker is present.
4. Remove or mutate the private bin inside the isolated temporary runtime.
5. Ask the real nested resolver which path it selects.
6. Pass only if it returns a structured fail-closed error; fallback to an original/system path is a finding.

Also keep positive controls for intact bundles so a failing probe cannot be dismissed as a broken harness.

## Review/report discipline

- Passing contract tests do not override a transitive-closure probe failure.
- Grade severity from reachable impact; do not downgrade merely because the escaped system executable is currently benign.
- Never label a review `end-closed` unless the final boundary verification actually ran after all candidate-facing operations.
- If interrupted before report hashing or end verification, report the findings and explicitly mark report sealing/end closure incomplete. Do not imply the requested attestation was completed.
