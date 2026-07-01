# Relay resource cleanup lessons

Use this when a Busdriver-relay / Hermes Delivery Mode session has finished and the user reports high resource use or asks to clean up system resources.

## Safe cleanup sequence

1. **Separate Hermes-owned background jobs from system processes.**
   - First use the Hermes process list for `terminal(background=true)` jobs; exited entries are just session history, not live processes.
   - Then inspect OS processes separately with `ps`, grouped by command family and parent PID.

2. **Verify repo housekeeping before process cleanup.**
   - Confirm the repo is clean and synced, the feature branch is gone locally/remotely, and no relay worktree remains.
   - Only then clean temporary artifacts and per-run caches.

3. **Delete only clearly disposable artifacts without asking again.**
   Safe examples after a completed relay PR:
   - repo-local `.pytest_cache` and `__pycache__` created by verification;
   - `/tmp` / `/private/tmp` relay evidence files such as `hbr-*`, `hbr-pr<N>-*`, `hermes-relay-*`, `hermes-smoke-*`, `hermes-delivery-*`, `hermes-busdriver-*`;
   - `~/.hermes/tmp/*` and `~/.hermes/cache/*`.

4. **Be conservative with persistent state.**
   - Do not delete `~/.hermes/state.db`, sessions, auth, skills, or recent state snapshots as part of automatic cleanup.
   - If disk pressure is real, propose session prune / SQLite vacuum / older snapshot pruning as a separate explicit step.
   - Old snapshots can be pruned conservatively by age (for example older than 14 days) while keeping recent rollback points.

5. **Target process cleanup by ownership, not name alone.**
   - For Codex/OpenAI companion processes spawned for this relay repo, find `app-server-broker.mjs serve` processes whose command line has `--cwd <relay repo>` and kill that process tree only.
   - Do not kill all `codex`, `Claude`, `Happy`, `headroom`, or `Codex Computer Use` processes by broad pattern; many may belong to active user sessions or other worktrees.
   - When in doubt, report candidates and ask before killing.

6. **Distinguish unrelated hotspots.**
   - High CPU may come from unrelated apps (for example an Electron calendar renderer), not Hermes. Report this separately instead of attributing all resource pressure to Hermes.

## Useful verification probes

- Live Hermes background jobs: Hermes `process list`.
- Repo state: `git status --short --branch`, `git worktree list`, `git ls-remote --heads origin <branch>`.
- Process families: `ps -axo pid,ppid,%cpu,%mem,rss,etime,command` and group by `hermes_cli.main gateway`, `codex app-server`, `app-server-broker.mjs`, `Codex Computer Use`, `claude`, `happy-coder`, `headroom`.
- Disk pressure: `df -h /System/Volumes/Data`, `du -sh ~/.hermes ~/.hermes/*`.

## Pitfalls from dogfood

- `pgrep -af` on macOS can produce noisy output; prefer `ps -axo ... | awk` for grouped summaries.
- A cleanup script that kills a parent process may terminate the running shell/tool call; run a quick follow-up probe to verify what changed before continuing.
- Treat exited Hermes process records as historical handles, not live resources.
