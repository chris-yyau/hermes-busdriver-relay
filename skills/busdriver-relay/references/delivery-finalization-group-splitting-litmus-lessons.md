# Delivery finalization group-splitting and litmus lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this when Hermes is dogfooding `hermes-busdriver-deliver` / Delivery Mode and the staged candidate keeps failing Busdriver litmus because of size, stale staged-diff hashes, or commit/pre-PR evidence mismatches.

## Core workflow lesson

When a user asks for end-to-end Delivery Mode completion, do not keep rerunning the same oversized staged diff. If litmus says `TOO_LARGE`, split the staged candidate into smaller coherent commits and run the full cycle for each:

```text
stage only one group
→ targeted tests for that group
→ Busdriver litmus init + run-review-loop
→ Delivery Mode commit only after PASS/fresh staged-diff evidence
→ repeat for remaining groups
```

If a combined script+test candidate is still too large, split further into script-only and test-only commits. Preserve non-current groups with `git stash push --keep-index` only after verifying the current staged set; later `stash pop`/apply and repeat the same cycle.

## Staged-diff hash and marker binding pitfalls

- `litmus-passed.local` 64-hex commit markers must expose a sanitized `diff_hash` so `deliver commit` can compare them with the current staged diff.
- The staged-diff hash must match Busdriver's writer semantics. Hash the raw `git diff --cached` byte stream exactly as produced, including trailing newline; do not decode to text or strip trailing newlines unless the live Busdriver writer does so.
- After any patch to address litmus feedback, rerun targeted tests, restage the exact group, rerun litmus, and treat old marker hashes as stale/mismatched.
- If `deliver commit` reports `commit_litmus_staged_diff_mismatch`, do not force commit. Recompute/review staged hash semantics and rerun commit-mode litmus for the exact staged diff.

## Base-ref and state-dir consistency

- Normalize refs before forwarding to Busdriver PR/litmus env. `refs/heads/main` should become `origin/main`; `refs/remotes/origin/trunk` should become `origin/trunk`; unsupported other `refs/*` should fail closed rather than being forwarded as `origin/refs/...`.
- Keep `--busdriver-state-dir-name` consistent across delivery-status evidence, finalization locks, trusted writer calls, and the actual `git commit` subprocess. If commit hooks are expected to read `.opencode`, pass `BUSDRIVER_STATE_DIR=.opencode` to `git commit`; otherwise hooks can fall back to `.claude` and validate/consume the wrong marker.
- Validate marker state dirs before any trusted writer invocation. Reject absolute paths, `.`/`..`, symlink components, and paths resolving outside the repo. Do this before setting `BUSDRIVER_STATE_DIR` for writer scripts.

## Dirty-tree and marker allowlist pitfalls

- For PR/pre-PR gates, trusted marker files may appear as tracked modifications (`M `, ` M`, `MM`, `A `, or `??`). Allow only exact Busdriver marker paths in configured state dirs; continue to block deletions, renames/copies, and all non-marker dirty entries.
- For commit gates, dirty checks should be scoped to unstaged/untracked non-marker changes while allowing the staged candidate.
- Use hardened Git diff/status probes for finalization evidence: strip ambient `GIT_*`/`GH_REPO`, set `core.attributesFile=/dev/null`, disable ext-diff/textconv/color, and fail closed on subprocess timeout or nonzero status.

## Finalization lock release semantics

Do not return from a `finally` block after a mutating side effect. A release failure must be reported in the run envelope, but it must not override a completed `git commit`/push/PR/merge result and make the side effect look like it never happened. Otherwise the operator may retry and duplicate a mutation.

## Test patterns to add with fixes

For each hardening fix, add focused contract coverage:

- diff hash timeout/OSError fail-closed;
- staged-diff hash preserves raw trailing newline;
- litmus-status summary includes sanitized 64-hex marker `diff_hash`;
- base-ref normalization for `refs/heads/*` and `refs/remotes/origin/*`;
- absolute/symlink marker state dirs blocked before trusted writers;
- tracked Busdriver marker modifications allowed while deletions/non-marker dirt remain blocked;
- `pr_review_fresh` reaches push/pr-create specific gates;
- `git commit` receives the requested `BUSDRIVER_STATE_DIR`;
- finalization lock release failure does not override a completed side-effect result.

## Operational warning

Repeated litmus timeouts during context collection are also a split signal. Inspect process state if needed, but prefer smaller staged candidates over raising limits indefinitely. A timeout, stale marker, or mismatch is not completion evidence.