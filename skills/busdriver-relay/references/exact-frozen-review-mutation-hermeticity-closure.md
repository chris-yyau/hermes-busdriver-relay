# Exact frozen review: mutation, hermeticity, and closure discipline

Use this when a frozen candidate needs an independently verifiable tests/docs/hermeticity review bounded by `START` and `END`.

## Ordering that preserves closure

1. `START`: authenticate the boundary, reconstruct the candidate outside the source, and record entry digest/tree identity.
2. Perform every candidate read, focused test, mutation probe, rendered-help invocation, and postflight identity check.
3. Inventory and remove reviewer-created basetemps, shadows, derived candidates, bytecode, and caches. Preserve only compact logs/evidence outside the candidate.
4. Freeze a report draft containing candidate identity, findings, commands/results, and evidence limitations.
5. Run live-source `END` as the final source-facing closure action.
6. After `END`, do not read or mutate the candidate. Generate only the final report, SHA-256 sidecar, and machine-readable delivery verification from the frozen draft and external START/END evidence.

Reserve enough tool-call budget for cleanup, draft, END, report, sidecar, and verification. If the run stops before END or delivery artifacts, report `INCOMPLETE`; never synthesize closure or hashes.

## Semantic-policy mutation testing

Do both layers:

- **Helper matrix:** test many natural clause boundaries and capability synonyms, plus a clean corpus for false positives.
- **Actual-target matrix:** clone the reconstructed candidate into a disposable derived tree, inject representative mutants into every active classified document, and run the real docs contract target.

If the active semantic corpus contains executable Python entrypoints, append mutants as comments (`# Production ...`). Appending bare prose makes those files fail syntax/help tests and produces false evidence that the semantic guard caught the mutant. Remove every derived tree after recording its process return code and summary.

Include reverse-order and causal clauses, not only the known controls: e.g. blocker-before-activation with `while`, `although`, `since`, or `as`. Include unlisted but unambiguous capability verbs such as `boots`, `schedules`, `forks`, `triggers`, or `kicks off`. A mutant that survives both helper and real-target checks is a guard/test finding; group equivalent survivors by root cause rather than multiplying findings.

## Independent CommonMark/HTML inventory

Do not validate the inventory with its own regex. Render each syntax fixture with an independent CommonMark implementation, parse rendered HTML hrefs, and compare those targets with the production extractor. Cover:

- inline and reference links, multiline labels/destinations, escapes, entities, fragments, and percent encoding;
- raw HTML attribute quoting/casing/newlines;
- link-bearing HTML elements beyond `<a>`, especially `<area href>` and `<link href>`.

For representative missed forms, inject the link into an active document in a derived candidate and run the actual docs target. Record both independent-renderer visibility and contract-suite survival.

## Process-scoped artifact authentication probe

Use a fresh private HOME/TMP/XDG and an unprivileged same-UID child:

1. Parent writes an authenticated artifact while its signing key exists only in memory.
2. Child records which parent paths are derivable from inherited environment/state and searches those private roots for persisted key material. Do not expose the key itself; comparison by a one-way key digest is enough for a standalone-key-file search.
3. Child removes/replaces the artifact, signs attacker-selected identity/freshness fields with its own process-local capability, and exits.
4. Verify that the original parent and a fresh real CLI status process both reject the child artifact with the documented fixed blocker.
5. Also verify that a fresh CLI cannot authenticate the parent's artifact after the writer process boundary.

A child accepting the artifact it signed in the same process is expected self-verification, not cross-process provenance. The security question is whether a trusted parent/fresh verifier accepts it. Independently check that active docs and rendered `--help` explicitly describe the process-scoped key and cross-process blocker; a help string that merely advertises “status lookup” is misleading if every fresh process fails closed.

## Real-tree hermeticity probe

Exercise the actual pinned package tree, not a tiny fixture only:

- Compute its independent digest and compare it with the trusted manifest.
- Record source file/directory/symlink counts.
- On the same filesystem, verify every regular destination file shares source device+inode (hardlink path), symlinks are preserved, and the shadow is removed after context exit.
- On a different filesystem, verify every regular file is on the destination device and shares no source inode, record file/symlink counts, and confirm cleanup.
- Wrap `copy2` so it materializes one destination file and then raises; verify the partially created shadow is removed.

Choose same/cross destinations by measured `st_dev`, not pathname assumptions.

## Existing full-suite evidence

Treat an earlier `N passed` sentence as producer evidence unless the raw process log, exit status, command, and exact candidate identity are preserved. Check timestamp ordering and residual runroot metadata, but state plainly when the raw log is absent. A scoped review may still run focused controls and independent probes without rerunning the full suite; do not upgrade the producer claim to reviewer-owned reproduction.

## Evidence integrity

For each decisive command preserve:

- child process return code;
- outer tool/wrapper return code when available;
- payload assertions over the generated JSON/log;
- exact candidate identity before END.

If an attempted probe is invalid (for example, syntax errors caused by bare prose appended to Python), exclude it from conclusions, fix the probe, and rerun it.