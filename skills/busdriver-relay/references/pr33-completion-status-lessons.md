# PR33 Completion Status Lessons

Session context: after PR #30–#32 added finalization guardrails, dual-review readiness, advisory pre-PR evidence, and recursive authority hardening, PR #33 was a docs/status-only completion pass for `hermes-busdriver-relay`.

## Durable lessons

- When the relay reaches a completion/status pass, do not stop at updating `CURRENT_STATUS.md`. Search README and settling docs for older authority language that contradicts the new boundary.
- Distinguish two concepts explicitly:
  - **Relay surface:** scripts/launchers in the relay repo remain read-only/non-mutating for finalization; mutating executor/envelope, marker writes, mutating PR-grind fix loops, deploy/release/publish, and direct MCP/plugin routing are policy-blocked unless a stronger Busdriver-approved integration surface is added.
  - **Hermes Delivery Mode:** a user-explicit operator procedure where main Hermes may perform ordinary Git/GitHub finalization (`git commit`, `git push`, `gh pr create`, `gh pr merge`) only after litmus/pre-PR-equivalent checks, local verification, reviewer/check wait, latest-head PR-grind clean, merge, and post-merge cleanup. This is not the same as adding mutating finalization code to the relay.
- Reviewer bots will flag this distinction if docs say both “mutating finalization is policy-blocked” and “Hermes may commit/PR/merge” without naming Delivery Mode as an external operator procedure. Rewrite stale delivery-mode paragraphs rather than just adding a new status note.
- After docs-only completion PRs, still run the full delivery loop: `git diff --check`, markdown fence sanity checks, full contract suite, smoke, `hermes-busdriver-deliver --operation verify`, PR creation, PR-grind, fix reviewer comments, rerun PR-grind, merge, prune branch, and post-merge verification.
- Completion verdict should say: read-only/non-mutating relay surface is complete for current policy scope; remaining items are policy-blocked finalization surfaces, not the next safe implementation slice.

## Evidence shape worth preserving in docs

Use top-level pre-PR evidence fields, not a non-existent nested `authority` object:

```text
pre_pr_dual_review_evidence.schema hermes-busdriver-pre-pr-dual-review-evidence/v0
pre_pr_dual_review_evidence.dispatch_allowed False
pre_pr_dual_review_evidence.finalization_allowed False
pre_pr_dual_review_evidence.marker_write_allowed False
```

## Final verification pattern

Post-merge final check should include:

```bash
PYTHONDONTWRITEBYTECODE=1 uvx --from pytest pytest -p no:cacheprovider tests/contract -q
scripts/hermes-busdriver-smoke --plugin-root ~/.claude/plugins/marketplaces/busdriver --pretty
scripts/hermes-busdriver-finalization-readiness --repo . --plugin-root ~/.claude/plugins/marketplaces/busdriver --pretty

git status --short --branch
gh pr list --state open --limit 20 --json number,title,headRefName,baseRefName,isDraft,mergeStateStatus,url
```

Expected final posture: clean `main`, no open PRs, contract/smoke passing, finalization readiness read-only with `finalization_guardrails.status=non_mutating_relay_only`, `dual_review_readiness.programmatic_execution_allowed=false`, and `pre_pr_dual_review_evidence.*_allowed=false`.
