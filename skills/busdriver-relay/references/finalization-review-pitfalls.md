# Finalization Review Pitfalls

Use this reference when hardening or operating Hermes/Busdriver Delivery Mode, especially after Busdriver/Codex review finds trust-boundary issues.

## Staged diff hash binding

- Bind litmus/review evidence to the exact staged diff hash used by the commit gate.
- Use the same canonical bytes everywhere: `git diff --cached --no-ext-diff --no-textconv --no-color` hashed as full bytes. Do **not** `rstrip()` or otherwise normalize the diff before hashing unless the marker writer and gate both do exactly the same thing.
- After any patch/test change, recompute the staged hash and rerun review; do not reuse an older `.claude/litmus-passed.local` marker.

## Review-loop size ceilings

- Busdriver review can fail before LLM review if weighted/total lines exceed its ceiling. Keep the staged group under both thresholds, or use the review tool's own suggested `LITMUS_MAX_WEIGHTED_LINES=<n>` override only when raw total/files are still within the displayed limit.
- If the candidate exceeds raw total/files ceilings, split by logical commit group and repeat: targeted verify -> full contract -> fresh review -> Delivery Mode commit.

## Git trust boundaries

- Dirty/status helpers that consume `git status --porcelain` must preserve leading status columns. Use `rstrip("\n")`, not `strip()`, on stdout.
- Git helper calls used for status/dirty checks should disable local hook/config surprises where relevant, e.g. `-c core.fsmonitor=false` plus hardened env (`GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`).
- Push/PR remote checks must not trust rewrite-expanded URLs. Read raw local `remote.<name>.url`, require an actual GitHub origin, and block `remote.<remote>.pushurl`, `url.*.pushInsteadOf`, `url.*.insteadOf`, and local push modifiers such as `remote.<remote>.mirror`, `remote.<remote>.push`, `push.followTags`, and `push.pushOption`.
- `git push` from Delivery Mode should avoid repo-local hooks and tag side effects: include `--no-verify`, `--no-follow-tags`, and the required `--force-with-lease=<lease>` for the reviewed branch.

## Marker and artifact safety

- Commit gates should block staged Busdriver marker files across known state dirs (`.claude`, `.opencode`) and any configured state dir. Include local marker names treated as markers by delivery-status, e.g. `skip-litmus.local` and `pr-grind-clean.local`, not just review JSON files.
- Artifact write failures after a completed mutating side effect must preserve that completed side-effect status. Also preserve release-failed completed statuses such as `committed_release_failed`, `pushed_release_failed`, `pr_created_release_failed`, `merged_release_failed`, and `pre_pr_review_complete_release_failed`; never rewrite them to a generic retryable `blocked/artifact_write_failed` decision.

## Useful convergence pattern

1. Patch only the review finding.
2. Add focused regression tests for the exact trust-boundary failure.
3. Run focused tests, then targeted contract subset, then full contract.
4. Recompute staged hash and update litmus state.
5. Rerun fresh Busdriver review.
6. Only after review PASS, retry Delivery Mode commit.
