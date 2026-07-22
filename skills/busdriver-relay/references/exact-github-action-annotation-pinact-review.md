# Exact GitHub Action annotation / pinact review
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this for a read-only review where a candidate changes only the trailing version comment on a SHA-pinned GitHub Action and the verdict depends on the repository's pinned pinact behavior.

## Minimal exact review

1. Bind the immutable candidate tuple: commit, tree, sole parent, target path, and file mode.
2. Assert the changed-path set is exactly the expected workflow and the patch is exactly one byte-level replacement. Require the `owner/repo[/subpath]@<40-hex SHA>` bytes to be identical before and after.
3. A trailing YAML comment cannot change triggers, permissions, inputs, jobs, or runtime behavior. Prove this from the exact replacement; do not run a broad suite unless repository policy separately requires it.
4. Resolve the pinning tool actually used by the workflow from the exact pinned action commit. For pinact-action, inspect its pinned `aqua/imports/pinact.yaml` and checksum lock rather than assuming the host-installed pinact version matches.
5. Query upstream refs with the read-only Git protocol. Use `git ls-remote --tags` to find every tag whose direct or peeled object equals the action SHA. If the claim is major-line membership rather than exact-tag equality, fetch the action SHA and major tag into a scratch bare repo and require `merge-base --is-ancestor`, with the merge base equal to the reviewed SHA when that is the expected relation.
6. Inspect the exact pinact source path for the annotation class. In pinact v4, a full SHA plus `# v3` is a short-semver annotation; under the default non-update path it searches tags on that exact SHA for a `v3...` tag and leaves the line unchanged when none exists.
7. Exercise the exact binary selected by the pinned action:
   - download it only into declared scratch;
   - authenticate its asset digest against the pinned action's checksum lock;
   - print and verify its version;
   - run a minimal fixture with `-fix=false`;
   - compare fixture hashes before and after and require exit 0.
8. If unauthenticated REST limits prevent the live probe, do not use or expose operator credentials. A small scratch GHES-compatible HTTP fixture may return the authoritative tag facts already obtained through Git; point pinact at it with command-local `GHES_API_URL` and fallback disabled. Label this a hermetic compatibility probe, not live-API evidence.
9. Close by verifying candidate identity, clean status including untracked files, index/worktree blob equality for the target path, unchanged mode, stopped fixture server, and absent scratch.

## Strict no-HOME reviews

Keep `HOME`, XDG paths, Git config, caches, and tokens command-local and scratch-scoped. Prefer `git ls-remote`, scratch bare fetches, or `curl` to stdout. Some long-page extraction paths persist omitted content under the user cache; do not use those when HOME is protected. If a tool creates a cache unexpectedly, remove only files proven to have been born during the review, disclose the transient write, and still require a clean close.

## Reporting

Lead with `PASS` or a concrete blocker. Report the exact identity tuple, one-line replacement, major-line/tag evidence, exact pinact version and digest provenance, probe exit/hash result, closing seal, and any evidence limitation. Do not describe a hermetic probe as authenticated live upstream verification.
