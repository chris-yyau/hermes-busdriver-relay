# Canonical-entry exact-boundary reconstruction and closure probes
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference for independent correctness/state-integrity pre-freeze reviews where the authority is a JSON inventory of canonical entry records rather than a ready-made tar/diff artifact.

## Start/end-closed sequence

1. Read only the boundary and verifier implementation before START; do not inspect candidate bytes first.
2. Verify the boundary file SHA-256 and sidecar, then recompute the live inventory exactly: sorted paths, `lstat` type/mode, regular-file or symlink-target bytes, size, and SHA-256. Canonicalize entries with the boundary's exact JSON separators, key ordering, and Unicode rules.
3. Verify every authoritative identity field at START: schema/generation, source digest/count, HEAD, branch, remote ref, remote URL, status counts, empty index, and candidate tree.
4. Reconstruct into a reviewer-only directory from authenticated entry bytes. A practical faithful method is `git clone --no-hardlinks --no-checkout`, set candidate-only branch/remote refs, delete every non-`.git` worktree entry, then materialize only boundary entries with exact modes and hashes. Never copy a linked-worktree gitfile back to the source.
5. Run candidate reads, focused tests, and adversarial probes only against the reconstruction.
6. Make END the final candidate operation. Re-run the same verifier against the live source after the last candidate read/test/probe. Writing the external report and checksum afterward is safe; touching candidate/source afterward is not.
7. Save the formal report and SHA-256 sidecar even when already BLOCKED. Report raw probe counts separately from root-cause finding counts.

## Frozen package needs both bytes and Git objects

A deterministic source tar and `git diff --binary HEAD` are not enough to reconstruct a faithful reviewer repository: the tar carries the complete dirty candidate bytes, while the patch omits untracked files and neither artifact necessarily carries the recorded HEAD/origin objects and refs.

For reusable formal frozen reviews, package and independently hash all of:

- a manifest with exact entry records and Git/source identity;
- a deterministic regular-file-only source tar of every canonical entry;
- the binary tracked diff against the recorded HEAD;
- a Git bundle containing the recorded HEAD, base/origin ref, and required history;
- identity-bound test logs, process exit records, and SHA sidecars.

Verify bundle bytes and `git bundle list-heads` before cloning. A clone from a bundle may not preserve bundled remote-tracking refs even when `list-heads` contains them. After authenticating the expected OIDs, explicitly create the required refs **inside the reviewer candidate only**, set the canonical remote URL, then materialize the exact tar entries and recompute the candidate tree. Never repair refs in the frozen source. Reject missing objects, unexpected refs relied upon as authority, unsafe tar members, extra/missing entries, or any manifest/artifact/sidecar mismatch.

Build the package atomically in a private runtime directory and publish it only after live entry bytes, status counts, HEAD/branch/base/remote, candidate tree, test evidence, tar reconstruction, and every sidecar pass. A smoke package must use a different output path and be removed after verification; it is not itself the formal freeze.

## Recompute a Git candidate tree without writing source objects

An alternate index alone is not source-read-only: `git add` can write new blobs/trees into the source object database. For a source-safe recomputation, use a temporary index and temporary object directory. Set `GIT_INDEX_FILE` and `GIT_OBJECT_DIRECTORY` to them, set `GIT_ALTERNATE_OBJECT_DIRECTORIES` to the source common Git objects directory, then run `read-tree HEAD`, `add -A`, and `write-tree` with hooks/fsmonitor/global/system config disabled. This reads existing source objects through alternates while forcing all newly hashed blobs/trees outside the source repository.

## Fixed-blocker ordering probe

For each unconditional blocker, load the real entrypoint and replace every forbidden pre-block helper with a hard sentinel: run-id/timestamp generation, delivery status/credential discovery, trusted executable lookup, lock acquisition, artifact path/write, and mutating dispatch. Invoke the real `main()` path.

Test both no caller `--run-id` and explicit caller `--run-id`, including the worst credential-capable accepted combination such as `--pr`. Require the documented blocker, zero sentinel calls, no created timestamp/artifact, and only an echoed caller run ID when supplied.

## Audit the full executable closure

A parent that hashes/copies its own helper is insufficient. Probe every nested edge: direct bare `git`/`gh`/`jq`; gates that independently resolve fixed PATHs; authenticated lock helpers that invoke bare Git internally; direct production checkers that hash then return the same mutable source; and nested shells whose PATH omits the private bin.

Instrument subprocess calls and require every real argv[0] to be an authenticated private copy under a 0700 directory, mode 0500, with the expected digest. Mutate the original after authentication and place ambient PATH sentinels; neither may execute. Treat `resolved == source` after a hash check as TOCTOU. Avoid circular tests that cover only selected helpers while sibling diff/hash, gate, or lock edges remain bare.

## Artifact authenticity negative probe

Schema/type validation is not writer provenance. Create a fully schema-valid artifact with authority flags false and a chosen run ID, without using the production writer. If status lookup accepts it, durable run evidence is forgeable even if mutation authority remains blocked.

Require reviewer-owned 0700 ancestors, 0600 regular files, no symlink/hardlink replacement, authenticated canonical bytes (for example HMAC with a key unavailable to repo-controlled children), binding to run/writer/operation/repo/HEAD/tree/time/path, replay rejection, and atomic no-follow descriptor-relative publication. A forged read-only status artifact may rank below direct mutation bypass, but still blocks a state-integrity CLEAN verdict.
