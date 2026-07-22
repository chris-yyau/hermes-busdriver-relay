# Frozen relay defensive trust-boundary review

Use this reference for authorized, read-only reviews of frozen Busdriver Relay authority artifacts. It supplements the general frozen-review and security-review guidance with process, transitive-runtime, credential-file, and final recheck lessons.

## Hard gate and evidence discipline

1. Verify the manifest, patch hash and exact byte size, source archive hash, and reconstructed candidate tree before reading mutable checkout content. Any mismatch is an immediate blocker.
2. Reject archive entries that are absolute, traverse with `..`, or are symlinks, hardlinks, devices, FIFOs, sockets, or otherwise outside the expected regular-file/directory set.
3. Validate every snapshot record and reject extra files. Prefer an authenticated archive or immutable Git object tree over the mutable worktree.
4. Repeat every frozen hash, size, metadata closure, and candidate-tree check at the end. If a tool ceiling or interruption prevents the final recheck, the review is incomplete and the verdict must remain `BLOCK`; do not present the initial check as a final check.
5. Keep expected and actual values in the report both before and after review. Never reconstruct a truncated hash from memory.

## Closed-world runtime review

Treat runtime integrity as a transitive closure, not a list of top-level executables. Inventory every file that can be executed, imported, sourced, loaded as a schema, or passed as an extension/tool definition. Common omissions include draft wrappers, adapter tools and schemas, delivery/litmus helpers, interpreters and package trees, and scripts sourced by authenticated helpers.

A digest check followed by execution through the original pathname is still a check-to-exec race. Use descriptor-relative `O_NOFOLLOW` open, `fstat`, bounded read, digest verification, copy into a parent-owned generation directory, then execute only that materialized copy. Contract tests should compare an explicit or derived runtime dependency closure against the manifest and fail on every missing edge.

## Parent-only HMAC and marker semantics

- A parent-generated per-run HMAC key is useful only if no worker, verifier, Git subprocess, plugin helper, output, or persisted artifact receives it.
- Authenticate the full canonical baseline, including repo/worktree identity, HEAD/ref, index, tracked/ignored fingerprints, hooks, operation state, markers, and scope.
- HMAC authenticates content, not pathname safety; baseline I/O still needs descriptor-safe bounded handling.
- Do not accept postflight or release a lock until the full worker containment domain is terminated and a final marker/repo snapshot is stable.
- If same-user untrusted processes can write accepted markers after postflight, use authenticated marker metadata in a parent-private location or an equivalent brokered writer contract; mtime/content freshness alone is not authenticity.

## Process lifecycle negative probes

Test timeout and normal-success paths:

1. Direct child exits successfully while a descendant closes inherited pipes and keeps running.
2. Descendant ignores termination.
3. Descendant creates a new session/process group.
4. Descendant attempts a delayed repo or marker write after direct-child exit.

The gate must not proceed merely because `communicate()` returned. Process groups do not contain descendants that create a new session. Prefer an OS containment primitive or a disposable private worktree whose reviewed diff is applied by the parent only after teardown. Always clean up probe processes.

## Descriptor-safe file and credential handling

For baseline, marker, result, artifact, HOME/XDG/GH/Pi/OpenCode auth, and verdict files:

- traverse every parent with `openat` plus `O_DIRECTORY|O_NOFOLLOW`;
- open the final object with `O_NOFOLLOW` and, where relevant, `O_NONBLOCK`;
- `fstat` regular type, expected owner, private mode, `st_nlink == 1`, and strict size cap;
- bounded-read from that same descriptor; never `stat()` and later reopen by pathname;
- write via an exclusive temp file in an already-open directory, `fsync`, then descriptor-relative atomic rename;
- reject final/parent symlinks, hardlinks, FIFO, socket/device, oversized, world/group-readable, and inode-swap cases.

An auth-only private HOME is unsafe if the model's file/tool permissions include that HOME or its parent run directory. Keep credentials outside model-readable namespaces or broker provider access without exposing raw values.

## Bounded output and redaction

`capture_output=True` followed by tailing is not bounded capture. Stream output into fixed-size ring buffers, cap accepted bytes, redact before persistence, and apply recursive schema allowlists and per-field limits. Test cross-chunk credential patterns and verify no raw output reaches artifacts.

## Git, hooks, worktrees, and locks

- Use authenticated absolute tools or materialized copies; fixed PATH alone is not integrity.
- Disable system/global config, replacement objects, fsmonitor, external diff/textconv, hooks, prompts, paging, and startup injection where possible.
- Inspect per-worktree and common Git directories and effective worktree config, including `core.hooksPath` and command-capable config.
- A denylist shim for mutating Git/GH verbs is not an authority boundary; use a positive allowlist or mediated tool surface.
- Recheck HEAD/ref, index/tree, config, destination, markers, and worktree immediately before side effects; require CAS/server preconditions or keep the operation non-dispatchable.
- Locks need parent-owned state, atomic publication, token compare-delete, stable worktree identity, and fail-closed release reconciliation. Locks do not replace descendant containment.

## Reporting

Separate critical/high/medium blockers from non-blocking hardening. Each blocker needs `file:line`, condition, impact, exact repair, and negative regression. Never disclose credential values. Distinguish passing existing tests from new probes that expose missing invariants. End with exactly `PASS` or `BLOCK` only after the final frozen recheck is complete.
