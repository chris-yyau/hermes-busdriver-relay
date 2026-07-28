# Executor-retirement PR-grind lessons

Use this when removing a production executor or fixing role/authority policy across runtime, manifests, tests, and docs.

Current authority: `coding-workflow-authority-map-v0.1.md`. This procedural guide must not override that policy map.

Closing phase: enter this guide only after steps 1–6 in `executor-retirement-and-policy-convergence.md` pass; return there for postmerge convergence after PR grind.

## Closure order

1. **Inventory every surface before editing.** Search production parsers, wrappers, manifests, consumer pins, status/brief envelopes, role resolvers, current-reference docs/ADRs, copied examples, and historical fixtures. A retired executor may remain only where the policy explicitly permits historical test evidence.
2. **Make the rejection contract explicit.** Test parser rejection, exact fail-closed reasons, empty/invalid config shapes, case and whitespace variants, and authority booleans. Add the contract first and observe expected RED.
3. **Validate aggregate/list paths independently.** A single-role lookup can reject a child `config_error` while `--list-*` still succeeds. List endpoints must scan every normalized child entry, validate child/error shapes, preserve deterministic precedence, and fail closed on any invalid fixed route.
4. **Pin exact trust metadata, not just identity.** Fixed roles must validate selected agent, adapter verification, dispatch blocker, and every mutation/finalization/dispatch flag. A correct agent name with forged trust metadata is still invalid.
5. **Name current policy directly.** When policy changes from “non-Codex” to “Pi-only,” add a `non_pi_*_allowed=false` invariant. Retain the old field only for schema compatibility, and teach every recursive authority validator that the new field is unsafe if true.
6. **Treat current docs as executable policy.** Include current-reference ADRs, active skill text, synchronized authority-map copies, copied config examples, and worker-envelope enums in semantic negative tests. Historical OpenCode prose must be past-tense or fixture-qualified; it cannot appear as a current lane, worker enum, digest-convergence item, or mutating mode.
7. **Close runtime-byte changes before PR grind.** For fixed-point resealing and downstream manifest validation, follow `executor-retirement-and-policy-convergence.md`; PR grind starts only after that closure passes.
8. **Freeze the exact candidate.**
   - Refresh the base with `git fetch --no-tags origin main`, then stage every intended new path. Read and record the entire two-column output of `git -c core.fsmonitor=false status --porcelain=v1 --untracked-files=all`: block on unexpected paths or unstaged tracked modifications, and record every deliberate index/worktree divergence. Require `git merge-base --is-ancestor origin/main HEAD` to pass; otherwise rebase before freezing. Record the base SHA from `git rev-parse origin/main` beside the candidate hash.
   - Freeze the staged candidate with `git --no-pager -c diff.algorithm=myers diff --cached origin/main --binary --no-color --full-index --no-renames --src-prefix=a/ --dst-prefix=b/ --unified=3 --no-ext-diff --no-textconv`. This reads indexed blobs instead of invoking worktree clean filters, pins deterministic format choices, and disables external diff/textconv helpers.
   - Record hash and line count. Run a secret/private-path scan on the frozen bytes before any external handoff; when binary files are in scope, justify `--binary` and inspect every path represented by binary literal chunks out-of-band, recording the result, or exclude those binaries for separate delivery. Run immutable review against that exact file, then verify the live staged diff still hashes identically before commit.
9. **Restart the PR grind after every head change.**
   - Repeat the fetch, ancestry, base-SHA, full-status, and staged-hash checks; then re-run the full suite, focused closure, static scan, readiness, immutable review, required checks, unresolved-thread query, and mergeability check.
   - Inspect unresolved threads, inline comments, issue comments, and full aggregate review bodies independently. An actionable outside-diff finding may exist only in a body attached to an older head commit; keep a body-only finding ledger until each finding is fixed with expected-RED evidence or explicitly rebutted. A later green reviewer check and zero unresolved threads do not prove closure. Do not treat a helper/check clean result as sufficient.
   - A prior green bot/check result is stale after force-push. Resolve a thread only after the fix is pushed and replied to.
10. **Verify before cleanup.** After merge, follow `executor-retirement-and-policy-convergence.md` completely; only then remove worktree and topic branches.

## Pitfalls

- A bot check marked “pass” because it was rate-limited is not a fresh review verdict; rely on the exact immutable review plus live unresolved-thread inspection and required-check policy.
- Updating only a README leaves active ADRs, status docs, skill references, or copied JSON examples contradictory.
- `coding_agent=pi` does not prove fixed primary/secondary/fallback route metadata or list-path safety.
- A full suite from the prior frozen hash is supporting evidence, not final-candidate evidence after another edit.
- Do not report merged, post-merge verified, or cleaned until each side effect is observed directly.
