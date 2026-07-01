# Litmus / Pre-PR Marker Freshness Lessons

Session context: while adding a read-only `hermes-busdriver-litmus-status` helper to `hermes-busdriver-relay`, Busdriver commit-mode litmus caught marker-freshness pitfalls that should apply to any future relay status/finalization helper.

## Pitfalls caught by Busdriver litmus

1. **Never follow marker symlinks or echo raw marker contents.**
   - A repo-controlled `.claude/litmus-passed.local` (or PR marker) can be a symlink to a readable local file.
   - A read-only status helper that follows the symlink and returns `value` can disclose file contents in JSON.
   - Safer pattern: use `lstat`, reject symlinks with `unsafe_symlink=true`, keep `fresh=false`, and expose only bounded metadata / hashes, not arbitrary full marker content.

2. **PR review artifacts require age-bound freshness, not just `status` + `diff_hash`.**
   - Busdriver PR artifacts (`pr-codex-lead.local.json`, `pr-backstop-verdict.local.json`) are accepted only when:
     - JSON parses to an object;
     - `status == "PASS"`;
     - `diff_hash` equals the current `base...HEAD` hash;
     - `ts` is an integer (not bool);
     - `0 <= now - ts <= LITMUS_PR_BACKSTOP_MAX_AGE` (default 3600s unless Busdriver config says otherwise).
   - Missing, future, or expired timestamps must be stale/fail-closed.

3. **Do not invent commit marker semantics.**
   - `litmus-passed.local` is governed by live `pre-commit-gate.sh`, not by an intuitive “equals HEAD SHA” rule.
   - Before reporting a commit marker as fresh, JIT-read the current gate acceptance logic (including marker prefixes such as `BUILTIN-` or other accepted formats, reviewed-commits behavior, and consumption semantics).
   - If the helper cannot exactly match live gate semantics, report `unknown_or_unverified` / stale with a warning; do not mark it fresh or imply commit authority.

4. **PR diff hash semantics must match Busdriver exactly.**
   - Writer/gate semantics use the merge-base and `git diff "${merge_base}...HEAD"`, captured through command substitution / `printf '%s'` and then SHA-256.
   - PR-mode empty diffs fail closed in Busdriver writers/gates; do not treat SHA-256(empty) as a valid PR review hash for freshness.

## Recommended relay implementation pattern

- Read marker files with symlink checks and bounded output.
- Return freshness booleans plus parse/read errors; never return secret-sized raw values.
- Include authority flags at root/decision (`finalization_allowed`, `commit_allowed`, `push_allowed`, `pr_allowed`, `merge_allowed`, `marker_write_allowed`) and keep them false.
- Add tests for symlink rejection, missing/expired/future `ts`, malformed JSON, empty PR diff, base-ref failure, and unknown commit marker formats.
- Re-run Busdriver commit-mode litmus after fixes; if staged diff changes after a reviewer/backstop PASS, recompute diff hash and re-run the review/backstop.