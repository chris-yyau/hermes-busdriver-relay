# Delivery finalization script-group litmus lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this when dogfooding `hermes-busdriver-deliver`, `hermes-busdriver-delivery-status`, or `hermes-busdriver-litmus-status` and Busdriver litmus repeatedly finds finalization hardening issues in the staged scripts group.

## Durable lessons

1. **Treat backstop verdict files as a trust boundary.** A `--backstop-verdict-file` used to authorize `pre-pr-review` must be constrained to the target repo, must not be a symlink, must avoid symlink components, must be a regular bounded-size file, and should be read with no-follow/stat checks. Validate and revalidate through the same safe reader before passing transformed contents to Busdriver trusted marker writers.
2. **Do not use an empty explicit `--force-with-lease=<ref>:` for first push.** If the remote branch is absent, avoid pretending this is a create-only lease. Use a clearly safe first-push path, then fail closed if a post-failure remote recheck shows the branch appeared concurrently (e.g. `remote_branch_changed_before_push`).
3. **Before any push with a verified remote tip, verify ancestry.** A matching force-with-lease prevents racing against a different tip, but it does not prevent overwriting known remote commits if local `HEAD` is behind/diverged. Require the verified remote head to be an ancestor of local `HEAD` before pushing.
4. **Use the litmus-observed base when `--base` is omitted.** Delivery-status/litmus may resolve a default base that differs from `origin/HEAD` in unusual repos. For push/PR finalization checks, compare against the explicit `--base` when present, otherwise use the `litmus_status.summary.repo.base_ref` observed by the fresh evidence envelope. Do not recompute a different default and create false `pr_review_base_mismatch` blockers.
5. **Nested CLI flags must exist at every wrapper layer.** If `deliver` forwards `--litmus-base-ref` to `delivery-status`, then `delivery-status` must define that argparse flag and forward it to `litmus-status` as `--base-ref`; add contract tests for both parser acceptance and subprocess argv.
6. **Bound read-only Git helpers used under finalization locks.** Shared helpers such as `git_output()` should use timeouts and structured failure returns; otherwise a hung Git/credential/config helper can leave finalization locks held until TTL.
7. **Commit marker parsing must preserve accepted hash-bearing external formats.** If `deliver` now requires a staged diff hash from `litmus-status`, support every valid Busdriver marker format that embeds a 64-hex hash (`BUILTIN-<hash>`, bare hex, and external/pass variants with an embedded hash) while keeping hashless markers non-fresh unless live Busdriver semantics intentionally allow and the finalizer re-verifies the exclusion.

## Verification pattern

For each litmus finding:

```text
patch narrowly
→ add focused contract regression
→ run targeted contract tests
→ stage only scripts group
→ rerun Busdriver litmus
```

Do not advance to Delivery Mode commit until litmus returns PASS for the exact staged script group. Treat repeated low/medium findings as convergence signals; the scripts group is security-sensitive because it controls finalization side effects.