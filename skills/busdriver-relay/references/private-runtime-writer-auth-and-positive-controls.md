# Private-runtime closure, writer authentication, and positive controls

Use this reference when reviewing or repairing a relay runtime that copies authenticated executables/helpers into a private bundle, or when a durable run artifact claims writer-authenticated status.

## 1. Private-runtime closure is an executable graph

Treat every directly or transitively executed file as part of one closure:

- dispatcher → loop → checker;
- checker → nested shell helpers;
- agent launcher → gate / lock;
- each helper → Git / GitHub CLI / jq or other tools.

For every retained entry, verify before execution:

1. expected path is inside the private runtime;
2. parent directory is private and owned by the current UID;
3. entry exists and is not a symlink;
4. entry is a regular file with one link;
5. owner is the current UID;
6. mode is exactly `0500` for executable copies;
7. digest equals the authenticated manifest value.

Execute the retained private path, never the original mutable source after hashing. A marker such as `HERMES_BUSDRIVER_PRIVATE_RUNTIME=1` is only a mode declaration; the child must independently validate the adjacent private bin and required entries.

### Validate exactly the dispatched helper set

A nested guard should authenticate every helper the shell will execute or source, but not unrelated manifest entries that were never materialized into that runtime. Derive an explicit allowlist from the command's actual transitive helper set. Requiring an extra manifest entry can make every legitimate invocation fail closed even though tamper tests still pass.

## 2. Every tamper matrix needs a positive control

Before deleting, symlinking, chmodding, or modifying an entry, execute the complete unmodified private runtime and require success. Then run each mutation and require a deterministic fail-closed result before the shell/tool target executes.

Minimum pattern:

1. Materialize exact authenticated closure.
2. **Positive control:** invoke a harmless command through the guard; require exit 0.
3. Mutate exactly one property: missing, symlink, owner (where feasible), mode, link count, or digest.
4. Invoke again; require nonzero and a private-runtime integrity reason.
5. Use a sentinel to prove ambient `PATH` or the protected shell target did not run.

Without step 2, an over-broad or permanently broken guard can make all negative tests pass.

## 3. Same-UID disk permissions are not writer identity

A mode-`0600` HMAC key in a mode-`0700` directory is readable by a child running under the same UID. Such a child can mint a forged artifact that a later status process accepts. Filesystem owner/mode checks establish integrity against other UIDs, not provenance among same-UID processes.

Safe choices are:

- an external credential/signing broker with a trust anchor unavailable to the child;
- an OS-enforced process identity/capability boundary;
- a parent-process-only capability retained in memory, with all exec children receiving neither the key nor an inheritable descriptor.

If only a process-scoped capability is available:

- never write it to disk or environment;
- ensure descriptors are non-inheritable;
- allow verification only while the writer process retains the capability;
- make later cross-process status lookup explicitly fail closed (for example, `artifact_writer_authentication_unavailable`);
- document that disk artifacts are durable records but not durable writer-authenticated evidence.

Do not downgrade this to a generic `run_not_found`: expose the fixed authentication blocker truthfully.

### Required adversarial probe

1. Parent writes and verifies a legitimate artifact.
2. Exec a same-UID child with no inherited capability.
3. Child deletes/replaces the artifact and signs with its own process key or arbitrary MAC.
4. Parent must reject the replacement.
5. A fresh status process must report the authentication blocker, not accept the artifact.
6. Assert that no key file exists under the artifact/state tree.

## 4. Exact-boundary review discipline

- Any source edit, embedded-digest refresh, manifest pin update, fixture change, or documentation change invalidates the current boundary.
- Refresh pins in dependency order (leaf helper/checker → loop/agent → dispatcher → manifest), then rerun focused contracts and the final isolated full suite.
- Re-run static checks and rebuild a new exact boundary only after the last source change.
- Each review lane needs its own fresh START, independent reconstruction, checks/probes, final live END, report, SHA-256 sidecar, and sidecar verification.
- END must occur after all candidate reads. Report/sidecar writes may follow only outside the candidate.
- Reserve closure calls from the start (draft → END → final report → sidecar → sidecar verification). A provider filter, tool-limit stop, missing END, missing report, or missing sidecar is `INCOMPLETE`, never zero findings.
- Do not splice an earlier lane's technical evidence together with a later END to manufacture a clean ceremony.

## 5. Verification checklist

- [ ] Valid private runtime executes successfully.
- [ ] Missing/symlink/mode/link/digest mutations fail before target execution.
- [ ] Original executable replacement after authentication does not affect retained execution.
- [ ] Child validates marker plus adjacent private entries.
- [ ] Same-UID forged artifact is rejected.
- [ ] Cross-process lookup states the authentication blocker truthfully.
- [ ] No signing key is persisted or inherited.
- [ ] Dependency pins and manifest match final bytes.
- [ ] Fresh isolated suite, static checks, leak scan, and residue scan are clean.
- [ ] Exact boundary was built after the last source edit.
- [ ] Every review lane has START/END/report/sidecar closure.
