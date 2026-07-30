# Untrusted Git Observation Sandbox Lessons

Read-only Git commands against an untrusted repository are executable and network-capable operations. Repository config, attributes, submodule config, and promisor/lazy-fetch state can select programs or transports.

## Required boundary

1. The caller defines every writable surface and persistent result channel before opening. A reviewer cannot exempt tool cache, spool, telemetry, HOME, installed skills, or scratch after the fact. If a literal no-write request has no non-persisting bounded output channel, stop and report the limitation before invoking a tool.
2. Authenticate absolute executable paths from a trusted manifest. Clear aliases, shell functions, ambient `GIT_*`, `PYTHON*`, askpass/editor/pager variables, and user-writable `PATH` entries before the first command; never fall back to an ambient binary or shell shim.
3. Dispatch local observers through an authenticated OS sandbox that denies **all filesystem writes**, network, and descendant execution across the repository, every Git dir/object store, worktrees, archives, HOME, installed skills, and other caller-forbidden roots. The sole network-enabled observer profile is a separately caller-approved GET-only client restricted to the intended HTTPS API endpoint while retaining the no-write/no-child boundary. `GIT_OPTIONAL_LOCKS=0` and drift seals are defense in depth, not a write boundary. Fail closed if the required profile is unavailable.
4. Rebuild a command-local Git environment: `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_ATTR_NOSYSTEM=1`, `GIT_OPTIONAL_LOCKS=0`, `GIT_NO_LAZY_FETCH=1`, `GIT_NO_REPLACE_OBJECTS=1`, and empty `GIT_ALLOW_PROTOCOL`; pin `core.attributesFile=/dev/null`, `core.fsmonitor=false`, hooks, signatures, diff/textconv, editor/askpass, credentials, recursion, and protocols. Reject local/worktree config includes, replacement refs, and unverified filter/diff drivers during plain-file preflight.
5. Keep submodule drift visible with `--ignore-submodules=none` only after every populated submodule has passed its own config/attributes/topology preflight and the broker allows only the authenticated exact recursive Git child. If strict no-child mode cannot satisfy that prerequisite, fail closed before top-level status rather than recursing into untrusted submodule configuration.
6. Reject split indexes, alternates, or reftable in strict mode unless every backing store is resolved descriptor-relatively and added to both the write-deny boundary and opening/closing seal.
7. In the Pi filesystem broker, audit effective local/worktree dynamic `filter.*.{clean,smudge,process}` and `diff.*.{command,textconv}` keys through the descriptor-bound Git anchor before every allowed Git verb. Keep the sandbox to close rename/ABA races.
8. Treat **any non-empty stderr** as an invalid observation even when Git exits zero. Discard partial stdout, return a fixed nonzero token, and apply the rule to every text, bytes, and NUL-framed dispatch seam.
9. Drain bounded stdout/stderr concurrently under one deadline; kill and reap the process group on timeout or inherited-pipe stalls. Never use an unchecked shell pipeline as evidence: run each stage separately, validate exit/stderr/complete bounded output, then pass bytes in memory. If a Git operation such as bundle verification requires an internal child, either broker only the authenticated exact child binary or report that verification unavailable; never silently weaken the no-child claim.
10. Enumerate observations from the production call graph, not a helper list. Every nested status/diff path requires the same boundary; reachability is part of severity.

## Descriptor-bound filesystem inventories

Start from a validated root directory descriptor. Reject absolute paths, `..`, duplicate normalized paths, symlink ancestors, and metadata paths that escape the root. Traverse with descriptor-relative no-follow operations. Open a regular file with `O_NOFOLLOW|O_NONBLOCK`, `fstat` before hashing, read exactly the bound size through that descriptor, then repeat `fstat` after hashing and require identical device, inode, type, mode, size, `mtime_ns`, and `ctime_ns`. Apply the same pre/post no-follow metadata equality around symlink `readlink`; record FIFOs, sockets, and devices by type without opening them. Include normalized relative path, kind, device, inode, mode, size, `mtime_ns`, `ctime_ns`, link text or regular-file SHA-256 in a NUL-framed row manifest. Record ignored paths separately from all non-ignored untracked paths. Any mid-read drift fails closed; `lstat(path)` followed by `open(path)` is not race closure.

Use exact raw/binary diff SHA-256 for byte seals; stable patch-ID is semantic deduplication only. Seal index bytes plus any backing store, refs/object inventories, pinned refs/merge-base, and the full worktree manifest. After the closing seal, perform no more candidate reads.

## Safe non-Git observers

- For in-memory Python parsing, authenticate an absolute interpreter and run it as `-I -S -B` with `PYTHON*` cleared inside the same deny-write/deny-child/deny-network sandbox. Feed the reviewer program on stdin and never import candidate modules; `compile(candidate_bytes, ..., "exec")` may check syntax only after this startup boundary is established.
- Read package/registry identities from already-known metadata bytes instead of executing a package manager. Query GitHub only through the shared sole network-enabled observer profile: a caller-approved authenticated GET-only client with extensions, helpers, pager, and local persistence disabled, restricted to the intended HTTPS API endpoint inside the write-deny/no-child sandbox. If either observer cannot satisfy its boundary, report a limitation rather than claiming closure.

## False-clean regression recipe

A sandbox can successfully prevent side effects while Git still fails open at the semantic layer:

1. Commit a file whose index and worktree bytes are `x`.
2. Add a repository-selected clean filter that emits `y` and arrange for the file to be rechecked.
3. Prove the control: ordinary Git executes the filter and reports the file modified.
4. Run the production sandboxed observer. Git may be unable to execute the filter, emit diagnostic stderr, exit `0`, and omit the modified path from stdout. The test may assert that a denial occurred, but production must not depend on one locale-specific phrase such as `Operation not permitted`.
5. The regression passes only if the production wrapper returns the fixed failure code/token, emits no usable stdout, and leaves the filter sentinel absent.

This test catches the important distinction between **side-effect containment** and **observation integrity**. A no-exec sandbox alone proves only the first.

## Verification discipline

Add hostile filter/signature/submodule/lazy-fetch regressions first and verify RED for the intended production reason rather than a broken fixture. Implement the boundary, refresh every transitive executable/script pin to a fixed point, and rerun the exact-byte full contract suite before freezing review evidence. When containment changes child environment construction, retain and rerun explicit legitimate-semantics checks for locale, `HOME`, and `TMPDIR`; fail-closed recognition should not require rewriting those values.

Any source-tree edit after a boundary is frozen—including a new regression or skill-source update—invalidates that boundary's reviews. Start a new repair round and obtain fresh closure on one immutable tree; never carry an earlier CLEAN verdict forward.
