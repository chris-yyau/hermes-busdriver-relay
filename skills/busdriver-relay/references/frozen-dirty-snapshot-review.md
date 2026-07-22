# Frozen dirty-snapshot review protocol

Use this when a review is scoped to an exact `HEAD + dirty tree` digest.

## Invariants

- Treat the requested digest as the review boundary, not merely metadata.
- Recompute the complete canonical snapshot before reading the diff and again immediately before reporting.
- Use the **same vetted canonicalization routine and constants** at both boundaries. Include at least: schema, canonical repo root, `HEAD`, comparison-base OID, exact porcelain status text, tracked binary diff, ordered untracked-file records (path/type/mode/size/content hash), and aggregate binary-diff hash.
- Run Git reads with hooks, fsmonitor, external diff/textconv, pager, optional locks, and ambient global/system config disabled where applicable.
- Do not infer equality from unchanged `HEAD`, base OID, status-line count, or filenames; dirty file bytes can drift while all of those remain unchanged.

## Sequence

1. Read the frozen manifest and expected digest.
2. Determine the review boundary explicitly:
   - **live frozen tree** — the live worktree itself is expected to match; or
   - **captured frozen artifact** — the caller supplied a complete tracked binary diff plus content-bound untracked records against recorded `HEAD`.
   - **pre-freeze live tree without a supplied digest** — do not establish the start boundary while a repair/test/status worker is still editing the candidate. Wait for mutators to quiesce, then record a complete start digest; any probes run before that point are exploratory only.
3. Recompute the canonical digest independently. If a pre-freeze tree changed while preliminary review was in progress, discard the preliminary boundary and restart from the first quiescent digest rather than mixing evidence from two generations.
4. For a live-tree boundary, if it differs, stop immediately and report `snapshot_drift`; do not inspect further or publish findings.
5. For a captured-artifact boundary, independently verify the manifest canonical hash, raw binary-diff hash/size, recorded OIDs, and every untracked file size/content hash. If all pass, reconstruct the candidate outside the source repository from recorded `HEAD`, apply the frozen binary diff, copy only verified untracked bytes, and require the reconstructed binary diff to reproduce the expected hash. A later live-worktree change is then informational, not drift of the captured review boundary.
6. Perform the read-only review against the attested live tree or reconstructed capture without checkout/reset/stash/test caches or source-repository writes.
7. Recompute the identical boundary immediately before reporting. For a reconstructed capture, recheck both source artifacts and reconstructed bytes.
8. If the selected boundary changes, discard all draft findings and report only `snapshot_drift`, including expected/observed snapshot and binary-diff digests plus unchanged OIDs when useful.
9. Only when both boundary checks pass may findings or `PASS` be reported.

## Pitfalls

- Unknown canonicalization is not proof of drift. Locate or reconstruct the producer contract before comparing.
- Once a known canonical routine passes at the start, an end mismatch is real drift even if `HEAD`, base, and status shape are unchanged.
- Never leak partially prepared findings after end-boundary drift; they describe a no-longer-frozen tree.
- Tool-generated temporary outputs must stay outside the reviewed repository.
