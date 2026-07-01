# PR36 Finalization Readiness Contract Status Embedding Lessons

Session context: after `hermes-busdriver-finalization-contract-status` existed as a separate read-only ADR 0005 capability matrix, the next small dogfood slice embedded that status inside `hermes-busdriver-finalization-readiness` so downstream readiness consumers do not need to call a second helper.

## Durable implementation lessons

- Embed the contract-status payload in every downstream location that a readiness consumer may inspect:
  - top-level `finalization_contract_status`;
  - `handoff_envelope.finalization_contract_status`;
  - `handoff_envelope.evidence.finalization_contract_status`.
- Treat contract-status as nested helper evidence, not as trusted local constants. Invoke `scripts/hermes-busdriver-finalization-contract-status`, then validate before embedding:
  - subprocess exit code is 0;
  - `schema == hermes-busdriver-finalization-contract-status/v0`;
  - `read_only is true`;
  - `ok is true`;
  - recursively reject any authority/capability-style boolean that is not exactly `false` (`finalization_allowed`, `commit_allowed`, `push_allowed`, `pr_allowed`, `merge_allowed`, `deploy_allowed`, `release_allowed`, `publish_allowed`, `marker_write_allowed`, `dispatch_allowed`, `mutation_allowed`, `programmatic_execution_allowed`, `marker_interop_allowed`, `raw_codex_exec_allowed`, `non_codex_agent_enablement_allowed`, `capability_allowed`, `safe_to_execute_by_this_helper`, `implemented`, `retired`).
- If contract-status validation fails, emit a sanitized fail-closed `finalization_contract_status` object with all authority false and add a readiness blocker such as `finalization_contract_status_unavailable`.
- Regression tests should assert:
  - top-level and handoff/evidence contract-status objects match;
  - summary counts remain `remaining_work_count=5`, `policy_blocked_count=5`, `retired_count=0`, `capability_allowed_count=0`;
  - contract-status remaining-work IDs match `finalization_guardrails.remaining_work`;
  - the recursive no-positive-authority helper includes the extra contract-status booleans (`capability_allowed`, `safe_to_execute_by_this_helper`, `implemented`, `retired`, etc.).
- Update README/status/skill docs to state that finalization-readiness embeds contract status; otherwise future operators may keep telling downstream consumers to run both helpers.

## Delivery-mode pitfall confirmed

When preparing PR-mode backstop verdicts, compute the reviewed diff hash with Busdriver's exact shell semantics, not by hashing a saved diff file with Python. The trusted writer uses command substitution / `printf '%s' "$diff"`, which strips the trailing newline from `git diff`. Hashing a file that preserves the final newline produced a stale `reviewed_diff_hash != current base...HEAD` rejection. Use the same pattern as Busdriver:

```bash
base=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/||' || echo origin/main)
mb=$(git merge-base "$base" HEAD)
diff_text=$(git diff "${mb}...HEAD")
diff_hash=$(printf '%s' "$diff_text" | (sha256sum 2>/dev/null || shasum -a 256) | cut -d' ' -f1)
```

Then pass that `reviewed_diff_hash` into the read-only backstop verdict before `run-review-loop.sh --write-backstop-verdict` and `--write-pr-marker`.

## GitHub merge partial-failure pitfall

If `gh pr merge --squash --delete-branch` returns a transient HTTP error (for example `502 Bad Gateway`), do **not** assume the merge failed. Immediately verify both PR state and `origin/<base>` before retrying or updating the branch. In this session GitHub had already advanced `origin/main` with the squash commit even though `gh` returned 502 and the PR still appeared open briefly. Running `gh pr update-branch` afterward made the PR branch merge the already-updated base, and a second squash merge created an empty duplicate squash commit with the same tree. Safer recovery sequence:

```bash
git fetch origin --prune
gh pr view <PR> --json state,mergedAt,mergeCommit,headRefOid,baseRefName,mergeStateStatus
# Compare base tip/tree before any retry/update-branch:
git log --oneline origin/<base> -3
git diff --stat origin/<base>...HEAD
```

If the base already contains the PR changes but GitHub still shows the PR open, wait/re-check or close as duplicate only with explicit operator judgment; do not run `update-branch` or a second merge attempt until the base/PR inconsistency is understood.

## Branch/review housekeeping pitfall

Before pushing a new branch, re-check `git status --short --branch` after all helper/smoke commands and any concurrent subagents finish. A sibling process can update a docs/status file (for example installed Busdriver plugin version) after the first commit. If that happens after the branch has been pushed but before a PR exists, do **not** rely on `git push --force-with-lease`: Hermes smart approval may block force-push. Prefer either (a) add a normal follow-up commit on the same remote branch if a PR already exists, or (b) create a replacement branch and later delete the stale remote branch during post-merge cleanup.

## Verification pattern

For this slice class, use:

```text
py_compile relevant helpers
→ focused finalization-readiness/contract-status tests
→ full tests/contract
→ hermes-busdriver-smoke
→ finalization-readiness sample confirming embedded contract_status fields
→ deliver verify artifact when proceeding to PR
→ commit litmus, PR-mode Codex lead, read-only backstop, trusted writers, PR creation, latest-head PR-grind loop
```
