# Full role-map resolver slice lessons

Use when a live `~/.hermes/busdriver-relay/config.json` role map has drifted ahead of repo resolver/status support, or when the user says the relay config is only partially set.

## Durable lessons

1. **Do not stop at resolver-known subset restoration.**
   - If the user says “還有很多未設定”, audit the whole intended role map, not only roles currently accepted by `hermes-busdriver-relay-role`.
   - Live config may already contain valid future/candidate routes such as `relay.impl.*`, `relay.review.*`, `relay.ide.manual`, and `relay.expert_witness.*`; the repo slice should make those first-class only with explicit resolver inventory + tests.

2. **Manual IDE sidecar is Zed, not Cursor.**
   - Treat `relay.ide.manual=["zed"]` as the copyable/manual sidecar route.
   - Remaining `Cursor` mentions should be only reviewer-bot/history context, not the user's manual IDE.

3. **Pi/OpenCode/Codex/Claude role policy for this class of relay work.**
   - `relay.impl.primary = pi`.
   - `relay.impl.secondary = opencode` and `relay.impl.fallback = opencode`, but repo-changing OpenCode fallback still requires adapter/plugin proof before use.
   - `relay.pr.lead = codex`; Codex is review/backstop-focused by default, not normal implementation fallback.
   - `relay.pr.backstop = claude-code`.
   - `relay.ide.manual = zed`.

4. **First-class resolver slice checklist.**
   - Add the full route map to the status helper inventory.
   - Keep `avoid_coding_agent_for_review=true` by default for review/backstop/decision roles.
   - Add per-role metadata such as `review_independence_sensitive`; implementation/manual roles may intentionally match `coding_agent`, but review/backstop roles should degrade when they select the coding agent.
   - Add contract tests for `--list-roles`, full live role-map resolution, no-degrade expected routes, and degradation when a review-sensitive route points at the coding agent.
   - Update docs, repo skill source, installed skill source, and reference tests together; stale tests are often the first signal that docs still encode old Codex/Cursor/future-only policy.

5. **Worktree/PR continuation pitfall.**
   - If a planned continuation says to reuse an old PR worktree but that PR has already merged, do not resurrect stale worktree state. Create a fresh follow-up worktree/branch from the saved/live PR base branch, then port the still-relevant diff.

6. **Verification discipline.**
   - Run focused resolver/status/skill-reference tests, then the full contract suite.
   - Probe all 19 roles against the actual live config.
   - `hermes-busdriver-smoke` can fail while the worktree is intentionally dirty because its preflight requires `repo_clean`; treat that as expected until after commit/clean tree, not as proof the implementation is broken.
