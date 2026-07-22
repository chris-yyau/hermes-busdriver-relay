# Hash-bound snapshot canonicalization lessons

Use this when reviewing a frozen dirty worktree or a captured manifest plus binary diff.

## Boundary verification

1. Treat the manifest digest as an input contract, not as a value to echo.
2. Locate or reconstruct the producer's exact canonicalization before declaring drift. Differences such as one terminal newline are hash-significant.
3. Verify independently:
   - canonical manifest hash with the digest field excluded;
   - raw binary-diff hash and byte size;
   - regenerated tracked-diff bytes using the producer's exact serialization flags;
   - `HEAD`, comparison-base OID, branch, and canonical repository path;
   - exact untracked path set and each file's size/content hash.

   Do not assume `--binary` implies the producer's full-index representation on every Git version. If `git diff --binary --no-ext-diff --no-textconv HEAD` differs while the authenticated source records still match, test narrow serialization variants before declaring drift—especially `--full-index`. Record the exact matching command and require byte-for-byte equality. A size delta consisting of abbreviated versus full object IDs is serialization mismatch, not source drift.
4. Recompute the full boundary after tests and review, before publishing findings.

## `hermes-dirty-snapshot/v0` canonical form encountered

For manifests shaped as `hermes-dirty-snapshot/v0`, the producer used compact, key-sorted JSON of every field except `snapshot_sha256`, followed by exactly one newline:

```python
payload = {k: v for k, v in manifest.items() if k != "snapshot_sha256"}
canonical = json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
) + "\n"
observed = hashlib.sha256(canonical.encode()).hexdigest()
```

Do not generalize this routine to a different schema/version without confirming its producer contract.

## Pitfalls

- A compact JSON hash without the terminal newline is a different digest; this is unknown canonicalization, not snapshot drift.
- A manifest hash only authenticates referenced hashes. Independently hash the diff and untracked bytes it names.
- `HEAD`, filename lists, and porcelain line counts can stay unchanged while dirty bytes drift.
- If a test command writes only outside the reviewed repository, still re-run the boundary check to prove the source snapshot stayed unchanged.
