> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR-grind readiness checker lessons

Use this reference when maintaining `scripts/hermes-busdriver-pr-grind-check` or any future Hermes-side PR-grind equivalent. These are implementation pitfalls discovered by dogfooding the checker on its own PR.

## Core pr-grind ordering

- PR grind is a loop against the **latest PR HEAD**: push → wait for checks/reviewer bots → collect feedback → fix → push again → repeat until clean.
- If relevant checks or reviewer-bot checks are pending, return `wait` before acting on stale comments from prior heads. Do not return `needs_fix` early just because old comments still exist.
- `mergeStateStatus=UNSTABLE` and `mergeStateStatus=UNKNOWN` are `wait`, never `clean`; treat hard merge states outside the accepted wait/clean set as blockers.
- After any fix push, previous clean/review/check state is invalidated.

## Live vs fixture mode

- Live mode must fail closed if any required GitHub feedback surface or Busdriver relevant-check semantics cannot be fetched/parsed.
- Fixture mode may use omitted/cached surfaces only behind an explicit `--fixture-mode` flag.
- Explicit `--relevant-check-script` paths are configuration assertions: missing, nonzero, or unparseable scripts must block, not fall back to generic `gh pr checks` parsing.

## GitHub pagination

- `gh api --paginate` can emit multiple JSON arrays. Use `--slurp` and flatten pages, or an equivalent concatenated-array parser.
- For GraphQL review threads, `reviewThreads(first:100)` is not enough if nested `comments(first:100)` reports `pageInfo.hasNextPage=true`. Either paginate nested comments or fail closed with a structured error; never trust partial thread state.

## Review-thread state

- REST PR review comments do not reliably expose `resolved`, `is_resolved`, or `thread.resolved` metadata. Use GraphQL review-thread state (`isResolved`, `isOutdated`, comment `databaseId`) to determine resolved/stale review-thread comments.
- Resolved or outdated thread comment IDs should be ignored.
- Active unresolved and non-outdated threads can remain actionable across pushes, even if their original comment timestamp or original commit predates the latest head.
- Dismissed or pending parent reviews must still suppress their inline comments; do not let active-thread logic revive comments from dismissed/pending reviews.
- GitHub may retarget REST `commit_id` for old comments to the current head. Use `original_commit_id` when deciding whether a bot inline comment is from a prior round.

## Review body classification

- Review bodies must be considered separately from inline comments. Bot review boilerplate such as Codex’s “Here are some automated review suggestions…” can be ignored only when the remaining body is truly empty after stripping exact boilerplate.
- Do not strip arbitrary `<details>` blocks; actionable text can live inside details. Only strip known boilerplate details such as “About Codex in GitHub”.
- Approved reviews are not automatically clean. Harmless exact approval text (`LGTM`, `Ship it`, `Great work!`, `Looks solid`, etc.) is non-actionable, but approved-with-caveat text such as “Approved, but this regression is broken” or “Please update the migration” is actionable.
- Same-reviewer review bodies should be evaluated newest-to-oldest, but non-submitted / non-actionable / stale reviews must not hide earlier actionable submitted feedback. A later harmless `APPROVED` review on the same head can supersede earlier body feedback from the same reviewer; `PENDING`, dismissed, stale, or non-actionable `COMMENTED` reviews should not.
- For bot reviewers, a current-head bot review can supersede older prior-round bot inline comments, but it must not suppress current-head inline findings from that same bot.

## Issue / top-level PR comments

- Top-level PR/issue comments must be bound to the latest head round. If head timing cannot be determined in fixture/incomplete data, treat unbound issue comments conservatively as actionable rather than dropping them.
- Commit authored/committed date is not always the PR-head push/review-round time. For live runs, prefer server-observed PR push activity (for example GitHub PushEvent where `payload.head` matches the PR head and `payload.ref` matches the branch) as the cutoff. If no push anchor is available, keep the cutoff unbound so comments remain conservatively actionable; do not use backdated commit metadata or delayed check-run starts to drop comments.
- Check-run timestamps can be useful diagnostic evidence, but they are not a safe issue-comment cutoff because checks may start after comments posted against the current head.
- Bot progress comments mean `wait`, not `clean` and not `needs_fix`, while the bot is explicitly processing. Keep the pattern narrow and bot-login-gated.
- Bot quota/rate-limit/pause comments are not ordinary progress. They should keep the PR non-clean until bounded-wait/policy handling decides whether to retry, ask for manual trigger, or bail. This applies even when the bot's GitHub status context is `SUCCESS`: a comment such as CodeRabbit “Review limit reached” / “couldn't start this review” means no real review occurred, so do not merge solely on the green status.
- CodeRabbit summary/walkthrough comments are non-actionable only when they are summary boilerplate; do not suppress rate-limit or actionable content mixed into a bot comment.
- When Busdriver `ack-ledger.sh` reports a reviewer bot has acknowledged the current head, suppress that bot’s stale top-level issue comments (including old rate-limit/progress comments) for that head. Match ACK SHA tokens safely: accept the exact 8-character head prefix or a longer hex prefix that the current head starts with; reject malformed or longer-than-head tokens.

## Freshness / race handling

- Read `headRefOid` before and after collection; if it changes, return `blocked` with a head-changed reason and force recollection.
- In live mode, avoid doing an initial feedback collection that will be discarded by a same-head refresh. A safer pattern is: initial view → fresh view/head check → checks → feedback → final head check → refresh checks → refresh feedback → final head check → classify.
- If the head is unchanged but the fresh PR view has changed (reviewDecision, mergeability, draft/state, mergeStateStatus), classify using the fresh view, not the stale initial view.
- Re-fetch relevant checks during same-head freshness handling; do not combine fresh comments with stale check results.
- Re-collect feedback after the final check refresh; do not combine fresh checks with stale comments/reviews. Check the PR head again after this final feedback pass before emitting `clean`.
- Keep result JSON explicit: `clean`, `wait`, `needs_fix`, `blocked`, plus blockers, check rows, pending rows, and actionable comment previews.

## Verification discipline

For every behavior change:

1. Add a focused regression first and observe it fail when practical.
2. Run targeted tests.
3. Run `python3 -m py_compile scripts/hermes-busdriver-pr-grind-check`.
4. Run full contract tests with `uvx --from pytest pytest tests/contract -q` when local pytest is unavailable.
5. Run Busdriver litmus review loop before commit.
6. Run relay smoke before push when the change touches the checker or gate semantics.
7. Push and restart pr-grind against the new PR HEAD; never merge immediately after a fix push.
