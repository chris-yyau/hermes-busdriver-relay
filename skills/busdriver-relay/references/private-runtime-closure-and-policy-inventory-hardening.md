# Private Runtime Closure and Policy-Inventory Hardening
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference when a frozen Busdriver delivery review finds that a trusted entrypoint can still reach mutable plugin bytes, ambient executables, weak documentation classification, or a self-referential package-identity test.

## 1. Preserve the blocked snapshot

- A Critical/High/Medium finding makes that frozen version `BLOCKED`; do not rewrite its source, manifest, report, or verdict into a clean state.
- `BLOCKED` stops delivery immediately but does not end evidence collection. Let every already-dispatched lane close (or explicitly cancel and replace it), harvest all accepted findings, and only then freeze the repair generation. Freezing vN+1 while a vN lane is still running invites a late finding that forces avoidable vN+2 churn.
- Create the repair worker from a verifier-rebuilt candidate of the blocked snapshot, not from an uncertain dirty source tree.
- Any source-byte repair requires a new versioned manifest, patch, deterministic source tar, candidate tree, and all-new review verdicts.
- A completed delegation notification is only scheduling evidence. A review lane counts only when its report, report digest, start verifier, end verifier, and exact identity comparison all exist.

## 2. Close the entire executable runtime graph

Authenticating the top-level helper is insufficient. Trace every subprocess reachable before policy boundaries, mutation dispatch, lock acquisition, and credential use.

For a private runtime:

1. Declare an exact source-to-digest inventory for every reachable helper script.
2. Read and authenticate the complete inventory before materializing any member; fail on missing, extra, symlinked, non-file, or digest-mismatched entries.
3. Write authenticated bytes into one private temporary runtime with non-writable executable modes such as `0500`.
4. Do not execute repository/plugin-worktree resolvers from the private path. Add an explicit non-executing status mode when the status envelope only needs declarative data.
5. Bare `git`, `gh`, `jq`, or other tools in transitive helpers are still ambient execution. Authenticate every pinned executable needed anywhere in the nested graph, re-hash the bytes actually read, copy those bytes into a private `trusted-bin`, and prepend only that private directory to a minimal system-shell PATH. Once a private runtime exists, each nested helper must select the sibling private copy for its final `argv[0]`; executing the original absolute source path after hashing it is still TOCTOU. A missing, symlinked, or mismatched private entry must fail closed—never fall back to the original path. Inventory all transitive tools rather than only the obvious Git/GH pair: shell helpers may also require `jq` or another parser.
6. Keep `PYTHONPATH`, `PYTHONHOME`, shell startup variables, unsafe Git config, and arbitrary caller PATH out of the child environment.
7. Test production control flow with a hostile plugin resolver and hostile executable sentinels across every operation that reaches the helper—not merely a mocked helper function.
8. Do not derive the closure solely from a helper's self-reported capability map. Build a second reachability inventory from actual subprocess edges and CLI forwarding; a private relay-role helper can still invoke a status helper without its non-executing flag and thereby escape into mutable plugin bytes.

Two useful RED contracts:

- Put a sentinel `resolve-cli.sh` under an isolated synthetic `HOME`, launch the real top-level plan/status path with the relay-role option under `env -i`, and assert the sentinel is never created. Record the private helper path from the returned envelope so the test proves the private copy—not the source checkout—was the caller.
- Replace expected trusted executables with synthetic bytes and require the spawned private child to observe separate `0500` copies at the first PATH component. Also intercept the real nested runner and assert its final `argv[0]` is inside that private `trusted-bin`; a digest check followed by execution of `/usr/bin/git`, a Homebrew/Cellar path, or any original source pathname is still hash-then-execute TOCTOU and must fail.

## 3. Make documentation authority fail closed

Do not use a loose regex plus an allowlist as the sole policy inventory.

- Start from explicit authoritative roots and recursively discover repo-internal Markdown targets.
- Canonicalize root-relative and source-relative paths, fragments, angle destinations, reference definitions, URL encoding, HTML entities, and backslash escapes.
- A deterministic scanner must handle nested link labels, escaped closing brackets in reference labels, reference destinations continued onto the next legal line, and balanced/escaped parentheses; all are legal CommonMark bypasses for simple regexes.
- Require every discovered target to belong to exactly one class. Validate uniqueness before converting lists to sets; reject duplicate classification, overlap between internal and external classes, unclassified targets, and missing targets.
- `external_or_unavailable_references` is not a downgrade escape hatch: reject any entry whose canonical target currently exists inside the repository, even if a reviewer moved it out of an internal list in the same patch.
- Run semantic activation mutants over the full union of every non-historical internal class, not only a small hand-picked policy subset. Include an internal-to-external reclassification mutant and prove the semantic cases do not disappear silently.
- Historical classification is not a bypass: require an unmistakable `HISTORICAL`, `SUPERSEDED`, or `NON-PRODUCTION` banner within the first few lines.
- Add mutants for new links, `./` and `../` links, fragments, inline/reference/HTML forms, escaped reference labels, next-line reference destinations, angle destinations, nested labels, balanced/escaped parentheses, duplicate/cross-class membership, internal-to-external movement, and historical-without-banner. When possible, confirm disputed syntax with a CommonMark implementation and require a concrete rendered link before assigning a blocker.

## 4. Verify package-tree pins independently

A test that compares a source constant with the same manifest constant is self-referential.

For a package-tree digest that includes symlinks:

1. Resolve the manifest's actual production executable and package root.
2. Independently canonicalize every relative path, entry type, regular-file bytes, and raw symlink target text.
3. Compare that independent digest with the manifest pin.
4. Call the real production trust resolver for a clean control.
5. Copy the real package tree once into an isolated external shadow tree (preserving symlinks). Register cleanup immediately—before digest or verifier assertions—using a context manager or test finalizer. The unchanged shadow must pass with the production pin unchanged.
6. Mutate one symlink target, then replace a symlink with a regular file containing identical target text; both must fail through the real production verification flow.
7. Clean explicitly on success and assert the shadow root is absent. Also force an assertion/exception path and prove registered teardown removes it. A test that retains a multi-hundred-MiB/large-inode shadow after passing is a state-integrity finding, not harmless pytest behavior.

## 5. Freeze and review discipline

Before freezing, use a fresh external `HOME`, `TMPDIR`, XDG directories, Git config, and bytecode/cache locations. Run affected contracts, the full suite, hostile sentinels, diff checks, syntax parsing, secret scanning, and no-cache checks. Refresh any current-tense installed-plugin/version evidence immediately before the final run.

A wrapper smoke command may invoke pytest without `-p no:cacheprovider` even when the direct suite is hermetic. After every smoke/full run, inspect the filesystem inventory—not only `git status`, because ignored `.pytest_cache`, `__pycache__`, or `*.pyc` entries can be invisible—and remove/verify all source-local cache material before computing the frozen tar or record set. Size the wrapper's pytest timeout from the measured full-suite runtime plus explicit margin, not from a historical constant; pin that minimum in a regression contract. A smoke envelope run on the intentionally dirty repair worker may correctly fail only at Busdriver's dirty-worktree preflight even when its embedded suite and other probes pass. Record that distinction, then require the complete smoke envelope to pass on the clean verifier-rebuilt frozen candidate. Recompute every embedded trusted-runtime digest after the last production-script/status/help change, in dependency order (leaf helper → parent helper/loop → top-level delivery entrypoint → manifest), then rerun the manifest contracts; hash cascades are part of the source change, not post-freeze bookkeeping.

Any reviewer that observes source drift between its start and end boundary cannot issue a reusable verdict. Preserve concrete findings that still reproduce, but mark the lane stale/incomplete and dispatch a fresh review against one exact immutable digest after repairs settle.

After freezing:

- Verify manifest, binary patch, deterministic tar, record counts, base/head/branch/remote, and candidate tree at start and end.
- Rebuild a candidate independently and rerun the full suite there.
- Dispatch correctness/state-integrity, defensive trust-boundary, and tests/docs/hermeticity as separate read-only lanes against the same manifest digest.
- Keep the main disposition `PENDING` until all three reports and sidecars are independently verified; any blocker starts a new repair/freeze version.
