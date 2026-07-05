# PR98 Roadmap Brief + Cleanup Lessons

Context: finishing a relay Status/UX slice that added `hermes-busdriver-relay-brief`, synced roadmap/cleanup skill references, and created a Hermes-only script cron cleanup job while PR reviewer bots drove several fix rounds.

## Durable lessons

1. **Compact status helpers must fail closed on unverified inputs.**
   - A missing installed skill path must not be treated as clean skill sync; report a blocked/unverified skill-sync state.
   - A valid Git checkout that lacks `skills/busdriver-relay` must not be treated as a clean relay source; report repo skill source missing.
   - A non-Git or Git-status-failing `--repo` must not be reported as clean; expose repo Git/status availability and block the idle-clean decision.
   - Top-level `ok` should reflect critical child evidence such as contract-status success and skill-sync checked status.

2. **Read-only helpers should avoid incidental Git writes.**
   - Use `git --no-optional-locks status --short` for status probes that claim `read_only=true`; plain `git status` can refresh the index.
   - Preserve the two-column porcelain status format: do not `.strip()` `git status --short` output, because a leading space distinguishes unstaged-only changes (` M file`) from staged changes (`M  file`).

3. **Brief text should reveal all drift classes and derive from source data.**
   - A one-line status like `drift diffs=N` hides missing/extra file drift; include `missing=N extra=N diffs=N`.
   - Derive human-readable roadmap summaries from `ROADMAP_TASKS` labels rather than duplicating a second hard-coded task list.
   - Treat empty environment overrides (for example `HERMES_BUSDRIVER_INSTALLED_SKILL_DIR=""`) as unset, not as the current directory.

4. **PR-grind after reviewer fixes must restart from the latest head.**
   - After every fix push, rerun local verification and then start a new latest-head PR-grind pass.
   - Reviewer comments that look minor/trivial still block if the PR-grind checker classifies them as actionable.
   - Do not merge after a fix push until latest-head PR-grind is clean; wait/needs-fix/block states all preserve authority flags false.

5. **Recurring cleanup jobs should be captured as class-level relay knowledge, not a one-off task note.**
   - Use script-only `no_agent=true` cron for routine disk cleanup.
   - Keep stdout silent unless action/pressure/warnings are worth notifying.
   - Restrict automatic deletion to Hermes-owned or repo-local generated artifacts; never clear Claude/Codex/Grok/OpenCode/claude-mem durable state from a routine job.
