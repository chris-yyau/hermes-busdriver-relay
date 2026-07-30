# Recover interrupted Claude runs without risking tmux

Use this when a Busdriver/Claude run disappears, reaches `--max-turns`, kills its terminal host, or leaves partially reviewed WIP.

## Reconstruct before resuming

1. Require an explicit session ID, then locate that exact transcript under the encoded project in `~/.claude/projects/`; never select a session by newest mtime alone. Before `--resume`, verify transcript evidence binds the session to the intended repository, working directory, and opening `HEAD`. Fail closed when any identity is absent or mismatched.
2. Parse actual assistant `tool_use` commands and `tool_result` records. A missing final response is not evidence that nothing ran.
3. Inspect the repository, index, live-installed copies, review state, and tmux state before changing anything. Preserve staged and unstaged ownership.
4. Separate direct evidence from likely aftereffects. A transient `getcwd` error often means a process remained inside a deleted temp directory; verify the repo path and surviving process CWDs before blaming APFS or permissions.

## Resume the same work

Before the first resume or setup command, clear imported aliases/functions and dangerous shell environment, then authenticate the absolute `CLAUDE_BIN` path.

Prefer print mode for autonomous recovery:
```sh
"$CLAUDE_BIN" -p --resume "$SESSION_ID" \
  --max-turns 40 \
  'Continue from the interrupted state. Preserve existing staged and unstaged WIP, inspect, reproduce safely, test, and report. Do not commit or push without fresh explicit authorization.'
```

Keep the normal permission boundary. Do not add `--dangerously-skip-permissions` by default: repository and transcript content from the interrupted session are part of the resumed context and must not gain unrestricted execution authority. Use that flag only when the user explicitly authorizes the privilege, the resumed inputs are trusted, and Busdriver hook coverage has been verified; it is not a routine recovery flag. Recovery authorization covers inspection and verification only; obtain fresh explicit authorization before commit or push even if the interrupted prompt mentioned delivery.

Set the repository as `workdir`. Route `TMPDIR` to the user's designated runtime area. If Claude exits at `--max-turns`, the filesystem and transcript contain real side effects: inspect both, then resume the same session with a focused continuation prompt. Do not restart from scratch or infer current state from the last visible prose.

### One-shot background tasks are not durable

Do not let a print-mode `claude -p` finalizer launch gate-bearing tests with its own `run_in_background` and then end its turn. The child task may be terminated with the CLI session, leaving a zero-byte task-output file plus partial caches while the final prose still says the suite is running.

For long gates, either keep the Claude process attached and run them synchronously, or let Hermes own the bounded process through its tracked process runner. After an early exit:

1. Recover the task ID and output path from the JSONL transcript.
2. Verify both the process table and task-output bytes; prose is not completion evidence.
3. Remove only identified cache artifacts, then re-bind the candidate hash and repository status.
4. Resume the same Claude session with the existing review findings and verified external test evidence; do not restart the review or silently rerun an expensive suite.

Also re-check `HOME`, `USER`, `LOGNAME`, and `PATH` before subsequent operator commands. A persistent shell snapshot can outlive the delegated process; restore expected values rather than diagnosing missing auth or binaries from a poisoned environment.

## Critical tmux isolation rule

`TMUX` contains an absolute socket path and overrides `TMUX_TMPDIR`. Exporting a private `TMUX_TMPDIR` is **not isolation** when a test starts inside a real tmux pane.

Before tmux setup, authenticate absolute `TMUX_BIN`, `MKTEMP_BIN`, `KILL_BIN`, `RM_BIN`, and `SLEEP_BIN` paths. Require the authenticated tmux to support `new-session ... [shell-command [argument ...]]`; fail closed instead of joining command and arguments into a shell string. Record the original tmux socket from the inherited `TMUX` value before changing the environment. Opening and closing canary observations must use that exact `-S` endpoint, or record `absent`.

The private server uses one fixed socket for creation, probes, and cleanup. The test process must not be able to replace its socket namespace:

```sh
cleanup() {
    rc=$?
    trap - EXIT INT TERM
    if [ -z "${TMUX_SERVER_PID:-}" ]; then
        if [ -e "$SOCK" ]; then
            printf '%s\n' 'private_tmux_identity_unknown' >&2
            exit 126
        fi
    elif [ ! -e "$SOCK" ]; then
        printf '%s\n' 'private_tmux_socket_missing' >&2
        exit 126
    else
        socket_pid=$("$TMUX_BIN" -S "$SOCK" display-message -p '#{pid}') || {
            printf '%s\n' 'private_tmux_identity_unknown' >&2
            exit 126
        }
        if [ "$socket_pid" != "$TMUX_SERVER_PID" ] || ! "$KILL_BIN" -0 "$TMUX_SERVER_PID" 2>/dev/null; then
            printf '%s\n' 'private_tmux_identity_changed' >&2
            exit 126
        fi
        if ! "$TMUX_BIN" -S "$SOCK" kill-server; then
            printf '%s\n' 'private_tmux_cleanup_failed' >&2
            exit 126
        fi
    fi
    if [ -n "${TMUX_SERVER_PID:-}" ] && "$KILL_BIN" -0 "$TMUX_SERVER_PID" 2>/dev/null; then
        printf '%s\n' 'private_tmux_still_running' >&2
        exit 126
    fi
    if ! "$RM_BIN" -rf -- "$WORK"; then
        printf '%s\n' 'private_tmux_workdir_cleanup_failed' >&2
        exit 126
    fi
    exit "$rc"
}

WORK=$("$MKTEMP_BIN" -d) || exit 1
SOCK=$WORK/tmux.sock
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

unset TMUX
"$TMUX_BIN" -f /dev/null -S "$SOCK" new-session -d -s private-canary "$SLEEP_BIN" 3600
pid=$("$TMUX_BIN" -S "$SOCK" display-message -p '#{pid}') || exit 1
case $pid in ''|*[!0-9]*) exit 1 ;; esac
TMUX_SERVER_PID=$pid
```

The cleanup trap is active before server creation. Every later tmux command uses the authenticated `"$TMUX_BIN" -S "$SOCK"` endpoint. Run the suspect test only inside an OS sandbox that denies it write access to `$WORK`; same-UID directory permissions alone are not a boundary, so fail closed if that sandbox is unavailable. Cleanup binds to the captured server PID, verifies termination before deleting the directory, and exits nonzero while preserving evidence on uncertainty.

Never use naked `tmux kill-server`, ambient `tmux`, or user configuration for test cleanup.

## Safe RED/GREEN reproduction

1. Start a disposable **outer** tmux server with the authenticated binary, `-f /dev/null`, and one exact private `-S` socket.
2. Run the suspect test with `TMUX` pointing to that outer socket. Before the fix, only this disposable server may die.
3. Apply the minimum root fix: `unset TMUX` plus socket-guarded cleanup.
4. Re-run and assert:
   - the suite passes;
   - the outer canary survives;
   - the original exact `-S` canary endpoint is byte-for-byte unchanged, or remains `absent`;
   - disposable sockets and temp directories are removed.

Do not run a known-broken tmux test from a real/default tmux server just to obtain RED.

## Finish through the gate

- Continue the existing Busdriver/Litmus loop; do not reset its WIP or use skip files.
- If `--max-turns` stops the finalizer, resume it again rather than taking an unreviewed shortcut.
- After PASS, install only when the original task or current user separately authorized installation; interrupted-session recovery never grants install authority.
- Compare repo and live-installed copies, then verify a clean tree and `HEAD == origin/<branch>`.
- Report non-blocking linter diagnostics separately; do not describe them as a full pass.
