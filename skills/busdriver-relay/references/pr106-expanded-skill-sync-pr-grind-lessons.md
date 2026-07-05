# PR106 expanded skill-sync and PR-grind lessons

## Trigger

Use this note during Hermes↔Busdriver relay skill-source sync slices when a tiny installed↔repo drift expands while the PR is already open, especially when the sync introduces a new `skills/busdriver-relay/references/*.md` file.

## Lessons

1. **Re-run whole-skill compare after every mid-slice skill-library update.** If `skill_manage` patches the installed skill while a repo sync PR is in flight, immediately treat installed↔repo skill compare as stale. Re-copy or re-patch the repo source from the installed skill before committing or pushing more changes.

2. **New reference files need durability tests in the same PR.** When syncing a new `skills/busdriver-relay/references/*.md`, add or update `tests/contract/test_skill_references.py` to assert:
   - the reference file exists;
   - `SKILL.md` points at `references/<file>.md`;
   - the reference contains durable key phrases;
   - private/local paths from `PRIVATE_PATH_LEAKS` are absent;
   - any known path-placeholder policy is asserted explicitly.

3. **Do not dismiss reviewer-bot “convention” comments when PR-grind marks them actionable.** Even if focused and full contract tests already pass, a missing durability assertion is a valid quality gap for this repo. Add the smallest test and rerun the focused/full contract evidence.

4. **Fix documentation-surface corrections against the authoritative upstream wording.** For Pi SDK / ResourceLoader wording, keep the surfaces distinct:
   - `createAgentSession()` uses a ResourceLoader for extensions, skills, prompt templates, themes, and context files.
   - tools and session setup belong to `createAgentSession()` / programmatic embedding APIs, not the ResourceLoader itself.

5. **Patch installed and repo copies together for reviewer doc fixes.** If a reviewer catches a factual wording issue in a reference that came from the installed skill, patch the installed skill first (or at least before final audit), then sync the repo copy from installed so whole-skill compare returns clean.

6. **After reviewer-fix pushes, restart latest-head evidence.** A follow-up commit invalidates the prior PR-mode review and PR-grind result. Rerun PR-mode litmus against the latest branch diff, rerun PR-grind against the latest PR head, and only merge after PR-grind reports clean.

7. **Resolved threads may need one more PR-grind poll.** If a bot resolves its own actionable thread shortly after the first post-fix PR-grind, rerun the bounded PR-grind loop once against the same latest head. Stop after it reports clean; do not keep polling once clean.

8. **Use scoped git identity/signing env for final full-suite verification.** Some contract tests create throwaway git repos. Run final full contract tests under scoped `user.name`, `user.email`, `commit.gpgsign=false`, and `tag.gpgSign=false` so local signing or SSH-key prompts do not contaminate unrelated test fixtures. The lesson is the scoped env retry pattern, not the transient signing failure.

## Minimal safe PR106-style sequence

```text
whole-skill compare
→ sync all current installed drift into repo source
→ add durability test for any new reference
→ focused/full tests + smoke + deliver verify
→ commit-mode litmus + commit/push
→ PR-mode litmus + PR-grind
→ fix actionable bot feedback if any
→ rerun latest-head PR-mode litmus + PR-grind
→ squash merge
→ release lock
→ final audit: clean main, open PRs 0, locks 0, skill-sync clean, contract policy_blocked remaining=5 allowed=0, authority all false
```
