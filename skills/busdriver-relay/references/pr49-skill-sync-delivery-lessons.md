# PR49 Skill Sync Delivery Lessons

Use when continuing `hermes-busdriver-relay` after a clean merged state and the next slice is a small skill/reference/docs sync PR.

## What happened

- The repo copy of `skills/busdriver-relay` drifted from the installed Hermes skill: the installed copy had a PR48 reference lesson and SKILL.md pointer that the repo lacked.
- Hermes used `hermes-busdriver-agent-draft` with scope `skills/busdriver-relay/**` to create the draft, then opened PR #49 and fixed reviewer feedback.
- CodeRabbit flagged hardcoded agent-private paths in the new reference (`~/.hermes/...`, `~/.claude/...`). The fix parameterized examples with explicit variables instead of embedding private install paths.
- PR-grind became clean on the latest head after the fix, then the PR was squash-merged and the reviewed repo skill was synced back into the installed skill path.

## Durable workflow lessons

1. **Parameterize private paths in repo skill references.**
   - In public/repo docs and reference examples, avoid hardcoding `~/.hermes/...` and `~/.claude/...` when the point is a reusable procedure.
   - Prefer explicit variables such as `REPO_SKILL_DIR`, `INSTALLED_SKILL_DIR`, and `BUSDRIVER_PLUGIN_ROOT`, with `: "${VAR:?message}"` guards in shell snippets.
   - It is still fine for live operator commands to use the local installed paths; do not teach future agents to depend on those paths as the generic example.

2. **`hermes-busdriver-deliver --verifier` executes argv, not a shell.**
   - Prefixes like `PYTHONDONTWRITEBYTECODE=1 uvx ...` fail because the dispatcher tries to execute `PYTHONDONTWRITEBYTECODE=1` as argv[0].
   - Use `env PYTHONDONTWRITEBYTECODE=1 uvx --from pytest pytest ...` when a verifier needs environment variables.

3. **Finalization lock release is branch/worktree identity-sensitive.**
   - The lock key includes the repo identity including branch/worktree. If a lock is acquired on a topic branch and `gh pr merge --delete-branch` switches or fast-forwards the checkout to `main`, releasing with `--repo .` from `main` can compute a different lock path and return `not-found`.
   - Release the lock before branch deletion/switch when possible.
   - If already switched and the branch was deleted locally, recreate/check out the recorded branch/ref from the lock or PR head, release with the recorded token from that branch identity, then return to `main` and delete the temporary local branch.

4. **Finalization-readiness expects the raw PR-grind loop payload.**
   - When `hermes-busdriver-deliver --operation pr-grind` wraps the loop, its JSON contains a nested `pr_grind_loop` payload.
   - For `hermes-busdriver-finalization-readiness --pr-grind-result-file`, pass the raw loop payload (or extract the nested `pr_grind_loop` to a temp file), not the outer deliver-run wrapper.

## Useful verification pattern

```bash
# Targeted reviewer-fix guard for path parameterization
python3 /tmp/check_pr49_review_fix.py

git diff --check -- skills/busdriver-relay/references/pr48-skill-source-sync-lessons.md

# Deliver verify with env-based verifier argv, not shell assignment prefixes
scripts/hermes-busdriver-deliver \
  --repo . \
  --plugin-root "$BUSDRIVER_PLUGIN_ROOT" \
  --mode execute \
  --operation verify \
  --run-id pr49-review-fix-verify \
  --verifier 'review-fix=python3 /tmp/check_pr49_review_fix.py' \
  --verifier 'contracts=env PYTHONDONTWRITEBYTECODE=1 uvx --from pytest pytest tests/contract -q -p no:cacheprovider' \
  --pretty

# If deliver wraps PR-grind, extract nested loop for finalization-readiness
python3 - <<'PY'
import json
wrapper=json.load(open('/tmp/hbr-pr-grind.json'))
json.dump(wrapper['pr_grind_loop'], open('/tmp/hbr-pr-grind-loop.json','w'), indent=2)
PY
```

## Pitfalls

- Do not treat an initial PR-grind clean/needs-fix state as durable after a reviewer-fix push. Rerun latest-head PR-grind on the new head.
- Do not resolve or dismiss reviewer feedback by editing around it superficially; verify the claim against current code and make the minimal policy-preserving change.
- If a finalization lock is left behind due to branch deletion, do not manually delete lock files first. Prefer using `hermes-busdriver-lock release` with the original token from the same recorded branch identity.
