# PR112 Pi-default dogfood lessons

## Context

The user explicitly changed relay policy from Codex-default implementation to Pi replacing Codex as the default implementation draft worker. The slice dogfooded the constrained Pi `bd_*` adapter and kept Busdriver/Claude as finalization authority.

## Durable workflow lessons

1. **Pi-default is a policy migration, not a one-line default change.** When promoting Pi over Codex, audit and update all of these surfaces together:
   - status/default route helpers (`DEFAULT_RELAY_CODING_AGENT`, default routes, role-policy strings);
   - real-agent smoke defaults;
   - planning helpers such as `hermes-busdriver-agent-balance-plan` (`selected_agent`, `current_agent`, and no-dispatch flags);
   - docs/status pages and authority maps;
   - installed-skill and repo-skill references;
   - tests that assert durable role-policy phrases.
2. **Preserve custom test/advanced command behavior when changing defaults.** If `hermes-busdriver-agent-draft` defaults to Pi, `--agent-cmd` without `--agent` must select `custom`, not Pi. Otherwise the launcher runs the shell command but later requires a Pi artifact (`pi-result.json`) and reports a false `blocked` result. Add a regression test asserting no `pi_artifact_error` for implicit custom runs.
3. **Balanced planning must track default implementation policy.** The read-only balance-plan helper should report Pi as the single gated mutating draft lane, while still keeping every authority flag false and execution flags false (`pi_called=false`, `codex_called=false`, `github_called=false`, etc.).
4. **Reviewer-bot stale wording checks require broad source search.** PR-grind may keep unresolved current-head threads for earlier comments until they are resolved or bots refresh. Before resolving, prove the finding is addressed by searching exact stale phrases across repo and installed skill copies, including hidden/truncated matches in long SKILL.md lines. Do not rely on a displayed snippet that omits the matching substring.
5. **Latest-head PR-grind still wins.** After every amend/force-push, treat earlier green CI/reviewer state as invalid; rerun required checks and PR-grind against the new head. Merge only after the latest head is clean or addressed threads are explicitly resolved with evidence.
6. **Merge from a neutral cwd if `gh pr merge` trips linked-worktree branch checks.** When the PR worktree is on the feature branch and the primary checkout already owns `main`, `gh pr merge` may invoke local git and fail with `fatal: 'main' is already used by worktree ...`. Re-run with explicit `--repo owner/repo` from a neutral directory (for example the Hermes runtime dir) so the GitHub merge proceeds without trying to checkout `main` in the feature worktree.
7. **Before deleting a PR worktree, inspect and preserve unexpected leftover WIP.** If `git worktree remove` refuses because the feature worktree contains modified/untracked files after PR merge, do not blindly force-delete. First run `git status`/`git diff`, classify whether the leftover diff belongs to the just-merged PR or a separate follow-up, save a patch under Hermes runtime if it is unrelated, then reset/clean only the throwaway PR worktree and remove it. Mention the preserved patch path in the final report.
8. **Post-merge evidence should include both GitHub merge-sha workflows and primary-repo local smoke.** After squash merge, sync the primary base branch, verify `HEAD == origin/<base> == mergeCommit`, watch `Tests`/`Security` (or repo-relevant workflows) for the merge SHA, and rerun contract/smoke from the primary checkout. Do not count the removed PR worktree as final state.

## Search phrases worth checking during Pi-default migrations

```text
Codex-worker
Codex as the worker
current normal draft
Codex lane = current
Codex writes normal drafts
Pi constrains tool access
Pi = deferred
implementation.primary.current = codex
relay.impl.primary = codex
selected_agent": "codex"
current_agent": "codex"
DEFAULT_RELAY_CODING_AGENT = "codex"
default="codex"
```

Codex may still appear in legitimate review/backstop/fallback contexts. The problematic pattern is Codex as the default/primary implementation draft lane or Pi as merely deferred/candidate after proof has passed.
