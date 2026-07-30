# Read-only forensic audit of archived branch state

Use this when an archived Busdriver/Hermes worktree is represented by a Git bundle plus metadata, staged/unstaged patches, and captured untracked bytes, and the question is whether any intent still deserves rescue into current `main`.

## Goal

Classify **intent**, not merely changed paths:

- **A — already present:** current `main` contains the same behavior, usually in a safer or more complete form.
- **B — retired or dangerous:** policy deliberately removed/reversed it, or legacy tests assert behavior current `main` now rejects.
- **C — genuinely rescuable:** still valuable, not already represented, and compatible with current policy.

A patch being non-equivalent under `git cherry` does not make it C. Restacks, squash merges, later hardening, and retirement commits commonly change patch identity while preserving or superseding intent.

## Strict read-only procedure

1. **Freeze scope.** Record the archive path and exact current-main commit supplied by the caller. Before opening, require the caller to define any persistent result channel. If cache, spool, or telemetry is forbidden and no non-persisting bounded channel exists, stop. Forbid repository/worktree/archive, HOME, installed-skill, memory, GitHub, ref/index, and scratch writes; return proposed lessons to the parent instead of mutating skills or memory.
2. **Verify archive integrity and provenance.** Apply every executable, all-filesystem-write, child/network, environment, descriptor-walker, pipeline, and observer rule in `git-observation-sandbox-lessons.md` to Git, hashing, and parsing. Validate metadata paths as normalized scope-relative names before descriptor-bound reads. Compare recursive kind/mode/size/link-text/content rows and metadata bytes with a trusted creation digest when available. Cross-bind bundle ref/OID to metadata branch/HEAD, metadata base/merge-base to the bundle graph, staged OLD OID/mode/path to the bundle HEAD tree, and each patch payload to its recomputed NEW blob. Without a trusted creation digest, report integrity—not provenance. `git bundle verify` either brokers only its authenticated exact `rev-list` child or is reported unavailable under strict no-child mode; never silently weaken containment.
3. **Reconstruct and triangulate dirty layers.** Read metadata/status, then inspect:
   - bundle commits (`HEAD` relative to its merge base),
   - `index-vs-head.patch` for staged intent,
   - `worktree-vs-index.patch` for unstaged intent,
   - `worktree-vs-head.patch` as the aggregate cross-check,
   - captured untracked bytes exactly as archived.

   Require NUL-framed raw/name-status sidecars for exact path accounting. Handle rename/copy source and destination explicitly; fail closed on unmerged, intent-to-add, typechange, or sparse states not represented by the schema. Validate full-index OLD/NEW modes and OIDs, recompute regular-file NEW blobs from payload bytes, and require `HEAD→index→worktree = HEAD→worktree`. Captured untracked inventory must exactly match metadata; ignored paths are declared exclusions, not captured evidence.
4. **Avoid the live worktree.** Resolve `.git` during the plain-file preflight: accept either a directory or a gitfile containing one `gitdir:` path, resolve a relative gitfile target against the worktree root, and reject malformed or out-of-scope targets. Bind the result as `$GIT_DIR` and use only `git --git-dir="$GIT_DIR"` with exact object expressions such as `<main>:path`. Disable external diff and text conversion for diff review (`--no-ext-diff --no-textconv`); use `git grep <main> -- <tracked paths>` or `git blame -L ... <main> -- path` for precise evidence.
5. **Map branch intent.** For each archive-only commit, record subject, changed paths, and the capability/policy it tried to establish. Split mixed commits into separate A/B/C sub-intents.
6. **Compare against current-main behavior.** Prefer current production parsers, blocker maps, route policy, tests, ADRs, and status docs over historical claims. Look for renamed or relocated equivalents before declaring C.
7. **Audit tests semantically, including unchanged inherited tests.** Dirty-diff symbol extraction sees only changed lines; unsafe behavior may live unchanged in the archived HEAD. Compare focused legacy tests and their current replacements even when neither appears in the dirty patch. A legacy-only test is not automatically missing coverage. Check whether it asserts retired authority, dispatchability, marker writes, push/PR/merge success, automatic stale-lock reaping, post-commit cleanup, or other behavior that current-main rejection/reconciliation tests deliberately negate. Such tests are B.
8. **Report exact rescue surface.** If C exists, name exact paths and symbols plus the minimal extraction boundary. If none exists, state `C = ∅`; do not invent a salvage patch merely because the archive is large.
9. **Recommend disposition.** With C empty, recommend removal after retention requirements, or immutable `superseded / no-restore` retention when provenance is required. Never recreate the legacy branch as a default. Keep the judgments separate: operational/code continuity may permit deletion while forensic policy may still require both divergent dirty snapshots.

## Duplicate-stack proof

When two archives appear related, do not compare only commit SHAs or subjects:

1. Enumerate each stack oldest-first from its merge base.
2. Broker `git show --no-ext-diff --no-textconv --pretty=format: --binary --full-index <commit>` and `git patch-id --stable` as two separate validated steps with bytes passed in memory; never trust a shell pipeline. Classify merge/empty commits parent-by-parent or mark them unsupported.
3. If bundle heads still differ, compare the base-to-base delta and head-to-head delta by stable patch-ID. Matching deltas usually prove inherited base drift rather than divergent feature intent.
4. Compare dirty snapshots independently. Duplicate committed stacks do not make one staged/unstaged/untracked state a forensic substitute for the other.

`git cherry` showing `+` against current main proves only that there is no exact patch-ID match. It does not prove the legacy behavior is unique, desirable, or C.

## Brokered read-only operations

Use the authenticated broker—not ambient shell commands or globs—for bundle head listing/verification, descriptor-bound SHA-256, merge-base/count/cherry/log, no-ext-diff/no-textconv comparisons, and object-level grep. Validate each operation's exit status, empty stderr, complete bounded output, and opening/closing inventory. Never point an operation at the live worktree.

## Evidence and output contract

Report:

- archive integrity and exact refs;
- committed, staged, unstaged, and untracked intent classifications;
- the precise legacy tests that encode reversed/dangerous behavior;
- exact C paths/symbols, or `C = ∅`;
- archive/remove recommendation;
- commands intentionally not run (tests, hooks, formatters, fetch, ref/index writes);
- files created or modified (normally none inside the audited scope);
- limitations, especially ignored files and runtime behavior not exercised.

## Pitfalls

- **Do not use patch identity as semantic identity.** `git cherry` can report every commit unique even when current `main` contains a restacked and hardened equivalent.
- **Do not rescue production entrypoints just because their validators are useful.** Current `main` may retain the validator/schema only as a historical fixture while deliberately retiring dispatch.
- **Do not equate hash-then-exec with a trusted execution boundary.** Reading a digest and then executing the same mutable path leaves substitution/TOCTOU and ancestry problems. If current main instead requires root-owned ancestry, descriptor-bound reads, or a pinned committed snapshot, classify the older helper as superseded B—not a missing C hardening.
- **Do not treat stale docs as authority.** Later policy commits and executable blocker maps win.
- **Do not run tests in a strict archival audit.** Tests create caches and exercise mutation-oriented fixtures; static current-main contract evidence is the admissible comparison unless the caller explicitly authorizes a sandbox.
- **Do not import a bundle to inspect it.** If the objects already exist in the canonical object database, inspect them by hash; otherwise stop rather than creating refs, indexes, or scratch repositories under a no-write mandate.
- **Do not overstate the image.** If ignored bytes, original untracked modes, symlink identity, xattrs, or ACLs were not recorded, call it recovery-complete within its declared scope—not a bit-for-bit forensic image. This limitation does not by itself create a C chunk.
- **Do not excuse tooling side effects afterward.** Persistent output is allowed only when the caller approved that channel before opening. Otherwise fail closed before a tool that may spool; later disclosure does not satisfy no-write.
- **Do not leave installed skills outside an underspecified no-write boundary.** A reviewer can correctly avoid the archive and repo yet still mutate the live skill library while following generic post-task learning guidance. Name installed skills, memory, and their management tools explicitly in the forbidden surfaces; collect proposed lessons in the report, then patch them only after the audit closes.
