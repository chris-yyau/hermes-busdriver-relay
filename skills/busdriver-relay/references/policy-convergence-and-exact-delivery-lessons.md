# Policy Convergence and Exact Delivery Lessons

Use this when a role-policy, authority-map, runtime/config, or workflow-hygiene change must move through exact candidate review, squash delivery, post-merge verification, and installed-skill convergence.

## Exact-candidate discipline

- Bind every verdict to immutable `commit`, `tree`, and `parent` identities. Branch names and earlier green CI are not exact authority.
- Any fix commit invalidates the prior candidate's full-suite and independent-review verdicts. Focused evidence may explain the history, but the new exact tree needs its own required CI, full complement where the repository contract requires it, and independent read-only review.
- Keep semantic/content seals separate from temporal metadata seals. An unexplained mtime-only drift blocks only the exact review in which it occurred when that review contract requires temporal immutability; do not transplant it to a later candidate whose opening/closing semantic and temporal manifests are stable. Conversely, a matching Git tree does not erase temporal movement observed inside the same strict review.
- Record every deselected test by exact node ID and adjudicate why it is outside the complement. Never inherit a deselection rationale or test count from an older candidate after the tree changes.
- Compute diff evidence only after unsetting `GIT_EXTERNAL_DIFF`; use binary/full-index diff bytes when the authority format expects them.
- Keep candidate authority outside Git-tracked candidate docs. Embedding the candidate commit in a file changes that commit and creates an impossible self-reference. Track the SHA/tree in an external authority artifact instead.
- Seal only after local/remote HEAD, tree, parent, clean worktree, CI, unresolved review threads, and opening/closing reviewer seals all agree.

## Authority chronology in current-status docs

Keep three states separate:

1. the historical sealed ancestor and the evidence that sealed it;
2. any later merged prerequisite with its own independent seal/post-merge evidence;
3. the policy candidate represented by the document, which cannot borrow either earlier seal.

Write candidate status as an at-verification/pre-delivery state and point to the external authority artifact for exact identity. Contracts should enforce the three-state chronology, not freeze an old ancestor as today's `main/top`.

## Policy migration closure

A role migration is not docs-only. Close all of these together:

- runtime defaults and live relay config;
- producer and consumer authority semantics;
- adversarial contracts for clean-looking positive metadata;
- canonical docs, repo skill, installed skill, and trusted digest/inventory consumers.

`configured` or `resolved` means metadata exists, not that dispatch is allowed. Require production `programmatic_dispatch_allowed=false`, `adapter_verified=false`, `dispatch_allowed=false`, mutation/finalization authority false on every role, including clean resolved metadata. Treat `avoid_coding_agent_for_review=true` as a non-overridable safety invariant.

When installed skills contain a large historical knowledge base, do not replace the whole library with the smaller repo snapshot. Patch the active class-level policy surfaces and copy the critical current references byte-for-byte; mark superseded references historical/non-production.

## Minimal workflow-annotation hygiene

When pinning tools reject a valid action-tag annotation:

- prove the existing immutable SHA/tag relationship;
- change only the annotation accepted by the pinning tool (for example a major tag comment), never the SHA or workflow behavior unless separately requested;
- validate with the repository's pinned tool version, the current installed version, `actionlint`, diff scope, and existing CI;
- keep it in a separate hygiene PR from unrelated policy work.

If anonymous GitHub tag lookup hits a transient 5xx or rate limit, retry once after failure using authenticated API lookup without printing the token. Preserve the successful retry pattern, not the transient error as a permanent limitation.

## Merge and post-merge handling

- A GitHub squash merge may succeed remotely even if the CLI then fails while trying to check out a base branch already owned by another worktree. Read PR state and remote `main` before retrying; never issue a second merge blindly.
- Verify the squash tree equals the sealed candidate tree, wait for post-merge Tests/Security, then write post-merge authority.
- Update live config and installed skill only after the repository candidate is merged and post-merge verified.
- Remove the delivery worktree/branches and rebuildable candidate homes/tmp while preserving authority files and logs.
- For workflows triggered only by `push` to `main`, verify their real post-merge run instead of pretending pull-request CI exercised them.
