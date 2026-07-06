# PR109 Pi adapter review/rebase lessons

Use this when delivering a Hermes relay slice that adds or changes a constrained agent adapter, especially Pi or any other Busdriver-shaped tool harness.

## Review-bot fixes that should be treated as class-level blockers

When a worker adapter claims fail-closed authority, verify these explicitly before delivery:

- **Blocked artifacts must propagate as blocked.** If an adapter artifact is syntactically valid but has `status: "blocked"` or `ok: false`, the wrapper must return a blocked/nonzero result. Do not promote it to `needs_busdriver_review` merely because the worker process exited 0 and schema validation passed.
- **Authority schemas must require every false flag they document.** Top-level and nested `authority` objects should require all relevant false flags, including `deploy_allowed`, `release_allowed`, and `publish_allowed`, not just commit/push/PR/merge/marker/finalization.
- **Authority flags should be applied last in helper envelopes.** If a tool response helper accepts an `extra` map, spread/merge `extra` before the hardcoded false authority flags so caller-provided fields cannot override them.
- **Size guards should run before reading full file contents.** For read tools like `bd_read`, check `lstat`/file size first, then read the file; keep the byte-length check after read as a second guard for encoding edge cases.
- **Read-only git commands are not all equally safe.** For adapter-exposed `git status`, inject `-c core.fsmonitor=false`. For adapter-exposed `git diff`, include `--no-ext-diff` and `--no-textconv` so repo/user config cannot run external helpers.

## Rebase conflict pitfall

During `git rebase`, remember that conflict labels are inverted relative to ordinary merge intuition:

- `ours` / `HEAD` = the branch being rebased onto, usually `origin/main`.
- `theirs` = the commit being replayed, i.e. the feature slice.

Do not run `git checkout --ours` on conflicted skill/reference files and assume it kept feature work. If you use it for inspection or as a base, re-merge the feature changes intentionally before `git add` and `git rebase --continue`.

## PR-grind sequence

After opening a PR for a relay adapter slice:

1. Run PR-grind latest-head checks.
2. If blockers show `mergeable=CONFLICTING` / `mergeStateStatus=DIRTY`, fetch/rebase onto the live PR base before fixing comments.
3. Fix medium correctness/data-egress/authority findings before re-pushing.
4. Re-run full local contracts, real adapter smoke if available, relay smoke, then `push --force-with-lease` after a rebase.
5. Restart PR-grind after the new head SHA; earlier clean/pending evidence is stale.
6. If PR-grind still reports old actionable comments on the new head immediately after a fix push, classify it as `wait` until reviewer/check freshness is clear; do not merge from local verification alone.

## Stale rebase metadata pitfall

After resolving a rebase and amending fixes, Git may show a clean branch and `git rebase --quit` may say `fatal: no rebase in progress`, while a stale pseudo-ref such as `REBASE_HEAD` still exists in the worktree gitdir. Relay `delivery-status` treats `REBASE_HEAD` like active merge/rebase state and blocks with `git_merge_rebase_cherry_pick_state_active`.

Recovery pattern:

```bash
gd=$(git rev-parse --git-dir)
for p in MERGE_HEAD REBASE_HEAD CHERRY_PICK_HEAD BISECT_LOG rebase-merge rebase-apply; do
  test -e "$gd/$p" && printf 'present %s\n' "$p"
done
# Only after status is clean and git says no rebase is active:
git update-ref -d REBASE_HEAD
```

Then rerun `hermes-busdriver-delivery-status --pr <n>` and verify `repo.merge_state=false` before continuing PR-grind.

## Adapter follow-up hardening checklist

When reviewer bots flag constrained-agent adapter issues, make the fix durable with matching tests, not just code changes:

- blocked adapter artifacts must produce wrapper `status=blocked`, nonzero exit, and tests asserting a blocked-artifact error;
- stale result artifacts / stdout / stderr / event logs in a reused `--run-dir` must be deleted before launch, with a no-artifact fake-worker regression test;
- worker timeouts should return structured blocked JSON (for Pi, `pi_returncode=124` and `pi_timeout` in stderr tail), not crash with an exception;
- launcher wrappers should pass resolved absolute repo paths into child adapters so relative `--repo` inputs keep working after cwd changes;
- smoke wrapper defaults should mirror runtime env overrides when forwarding adapter args (for Pi: `PI_BIN`, `PI_BD_MODEL`);
- consume or delete any new fixture files in the same PR; orphan fixtures become reviewer blockers.
