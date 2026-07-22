# Security hardening for standalone relay runners

Use this reference when immutable review findings touch subprocess containment, trusted artifact writes, or transitive digest pins across several standalone relay scripts.

## 1. Bounded subprocesses must assign one lifecycle owner

A retention limit applied after `communicate()` is not a bound. For cooperative trusted children, the production primitive should:

1. launch with bounded concurrent drains for stdout and stderr;
2. enforce byte limits while reading, not after retention;
3. make one layer solely responsible for timeout/overflow termination and reap;
4. return distinct timeout, overflow, launch-failure, and child-exit channels;
5. ensure outer wrappers never signal again after the owner returns a terminal result.

`start_new_session=True` plus `killpg` is only cooperative process-group cleanup, **not hostile-code containment**. Two hazards require explicit handling:

- `process.poll()` may reap the leader. Signaling `killpg(process.pid, ...)` afterward can hit a reused PGID.
- A descendant can call `setsid()`, leave the group, retain a pipe, and outlive group cleanup.

Therefore do not promise “all descendants are dead” from process groups alone. If arbitrary repository-controlled verifier commands require a guarantee and the host has no stable kernel-owned containment handle, fail closed before launch and remove the installed executor/dormant unlock branch; keep any needed executor only in a source-separated test harness. See `references/reviewer-finding-adjudication-and-process-lifecycle.md`.

Maintain enumerating contract tests for every bounded launch site. Exercise timeout, overflow, ordinary exit, leader-exit-with-pipe-holder, and an outer-layer canary that fails on post-reap signaling. Tests for adversarial descendants must not claim containment unless the implementation uses an OS primitive they cannot escape.

### Descriptor-bound Git on macOS

Do not assume a directory descriptor can be passed to Git as `/dev/fd/N`; macOS can reject that shape with `ENOTDIR`. A durable alternative is a child pre-exec step that `fchdir()`s to the authenticated Git-directory descriptor and executes Git with `GIT_DIR=.`. The ABA test must prove dispatch was reached and that replacing the pathname cannot redirect Git after authentication; an early preflight refusal is a vacuous pass.

## 2. Preserve test injection when replacing `subprocess.run`

Moving production from `subprocess.run` to bounded `Popen` often breaks tests that monkeypatch `subprocess.run`, even when production behavior is correct.

- Keep an internal, non-user-selectable bounded seam where practical.
- Otherwise retarget test doubles to the bounded seam; never restore an uncontained production launch merely to satisfy old mocks.
- A test adapter should translate a `CompletedProcess`-shaped fake into the bounded result type, translate `TimeoutExpired` into `timed_out=True`, preserve `OSError` as launch failure, and normalize stdout/stderr according to `text=True/False` (especially raw Git `-z` bytes).
- Run the shared primitive's own contract first, then every consumer suite. A primitive-level green result does not prove that old test seams or byte/text expectations survived.

## 3. Complete-write contract for trusted artifacts

For direct trusted-file creation:

1. open with `O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW` under an authenticated parent;
2. loop through short writes and EINTR; a zero-byte write is a terminating `short_write` failure;
3. `fsync(fd)`, then `fchmod(fd, requested_mode)`;
4. validate closing `fstat`: regular, expected owner/mode, `nlink == 1`, exact size;
5. compute SHA-256 by `pread()` through the same descriptor and compare with authenticated in-memory bytes;
6. immediately re-resolve the final name through the held parent descriptor and compare `(dev, ino)`;
7. on failure, unlink only when the name still identifies the inode created by this invocation. Never delete a replacement.

For same-parent temp-and-rename writers, additionally reopen the published destination no-follow, revalidate metadata/size/digest/identity after `replace`, and `fsync(parent_dir_fd)` before success.

Use adversarial tests for one-byte writes, zero writes, post-write corruption, post-fsync corruption, rename-time same-size corruption, destination replacement, and parent-directory fsync. Add an AST enumeration test so every production `os.write` that creates trusted bytes must live in a sanctioned primitive. Route executable/config/helper writers through that primitive rather than expanding an allowlist. Ban unchecked `Path.write_text/write_bytes` where later steps execute or trust the result.

## 4. Refresh transitive pins only after source settles

Embedded script digests form an acyclic dependency graph but require several propagation rounds. Refreshing once, or refreshing before the last source edit, leaves apparently unrelated consumer tests stale.

Use a deterministic fixed-point refresh:

1. hash current manifested scripts, adapter runtime, delivery runtime, and production entrypoints;
2. update every enumerated embedded consumer constant from the manifest;
3. repeat manifest hashes and consumer updates until a round changes neither;
4. fail if convergence does not occur within a small explicit round bound;
5. run the manifest closure test immediately, then consumer suites and the full suite.

Do not hand-edit one stale literal at a time. Keep the manifest as the single expected-value source, and check closure from both directions: every manifest path matches current bytes, and every embedded 64-hex literal is enumerated.

## 5. Action-pin annotation compatibility is not a dependency upgrade

Treat a pin checker rejecting an otherwise valid comment as an annotation problem first. Do not rotate an exact action SHA merely to satisfy a version-comment parser.

For an action commit whose only exact tag is a non-semver bundle tag (for example CodeQL's `codeql-bundle-*`) while the checker accepts only action-version comments:

1. independently verify the SHA's upstream tag/provenance;
2. keep the exact SHA unchanged;
3. use the narrow honest action-family annotation accepted by the checker (for CodeQL v3, `# v3`) rather than inventing a semver tag the commit does not have;
4. run the same checker version used by CI and the currently installed version against the complete workflow directory, not only the edited file.

Open a separate hygiene slice for this. Do not mix annotation compatibility into an unrelated runtime/policy change, and do not call it a dependency update when bytes did not change.

## 6. Efficient verification and worker recovery

- Give mutating workers one vertical slice with exact RED tests. A max-turn result can leave only tests or only half the implementation; inspect the tree and run the narrow test before continuing.
- After repeated broad-worker timeouts, split by contract surface instead of relaunching the same broad prompt.
- Before starting another mutator, inspect exact process state; do not infer completion from an empty result file.
- For long background pytest runs, resolve and pin the absolute Python interpreter that can import pytest before launch. Background shells can have a different PATH from foreground commands.
- If a full suite quickly accumulates a cluster of failures, stop it, save collection order with `pytest --collect-only -q`, map progress percentages to files, and run the implicated consumer suites. Resume the full suite only after the systematic seam regression is repaired.
- Keep test TMPDIR/PYTHONPYCACHEPREFIX outside the repo and finish with ignored-artifact count zero, compile/JSON/shell checks, and `git diff --check`.
