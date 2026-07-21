import argparse
import ast
import hashlib
import json
import os
import runpy
import shlex
import shutil
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / "tests" / "fixtures" / "pi" / "agent-draft-test-harness"
PRODUCTION_DRAFT = ROOT / "scripts" / "hermes-busdriver-agent-draft"
PRODUCTION_OPENCODE = ROOT / "scripts" / "opencode" / "run-opencode-busdriver-draft"
OPENCODE = ROOT / "tests" / "fixtures" / "opencode" / "run-opencode-test-harness"
LOCK = ROOT / "scripts" / "hermes-busdriver-lock"


def sh(cmd, cwd=None, check=True, env=None):
    cp = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, check=False)
    if check and cp.returncode != 0:
        raise AssertionError(f"cmd failed rc={cp.returncode}\nCMD={cmd}\nSTDOUT={cp.stdout}\nSTDERR={cp.stderr}")
    return cp


def init_repo(path: Path) -> None:
    sh(["git", "init"], cwd=path)
    sh(["git", "config", "user.email", "test@example.com"], cwd=path)
    sh(["git", "config", "user.name", "Test User"], cwd=path)
    (path / "src").mkdir()
    (path / "src" / "app.txt").write_text("hello\n")
    (path / ".gitignore").write_text(".env\n")
    sh(["git", "add", "."], cwd=path)
    env = os.environ | {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "commit.gpgSign", "GIT_CONFIG_VALUE_0": "false"}
    sh(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], cwd=path, env=env)


def fake_busdriver(path: Path) -> Path:
    root = path / "busdriver"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [], "PostToolUse": [], "Stop": []}}))
    (root / "package.json").write_text(json.dumps({"version": "test"}))
    return root


def run_draft(*args: str, check=True):
    cp = subprocess.run([sys.executable, str(DRAFT), *args], text=True, capture_output=True)
    if check and cp.returncode != 0:
        raise AssertionError(f"draft failed rc={cp.returncode}\nSTDOUT={cp.stdout}\nSTDERR={cp.stderr}")
    return cp, json.loads(cp.stdout)


def test_agent_trusted_git_is_the_root_owned_source_executed_in_place():
    """git is validated and executed where root put it — no private copy is materialized.

    What this replaced is worth naming, because it looked like it was testing something. The old
    test wrote its own `git` into tmp_path, pointed a `TRUSTED_GIT` global at it, patched the digest
    to match, and asserted the launcher ran a 0500 copy of those bytes. It passed. What it was
    demonstrating, in hindsight, is the defect the migration removed: the source was a *variable*,
    so a test could name it and so could anything else. `trusted_executable_path()` now takes a NAME
    and reads the path from a frozen table, and there is no `TRUSTED_GIT` left to point anywhere.
    """
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    globals_ = ns["trusted_executable_path"].__globals__

    resolved = ns["trusted_executable_path"]("git")

    assert resolved == globals_["TRUSTED_EXECUTABLE_SOURCES"]["git"] == Path("/usr/bin/git")
    st = os.lstat(resolved)
    assert st.st_uid == 0, "a same-UID adversary must not own the bytes that execute"
    assert not (st.st_mode & (stat.S_IWGRP | stat.S_IWOTH))
    assert not stat.S_ISLNK(st.st_mode), "the name that execs must not be a symlink"
    # Read back through __globals__, never through `ns`: runpy.run_path returns a *copy* of the
    # module namespace, so a rebind by the call above is invisible in `ns` and this assertion would
    # hold no matter what the resolver did.
    assert globals_["_TRUSTED_EXECUTABLE_RUNTIME"] is None, "a private runtime dir was created"
    assert globals_["_TRUSTED_EXECUTABLE_PATHS"] == {}, "a private copy was retained"


def test_agent_draft_has_no_caller_selected_git_source():
    """The frozen table is the whole source surface: no name to redirect, no env to set."""
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    globals_ = ns["trusted_executable_path"].__globals__

    assert "TRUSTED_GIT" not in globals_, "the redirectable global is back"
    assert set(globals_["TRUSTED_EXECUTABLE_SOURCES"]) == {"git", "gh", "bash", "python3"}
    for name, path in globals_["TRUSTED_EXECUTABLE_SOURCES"].items():
        assert path.is_absolute(), name
        assert not str(path).startswith("/opt/homebrew"), name


def test_agent_unsupported_name_is_refused_rather_than_resolved():
    """A name absent from the table is a refusal, never a PATH lookup."""
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    with pytest.raises(SystemExit) as excinfo:
        ns["trusted_executable_path"]("perl")
    assert "trusted_root_owned_source_unsupported" in str(excinfo.value)


def test_agent_missing_gh_fails_closed_by_name():
    """gh is allowed to be absent; an absent gh must refuse, not fall through to another gh."""
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    if Path("/usr/local/bin/gh").exists():
        assert ns["trusted_executable_path"]("gh") == Path("/usr/local/bin/gh")
        return
    with pytest.raises(SystemExit) as excinfo:
        ns["trusted_executable_path"]("gh")
    assert "trusted_root_owned_gh_unavailable" in str(excinfo.value)


def test_agent_command_resolves_default_pi_to_manifest_path(tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    args = argparse.Namespace(
        agent="pi",
        timeout=180,
        repo=str(tmp_path),
        pi_bin="pi",
        pi_model="openai-codex/gpt-5.4-mini",
        pi_provider="",
        scope_include=[],
        scope_exclude=[],
    )

    cmd = ns["agent_command"](args, tmp_path / "prompt.md", tmp_path / "run")

    private_pi = Path(cmd[cmd.index("--pi-bin") + 1])
    assert private_pi != ns["TRUSTED_PI"]
    assert stat.S_IMODE(private_pi.stat().st_mode) == 0o500
    assert hashlib.sha256(private_pi.read_bytes()).hexdigest() == ns["TRUSTED_EXECUTABLE_DIGESTS"]["pi"]


def test_agent_command_resolves_default_opencode_to_manifest_path(tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    args = argparse.Namespace(
        agent="opencode",
        timeout=180,
        repo=str(tmp_path),
        opencode_bin="opencode",
        opencode_agent="build",
        opencode_model="",
        scope_include=[],
        scope_exclude=[],
    )

    cmd = ns["agent_command"](args, tmp_path / "prompt.md", tmp_path / "run")

    private_opencode = Path(cmd[cmd.index("--opencode-bin") + 1])
    assert private_opencode != ns["TRUSTED_OPENCODE"]
    assert stat.S_IMODE(private_opencode.stat().st_mode) == 0o500
    assert hashlib.sha256(private_opencode.read_bytes()).hexdigest() == ns["TRUSTED_EXECUTABLE_DIGESTS"]["opencode"]


def test_agent_command_rejects_untrusted_opencode_override(tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    args = argparse.Namespace(
        agent="opencode",
        timeout=180,
        repo=str(tmp_path),
        opencode_bin=str(tmp_path / "untrusted-opencode"),
        opencode_agent="build",
        opencode_model="",
        scope_include=[],
        scope_exclude=[],
    )

    try:
        ns["agent_command"](args, tmp_path / "prompt.md", tmp_path / "run")
    except SystemExit as exc:
        data = json.loads(str(exc))
    else:
        raise AssertionError("untrusted OpenCode override was accepted")

    assert data["error"] == "opencode_executable_override_rejected"


def run_opencode_adapter(
    repo: Path,
    plugin: Path,
    state: Path,
    opencode_bin: Path,
    prompt: str,
    *scope_include: str,
    check: bool = True,
    timeout: int = 30,
):
    run_dir = state / "opencode-run"
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = run_dir / "prompt.md"
    prompt_file.write_text(prompt + "\n")
    guard_bin = state / "guard-bin"
    guard_bin.mkdir(parents=True, exist_ok=True)
    git_guard = guard_bin / "git"
    git_guard.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in commit|push|merge|rebase|reset|tag) exit 126;; esac\n"
        f"exec {shutil.which('git') or '/usr/bin/git'} \"$@\"\n"
    )
    git_guard.chmod(0o700)
    gh_guard = guard_bin / "gh"
    gh_guard.write_text("#!/bin/sh\nexit 126\n")
    gh_guard.chmod(0o700)

    env = os.environ.copy()
    env.update({
        "HERMES_AGENT_DRAFT_GUARDED": "1",
        "HERMES_AGENT_DRAFT_GUARD_BIN": str(guard_bin),
        "PATH": str(guard_bin) + os.pathsep + env.get("PATH", ""),
        "BUSDRIVER_PLUGIN_ROOT": str(plugin),
        "CLAUDE_PLUGIN_ROOT": str(plugin),
        "BUSDRIVER_STATE_DIR": ".opencode",
    })
    cmd = [
        sys.executable,
        str(OPENCODE),
        "--repo", str(repo),
        "--prompt-file", str(prompt_file),
        "--run-dir", str(run_dir),
        "--opencode-bin", str(opencode_bin),
        "--timeout", str(timeout),
    ]
    for pattern in scope_include:
        cmd += ["--scope-include", pattern]
    cp = subprocess.run(cmd, text=True, capture_output=True, env=env, check=False)
    if check and cp.returncode != 0:
        raise AssertionError(f"opencode adapter failed rc={cp.returncode}\nSTDOUT={cp.stdout}\nSTDERR={cp.stderr}")
    return cp, json.loads(cp.stdout), run_dir


def write_fake_opencode(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env python3\n" + body)
    path.chmod(0o755)


def valid_opencode_payload(files_changed: list[str], *, status: str = "needs_busdriver_review") -> dict:
    ok = status == "needs_busdriver_review"
    return {
        "schema": "opencode-busdriver-result/v0",
        "worker": "opencode",
        "mode": "generic_gated_draft",
        "ok": ok,
        "status": status,
        "not_busdriver_native_claude_runtime": True,
        "finalization_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pr_allowed": False,
        "merge_allowed": False,
        "marker_write_allowed": False,
        "deploy_allowed": False,
        "release_allowed": False,
        "publish_allowed": False,
        "authority": {
            "commit_allowed": False,
            "push_allowed": False,
            "pr_allowed": False,
            "merge_allowed": False,
            "marker_write_allowed": False,
            "deploy_allowed": False,
            "release_allowed": False,
            "publish_allowed": False,
            "finalization_allowed": False,
        },
        "files_changed": files_changed,
        **({"blockers": ["fake blocked"]} if not ok else {}),
    }


def test_production_launcher_ignores_ambient_git_and_gh_path(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo-pinned-tools"
    repo.mkdir()
    init_repo(repo)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    sentinel = tmp_path / "ambient-tool-ran"
    for name in ("git", "gh"):
        fake = fake_bin / name
        fake.write_text(f"#!/bin/sh\ntouch {sentinel}\nexit 99\n")
        fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin))
    ns = runpy.run_path(str(PRODUCTION_DRAFT))

    assert ns["git_root"](repo) == repo
    guard = ns["build_guard_bin"](tmp_path / "run")

    assert not sentinel.exists(), "the ambient PATH chose the binary that ran"
    # The shim the agent executes as `git` must exec the frozen root-owned source by ABSOLUTE
    # path. A bare `git` here would re-enter PATH resolution inside the shim and undo the guard.
    real_git = Path(shlex.split((guard / "git").read_text().splitlines()[-1])[1])
    assert real_git == ns["TRUSTED_EXECUTABLE_SOURCES"]["git"] == Path("/usr/bin/git")
    assert real_git.is_absolute()
    assert os.lstat(real_git).st_uid == 0
    assert str(fake_bin) not in (guard / "git").read_text()
    # gh is allowed to be absent, and this guard dir sits at the HEAD of a PATH whose tail still
    # has /opt/homebrew/bin — so an unclaimed `gh` name resolves PAST the guard to an unguarded
    # Homebrew gh holding the agent's HOME. Absent gh must mean "gh refuses", never "gh is
    # somebody else's". Asserted on whichever state this host is actually in, so that provisioning
    # gh later cannot turn this into a silent skip.
    gh_shim = (guard / "gh").read_text()
    assert "/opt/homebrew" not in gh_shim
    assert str(fake_bin) not in gh_shim
    if Path("/usr/local/bin/gh").exists():
        assert shlex.split(gh_shim.splitlines()[-1])[1] == "/usr/local/bin/gh"
    else:
        assert "trusted_root_owned_gh_unavailable" in gh_shim
        assert "exec" not in gh_shim


def fake_trusted_opencode(path: Path, sentinel: Path) -> Path:
    write_fake_opencode(
        path,
        "import json, os\n"
        "from pathlib import Path\n"
        f"Path({str(sentinel)!r}).write_text('ran')\n"
        f"Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text(json.dumps({valid_opencode_payload([])!r}))\n",
    )
    return path


def pin_trusted_opencode(ns: dict, monkeypatch, anchor: Path) -> None:
    globals_ = ns["main"].__globals__
    monkeypatch.setitem(globals_, "TRUSTED_OPENCODE", anchor.resolve())
    monkeypatch.setitem(globals_, "TRUSTED_OPENCODE_SHA256", hashlib.sha256(anchor.read_bytes()).hexdigest())


def environment_keys_read(tree: ast.Module) -> set[str]:
    keys: set[str] = set()
    for node in ast.walk(tree):
        environ = None
        key = None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            environ, key = node.func.value, node.args[0] if node.args else None
        elif isinstance(node, ast.Subscript):
            environ, key = node.value, node.slice
        if (
            isinstance(environ, ast.Attribute)
            and environ.attr == "environ"
            and isinstance(key, ast.Constant)
            and isinstance(key.value, str)
        ):
            keys.add(key.value)
    return keys


def test_production_opencode_wrapper_never_reads_binary_from_ambient_env_or_path():
    # v16-r25 MEDIUM-5: this wrapper mounts a private HOME holding a real
    # auth.json, so a PATH- or env-selected executable would run as arbitrary
    # code with live provider credentials. Neither source may name the launch
    # target, and there is no PATH fallback to regress back into. Asserted over
    # the AST so the docstring may keep naming the defect it closes.
    tree = ast.parse(PRODUCTION_OPENCODE.read_text())
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    opencode_bin_defaults = [
        keyword.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", None) == "add_argument"
        and node.args
        and getattr(node.args[0], "value", None) == "--opencode-bin"
        for keyword in node.keywords
        if keyword.arg == "default"
    ]

    assert "OPENCODE_BIN" not in environment_keys_read(tree)
    assert "which" not in called
    assert [default.value for default in opencode_bin_defaults] == [None]


def test_trusted_opencode_executable_rejects_untrusted_and_retains_verified_bytes(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_OPENCODE))
    planted_dir = tmp_path / "planted-bin"
    planted_dir.mkdir()
    planted = planted_dir / "opencode"
    planted.write_text("#!/bin/sh\nexit 0\n")
    planted.chmod(0o755)
    monkeypatch.setenv("PATH", str(planted_dir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("OPENCODE_BIN", str(planted))
    anchor = tmp_path / "trusted-opencode"
    anchor.write_bytes(b"reviewed-opencode\n")
    anchor.chmod(0o755)
    pin_trusted_opencode(ns, monkeypatch, anchor)

    with pytest.raises(RuntimeError) as planted_error:
        ns["trusted_opencode_executable"](str(planted))
    with pytest.raises(RuntimeError) as bare_name_error:
        ns["trusted_opencode_executable"]("opencode-on-path")

    assert str(planted_error.value) == "opencode_executable_integrity_failed"
    assert str(bare_name_error.value) == "opencode_executable_override_rejected"

    private = ns["trusted_opencode_executable"](None)
    retained = private.read_bytes()
    anchor.write_bytes(b"swapped-after-authentication\n")

    assert private != anchor
    assert private.read_bytes() == retained == b"reviewed-opencode\n"
    assert not private.is_symlink()
    assert private.stat().st_uid == os.getuid()
    assert private.stat().st_nlink == 1
    assert stat.S_IMODE(private.stat().st_mode) == 0o500


def opencode_wrapper_main(ns: dict, monkeypatch, repo: Path, run_dir: Path, *extra: str) -> int:
    guard_bin = run_dir.parent / "guard-bin"
    guard_bin.mkdir(parents=True, exist_ok=True)
    for name in ("git", "gh"):
        helper = guard_bin / name
        helper.write_text(f"#!/bin/sh\nexec {shutil.which(name) or '/usr/bin/' + name} \"$@\"\n")
        helper.chmod(0o700)
    prompt_file = run_dir.parent / "prompt.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text("draft the change\n")
    monkeypatch.setenv("HERMES_AGENT_DRAFT_GUARDED", "1")
    monkeypatch.setenv("HERMES_AGENT_DRAFT_GUARD_BIN", str(guard_bin))
    monkeypatch.setenv("PATH", str(guard_bin) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setattr(sys, "argv", [
        str(PRODUCTION_OPENCODE),
        "--repo", str(repo),
        "--prompt-file", str(prompt_file),
        "--run-dir", str(run_dir),
        *extra,
    ])
    return ns["main"]()


def test_production_opencode_wrapper_ignores_ambient_opencode_bin_env(monkeypatch, capsys, tmp_path: Path):
    repo = tmp_path / "repo-env-planted-opencode"
    repo.mkdir()
    init_repo(repo)
    ns = runpy.run_path(str(PRODUCTION_OPENCODE))
    monkeypatch.setitem(ns["main"].__globals__, "production_dispatch_blocker", lambda: None)
    planted_dir = tmp_path / "planted-bin"
    planted_dir.mkdir()
    planted_sentinel = tmp_path / "planted-ran"
    planted = planted_dir / "opencode"
    planted.write_text(f"#!/bin/sh\ntouch {planted_sentinel}\n")
    planted.chmod(0o755)
    trusted_sentinel = tmp_path / "trusted-ran"
    anchor = fake_trusted_opencode(tmp_path / "trusted-opencode", trusted_sentinel)
    pin_trusted_opencode(ns, monkeypatch, anchor)
    run_dir = tmp_path / "state" / "run"
    monkeypatch.setenv("OPENCODE_BIN", str(planted))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    returncode = opencode_wrapper_main(ns, monkeypatch, repo, run_dir)
    payload = json.loads(capsys.readouterr().out)
    launched = json.loads((run_dir / "opencode-command.json").read_text())

    assert returncode == 0
    assert payload["ok"] is True
    assert not planted_sentinel.exists()
    assert trusted_sentinel.read_text() == "ran"
    assert launched[0] not in (str(planted), "opencode", str(anchor))
    assert Path(launched[0]).read_bytes() == anchor.read_bytes()
    assert stat.S_IMODE(Path(launched[0]).stat().st_mode) == 0o500


def test_production_opencode_wrapper_blocks_planted_binary_before_mounting_private_auth(monkeypatch, capsys, tmp_path: Path):
    repo = tmp_path / "repo-planted-opencode"
    repo.mkdir()
    init_repo(repo)
    ns = runpy.run_path(str(PRODUCTION_OPENCODE))
    monkeypatch.setitem(ns["main"].__globals__, "production_dispatch_blocker", lambda: None)
    planted_sentinel = tmp_path / "planted-ran"
    planted = tmp_path / "planted-opencode"
    planted.write_text(f"#!/bin/sh\ntouch {planted_sentinel}\n")
    planted.chmod(0o755)
    anchor = fake_trusted_opencode(tmp_path / "trusted-opencode", tmp_path / "trusted-ran")
    pin_trusted_opencode(ns, monkeypatch, anchor)
    home = tmp_path / "home"
    auth = home / ".local" / "share" / "opencode" / "auth.json"
    auth.parent.mkdir(parents=True)
    auth.write_text('{"secret":"must-not-mount"}\n')
    monkeypatch.setenv("HOME", str(home))
    run_dir = tmp_path / "state" / "run"

    returncode = opencode_wrapper_main(ns, monkeypatch, repo, run_dir, "--opencode-bin", str(planted))
    payload = json.loads(capsys.readouterr().out)

    assert returncode == 2
    assert payload["ok"] is False
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["opencode_executable_integrity_failed"]
    assert not planted_sentinel.exists()
    assert not (run_dir / "opencode-home").exists()
    assert json.loads((run_dir / "opencode-result.json").read_text())["blockers"] == ["opencode_executable_integrity_failed"]


def test_opencode_private_home_copies_regular_auth_and_rejects_symlink(monkeypatch, tmp_path: Path):
    home = tmp_path / "home"
    auth_dir = home / ".local" / "share" / "opencode"
    auth_dir.mkdir(parents=True)
    auth = auth_dir / "auth.json"
    auth.write_text('{"provider":"fake"}\n')
    monkeypatch.setenv("HOME", str(home))
    ns = runpy.run_path(str(OPENCODE))

    private_home, private_data, private_config = ns["prepare_private_opencode_home"](tmp_path / "regular-run")

    copied = private_data / "opencode" / "auth.json"
    assert copied.read_text() == '{"provider":"fake"}\n'
    assert copied.stat().st_mode & 0o777 == 0o600
    assert (private_config / "opencode" / "opencode.json").stat().st_mode & 0o777 == 0o600
    assert private_home.is_dir()

    auth.unlink()
    secret = tmp_path / "secret.json"
    secret.write_text('{"provider":"secret"}\n')
    auth.symlink_to(secret)
    _, symlink_data, _ = ns["prepare_private_opencode_home"](tmp_path / "symlink-run")

    assert not (symlink_data / "opencode" / "auth.json").exists()


def test_custom_agent_draft_modifies_scoped_file_and_needs_review(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"

    cp, data = run_draft(
        "--plugin-root", str(plugin),
        "--repo", str(repo),
        "--state-dir", str(state),
        "--agent", "custom",
        "--agent-cmd", "python3 - <<'PY'\nfrom pathlib import Path\nPath('src/app.txt').write_text('draft\\n')\nprint('changed')\nPY",
        "--prompt", "change src/app.txt",
        "--scope-include", "src/**",
        "--verifier", "check=test -f src/app.txt",
    )

    assert cp.returncode == 0
    assert data["ok"] is True
    assert data["status"] == "needs_busdriver_review"
    assert data["postflight"]["changed_files"] == ["src/app.txt"]
    assert data["decision"]["agent_implementation_draft_allowed"] is True
    assert data["decision"]["commit_allowed"] is False
    assert sh(["git", "status", "--short"], cwd=repo).stdout.strip() == "M src/app.txt"


def test_agent_cmd_without_agent_uses_test_harness_pi_and_requires_artifact(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"

    cp, data = run_draft(
        "--plugin-root", str(plugin),
        "--repo", str(repo),
        "--state-dir", str(state),
        "--agent-cmd", "python3 - <<'PY'\nfrom pathlib import Path\nPath('src/app.txt').write_text('implicit-custom\\n')\nPY",
        "--prompt", "change src/app.txt",
        "--scope-include", "src/**",
    )

    assert cp.returncode == 0
    assert data["agent"] == "pi"
    assert data["ok"] is True
    assert data["status"] == "needs_busdriver_review"
    assert data["pi_artifact"]["worker"] == "pi"
    assert data["pi_artifact"]["authority"]["finalization_allowed"] is False
    assert (repo / "src" / "app.txt").read_text() == "implicit-custom\n"



def test_agent_draft_blocks_git_commit_via_path_guard(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"

    cp, data = run_draft(
        "--plugin-root", str(plugin),
        "--repo", str(repo),
        "--state-dir", str(state),
        "--agent", "custom",
        "--agent-cmd", "git commit --allow-empty -m nope",
        "--prompt", "try to commit",
        check=False,
    )

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["agent_result"]["returncode"] == 2
    adapter_result = json.loads(data["agent_result"]["stdout_tail"])
    assert adapter_result["pi_returncode"] == 126
    assert "blocked git commit" in adapter_result["stderr_tail"]
    assert sh(["git", "rev-list", "--count", "HEAD"], cwd=repo).stdout.strip() == "1"


def test_agent_draft_blocks_out_of_scope_change(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"

    cp, data = run_draft(
        "--plugin-root", str(plugin),
        "--repo", str(repo),
        "--state-dir", str(state),
        "--agent", "custom",
        "--agent-cmd", "python3 - <<'PY'\nfrom pathlib import Path\nPath('README.md').write_text('oops\\n')\nPY",
        "--prompt", "change README",
        "--scope-include", "src/**",
        check=False,
    )

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    scope = next(c for c in data["postflight"]["checks"] if c["name"] == "changed_files_within_scope")
    assert scope["ok"] is False
    assert "README.md" in scope["detail"]["out_of_scope"]


def test_agent_draft_exports_busdriver_env(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"

    cp, data = run_draft(
        "--plugin-root", str(plugin),
        "--repo", str(repo),
        "--state-dir", str(state),
        "--agent", "custom",
        "--agent-cmd", "python3 - <<'PY'\nimport os\nfrom pathlib import Path\nPath('src/env.txt').write_text(os.environ['BUSDRIVER_PLUGIN_ROOT'] + '\\n' + os.environ['BUSDRIVER_STATE_DIR'] + '\\n')\nPY",
        "--prompt", "write env",
        "--scope-include", "src/env.txt",
        "--verifier", f"env=grep -qx {plugin} src/env.txt && grep -qx .claude src/env.txt",
    )

    assert cp.returncode == 0
    assert data["ok"] is True
    assert (repo / "src" / "env.txt").read_text().splitlines() == [str(plugin), ".claude"]


def test_agent_draft_respects_existing_lock(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"

    lock_cp = sh([sys.executable, str(LOCK), "acquire", "--repo", str(repo), "--operation", "agent-draft", "--state-dir", str(state)])
    lock = json.loads(lock_cp.stdout)
    assert lock["acquired"] is True

    cp, data = run_draft(
        "--plugin-root", str(plugin),
        "--repo", str(repo),
        "--state-dir", str(state),
        "--agent", "noop",
        "--prompt", "noop",
        check=False,
    )

    assert cp.returncode == 2
    assert data["status"] == "blocked"
    assert data["reason"] == "lock_not_acquired"

    sh([sys.executable, str(LOCK), "release", "--repo", str(repo), "--operation", "agent-draft", "--state-dir", str(state), "--token", lock["token"]])


def test_opencode_adapter_fake_smoke_preserves_authority_false(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake_opencode = tmp_path / "fake-opencode"
    fake_opencode.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "repo = Path(os.environ['OPENCODE_BD_REPO'])\n"
        "Path(repo / 'src' / 'app.txt').write_text('opencode-draft\\n')\n"
        "payload = {\n"
        "  'schema': 'opencode-busdriver-result/v0',\n"
        "  'worker': 'opencode',\n"
        "  'mode': 'generic_gated_draft',\n"
        "  'ok': True,\n"
        "  'status': 'needs_busdriver_review',\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'finalization_allowed': False,\n"
        "  'commit_allowed': False,\n"
        "  'push_allowed': False,\n"
        "  'pr_allowed': False,\n"
        "  'merge_allowed': False,\n"
        "  'marker_write_allowed': False,\n"
        "  'deploy_allowed': False,\n"
        "  'release_allowed': False,\n"
        "  'publish_allowed': False,\n"
        "  'authority': {\n"
        "    'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False,\n"
        "    'merge_allowed': False, 'marker_write_allowed': False, 'deploy_allowed': False,\n"
        "    'release_allowed': False, 'publish_allowed': False, 'finalization_allowed': False,\n"
        "  },\n"
        "  'summary': 'draft complete',\n"
        "  'changed_files': ['src/app.txt'],\n"
        "  'limitations': [],\n"
        "  'files_changed': ['src/app.txt'],\n"
        "}\n"
        "Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text(json.dumps(payload) + '\\n')\n"
    )
    fake_opencode.chmod(0o755)

    cp, data, run_dir = run_opencode_adapter(
        repo, plugin, state, fake_opencode, "change src/app.txt", "src/**"
    )

    assert cp.returncode == 0
    assert data["ok"] is True
    assert data["worker"] == "opencode"
    assert data["status"] == "needs_busdriver_review"
    assert data["not_busdriver_native_claude_runtime"] is True
    assert all(value is False for value in data["authority"].values())
    assert data["commit_allowed"] is False
    assert data["marker_write_allowed"] is False
    assert data["repo"] == str(repo)
    assert data["artifacts"] == [str(run_dir / "opencode-result.json")]
    assert data["summary"] == "draft complete"
    assert data["changed_files"] == ["src/app.txt"]

    adapter_prompt = (run_dir / "opencode-adapter-prompt.txt").read_text()
    assert "Do not commit, push, create PRs, merge, deploy, release, publish, or write Busdriver markers." in adapter_prompt
    assert "Allowed include scopes: ['src/**']" in adapter_prompt
    assert "every authority flag false" in adapter_prompt




def test_opencode_adapter_does_not_forward_ambient_secret_environment(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake_opencode = tmp_path / "fake-opencode"
    fake_opencode.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "run_dir = Path(os.environ['OPENCODE_BD_RUN_DIR'])\n"
        "seen = {key: os.environ.get(key) for key in ['PATH', 'HOME', 'OPENCODE_BD_REPO', 'OPENCODE_BD_RESULT_FILE', 'BUSDRIVER_STATE_DIR', 'BUSDRIVER_PLUGIN_ROOT', 'CLAUDE_PLUGIN_ROOT', 'OPENAI_API_KEY', 'GITHUB_TOKEN', 'CUSTOM_SECRET_TOKEN', 'LC_SECRET_TOKEN']}\n"
        "(run_dir / 'seen-env.json').write_text(json.dumps(seen, sort_keys=True) + '\\n')\n"
        "payload = {\n"
        "  'schema': 'opencode-busdriver-result/v0',\n"
        "  'worker': 'opencode',\n"
        "  'mode': 'generic_gated_draft',\n"
        "  'ok': True,\n"
        "  'status': 'needs_busdriver_review',\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'finalization_allowed': False, 'commit_allowed': False, 'push_allowed': False,\n"
        "  'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False,\n"
        "  'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False,\n"
        "  'authority': {'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False, 'finalization_allowed': False},\n"
        "  'files_changed': [],\n"
        "  'summary': 'env checked',\n"
        "}\n"
        "Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text(json.dumps(payload) + '\\n')\n"
    )
    fake_opencode.chmod(0o755)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-ambient")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret_ambient")
    monkeypatch.setenv("CUSTOM_SECRET_TOKEN", "custom-secret-ambient")
    monkeypatch.setenv("LC_SECRET_TOKEN", "locale-looking-secret")
    monkeypatch.setenv("BUSDRIVER_PLUGIN_ROOT", str(plugin))
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin))

    cp, data, run_dir = run_opencode_adapter(
        repo, plugin, state, fake_opencode, "inspect env"
    )

    assert cp.returncode == 0
    assert data["ok"] is True
    seen = json.loads((run_dir / "seen-env.json").read_text())
    assert seen["OPENCODE_BD_REPO"] == str(repo)
    assert seen["OPENCODE_BD_RESULT_FILE"] == str(run_dir / "opencode-result.json")
    assert seen["BUSDRIVER_STATE_DIR"] == ".opencode"
    assert seen["BUSDRIVER_PLUGIN_ROOT"] == str(plugin)
    assert seen["CLAUDE_PLUGIN_ROOT"] == str(plugin)
    assert seen["PATH"]
    assert seen["OPENAI_API_KEY"] is None
    assert seen["GITHUB_TOKEN"] is None
    assert seen["CUSTOM_SECRET_TOKEN"] is None
    assert seen["LC_SECRET_TOKEN"] is None


def test_opencode_adapter_rejects_unexpected_authority_like_fields(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake_opencode = tmp_path / "fake-opencode"
    fake_opencode.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "payload = {\n"
        "  'schema': 'opencode-busdriver-result/v0',\n"
        "  'worker': 'opencode',\n"
        "  'mode': 'generic_gated_draft',\n"
        "  'ok': True,\n"
        "  'status': 'needs_busdriver_review',\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'finalization_allowed': False, 'commit_allowed': False, 'push_allowed': False,\n"
        "  'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False,\n"
        "  'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False,\n"
        "  'dispatch_allowed': True,\n"
        "  'authority': {'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False, 'finalization_allowed': False},\n"
        "  'files_changed': [],\n"
        "}\n"
        "Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text(json.dumps(payload) + '\\n')\n"
    )
    fake_opencode.chmod(0o755)

    cp, data, _run_dir = run_opencode_adapter(
        repo, plugin, state, fake_opencode, "do nothing", check=False
    )

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["blockers"] == ["unexpected_result_keys"]
    assert all(value is False for value in data["authority"].values())


def test_opencode_adapter_rejects_blocked_result_with_ok_true(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake_opencode = tmp_path / "fake-opencode"
    fake_opencode.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "payload = {\n"
        "  'schema': 'opencode-busdriver-result/v0',\n"
        "  'worker': 'opencode',\n"
        "  'mode': 'generic_gated_draft',\n"
        "  'ok': True,\n"
        "  'status': 'blocked',\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'finalization_allowed': False, 'commit_allowed': False, 'push_allowed': False,\n"
        "  'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False,\n"
        "  'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False,\n"
        "  'authority': {'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False, 'finalization_allowed': False},\n"
        "  'files_changed': [],\n"
        "  'blockers': ['fake blocked'],\n"
        "}\n"
        "Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text(json.dumps(payload) + '\\n')\n"
    )
    fake_opencode.chmod(0o755)

    cp, data, _run_dir = run_opencode_adapter(
        repo, plugin, state, fake_opencode, "do nothing", check=False
    )

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["blockers"] == ["blocked_requires_ok_false"]


def test_opencode_adapter_rejects_nested_extra_authority_fields(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake_opencode = tmp_path / "fake-opencode"
    fake_opencode.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "payload = {\n"
        "  'schema': 'opencode-busdriver-result/v0',\n"
        "  'worker': 'opencode',\n"
        "  'mode': 'generic_gated_draft',\n"
        "  'ok': True,\n"
        "  'status': 'needs_busdriver_review',\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'finalization_allowed': False, 'commit_allowed': False, 'push_allowed': False,\n"
        "  'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False,\n"
        "  'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False,\n"
        "  'authority': {'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False, 'finalization_allowed': False, 'dispatch_allowed': True},\n"
        "  'files_changed': [],\n"
        "}\n"
        "Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text(json.dumps(payload) + '\\n')\n"
    )
    fake_opencode.chmod(0o755)

    cp, data, _run_dir = run_opencode_adapter(
        repo, plugin, state, fake_opencode, "do nothing", check=False
    )

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["blockers"] == ["authority_flags_invalid"]


def test_opencode_wrapper_blocks_when_not_inside_agent_draft_guard(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("do nothing\n")
    run_dir = tmp_path / "run"

    cp = subprocess.run(
        [
            sys.executable,
            str(OPENCODE),
            "--repo",
            str(repo),
            "--prompt-file",
            str(prompt),
            "--run-dir",
            str(run_dir),
            "--opencode-bin",
            "definitely-not-run",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode == 2
    data = json.loads(cp.stdout)
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["blockers"] == ["missing_agent_draft_guard"]
    assert (run_dir / "opencode-result.json").exists()


def test_production_opencode_blocks_valid_guard_before_worker_launch(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("do nothing\n")
    run_dir = tmp_path / "run"
    sentinel = tmp_path / "worker-launched"
    fake_opencode = tmp_path / "fake-opencode"
    fake_opencode.write_text(f"#!/bin/sh\nprintf launched > {sentinel}\n")
    fake_opencode.chmod(0o755)
    guard_bin = tmp_path / "guard-bin"
    guard_bin.mkdir()
    real_git = shutil.which("git")
    assert real_git
    git_helper = guard_bin / "git"
    git_helper.write_text(f'#!/bin/sh\nexec "{real_git}" "$@"\n')
    git_helper.chmod(0o700)
    gh_helper = guard_bin / "gh"
    gh_helper.write_text("#!/bin/sh\nexit 126\n")
    gh_helper.chmod(0o700)
    env = os.environ.copy()
    env.update({
        "HERMES_AGENT_DRAFT_GUARDED": "1",
        "HERMES_AGENT_DRAFT_GUARD_BIN": str(guard_bin),
        "PATH": str(guard_bin) + os.pathsep + env.get("PATH", ""),
    })

    cp = subprocess.run(
        [
            sys.executable,
            str(PRODUCTION_OPENCODE),
            "--repo", str(repo),
            "--prompt-file", str(prompt),
            "--run-dir", str(run_dir),
            "--opencode-bin", str(fake_opencode),
        ],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode == 2
    data = json.loads(cp.stdout)
    assert data["blockers"] == ["agent_containment_and_credential_broker_unavailable"]
    assert not sentinel.exists()
    assert not run_dir.exists()


def test_opencode_adapter_redacts_untrusted_output_and_invalid_payload(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake_opencode = tmp_path / "fake-opencode"
    secret = "ghp_" + "A" * 36
    api_secret = "plain-secret-value-1234567890"
    fake_opencode.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        f"secret = {secret!r}\n"
        f"api_secret = {api_secret!r}\n"
        "print('Authorization: Bearer ' + secret)\n"
        "sys.stderr.write('api_key=' + api_secret + '\\n')\n"
        "payload = {\n"
        "  'schema': 'opencode-busdriver-result/v0',\n"
        "  'worker': 'opencode',\n"
        "  'mode': 'generic_gated_draft',\n"
        "  'ok': True,\n"
        "  'status': 'needs_busdriver_review',\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'finalization_allowed': False, 'commit_allowed': False, 'push_allowed': False,\n"
        "  'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False,\n"
        "  'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False,\n"
        "  'authority': {'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False, 'finalization_allowed': False},\n"
        "  'files_changed': [],\n"
        "  'unexpected_secret_field': secret,\n"
        "}\n"
        "Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text(json.dumps(payload) + '\\n')\n"
    )
    fake_opencode.chmod(0o755)

    cp, data, run_dir = run_opencode_adapter(
        repo, plugin, state, fake_opencode, "do nothing", check=False
    )

    assert cp.returncode == 2
    serialized = json.dumps(data, sort_keys=True)
    assert secret not in serialized
    assert api_secret not in serialized
    assert data["stdout_tail"].strip().endswith("[REDACTED]")
    assert data["stderr_tail"].strip() == "api_key=[REDACTED]"
    artifact = run_dir / "opencode-result.json"
    assert secret not in artifact.read_text()
    assert api_secret not in artifact.read_text()
    keys = data["observed_result_keys"]
    assert "unexpected_secret_field" in keys
    assert all(secret not in key and api_secret not in key for key in keys)
    assert secret not in (run_dir / "opencode.stdout").read_text()
    assert api_secret not in (run_dir / "opencode.stderr").read_text()


def test_opencode_adapter_redacts_success_payload_allowed_fields(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake_opencode = tmp_path / "fake-opencode"
    secret = "sk-" + "B" * 32
    fake_opencode.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        f"secret = {secret!r}\n"
        "payload = {\n"
        "  'schema': 'opencode-busdriver-result/v0',\n"
        "  'worker': 'opencode',\n"
        "  'mode': 'generic_gated_draft',\n"
        "  'ok': True,\n"
        "  'status': 'needs_busdriver_review',\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'finalization_allowed': False, 'commit_allowed': False, 'push_allowed': False,\n"
        "  'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False,\n"
        "  'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False,\n"
        "  'authority': {'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False, 'finalization_allowed': False},\n"
        "  'files_changed': [],\n"
        "  'summary': 'used token=' + secret,\n"
        "  'event_log': ['--token ' + secret],\n"
        "  'tests_run': [{'name': 'smoke', 'command': 'tool --token ' + secret, 'ok': True}],\n"
        "}\n"
        "Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text(json.dumps(payload) + '\\n')\n"
    )
    fake_opencode.chmod(0o755)

    cp, data, _run_dir = run_opencode_adapter(
        repo, plugin, state, fake_opencode, "do nothing"
    )

    assert cp.returncode == 0
    serialized = json.dumps(data, sort_keys=True)
    assert secret not in serialized
    assert "token=[REDACTED]" in serialized
    assert "--token [REDACTED]" in serialized


def test_opencode_adapter_rejects_schema_allowed_invalid_shapes(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake_opencode = tmp_path / "fake-opencode"
    fake_opencode.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "payload = {\n"
        "  'schema': 'opencode-busdriver-result/v0',\n"
        "  'worker': 'opencode',\n"
        "  'mode': 'generic_gated_draft',\n"
        "  'ok': True,\n"
        "  'status': 'needs_busdriver_review',\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'finalization_allowed': False, 'commit_allowed': False, 'push_allowed': False,\n"
        "  'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False,\n"
        "  'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False,\n"
        "  'authority': {'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False, 'finalization_allowed': False},\n"
        "  'files_changed': [],\n"
        "  'tests_run': 'bad',\n"
        "}\n"
        "Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text(json.dumps(payload) + '\\n')\n"
    )
    fake_opencode.chmod(0o755)

    cp, data, _run_dir = run_opencode_adapter(
        repo, plugin, state, fake_opencode, "do nothing", check=False
    )

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["blockers"] == ["tests_run_invalid"]


def test_opencode_adapter_rejects_invalid_mode(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake_opencode = tmp_path / "fake-opencode"
    fake_opencode.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "payload = {\n"
        "  'schema': 'opencode-busdriver-result/v0',\n"
        "  'worker': 'opencode',\n"
        "  'mode': 'finalization',\n"
        "  'ok': True,\n"
        "  'status': 'needs_busdriver_review',\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'finalization_allowed': False, 'commit_allowed': False, 'push_allowed': False,\n"
        "  'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False,\n"
        "  'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False,\n"
        "  'authority': {'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False, 'finalization_allowed': False},\n"
        "  'files_changed': [],\n"
        "}\n"
        "Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text(json.dumps(payload) + '\\n')\n"
    )
    fake_opencode.chmod(0o755)

    cp, data, _run_dir = run_opencode_adapter(
        repo, plugin, state, fake_opencode, "do nothing", check=False
    )

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["blockers"] == ["mode_invalid"]


def test_opencode_adapter_rejects_out_of_scope_change(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake = tmp_path / "fake-opencode"
    payload = valid_opencode_payload(["README.md"])
    write_fake_opencode(
        fake,
        "import json, os\n"
        "from pathlib import Path\n"
        "repo = Path(os.environ['OPENCODE_BD_REPO'])\n"
        "(repo / 'README.md').write_text('outside\\n')\n"
        f"payload = {payload!r}\n"
        "Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text(json.dumps(payload) + '\\n')\n",
    )

    cp, data, _ = run_opencode_adapter(repo, plugin, state, fake, "change README", "src/**", check=False)

    assert cp.returncode == 2
    assert data["status"] == "blocked"
    assert data["blockers"] == ["scope_violation"]
    assert data["files_changed"] == ["README.md"]


def test_opencode_scope_single_star_does_not_cross_path_segment():
    ns = runpy.run_path(str(OPENCODE))

    assert ns["scope_violations"](
        ["src/direct.txt", "src/nested/blocked.txt"], ["src/*.txt"], []
    ) == ["src/nested/blocked.txt"]


def test_opencode_scope_double_star_may_cross_path_segment():
    ns = runpy.run_path(str(OPENCODE))

    assert ns["scope_violations"](
        ["src/direct.txt", "src/nested/allowed.txt"], ["src/**/*.txt"], []
    ) == []


def test_opencode_adapter_rejects_result_file_change_mismatch(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake = tmp_path / "fake-opencode"
    payload = valid_opencode_payload([])
    write_fake_opencode(
        fake,
        "import json, os\n"
        "from pathlib import Path\n"
        "repo = Path(os.environ['OPENCODE_BD_REPO'])\n"
        "(repo / 'src' / 'app.txt').write_text('changed\\n')\n"
        f"payload = {payload!r}\n"
        "Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text(json.dumps(payload) + '\\n')\n",
    )

    cp, data, _ = run_opencode_adapter(repo, plugin, state, fake, "change src", "src/**", check=False)

    assert cp.returncode == 2
    assert data["blockers"] == ["files_changed_mismatch"]
    assert data["files_changed"] == ["src/app.txt"]


def test_opencode_adapter_rejects_oversized_result(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake = tmp_path / "fake-opencode"
    write_fake_opencode(
        fake,
        "import os\n"
        "from pathlib import Path\n"
        "Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text('{' + 'x' * 1048577)\n",
    )

    cp, data, _ = run_opencode_adapter(repo, plugin, state, fake, "do nothing", check=False)

    assert cp.returncode == 2
    assert data["blockers"] == ["opencode_result_too_large"]


def test_opencode_adapter_prompt_contains_canonical_json_template(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake = tmp_path / "fake-opencode"
    payload = valid_opencode_payload([])
    write_fake_opencode(
        fake,
        "import json, os\n"
        "from pathlib import Path\n"
        f"payload = {payload!r}\n"
        "Path(os.environ['OPENCODE_BD_RESULT_FILE']).write_text(json.dumps(payload) + '\\n')\n",
    )

    _, _, run_dir = run_opencode_adapter(repo, plugin, state, fake, "do nothing")
    prompt = (run_dir / "opencode-adapter-prompt.txt").read_text()

    assert '"schema": "opencode-busdriver-result/v0"' in prompt
    assert '"authority": {' in prompt
    assert '"finalization_allowed": false' in prompt
    assert '"files_changed": []' in prompt


def test_opencode_adapter_fails_closed_for_missing_and_malformed_results(tmp_path: Path):
    plugin = fake_busdriver(tmp_path)
    cases = (
        ("missing", "pass\n", "opencode_result_missing"),
        (
            "malformed",
            "import os\nfrom pathlib import Path\nPath(os.environ['OPENCODE_BD_RESULT_FILE']).write_text('{bad')\n",
            "opencode_result_parse_failed",
        ),
    )
    for name, body, blocker in cases:
        repo = tmp_path / f"repo-{name}"
        repo.mkdir()
        init_repo(repo)
        fake = tmp_path / f"fake-{name}"
        write_fake_opencode(fake, body)
        cp, data, _ = run_opencode_adapter(repo, plugin, tmp_path / f"state-{name}", fake, "do nothing", check=False)
        assert cp.returncode == 2
        assert data["blockers"] == [blocker]
        assert all(value is False for value in data["authority"].values())


def test_opencode_adapter_timeout_is_structured_and_non_authoritative(tmp_path: Path):
    repo = tmp_path / "repo-timeout"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    fake = tmp_path / "fake-timeout"
    write_fake_opencode(fake, "import time\ntime.sleep(5)\n")

    cp, data, _ = run_opencode_adapter(
        repo,
        plugin,
        tmp_path / "state-timeout",
        fake,
        "do nothing",
        check=False,
        timeout=1,
    )

    assert cp.returncode == 2
    assert data["blockers"] == ["opencode_timeout"]
    assert data["returncode"] == 124
    assert all(value is False for value in data["authority"].values())


def test_production_agent_draft_blocks_before_opencode_executable_dispatch(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake = tmp_path / "fake-opencode"
    sentinel = tmp_path / "fake-opencode-launched"
    write_fake_opencode(fake, f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('launched')\n")

    cp = subprocess.run(
        [
            sys.executable,
            str(PRODUCTION_DRAFT),
            "--plugin-root", str(plugin),
            "--repo", str(repo),
            "--state-dir", str(state),
            "--agent", "opencode",
            "--opencode-bin", str(fake),
            "--prompt", "change src/app.txt",
            "--scope-include", "src/**",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode == 2
    data = json.loads(cp.stdout)
    assert data["status"] == "blocked"
    assert data["agent"] == "opencode"
    assert data["reason"] == "agent_containment_and_credential_broker_unavailable"
    assert data["blockers"] == ["agent_containment_and_credential_broker_unavailable"]
    assert "preflight" not in data
    assert not sentinel.exists()
    assert not state.exists()
    assert sh(["git", "status", "--short"], cwd=repo).stdout == ""


@pytest.mark.parametrize("agent", ["pi", "opencode"])
def test_production_agent_draft_policy_blocker_precedes_repo_home_and_state_access(tmp_path: Path, agent: str):
    repo = tmp_path / "repo-must-not-be-read"
    plugin = tmp_path / "plugin-must-not-be-read"
    home = tmp_path / "home-must-not-be-touched"
    state = home / ".hermes" / "busdriver-relay"
    env = os.environ.copy()
    env["HOME"] = str(home)

    cp = subprocess.run(
        [
            sys.executable,
            str(PRODUCTION_DRAFT),
            "--plugin-root", str(plugin),
            "--repo", str(repo),
            "--state-dir", str(state),
            "--agent", agent,
            "--prompt", "must not be loaded",
            "--scope-include", "src/**",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert cp.returncode == 2
    data = json.loads(cp.stdout)
    assert data["status"] == "blocked"
    assert data["reason"] == "agent_containment_and_credential_broker_unavailable"
    assert data["blockers"] == ["agent_containment_and_credential_broker_unavailable"]
    assert all(value is False for value in data["authority"].values())
    assert not repo.exists()
    assert not plugin.exists()
    assert not home.exists()
    assert not state.exists()


def test_production_agent_draft_policy_blocker_calls_no_access_or_dispatch_prerequisite(monkeypatch, capsys):
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    globals_ = ns["main"].__globals__

    def forbidden(name: str):
        def fail(*_args, **_kwargs):
            pytest.fail(f"production blocker reached forbidden prerequisite:{name}")
        return fail

    for name in (
        "git_root",
        "state_root",
        "materialize_trusted_lock",
        "acquire_lock",
        "allocate_run_dir",
        "materialize_trusted_gate",
        "load_prompt",
        "build_guard_bin",
        "gate_preflight",
        "agent_command",
        "run_worker",
        "gate_postflight",
        "release_lock",
        "persist_final_report",
    ):
        monkeypatch.setitem(globals_, name, forbidden(name))
    monkeypatch.setattr(sys, "argv", [
        str(PRODUCTION_DRAFT),
        "--plugin-root", "/must/not/be/read/plugin",
        "--repo", "/must/not/be/read/repo",
        "--agent", "pi",
        "--prompt-file", "/must/not/be/read/prompt",
        "--state-dir", "/must/not/be/read/state",
    ])

    rc = ns["main"]()
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["reason"] == "agent_containment_and_credential_broker_unavailable"
    assert data["repo"] is None
    assert all(value is False for value in data["authority"].values())


def test_production_losing_lock_creates_no_agent_inputs(monkeypatch, capsys, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    repo = tmp_path / "repo-loser"
    repo.mkdir()
    init_repo(repo)
    state = tmp_path / "state-loser"
    plugin = fake_busdriver(tmp_path / "plugin-loser")
    globals_ = ns["main"].__globals__
    monkeypatch.setitem(globals_, "production_dispatch_blocker", lambda: "")
    monkeypatch.setitem(globals_, "git_root", lambda _repo: repo)
    monkeypatch.setitem(globals_, "acquire_lock", lambda _args: {"acquired": False, "reason": "lock-active"})
    monkeypatch.setattr(sys, "argv", [
        str(PRODUCTION_DRAFT), "--plugin-root", str(plugin), "--repo", str(repo),
        "--state-dir", str(state), "--agent", "noop", "--prompt", "noop",
    ])

    rc = ns["main"]()
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["reason"] == "lock_not_acquired"
    assert not (state / "agent-runs").exists()


def test_worker_timeout_kills_term_ignoring_grandchild(tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    delayed = tmp_path / "delayed-write"
    child_pid = tmp_path / "child-pid"
    child_ready = tmp_path / "child-ready"
    child = (
        "import os,signal,time; from pathlib import Path; "
        "devnull=os.open(os.devnull, os.O_WRONLY); os.dup2(devnull, 1); os.dup2(devnull, 2); "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"Path({str(child_ready)!r}).write_text('ready'); "
        f"time.sleep(5); Path({str(delayed)!r}).write_text('survived')"
    )
    parent = (
        "import subprocess,sys,time; from pathlib import Path; "
        f"p=subprocess.Popen([sys.executable, '-c', {child!r}]); "
        f"Path({str(child_pid)!r}).write_text(str(p.pid)); "
        f"deadline=time.monotonic()+2; ready=Path({str(child_ready)!r}); "
        "\nwhile not ready.exists() and time.monotonic() < deadline: time.sleep(0.01)\n"
        "time.sleep(10)"
    )

    result = ns["run_worker"](
        [sys.executable, "-c", parent], cwd=tmp_path, env=os.environ.copy(), timeout=3, termination_grace=0.2
    )

    assert result.returncode == 124
    assert child_ready.exists(), "grandchild never installed its SIGTERM-ignore handler"
    pid = int(child_pid.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert not delayed.exists()


def test_worker_success_fails_closed_and_drains_lingering_grandchild(tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    delayed = tmp_path / "late-success-write"
    child_pid = tmp_path / "success-child-pid"
    child_ready = tmp_path / "success-child-ready"
    child = (
        "import os,signal,time; from pathlib import Path; "
        "devnull=os.open(os.devnull, os.O_WRONLY); os.dup2(devnull, 1); os.dup2(devnull, 2); "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"Path({str(child_ready)!r}).write_text('ready'); "
        f"time.sleep(2); Path({str(delayed)!r}).write_text('escaped')"
    )
    parent = (
        "import subprocess,sys,time; from pathlib import Path; "
        f"p=subprocess.Popen([sys.executable, '-c', {child!r}]); "
        f"Path({str(child_pid)!r}).write_text(str(p.pid)); "
        f"deadline=time.monotonic()+2; ready=Path({str(child_ready)!r}); "
        "\nwhile not ready.exists() and time.monotonic() < deadline: time.sleep(0.01)\n"
        "raise SystemExit(0)"
    )

    result = ns["run_worker"](
        [sys.executable, "-c", parent], cwd=tmp_path, env=os.environ.copy(), timeout=3, termination_grace=0.2
    )

    assert child_ready.exists(), "grandchild did not become ready before the direct parent exited"
    assert result.returncode == 0
    assert "worker_descendants_outlived_parent" not in result.stderr
    pid = int(child_pid.read_text())
    deadline = time.monotonic() + 1.0
    while True:
        try:
            os.kill(pid, 0)
            alive = True
        except ProcessLookupError:
            alive = False
        if not alive:
            break
        if time.monotonic() >= deadline:
            raise AssertionError(f"grandchild {pid} survived worker cleanup")
        time.sleep(0.01)
    time.sleep(2.1)
    assert not delayed.exists()


@pytest.mark.parametrize("release_reason", ["not-found", "token-mismatch"])
def test_lock_release_failure_is_the_same_blocked_stdout_and_final_report(monkeypatch, capsys, tmp_path: Path, release_reason: str):
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    repo = tmp_path / "repo-release"
    repo.mkdir()
    state = tmp_path / "state-release"
    plugin = fake_busdriver(tmp_path / "plugin-release")
    globals_ = ns["main"].__globals__
    monkeypatch.setitem(globals_, "production_dispatch_blocker", lambda: "")
    monkeypatch.setitem(globals_, "git_root", lambda _repo: repo)
    monkeypatch.setitem(globals_, "materialize_trusted_lock", lambda _state: tmp_path / "trusted-lock")
    monkeypatch.setitem(globals_, "acquire_lock", lambda _args: {"acquired": True, "token": "token", "path": str(tmp_path / "lock")})
    monkeypatch.setitem(globals_, "materialize_trusted_gate", lambda run_dir: run_dir / "gate")
    monkeypatch.setitem(globals_, "build_guard_bin", lambda run_dir: run_dir)
    monkeypatch.setitem(globals_, "gate_preflight", lambda _args, _baseline: {"ok": True, "decision": {"agent_implementation_draft_allowed": True}})
    monkeypatch.setitem(globals_, "agent_command", lambda *_args: ["noop"])
    monkeypatch.setitem(globals_, "run_worker", lambda *_args, **_kwargs: subprocess.CompletedProcess(["noop"], 0, "", ""))
    monkeypatch.setitem(globals_, "gate_postflight", lambda _args, _baseline: {"ok": True, "decision": {}})
    monkeypatch.setitem(globals_, "release_lock", lambda *_args: {"released": False, "reason": release_reason})
    monkeypatch.setattr(globals_["shutil"], "rmtree", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sys, "argv", [
        str(PRODUCTION_DRAFT), "--plugin-root", str(plugin), "--repo", str(repo),
        "--state-dir", str(state), "--agent", "noop", "--prompt", "noop",
    ])

    rc = ns["main"]()
    stdout = json.loads(capsys.readouterr().out)
    artifact = json.loads(Path(stdout["final_report_path"]).read_text())

    assert rc != 0
    assert stdout == artifact
    assert stdout["ok"] is False
    assert stdout["status"] == "blocked"
    assert stdout["reason"] == "lock_release_failed"
    assert all(value is False for value in stdout["authority"].values())


def test_agent_executes_materialized_lock_bytes_after_source_replacement(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    source = tmp_path / "lock-source"
    trusted_bytes = b"#!/usr/bin/env python3\n# trusted\n"
    source.write_bytes(trusted_bytes)
    globals_ = ns["materialize_trusted_lock"].__globals__
    monkeypatch.setitem(globals_, "LOCK", source)
    monkeypatch.setitem(globals_, "TRUSTED_LOCK_SHA256", hashlib.sha256(trusted_bytes).hexdigest())
    trusted = ns["materialize_trusted_lock"](tmp_path / "state")
    source.write_text("raise SystemExit('mutable source executed')\n")
    commands = []

    def fake_run(cmd, **kwargs):
        commands.append(cmd)
        assert Path(cmd[2]).read_bytes() == trusted_bytes
        env = kwargs["env"]
        # The private-runtime handshake is gone in both directions: there is no `trusted-bin` of
        # copies to put at PATH head, and no flag for the helper to select it with, because the
        # lock helper re-derives git from its own frozen root-owned table. What a parent hands
        # down is a PATH of root-owned components only.
        assert "HERMES_BUSDRIVER_PRIVATE_RUNTIME" not in env
        assert not (trusted.parents[1] / "trusted-bin").exists()
        assert env["PATH"] == "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin"
        assert "/opt/homebrew" not in env["PATH"]
        for denied in ns["ENV_DENIED_FOR_TRUSTED_DISPATCH"]:
            assert denied not in env, denied
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"acquired": True, "token": "token", "path": str(tmp_path / "lock")}), "")

    monkeypatch.setitem(ns["acquire_lock"].__globals__, "run", fake_run)
    args = argparse.Namespace(
        trusted_lock_path=trusted, repo=str(tmp_path), lock_ttl_seconds=100, state_dir=str(tmp_path / "state")
    )
    acquired = ns["acquire_lock"](args)

    assert acquired["acquired"] is True
    assert commands[0][2] == str(trusted)


def test_final_report_write_failure_publishes_one_recoverable_blocked_envelope(monkeypatch, capsys, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    repo = tmp_path / "repo-artifact"
    repo.mkdir()
    state = tmp_path / "state-artifact"
    plugin = fake_busdriver(tmp_path / "plugin-artifact")
    globals_ = ns["main"].__globals__
    monkeypatch.setitem(globals_, "production_dispatch_blocker", lambda: "")
    monkeypatch.setitem(globals_, "git_root", lambda _repo: repo)
    monkeypatch.setitem(globals_, "materialize_trusted_lock", lambda _state: tmp_path / "trusted-lock")
    monkeypatch.setitem(globals_, "acquire_lock", lambda _args: {"acquired": True, "token": "token", "path": str(tmp_path / "lock")})
    monkeypatch.setitem(globals_, "materialize_trusted_gate", lambda run_dir: run_dir / "gate")
    monkeypatch.setitem(globals_, "build_guard_bin", lambda run_dir: run_dir)
    monkeypatch.setitem(globals_, "gate_preflight", lambda *_args: {"ok": True, "decision": {"agent_implementation_draft_allowed": True}})
    monkeypatch.setitem(globals_, "agent_command", lambda *_args: ["noop"])
    monkeypatch.setitem(globals_, "run_worker", lambda *_args, **_kwargs: subprocess.CompletedProcess(["noop"], 0, "", ""))
    monkeypatch.setitem(globals_, "gate_postflight", lambda *_args: {"ok": True, "decision": {}})
    monkeypatch.setitem(globals_, "release_lock", lambda *_args: {"released": True})
    monkeypatch.setattr(globals_["shutil"], "rmtree", lambda *_args, **_kwargs: None)
    original_persist = globals_["persist_final_report"]
    attempts = 0

    def fail_once(path, report):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("disk interrupted")
        original_persist(path, report)

    monkeypatch.setitem(globals_, "persist_final_report", fail_once)
    monkeypatch.setattr(sys, "argv", [
        str(PRODUCTION_DRAFT), "--plugin-root", str(plugin), "--repo", str(repo),
        "--state-dir", str(state), "--agent", "noop", "--prompt", "noop",
    ])

    rc = ns["main"]()
    stdout = json.loads(capsys.readouterr().out)
    artifact = json.loads(Path(stdout["final_report_path"]).read_text())

    assert rc == 1
    assert attempts == 2
    assert stdout == artifact
    assert stdout["ok"] is False
    assert stdout["reason"] == "final_report_write_failed"


def test_frozen_timestamp_concurrent_run_directories_are_unique_and_exclusive(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DRAFT))
    monkeypatch.setitem(ns["allocate_run_dir"].__globals__, "timestamp", lambda: "20260710T000000Z")
    directories = []
    threads = [threading.Thread(target=lambda: directories.append(ns["allocate_run_dir"](tmp_path, "noop"))) for _ in range(8)]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)

    assert len(directories) == len(set(directories)) == 8
    assert all(path.is_dir() for path in directories)


# --- v16-r21: opencode git helper structured OSError fail-closed ---

def test_opencode_git_output_raises_structured_error_on_launch_oserror(tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_OPENCODE))
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x\n")

    with pytest.raises(RuntimeError) as excinfo:
        ns["git_output"](not_a_dir, "rev-parse", "HEAD")

    assert "git_rev_parse_HEAD" in str(excinfo.value)


def test_opencode_repo_pointing_at_a_file_fails_closed_without_traceback(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("task\n")
    not_a_dir = tmp_path / "regular-file.txt"
    not_a_dir.write_text("x\n")

    cp = subprocess.run(
        [
            sys.executable,
            str(PRODUCTION_OPENCODE),
            "--repo",
            str(not_a_dir),
            "--prompt-file",
            str(prompt_file),
            "--run-dir",
            str(run_dir),
        ],
        text=True,
        capture_output=True,
    )

    assert "Traceback" not in cp.stderr
    assert cp.returncode != 0
