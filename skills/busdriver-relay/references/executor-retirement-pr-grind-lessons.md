# Executor-retirement PR-grind lessons

Use this when removing a production executor or fixing role/authority policy across runtime, manifests, tests, and docs.

## Closure order

1. **Inventory every surface before editing.** Search production parsers, wrappers, manifests, consumer pins, status/brief envelopes, role resolvers, current-reference docs/ADRs, copied examples, and historical fixtures. A retired executor may remain only where the policy explicitly permits historical test evidence.
2. **Make the rejection contract explicit.** Test parser rejection, exact fail-closed reasons, empty/invalid config shapes, case and whitespace variants, and authority booleans. Add the contract first and observe expected RED.
3. **Validate aggregate/list paths independently.** A single-role lookup can reject a child `config_error` while `--list-*` still succeeds. List endpoints must scan every normalized child entry, validate child/error shapes, preserve deterministic precedence, and fail closed on any invalid fixed route.
4. **Pin exact trust metadata, not just identity.** Fixed roles must validate selected agent, adapter verification, dispatch blocker, and every mutation/finalization/dispatch flag. A correct agent name with forged trust metadata is still invalid.
5. **Name current policy directly.** When policy changes from “non-Codex” to “Pi-only,” add a `non_pi_*_allowed=false` invariant. Retain the old field only for schema compatibility, and teach every recursive authority validator that the new field is unsafe if true.
6. **Treat current docs as executable policy.** Include current-reference ADRs, active skill text, synchronized authority-map copies, copied config examples, and worker-envelope enums in semantic negative tests. Historical OpenCode prose must be past-tense or fixture-qualified; it cannot appear as a current lane, worker enum, digest-convergence item, or mutating mode.
7. **Reseal after runtime-byte changes.** Any changed manifested script requires fixed-point runtime resealing until consumer digests stop changing, then run manifest/pin closure tests.
8. **Freeze the exact candidate.** Review `git diff origin/main --binary --no-ext-diff` so staged renames and unstaged changes are both included. Record hash and line count, run immutable review against that exact file, then verify the live diff still hashes identically before commit.
9. **Restart the PR grind after every head change.** Re-run the full suite, focused closure, static scan, readiness, immutable review, required checks, unresolved-thread query, and mergeability check. A prior green bot/check result is stale after force-push. Resolve a thread only after the fix is pushed and replied to.
10. **Merge and verify before cleanup.** Latest-head checks and reviews must be clean before merge. Post-merge, probe the retired parser rejection, the retained executor blocker, manifest absence, role/list fail-closed behavior, authority flags, and clean main; only then remove worktree and topic branches.

## Pitfalls

- A bot check marked “pass” because it was rate-limited is not a fresh review verdict; rely on the exact immutable review plus live unresolved-thread inspection and required-check policy.
- Updating only a README leaves active ADRs, status docs, skill references, or copied JSON examples contradictory.
- `coding_agent=pi` does not prove fixed primary/secondary/fallback route metadata or list-path safety.
- A full suite from the prior frozen hash is supporting evidence, not final-candidate evidence after another edit.
- Do not report merged, post-merge verified, or cleaned until each side effect is observed directly.
