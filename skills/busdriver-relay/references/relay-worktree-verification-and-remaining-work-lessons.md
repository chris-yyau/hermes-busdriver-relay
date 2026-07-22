# Relay worktree verification and remaining-work lessons

Use this when a relay continuation/verification request references target tests or files that are not present in the current checkout.

## Lessons

- Do not assume the primary repo checkout is the active worktree. If the main checkout is clean or target tests are missing, run a worktree discovery step and locate the branch/worktree that actually contains the dirty WIP before concluding tests are absent.
- For verification requests like “run these targeted tests + full tests,” first report the checkout actually used if it differs from the primary repo path. This prevents a false “test not found” result from the wrong worktree.
- Passing targeted/full tests on a dirty relay worktree is not a delivery-complete state. Immediately distinguish:
  - verified dirty WIP (tests passed), from
  - deliverable completion (reconciled dirty tree, staged intended diff, final gates/backstop, commit, push/PR, PR-grind, merge, cleanup).
- When the user asks “what remains?” after tests pass, use a compact remaining-work audit: dirty tree, staged/unstaged/untracked split, skill-sync drift, commit/PR existence, missing backstop/gates, PR-grind, merge/cleanup.
- If available, `scripts/hermes-busdriver-relay-brief --repo . --brief` is the right read-only summary after local test verification; use its `next_safe_slice` and skill-sync drift fields to ground the remaining-work answer.

## Minimal sequence

1. Phase-0 read: repo root, branch, status, staged/unstaged/untracked, worktree list when needed.
2. If target tests are absent in the current checkout, search sibling relay worktrees before declaring failure.
3. Run requested targeted tests in the matching worktree.
4. Run the full suite from the same worktree.
5. For “remaining work,” check current branch PR status plus relay brief/status helpers, then answer in terms of delivery state rather than only test state.
