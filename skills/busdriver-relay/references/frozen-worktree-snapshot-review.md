# Frozen worktree snapshot review
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this for read-only final reviews where the user supplies a base commit, expected changed-file count, and expected SHA-256.

## Canonical snapshot

Build a deterministic payload from the union of:

- `git diff --no-ext-diff --no-textconv --name-only -z <base>`
- `git ls-files --others --exclude-standard -z`

Sort paths. For each path record:

```json
{"path":"<relative path>","sha256":"<content identity>","untracked":false}
```

For regular files, content identity is SHA-256 of bytes. Represent symlinks as `SYMLINK:<target>`, missing paths as `MISSING`, and special files as `SPECIAL:<type>`. Hash compact canonical JSON:

```python
payload = {"base": base, "files": files}
raw = json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
).encode()
snapshot = hashlib.sha256(raw).hexdigest()
```

Run Git with an isolated read-only environment (`GIT_OPTIONAL_LOCKS=0`, no system/global config where practical, `core.fsmonitor=false`, `core.hooksPath=/dev/null`) and Python with bytecode writes disabled.

## Review sequence

1. Compute the snapshot before reading review targets.
2. Verify expected hash, file count, untracked count, and that every entry is regular unless another type was explicitly expected.
3. If any pre-review value mismatches, stop immediately. Do not continue the substantive review or promote partial observations to findings for the requested frozen snapshot.
4. If an earlier canonical payload is available, compare per-path identities read-only to identify the drifted file without modifying the worktree.
5. Recompute with the identical algorithm immediately before the verdict.
6. Report both hashes. A stable but unexpected hash is still fail-closed.

## Reporting rule

On mismatch, report:

- expected hash;
- pre/post observed hashes;
- file and untracked counts;
- drifted path and expected/current per-file identity when available;
- `FAIL CLOSED — SNAPSHOT MISMATCH`.

Do not run tests that may create caches/artifacts after the mismatch. Do not claim tests/spec/security findings as authoritative for the expected snapshot. Suggest freezing concurrent writers and generating a new approved baseline before restarting.

## Pitfalls

- Hashing only textual `git diff` omits untracked files and is not the same contract.
- Hashing path+content with ad-hoc separators will not reproduce the canonical JSON digest.
- A matching file count does not prove identity.
- Two equal pre/post observed hashes do not rescue a mismatch against the expected hash.
- Creating a snapshot payload inside the repository violates strict read-only review; keep any optional diagnostic payload outside the worktree, or avoid writing one entirely.