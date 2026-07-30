# Recover interrupted Claude runs without risking tmux

Use this when a Busdriver/Claude run disappears, reaches `--max-turns`, kills its terminal host, or leaves partially reviewed WIP.

## Reconstruct before resuming

1. Require an explicit session ID, then locate that exact transcript under the encoded project in `~/.claude/projects/`; never select a session by newest mtime alone. Before `--resume`, verify transcript evidence binds the session to the intended repository, working directory, and opening `HEAD`. Fail closed when any identity is absent or mismatched.
2. Parse actual assistant `tool_use` commands and `tool_result` records. A missing final response is not evidence that nothing ran.
3. Inspect the repository, index, live-installed copies, review state, and tmux state before changing anything. Preserve staged and unstaged ownership.
4. Separate direct evidence from likely aftereffects. A transient `getcwd` error often means a process remained inside a deleted temp directory; verify the repo path and surviving process CWDs before blaming APFS or permissions.

## Resume the same work

Prefer print mode for autonomous recovery:
```sh
claude -p --resume "$SESSION_ID" \
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

Minimum safe setup defines cleanup before allocation and installs the trap immediately after `WORK` exists, before any later checked command:

```sh
cleanup() {
    sock=$(tmux display-message -p '#{socket_path}' 2>/dev/null || true)
    case ${sock:-} in
        "$WORK"/*) tmux kill-server 2>/dev/null ;;
    esac
    [ -n "${WORK:-}" ] && rm -rf -- "$WORK"
}

WORK=$(mktemp -d) || exit 1
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

unset TMUX
TMUX_TMPDIR=$WORK/socket
mkdir -p "$TMUX_TMPDIR" || exit 1
export TMUX_TMPDIR
```

The cleanup trap is active before `mkdir` or any other fallible setup. Any cleanup that can terminate a server must fail closed:

Never use naked `tmux kill-server` in test cleanup unless every command is explicitly bound to a private `-L`/`-S` endpoint or the resolved socket is proven to be under the test directory.

## Safe RED/GREEN reproduction

1. Start a disposable **outer** tmux server with a unique `-L` label and private `TMUX_TMPDIR`.
2. Run the suspect test with `TMUX` pointing to that outer socket. Before the fix, only this disposable server may die.
3. Apply the minimum root fix: `unset TMUX` plus socket-guarded cleanup.
4. Re-run and assert:
   - the suite passes;
   - the outer canary survives;
   - the default tmux session list is byte-for-byte unchanged;
   - disposable sockets and temp directories are removed.

Do not run a known-broken tmux test from a real/default tmux server just to obtain RED.

## Finish through the gate

- Continue the existing Busdriver/Litmus loop; do not reset its WIP or use skip files.
- If `--max-turns` stops the finalizer, resume it again rather than taking an unreviewed shortcut.
- After PASS, install the reviewed version and re-run the nested outer-canary check.
- Compare repo and live-installed copies, then verify a clean tree and `HEAD == origin/<branch>`.
- Report non-blocking linter diagnostics separately; do not describe them as a full pass.
