# Truly read-only exact-candidate review

Use this procedure when the user requires an immutable review of frozen candidate bytes and forbids all repository, HOME, installed-skill, and GitHub mutation.

## Scope contract

- Treat the frozen diff as the review subject. Do not apply it or reconstruct it on disk.
- Do not run checkout, switch, stash, add, reset, commit, fetch, tests, formatters, linters, hooks, or package commands unless the user explicitly permits them.
- Never use object-producing probes such as `git write-tree`, `git hash-object -w`, temporary indexes, or commits.
- Do not create reviewer-owned scratch files. Keep parsing, comparisons, syntax checks, and digests in memory. When Python is necessary, use the authenticated absolute `-I -S -B` stdin-only interpreter boundary in `git-observation-sandbox-lessons.md`; `-B` alone is not isolation.
- Before opening, require the caller to define writable surfaces and any persistent result channel. The reviewer cannot exempt cache, spool, or telemetry after the fact; without a non-persisting bounded channel under a literal no-write mandate, stop.
- Treat the review target as an untrusted Git repository. Apply the matching executable, all-filesystem-write, child/network, descriptor-walker, and observer profile in `git-observation-sandbox-lessons.md` to every Git and non-Git observation. Local observers remain no-network; Step 6 may use only the shared sole network-enabled GET profile. Fail closed if any required boundary is unavailable.
- As defense in depth for every Git observation, clear ambient `GIT_*`, disable system/global config and attributes, set `GIT_OPTIONAL_LOCKS=0`, `GIT_NO_LAZY_FETCH=1`, `GIT_NO_REPLACE_OBJECTS=1`, an empty `GIT_ALLOW_PROTOCOL`, and `core.fsmonitor=false`; reject config includes and reject every `refs/replace/**` entry. Fail closed on populated submodules unless each passes separate preflight and the broker permits only the authenticated exact recursive Git child; then keep gitlink drift visible with `--ignore-submodules=none`. Reject non-empty stderr and partial stdout even when Git exits zero.
- Clean/process filters are a separate execution surface: `--no-ext-diff`, `--no-textconv`, and `core.attributesFile=/dev/null` do not neutralize a `filter.*.clean` or `filter.*.process` selected by repository or Git-dir attributes. Before the first `status`, worktree/index `diff`, or other worktree-content observation, inspect only direct filesystem bytes and non-materializing Git plumbing; reject every worktree/index/`HEAD` `.gitattributes`, `$GIT_DIR/info/attributes`, non-default `core.attributesFile`, configured `filter.*.(clean|process)`, external diff/textconv command, active fsmonitor, or assume-unchanged/skip-worktree index flag. If any surface is present, block the strict review rather than executing it as a positive-control probe or claiming the observation is read-only.

## Procedure

1. **Capture opening evidence before content inspection.** Record:
   - frozen candidate path, byte count, and SHA-256;
   - `HEAD`, documented base commit, and base tree via `rev-parse`;
   - exact NUL-framed porcelain status, separate ignored inventory, and descriptor-bound full worktree manifest;
   - index byte count and SHA-256 plus every backing store;
   - ref inventories;
   - Git object-store inventory; and
   - any direct-source package/registry/index/status identities cited by the candidate.
   - For every recursive inventory whose drift would block the verdict, retain the full sorted row manifest in tool output—not only its aggregate count/byte total/digest—so the final close can localize a concurrent change without reopening the candidate.
2. **Handle Git layout explicitly.** `--absolute-git-dir` may contain only the worktree `HEAD`; refs usually live under `--git-common-dir`. Inventory both Git dirs and resolve index/object paths. Fail closed on split index, alternates, or reftable unless every backing store is inside the opening/closing seal and write-deny boundary.
3. **Prove the review boundary.** Reproduce the candidate's exact pinned diff format in memory and compare its bytes, size, and SHA-256 with the frozen file. Use `git diff --cached <base>` for a staged candidate and `git diff <base> <head>` for an already committed PR head; do not substitute Git's default formatting merely because it happens to hash the same on one patch. Also confirm the intended path set and that there is no unreviewed binary patch.
4. **Inspect without materialization.** Read old/new blobs using brokered `git cat-file`; parse bytes in memory. Syntax checks use the authenticated absolute `-I -S -B` stdin-only interpreter under the same sandbox and never import candidate modules. Resolve commit/tree pairs with `rev-parse` rather than creating trees.
5. **Verify direct claims at their real source.** Read already-known installed-package, marketplace, registry, and manifest metadata bytes without executing package managers. For source checkouts, use the same strict observer. Historical claims and current identity remain separate evidence.
6. **Triage live review state without conflating it with content.** Re-query the exact PR head only through the caller-approved authenticated GET-only observer defined in the shared boundary; disable extensions, helpers, pager, credentials side effects, and local persistence. If safe observation is unavailable, report that limitation and do not claim PR-grind closure.
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

Build every inventory with the descriptor-bound no-follow walker in `git-observation-sandbox-lessons.md`; a path-based `lstat` followed by `open` is insufficient. Hash sorted NUL-framed rows including path, kind, mode, size, link text, or regular-file SHA-256.

## Accidental mutation

Any object, ref, index, cache, or other prohibited write invalidates the review. Stop and report exact observed drift; do not delete, prune, restore, or otherwise repair it inside the immutable review. Recovery requires a separately authorized mutating workflow, a quiescent/exclusively owned repository, and a fresh review from a new opening snapshot.

## Pitfalls

- **Hashing only `$GIT_DIR/refs` in a linked worktree:** misses common refs. Inventory `--git-common-dir` too.
- **Calling status without optional-lock protection:** Git may refresh the index. Set `GIT_OPTIONAL_LOCKS=0` and `core.fsmonitor=false`.
- **Using `git apply --check` as a harmless probe:** it is unnecessary when the contract limits review to frozen bytes and blob inspection; parse the patch in memory instead.
- **Treating a staged candidate as an unclean review:** the expected state may be staged modifications with an empty worktree diff. Compare opening and closing status, not a generic “clean repo” label.
- **Running tests to improve confidence despite an immutability prohibition:** test runners commonly write caches and artifacts. Respect the boundary and report the unrerun evidence honestly.
- **Taking the object inventory too early at closing:** run every final Git observation first, then hash objects/refs/index so the snapshot covers the reviewer’s last command.
