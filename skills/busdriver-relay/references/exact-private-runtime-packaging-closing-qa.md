# Exact private-runtime packaging closing QA

Use this reference for a bounded, local-only review of a frozen runtime bundle when the required output is a formal START/END-closed report and SHA-256 sidecar.

## Ceremony

1. Before START, inspect only the supplied boundary and external verifier implementation. Resolve the actual pytest runner without reading the candidate. Also resolve the exact START/END CLI syntax now; do not discover END arguments after START.
2. Run verifier `START` into a private lane and require agreement between JSON `ok=true`, stderr expectations, and outer rc=0.
3. Perform all candidate reads, focused tests, and benign probes between START and END.
4. Remove reviewer residue and independently recompute the candidate inventory digest. It must exactly match the boundary before END.
5. Only after that postcheck succeeds, freeze the report draft before END. The draft must contain the *actual* postcheck outcome (entry count, digest, and empty extra/missing/mismatched/unsafe/residue sets), boundary identity, provisional verdict, severity counts, findings, focused evidence, operational exclusions, and limitations. Do not run the postcheck and draft write in parallel: after END, a draft that merely says the postcheck is “expected” or “required” cannot truthfully support the final report under the draft/START/END-only rule.
6. Run verifier `END` as the final source-facing operation; do not pass the candidate to END. Require payload/process agreement.
7. After END, read neither source nor candidate. Finalize only external artifacts, create `report.md.sha256`, and verify it with `shasum -a 256 -c`.

### Verifier invocation pitfall

For the current `review-verifier.py` interface, the accepted shapes are:

```bash
python3 review-verifier.py START --lane "$lane" --candidate "$candidate" --output "$lane/start.json"
python3 review-verifier.py END   --lane "$lane"                         --output "$lane/end.json"
```

`END` recovers the START record from the lane; it does **not** accept `--start`. If the interface may differ, inspect `--help` or argparse source before START. A parser-error retry is operational rather than candidate evidence, but avoiding it preserves a cleaner closing transcript and ensures the successful END remains the final source-facing operation.

A closed lane with nonzero Critical/High/Medium findings is `BLOCKED`, not `INCOMPLETE`. Missing END, report, sidecar, or sidecar verification is `INCOMPLETE`.

## Pytest containment and retry pattern

- Put `--basetemp` outside the candidate and create its parent directory first; pytest does not create missing ancestors for a nested basetemp.
- Use `-p no:cacheprovider` **and** `PYTHONDONTWRITEBYTECODE=1`. Disabling pytest's cache provider does not prevent imported test modules from creating `__pycache__/*.pyc`.
- If the runner fails before collection because the reviewer harness was invalid, record it as an operational note, fix only the harness, and rerun the same focused control once. Do not count the failed launch as candidate evidence.
- Before END, inventory the candidate against boundary entries, remove only reviewer-created residue, and recompute the canonical entry digest. Preserve the successful post-cleanup identity result outside the candidate.
- Never derive a full-suite node list from a tool-returned stdout string that may be capped or truncated. Redirect `pytest --collect-only -q` stdout to a private-runtime artifact inside the command, require the command's outer rc to be zero, and parse the file itself. Cross-check the parsed node count against pytest's collection summary (and the prior known count when available), then preserve/hash the collection artifact. A suspiciously small list is an evidence failure, not a smaller suite.
- Retry only after a concrete failure. For an isolated environmental/flaky node, rerun that exact node once in a fresh private runtime; if it passes, record the initial failure plus successful retry and stop retrying. Do not silently promote a failed partition to an all-green full-suite claim.

## Deterministic runtime-closure probes

Probe the production launcher/materializer, not only resolver helpers. Every negative matrix needs a valid positive control first.

For a parent → loop → checker chain, test at least:

- valid private checker dispatch;
- missing and symlink entries;
- exact mode drift such as `0500` → `0700`;
- `nlink == 2` via a benign hardlink;
- digest/content mismatch;
- adjacent private-bin absence while the private-runtime marker is set;
- post-authentication source replacement;
- replacement in the interval after parent hashing but before the child opens the path.

The last probe distinguishes a retained-copy design from hash-then-execute. A safe deterministic shape is:

1. create trusted checker bytes and set the expected digest;
2. call the real launcher function;
3. intercept only final `subprocess.run` dispatch;
4. replace the checker path with harmless bytes that write a sentinel and valid JSON;
5. invoke the real subprocess;
6. fail the QA if the sentinel appears or the replacement result is accepted.

Treat mode, owner, link-count, directory-mode, and digest checks as distinct. `is_file()` plus digest is not a complete private-runtime metadata contract.

For nested shell helpers, require a child-side guard immediately before `/bin/bash` dispatch to validate the exact reachable set: Git/GH/jq plus each sourced/executed helper, all regular non-links, current-UID-owned, `nlink == 1`, exact `0500`, in `0700` directories, with pinned digests.

## Writer-authenticated artifacts

For process-scoped writer capabilities, preserve these independent controls:

- parent accepts its own legitimate artifact;
- same-UID child replacement is rejected by the parent;
- fresh process rejects both parent and child artifacts with the documented fixed blocker;
- no key file exists under state/artifact roots;
- help/docs disclose the process-scoped and cross-process boundary.

Passing these controls does not repair unrelated runtime packaging defects; report them as non-findings separately.

## Raw full-suite evidence

A prose claim such as `N passed` is producer evidence only. To authenticate it, require an explicit raw-log path, command, outer rc, exact candidate identity, and a verified SHA-256 sidecar. Do not infer a log location from a leftover pytest basetemp or broad filesystem search. If the exact review kit/boundary does not supply the path and sidecar, state that the claim was not promoted to reviewer-authenticated evidence; do not rerun a prohibited full suite merely to fill the gap.

## Transitive hash-pin closure before broad gates

When a trusted runtime component changes, close the digest chain in dependency order **before** running broad delivery tests. For a checker/loop/deliver chain:

1. compute the final checker digest and update every loop/deliver/manifest pin;
2. compute the resulting loop digest and update every deliver/manifest pin;
3. compute the resulting deliver digest and update the manifest;
4. run the manifest contract and focused launcher tests;
5. only then run affected and full suites.

Otherwise a single stale child pin can make dozens of unrelated delivery tests fail early with the same runtime-integrity blocker. Treat that pattern as one hash-closure root cause, not many regressions; synchronize the chain and rerun the unchanged suite.

## Warning-free producer logs

A zero-exit pytest run with an unraisable/resource warning is not ideal frozen evidence even when every test passed. Remove deterministic harness noise and regenerate the exact-source raw log before boundary creation. Cleanup test doubles should preserve production-call compatibility—for example, a monkeypatched `shutil.rmtree` stub must accept both positional and keyword arguments so `TemporaryDirectory` finalizers cannot emit late warnings. The final raw log and sidecar should show the pass count without a warnings section.

## Formal report minimum

Include:

- exact boundary path/SHA, source digest, candidate tree, and any intentionally surprising boundary field;
- START and END outer rc, payload status, entry counts, and matching snapshot digest;
- focused commands/counts and raw evidence paths;
- operational notes excluded from candidate conclusions;
- root-cause findings with exact severity accounting (`C/H/M/L`);
- explicit `CLEAN`, `BLOCKED`, or `INCOMPLETE` disposition;
- report SHA-256 and successful sidecar verification.
