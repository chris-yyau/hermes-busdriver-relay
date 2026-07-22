# Authority-chronology-only exact reviews
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this playbook when a previously reviewed policy candidate is restacked onto a newly merged, separately sealed base and the final delta is limited to status chronology plus its contract test.

## Review boundary

1. Bind the candidate from an external immutable pair `(commit, tree)`; do not require a status document to embed its own commit SHA, because that edit would change the SHA.
2. Verify the candidate parent is the current sealed base and that the hosting API reports the PR head/base pair expected by the handoff.
3. Compare against the previously reviewed candidate, not only against the new base. Require the exact changed-path set to equal the chronology document and its contract test. A complete tree-entry comparison is stronger than a prose claim that runtime policy is unchanged.
4. Treat every other identical tree entry as inherited review scope. Do not rerun unrelated broad security suites merely to make a narrow review look larger.

## Three-row chronology adjudication

Keep these authorities separate and ordered:

1. **Historical pre-merge seal** — identify the old main commit/tree and say explicitly that it is no longer current main/top.
2. **Current merged base seal** — identify the merge commit/tree and its own exact-suite, independent-review, and postmerge-CI authority. Never describe this base as “merged but unsealed” when a separate runtime reseal exists; equally, never imply it borrowed the historical stack seal.
3. **Current policy candidate** — state its status at candidate-verification time as unmerged/unsealed until its own exact suite, independent reviews, and delivery authority pass. It may inherit reviewed bytes, but it cannot borrow either prior seal.

The contract test should assert the exact three blocks and their order under the current-verification heading, plus their position before historical/superseded evidence. Search for stale contradictory “latest sealed main” wording outside that block.

## Minimal exact execution

- Materialize the named commit into owned external scratch with `git archive` or an equivalent byte copy; never run candidate tests in the protected checkout.
- Independently recompute the Git root tree from materialized modes and bytes, then run the changed chronology test and the required portable smoke using the workflow-pinned Python/pytest versions.
- Recompute the materialized tree after tests and require no local cache artifacts.
- Opening/closing seals must cover the protected worktree and linked-worktree/common Git metadata, and the close must remove all reviewer-owned scratch.

## Live evidence refresh

Refresh mutable PR identity at the end with the smallest possible endpoint set: PR state/head/base plus the immutable candidate commit/tree endpoint. Previously validated immutable base commit and run/job records do not need to be re-downloaded in the same broad batch.

A broad API refresh can fail halfway and obscure which evidence is fresh. Preserve the last valid immutable snapshots, then retry only the missing mutable boundary with bounded retries and atomic scratch-only promotion. The durable lesson is targeted refresh, not a claim that the provider API is unreliable.

## PASS threshold

PASS only when all are true:

- external candidate commit/tree/parent match locally and through the hosting API;
- the protected checkout is clean at opening and closing;
- the prior-candidate delta contains only the chronology document and its test;
- the three chronology rows are factually and temporally correct;
- focused exact-tree tests pass and post-test tree identity is unchanged;
- final live PR refresh succeeds; and
- scratch removal is proven.
