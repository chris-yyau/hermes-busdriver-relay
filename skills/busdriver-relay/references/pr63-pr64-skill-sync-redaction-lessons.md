# PR63–PR64 Skill-Sync Redaction and Docs-Refresh Lessons

Use when a relay continuation discovers installed-skill drift after a docs/status merge, especially when syncing a newly created installed reference back into the repo source.

## What happened

- After PR62 refreshed `docs/CURRENT_STATUS.md`, final audit found installed Hermes skill drift again: repo `SKILL.md` differed and installed-only `references/pr61-pr62-continuation-lessons.md` existed.
- PR63 synced that installed reference into the repo, added a `SKILL.md` pointer, and added durability coverage.
- Independent Grok backstop initially failed the PR because the installed reference copied session-local/private paths into durable repo docs:
  - user home / Hermes agent-run baseline paths;
  - temp verifier paths.
- The fix was to sanitize the durable reference using placeholders such as `<current-status-verifier>` and `<Hermes agent-run baseline.json>`, patch the installed skill copy to match, and strengthen tests/verifier checks so private paths cannot reappear.
- After PR63 merged, final audit was clean for skill source but `docs/CURRENT_STATUS.md` was again stale because it still described PR61 evidence. PR64 became the follow-up docs-only status refresh to PR63 evidence.

## Durable workflow updates

1. **Sanitize installed-skill references before repo sync.** Do not copy user-home, temp, agent-run, or one-off artifact paths into repo-tracked skill references. Replace with symbolic placeholders (`<current-status-verifier>`, `<Hermes agent-run baseline.json>`, etc.) before commit/PR.
2. **Patch installed and repo copies together when redacting synced references.** If the source of drift is the installed skill, sanitize the installed reference too; otherwise the next `diff -qr` audit will immediately recreate the same drift.
3. **Backstop failures on private path leakage are blocking.** Treat durable-doc private path leakage as at least medium/high severity for relay references, even when no secret value is present.
4. **Durability tests should include negative leakage assertions.** For new skill-sync references, assert the full relative path appears in `SKILL.md`, important lesson phrases appear in the reference, and known private/local path patterns are absent.
5. **Expect skill-sync PRs to trigger a follow-up docs/status refresh.** After a skill-sync PR merges, final audit may find `docs/CURRENT_STATUS.md` still naming the previous PR/head/test count. If so, do a docs-only refresh rather than leaving stale evidence.
6. **Keep docs/status refreshes evidence-only.** Updating `CURRENT_STATUS` after PR63/PR64 must not imply new finalization, marker-write, commit/push/PR/merge, deploy, release, publish, or direct MCP/plugin authority.

## Verification pattern

```text
installed-vs-repo diff shows installed-only reference / SKILL.md pointer drift
→ copy/sanitize reference into repo source
→ patch installed copy to the same sanitized text if it contained private paths
→ add/strengthen durability tests:
   - full `references/<file>.md` path in SKILL.md
   - important lesson phrases present
   - private/local path patterns absent
   - placeholders present when paths were redacted
→ `diff -qr skills/busdriver-relay $INSTALLED_SKILL_DIR` clean
→ focused skill-reference tests
→ full contract/deliver verify
→ commit litmus + commit/amend
→ PR-mode lead + independent backstop
→ trusted PR marker writers
→ PR create + post-PR marker cleanup
→ latest-head PR-grind
→ readiness, merge, branch/lock cleanup
→ final audit; if only CURRENT_STATUS evidence is stale, run a docs-only refresh PR
```

## Pitfalls

- Do not treat an installed skill reference as automatically safe to vendor into the repo. Installed skills often contain session-local evidence that should be parameterized before becoming repo history.
- Do not satisfy drift by changing only the repo copy after redaction; keep installed and repo copies byte-aligned.
- Do not weaken tests to only check basenames or generic phrases. Full relative path and leakage-negative assertions prevent silent recurrence.
- Do not stop at PR merge if the docs/status evidence now lags behind the newly merged skill-sync PR.
