# Trusted runtime and frozen-review hardening
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this checklist when finalizing security-sensitive Relay changes.

## Frozen dirty-tree reviews

- Bind the review to both the committed base (`origin/main`, merge-base, and `HEAD`) and the complete dirty overlay.
- Hash `git diff --binary HEAD`, and hash every untracked file by path, size, and content. The `HEAD` SHA identifies all already-committed branch changes; the dirty hash alone does not.
- Keep the manifest outside the repo so evidence creation does not change the reviewed tree.
- Review the cumulative `origin/main` → frozen tree, not merely `HEAD` → working tree.
- Recompute a manifest digest using the exact original schema and fields. A verifier that adds, renames, or omits fields can falsely report drift even when the binary diff is unchanged.
- Do not stage, patch, format, or sync repo files while hash-bound reviewers are running. Staging can change porcelain-based manifests even when file bytes remain identical.
- Any finding-driven edit invalidates the snapshot: rerun gates, regenerate the manifest, and repeat affected reviews.

### Reviewer lifecycle and provenance

- Do not report that background reviewers are still running merely because they were dispatched earlier. Before a status claim, require a live task handle/process or an actual returned result; if neither exists, state that the review was lost and launch a replacement after the tree is ready.
- Read-only reviewer work must never share a mutating absolute worktree. Prefer an immutable snapshot/copy or a separate worktree, and explicitly prohibit writes in the review prompt.
- A file-provenance warning that names a sibling agent does **not** by itself prove post-freeze drift. Recompute the canonical snapshot digest and inspect the diff before accepting or reverting anything.
- Never overwrite sibling-owned dirty files on a warning alone. Read the complete affected files first, determine whether bytes changed after freeze, then patch with narrow unique context.

## Trusted executable resolution

- Sanitize control-plane environment **before the first Git/GH/runtime lookup**. Resolving with ambient `PATH` and sanitizing only the child process is too late.
- Prefer reviewed absolute paths plus SHA-256 pins from the shared trusted-runtime manifest. Keep embedded consumer pins and the manifest synchronized by contract tests.
- Do not use `shutil.which()` to choose production Git/GH/runtime bytes before environment sanitization.
- Audit **every consumer call site**, not only the central helper: direct `subprocess.run(["git", ...])`, archive/materialization helpers, ref validators, and preflight checks can silently bypass an otherwise correct authenticated resolver.
- A fixed system `PATH` is environment hardening, not byte authentication. If the manifest pins one Git binary, a consumer that selects a different OS Git remains outside that authority even when both are absolute and locally trustworthy.
- Model/agent output remains untrusted even when the launcher binary is pinned. Derive repository state, HEADs, and changed paths independently from trusted Git.

### Package-tree pins and symlinks

- A package-tree digest must bind entry type and symlink target text, not only regular-file bytes. Simply skipping symlinks lets a link be repointed without changing the digest.
- Reject links that escape the authenticated package root unless the contract explicitly pins the external target and its bytes.
- Test the production verifier against: a modified regular file, a new file, a removed file, a repointed internal link, an external link, and target changes after pin generation.
- Manifest synchronization tests are insufficient by themselves; run direct negative tests through the production resolver.

### Integrity-pin cascade

Treat authenticated scripts as a dependency graph, not a flat list of hashes:

1. Finish edits to the leaf authenticated file first.
2. Compute its live digest and update every direct embedded consumer plus the shared manifest.
3. If a consumer changed because its embedded pin changed, recompute that consumer's digest and update its own consumers.
4. Repeat outward until the graph reaches an unpinned root. Import cleanup, comments, and formatting all change authenticated bytes and therefore participate in the cascade.
5. Run the narrow manifest/embedded-pin contract before broad integration tests. Predictable `*_integrity_failed` tests should not be debugged as runtime regressions until the cascade is synchronized.
6. After targeted regressions pass, run static undefined-name/lint/security checks **before** the expensive full suite; they can expose unexecuted fail-closed branches that tests missed.
7. Only then run the full suite, regenerate the frozen snapshot, and start hash-bound reviews.

Always obtain hashes from a real checksum tool. Never transcribe or infer a downstream digest before the upstream consumer has reached final bytes.

## Authentication-only private homes

- Copy only the minimum authentication artifact; never copy user plugins, packages, extensions, or ambient settings.
- Avoid `is_file()` followed by `copyfile()`: that check-then-copy sequence is vulnerable to a symlink/rename race.
- Open the source with `O_NOFOLLOW` where available, verify the opened descriptor with `fstat`, enforce a size ceiling, and copy from the descriptor into a newly created mode-0600 target.
- `O_NOFOLLOW` on the leaf does not protect source parent components. Traverse source and destination parents with dirfd-based no-follow opens, or explicitly validate each component; include a symlinked-parent negative test.
- Create or re-check every private directory as non-symlink and mode 0700, including when it already exists.
- Never include credential values in logs, evidence, prompts, or summaries; use `[REDACTED]`.

## Large gated deliveries

- Calculate Busdriver commit-mode litmus limits before staging. Split into logical groups that respect file-count and weighted-line limits.
- A documented per-project threshold override is acceptable only for a tightly coupled implementation/test pair that remains below the hard raw-line ceiling; record the calculation. It is not a generic bypass.
- Commit-mode litmus reviews staged changes. PR-mode litmus reviews `base...HEAD`; therefore dirty changes must not be mistaken for reviewed PR evidence.
