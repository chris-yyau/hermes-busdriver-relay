# PR48 Skill Source Sync Lessons

Use when continuing `hermes-busdriver-relay` and the repo copy of `skills/busdriver-relay` drifts from the installed Hermes skill.

## What happened

- The repo skill source lagged the installed Hermes skill, so the safe next slice after a clean main was a docs/skill-source sync.
- A direct mirror from installed skill to repo carried accumulated session notes, but reviewer bots found that some older reference lessons encoded unsafe or stale delivery guidance.
- The fix round preserved the useful session references while aligning them with current policy: Codex-only active relay scope, no Hermes-written Busdriver markers, no force-push default, and current helper field names.
- After PR merge, the installed skill was refreshed back from the reviewed repo copy so future Hermes sessions load the corrected skill library.

## Durable workflow

1. Treat repo-vs-installed skill sync as a docs/reference slice, not runtime code.
2. Use agent-draft only with scope `skills/busdriver-relay/**`; main Hermes remains verifier/finalizer.
3. Do **not** blindly trust the installed skill copy as authoritative when copying into the repo. Review/sanitize reference lessons for current policy before merge:
   - active draft implementation remains Codex-only unless explicitly validated/approved;
   - Hermes Delivery Mode must not write Busdriver markers directly;
   - prefer normal follow-up commits for PR feedback; do not teach force-push as the default fix path;
   - stale helper field names and verifier examples should be updated to current contract output.
4. PR-grind feedback on skill/reference docs is real workflow feedback. Fix valid P1/P2 issues and straightforward P3 clarity issues before merge.
5. After the repo PR merges and post-merge verification passes, sync the reviewed repo skill back into the installed skill path, then verify `diff -qr` is clean.

## Useful verification

```bash
: "${REPO_SKILL_DIR:?set REPO_SKILL_DIR to the repo skill directory}"
: "${INSTALLED_SKILL_DIR:?set INSTALLED_SKILL_DIR to the installed skill directory}"
: "${BUSDRIVER_PLUGIN_ROOT:?set BUSDRIVER_PLUGIN_ROOT to the Busdriver plugin root}"

# Repo skill equals installed skill after final sync
diff -qr "$REPO_SKILL_DIR" "$INSTALLED_SKILL_DIR"

# Skill/reference tests
PYTHONDONTWRITEBYTECODE=1 uvx --from pytest pytest \
  tests/contract/test_skill_references.py tests/contract/test_smoke.py \
  -q -p no:cacheprovider

# Full repo confidence before/after PR
uvx --from pytest pytest tests/contract -q
python3 -m py_compile scripts/hermes-busdriver-*
scripts/hermes-busdriver-smoke --plugin-root "$BUSDRIVER_PLUGIN_ROOT" --repo . --pretty
```

## Pitfalls

- If an agent-draft verifier times out but leaves a scoped diff, release any stale `agent-draft` lock and run `hermes-busdriver-gate postflight` manually against the draft baseline before continuing.
- A broad forbidden-term grep across all references can over-block historical notes. Prefer targeted checks against the specific files/claims under review, or require the unsafe term to appear only in a safe “do not do this” context.
- CodeRabbit rate-limit comments mean incomplete coverage, but a latest-head PR-grind clean result may still be acceptable when other reviewer surfaces/checks are clean under the current bounded-wait policy.
