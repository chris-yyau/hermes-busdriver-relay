# Delivery Mode hook preservation and backstop lessons

Context: while dogfooding Hermes Delivery Mode finalization for `hermes-busdriver-relay`, pre-PR independent backstop review caught two classes of authority regressions after contract tests had passed.

## Durable lessons

1. **Backstop verdict is required before PR evidence.** `execute --operation pre-pr-review` may require a validated `hermes-busdriver-backstop-verdict/v0` JSON bound to the exact clean branch candidate (`origin/main...HEAD`), not just local contract tests or a commit-mode litmus marker.
2. **Do not stop at the first PASS if the operation surface changed.** A full-branch independent backstop can still find cross-slice authority drift after per-slice Busdriver review PASS. Run it again after fixing review blockers and after each new Delivery Mode hardening commit.
3. **OpenCode/adapters must use an allowlisted child environment.** Do not pass ambient provider tokens or arbitrary env into external agent subprocesses. Forward only generic process context plus explicit adapter contract variables (`OPENCODE_BD_*`, `BUSDRIVER_STATE_DIR`) and explicitly required Busdriver plugin roots (`BUSDRIVER_PLUGIN_ROOT`, `CLAUDE_PLUGIN_ROOT`). Never wildcard-prefix allowlist variables such as `LC_*`; `LC_SECRET_TOKEN`-style names are possible.
4. **Mutating Delivery Mode must preserve Busdriver hook/runtime surfaces.** `git commit-tree` + `git update-ref`, `git push --no-verify`, or force-push-style shortcuts may look safer locally but bypass Busdriver hooks and violate ADR-style no-bypass contracts. Use hook-preserving `git commit` / `git push` and test that hooks actually run.
5. **Contract tests should prove the authority boundary, not encode bypasses.** If a test asserts `--no-verify` or hook bypass as desired behavior, invert it: assert the bypass is absent and add a hook fixture that fails unless the expected hook surface executes.
6. **Success-path mutating coverage matters.** For `pre-pr-review`, `commit`, `push`, `pr-create`, and `merge`, test lock acquire/release evidence, redacted mutating-run transcript shape, operation-specific authority flags, and the exact side-effect name (`busdriver_write_pr_marker`, `git_commit`, `git_push`, `gh_pr_create`, `gh_pr_merge`).

## Practical checklist before Delivery Mode push/PR

- Clean worktree and no stashes left from split slices.
- Full contract suite green on current HEAD.
- Independent full-branch backstop PASS bound to `origin/main...HEAD`.
- Pre-PR markers produced through Busdriver trusted writer commands, not raw `.claude/*` writes.
- Push command preserves hooks and avoids `--no-verify` / force-push shortcuts.
- PR creation verifies remote head matches local reviewed head.
