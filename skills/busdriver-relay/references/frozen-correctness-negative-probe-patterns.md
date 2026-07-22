# Frozen correctness negative-probe patterns
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this alongside `frozen-correctness-state-integrity-review.md` when a frozen candidate has green tests but permission metadata or lock ownership may still fail open.

## Producer declaration integrity

Proof-like booleans must be explicit in the authoritative declaration map, not merely present in normalized output.

Read-only probe sequence:

1. Load the producer with `runpy.run_path` in a fresh temporary `HOME`.
2. Inspect the source declaration map directly. For every entry, require permission/proof fields (for example `programmatic_dispatch_allowed` and `adapter_verified`) to exist and be booleans.
3. Search producer normalization for permissive forms such as `entry.get(field, True)`.
4. Deep-copy the declaration map and run a Cartesian mutation matrix across **every authoritative entry**, not one representative role: for each proof field, test deletion plus malformed values such as `None`, integer `1` (which must not pass as a boolean), and strings such as `"true"`. Temporarily inject each copy into the loaded function's globals and invoke the real producer.
5. Repeat malformed/contradictory cases at the consumer boundary: missing or wrongly typed proof fields, dispatch allowed with adapter unverified, dispatch allowed with a non-null blocker, and dispatch denied without a non-empty blocker must all remain non-dispatchable.
6. A deleted or malformed proof field must never produce `true`; require a structured fail-closed error or explicit `false`.
7. Check tests validate the declaration map itself. Tests that assert only normalized output can accidentally encode a fail-open default as expected behavior.

A downstream consumer that rejects missing fields does not repair this issue when its trusted producer has already replaced omission with `true`.

## Lock ownership and recovery

Test normal release and recovery as separate contracts.

1. Acquire a fresh, non-stale lock in a temporary repo/state directory.
2. Verify a wrong or missing token cannot release it through any normal, force, or recovery-shaped CLI path.
3. If explicit stale recovery exists, require staleness and the expected lock identity/snapshot to be checked under the same mutation guard before deletion.
4. Race recovery/release against a waiting replacement and prove compare-delete cannot remove the replacement.
5. Do not accept serialization alone as ownership proof: a guard can serialize an unsafe deletion while still allowing a non-owner to delete an active lock.

A public `release --force` that skips token comparison and does not require staleness is a state-integrity blocker even if ordinary token mismatch and compare-delete tests pass.

## Practical probe mechanics learned from frozen reviews

### Mutate function globals, not only the `runpy` result dict

`runpy.run_path()` returns a namespace, but a function under test resolves globals through `function.__globals__`. For a complete producer mutation matrix:

1. Deep-copy the authoritative declaration map.
2. Replace `producer.__globals__["DECLARATION_MAP_NAME"]` with the copy.
3. Mutate every entry × proof field with deletion, `None`, integer `1`, string `"true"`, and a container value.
4. Invoke the real producer and then feed its output to the real consumer.
5. Restore the original global after the matrix.

Changing only the dictionary returned by `runpy.run_path()` can leave the function bound to its original map and produce a false-positive test.

### Exercise the two-replacement lock race

A single replacement-before-rename test does not cover restoration contention. Add a read-only temporary-fixture probe that:

1. installs replacement A immediately before canonical-to-quarantine rename;
2. lets release move A to quarantine and detect token mismatch;
3. installs replacement B at the canonical path immediately before restoration;
4. asserts release blocks, canonical B survives, quarantined A survives, and the detached original generation also survives.

This directly proves the restore path does not overwrite a second owner or delete either replacement generation.

### Distinguish staged frozen candidates from empty diffs

Reconstructed frozen candidates may have all reviewed changes staged. In that shape, plain `git diff` is empty even though `git status --short` lists the complete candidate. Use `git diff --cached --stat` / `--numstat` for review discovery and `git write-tree` to compare the candidate tree with the verifier-pinned tree. Do not conclude that there is nothing to review from an empty unstaged diff.

### Containment evidence when production is intentionally non-dispatchable

If the supported production entry point unconditionally returns a containment blocker before any worker/verifier launch and exposes no CLI or environment unlock seam, normal-success descendant containment can be satisfied by proving non-dispatchability rather than invoking an internal legacy runner. Require production sentinel tests, blocker-before-credential-discovery ordering, no run artifact or authority output, and a fresh-HOME FIFO credential probe. Keep positive execution confined to clearly non-installed test harnesses and exclude those harnesses from the production-entrypoint manifest.

## Evidence/report discipline

- Run every verifier, pytest invocation, and custom probe with its own fresh temporary `HOME`, isolated Git config, `GIT_CONFIG_NOSYSTEM=1`, `PYTHONDONTWRITEBYTECODE=1`, and pytest `-p no:cacheprovider`.
- Preserve exact initial/final manifest, patch, source-tar, HEAD, record-count, and candidate-tree evidence.
- Green full-suite output does not override a reproducible fail-open negative probe.
- For a checksum inside the report without self-reference, hash the complete report body first, then append a checksum section explicitly stating that the digest covers the bytes before that section. Beware the separator-newline trap: appending `\n## checksum` to a body that already ends in `\n` adds one unhashed byte before the heading. After the append, split the final bytes at the checksum heading, recompute SHA-256 over that exact prefix (including separator whitespace), and assert it equals the embedded digest. Then compute the final whole-file SHA-256 for the handoff response.
- Keep probes outside the candidate: use `runpy` or disposable `/tmp` fixtures, then rerun the exact frozen verifier before writing the report.
