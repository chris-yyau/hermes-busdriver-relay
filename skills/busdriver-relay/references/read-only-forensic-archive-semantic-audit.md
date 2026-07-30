# Read-only forensic audit of archived branch state

Use this when an archived Busdriver/Hermes worktree is represented by a Git bundle plus metadata, staged/unstaged patches, and captured untracked bytes, and the question is whether any intent still deserves rescue into current `main`.

## Goal

Classify **intent**, not merely changed paths:

- **A — already present:** current `main` contains the same behavior, usually in a safer or more complete form.
- **B — retired or dangerous:** policy deliberately removed/reversed it, or legacy tests assert behavior current `main` now rejects.
- **C — genuinely rescuable:** still valuable, not already represented, and compatible with current policy.

A patch being non-equivalent under `git cherry` does not make it C. Restacks, squash merges, later hardening, and retirement commits commonly change patch identity while preserving or superseding intent.

## Strict read-only procedure

1. **Freeze scope.** Record the archive path and exact current-main commit supplied by the caller. Do not fetch, switch branches, inspect the live checkout, or refresh its index. In a delegated audit, make the no-write boundary exhaustive: forbid repository/worktree/archive, HOME, installed-skill, memory, GitHub, ref/index, scratch, cache, and telemetry writes. Explicitly forbid `skill_manage`/memory updates even when generic post-task guidance would normally encourage capturing a lesson; the reviewer should return suggested skill text in its report and let the parent apply it after the closing seal.
2. **Verify archive integrity and provenance.** Compare the actual recursive inventory, artifact sizes, and SHA-256 values to metadata; report missing and extra paths. Treat the metadata schema as data rather than assuming fixed key names: enumerate its declared artifact map first, then verify each declaration. Recompute `metadata.json` itself and compare it with any archive-creation transcript or signed manifest that recorded the digest—read-only permissions alone are not provenance. For an in-session zero-drift check, compute an opening and closing aggregate digest in memory over sorted `relative_path + NUL + byte_count + NUL + sha256 + LF`; this binds names as well as contents without creating reviewer scratch. Before any Git command, follow `git-observation-sandbox-lessons.md`: authenticate the Git binary, deny child processes, network, and writes, clear ambient `GIT_*`, disable system/global config and pagers, set optional-lock/lazy-fetch/protocol defenses, and fail closed on stderr or partial output. Then run `git bundle list-heads` and `git bundle verify`; never `unbundle`, import objects, or create refs. Inspect every path with `lstat` before opening it: hash regular-file bytes without following symlinks, record symlinks by link text, and classify FIFOs/sockets/devices by type without opening them. File-content hashes do not bind mode, xattrs, ACLs, symlink identity, or timestamps unless the schema records them.
3. **Reconstruct and triangulate dirty layers.** Read metadata/status, then inspect:
   - bundle commits (`HEAD` relative to its merge base),
   - `index-vs-head.patch` for staged intent,
   - `worktree-vs-index.patch` for unstaged intent,
   - `worktree-vs-head.patch` as the aggregate cross-check,
   - captured untracked bytes exactly as archived.

   Parse `diff --git` paths and full `index OLD..NEW` headers in memory. Require each patch path set to match the corresponding porcelain status column, aggregate paths to equal their union, and per-path blob endpoints to compose as `HEAD→index→worktree = HEAD→worktree`. An empty staged patch is valid only when metadata reports no staged paths. Captured untracked inventory must exactly match metadata; ignored paths are declared exclusions, not captured evidence.
4. **Avoid the live worktree.** Query committed sources with `git --git-dir=<repo>/.git` and exact object expressions such as `<main>:path`. Disable external diff and text conversion for diff review (`--no-ext-diff --no-textconv`); use `git grep <main> -- <tracked paths>` or `git blame -L ... <main> -- path` for precise evidence.
5. **Map branch intent.** For each archive-only commit, record subject, changed paths, and the capability/policy it tried to establish. Split mixed commits into separate A/B/C sub-intents.
6. **Compare against current-main behavior.** Prefer current production parsers, blocker maps, route policy, tests, ADRs, and status docs over historical claims. Look for renamed or relocated equivalents before declaring C.
7. **Audit tests semantically, including unchanged inherited tests.** Dirty-diff symbol extraction sees only changed lines; unsafe behavior may live unchanged in the archived HEAD. Compare focused legacy tests and their current replacements even when neither appears in the dirty patch. A legacy-only test is not automatically missing coverage. Check whether it asserts retired authority, dispatchability, marker writes, push/PR/merge success, automatic stale-lock reaping, post-commit cleanup, or other behavior that current-main rejection/reconciliation tests deliberately negate. Such tests are B.
8. **Report exact rescue surface.** If C exists, name exact paths and symbols plus the minimal extraction boundary. If none exists, state `C = ∅`; do not invent a salvage patch merely because the archive is large.
9. **Recommend disposition.** With C empty, recommend removal after retention requirements, or immutable `superseded / no-restore` retention when provenance is required. Never recreate the legacy branch as a default. Keep the judgments separate: operational/code continuity may permit deletion while forensic policy may still require both divergent dirty snapshots.

## Duplicate-stack proof

When two archives appear related, do not compare only commit SHAs or subjects:

1. Enumerate each stack oldest-first from its merge base.
2. Compute `git show --no-ext-diff --no-textconv --pretty=format: --binary --full-index <commit> | git patch-id --stable` and pair commits by patch-ID and intent.
3. If bundle heads still differ, compare the base-to-base delta and head-to-head delta by stable patch-ID. Matching deltas usually prove inherited base drift rather than divergent feature intent.
4. Compare dirty snapshots independently. Duplicate committed stacks do not make one staged/unstaged/untracked state a forensic substitute for the other.

`git cherry` showing `+` against current main proves only that there is no exact patch-ID match. It does not prove the legacy behavior is unique, desirable, or C.

## Useful read-only commands

```bash
# Never point these at the live worktree.
git bundle list-heads "$ARCHIVE/branch.bundle"
git --git-dir="$REPO/.git" bundle verify "$ARCHIVE/branch.bundle"
shasum -a 256 "$ARCHIVE"/branch.bundle "$ARCHIVE"/*.patch

git --git-dir="$REPO/.git" merge-base "$MAIN" "$ARCHIVE_HEAD"
git --git-dir="$REPO/.git" rev-list --left-right --count "$MAIN...$ARCHIVE_HEAD"
git --git-dir="$REPO/.git" cherry "$MAIN" "$ARCHIVE_HEAD"
git --git-dir="$REPO/.git" log --format='%H%x09%P%x09%s' "$MAIN..$ARCHIVE_HEAD"
git --git-dir="$REPO/.git" diff --no-ext-diff --no-textconv --name-status "$MAIN" "$ARCHIVE_HEAD"
git --git-dir="$REPO/.git" grep -n -I -E '<policy-or-symbol-pattern>' "$MAIN" -- <tracked-paths>
```

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
- **Account for tooling side effects.** Oversized output may be automatically spooled outside the audited scope. Include any such path in the side-effect report; under a strict no-delete order, disclose it rather than silently cleaning it.
- **Do not leave installed skills outside an underspecified no-write boundary.** A reviewer can correctly avoid the archive and repo yet still mutate the live skill library while following generic post-task learning guidance. Name installed skills, memory, and their management tools explicitly in the forbidden surfaces; collect proposed lessons in the report, then patch them only after the audit closes.
