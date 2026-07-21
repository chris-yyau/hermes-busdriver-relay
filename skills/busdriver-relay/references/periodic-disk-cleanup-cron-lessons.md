> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Periodic Hermes-only disk cleanup cron lessons

Use when the user asks Busdriver/Hermes relay work to keep disk clean periodically after delivery or while relay work continues.

## Durable pattern

1. **Prefer a script-only cron job for routine cleanup.**
   - Use Hermes cron with `no_agent=true` so each tick costs no LLM tokens and the script controls exactly what is delivered.
   - Design stdout semantics deliberately: empty stdout means silent/no delivery; print only when meaningful space was cleaned, disk remains below threshold, or a cleanup warning needs attention.
   - Keep the prompt empty/minimal and make the script self-contained because cron runs in a fresh context.

2. **Default scope is Hermes-owned and repo-local generated artifacts only.**
   Safe automatic targets:
   - `/Volumes/Work/.hermes-runtime/tmp`, `sandboxes`, and age-bounded Hermes runtime caches;
   - `~/.hermes/tmp` and `~/.hermes/cache`;
   - relay repo-local `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.codegraph`, and `__pycache__`;
   - old Hermes/relay temp artifacts under `/private/tmp` or `/tmp` matching narrow prefixes such as `hbr-*`, `hermes-relay-*`, `hermes-smoke-*`, `hermes-delivery-*`, `hermes-busdriver-*`.

3. **Do not automatically clean other agents' durable state.**
   Never include these in a recurring job without fresh explicit user scope:
   - Claude Code plugin cache, VM bundles, projects, or marker state;
   - Codex sessions;
   - Grok/OpenCode state;
   - claude-mem stores;
   - Hermes `state.db`, sessions, auth, skills, memories, snapshots, or profiles.

4. **Bound noise and preserve observability.**
   - Use a low-disk threshold that reflects real pressure, not normal macOS accounting noise.
   - Report local Time Machine/APFS snapshots as a hint only; do not auto-delete snapshots from the recurring job.
   - Run an initial dry-run and one foreground run before scheduling. Confirm a follow-up dry-run is quiet or reports only expected low-disk state.

5. **Useful cron shape.**

```text
name: Hermes safe disk cleanup
schedule: 0 4 * * *
script: hermes_safe_disk_cleanup.py
no_agent: true
deliver: origin
```

## Pitfalls

- A recurring cleanup script that prints a normal “nothing to do” summary will spam Telegram every day. Keep it silent below the cleanup/report thresholds.
- A cron script that removes broad cache roots can break active Claude/Codex/Grok/OpenCode sessions. Clean children by age under Hermes-owned roots instead.
- macOS `df` may not improve after deletion because local snapshots retain blocks. Report snapshots; leave deletion to an explicit disk-pressure action, not the routine cron.
