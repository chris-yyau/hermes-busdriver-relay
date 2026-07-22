# Frozen Relay Candidate Consistency and Negative-Probe Lessons

Use this reference when a frozen relay candidate includes an immutable manifest plus a byte-exact binary Git diff and the review spans production, tests, schemas, docs, status, ADRs, skills, and authority.

## Review an immutable artifact, not post-freeze worktree drift

If the live worktree has advanced after freezing but the supplied manifest and binary diff authenticate successfully, do not silently review the live files. Reconstruct an isolated candidate from the manifest's exact HEAD, apply the authenticated binary diff, and copy only untracked files whose path/mode/size/hash match the manifest. Verify that regenerating the tracked binary diff from the reconstruction is byte-identical to the frozen artifact. Label live worktree changes as post-freeze and exclude them.

This reconstruction exception applies only when the immutable artifact is complete and independently authenticated. If the boundary is only a claimed worktree digest with no complete artifact, ordinary snapshot drift remains fail-closed.

If the source fingerprint changes during the review, immediately invalidate source-dependent conclusions and rerun the affected probes against the new bytes. Re-read exact finding locations instead of carrying forward stale line numbers, because concurrent repairs can fix one issue while leaving another unchanged. Keep an opening fingerprint, a fingerprint beside each destructive or expensive probe batch, and a closing fingerprint. A closing fingerprint different from the reviewed probe boundary is not a clean closure; either wait for a stable candidate and restart the affected lanes or report the concurrent drift explicitly.

## Negative probes that passing happy-path tests miss

1. **Ignored-file enumeration caps**
   - Create more ignored files than the configured baseline limit.
   - Mutate an item beyond the retained prefix.
   - Postflight must report overflow and block; silently truncating both snapshots creates a bypass.

2. **Path-glob segment semantics**
   - Probe `src/*.txt` against `src/nested/file.txt`.
   - `*` must not cross `/`; reserve recursive matching for `**`.
   - Run the same corpus against the outer gate and every adapter. Two equally permissive layers do not provide defense in depth.

3. **Private-runtime parent symlinks**
   - Test symlinks at every destination component, not only the copied credential source or final file.
   - Predictable/reused run directories plus `mkdir(parents=True, exist_ok=True)` can allow an intermediate symlink to redirect private config or auth outside the run root even when the final open uses `O_NOFOLLOW`.
   - Prefer collision-resistant exclusive run-directory creation and dirfd-based no-follow traversal for every component.

4. **Schema/runtime validator parity**
   - Validate every positive and negative fixture through both the published JSON Schema and production validator.
   - Test both directions: schema-accepts/runtime-rejects and runtime-accepts/schema-rejects.
   - Include status/boolean correlations, required blockers, unique arrays, exact authority keys, and Python `bool` versus integer edge cases.

5. **Fail-closed dispatch metadata**
   - Permission-like fields must be explicitly present and correctly typed.
   - Never default missing `programmatic_dispatch_allowed` or `adapter_verified` to true.
   - Reject contradictions such as dispatch allowed with adapter unverified, or a non-null blocker with dispatch allowed.
   - Resolve/read-only role availability separately from programmatic execution authority; review-role resolution must not imply that policy-blocked dual review is executable.

## Documentation and status checks

Build an operation matrix from production and tests before reading prose:

- actually capable of side effects when evidence passes;
- exposed but intentionally always blocked with an exact reason;
- read-only/status-only;
- policy-blocked or absent.

README, CURRENT_STATUS, ADRs, skill guidance, help text, and capability rows must use that distinction. An exposed `pr-create` or `merge` CLI choice is not an implemented mutating capability if production always returns an atomic-binding-unavailable blocker.

Cross-check production `--help` against every skill workflow. Remove stale claims for agent routes or smoke modes no longer exposed. Compare repo skill source with the installed skill as a separate drift check; do not claim synchronization from reference-link tests alone.

## Isolated test execution without invalidating the snapshot

Run write-producing tests from a temporary copy, but preserve enough repository identity for repo-aware helpers:

- A source-only copy with `.git` omitted can create false failures in status, branch, dirty-tree, or installed-skill drift tests.
- Prefer a standalone temporary repository copy containing the frozen worktree bytes and usable Git metadata. If the source is a linked worktree, materialize independent `.git` metadata rather than copying a pointer back to the reviewed repository.
- Disable pytest caches and bytecode where practical, then delete the temporary copy.
- Treat failures caused solely by missing Git metadata as harness defects, not candidate defects; rerun in the faithful temporary repository before reporting.
- Recompute the frozen boundary in the original worktree after the suite.

## Evidence discipline under tool ceilings

A started background test suite is not a passing suite. If its completion output cannot be collected, report test status as unverified. Likewise, if a final hash recomputation cannot be performed, distinguish the successful initial binding from an unavailable closing-boundary check; never imply a complete hash-bound CLEAN review.
