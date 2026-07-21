import argparse
import json
import hashlib
import os
import runpy
import stat
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_CHECK = ROOT / "scripts" / "hermes-busdriver-pr-grind-check"
# Source-separated, never installed: the only entrypoint that can inject a helper double.
CHECK_HARNESS = ROOT / "tests" / "fixtures" / "pr-grind-check-test-harness"
CHECK = CHECK_HARNESS
GITHUB_AUTH_ENV_KEYS = (
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_ENTERPRISE_TOKEN",
)


def configure_isolated_github_auth(monkeypatch, root: Path) -> None:
    """Keep unit tests independent of the operator's real GitHub config."""
    home = root / "synthetic-home"
    config = home / ".config" / "gh"
    config.mkdir(parents=True, mode=0o700)
    hosts = config / "hosts.yml"
    hosts.write_text(
        "github.com:\n"
        "  user: synthetic-test-user\n"
        "  users:\n"
        "    synthetic-test-user:\n"
        "      oauth_token: synthetic-test-token\n"
    )
    hosts.chmod(0o600)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("GH_CONFIG_DIR", raising=False)
    for name in GITHUB_AUTH_ENV_KEYS:
        monkeypatch.delenv(name, raising=False)


def patch_bounded_run(monkeypatch, ns: dict, fake_run) -> None:
    """Bind a subprocess.run-shaped test double to the bounded production seam.

    The double replaces the primitive, so it also replaces the primitive's CONTRACT — and the two
    halves it used to drop are the two this repo cares about.

    `limit` was a named sink: declared so the call would not TypeError, then never read. Production
    spells it `limit: int = MAX_CAPTURED_BYTES`, and a default is frozen at def time, so a double
    that lets it default to `None` is not a lenient double — it is a different contract, one under
    which a production caller that dropped the bound still passes. Defaulting to the module's own
    constant means a site omitting `limit` is exercised against exactly the number production would
    have used, and a site that WEAKENS it is exercised against the weakened one, where the overflow
    assertion below can see it.

    And `overflowed` was hardcoded `False`, so no test reaching this seam could ever observe the
    refusal — `_bounded_run`'s `RuntimeError("child_output_too_large")` and `git_raw`'s
    `git_output_too_large` were unreachable through the fake, and a double could hand back oversized
    bytes as though they had arrived, which is the one shape production cannot produce. Production
    bounds at the pipe and REFUSES over it rather than slicing (a slice cuts the `token:` prefix off
    a secret and emits the remainder as ordinary text), so the double refuses the same way.
    """
    globals_ = ns["run"].__globals__
    BoundedOutput = globals_["BoundedOutput"]

    def bounded(cmd, *, cwd=None, env=None, timeout=None, stdin_bytes=None, limit=None, text=True):
        # Production's default, not None: a caller that omits the bound must still be bound.
        effective_limit = globals_["MAX_CAPTURED_BYTES"] if limit is None else limit
        kwargs = {
            "cwd": str(cwd) if cwd else None,
            "env": env,
            "timeout": timeout,
            "text": text,
            "capture_output": True,
            "check": False,
        }
        if stdin_bytes is not None:
            kwargs["input"] = stdin_bytes.decode() if text else stdin_bytes
        try:
            cp = fake_run(cmd, **kwargs)
        except subprocess.TimeoutExpired as exc:
            empty = "" if text else b""
            stdout = exc.output if exc.output is not None else empty
            stderr = exc.stderr if exc.stderr is not None else empty
            return BoundedOutput(124, stdout, stderr, False, True)
        # Production counts what the child SAID and refuses BOTH streams if either exceeded the
        # bound. `>` not `>=`: exactly `limit` bytes is not an overflow.
        measured = max(
            len(cp.stdout) if cp.stdout is not None else 0,
            len(cp.stderr) if cp.stderr is not None else 0,
        )
        if measured > effective_limit:
            return BoundedOutput(cp.returncode, "" if text else b"", "" if text else b"", True, False)
        stdout, stderr = cp.stdout, cp.stderr
        if text:
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
        else:
            if isinstance(stdout, str):
                stdout = stdout.encode()
            if isinstance(stderr, str):
                stderr = stderr.encode()
        return BoundedOutput(cp.returncode, stdout, stderr, False, False)

    monkeypatch.setitem(globals_, "run_bounded", bounded)


@pytest.fixture(autouse=True)
def isolated_github_auth_config(monkeypatch, tmp_path: Path):
    configure_isolated_github_auth(monkeypatch, tmp_path)


def test_autouse_github_auth_fixture_starts_without_ambient_tokens():
    assert "GH_CONFIG_DIR" not in os.environ
    for name in GITHUB_AUTH_ENV_KEYS:
        assert name not in os.environ


def test_isolated_github_auth_fixture_removes_all_ambient_token_variants(monkeypatch, tmp_path: Path):
    token_names = GITHUB_AUTH_ENV_KEYS
    for name in token_names:
        monkeypatch.setenv(name, f"ambient-{name.lower()}")
    monkeypatch.setenv("GH_CONFIG_DIR", str(tmp_path / "ambient-gh-config"))

    configure_isolated_github_auth(monkeypatch, tmp_path / "manual-fixture")

    assert "GH_CONFIG_DIR" not in os.environ
    for name in token_names:
        assert name not in os.environ


def live_view(head: str = "a" * 40) -> dict:
    return {
        "number": 7,
        "url": "https://github.com/owner/name/pull/7",
        "state": "OPEN",
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "isDraft": False,
        "headRefOid": head,
        "baseRefOid": "b" * 40,
        "headRefName": "feature",
        "baseRefName": "main",
        "headRepository": {"nameWithOwner": "owner/name"},
        "headRepositoryOwner": {"login": "owner"},
    }


def live_identity_argv(repo: Path) -> list[str]:
    # PRODUCTION_CHECK, never the harness: every caller of this builder is asserting what the
    # INSTALLED entrypoint does with a live identity, and routing it through the harness would
    # assert only what the double does.
    return [
        str(PRODUCTION_CHECK), "--repo", str(repo), "--pr", "7",
        "--expected-repository", "owner/name",
        "--expected-head-repository", "owner/name",
        "--expected-head-ref", "feature",
        "--expected-base-repository", "owner/name",
        "--expected-base-ref", "main",
        "--expected-head-sha", "a" * 40,
        "--expected-base-sha", "b" * 40,
    ]


def run_check(tmp_path: Path, checks: str, comments: list[dict], head: str = "abc123def456", view_extra: dict | None = None):
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text(checks)
    comments_file.write_text(json.dumps(comments))
    view = {
        "number": 7,
        "url": "https://example.test/pull/7",
        "state": "OPEN",
        "mergeable": "MERGEABLE",
        "headRefOid": head,
        "baseRefName": "main",
        "headRefName": "feature",
    }
    if view_extra:
        view.update(view_extra)
    view_file.write_text(json.dumps(view))
    cp = subprocess.run(
        [
            sys.executable,
            str(CHECK),
            "--repo",
            str(repo),
            "--pr",
            "7",
            "--fixture-mode",
            "--checks-file",
            str(checks_file),
            "--review-comments-file",
            str(comments_file),
            "--view-json-file",
            str(view_file),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    return json.loads(cp.stdout)


def test_immutable_check_lookup_failure_is_structured_and_tailed(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    failures = iter([
        subprocess.CompletedProcess(["gh"], 1, "", "r" * 3000),
        subprocess.CompletedProcess(["gh"], 1, "", "s" * 3000),
    ])
    monkeypatch.setitem(ns["load_checks"].__globals__, "run", lambda *_args, **_kwargs: next(failures))
    args = type("Args", (), {"checks_file": None, "_repository": "owner/repo", "expected_repository": "owner/repo"})()

    with pytest.raises(SystemExit) as exc:
        ns["load_checks"](args, tmp_path, "a" * 40)

    payload = json.loads(str(exc.value))
    assert payload["error"] == "immutable_head_checks_unavailable"
    assert len(payload["stderr"]) == 4000
    assert payload["stderr"] == "r" * 1000 + "s" * 3000


def _write_plugin_helper(root: Path, relative: str, payload: bytes) -> Path:
    helper = root / relative
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_bytes(payload)
    helper.chmod(0o500)
    return helper


def test_authenticated_plugin_bytes_declares_the_same_bound_as_other_ingress_readers():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    limit = ns.get("MAX_AUTHENTICATED_HELPER_BYTES")

    assert isinstance(limit, int)
    assert 256 * 1024 <= limit <= 8 * 1024 * 1024


def test_authenticated_plugin_bytes_refuses_oversized_plugin_before_read_bytes(monkeypatch, tmp_path: Path):
    """The credential-bearing plugin helper chooses its size; digesting it after read_bytes() is too late."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    limit = ns.get("MAX_AUTHENTICATED_HELPER_BYTES", 1024 * 1024)
    root = tmp_path / "plugin"
    relative = "scripts/fetch-pr-state.sh"
    helper = _write_plugin_helper(root, relative, b"x" * (limit + 4096))
    monkeypatch.setitem(
        ns["authenticated_plugin_bytes"].__globals__,
        "TRUSTED_PLUGIN_DIGESTS",
        {relative: hashlib.sha256(helper.read_bytes()).hexdigest()},
    )
    original_read_bytes = Path.read_bytes

    def refuse_whole_file_read(path: Path) -> bytes:
        if path == helper:
            raise AssertionError("oversized authenticated plugin helper was read whole before refusal")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", refuse_whole_file_read)

    assert ns["authenticated_plugin_bytes"](root, relative) is None


def test_authenticated_plugin_bytes_reads_an_untouched_bounded_helper(tmp_path: Path, monkeypatch):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    root = tmp_path / "plugin"
    relative = "scripts/fetch-pr-state.sh"
    payload = b"#!/bin/sh\ntrusted helper\n"
    helper = _write_plugin_helper(root, relative, payload)
    monkeypatch.setitem(
        ns["authenticated_plugin_bytes"].__globals__,
        "TRUSTED_PLUGIN_DIGESTS",
        {relative: hashlib.sha256(payload).hexdigest()},
    )

    assert ns["authenticated_plugin_bytes"](root, relative) == helper.read_bytes()


# --- v16-r34c: git/gh/jq are fixed root-owned sources; only the plugin .sh files stay private ---
#
# The tests replaced here asserted the r34 design: a `trusted-bin` of private 0500 copies selected
# by `PRIVATE_TRUSTED_BIN` / `HERMES_BUSDRIVER_PRIVATE_RUNTIME` and put at PATH head. Both are gone.
# Note that the old `test_run_prefers_authenticated_private_runtime_git_and_gh` pointed
# PRIVATE_TRUSTED_BIN at its own tmp_path directory and the resolver took it — a writable directory
# naming the executable is precisely what the migration removed, not a property to carry forward.
#
# The .sh helpers are a deliberate exception and their tests are KEPT: they are Busdriver plugin
# bytes with no root-owned home, so they must be materialized to be interpreted, and the guard
# digest-checks them immediately before bash opens them.


def _guard_runtime(ns: dict, tmp_path: Path, monkeypatch) -> tuple[tuple[Path, bytes, str], Path]:
    """A private helper runtime shaped exactly like the one load_acked_bot_logins() builds:
    the three .sh copies and the guard together in one 0700 directory."""
    root = tmp_path / "runtime"
    root.mkdir(mode=0o700)
    digests = ns["write_private_helper_guard"].__globals__["TRUSTED_PLUGIN_DIGESTS"]
    for name in ("fetch-pr-state.sh", "augment-equiv-acks.sh", "ack-ledger.sh"):
        helper = root / name
        helper.write_bytes(f"private-{name}\n".encode())
        helper.chmod(0o500)
        monkeypatch.setitem(digests, f"scripts/{name}", hashlib.sha256(helper.read_bytes()).hexdigest())
    guard, program = ns["write_private_helper_guard"](root)
    return (guard, program, ns["PRIVATE_HELPER_GUARD_STDIN_LOADER"]), root


def _run_guard(guard: tuple[Path, bytes, str] | Path, helper_dir: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    """The guard's argv is retained-loader virtual-path, then (helper_dir, *cmd)."""
    if isinstance(guard, tuple):
        guard_path, program, loader = guard
        return subprocess.run(
            [sys.executable, "-I", "-c", loader, str(guard_path), str(helper_dir), "/usr/bin/true"],
            input=program.decode(),
            text=True,
            capture_output=True,
            env={"PATH": "/usr/bin:/bin"} if env is None else env,
            check=False,
        )
    return subprocess.run(
        [sys.executable, "-I", str(guard), str(helper_dir), "/usr/bin/true"],
        text=True,
        capture_output=True,
        env={"PATH": "/usr/bin:/bin"} if env is None else env,
        check=False,
    )


def test_run_dispatches_the_frozen_root_owned_absolute_path(monkeypatch):
    """`run()` rewrites a bare `git` to the validated absolute source; no PATH lookup survives."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "", "")

    patch_bounded_run(monkeypatch, ns, fake_run)
    ns["run"](["git", "--version"])

    dispatched = Path(calls[0][0][0])
    assert dispatched == ns["TRUSTED_EXECUTABLE_SOURCES"]["git"] == Path("/usr/bin/git")
    assert dispatched.is_absolute()
    assert os.lstat(dispatched).st_uid == 0
    assert "/opt/homebrew" not in calls[0][1]["env"]["PATH"]


def test_checker_validates_sources_in_place_without_copying_them():
    """No private copy is materialized: the returned path IS the root-owned source."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    for name in ("git", "jq"):  # gh is absent on this host and has its own test below
        source = ns["TRUSTED_EXECUTABLE_SOURCES"][name]
        resolved = ns["trusted_executable_path"](name)
        assert resolved == source
        st = os.lstat(resolved)
        assert st.st_uid == 0, "a same-UID adversary must not own the bytes that execute"
        assert not (st.st_mode & (stat.S_IWGRP | stat.S_IWOTH))
        assert not stat.S_ISLNK(st.st_mode)


def test_gh_lane_fails_closed_by_name_when_the_root_owned_gh_is_absent():
    """gh is allowed to be absent; absence is refused by name, never resolved to another gh."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    if Path("/usr/local/bin/gh").exists():
        assert ns["trusted_executable_path"]("gh") == Path("/usr/local/bin/gh")
        return
    with pytest.raises(SystemExit) as exc:
        ns["trusted_executable_path"]("gh")
    assert json.loads(str(exc.value))["error"] == "trusted_root_owned_gh_unavailable"


def test_nested_ack_helper_binds_validated_absolute_paths_not_bare_names(monkeypatch, tmp_path: Path):
    """The plugin .sh files call git/gh/jq by BARE NAME and are digest-pinned Busdriver bytes — not
    ours to rewrite. So the names are bound to exported shell functions whose bodies are the
    validated absolute paths, and PATH deliberately carries no gh at all: a binding that ever went
    missing must fail "command not found" rather than quietly resolve to somebody else's gh.

    The resolver is stubbed because /usr/local/bin/gh is absent here and this test is about what the
    ack script BINDS. Resolution itself is covered by the two tests above.
    """
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    repo = tmp_path / "repo"
    repo.mkdir()
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    tools = {
        "git": Path("/usr/bin/git"),
        "gh": Path("/usr/bin/gh"),
        "jq": Path("/usr/bin/jq"),
        "python3": Path("/usr/bin/python3"),
        "bash": Path("/bin/bash"),
    }
    globals_ = ns["load_acked_bot_logins"].__globals__
    monkeypatch.setitem(globals_, "trusted_busdriver_plugin_root", lambda *_args: plugin)
    monkeypatch.setitem(globals_, "authenticated_plugin_bytes", lambda *_args: b"# trusted helper\n")
    monkeypatch.setitem(globals_, "trusted_executable_path", lambda name: tools[name])
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = list(cmd)
        seen["env"] = dict(kwargs["env"])
        assert isinstance(kwargs.get("input"), str)
        helper_dir = Path(cmd[5])
        assert cmd[:2] == ["/usr/bin/python3", "-I"]
        assert cmd[2] == "-c"
        assert Path(cmd[4]).name == "private-runtime-guard.py"
        assert cmd[6] == "/bin/bash"
        assert all(
            stat.S_IMODE((helper_dir / name).stat().st_mode) == 0o500
            for name in ("fetch-pr-state.sh", "augment-equiv-acks.sh", "ack-ledger.sh")
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    patch_bounded_run(monkeypatch, ns, fake_run)
    args = argparse.Namespace(fixture_mode=False, pr="1")

    assert ns["load_acked_bot_logins"](args, repo, "a" * 40) == set()

    script = seen["cmd"][[idx for idx, value in enumerate(seen["cmd"]) if value == "-c"][-1] + 1]
    for name, path in {name: tools[name] for name in ("git", "gh", "jq")}.items():
        assert f'{name}() {{ {path} "$@"; }}' in script, f"{name} is not bound to an absolute path"
    assert "export -f git gh jq" in script
    assert seen["env"]["PATH"] == "/usr/bin:/bin:/usr/sbin:/sbin"
    assert "/usr/local/bin" not in seen["env"]["PATH"], "a lost gh binding must not resolve via PATH"
    assert "/opt/homebrew" not in seen["env"]["PATH"]
    assert "HERMES_BUSDRIVER_PRIVATE_RUNTIME" not in seen["env"]


def test_nested_ack_helper_executes_retained_guard_bytes_not_swappable_private_path(monkeypatch, tmp_path: Path):
    """The authenticated guard is the authority that validates every credentialed shell helper.

    Replacing its final private pathname after authentication must not let attacker bytes forge an
    acknowledgement.  This swaps at the actual run_bounded dispatch seam rather than mocking a
    successful result, so the forged ack is the observable attacker effect.
    """
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    repo = tmp_path / "repo"
    repo.mkdir()
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    head = "a" * 40
    globals_ = ns["load_acked_bot_logins"].__globals__
    helper_bytes = b"# trusted helper\n"
    monkeypatch.setitem(globals_, "trusted_busdriver_plugin_root", lambda *_args: plugin)
    monkeypatch.setitem(globals_, "authenticated_plugin_bytes", lambda *_args: helper_bytes)
    monkeypatch.setitem(
        globals_,
        "TRUSTED_PLUGIN_DIGESTS",
        {
            "scripts/fetch-pr-state.sh": hashlib.sha256(helper_bytes).hexdigest(),
            "scripts/augment-equiv-acks.sh": hashlib.sha256(helper_bytes).hexdigest(),
            "scripts/ack-ledger.sh": hashlib.sha256(helper_bytes).hexdigest(),
        },
    )
    monkeypatch.setitem(globals_, "TRUSTED_EXECUTABLE_SOURCES", {"bash": Path("/bin/bash")})
    monkeypatch.setitem(globals_, "TRUSTED_EXECUTABLE_DIGESTS", {"bash": hashlib.sha256(Path("/bin/bash").read_bytes()).hexdigest()})
    tools = {
        "git": Path("/usr/bin/git"),
        "gh": Path("/usr/bin/true"),
        "jq": Path("/usr/bin/true"),
        "python3": Path(sys.executable),
        "bash": Path("/bin/bash"),
    }
    monkeypatch.setitem(globals_, "trusted_executable_path", lambda name: tools[name])

    def swap_guard_then_run(cmd, **kwargs):
        guard = next(Path(arg) for arg in cmd if Path(str(arg)).name == "private-runtime-guard.py")
        guard.chmod(0o700)
        guard.write_text(f"print('chatgpt-codex-connector={head[:8]}:E')\n")
        guard.chmod(0o500)
        return subprocess.run(cmd, **kwargs)

    patch_bounded_run(monkeypatch, ns, swap_guard_then_run)
    acked = ns["load_acked_bot_logins"](argparse.Namespace(fixture_mode=False, pr="1"), repo, head)

    assert "chatgpt-codex-connector" not in acked, "attacker-replaced guard forged a bot acknowledgement"


@pytest.mark.parametrize("target", ["fetch-pr-state.sh", "ack-ledger.sh"])
def test_nested_ack_helper_reopens_swapped_private_helper_after_guard_authenticated_it(monkeypatch, tmp_path: Path, target: str):
    """The guard digest-authenticates the private .sh helpers in validate_entries(), then execve's
    bash — which reopens them BY PATHNAME: `. "$1"` sources fetch-pr-state.sh and `bash "$ack_script"`
    opens ack-ledger.sh. Nothing re-authenticates between the guard's check and bash's open, so a
    same-UID substitution landed in that window executes with GitHub credentials and forges acks.

    Determinism: a real racing thread cannot be scheduled reliably, so the swap is injected as a
    single line into the OTHERWISE-PRODUCTION guard bytes, positioned exactly where a winning
    attacker would land it — after every validation (validate_entries + validate_source) and before
    os.execve. It truncates-in-place, keeping the same inode, so even an inode-identity re-check would
    pass: the only thing that admits the swap is that bash reopens the path without re-digesting it.
    That IS the production defect — the seam only removes the scheduler's nondeterminism, not any
    guard step. The observable effect is a forged current-head bot acknowledgement, produced by the
    real python->guard->execve->bash chain, not a mocked CompletedProcess.
    """
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    repo = tmp_path / "repo"
    repo.mkdir()
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    head = "a" * 40
    head8 = head[:8]
    globals_ = ns["load_acked_bot_logins"].__globals__
    helper_bytes = b"# trusted helper\n"
    monkeypatch.setitem(globals_, "trusted_busdriver_plugin_root", lambda *_args: plugin)
    monkeypatch.setitem(globals_, "authenticated_plugin_bytes", lambda *_args: helper_bytes)
    monkeypatch.setitem(
        globals_,
        "TRUSTED_PLUGIN_DIGESTS",
        {
            "scripts/fetch-pr-state.sh": hashlib.sha256(helper_bytes).hexdigest(),
            "scripts/augment-equiv-acks.sh": hashlib.sha256(helper_bytes).hexdigest(),
            "scripts/ack-ledger.sh": hashlib.sha256(helper_bytes).hexdigest(),
        },
    )
    # Only bash as a root-owned source, so the guard's validate_source() reaches execve on a host
    # without /usr/local/bin/gh (mirrors the retained-bytes swap test above).
    monkeypatch.setitem(globals_, "TRUSTED_EXECUTABLE_SOURCES", {"bash": Path("/bin/bash")})
    monkeypatch.setitem(globals_, "TRUSTED_EXECUTABLE_DIGESTS", {"bash": hashlib.sha256(Path("/bin/bash").read_bytes()).hexdigest()})
    tools = {
        "git": Path("/usr/bin/true"),
        "gh": Path("/usr/bin/true"),
        "jq": Path("/usr/bin/true"),
        "python3": Path(sys.executable),
        "bash": Path("/bin/bash"),
    }
    monkeypatch.setitem(globals_, "trusted_executable_path", lambda name: tools[name])

    # The swapped helper forges an ack for chatgpt-codex-connector at the CURRENT head. ack-ledger.sh
    # is invoked as `bash "$ack_script" "$b"` and its stdout becomes the ack value; fetch-pr-state.sh
    # is sourced, so it prints a forged `login=value` line straight to the parsed stdout.
    if target == "ack-ledger.sh":
        swapped = f'printf "%s\\n" "{head8}:E"\n'.encode()
    else:
        swapped = f'printf "%s\\n" "chatgpt-codex-connector={head8}:E"\n'.encode()

    real_guard_bytes = ns["private_helper_guard_bytes"]
    execve_line = "os.execve(sys.argv[2], sys.argv[2:], os.environ)"
    seam = (
        "_swap = os.path.join(helper_dir, {target!r})\n"
        "os.chmod(_swap, 0o700)\n"
        "_fd = os.open(_swap, os.O_WRONLY | os.O_TRUNC)\n"
        "os.write(_fd, {swapped!r})\n"
        "os.close(_fd)\n"
        "os.chmod(_swap, 0o500)\n"
    ).format(target=target, swapped=swapped)
    patched = real_guard_bytes().decode().replace(execve_line, seam + execve_line)
    assert patched.count(seam) == 1, "seam must be injected exactly once, before execve"
    monkeypatch.setitem(globals_, "private_helper_guard_bytes", lambda: patched.encode())

    patch_bounded_run(monkeypatch, ns, subprocess.run)
    acked = ns["load_acked_bot_logins"](argparse.Namespace(fixture_mode=False, pr="1"), repo, head)

    assert "chatgpt-codex-connector" not in acked, (
        "helper reopened by pathname after guard authentication executed attacker bytes and forged an ack"
    )


@pytest.mark.parametrize("missing", ["python3", "bash"])
def test_nested_ack_helper_refuses_unavailable_interpreter_without_dispatch(monkeypatch, tmp_path: Path, missing: str):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    globals_ = ns["load_acked_bot_logins"].__globals__
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    monkeypatch.setitem(globals_, "trusted_busdriver_plugin_root", lambda *_args: plugin)
    monkeypatch.setitem(globals_, "authenticated_plugin_bytes", lambda *_args: b"# trusted helper\n")

    def resolve(name):
        if name == missing:
            raise SystemExit(json.dumps({"ok": False, "error": f"trusted_root_owned_{name}_unavailable"}))
        return Path("/usr/bin") / name

    monkeypatch.setitem(globals_, "trusted_executable_path", resolve)
    patch_bounded_run(monkeypatch, ns, lambda *_a, **_k: pytest.fail("an unavailable interpreter must not dispatch"))

    with pytest.raises(SystemExit) as exc:
        ns["load_acked_bot_logins"](argparse.Namespace(fixture_mode=False, pr="1"), tmp_path, "a" * 40)

    assert json.loads(str(exc.value))["error"] == f"trusted_root_owned_{missing}_unavailable"


def test_nested_ack_helper_guard_revalidates_the_root_owned_sources_before_exec(tmp_path: Path, monkeypatch):
    """The parent validated the sources already, but that check is a statement about the past and
    this process is the one that hands them to bash — so the guard re-walks them itself.

    /usr/local/bin/gh is absent on this host and `gh` sorts first, so the guard's own refusal is
    what proves it revalidated rather than trusting the parent. Both host states are asserted, so
    provisioning gh later turns this into a stronger test rather than a silent skip.
    """
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    guard, helper_dir = _guard_runtime(ns, tmp_path, monkeypatch)

    cp = _run_guard(guard, helper_dir)

    if Path("/usr/local/bin/gh").exists():
        assert cp.returncode == 0, cp.stdout + cp.stderr
        return
    assert cp.returncode == 3
    payload = json.loads(cp.stdout)
    assert payload["error"] == "trusted_root_owned_gh_unavailable"
    assert payload["executable"] == "gh"


def test_nested_ack_helper_guard_refuses_denied_env_before_exec(tmp_path: Path, monkeypatch):
    """$DEVELOPER_DIR redirects the /usr/bin/git CommandLineTools shim through xcrun to an
    attacker-chosen toolchain — a root-owned, SIP-restricted, digest-matching binary then execs
    somebody else's code, and no ancestry walk can see it. The parent builds the child env from an
    allowlist that has no such key, so this can only fire if that construction is ever bypassed,
    which is exactly when it matters. Refused before execve, not merely absent from the allowlist.
    """
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    guard, helper_dir = _guard_runtime(ns, tmp_path, monkeypatch)

    cp = _run_guard(guard, helper_dir, env={"PATH": "/usr/bin:/bin", "DEVELOPER_DIR": str(tmp_path)})

    assert cp.returncode == 3
    payload = json.loads(cp.stdout)
    assert payload["error"] == "trusted_root_owned_source_env_denied"
    assert payload["executable"] == "DEVELOPER_DIR"


@pytest.mark.parametrize("case", ("missing", "symlink", "mode", "digest"))
def test_nested_ack_helper_guard_validates_private_helper_scripts(tmp_path: Path, case: str, monkeypatch):
    """The .sh copies are the one thing here that is still a private copy, so the guard is the only
    thing standing between a tampered helper and bash. Kept, with the guard's new argv."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    guard, helper_dir = _guard_runtime(ns, tmp_path, monkeypatch)
    # Baseline: with the helpers intact the guard gets PAST helper validation. It cannot reach exec
    # on a host without gh, so the baseline is "the complaint is no longer about the helpers".
    baseline = _run_guard(guard, helper_dir)
    assert not json.loads(baseline.stdout or "{}").get("error", "").startswith("private_trusted_helper_")
    target = helper_dir / "fetch-pr-state.sh"
    if case == "missing":
        target.unlink()
    elif case == "symlink":
        target.unlink()
        target.symlink_to("augment-equiv-acks.sh")
    elif case == "mode":
        target.chmod(0o700)
    else:
        target.chmod(0o700)
        target.write_bytes(b"changed\n")
        target.chmod(0o500)

    cp = _run_guard(guard, helper_dir)

    assert cp.returncode == 3
    assert json.loads(cp.stdout)["error"].startswith("private_trusted_helper_")


@pytest.mark.parametrize("missing", ["state", "mergeable", "mergeStateStatus", "isDraft"])
def test_live_view_rejects_missing_required_state_before_collecting_evidence(monkeypatch, tmp_path: Path, missing: str):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    view = {
        "number": 7,
        "url": "https://github.com/owner/repo/pull/7",
        "state": "OPEN",
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "isDraft": False,
        "headRefOid": "a" * 40,
        "baseRefOid": "b" * 40,
        "headRefName": "feature",
        "baseRefName": "main",
        "headRepository": {"nameWithOwner": "fork/repo"},
        "headRepositoryOwner": {"login": "fork"},
    }
    del view[missing]
    monkeypatch.setitem(ns["main"].__globals__, "owner_repo", lambda _repo: "owner/repo")
    monkeypatch.setitem(ns["main"].__globals__, "load_view", lambda _args, _repo: view)
    monkeypatch.setitem(ns["main"].__globals__, "load_checks", lambda *_args: pytest.fail("invalid identity must block before checks"))
    monkeypatch.setattr(sys, "argv", [
        str(CHECK), "--repo", str(tmp_path), "--pr", "7",
        "--expected-repository", "owner/repo",
        "--expected-head-repository", "fork/repo",
        "--expected-head-ref", "feature",
        "--expected-base-repository", "owner/repo",
        "--expected-base-ref", "main",
        "--expected-head-sha", "a" * 40,
        "--expected-base-sha", "b" * 40,
    ])

    with pytest.raises(SystemExit) as exc:
        ns["main"]()

    assert json.loads(str(exc.value)) == {"ok": False, "error": "pr_view_identity_invalid", "field": missing}


@pytest.mark.parametrize(("field", "value", "reported_field"), [
    ("headRepository", {"nameWithOwner": "fork/name"}, "headRepository"),
    ("headRepository", None, "headRepository"),
    ("headRepositoryOwner", None, "headRepositoryOwner"),
    ("baseRefName", "release", "baseRefName"),
    ("number", 8, "number"),
    ("url", "https://github.com/owner/repo/pull/8", "url"),
    ("headRefOid", "c" * 40, "headRefOid"),
    ("baseRefOid", "d" * 40, "baseRefOid"),
])
def test_live_view_rejects_identity_mismatch(field: str, value: object, reported_field: str):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    args = type("Args", (), {
        "pr": "7",
        "expected_repository": "owner/repo",
        "expected_head_repository": "owner/repo",
        "expected_head_ref": "feature",
        "expected_base_repository": "owner/repo",
        "expected_base_ref": "main",
        "expected_head_sha": "a" * 40,
        "expected_base_sha": "b" * 40,
    })()
    view = live_view()
    view["url"] = "https://github.com/owner/repo/pull/7"
    view[field] = value

    with pytest.raises(SystemExit) as exc:
        ns["validate_live_view"](args, view)

    assert json.loads(str(exc.value))["field"] == reported_field


def test_live_view_rejects_wrong_expected_base_repository():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    args = type("Args", (), {
        "pr": "7",
        "expected_repository": "owner/repo",
        "expected_head_repository": "owner/name",
        "expected_head_ref": "feature",
        "expected_base_repository": "attacker/repo",
        "expected_base_ref": "main",
        "expected_head_sha": "a" * 40,
        "expected_base_sha": "b" * 40,
    })()
    view = live_view()
    view["url"] = "https://github.com/owner/repo/pull/7"

    with pytest.raises(SystemExit) as exc:
        ns["validate_live_view"](args, view)

    assert json.loads(str(exc.value))["field"] == "baseRepository"


def test_load_checks_keeps_pending_legacy_status_after_first_page(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    head = "a" * 40
    commands = []
    first_page = [{"context": f"status-{index}", "state": "success", "target_url": ""} for index in range(30)]
    responses = iter([
        subprocess.CompletedProcess(["gh"], 0, json.dumps([{"check_runs": []}]), ""),
        subprocess.CompletedProcess(["gh"], 0, json.dumps([
            {"sha": head, "statuses": first_page},
            {"sha": head, "statuses": [{"context": "late", "state": "pending", "target_url": ""}]},
        ]), ""),
    ])

    def fake_run(cmd, **_kwargs):
        commands.append(cmd)
        return next(responses)

    monkeypatch.setitem(ns["load_checks"].__globals__, "run", fake_run)
    args = type("Args", (), {"checks_file": None, "_repository": "owner/repo", "expected_repository": "owner/repo"})()

    checks = ns["load_checks"](args, tmp_path, head)

    assert "late\tpending" in checks
    assert all(cmd[-2:] == ["--paginate", "--slurp"] for cmd in commands)


@pytest.mark.parametrize(("runs_payload", "statuses_payload", "error"), [
    ([{"check_runs": [{"name": "unit", "status": "completed", "conclusion": "success"}]}], [{"sha": "a" * 40, "statuses": []}], "check_run_head_mismatch"),
    ([{"check_runs": [{"name": "unit", "head_sha": "c" * 40, "status": "completed", "conclusion": "success"}]}], [{"sha": "a" * 40, "statuses": []}], "check_run_head_mismatch"),
    ([{"check_runs": []}], [{"statuses": []}], "status_contexts_schema_invalid"),
    ([{"check_runs": []}], [{"sha": "c" * 40, "statuses": []}], "status_contexts_schema_invalid"),
    ({"message": "denied"}, [{"sha": "a" * 40, "statuses": []}], "check_runs_schema_invalid"),
])
def test_load_checks_rejects_missing_mismatched_or_malformed_sha(monkeypatch, tmp_path: Path, runs_payload, statuses_payload, error: str):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    responses = iter([
        subprocess.CompletedProcess(["gh"], 0, json.dumps(runs_payload), ""),
        subprocess.CompletedProcess(["gh"], 0, json.dumps(statuses_payload), ""),
    ])
    monkeypatch.setitem(ns["load_checks"].__globals__, "run", lambda *_args, **_kwargs: next(responses))
    args = type("Args", (), {"checks_file": None, "_repository": "owner/repo", "expected_repository": "owner/repo"})()

    with pytest.raises(SystemExit) as exc:
        ns["load_checks"](args, tmp_path, "a" * 40)

    assert json.loads(str(exc.value))["error"] == error


@pytest.mark.parametrize("loader_name", ["load_review_comments", "load_issue_comments", "load_reviews"])
def test_live_rest_feedback_surface_rejects_partial_item(loader_name: str, monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    loader = ns[loader_name]
    monkeypatch.setitem(loader.__globals__, "run", lambda cmd, **_kwargs: subprocess.CompletedProcess(cmd, 0, "[[{}]]", ""))
    args = type("Args", (), {
        "review_comments_file": None,
        "issue_comments_file": None,
        "reviews_file": None,
        "fixture_mode": False,
        "_repository": "owner/repo",
        "expected_repository": "owner/repo",
        "pr": "7",
    })()

    with pytest.raises(SystemExit) as exc:
        loader(args, tmp_path)

    assert json.loads(str(exc.value))["error"] == f"{loader_name.removeprefix('load_')}_schema_invalid"


def test_clean_when_relevant_checks_pass_and_no_current_head_findings(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="CodeRabbit\tpass\t1m\turl\nunit\tpass\t1m\turl\n",
        comments=[{"commit_id": "oldsha", "body": "Please change old code", "path": "x.py", "line": 1}],
    )

    assert data["status"] == "clean"
    assert data["clean"] is True
    assert data["checks"]["failed"] == 0
    assert data["checks"]["pending"] == 0
    assert data["actionable_comments"] == []


def test_waits_when_relevant_checks_are_pending(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpending\t1m\turl\nCodeRabbit\tpass\t1m\turl\n",
        comments=[],
    )

    assert data["status"] == "wait"
    assert data["clean"] is False
    assert data["checks"]["pending"] == 1


def test_unstable_merge_state_with_pending_checks_waits(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpending\t1m\turl\n",
        comments=[],
        view_extra={"mergeStateStatus": "UNSTABLE"},
    )

    assert data["status"] == "wait"
    assert data["clean"] is False


def test_unknown_merge_state_with_passed_checks_still_waits(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[],
        view_extra={"mergeStateStatus": "UNKNOWN"},
    )

    assert data["status"] == "wait"
    assert data["clean"] is False


def test_unstable_merge_state_with_passed_checks_still_waits(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[],
        view_extra={"mergeStateStatus": "UNSTABLE"},
    )

    assert data["status"] == "wait"
    assert data["clean"] is False


def test_waits_for_pending_checks_before_acting_on_comments(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpending\t1m\turl\n",
        comments=[{"commit_id": "abc123def456", "body": "This can crash on empty input", "path": "src/app.py", "line": 12}],
    )
    assert data["status"] == "wait"
    assert data["actionable_comments"]


def test_needs_fix_for_actionable_comment_on_current_head(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[{"commit_id": "abc123def456", "body": "This can crash on empty input", "path": "src/app.py", "line": 12, "user": {"login": "codex"}}],
    )

    assert data["status"] == "needs_fix"
    assert data["clean"] is False
    assert len(data["actionable_comments"]) == 1
    assert data["actionable_comments"][0]["path"] == "src/app.py"


def test_advisory_pattern_is_literal_not_regex(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    comments_file.write_text("[]")
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--view-json-file", str(view_file), "--advisory-pattern", ".*"],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["checks"]["kept"] == 1


def test_fixture_comments_with_review_id_are_actionable_without_reviews_file(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[{"id": 123, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Current fixture finding", "path": "src/app.py", "line": 12}],
    )

    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["path"] == "src/app.py"


def test_active_prior_round_thread_before_latest_head_is_actionable_when_not_outdated():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    head_time = ns["parse_github_time"]("2026-01-01T00:01:00Z")
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "oldsha123", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z", "body": "Old but still unresolved active thread", "path": "src/app.py", "line": 4, "user": {"login": "reviewer"}}]
    out = ns["actionable_comments"](comments, "abc123def456", head_time, set(), {123}, {9}, set())
    assert len(out) == 1
    assert out[0]["source"] == "review_comment"


def test_active_thread_from_dismissed_review_is_ignored():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "oldsha123", "body": "Dismissed unresolved thread", "path": "src/app.py", "line": 4, "user": {"login": "reviewer"}}]
    out = ns["actionable_comments"](comments, "abc123def456", None, set(), {123}, {9}, {9})
    assert out == []


def test_ignores_comments_from_dismissed_current_review(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    comments_file.write_text(json.dumps([{"id": 123, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Dismissed finding", "path": "src/app.py", "line": 12}]))
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "abc123def456", "state": "DISMISSED", "body": "Old review"}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_active_prior_round_thread_comment_is_actionable():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "oldsha123", "body": "Still unresolved", "path": "src/app.py", "line": 4, "user": {"login": "reviewer"}}]
    out = ns["actionable_comments"](comments, "abc123def456", None, set(), {123}, {9}, set())
    assert len(out) == 1
    assert out[0]["source"] == "review_comment"


def test_ignores_comments_from_previous_review_round(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    comments_file.write_text(json.dumps([{"id": 123, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Old round finding", "path": "src/app.py", "line": 12}]))
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "old123456789", "state": "COMMENTED", "body": "Old review"}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_ignores_resolved_review_comment_ids(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    resolved_file = tmp_path / "resolved.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    comments_file.write_text(json.dumps([{"id": 123, "commit_id": "abc123def456", "body": "Please fix this", "path": "src/app.py", "line": 12}]))
    resolved_file.write_text(json.dumps([123]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--resolved-review-comment-ids-file", str(resolved_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_review_progress_issue_comment_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("CodeRabbit\tpending\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "Currently processing new changes in this PR. This may take a few minutes, please wait...", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "coderabbitai[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "wait"
    assert data["actionable_comments"][0]["source"] == "bot_progress"


def test_coderabbit_summary_issue_comment_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "<!-- This is an auto-generated comment: summarize by coderabbit.ai --> ## Summary by CodeRabbit", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "coderabbitai[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_ack_value_matches_exact_head_prefix_or_longer_prefix():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    assert ns["ack_matches_head"]("abc123de:E", "abc123def456") is True
    assert ns["ack_matches_head"]("abc123de", "abc123def456") is True
    assert ns["ack_matches_head"]("abc123def:E", "abc123def456") is True
    assert ns["ack_matches_head"]("abc123d0:E", "abc123def456") is False
    assert ns["ack_matches_head"]("abc123dezzz:E", "abc123def456") is False
    assert ns["ack_matches_head"]("abc123def4560:E", "abc123def456") is False


def test_load_acked_bot_logins_ignores_ambient_plugin_roots(tmp_path: Path, monkeypatch):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    plugin = tmp_path / "plugin"
    scripts = plugin / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "fetch-pr-state.sh").write_text("FETCH_OK=1; export FETCH_OK\n")
    (scripts / "ack-ledger.sh").write_text("#!/usr/bin/env bash\necho abc123de:E\n")
    (scripts / "ack-ledger.sh").chmod(0o755)
    monkeypatch.setenv("BUSDRIVER_PLUGIN_ROOT", str(plugin))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "empty-home"))
    args = type("Args", (), {"fixture_mode": False, "plugin_root": None, "pr": "7"})()
    assert ns["load_acked_bot_logins"](args, tmp_path, "abc123def456") == set()


@pytest.mark.parametrize("relative_path", ["scripts/fetch-pr-state.sh", "scripts/augment-equiv-acks.sh", "scripts/ack-ledger.sh", "scripts/relevant-check-status.sh"])
def test_trusted_plugin_rejects_modified_tracked_helper(tmp_path: Path, monkeypatch, relative_path: str):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    home = tmp_path / "home"
    plugin = home / ".claude/plugins/marketplaces/busdriver"
    (plugin / "scripts").mkdir(parents=True)
    (plugin / "package.json").write_text(json.dumps({"name": "busdriver", "version": "1.0.0"}))
    for name in ["fetch-pr-state.sh", "augment-equiv-acks.sh", "ack-ledger.sh", "relevant-check-status.sh"]:
        (plugin / "scripts" / name).write_text("#!/bin/sh\nexit 0\n")
    for cmd in [
        ["git", "init"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
        ["git", "config", "commit.gpgsign", "false"],
        ["git", "add", "package.json", "scripts"],
        ["git", "commit", "-m", "trusted"],
    ]:
        assert subprocess.run(cmd, cwd=plugin, text=True, capture_output=True).returncode == 0
    ns["trusted_busdriver_plugin_root"].__globals__["TRUSTED_PLUGIN_DIGESTS"] = {
        rel: hashlib.sha256((plugin / rel).read_bytes()).hexdigest()
        for rel in ["package.json", "scripts/fetch-pr-state.sh", "scripts/augment-equiv-acks.sh", "scripts/ack-ledger.sh", "scripts/relevant-check-status.sh"]
    }
    (plugin / relative_path).write_text("#!/bin/sh\nprintf stolen\n")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    args = type("Args", (), {"plugin_root": None})()

    with pytest.raises(SystemExit) as exc:
        ns["trusted_busdriver_plugin_root"](args, (relative_path,))

    assert json.loads(str(exc.value))["error"] == "plugin_root_integrity_failed"


def test_acked_coderabbit_rate_limit_comment_does_not_block():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    comments = [{"body": "Review limit reached: rate limited by CodeRabbit", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "coderabbitai[bot]"}}]
    head_time = ns["parse_github_time"]("2026-01-01T00:00:00Z")
    out = ns["actionable_issue_comments"](comments, head_time, {"coderabbitai[bot]"})
    assert out == []


def test_coderabbit_rate_limit_comment_blocks_clean(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "Review limit reached: rate limited by CodeRabbit", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "coderabbitai[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "issue_comment_after_head"


def test_rate_limit_comment_with_progress_phrase_is_not_wait(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "Currently processing new changes, but review limit reached and rate limited by CodeRabbit", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "coderabbitai[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "issue_comment_after_head"


def test_please_wait_actionable_issue_comment_is_not_suppressed(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "Please wait to merge until this null dereference is fixed", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "reviewer"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "issue_comment_after_head"


def test_missing_explicit_relevant_script_blocks_without_traceback(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    comments_file.write_text("[]")
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK_HARNESS), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--view-json-file", str(view_file), "--relevant-check-script", str(tmp_path / "missing.sh")],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "blocked"
    assert data["checks"]["error"] == "script_not_found"
    assert "Traceback" not in cp.stderr


def test_relevant_script_parse_failure_blocks(tmp_path: Path):
    script = tmp_path / "relevant-check-status.sh"
    script.write_text("#!/bin/sh\nprintf 'not parseable\\n'\n")
    script.chmod(0o755)
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    comments_file.write_text("[]")
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK_HARNESS), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--view-json-file", str(view_file), "--relevant-check-script", str(script)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "blocked"
    assert "relevant_check_status_unavailable" in data["blockers"]


def test_blocks_when_pr_is_not_mergeable_even_if_checks_pass(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[],
        view_extra={"mergeable": "CONFLICTING"},
    )

    assert data["status"] == "blocked"
    assert "mergeable=CONFLICTING" in data["blockers"]


def test_blocks_when_review_decision_requests_changes(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[],
        view_extra={"reviewDecision": "CHANGES_REQUESTED", "mergeStateStatus": "CLEAN", "isDraft": False},
    )

    assert data["status"] == "blocked"
    assert "reviewDecision=CHANGES_REQUESTED" in data["blockers"]


def test_negative_fixed_phrase_is_still_actionable(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[{"commit_id": "abc123def456", "body": "Thanks, but this is not fixed and still crashes", "path": "src/app.py", "line": 12}],
    )

    assert data["status"] == "needs_fix"
    assert len(data["actionable_comments"]) == 1


def test_ignores_malformed_short_comment_sha(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[{"commit_id": "a", "body": "This should not bind to HEAD", "path": "src/app.py", "line": 12}],
    )

    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_external_relevant_script_controls_pending_rows(tmp_path: Path):
    script = tmp_path / "relevant-check-status.sh"
    script.write_text("#!/bin/sh\nprintf '0 0 required 1\\n'\n")
    script.chmod(0o755)
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("advisory\tpending\t1m\turl\nunit\tpass\t1m\turl\n")
    comments_file.write_text("[]")
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [
            sys.executable,
            str(CHECK_HARNESS),
            "--repo", str(repo),
            "--pr", "7",
            "--fixture-mode",
            "--checks-file", str(checks_file),
            "--review-comments-file", str(comments_file),
            "--view-json-file", str(view_file),
            "--relevant-check-script", str(script),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["checks"]["pending_rows"] == []


def test_external_relevant_script_reports_pending_diagnostic_rows(tmp_path: Path):
    script = tmp_path / "relevant-check-status.sh"
    script.write_text("#!/bin/sh\nprintf '0 1 required 1\\npending-required\\tpending\\t1m\\turl\\n'\n")
    script.chmod(0o755)
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("advisory\tpending\t1m\turl\nunit\tpass\t1m\turl\n")
    comments_file.write_text("[]")
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK_HARNESS), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--view-json-file", str(view_file), "--relevant-check-script", str(script)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "wait"
    assert data["checks"]["pending_rows"] == ["pending-required\tpending\t1m\turl"]


def test_resolved_current_head_comment_is_not_actionable(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[{"commit_id": "abc123def456", "body": "This used to need a fix", "path": "src/app.py", "line": 12, "resolved": True}],
    )

    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_cubic_no_issues_review_body_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "**No issues found** across 5 files\n\n<sub>[Re-trigger cubic](https://www.cubic.dev/action/re-review/pr/owner/repo/5)</sub>", "user": {"login": "cubic-dev-ai[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_cubic_no_issues_single_file_review_body_is_not_actionable():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    reviews = [{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "**No issues found** across 1 file reviewed.", "user": {"login": "cubic-dev-ai[bot]"}}]
    assert ns["actionable_reviews"](reviews, "abc123def456") == []


def test_generic_bot_review_summary_without_inline_comment_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "### 💡 Codex Review\nHere are some automated review suggestions for this pull request.\n**Reviewed commit:** `abc123def456`\n<details><summary>ℹ️ About Codex in GitHub</summary>Boilerplate</details>", "user": {"login": "chatgpt-codex-connector[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_generic_bot_review_summary_with_inline_comment_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text(json.dumps([{"id": 1, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Resolved inline detail", "resolved": True, "path": "x.py", "line": 1}]))
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "### 💡 Codex Review\nHere are some automated review suggestions for this pull request.\n**Reviewed commit:** `abc123def456`\n<details><summary>ℹ️ About Codex in GitHub</summary>Boilerplate</details>", "user": {"login": "chatgpt-codex-connector[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_bot_review_summary_with_actionable_details_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text(json.dumps([{"id": 1, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Resolved inline detail", "resolved": True, "path": "x.py", "line": 1}]))
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "### 💡 Codex Review\nHere are some automated review suggestions for this pull request.\n**Reviewed commit:** `abc123def456`\n<details><summary>Actionable details</summary>Please update the migration before merging.</details>", "user": {"login": "chatgpt-codex-connector[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "review"


def test_bot_review_summary_with_actionable_extra_text_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text(json.dumps([{"id": 1, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Resolved inline detail", "resolved": True, "path": "x.py", "line": 1}]))
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "### 💡 Codex Review\nHere are some automated review suggestions for this pull request.\nPlease update the migration before merging.\n**Reviewed commit:** `abc123def456`\n<details><summary>ℹ️ About Codex in GitHub</summary>Boilerplate</details>", "user": {"login": "chatgpt-codex-connector[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "review"


def test_review_body_on_current_head_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "COMMENTED", "body": "Please handle the edge case", "user": {"login": "bot"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "review"


def test_approved_review_body_with_harmless_text_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "APPROVED", "body": "Ship it", "user": {"login": "bot"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_approved_review_body_with_great_work_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "APPROVED", "body": "Great work!", "user": {"login": "human"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"


def test_approved_review_body_with_actionable_text_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "APPROVED", "body": "Approved overall, but please fix the fallback before merging", "user": {"login": "bot"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "review"


def test_approved_review_body_with_broken_regression_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "APPROVED", "body": "Approved, but this regression is broken", "user": {"login": "human"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "review"


def test_approved_review_body_with_please_update_migration_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "APPROVED", "body": "Please update the migration", "user": {"login": "human"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "review"


def test_non_actionable_commented_review_does_not_supersede_prior_actionable_review(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([
        {"id": 1, "commit_id": "abc123def456", "state": "COMMENTED", "body": "Please update the migration", "user": {"login": "reviewer"}, "submitted_at": "2026-01-01T00:00:00Z"},
        {"id": 2, "commit_id": "abc123def456", "state": "COMMENTED", "body": "thanks", "user": {"login": "reviewer"}, "submitted_at": "2026-01-01T00:01:00Z"},
    ]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"


def test_pending_review_does_not_supersede_prior_actionable_review(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([
        {"id": 1, "commit_id": "abc123def456", "state": "COMMENTED", "body": "Please update the migration", "user": {"login": "reviewer"}, "submitted_at": "2026-01-01T00:00:00Z"},
        {"id": 2, "commit_id": "abc123def456", "state": "PENDING", "body": "Draft note", "user": {"login": "reviewer"}, "submitted_at": "2026-01-01T00:01:00Z"},
    ]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "review"


def test_latest_same_reviewer_approval_supersedes_prior_review_body(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([
        {"id": 1, "commit_id": "abc123def456", "state": "COMMENTED", "body": "Please update the migration", "user": {"login": "reviewer"}, "submitted_at": "2026-01-01T00:00:00Z"},
        {"id": 2, "commit_id": "abc123def456", "state": "APPROVED", "body": "Looks good", "user": {"login": "reviewer"}, "submitted_at": "2026-01-01T00:01:00Z"},
    ]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"


def test_current_head_bot_inline_comment_not_superseded_by_same_review():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Current bot finding", "path": "src/app.py", "line": 4, "user": {"login": "chatgpt-codex-connector[bot]"}}]
    out = ns["actionable_comments"](comments, "abc123def456", None, set(), {123}, {9}, set(), {"chatgpt-codex-connector[bot]"})
    assert len(out) == 1
    assert out[0]["source"] == "review_comment"


def test_later_current_head_bot_review_supersedes_rest_comment_retargeted_to_head():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "abc123def456", "original_commit_id": "oldsha123", "body": "Old bot finding", "path": "src/app.py", "line": 4, "user": {"login": "chatgpt-codex-connector[bot]"}}]
    out = ns["actionable_comments"](comments, "abc123def456", None, set(), {123}, {9}, set(), {"chatgpt-codex-connector[bot]"})
    assert out == []


def test_later_current_head_bot_review_supersedes_prior_round_bot_inline_comment():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "oldsha123", "body": "Old bot finding", "path": "src/app.py", "line": 4, "user": {"login": "chatgpt-codex-connector[bot]"}}]
    out = ns["actionable_comments"](comments, "abc123def456", None, set(), {123}, {9}, set(), {"chatgpt-codex-connector[bot]"})
    assert out == []


def test_current_head_bot_review_is_not_hidden_by_later_stale_review():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    reviews = [
        {"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "Current-head summary", "user": {"login": "chatgpt-codex-connector[bot]"}, "submitted_at": "2026-01-01T00:00:00Z"},
        {"id": 10, "commit_id": "oldsha123", "state": "COMMENTED", "body": "Stale summary", "user": {"login": "chatgpt-codex-connector[bot]"}, "submitted_at": "2026-01-01T00:01:00Z"},
    ]
    assert "chatgpt-codex-connector[bot]" in ns["current_head_bot_review_logins"](reviews, "abc123def456")



def test_head_changed_check_counts_keeps_stable_schema():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    counts = ns["head_changed_check_counts"]()
    assert counts["source"] == "head_changed"
    assert counts["relevance_unavailable"] is False



def test_unresolved_outdated_thread_comment_is_not_actionable_when_not_live():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "oldsha123", "body": "Unresolved outdated feedback", "path": "src/app.py", "line": 4, "user": {"login": "reviewer"}}]
    out = ns["actionable_comments"](comments, "abc123def456", None, set(), set(), {9}, set())
    assert out == []



def test_unresolved_outdated_thread_id_is_ignored_like_resolved(tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    repo = tmp_path / "repo"
    repo.mkdir()
    ns["owner_repo"] = lambda _repo: "owner/name"

    def fake_run(cmd, cwd=None, check=False):
        payload = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {"isResolved": False, "isOutdated": True, "comments": {"pageInfo": {"hasNextPage": False}, "nodes": [{"databaseId": 123}]}}
                            ],
                        }
                    }
                }
            }
        }
        return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")

    ns["load_review_thread_comment_states"].__globals__["run"] = fake_run
    ns["load_review_thread_comment_states"].__globals__["owner_repo"] = lambda _repo: "owner/name"
    resolved, active = ns["load_review_thread_comment_states"](type("Args", (), {"resolved_review_comment_ids_file": None, "fixture_mode": False, "pr": "7"})(), repo)
    assert resolved == {123}
    assert active == set()


@pytest.mark.parametrize("payload", [
    {"errors": [{"message": "denied"}], "data": None},
    {"data": None},
    {"data": {"repository": None}},
    {"data": {"repository": {"pullRequest": None}}},
    {"data": {"repository": {"pullRequest": {"reviewThreads": None}}}},
    {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": None}}}}},
    {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{"isResolved": False, "isOutdated": False, "comments": {"pageInfo": {"hasNextPage": True}, "nodes": []}}], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}},
    {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{"isResolved": False, "isOutdated": False, "comments": {"pageInfo": {"hasNextPage": False}, "nodes": [{"databaseId": "bad"}]}}], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}},
    {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": None}}}}}},
])
def test_review_threads_reject_malformed_graphql(payload: dict, monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    monkeypatch.setitem(ns["load_review_thread_comment_states"].__globals__, "owner_repo", lambda _repo: "owner/repo")
    monkeypatch.setitem(
        ns["load_review_thread_comment_states"].__globals__,
        "run",
        lambda cmd, **_kwargs: subprocess.CompletedProcess(cmd, 0, json.dumps(payload), ""),
    )
    args = type("Args", (), {"resolved_review_comment_ids_file": None, "fixture_mode": False, "pr": "7"})()

    with pytest.raises(SystemExit) as exc:
        ns["load_review_thread_comment_states"](args, tmp_path)

    assert json.loads(str(exc.value))["error"] in {"review_threads_schema_invalid", "review_thread_comments_truncated"}



def test_devin_review_summary_without_live_inline_issue_is_not_actionable():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    reviews = [{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "**Devin Review** found 1 new potential issue.\n\n<!-- devin-review-badge-begin -->", "user": {"login": "devin-ai-integration[bot]"}}]
    assert ns["actionable_reviews"](reviews, "abc123def456") == []


def test_devin_review_summary_plural_without_live_inline_issue_is_not_actionable():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    reviews = [{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "**Devin Review** found 2 new potential issues.\n\n<!-- devin-review-badge-begin -->", "user": {"login": "devin-ai-integration[bot]"}}]
    assert ns["actionable_reviews"](reviews, "abc123def456") == []


def test_devin_no_issues_review_body_is_not_actionable():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    reviews = [{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "## ✅ Devin Review: No Issues Found\n\nDevin Review analyzed this PR and found no bugs or issues to report.", "user": {"login": "devin-ai-integration[bot]"}}]
    assert ns["actionable_reviews"](reviews, "abc123def456") == []


def test_devin_no_issues_review_body_with_variation_selector_is_not_actionable():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    reviews = [{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "## ✔️ Devin Review: No Issues Found\n\nDevin Review analyzed this PR and found no bugs or issues to report.", "user": {"login": "devin-ai-integration[bot]"}}]
    assert ns["actionable_reviews"](reviews, "abc123def456") == []


def test_devin_no_issues_substring_does_not_hide_actionable_body():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    reviews = [{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "Please fix this bug before merging. Previous text said Devin Review: No Issues Found, but this body is actionable.", "user": {"login": "devin-ai-integration[bot]"}}]
    assert ns["actionable_reviews"](reviews, "abc123def456")



def test_fallback_check_counts_treats_failing_as_failed():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    counts = ns["fallback_check_counts"]("unit\tfailing\t1m\turl\n", "CodeScene")
    assert counts["failed"] == 1
    assert counts["failed_rows"] == ["unit\tfailing\t1m\turl"]



def test_dismissed_review_body_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "DISMISSED", "body": "Old request changes", "user": {"login": "bot"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_select_head_time_without_push_anchor_is_unbound_even_with_check_time():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    commit_time = ns["parse_github_time"]("2026-01-01T00:00:00Z")
    check_time = ns["parse_github_time"]("2026-01-02T03:05:00Z")
    assert ns["select_head_time"](commit_time, check_time, None) is None



def test_select_head_time_without_server_anchor_is_unbound():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    commit_time = ns["parse_github_time"]("2026-01-01T00:00:00Z")
    fallback_time = ns["parse_github_time"]("2026-01-01T00:00:00Z")
    assert ns["select_head_time"](commit_time, None, fallback_time) is None



def test_select_head_time_prefers_pr_push_time_over_backdated_commit_time():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    commit_time = ns["parse_github_time"]("2026-01-01T00:00:00Z")
    push_time = ns["parse_github_time"]("2026-01-02T03:04:05Z")
    check_time = ns["parse_github_time"]("2026-01-02T03:05:00Z")
    assert ns["select_head_time"](commit_time, check_time, None, push_time=push_time) == push_time



def test_push_events_head_time_filters_head_and_branch():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    stdout = json.dumps([
        [
            {"type": "PushEvent", "created_at": "2026-01-02T03:03:00Z", "payload": {"head": "abc123def456", "ref": "refs/heads/other"}},
            {"type": "PushEvent", "created_at": "2026-01-02T03:04:05Z", "payload": {"head": "abc123def456", "ref": "refs/heads/feature"}},
            {"type": "PushEvent", "created_at": "2026-01-02T03:06:00Z", "payload": {"head": "different", "ref": "refs/heads/feature"}},
        ]
    ])
    assert ns["push_events_head_time"](stdout, "abc123def456", "feature") == ns["parse_github_time"]("2026-01-02T03:04:05Z")





def test_same_head_fresh_view_collects_feedback_once_after_refresh(tmp_path: Path, monkeypatch):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    calls = []
    view = live_view()

    def fake_load_view(args, repo):
        return dict(view)

    def fake_collect(args, repo, current_view, head):
        calls.append(current_view)
        return [{"id": 99, "source": "review_comment", "body_preview": "new same-head feedback"}]

    ns["main"].__globals__["load_view"] = fake_load_view
    ns["main"].__globals__["owner_repo"] = lambda _repo: "owner/name"
    parse_calls = []
    ns["main"].__globals__["load_checks"] = lambda args, repo, *_head: "unit\tpass\t1m\turl\n"
    ns["main"].__globals__["resolve_relevant_script"] = lambda args: None
    def fake_parse(script, repo, checks, advisory, relevance_expected=True):
        parse_calls.append(checks)
        return {"failed": 0, "pending": 0, "mode": "all", "kept": 1, "failed_rows": [], "pending_rows": [], "source": "test", "relevance_unavailable": False}
    ns["main"].__globals__["parse_relevant_counts"] = fake_parse
    ns["main"].__globals__["collect_actionable_feedback"] = fake_collect
    monkeypatch.setattr(sys, "argv", live_identity_argv(tmp_path))
    rc = ns["main"]()
    assert rc == 0
    assert len(calls) == 2
    assert len(parse_calls) == 2



def test_same_head_recollect_rechecks_head_after_feedback_collection(tmp_path: Path, monkeypatch, capsys):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    heads = ["a" * 40, "a" * 40, "c" * 40]

    def fake_load_view(args, repo):
        head = heads.pop(0)
        return live_view(head)

    ns["main"].__globals__["load_view"] = fake_load_view
    ns["main"].__globals__["owner_repo"] = lambda _repo: "owner/name"
    ns["main"].__globals__["load_checks"] = lambda args, repo, *_head: "unit\tpass\t1m\turl\n"
    ns["main"].__globals__["resolve_relevant_script"] = lambda args: None
    ns["main"].__globals__["parse_relevant_counts"] = lambda script, repo, checks, advisory, relevance_expected=True: {"failed": 0, "pending": 0, "mode": "all", "kept": 1, "failed_rows": [], "pending_rows": [], "source": "test", "relevance_unavailable": False}
    ns["main"].__globals__["collect_actionable_feedback"] = lambda args, repo, view, head: []
    monkeypatch.setattr(sys, "argv", live_identity_argv(tmp_path))
    with pytest.raises(SystemExit) as exc:
        ns["main"]()
    assert json.loads(str(exc.value)) == {"ok": False, "error": "pr_view_identity_mismatch", "field": "headRefOid"}




def test_same_head_rechecks_head_after_final_feedback_refresh(tmp_path: Path, monkeypatch, capsys):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    heads = ["a" * 40, "a" * 40, "a" * 40, "c" * 40]

    def fake_load_view(args, repo):
        head = heads.pop(0)
        return live_view(head)

    ns["main"].__globals__["load_view"] = fake_load_view
    ns["main"].__globals__["owner_repo"] = lambda _repo: "owner/name"
    ns["main"].__globals__["load_checks"] = lambda args, repo, *_head: "unit\tpass\t1m\turl\n"
    ns["main"].__globals__["resolve_relevant_script"] = lambda args: None
    ns["main"].__globals__["parse_relevant_counts"] = lambda script, repo, checks, advisory, relevance_expected=True: {"failed": 0, "pending": 0, "mode": "all", "kept": 1, "failed_rows": [], "pending_rows": [], "source": "test", "relevance_unavailable": False}
    ns["main"].__globals__["collect_actionable_feedback"] = lambda args, repo, view, head: []
    monkeypatch.setattr(sys, "argv", live_identity_argv(tmp_path))
    with pytest.raises(SystemExit) as exc:
        ns["main"]()
    assert json.loads(str(exc.value)) == {"ok": False, "error": "pr_view_identity_mismatch", "field": "headRefOid"}


def test_invalid_pr_number_is_rejected():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    try:
        ns["validate_pr_number"]("3; rm -rf /")
    except SystemExit as exc:
        assert "invalid_pr_number" in str(exc)
    else:
        raise AssertionError("expected invalid PR number to fail")


def test_parse_paginated_check_runs_flattens_slurped_pages():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    stdout = json.dumps([
        {"check_runs": [{"name": "late", "started_at": "2026-01-02T03:05:00Z"}]},
        {"check_runs": [{"name": "early", "started_at": "2026-01-02T03:04:00Z"}]},
    ])
    rows = ns["parse_paginated_check_runs"](stdout)
    assert [r["name"] for r in rows] == ["late", "early"]
    assert ns["check_runs_head_time"]({"check_runs": rows}) == ns["parse_github_time"]("2026-01-02T03:04:00Z")


def test_check_runs_head_time_uses_earliest_check_start():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    parsed = ns["check_runs_head_time"]({"check_runs": [
        {"created_at": "2026-01-02T03:05:00Z"},
        {"started_at": "2026-01-02T03:04:05Z"},
    ]})
    assert parsed == ns["parse_github_time"]("2026-01-02T03:04:05Z")


def test_commit_json_time_prefers_committer_date():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    parsed = ns["commit_json_time"]({"commit": {"committer": {"date": "2026-01-02T03:04:05Z"}, "author": {"date": "2026-01-01T00:00:00Z"}}})
    assert parsed == ns["parse_github_time"]("2026-01-02T03:04:05Z")


def test_issue_comment_without_head_time_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "Do not merge until X is fixed", "user": {"login": "reviewer"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "issue_comment_unbound"


def test_issue_comment_is_conservative_actionable_signal(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "This still needs a fix", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "reviewer"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "issue_comment_after_head"


def test_old_issue_comment_before_latest_head_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "This used to need a fix", "created_at": "2025-12-31T23:59:00Z", "user": {"login": "reviewer"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_parse_paginated_json_flattens_slurped_pages():
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    parse_paginated_json = ns["parse_paginated_json"]

    data = parse_paginated_json(json.dumps([[{"id": 1}], [{"id": 2}], []]))

    assert data == [{"id": 1}, {"id": 2}]


def test_owner_repo_uses_only_local_origin_and_never_ambient_gh(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    repo = tmp_path / "repo-owner"
    repo.mkdir()

    def fake_run(cmd, cwd=None, check=False):
        if cmd[0] == "gh":
            raise AssertionError("owner_repo must not consult ambient gh repository selection")
        assert cmd == ["git", "config", "--local", "--get-all", "remote.origin.url"]
        return subprocess.CompletedProcess(cmd, 0, "git@github.com:owner/name.git\n", "")

    monkeypatch.setitem(ns["owner_repo"].__globals__, "run", fake_run)

    assert ns["owner_repo"](repo) == "owner/name"


def test_live_view_and_checks_pin_explicit_local_repository(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    repo = tmp_path / "repo-pinned"
    repo.mkdir()
    args = type("Args", (), {"pr": 7, "view_json_file": None, "checks_file": None})()
    captured = {}

    def fake_gh_json(cmd, _repo):
        captured["view"] = cmd
        return {"number": 7}

    def fake_run(cmd, cwd=None, check=False):
        captured.setdefault("checks", []).append(cmd)
        if cmd[2].endswith("/status"):
            return subprocess.CompletedProcess(cmd, 0, json.dumps([{"sha": "a" * 40, "statuses": []}]), "")
        return subprocess.CompletedProcess(cmd, 0, json.dumps([{"check_runs": [{"name": "unit", "head_sha": "a" * 40, "status": "completed", "conclusion": "success"}]}]), "")

    monkeypatch.setitem(ns["load_view"].__globals__, "owner_repo", lambda _repo: "owner/name")
    monkeypatch.setitem(ns["load_view"].__globals__, "gh_json", fake_gh_json)
    monkeypatch.setitem(ns["load_checks"].__globals__, "owner_repo", lambda _repo: "owner/name")
    monkeypatch.setitem(ns["load_checks"].__globals__, "run", fake_run)

    assert ns["load_view"](args, repo) == {"number": 7}
    assert ns["load_checks"](args, repo, "a" * 40).startswith("unit")
    assert captured["view"][-2:] == ["--repo", "owner/name"]
    assert all("repos/owner/name/commits/" in " ".join(cmd) for cmd in captured["checks"])


def test_run_scrubs_ambient_repo_host_and_git_command_overrides(monkeypatch):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    blocked = ["GH_REPO", "GH_HOST", "GH_CONFIG_DIR", "GIT_CONFIG_COUNT", "GIT_SSH_COMMAND", "GIT_ASKPASS", "SSH_ASKPASS", "BASH_ENV", "PYTHONPATH", "PYTHONHOME", "OPAQUE_SECRET"]
    for key in blocked:
        monkeypatch.setenv(key, "attacker-controlled")

    cp = ns["run"](
        [sys.executable, "-c", "import json,os; print(json.dumps({k: os.environ.get(k) for k in ['GH_REPO','GH_HOST','GIT_CONFIG_COUNT','GIT_SSH_COMMAND','GIT_ASKPASS','SSH_ASKPASS']}))"]
    )

    assert cp.returncode == 0
    assert all(value is None for value in json.loads(cp.stdout).values())
    assert all(key not in ns["safe_subprocess_env"]() for key in blocked)


def test_materialized_github_auth_config_is_private_and_source_bound(tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    source = tmp_path / "hosts.yml"
    payload = b"github.com:\n  user: test-user\n  users:\n    test-user:\n"
    source.write_bytes(payload)
    source.chmod(0o600)

    guard = ns["materialize_github_auth_config"](source)
    try:
        private = Path(guard.name)
        copied = private / "hosts.yml"
        assert copied.read_bytes() == payload
        assert stat.S_IMODE(private.stat().st_mode) == 0o700
        assert stat.S_IMODE(copied.stat().st_mode) == 0o600
        assert ns["safe_subprocess_env"]()["GH_CONFIG_DIR"] == str(private)
        assert not (private / "config.yml").exists()
    finally:
        guard.cleanup()
        ns["safe_subprocess_env"].__globals__["_TRUSTED_GH_CONFIG_DIR"] = None


@pytest.mark.parametrize("attack", ["symlink", "parent_symlink", "oversized", "world_readable"])
def test_github_auth_source_rejects_unsafe_files(tmp_path: Path, attack: str):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    source = tmp_path / "hosts.yml"
    if attack == "symlink":
        target = tmp_path / "target.yml"
        target.write_text("github.com:\n  user: test-user\n")
        target.chmod(0o600)
        source.symlink_to(target)
    elif attack == "parent_symlink":
        real_parent = tmp_path / "real-parent"
        real_parent.mkdir()
        source = real_parent / "hosts.yml"
        source.write_text("github.com:\n  user: test-user\n")
        source.chmod(0o600)
        linked_parent = tmp_path / "linked-parent"
        linked_parent.symlink_to(real_parent, target_is_directory=True)
        source = linked_parent / "hosts.yml"
    elif attack == "oversized":
        source.write_bytes(b"x" * (64 * 1024 + 1))
        source.chmod(0o600)
    else:
        source.write_text("github.com:\n  user: test-user\n")
        source.chmod(0o644)

    with pytest.raises(SystemExit) as exc:
        ns["materialize_github_auth_config"](source)

    assert json.loads(str(exc.value))["error"] == "github_auth_config_untrusted"


def test_relevant_check_script_receives_no_github_or_git_credentials(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    script = tmp_path / "relevant-check-status.sh"
    script.write_text("#!/bin/sh\n")
    captured = {}
    for key in ["GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "GH_HOST", "GIT_CONFIG_COUNT", "GIT_ASKPASS", "SSH_AUTH_SOCK", "HOME"]:
        monkeypatch.setenv(key, "secret-or-attacker-controlled")

    def fake_run(cmd, **kwargs):
        captured["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(cmd, 0, "0 0 all 1\n", "")

    patch_bounded_run(monkeypatch, ns, fake_run)
    result = ns["parse_relevant_counts"](script, tmp_path, "unit\tpass\t1m\turl\n", "CodeScene")

    assert result["relevance_unavailable"] is False
    assert captured["env"] is not None
    assert all(captured["env"].get(key) is None for key in ["GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "GH_HOST", "GIT_CONFIG_COUNT", "GIT_ASKPASS", "SSH_AUTH_SOCK", "HOME"])


def test_relevant_check_script_executes_retained_bytes_not_swappable_private_path(monkeypatch, tmp_path: Path):
    """A substituted private shell copy must not forge a failing check into a clean verdict."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    home = tmp_path / "home"
    canonical_root = home / ".claude" / "plugins" / "marketplaces" / "busdriver"
    script = canonical_root / "scripts" / "relevant-check-status.sh"
    script.parent.mkdir(parents=True)
    trusted = b"#!/bin/bash\nprintf '1 0 all 1\\nfailed-check\\tfailure\\n'\n"
    script.write_bytes(trusted)
    script.chmod(0o700)
    globals_ = ns["parse_relevant_counts"].__globals__
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    monkeypatch.setitem(globals_, "authenticated_plugin_bytes", lambda *_args: trusted)
    monkeypatch.setitem(globals_, "trusted_executable_path", lambda name: Path("/bin/bash") if name == "bash" else Path("/usr/bin") / name)

    def swap_script_then_run(cmd, **kwargs):
        assert "-c" in cmd
        assert trusted.decode() in cmd
        # Replace the source pathname after authentication. The child must execute the retained
        # command string, not reopen this path or any private copy of it.
        script.write_text("#!/bin/bash\nprintf '0 0 all 1\\n'\n")
        script.chmod(0o700)
        return subprocess.run(cmd, **kwargs)

    patch_bounded_run(monkeypatch, ns, swap_script_then_run)
    counts = ns["parse_relevant_counts"](
        script,
        tmp_path,
        "failed-check\tfailure\t1m\turl\n",
        "CodeScene",
    )

    assert counts["failed"] == 1, "attacker-replaced relevance helper forged a clean result"


# --- v16-r21: structured OSError fail-closed ---

def test_pr_grind_check_run_helper_returns_rc_127_on_launch_oserror(tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x\n")

    cp = ns["run"](["git", "rev-parse", "HEAD"], cwd=not_a_dir)

    assert cp.returncode == 127
    assert cp.stderr


def test_pr_grind_check_repo_pointing_at_a_file_fails_closed_without_traceback(tmp_path: Path):
    # HOME/gh auth isolation comes from the autouse isolated_github_auth_config fixture.
    not_a_dir = tmp_path / "regular-file.txt"
    not_a_dir.write_text("x\n")

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(not_a_dir), "--pr", "1", "--fixture-mode"],
        text=True,
        capture_output=True,
        env=dict(os.environ),
    )

    assert "Traceback" not in cp.stderr
    assert cp.returncode != 0
    # Same structured fail-closed exit a non-git directory already produces: the rc 127 from
    # run() flows into the existing owner/repo resolution failure instead of an OSError crash.
    # This path exits via SystemExit(json), so the envelope lands on stderr.
    payload = json.loads(cp.stderr)
    assert payload["ok"] is False
    assert payload["error"] == "owner_repo_unresolved"
    assert "Not a directory" in payload["stderr"]


# --- v16-r24 B5: check names and status contexts are third-party-writable strings ---

HEAD40 = "a" * 40


def _load_checks(ns, runs_payload, statuses_payload, monkeypatch, tmp_path: Path):
    responses = iter([
        subprocess.CompletedProcess(["gh"], 0, json.dumps(runs_payload), ""),
        subprocess.CompletedProcess(["gh"], 0, json.dumps(statuses_payload), ""),
    ])
    monkeypatch.setitem(ns["load_checks"].__globals__, "run", lambda *_a, **_k: next(responses))
    args = type("Args", (), {"checks_file": None, "_repository": "owner/repo", "expected_repository": "owner/repo"})()
    return ns["load_checks"](args, tmp_path, HEAD40)


@pytest.mark.parametrize("name", [
    "Build\tsuccess",            # forges the status column of its own row
    "Build\nfabricated\tsuccess",  # fabricates a whole extra row
    "Build\rsuccess",
])
def test_load_checks_rejects_delimiter_injection_in_check_run_name(monkeypatch, tmp_path: Path, name: str):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    runs = [{"check_runs": [{"name": name, "head_sha": HEAD40, "status": "failure", "conclusion": "failure"}]}]

    with pytest.raises(SystemExit) as exc:
        _load_checks(ns, runs, [{"sha": HEAD40, "statuses": []}], monkeypatch, tmp_path)

    assert json.loads(str(exc.value))["error"] == "check_runs_field_delimiter_injection"


@pytest.mark.parametrize("field", ["context", "state"])
def test_load_checks_rejects_delimiter_injection_in_status_context(monkeypatch, tmp_path: Path, field: str):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    item = {"context": "ci", "state": "failure", "target_url": ""}
    item[field] = f"{item[field]}\tsuccess"
    statuses = [{"sha": HEAD40, "statuses": [item]}]

    with pytest.raises(SystemExit) as exc:
        _load_checks(ns, [{"check_runs": []}], statuses, monkeypatch, tmp_path)

    assert json.loads(str(exc.value))["error"] == "status_contexts_field_delimiter_injection"


def test_injected_check_name_cannot_yield_a_clean_verdict(monkeypatch, tmp_path: Path):
    """The end the injection is a means to: a failing check parsed as a passing one.

    `Build\tsuccess` splits into name="Build", status="success", which is not in FAIL_STATUSES,
    so failed stays 0 and classify() returns clean with decision.pr_grind_clean true.
    """
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    runs = [{"check_runs": [{"name": "Build\tsuccess", "head_sha": HEAD40, "status": "completed", "conclusion": "failure"}]}]

    with pytest.raises(SystemExit) as exc:
        _load_checks(ns, runs, [{"sha": HEAD40, "statuses": []}], monkeypatch, tmp_path)

    assert json.loads(str(exc.value))["ok"] is False


# --- v16-r24 B6: fallback counts must state their own relevance truthfully ---


def test_fallback_check_counts_declares_relevance_unavailable_in_live_mode(tmp_path: Path):
    """Live mode reaching the fallback means the pinned plugin lost relevant-check-status.sh.

    r23 omitted the key; classify() reads a missing key as falsy and raises no blocker, so plugin
    drift silently certified a verdict as relevance-checked for any direct consumer.
    """
    ns = runpy.run_path(str(PRODUCTION_CHECK))

    counts = ns["fallback_check_counts"]("unit\tsuccess\t0s\turl\n", "CodeScene", relevance_expected=True)

    assert counts["relevance_unavailable"] is True
    assert counts["source"] == "fallback"


def test_fallback_check_counts_declares_relevance_present_in_fixture_mode(tmp_path: Path):
    """Fixture mode supplies the rows itself, so no relevance authority was ever expected."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))

    counts = ns["fallback_check_counts"]("unit\tsuccess\t0s\turl\n", "CodeScene", relevance_expected=False)

    assert counts["relevance_unavailable"] is False


def test_fallback_counts_block_a_direct_consumer(tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    counts = ns["fallback_check_counts"]("unit\tsuccess\t0s\turl\n", "CodeScene", relevance_expected=True)

    status, blockers = ns["classify"]({"state": "OPEN", "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN", "isDraft": False}, counts, [])

    assert "relevant_check_status_unavailable" in blockers
    assert status != "clean"


def test_live_mode_without_a_relevance_authority_cannot_report_clean(tmp_path: Path):
    """End to end: plugin drift must not yield a clean verdict a consumer would merge on."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    counts = ns["parse_relevant_counts"](None, tmp_path, "unit\tsuccess\t0s\turl\n", "CodeScene", relevance_expected=True)

    status, blockers = ns["classify"]({"state": "OPEN", "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN", "isDraft": False}, counts, [])

    assert counts["relevance_unavailable"] is True
    assert status == "blocked"
    assert "relevant_check_status_unavailable" in blockers


# --- v16-r25 B2: every injected evidence flag is a test double, not live evidence ---

# Read and labelled, never executed: --fixture-mode is a sufficient boundary for these.
INJECTED_EVIDENCE_FILE_FLAGS = (
    "--checks-file",
    "--review-comments-file",
    "--issue-comments-file",
    "--reviews-file",
    "--resolved-review-comment-ids-file",
    "--view-json-file",
)
# Names a program rather than a file, so no flag makes it acceptable. See r32 item 1.
CUSTOM_HELPER_EXECUTABLE_FLAG = "--relevant-check-script"
INJECTED_EVIDENCE_FLAGS = (*INJECTED_EVIDENCE_FILE_FLAGS, CUSTOM_HELPER_EXECUTABLE_FLAG)


@pytest.mark.parametrize("flag", INJECTED_EVIDENCE_FILE_FLAGS)
def test_injected_evidence_flag_is_not_in_the_production_parser_at_all(tmp_path: Path, flag: str):
    """v16-r33 A: there is nothing left to gate, because the flag no longer exists here.

    r24 gated only --relevant-check-script; the other six ran fully live, so `--checks-file
    forged.tsv` on an otherwise real invocation emitted an authoritative clean. r32 closed that by
    making every injected flag imply --fixture-mode — still the wrong boundary, because production
    went on shipping a parser AND a reader for caller-authored evidence, and the caller who passes
    the evidence is the caller who passes the mode. r33 removes the affordance instead of labelling
    it: the flags, their readers and their labels live only in the non-installed harness, so
    production rejects the NAME before main() runs and never reaches a read of any kind.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    payload = tmp_path / "injected"
    payload.write_text("[]")

    cp = subprocess.run(
        [sys.executable, *live_identity_argv(repo), flag, str(payload)],
        text=True, capture_output=True,
    )

    assert cp.returncode == 2, f"production accepted {flag}: {cp.stdout}"
    assert "unrecognized arguments" in cp.stderr
    assert flag in cp.stderr
    # Refused at the parser, so no live read and no envelope were ever produced.
    assert cp.stdout == ""


def test_custom_helper_executable_is_refused_outright_not_merely_gated(tmp_path: Path):
    """r32 item 1: --fixture-mode gated this, and the caller passes --fixture-mode.

    The other injected-evidence flags name FILES, whose bytes the envelope can label as a double.
    This one names a PROGRAM, and a label cannot un-run code. Production refuses it at every flag
    setting; the double reaches the checker only through the source-separated harness.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    witness = tmp_path / "spawned"
    script = tmp_path / "relevant.sh"
    script.write_text(f"#!/bin/sh\ntouch {witness}\nprintf '0 0 all 1\\n'\n")
    script.chmod(0o755)

    # --fixture-mode is no longer a setting production has (r33 A), so the only combination left is
    # the bare flag — and it is refused by name rather than by argparse accident, which is why
    # --relevant-check-script is still in production's parser at all.
    for combination in (["--fixture-mode"], []):
        cp = subprocess.run(
            [sys.executable, *live_identity_argv(repo), *combination, CUSTOM_HELPER_EXECUTABLE_FLAG, str(script)],
            text=True, capture_output=True,
        )

        assert cp.returncode != 0, f"production accepted {combination}: {cp.stdout}"
        assert not witness.exists(), f"the caller's program was spawned under {combination}"

    # The bare invocation is the one that must produce the STRUCTURED refusal, not a usage dump.
    cp = subprocess.run(
        [sys.executable, *live_identity_argv(repo), CUSTOM_HELPER_EXECUTABLE_FLAG, str(script)],
        text=True, capture_output=True,
    )
    body = json.loads(cp.stderr)
    assert body["error"] == "custom_helper_execution_not_permitted"
    assert body["flags"] == ["relevant_check_script"]
    assert not witness.exists()


def test_injected_evidence_cannot_forge_a_live_authoritative_clean(tmp_path: Path):
    """The r24 HIGH-1 attack verbatim: real identity args, forged evidence files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    checks = tmp_path / "checks.tsv"
    checks.write_text("unit\tsuccess\t0s\turl\n")
    empty = tmp_path / "empty.json"
    empty.write_text("[]")

    cp = subprocess.run(
        [
            sys.executable, *live_identity_argv(repo),
            "--checks-file", str(checks),
            "--review-comments-file", str(empty),
            "--issue-comments-file", str(empty),
            "--reviews-file", str(empty),
        ],
        text=True, capture_output=True,
    )

    assert cp.returncode == 2, f"production accepted forged evidence: {cp.stdout}"
    assert "unrecognized arguments" in cp.stderr
    for flag in ("--checks-file", "--review-comments-file", "--issue-comments-file", "--reviews-file"):
        assert flag in cp.stderr
    # The forged clean is not merely labelled non-authoritative any more: it is never emitted.
    assert cp.stdout == ""


def test_fixture_mode_result_declares_non_authoritative_provenance(tmp_path: Path):
    """Fixture evidence may still be clean, but must say so is not authoritative."""
    result = run_check(tmp_path, "unit\tsuccess\t0s\turl\n", [])

    assert result["status"] == "clean"
    assert result["evidence"]["authoritative"] is False
    assert result["evidence"]["fixture_mode"] is True
    assert result["evidence"]["injected_flags"] == [
        "--checks-file", "--review-comments-file", "--view-json-file",
    ]


# --- v16-r25 B4: every splitlines() boundary and C0/C1 control is a delimiter ---


@pytest.mark.parametrize("char, label", [
    ("\v", "vertical_tab"),
    ("\f", "form_feed"),
    ("\x1c", "file_separator"),
    ("\x1d", "group_separator"),
    ("\x1e", "record_separator"),
    ("\x85", "next_line"),
    (" ", "line_separator"),
    (" ", "paragraph_separator"),
    ("\x00", "nul"),
    ("\x1b", "escape"),
])
def test_delimiter_safe_rejects_every_control_character(char: str, label: str):
    ns = runpy.run_path(str(PRODUCTION_CHECK))

    with pytest.raises(SystemExit) as exc:
        ns["delimiter_safe"](f"Build{char}success", "check_runs_field_delimiter_injection")

    assert json.loads(str(exc.value))["error"] == "check_runs_field_delimiter_injection"


def test_delimiter_safe_rejects_every_character_its_consumers_split_on():
    """The guard must be a superset of what splitlines() splits on, proven exhaustively.

    r24 pinned ROW_DELIMITERS to tab/LF/CR by hand while two in-file consumers re-split with
    splitlines(), which additionally breaks on \\v \\f \\x1c \\x1d \\x1e \\x85 \\u2028 \\u2029.
    Enumerating the boundary set from the consumer, rather than restating it, is what keeps the
    two from drifting apart again.
    """
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    boundaries = [chr(code) for code in range(0x11000) if len(f"a{chr(code)}b".splitlines()) > 1]
    assert " " in boundaries  # guard against a no-op enumeration

    for char in boundaries:
        with pytest.raises(SystemExit):
            ns["delimiter_safe"](f"Build{char}success", "check_runs_field_delimiter_injection")


def test_delimiter_safe_still_accepts_ordinary_check_names():
    ns = runpy.run_path(str(PRODUCTION_CHECK))

    assert ns["delimiter_safe"]("build / test (ubuntu-latest, 3.12)", "e") == "build / test (ubuntu-latest, 3.12)"
    assert ns["delimiter_safe"]("codecov/patch — 92% of diff hit", "e") == "codecov/patch — 92% of diff hit"


@pytest.mark.parametrize("char", ["\v", "\x85", " "])
def test_control_character_check_name_cannot_inflate_kept(monkeypatch, tmp_path: Path, char: str):
    """The end the injection is a means to: fabricating rows a consumer counts as kept."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    runs = [{"check_runs": [{"name": f"Build{char}extra\tsuccess", "head_sha": HEAD40, "status": "completed", "conclusion": "failure"}]}]

    with pytest.raises(SystemExit) as exc:
        _load_checks(ns, runs, [{"sha": HEAD40, "statuses": []}], monkeypatch, tmp_path)

    assert json.loads(str(exc.value))["ok"] is False


# --- v16-r25 B5: no production envelope emits a raw secret or credential-bearing remote ---


def test_owner_repo_failure_redacts_userinfo_in_the_remote_url(monkeypatch, tmp_path: Path):
    """r24 echoed the remote verbatim: the userinfo form matches no pattern, so it fell through."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    url = "https://" + "x-access-token:" + "ghs_deadbeefdeadbeefdeadbeefdeadbeef@github.com/o/r.git"
    monkeypatch.setitem(ns["owner_repo"].__globals__, "run", lambda *_a, **_k: subprocess.CompletedProcess(["git"], 0, f"{url}\n", ""))

    with pytest.raises(SystemExit) as exc:
        ns["owner_repo"](tmp_path)

    body = json.loads(str(exc.value))
    assert body["error"] == "owner_repo_unresolved"
    assert "ghs_deadbeefdeadbeefdeadbeefdeadbeef" not in json.dumps(body)
    assert body["remote"] == "https://[REDACTED]@github.com/o/r.git"


def test_gh_failure_stderr_is_bounded_and_redacted(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    secret = "ghp_" + "z" * 36
    monkeypatch.setitem(ns["gh_json"].__globals__, "run", lambda *_a, **_k: subprocess.CompletedProcess(["gh"], 1, "", f"HTTP 401: bad credentials {secret}\n" + "x" * 9000))

    with pytest.raises(SystemExit) as exc:
        ns["gh_json"](["gh", "pr", "view"], tmp_path)

    body = json.loads(str(exc.value))
    assert body["error"] == "gh_failed"
    assert secret not in json.dumps(body)
    assert len(body["stderr"]) <= 4000


@pytest.mark.parametrize("loader, error", [
    ("load_review_comments", "review_comments_unavailable"),
    ("load_issue_comments", "issue_comments_unavailable"),
    ("load_reviews", "reviews_unavailable"),
])
def test_feedback_loader_failures_are_bounded_and_redacted(monkeypatch, tmp_path: Path, loader: str, error: str):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    secret = "ghp_" + "q" * 36
    monkeypatch.setitem(ns[loader].__globals__, "run", lambda *_a, **_k: subprocess.CompletedProcess(["gh"], 1, "", f"{secret} " + "y" * 9000))
    args = type("Args", (), {
        "review_comments_file": None, "issue_comments_file": None, "reviews_file": None,
        "fixture_mode": False, "pr": "7", "_repository": "owner/repo", "expected_repository": "owner/repo",
    })()

    with pytest.raises(SystemExit) as exc:
        ns[loader](args, tmp_path)

    body = json.loads(str(exc.value))
    assert body["error"] == error
    assert secret not in json.dumps(body)
    assert len(body["stderr"]) <= 4000


def test_relevant_script_error_is_bounded_and_redacted(monkeypatch, tmp_path: Path):
    """parse_relevant_counts:1019 copied stderr AND stdout onto an ok:true envelope."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    secret = "ghp_" + "w" * 36
    script = tmp_path / "relevant.sh"
    script.write_text("#!/bin/sh\nexit 1\n")
    script.chmod(0o700)
    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(["bash"], 1, "", f"{secret} " + "e" * 9000)

    patch_bounded_run(monkeypatch, ns, fake_run)

    counts = ns["parse_relevant_counts"](script, tmp_path, "unit\tsuccess\t0s\turl\n", "CodeScene")

    assert counts["relevance_unavailable"] is True
    assert secret not in json.dumps(counts)
    assert len(counts["error"]) <= 4000


def test_redact_text_removes_credential_env_values(monkeypatch):
    """A token that matches no shape pattern is still a token when it is our own env value."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    monkeypatch.setenv("GH_TOKEN", "an-opaque-enterprise-credential")

    assert "an-opaque-enterprise-credential" not in ns["redact_text"]("failed: an-opaque-enterprise-credential")


@pytest.mark.parametrize("prefix_len", [0, 3990, 3999, 4000, 4200])
def test_secrets_are_redacted_across_the_truncation_boundary(prefix_len: int):
    """Redaction must run BEFORE the tail slice, or a bisected token survives the cut.

    Each prefix length lands the token on a different side of, or straddling, the 4000-byte cut.
    The prefix ends in a space because a token abutted to word characters is not a token — the
    \b anchor in the shape patterns is a false-positive guard, not a gap.
    """
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    secret = "ghp_" + "k" * 36

    out = ns["tail"]("p" * prefix_len + " " + secret + " " + "s" * 50)

    assert "ghp_" not in out
    assert len(out) <= 4000


# --- v16-r33 item B1: a comment body is untrusted text, and every body path redacts it ---
#
# r32 High: reviews, review comments and issue comments were each copied into `body_preview` as a
# raw `body[:500]` and printed. A PR body is written by anyone who can comment on the PR — a bot
# pasting a failing curl, a reviewer quoting a log — so it is exactly the untrusted text the
# redaction contract governs, and it was the one emitter that never ran it. The four sites are one
# helper's callers, so the fix is tested at the helper AND at every path that reaches it.

# A NONSECRET diagnostic must survive alongside each: the preview exists to be read.
DIAGNOSTIC = "Please fix the retry loop in worker.py"

BODY_SECRETS = {
    "github_token": "ghp_" + "z" * 36,
    "github_pat": "github_pat_" + "1" * 30,
    "openai_key": "sk-" + "s" * 40,
    "bearer_header": "Authorization: Bearer " + "b" * 40,
    "assignment": "api_key=" + "k" * 40,
    # Nested, which is the shape the reviewer called out: a secret buried inside a JSON blob a bot
    # pasted into its comment, not sitting at the top level where a shallow scan would find it.
    "nested_json": '{"ci": {"env": {"token": "' + "n" * 40 + '"}}}',
    "url_userinfo": "https://" + "x-access-token:" + "ghs_" + "y" * 36 + "@github.com/o/r.git",
}


def secret_needle(name: str) -> str:
    """The part that must never survive — for the two shapes whose key/prefix legitimately stays."""
    if name == "bearer_header":
        return "b" * 40
    if name == "assignment":
        return "k" * 40
    if name == "nested_json":
        return "n" * 40
    if name == "url_userinfo":
        return "ghs_" + "y" * 36
    return BODY_SECRETS[name]


HEAD = "a" * 40


def _body(secret: str) -> str:
    return f"{DIAGNOSTIC}. Repro: {secret}"


@pytest.mark.parametrize("name", sorted(BODY_SECRETS))
def test_review_body_preview_never_emits_a_credential(name: str):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    review = {"id": 1, "state": "CHANGES_REQUESTED", "commit_id": HEAD, "user": {"login": "reviewer"}, "body": _body(BODY_SECRETS[name])}

    out = ns["actionable_reviews"]([review], HEAD)

    assert secret_needle(name) not in json.dumps(out)
    assert DIAGNOSTIC in out[0]["body_preview"], "redaction ate the diagnostic"


@pytest.mark.parametrize("name", sorted(BODY_SECRETS))
def test_review_comment_body_preview_never_emits_a_credential(name: str):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    comment = {"id": 5, "path": "worker.py", "line": 4, "commit_id": HEAD, "user": {"login": "reviewer"}, "body": _body(BODY_SECRETS[name])}

    out = ns["actionable_comments"]([comment], HEAD, None, set(), set(), None, set())

    assert secret_needle(name) not in json.dumps(out)
    assert DIAGNOSTIC in out[0]["body_preview"], "redaction ate the diagnostic"


@pytest.mark.parametrize("name", sorted(BODY_SECRETS))
def test_issue_comment_body_preview_never_emits_a_credential(name: str):
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    comment = {"id": 7, "user": {"login": "reviewer"}, "body": _body(BODY_SECRETS[name])}

    out = ns["actionable_issue_comments"]([comment], None)

    assert secret_needle(name) not in json.dumps(out)
    assert DIAGNOSTIC in out[0]["body_preview"], "redaction ate the diagnostic"


@pytest.mark.parametrize("name", sorted(BODY_SECRETS))
def test_bot_progress_body_preview_never_emits_a_credential(name: str):
    """The fourth body[:500] site: the bot_progress branch has its own copy of the same bug."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    body = f"Currently processing new changes. {DIAGNOSTIC}. Repro: {BODY_SECRETS[name]}"
    comment = {"id": 9, "user": {"login": "coderabbitai[bot]"}, "body": body}

    out = ns["actionable_issue_comments"]([comment], None)

    assert out[0]["source"] == "bot_progress"
    assert secret_needle(name) not in json.dumps(out)


def test_body_preview_redacts_our_own_credential_env_value(monkeypatch):
    """An opaque enterprise token matches no shape pattern; a bot echoing it back must not print it."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    monkeypatch.setenv("GH_TOKEN", "an-opaque-enterprise-credential-value")
    review = {"id": 1, "state": "CHANGES_REQUESTED", "commit_id": HEAD, "user": {"login": "reviewer"}, "body": f"{DIAGNOSTIC}. push failed with an-opaque-enterprise-credential-value"}

    out = ns["actionable_reviews"]([review], HEAD)

    assert "an-opaque-enterprise-credential-value" not in json.dumps(out)


def test_body_preview_stays_bounded_at_500_characters():
    """The bound the raw slice already had must survive the redaction that now precedes it."""
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    review = {"id": 1, "state": "CHANGES_REQUESTED", "commit_id": HEAD, "user": {"login": "reviewer"}, "body": "L" * 5000}

    out = ns["actionable_reviews"]([review], HEAD)

    assert len(out[0]["body_preview"]) == 500


def test_body_preview_redacts_a_secret_straddling_the_500_character_cut():
    """Slice-then-redact leaves a bisected token: the fragment matches no shape pattern and ships.

    This is the head-slice twin of the tail bug the r26 suite above already fences. The token
    starts inside the emitted region and runs past it, so only redaction BEFORE the cut can see it
    whole.
    """
    ns = runpy.run_path(str(PRODUCTION_CHECK))
    secret = "ghp_" + "m" * 36
    review = {"id": 1, "state": "CHANGES_REQUESTED", "commit_id": HEAD, "user": {"login": "reviewer"}, "body": "P" * 480 + " " + secret + " trailing"}

    out = ns["actionable_reviews"]([review], HEAD)

    assert "ghp_" not in out[0]["body_preview"], "a bisected token survived the 500-char cut"
