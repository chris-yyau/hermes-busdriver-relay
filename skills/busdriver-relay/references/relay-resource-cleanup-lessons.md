# Relay resource cleanup lessons

Use this when a Busdriver-relay / Hermes Delivery Mode session has finished and the user reports high resource use or asks to clean up system resources.

## Safe cleanup sequence

1. **Separate Hermes-owned background jobs from system processes.**
   - First use the Hermes process list for `terminal(background=true)` jobs; exited entries are just session history, not live processes.
   - Then inspect OS processes separately with `ps`, grouped by command family and parent PID.

2. **Verify repo housekeeping before process cleanup.**
   - Confirm the repo is clean and synced, the feature branch is gone locally/remotely, and no relay worktree remains.
   - Only then clean temporary artifacts and per-run caches.

3. **If the user mentions “no space”, “disk usage”, or corrects a generic cleanup audit, switch immediately to disk-pressure cleanup.**
   - Measure with `df -h /System/Volumes/Data /Volumes/Work` and `du -xhd 1 "$HOME"` before deleting anything.
   - Inspect likely large safe caches: `~/Library/Caches`, `~/.cache`, `~/.codex/.tmp`, `~/.codex/plugins/cache`, `~/.grok/marketplace-cache`, `~/.grok/downloads`, `~/.codegraph`, `~/.claude/cache`, `~/.claude/telemetry`, repo-local `.pytest_cache` / `.ruff_cache` / `.mypy_cache` / `.codegraph`, and `$SPACIOUS_RUNTIME_VOLUME` / `/Volumes/Work/.hermes-runtime/tmp` test temp trees.
   - Prefer moving rebuildable cache/temp workloads to `/Volumes/Work/.hermes-runtime/` when the system volume is tight, but do not move live tool runtime directories without explicit user intent because symlinked cache roots can affect app/tool startup.

4. **Delete only clearly disposable artifacts without asking again.**
   Safe examples after a completed relay PR or disk-pressure cleanup request:
   - repo-local `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.codegraph`, and `__pycache__` created by verification;
   - `/tmp` / `/private/tmp` relay evidence files such as `hbr-*`, `hbr-pr<N>-*`, `hermes-relay-*`, `hermes-smoke-*`, `hermes-delivery-*`, `hermes-busdriver-*`;
   - `~/.hermes/tmp/*` and `~/.hermes/cache/*`;
   - package/app caches that are clearly rebuildable, such as `~/Library/Caches/trivy`, `~/Library/Caches/ms-playwright-go`, `~/.cache/uv`, `~/.cache/chroma`, `~/.codex/.tmp`, `~/.codex/plugins/cache`, `~/.grok/marketplace-cache`, `~/.grok/downloads`, `~/.codegraph`, `~/.claude/cache`, and `~/.claude/telemetry`.

5. **If `rm -rf` does not improve `df`, check local APFS snapshots before assuming cleanup failed.**
   - Run `tmutil listlocalsnapshots /` and `diskutil apfs listSnapshots /System/Volumes/Data`.
   - A purgeable local Time Machine snapshot can retain deleted cache blocks and make `df` stay flat until the snapshot is removed or purged by macOS.
   - When disk pressure is the task and the snapshot is local/purgeable, deleting a clearly related local snapshot with `tmutil deletelocalsnapshots <timestamp>` may be the step that actually releases space. Re-measure `df` afterward.

6. **When the user wants only Hermes work moved to Work volume, use Hermes-only/per-process relocation.**
   - Do **not** change global shell rc files, global `launchctl setenv`, or other agents' homes/caches. Do not move/symlink Claude Code, Codex, Grok, OpenCode, or claude-mem state unless the user explicitly asks.
   - Use `/Volumes/Work/.hermes-runtime/` as the root for Hermes-owned runtime paths such as `tmp`, `xdg-cache`, `uv-cache`, `pip-cache`, `npm-cache`, `bun-cache`, `playwright-browsers`, `trivy-cache`, and `sandboxes`.
   - Put non-secret runtime env vars in the Hermes profile's `.env` so they apply only to Hermes processes for that `HERMES_HOME`: `TMPDIR`, `TMP`, `TEMP`, `XDG_CACHE_HOME`, `UV_CACHE_DIR`, `PIP_CACHE_DIR`, `NPM_CONFIG_CACHE`, `BUN_INSTALL_CACHE_DIR`, `PLAYWRIGHT_BROWSERS_PATH`, `TRIVY_CACHE_DIR`, `TERMINAL_SANDBOX_DIR`.
   - For a launchd-managed Hermes gateway, add the same keys to `~/Library/LaunchAgents/ai.hermes.gateway.plist` under `EnvironmentVariables`, then validate with `plutil -lint`. This affects only the Hermes gateway service, not the user's interactive shell or other CLI agents.
   - Ensure `terminal.env_passthrough` in `~/.hermes/config.yaml` is a YAML list containing those non-secret keys so Hermes terminal/`execute_code` child processes inherit the relocated paths. Beware: `hermes config set terminal.env_passthrough '[...]'` may serialize the JSON-looking value as a string; verify the parsed type and normalize to a YAML list if needed.
   - Verify with a fresh Hermes-process-style load that `tempfile.gettempdir()` resolves under `/Volumes/Work/.hermes-runtime/tmp` and that every configured directory exists. The currently running gateway may not pick this up until `/restart` or an external `hermes gateway restart`.

7. **Be conservative with persistent state.**
   - Do not delete `~/.hermes/state.db`, Hermes/Codex/Claude sessions, auth, skills, claude-mem stores, or recent state snapshots as part of automatic cleanup.
   - Do not blindly remove `~/.claude/plugins/cache`, `~/Library/Application Support/Claude/vm_bundles`, `~/.claude/projects`, `~/.codex/sessions`, or `~/.hermes/state-snapshots`; these are large but may be active runtimes, plugin installs, history, or rollback points.
   - If disk pressure is still real after safe cache cleanup, propose session prune / SQLite vacuum / older snapshot pruning as a separate explicit step.
   - Old snapshots can be pruned conservatively by age (for example older than 14 days) while keeping recent rollback points.

8. **Target process cleanup by ownership, not name alone.**
   - For Codex/OpenAI companion processes spawned for this relay repo, find `app-server-broker.mjs serve` processes whose command line has `--cwd <relay repo>` and kill that process tree only.
   - Do not kill all `codex`, `Claude`, `Happy`, `headroom`, or `Codex Computer Use` processes by broad pattern; many may belong to active user sessions or other worktrees.
   - When in doubt, report candidates and ask before killing.

9. **Distinguish unrelated hotspots.**
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
