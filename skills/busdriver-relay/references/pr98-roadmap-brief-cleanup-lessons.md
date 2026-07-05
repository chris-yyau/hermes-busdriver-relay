# PR98 Roadmap Brief + Cleanup Lessons

Context: finishing a relay Status/UX slice that added `hermes-busdriver-relay-brief`, synced roadmap/cleanup skill references, and created a Hermes-only script cron cleanup job while PR reviewer bots drove several fix rounds.

## Durable lessons

1. **Compact status helpers must fail closed on unverified inputs.**
   - A missing installed skill path must not be treated as clean skill sync; report a blocked/unverified skill-sync state.
   - A path that exists but is not a directory (for example a regular file passed as `--installed-skill`) must also be unverified/fail-closed.
   - Treat empty installed-skill overrides as unset, both from env (`HERMES_BUSDRIVER_INSTALLED_SKILL_DIR=""`) and explicit CLI args (`--installed-skill ""`); never resolve them to cwd.
   - A valid Git checkout that lacks `skills/busdriver-relay` must not be treated as a clean relay source; report repo skill source missing.
   - A non-Git, missing, or Git-status-failing `--repo` must not be reported as clean; expose repo Git/status availability and block the idle-clean decision with structured JSON instead of tracebacks.
   - If `--repo` points inside a worktree subdirectory, resolve the Git root before comparing repo skill source to the installed skill.
   - Top-level `ok` should reflect critical child evidence such as repo Git/status verification, contract-status success, and skill-sync checked status.

2. **Read-only Git probes must be isolated and config-stable.**
   - Strip inherited `GIT_*` identity/path variables before subprocess Git probes; `GIT_DIR` / `GIT_WORK_TREE` inherited from hooks or wrapper processes can otherwise make a status helper inspect the wrong repository despite a correct `cwd`.
   - Use `git --no-optional-locks` for status probes that claim `read_only=true`; plain `git status` can refresh the index.
   - Override config-sensitive dirty checks: use `-c status.showUntrackedFiles=all status --short --untracked-files=all` so local repo config such as `status.showUntrackedFiles=no` cannot hide untracked WIP.
   - Preserve the two-column porcelain status format: do not `.strip()` `git status --short` output, because the leading index/worktree columns distinguish unstaged-only changes from staged changes.

3. **Brief text should reveal all drift classes and choose the right reconciliation direction.**
   - A one-line status like `drift diffs=N` hides missing/extra file drift; include `missing=N extra=N diffs=N`.
   - Repo-only extra files mean “sync repo skill reference to installed skill,” not “copy installed reference back to repo.” Installed-only missing files mean the reverse. Mixed drift should say to reconcile rather than imply one direction.
   - Derive human-readable roadmap summaries from `ROADMAP_TASKS` labels rather than duplicating a second hard-coded task list.

4. **PR-grind after reviewer fixes must restart from the latest head.**
   - After every fix push, rerun local verification and then start a new latest-head PR-grind pass.
   - Reviewer comments that look minor/trivial still block if the PR-grind checker classifies them as actionable.
   - Do not merge after a fix push until latest-head PR-grind is clean; wait/needs-fix/block states all preserve authority flags false.

5. **Recurring cleanup jobs should be captured as class-level relay knowledge, not a one-off task note.**
   - Use script-only `no_agent=true` cron for routine disk cleanup.
   - Keep stdout silent unless action/pressure/warnings are worth notifying.
   - Restrict automatic deletion to Hermes-owned or repo-local generated artifacts; never clear Claude/Codex/Grok/OpenCode/claude-mem durable state from a routine job.
