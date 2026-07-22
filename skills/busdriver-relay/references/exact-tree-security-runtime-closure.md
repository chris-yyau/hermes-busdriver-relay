# Exact-tree security/runtime closure lessons

Use this playbook when reviewing a supplied Git **tree object** rather than a trusted branch or worktree.

## Identity and materialization

1. Treat worktrees, refs, repository config, alternates, and candidate evidence as untrusted observations—not delivery identity.
2. Seal the protected footprint before Git inspection. Include the source worktree, worktree/common Git metadata, refs, object stores, and candidate envelope. Resolve `objects/info/alternates` and any replay/repair object stores **transitively before the first object read**: sealing a bare repository that merely points at external stores does not seal the object closure. If a store is discovered late, add and seal it before reading its bytes, and disclose that the original opening footprint was incomplete.
3. Persist both an aggregate seal and a sorted per-entry manifest so an opening/closing mismatch is diagnosable without another candidate read. The semantic layer should bind relative path, object type, executable mode, regular-file size/content, and symlink target; do not use directory `st_size` as semantic identity because filesystems may change it without a tracked-content change. Keep directory mtimes and other mutable metadata in a separate temporal seal.
4. Copy required object stores to private scratch without hardlinks, preserve metadata, and verify source/copy path sets, file types, modes, sizes, and content digests. Assert copied regular files do not share `(device, inode)` with their sources. After verification, remove copied `info/alternates`/`info/http-alternates` so private Git cannot escape back to protected stores.
5. Resolve the target only in a private Git environment with system/global config disabled, a private `HOME`, hooks disabled, replacements and lazy fetch disabled, closed protocols, and no inherited Git dir/index/object variables. A private `--git-dir` alone is insufficient when the object database is supplied with `GIT_OBJECT_DIRECTORY`/`GIT_ALTERNATE_OBJECT_DIRECTORIES`; record and pass both parts explicitly. For per-layer provenance, do not test only loose object paths: packed objects will appear absent. Enumerate each copied store independently with `git cat-file --batch-all-objects --batch-check='%(objectname)'` and map required/reachable OIDs against those sets.
6. Independently parse/materialize every commit/tree/blob, verify each Git object hash, rebuild canonical tree bytes, and require the rebuilt root hash to equal the supplied tree.
7. Compare the supplied source worktree and exact checkout independently with the materialized target. If the source worktree differs, do not run target tests there: record the exact path/mode/blob differences, test only a scratch copy of the private materialization, and treat the source mismatch as a provenance/content finding rather than quietly substituting it for the target. In a direct checkout leaf inventory, exclude root `.git` whether it is a directory or a gitfile; filtering directory-form `.git` alone creates a false extra-leaf mismatch.
8. If tests require a repository, copy the materialization to a separate test tree, initialize a private `.git`, stage it, and require `git write-tree` to reproduce the exact target hash before committing or testing. Never initialize Git inside the sealed materialization itself.
9. If Git-dependent tests expect `HEAD`/`git ls-files`, build a **synthetic local commit** from the reviewed tree in the disposable test tree rather than trusting ambient refs: run with `env -i`, unset all `GIT_*` dir/index/object variables, `git init`, `git commit-tree <target-tree>`, `git update-ref`, `git symbolic-ref HEAD ...`, then `git reset --mixed HEAD`. Verify `git rev-parse HEAD^{tree}` equals the supplied tree, `git fsck --strict` passes, `git ls-files` has the materialized entry count, and `git status --porcelain --untracked-files=all` is empty. A surprising `--show-toplevel` outside the scratch tree or `fatal: bad object HEAD` usually means inherited Git environment/worktree state leaked into the harness; fix the harness, not the candidate.
10. **Never copy or repoint an existing `.git` directory as the executable-test repository.** Even a private byte copy can retain `core.worktree`, linked-worktree administration, or other path-bearing config that points back to the protected checkout. A test launched from the scratch filesystem can then make Git resolve the original checkout, producing false inventory failures or mutating protected directory metadata while candidate bytes later compare equal. Before the first test, remove the copied `.git` marker, initialize a fresh scratch-local repository, stage the exact materialization, and require all of: `git rev-parse --show-toplevel` equals the canonical scratch test root; `git write-tree` and `HEAD^{tree}` equal the reviewed tree; and `git ls-files` has the expected nonzero entry count. Run a tiny inventory probe before the real selector.
11. If a contaminated exploratory harness may have reached a protected checkout, do not repair mtimes or silently retry into a PASS. Complete the closing content and metadata seals, localize the changed rows, and latch a strict-footprint blocker even when the independent tree rehash and every file digest remain exact. Report semantic identity and temporal-metadata stability as separate truths.

## Focused adversarial closure

- Trace authority→target changes through their callers rather than reviewing only edited helpers.
- For nested broker subprocesses, verify `outer deadline > inner deadline + owned-group cleanup budget`; preserve a short deadline for non-broker operations.
- Probe timeout, output-overflow, successful-leader-with-descendant, and `BaseException` paths. A success path must kill descendants before reaping the process-group leader.
- On Apple `/usr/bin/python3` 3.9, run the real production interpreter—not only a newer pytest venv. Exercise the `kqueue`/`KQ_NOTE_EXIT` fallback with immediate exits plus success, timeout, and overflow descendants, and assert descendant death.
- Independently inventory every production Git observer. Do not let a test discover observers only by looking for the helper/pin whose completeness it is supposed to prove. Confirm all status-authority paths force `core.fileMode=true`, complete untracked/submodule observation, closed transports, and fail-closed stderr/return-code handling.
- Test hostile local/includes/worktree config, filter/diff programs, Git self-exec aliases, pager/credential/transport influence, and output bounds at the real dispatch boundary.

## Embedded fingerprint self-consistency

Security scanners often exempt a narrowly approved wrapper only when its exact SHA-256 or canonical-AST fingerprint matches. Whenever production source changes:

1. Recompute every embedded source/function fingerprint from the **same exact tree**.
2. Run both the positive approval test and the generic scanner test.
3. Treat a stale fingerprint as a concrete release/security-validation finding: the scanner correctly falls closed, but the exact tree cannot satisfy its own required security contract.
4. Report the source digest, embedded digest, exact failing node(s), and scanner violations. Do not dismiss it merely because the runtime wrapper may still be safe.

A useful focused set is the generic “installed production has no direct ambient dispatch” test plus the wrapper-specific fingerprint/enumeration tests. A passing manifest test does not imply embedded test-only fingerprints are current.

## Policy, documentation, required-check, and digest-DAG closure

- Treat shipped skills, references, contributor instructions, and operator runbooks as operational security content. Search them for stale commands or claims that contradict the exact production invariant. For example, guidance that says `--ignore-submodules=all` while production correctly forces complete submodule observation is a content finding, not an evidence caveat; likewise documentation that says required scanners may be path-skipped when the workflow contract says they must always run.
- A documentation inventory is an allowlist, not proof of documentation closure. Enumerate every shipped skill/reference file, including unlinked and unclassified files, and scan unbannered material for stale positive-authority language such as “one safe resolved role,” `dispatch_allowed=true`, or requirements that downstream consumers accept only dispatchable evidence. Historical contradictions are admissible only when the file is visibly bannered as superseded/non-production; an orphan reference with current-tense authority instructions is still shipped policy content.
- After every rebase onto a prerequisite/security-pin commit, compare current-status head/tree claims to the exact parent and ancestry. A document that still calls the previous commit `main/top`, or discusses only “unmerged follow-ups” after the prerequisite has merged, is current-status drift even when the older full-suite seal remains historically valid. Preserve the old seal as historical evidence and describe the new merged-but-unsealed state explicitly.
- For host-bound pin failures, compare the candidate manifest sections to the exact parent before assigning blame. Unchanged pins plus a changed live binary establish tree-external host drift, not a candidate-local digest regression; verify that production fails closed, report the failing required test separately, and still withhold a clean-suite `PASS` until admissible pinned-runtime evidence exists.
- Validate required-check mappings against the actual `jobs:` mapping, not any matching two-space YAML key. For every required row, require literal workflow path, job id, rendered job `name`, and `(context, app_id)` equality. Required scanner jobs must have no PR path filters, job-level skip condition, or dependency on an aggregator; an aggregator may summarize scanners but must not substitute for their individual required contexts.
- Reconcile live/existing CI evidence as an exact set and retain job execution evidence, not only an aggregate workflow conclusion. A green aggregator cannot prove that required scanner jobs ran.
- Recompute digest provenance as edges, not a bag of hashes: producer bytes → consumer embedded pin → next consumer → manifest. Verify every edge independently from the exact materialization, check the live package-tree/version pin where the runtime is host-installed, and then verify the manifest’s enumerated runtime sections have no missing or surplus production entrypoint. Do not infer a referenced artifact pathname from the hash field's label; locate matching bytes by digest within already sealed roots, then validate that artifact's schema and identity.

## Read-only tests and closing attestation

- Route `TMPDIR`, pytest base temp, pytest cache, Python bytecode/pycache, coverage, and package-manager output to scratch. Disable pytest's cache provider when practical.
- Run tests only in the private test tree. Keep the independently rebuilt materialization untouched for final identity verification.
- Reserve tool budget for: exact line capture, final focused reproduction, closing seal, scratch removal, and the verdict. Once one concrete blocker is confirmed, stop broad exploration.
- Compare opening and closing footprints in two layers:
  - **content/identity:** path, type, mode, size, inode/device where relevant, and content digest;
  - **temporal metadata:** mtimes and directory mtimes.
- Metadata-only drift is still concurrent activity and blocks a claim of byte-for-byte footprint stability, but it must not be misreported as content mutation when digests, sizes, and modes are unchanged. State both facts explicitly. A semantic target seal, mutable source-worktree seal, and Git-control/object-store seal are separate claims; do not use one to erase failure of another.
- A mismatching closing seal is not the final seal. Diagnose it from the stored per-entry manifests where possible. If diagnosis requires any further protected-source read—even a checksum or `stat`—perform a fresh authority seal afterward and make that the last protected-source operation.
- After the last candidate read/test, perform no further protected-source operation. The close path must remove scratch even when resealing or comparison fails: capture the failure, `chdir` to a stable parent, delete only the owned root, verify absence, then return the original nonzero result. If cleanup cannot be completed, state the residual path and do not claim cleanup succeeded.

## Verdict discipline

- A confirmed finding remains latched even when later target areas pass.
- Report exact focused totals as passed/failed, not only the passing subtotal.
- Do not issue `PASS` when a required security-contract test fails, closing attestation is incomplete, or scratch cleanup was not verified.
