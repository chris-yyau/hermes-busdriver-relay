# Truly read-only exact-candidate review

Use this procedure when the user requires an immutable review of frozen candidate bytes and forbids all repository, HOME, installed-skill, and GitHub mutation.

## Scope contract

- Treat the frozen diff as the review subject. Do not apply it or reconstruct it on disk.
- Do not run checkout, switch, stash, add, reset, commit, fetch, tests, formatters, linters, hooks, or package commands unless the user explicitly permits them.
- Never use object-producing probes such as `git write-tree`, `git hash-object -w`, temporary indexes, or commits.
- Do not create reviewer-owned scratch files. Keep parsing, comparisons, syntax checks, and digests in memory; use `python -B` when Python is needed so inspection cannot create bytecode.
- Define the audited filesystem surfaces before the opening snapshot. Hermes may automatically persist captured tool output under its configured runtime result cache; that telemetry may be declared out of scope before review because the reviewer did not create it. Never use that exemption for reviewer-authored scratch or repository/HOME/installed-skill/GitHub writes. If the requirement is literally “no filesystem writes anywhere,” resolve that boundary before review rather than producing an impossible false blocker after otherwise clean work.
- Treat the review target as an untrusted Git repository. Before any worktree-facing Git command, follow `git-observation-sandbox-lessons.md`: authenticate the Git binary, use a no-child/no-network sandbox, inspect repository/common/worktree config and every attributes source as plain files, and fail closed if that boundary is unavailable. A config denylist alone cannot close filter, submodule, lazy-fetch, or rename/ABA execution races.
- As defense in depth for every Git observation, clear ambient `GIT_*`, disable system/global config, set `GIT_OPTIONAL_LOCKS=0`, `GIT_NO_LAZY_FETCH=1`, `GIT_NO_REPLACE_OBJECTS=1`, an empty `GIT_ALLOW_PROTOCOL`, and `core.fsmonitor=false`; reject every `refs/replace/**` entry during the plain-file preflight; use `--ignore-submodules=none` for status and `--no-ext-diff --no-textconv` for diff. Reject non-empty stderr and partial stdout even when Git exits zero.
- Clean/process filters are a separate execution surface: `--no-ext-diff`, `--no-textconv`, and `core.attributesFile=/dev/null` do not neutralize a `filter.*.clean` or `filter.*.process` selected by repository or Git-dir attributes. Before the first `status`, worktree/index `diff`, or other worktree-content observation, inspect only direct filesystem bytes and non-materializing Git plumbing; reject every worktree/index/`HEAD` `.gitattributes`, `$GIT_DIR/info/attributes`, non-default `core.attributesFile`, configured `filter.*.(clean|process)`, external diff/textconv command, active fsmonitor, or assume-unchanged/skip-worktree index flag. If any surface is present, block the strict review rather than executing it as a positive-control probe or claiming the observation is read-only.

## Procedure

1. **Capture opening evidence before content inspection.** Record:
   - frozen candidate path, byte count, and SHA-256;
   - `HEAD`, documented base commit, and base tree via `rev-parse`;
   - exact porcelain status;
   - index byte count and SHA-256;
   - ref inventories;
   - Git object-store inventory; and
   - any direct-source package/registry/index/status identities cited by the candidate.
   - For every recursive inventory whose drift would block the verdict, retain the full sorted row manifest in tool output—not only its aggregate count/byte total/digest—so the final close can localize a concurrent change without reopening the candidate.
2. **Handle linked worktrees correctly.** `--absolute-git-dir` may contain only the worktree `HEAD`; refs usually live under `--git-common-dir`. Inventory both the worktree Git dir and common refs (`HEAD`, `packed-refs`, `refs/**`) separately. Resolve the index and object directory with `git rev-parse --git-path`.
3. **Prove the review boundary.** Reproduce the candidate's exact pinned diff format in memory and compare its bytes, size, and SHA-256 with the frozen file. Use `git diff --cached <base>` for a staged candidate and `git diff <base> <head>` for an already committed PR head; do not substitute Git's default formatting merely because it happens to hash the same on one patch. Also confirm the intended path set and that there is no unreviewed binary patch.
4. **Inspect without materialization.** Read old/new blobs using `git cat-file`; parse documentation, JSON, regex contracts, and source syntax in memory. Python `compile(source_bytes, name, "exec")` checks syntax without writing `.pyc`. Resolve documented commit/tree pairs with `rev-parse` rather than creating trees.
5. **Verify direct claims at their real source.** If a status document cites an installed package version, marketplace commit, or trust-manifest pin, read the installed package metadata/registry and the manifest independently. For a dated or explicitly pre-refresh observation, current drift does not itself refute the claim: verify the historical commit's package metadata, report the current identity separately, and distinguish a historical installed↔repo comparison from present-day equivalence. For a source checkout, record read-only `HEAD`, index digest, status, and worktree/index diff state.
6. **Triage live review state without conflating it with content.** Re-query the exact GitHub PR head and current non-outdated threads. A thread that remains unresolved in the UI after its requested line is present on the current head is not a new content finding, but it is still process state: report it and do not claim PR-grind closure until policy-required resolution/reply is complete. Keep exact-head portable CI subsets, user-supplied focused results, and externally running full suites labeled as separate evidence; never promote a subset or an unobserved concurrent result into a full-suite claim.
7. **Capture closing evidence last.** Re-run GitHub identity, status, and all Git observations first, then compute final candidate/index/ref/object/installed-skill/direct-source inventories. In the same closing entrypoint, compare the stored opening rows and emit localized created/deleted/changed rows before declaring the no-more-tools boundary. Make no tool calls after the closing snapshot. Compare every opening and closing value exactly. Current installed-skill differences may be an out-of-candidate observation; the immutability question is whether that inventory changed during this review unless the candidate itself claims current equivalence. If only an aggregate digest was retained and it drifts, report a review-integrity blocker and do not guess which file changed.
8. **Report one verdict.** Give exact Blocker/Major/Minor counts and the reviewed SHA-256. `PASS` is allowed only at `0/0/0` *and* zero reviewer drift. State explicitly that prohibited tests were not rerun; prior or concurrently running test evidence is supporting evidence, not a result of this review.

## Zero-drift evidence

A strong closing report includes identical opening/closing values for:

- candidate bytes and SHA-256;
- index bytes and SHA-256;
- worktree Git-dir ref inventory;
- common-dir ref inventory;
- object-store file count, byte count, and deterministic inventory digest;
- `HEAD`, tree, and porcelain status;
- worktree diff state and staged candidate identity; and
- directly inspected installed-package/registry/source metadata.

Hash each inventory over sorted, NUL-framed tuples of relative path, entry kind, size, and mode. Classify paths with `lstat` before opening them: include file-content SHA-256 only for regular files without following symlinks, encode symlinks by link text, and encode FIFOs/sockets/devices by type without opening them. This detects created, deleted, renamed, or changed object/ref files without generating Git objects.

## Recovering accidental loose Git objects

If a reviewer accidentally runs an object-producing probe, the verdict is invalid even when candidate bytes remain unchanged.

1. Stop the review and identify the exact newly created loose-object cluster from the opening inventory and filesystem timestamps; do not run broad `gc` or `prune`.
2. Enumerate the current index plus every linked worktree index under the common Git directory, including detached or prunable worktree metadata, and collect their staged blob OIDs without refreshing any index. For every candidate object, prove it is the expected Git type, unreachable from `git rev-list --objects --all --reflog`, and absent from **every linked worktree index**. Never delete a staged blob merely because no ref reaches it or because the reviewing worktree's index does not contain it.
3. Snapshot candidate diff hash, every linked worktree index's raw bytes and staged-OID inventory, refs, `HEAD`, and the reviewed worktree's porcelain status. Delete only the proven reviewer-created unreachable objects, then prove every snapshot is byte-identical and each targeted object is gone.
4. Restart immutable review from a fresh opening snapshot. A content-clean verdict from the polluted run is supporting evidence only, not closure.

## Pitfalls

- **Hashing only `$GIT_DIR/refs` in a linked worktree:** misses common refs. Inventory `--git-common-dir` too.
- **Calling status without optional-lock protection:** Git may refresh the index. Set `GIT_OPTIONAL_LOCKS=0` and `core.fsmonitor=false`.
- **Using `git apply --check` as a harmless probe:** it is unnecessary when the contract limits review to frozen bytes and blob inspection; parse the patch in memory instead.
- **Treating a staged candidate as an unclean review:** the expected state may be staged modifications with an empty worktree diff. Compare opening and closing status, not a generic “clean repo” label.
- **Running tests to improve confidence despite an immutability prohibition:** test runners commonly write caches and artifacts. Respect the boundary and report the unrerun evidence honestly.
- **Taking the object inventory too early at closing:** run every final Git observation first, then hash objects/refs/index so the snapshot covers the reviewer’s last command.
