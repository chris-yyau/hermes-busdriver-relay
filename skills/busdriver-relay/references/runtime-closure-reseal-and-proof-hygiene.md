# Runtime closure reseal and exact-proof hygiene

Use this after security remediation changes any repo-local runtime byte that is named by a manifest, embedded digest, retained-helper bundle, production-entrypoint table, or exact AST/source fingerprint.

This complements `final-tree-review-triage-and-temporal-slicing.md`: that note decides what must be fixed; this note closes the changed-byte graph without manufacturing a false green result. For post-review reseal hardening patterns discovered during exact-tree security remediation (Bash function import, required-check false-clean cases, Git observation sandbox writes, CI portability, and evidence rebinding), see `exact-tree-review-reseal-security-lessons.md`.

## Treat digest closure as a directed execution graph

Do not equate a broad metadata inventory with the set of bytes one helper can execute.

For each consumer, derive and record:

- helpers it executes directly;
- helpers those children can execute transitively;
- metadata-only public entrypoints it merely reports;
- its own source, which must never appear in a self-pin.

Pin the executable transitive closure only. A metadata inventory may remain broader, but must not be copied wholesale into an execution-pin map.

A mutual edge such as `A -> B` and `B -> A` has no ordinary SHA-256 fixed point: writing either digest changes the bytes on the other side. Non-convergence is evidence of a graph-design defect, not an invitation to run more rounds or choose an arbitrary hash. Inspect the graph, remove metadata-only edges, or introduce a genuine acyclic trust root.

A concrete recurring failure shape is a smoke helper that correctly pins readiness while readiness over-broadly pins every public runtime entrypoint, including smoke. The repair is to narrow readiness to the helpers it and its children actually execute.

## Fixed-point reseal procedure

1. Freeze the exact remediation tree and ensure no unrelated writer is changing it.
2. Update manifest hashes for current producer bytes.
3. Derive every embedded consumer pin from the manifest's authoritative section; do not restate hashes in a second hand-maintained map.
4. Rewrite only assignments whose semantic value changed.
5. Re-hash files changed by step 4 and repeat.
6. Stop only when a full round changes neither the manifest nor any embedded pin.
7. Enforce a small round limit. On exhaustion, emit the changed edges and diagnose a cycle.
8. Run the manifest closure test independently. The updater's “converged” message is not verification.
9. Run the far-end literal test that requires every embedded digest literal to be claimed by one consumer mapping.
10. Run high-fanout consumers after closure: parent launchers, helper bundles, smoke, delivery/readiness, and adapter wrappers.

Manifest, consumer pins, and their closure tests belong in one reviewed transition. A commit whose source bytes changed while its pins still intentionally reject them is not an independently operable capability slice.

## Independent completeness surfaces

Avoid proving one hand-written list with another hand-written list.

Useful independent surfaces include:

- Git mode `100755` for the complete shipped executable surface;
- Git-tracked paths from `git ls-files` for source scanners;
- AST discovery of functions that both define and call a security mechanism;
- the manifest itself only after an independent producer set has been established.

For example, the manifested production entrypoint set should equal the complete tracked `100755` set in both directions. A Git-observer behavior matrix should equal the AST-discovered shipped consumers of `git_observation_argv`.

Mechanism-use discovery is **not** an independent bypass detector by itself. A new script that dispatches raw Git without defining or calling `git_observation_argv` is invisible to a scanner whose admission rule is “defines and calls `git_observation_argv`”; the matrix can remain green precisely because the bypass avoided the mechanism being discovered. Pair mechanism discovery with a separately derived dispatch/use surface and a mutation test that introduces a raw observation and requires the suite to fail. Report a mechanism-only matrix pass narrowly: it proves parity for compliant consumers, not absence of unobserved dispatches.

### Documentation-policy graph closure

Treat documentation authority as a graph, not a hand-maintained list. Parse inline links, reference definitions, HTML `href`, and single-backtick code spans whose entire content is one repo-local `.md[#fragment]` path. Reject glob-like code spans such as ``references/*.md`` as edges; they name a class, not a document.

Start traversal from declared roots and independently derived ADR roots. Do **not** add every classified active document to the root set, because that makes reachability self-proving. Require every reachable existing document to have one classification and every active classification to be reachable from a real root. Missing repo-logical references must be explicitly listed as external/unavailable exceptions so absent policy dependencies remain auditable rather than silently ignored.

## Keep verification scanners side-effect free

Loading extensionless Python scripts with `SourceFileLoader`, imports, or `runpy` can create `__pycache__` beside production scripts. A recursive scanner can then ingest binary `.pyc` files as alleged production consumers or crash while decoding them.

Defenses:

- set `sys.dont_write_bytecode = True` around source loading and restore it in `finally`, but treat this only as defense in depth: another test/reviewer process or a delayed loader can still create a transient cache;
- remember that `python -I` ignores `PYTHON*` environment variables, including `PYTHONDONTWRITEBYTECODE`; if bytecode suppression is part of the proof envelope, use `python -B -I ...` or an in-process `sys.dont_write_bytecode` guard. `pytest -p no:cacheprovider` only disables `.pytest_cache`, not `__pycache__`;
- audit wrapper commands separately from the direct CI command. A smoke runner may still launch `python -I -m pytest` without `-B`/`-p no:cacheprovider`, and an explicit `python -m py_compile` stage writes source-local cache artifacts by design rather than through ordinary import caching. Do not assume adding `-B` around an explicit compiler is sufficient: probe the exact command in a scratch tree. Prefer in-memory `compile()` validation or an explicitly external cache destination, and add a regression that runs the documented wrapper then asserts zero source-local `.pytest_cache`, `__pycache__`, and `*.pyc` artifacts;
- derive the default production surface from `git ls-files -z` (or another independent tracked-file source), not unrestricted `rglob()` and not a momentary assertion that `__pycache__` is absent;
- let scanner mutation tests inject explicit extra candidate paths into the parser instead of depending on untracked temporary files being auto-discovered by the production inventory;
- exclude cache/binary outputs by construction, not merely by suffix guesses;
- remove rebuildable cache artifacts and re-check the tree before exact evidence;
- ensure focused tests do not dirty the candidate they are meant to attest.

When a full suite fails because a transient `.pyc` appears only under suite ordering or concurrent read-only reviews, do not dismiss it as order noise. Reproduce the producer/consumer order, instrument per-test setup/call/teardown if needed, fix the loader, and independently make the inventory immune to untracked rebuildable artifacts. The latter is the durable correctness property.

## Exact provenance tests after a reviewed seam changes

Security scanners may allow a forwarding launcher only when its full source hash or function AST hash matches an approved value. When a legitimate remediation adds stdin bytes, timeout parameters, or a credential wrapper:

1. inspect the new function and its data flow;
2. recompute only the affected full-source/AST fingerprints;
3. update the explicit child-command inventory;
4. retain mutation tests proving alternate commands, reordered validation, extra dispatch, and different forwarded variables still fail;
5. never replace an exact fingerprint with a broad name-based exemption merely to make the suite green.

An absolute root-owned child such as `/usr/bin/head` should be enumerated explicitly if introduced. Positional `$@` forwarding is acceptable only inside an exact-source-bound wrapper whose caller validates the executable and environment.

## Host-sealed pin refresh as a prerequisite slice

When an OS/toolchain update changes root-owned system bytes, keep the pin refresh separate from an unrelated semantic policy change whenever the graph permits it.

1. Audit each changed target on the intended host: canonical path, regular/non-symlink shape, owner/mode, platform signature verification, version, and SHA-256. Do not repin user-managed optional tools merely because they also drifted.
2. Update only the audited producer pins and their complete transitive consumer DAG; run closure tests, high-fanout focused tests, and the exact full complement.
3. Merge and post-merge verify this narrow prerequisite first.
4. Rebase the semantic candidate onto that exact main tree, preserve both semantic edits and the new host pins, and recompute the digest DAG again. Prior closure evidence does not survive the rebase.

External scanners must compare a host-sealed pin to the intended host, not to the scanner's own similarly named binary. A Linux review container hashing its `/bin/bash` cannot invalidate a macOS target pin; answer with target-host ownership/signature/digest evidence rather than changing the manifest to the scanner runtime.

## Portable vs host-sealed contract split

A workflow or job name such as "portable contract tests" is not evidence by itself. When host-sealed runtime tests are moved to a self-hosted macOS lane, independently scan the remaining portable lane for host assumptions before calling the split complete.

Audit the non-ignored portable test set for markers such as:

- user-home paths (`/Users/<name>/...`), local tool anchors, or checked-in operator paths;
- macOS-only system paths (`/Library/Developer/CommandLineTools/...`, `/usr/bin/sandbox-exec`);
- SIP / file-flag assertions (`st_flags`, `SF_RESTRICTED`) and other Darwin-only permission semantics;
- tests that require a locally provisioned binary instead of a repo fixture.

Treat an explicit filename allowlist as only the start of the audit. Trace every allowlisted test through the production scripts and helpers it actually invokes. A test file can look platform-neutral while calling a helper that validates an absolute macOS binary against a host-specific SHA-256 before any assertion runs; the local allowlist passes on macOS while the required Ubuntu lane deterministically exits during setup. A contract that merely asserts the workflow contains the chosen filenames and `-B -I` flags does not prove those filenames are portable.

For host-pinned binaries in a purported hosted lane, compare the embedded pin with the actual hosted-image artifact rather than with the review host. Prefer a real run in the matching runner/container. When that is unavailable, use the authoritative runner-image inventory to identify the exact package version, download that package, extract the binary, and compare its format and digest. Record the image/package version and hash so the portability result is reproducible rather than an inference from path spelling alone.

Any host-sealed test must be skipped/guarded on non-macOS or excluded from the Ubuntu lane and covered by the host-sealed required check. Otherwise the required-check lock may be locally clean while the hosted portable job is guaranteed to fail. Keep a small source-only workflow-contract test in the portable lane if needed; do not keep an entire host-sealed runtime test file there merely because one test in that file inspects workflow YAML.

## Credential-bearing shell lane

Keep Apple-shim validation and credential-bearing GitHub calls as separate functions.

- The credential-free prevalidator must build an empty environment before invoking `/usr/bin/python3 -I -c`.
- The credential-bearing wrapper may capture only explicit token variables, then clear the full inherited environment and re-export the approved tokens plus fixed `PATH`/locale.
- Do not forward `GH_HOST`, `GH_REPO`, proxy variables, loader/startup variables, arbitrary Git variables, or ambient `HOME` as a credential source.
- For remote authority checks, require an explicit complete repository identity (for example, both `--owner` and `--repo`) before resolving or invoking the credential-bearing client. Do not infer the target from ambient/local Git state and do not turn unresolved identity into a clean skip.
- Bound every captured GitHub payload before command substitution can allocate it; use a limit-plus-one convention and treat oversize/nonzero as fail-closed.
- Required-check comparison must preserve both legacy `contexts[]` and app-bound `checks[].context/app_id`; reducing the server response to names loses authority binding.

Tests should extract and execute the production shell functions with hostile ambient variables, rather than only searching for reassuring strings.

## Bind evidence to a dirty candidate exactly

A remediation tree may be intentionally uncommitted while defects are still being fixed. Bind evidence to its exact bytes without touching the real index:

1. Create a temporary `GIT_INDEX_FILE` under the pinned runtime/evidence directory.
2. `git read-tree HEAD` into that temporary index.
3. `git add -A` with the temporary index so tracked modifications **and untracked candidate files** are included.
4. Record `git write-tree` as the virtual candidate tree hash.
5. Generate the review patch and numstat from `git diff --cached HEAD` using that same temporary index.
6. Hash the patch, numstat, and eventual full-suite log; remove the temporary index and verify the real index is unchanged.
7. Recompute the virtual tree after the suite. A matching hash plus a clean generated-cache check binds the log to the same candidate bytes.
8. When piping a full suite through `tee`, invoke `/bin/bash -lc`, enable `set -o pipefail`, and capture `${PIPESTATUS[0]}` immediately after the pipeline. Hermes terminal sessions may otherwise use zsh, whose `PIPESTATUS` semantics differ; a blank/scalar value can manufacture an incorrect exit sidecar even when the pytest log itself is valid.

A normal working-tree `git diff` omits untracked files and is therefore not an exact candidate archive. Likewise, a full suite that starts before README/status/test changes and finishes after them is mixed-tree evidence: stop it, update the candidate truth, recompute the virtual tree, and restart from zero.

Independent reviews must name or otherwise prove the final virtual tree they reviewed. If even test-only bytes change after review dispatch, verify the reviewers observed the final tree or re-dispatch; do not call stale reviews exact-tree reviews.

## Evidence and documentation order

Use this order:

1. focused RED -> GREEN tests for each confirmed defect;
2. fixed-point runtime reseal;
3. affected high-fanout suites;
4. completeness/security scanner suites;
5. update in-repo README/status/docs to a truthful **pre-seal** state (for example: focused TDD and manifest closure complete, full exact suite/reviews still pending), then freeze the candidate;
6. compute the virtual tree and run the clean exact-tree full suite;
7. run independent reviews against that exact tree;
8. write worktree-external evidence sidecars, hashes, and restack plans; re-slice/restack only after the accepted remediation boundary is stable.

Any in-repo status/doc/test edit after step 6 invalidates the exact-tree suite and reviews. Either keep the candidate's status conservatively `BLOCKED / UNSEALED` while external evidence records the later result, or make the truthful in-repo update and repeat the exact-tree proof from the new virtual tree.

Until step 6 succeeds, current status must say `BLOCKED / UNSEALED`. Historical test logs and reviews belong under an explicitly superseded/provenance heading and must not be presented as evidence for current bytes. README/status inventories should be mechanically checked against the independent production surface; never list a file that does not exist merely because a prior slice review mentioned it.

## Pitfalls

- Treating a fixed-point updater's output as a passing closure test.
- Letting metadata-only entries create digest cycles.
- Continuing reseal rounds after non-convergence instead of inspecting the graph.
- Running full-suite claims before exact provenance fingerprints and child inventories are refreshed.
- Weakening a scanner to admit a new launcher without binding its exact implementation.
- Letting tests create bytecode/cache files in the tree they attest.
- Using ordinary `git diff` as an exact archive when the candidate contains untracked files.
- Treating test-only or docs-only edits as evidence-preserving after a full-suite/review dispatch.
- Accepting independent review summaries that do not bind themselves to the final virtual tree.
- Calling old evidence “latest” after runtime bytes changed.
- Creating a missing test filename from a reviewer narrative instead of checking the final tree and classifying it as temporal packaging debt.
