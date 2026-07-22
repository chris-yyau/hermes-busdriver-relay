# Postmerge SUCCESS-only live closeout
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this for an independent, strictly read-only audit where a sealed postmerge authority must be reconciled against current GitHub and local-repository state. Return binary `PASS` or an exact blocker; an authority boolean is only a claim until its evidence and live postconditions are independently checked.

## Minimal evidence order

1. **Seal the authority bytes first.** Parse the authority and require the expected schema, `status: SUCCESS`, and `pass: true`. Recompute its declared self-digest and every immediate evidence digest. If the closing authority contains a filename-to-SHA-256 map, verify every locatable row too and report cardinalities such as `3/3` and `9/9`.
2. **Cross-bind the sealed artifacts.** Require the plan, postmerge snapshot, and merge-progress rows to agree on base, ordered PR/head pairs, top commit, tree, and expected deleted heads. Do not use filenames or prior prose as authority.
3. **Prove exact ancestry live.** Read the live default-branch ref and immutable commit API. Use the compare endpoint from sealed base to sealed top and require the exact merge base, ahead/behind counts, commit count, and ordered commit SHA list to equal the plan—not merely that base is an ancestor.
4. **Prove PR closeout live.** For every stack PR and evidence PR, require REST `state == closed`, non-null `merged_at`, base `main`, and exact planned head SHA. Separately require the current open-PR list to be empty.
5. **Prove branch cleanup live.** Read all remote heads and require every snapshot-declared split/CI head absent. Report the surviving heads rather than only a boolean.
6. **Prove required execution live.** Normalize live branch-protection requirements and compare them with the sealed required-context set. Select the newest `main`/`push` workflow generation by `(created_at, run_id)` for each required workflow; require exact top SHA and `completed/success`. Resolve every required check-run through its `details_url` to the selected run/job, then require the job itself `completed/success` from the expected app. A workflow-level success alone is insufficient.
7. **Prove local closeout without syncing.** Discover the actual repository first if no exact local path was supplied. Do not fetch, pull, reset, switch, or prune. Unset ambient Git routing variables, set `GIT_OPTIONAL_LOCKS=0`, then require origin identity, branch `main`, `HEAD == refs/heads/main == origin/main == sealed top`, exact tree, empty porcelain-v2 status with all untracked files, and empty staged/unstaged diffs.

## Non-required red workflow adjudication

A disclosed failure is non-blocking only after all of these are independently true:

- its workflow/job context is absent from the live required-policy set;
- every actual required context has fresh exact-SHA successful execution;
- the failed run is bound to the same sealed top and did not move `main`;
- its failed log is inspected and the claimed reason is reproduced from exact source bytes or upstream metadata;
- it is reported explicitly as maintenance debt and never counted as, or used to replace, required success.

For action-pin annotation failures, inspect the exact workflow line and resolve the claimed upstream tag/ref. If a legal non-semver tag resolves to the exact pinned commit while the maintenance tool rejects the annotation as not being a version comment, that corroborates the compatibility diagnosis; it does not excuse any required failure.

## Read-only implementation discipline

- Prefer one in-memory checker that reads JSON, calls `gh api --method GET`, and prints evidence to stdout. Do not write audit scripts or API snapshots unless durability was requested.
- Pass query fields with `-f`/`-F` under explicit GET rather than interpolating shell query strings; this avoids quoting/backgrounding mistakes around `&`.
- Do not use `git fetch`: compare the already-discovered local refs with a separately queried live remote ref.
- If no scratch is needed, create none and state `scratch_created=0`. If scratch is authorized, keep it below the named root, delete it before verdict, and verify absence.

## Mandatory final refresh

After optional diagnosis, run one bounded closer and then perform no more candidate operations. Freshly re-check:

- authority self/immediate evidence digests;
- live `main` and tree;
- every PR closeout row plus open-PR count;
- expected remote-head absence;
- required policy, newest required workflow runs, and required check conclusions;
- disclosed non-required failure classification;
- local branch/head/tree/clean state;
- review scratch absence.

Only a successful closer permits `PASS`. Lead the result with `PASS — no blocker`, then compact bullets for authority, exact identity/ancestry, CI IDs and context count, PRs, remote heads, local cleanliness, the disclosed non-required failure, and mutation/scratch footprint. Otherwise return the first exact mismatched row as the blocker.
