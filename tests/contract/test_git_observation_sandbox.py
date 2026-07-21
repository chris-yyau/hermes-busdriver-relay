"""r74: read-only Git observations are an OS-enforced no-exec/no-network boundary.

A finite `-c` denylist is not an execution boundary: repository attributes choose arbitrary
filter/diff driver names, signature programs are repo-configurable, submodules can start nested Git,
and promisor objects can trigger lazy network fetches.  Every production observer therefore builds
its Git argv through the same-shaped sandbox helper.  These regressions prove both the guard and the
hostile fixture rather than merely searching for reassuring constants.
"""
from __future__ import annotations

import os
import ast
import runpy
import subprocess
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
GIT = Path("/usr/bin/git")
OBSERVERS = (
    "hermes-busdriver-status",
    "hermes-busdriver-relay-brief",
    "hermes-busdriver-gate",
    "hermes-busdriver-delivery-status",
    "hermes-busdriver-litmus-status",
    "hermes-busdriver-lock",
)
STATUS_SCRIPT_OBSERVERS = (*OBSERVERS, "hermes-busdriver-deliver")
MODE_OBSERVER_SURFACES = {
    *(f"scripts/{name}" for name in STATUS_SCRIPT_OBSERVERS),
    "adapters/pi/busdriver-fs-broker.py",
}
PROGRAM_KEYS = {
    "core.fsmonitor",
    "core.hooksPath",
    "log.showSignature",
    "gpg.program",
    "gpg.ssh.program",
    "gpg.x509.program",
    "diff.external",
    "core.pager",
    "core.sshCommand",
    "core.editor",
    "core.askPass",
    "credential.helper",
    "protocol.allow",
    "protocol.file.allow",
    "protocol.ext.allow",
    "submodule.recurse",
    "fetch.recurseSubmodules",
    "status.showUntrackedFiles",
    "core.fileMode",
}


def discovered_observers() -> set[str]:
    """Derive every shipped observer from the production mechanism, independently of OBSERVERS."""
    staged = subprocess.run(
        ["git", "ls-files", "--stage", "scripts"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    found: set[str] = set()
    for row in staged:
        mode, _object_type, _object_id, relative = row.split(maxsplit=3)
        if mode != "100755":
            continue
        path = ROOT / relative
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        definitions = {
            node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        if "git_observation_argv" in definitions and "git_observation_argv" in calls:
            found.add(path.name)
    return found


def discovered_mode_observer_surfaces() -> set[str]:
    """Derive every production status pin tuple from tracked Python runtime surfaces."""
    staged = subprocess.run(
        ["git", "ls-files", "--stage", "scripts", "adapters/pi/busdriver-fs-broker.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    found: set[str] = set()
    for row in staged:
        mode, _object_type, _object_id, relative = row.split(maxsplit=3)
        if relative.startswith("scripts/") and mode != "100755":
            continue
        if relative == "adapters/pi/busdriver-fs-broker.py" and mode not in {"100644", "100755"}:
            continue
        path = ROOT / relative
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {target.id for target in targets if isinstance(target, ast.Name)}
            if not names.intersection({"GIT_OBSERVATION_INERT_CONFIG", "INERT_GIT_CONFIG"}):
                continue
            if node.value is None:
                continue
            try:
                pins = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            if isinstance(pins, tuple) and "status.showUntrackedFiles=all" in pins:
                found.add(relative)
    return found


def test_behavioral_observer_matrix_equals_the_ast_discovered_production_surface():
    assert set(OBSERVERS) == discovered_observers()


def test_mode_observer_matrix_equals_the_ast_discovered_production_surface():
    assert MODE_OBSERVER_SURFACES == discovered_mode_observer_surfaces()


def git_env(home: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_PAGER": "cat",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_ALLOW_PROTOCOL": "",
        "LC_ALL": "C",
    }


def init_repo(tmp_path: Path, *, hostile_key: str) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    repo.mkdir()
    home.mkdir()
    env = git_env(home)

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(GIT), *args], cwd=repo, env=env, capture_output=True, text=True, check=True)

    git("init", "-q", ".")
    git("config", "user.email", "t@example.test")
    git("config", "user.name", "t")
    (repo / "tracked.txt").write_text("x\n")
    if hostile_key.startswith("filter."):
        (repo / ".gitattributes").write_text("* filter=pwn\n")
    git("add", ".")
    git("commit", "-qm", "init")

    sentinel = tmp_path / "PWNED"
    payload = tmp_path / "payload.sh"
    payload.write_text(f"#!/bin/sh\ntouch '{sentinel}'\ncat\n")
    payload.chmod(0o700)
    git("config", hostile_key, str(payload))
    if hostile_key == "gpg.program":
        git("config", "log.showSignature", "true")
    (repo / "tracked.txt").write_text("changed\n")
    return repo, home, sentinel


def observer_namespace(script: str) -> dict[str, Any]:
    return runpy.run_path(str(ROOT / "scripts" / script))


def invoke_production_status(script: str, ns: dict[str, Any], repo: Path) -> tuple[int, str | bytes, str | bytes]:
    if script in {"hermes-busdriver-status", "hermes-busdriver-relay-brief"}:
        result = ns["run"](ns["git_argv"]("status", "--porcelain=v1"), cwd=repo)
    elif script == "hermes-busdriver-lock":
        result = ns["run"](ns["git_observation_argv"]("status", "--porcelain=v1"), cwd=repo)
    elif script == "hermes-busdriver-deliver":
        returncode, records, stderr = ns["git_status_records"](repo, "--untracked-files=all")
        rendered = "\n".join(f"{xy} {' '.join(paths)}" for xy, paths in records)
        return returncode, rendered, stderr
    else:
        result = ns["git"](repo, "status", "--porcelain=v1")
    if isinstance(result, dict):
        return result["returncode"], result["stdout_bytes"], result["stderr"]
    return result.returncode, result.stdout, result.stderr


def test_hostile_filter_control_really_executes_without_the_observation_sandbox(tmp_path: Path):
    repo, home, sentinel = init_repo(tmp_path, hostile_key="filter.pwn.clean")

    subprocess.run([str(GIT), "status", "--porcelain=v1"], cwd=repo, env=git_env(home), capture_output=True)

    assert sentinel.exists(), "hostile filter fixture is inert; the sandbox regressions would be vacuous"


@pytest.mark.parametrize("script", OBSERVERS)
def test_every_observer_denies_git_self_exec_alias_index_mutation(script: str, tmp_path: Path):
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    repo.mkdir()
    home.mkdir()
    environment = git_env(home)

    def git(*args: str, check: bool = True):
        return subprocess.run(
            [str(GIT), *args], cwd=repo, env=environment,
            capture_output=True, text=True, check=check,
        )

    git("init", "-q", ".")
    git("config", "user.email", "t@example.test")
    git("config", "user.name", "t")
    (repo / ".gitattributes").write_text("tracked.txt filter=pwn\n")
    (repo / "tracked.txt").write_text("committed\n")
    git("add", ".")
    git("commit", "-qm", "init")
    (repo / "tracked.txt").write_text("staged\n")
    git("add", "tracked.txt")
    index = repo / ".git" / "index"
    before = index.read_bytes()

    git_real = Path("/Library/Developer/CommandLineTools/usr/bin/git")
    assert git_real.is_file(), "host profile lacks the authenticated production Git target"
    reset_alias = tmp_path / "git-reset"
    reset_alias.symlink_to(git_real)
    git("config", "filter.pwn.clean", str(reset_alias))
    os.utime(repo / "tracked.txt", None)

    invoke_production_status(script, observer_namespace(script), repo)

    assert index.read_bytes() == before, f"{script}: observation let repo-selected git-reset rewrite the index"
    assert git("show", ":tracked.txt").stdout == "staged\n"


@pytest.mark.parametrize("script", OBSERVERS)
def test_every_observer_sandboxes_dynamic_clean_filters(script: str, tmp_path: Path):
    repo, home, sentinel = init_repo(tmp_path, hostile_key="filter.pwn.clean")
    ns = observer_namespace(script)

    argv = ns["git_observation_argv"]("status", "--porcelain=v1", "--ignore-submodules=all")
    cp = subprocess.run(argv, cwd=repo, env=git_env(home), capture_output=True, text=True)

    assert cp.returncode in (0, 1), cp.stderr
    assert not sentinel.exists(), f"{script}: repository-selected filter escaped the observation sandbox"


@pytest.mark.parametrize("script", OBSERVERS)
def test_every_observer_refuses_a_status_whose_filter_was_denied(script: str, tmp_path: Path):
    """Sandbox denial must not turn a real dirty file into an authoritative clean result.

    The indexed blob and worktree both contain `x`, while the configured clean filter emits `y`.
    Normal Git therefore reports the file modified. Sandboxed Git cannot launch the filter and
    otherwise exits zero while omitting that modification, so the production wrapper must discard
    stdout and convert the observation to a fail-closed nonzero result.
    """
    repo, home, sentinel = init_repo(tmp_path, hostile_key="filter.pwn.clean")
    (repo / "tracked.txt").write_text("x\n")
    payload = tmp_path / "payload.sh"
    payload.write_text(f"#!/bin/sh\ntouch '{sentinel}'\nprintf 'y\\n'\n")
    payload.chmod(0o700)
    subprocess.run(
        [str(GIT), "config", "filter.pwn.clean", str(payload)],
        cwd=repo,
        env=git_env(home),
        check=True,
    )
    os.utime(repo / "tracked.txt", None)
    control = subprocess.run(
        [str(GIT), "status", "--porcelain=v1"],
        cwd=repo,
        env=git_env(home),
        capture_output=True,
        text=True,
        check=True,
    )
    sentinel.unlink()
    assert " M tracked.txt" in control.stdout

    returncode, stdout, stderr = invoke_production_status(script, observer_namespace(script), repo)

    assert returncode == 126
    assert stdout in ("", b"")
    assert stderr in ("git_observation_stderr", b"git_observation_stderr")
    assert not sentinel.exists()


def test_delivery_status_bytes_mode_status_refuses_a_denied_filter(tmp_path: Path):
    """The real delivery-status repo probe must not bypass its stderr-refusing Git wrapper."""
    repo, home, sentinel = init_repo(tmp_path, hostile_key="filter.pwn.clean")
    (repo / "tracked.txt").write_text("x\n")
    payload = tmp_path / "payload.sh"
    payload.write_text(f"#!/bin/sh\ntouch '{sentinel}'\nprintf 'y\\n'\n")
    payload.chmod(0o700)
    subprocess.run(
        [str(GIT), "config", "filter.pwn.clean", str(payload)],
        cwd=repo,
        env=git_env(home),
        check=True,
    )
    os.utime(repo / "tracked.txt", None)
    control = subprocess.run(
        [str(GIT), "status", "--porcelain=v1"],
        cwd=repo,
        env=git_env(home),
        capture_output=True,
        text=True,
        check=True,
    )
    sentinel.unlink()
    assert " M tracked.txt" in control.stdout

    ns = observer_namespace("hermes-busdriver-delivery-status")
    returncode, records, completed = ns["git_status_records"](repo)

    assert returncode == 126
    assert records == []
    assert completed.returncode == 126
    assert completed.stdout == ""
    assert completed.stderr == "git_observation_stderr"
    assert not sentinel.exists()


def test_delivery_executor_status_sandboxes_and_refuses_a_denied_filter(tmp_path: Path):
    """The mutating executor still observes status; that read must not execute repository code."""
    repo, home, sentinel = init_repo(tmp_path, hostile_key="filter.pwn.clean")
    (repo / "tracked.txt").write_text("x\n")
    payload = tmp_path / "payload.sh"
    payload.write_text(f"#!/bin/sh\ntouch '{sentinel}'\nprintf 'y\\n'\n")
    payload.chmod(0o700)
    subprocess.run(
        [str(GIT), "config", "filter.pwn.clean", str(payload)],
        cwd=repo,
        env=git_env(home),
        check=True,
    )
    os.utime(repo / "tracked.txt", None)
    control = subprocess.run(
        [str(GIT), "status", "--porcelain=v1"],
        cwd=repo,
        env=git_env(home),
        capture_output=True,
        text=True,
        check=True,
    )
    sentinel.unlink()
    assert " M tracked.txt" in control.stdout

    ns = observer_namespace("hermes-busdriver-deliver")
    returncode, records, stderr = ns["git_status_records"](repo, "--untracked-files=all")

    assert returncode == 126
    assert records == []
    assert stderr == "git_observation_stderr"
    assert not sentinel.exists()


def test_delivery_executor_diff_sandboxes_and_refuses_a_denied_filter(tmp_path: Path):
    """Finalizer diff observations must use the same no-exec boundary as status."""
    repo, home, sentinel = init_repo(tmp_path, hostile_key="filter.pwn.clean")
    (repo / "tracked.txt").write_text("x\n")
    payload = tmp_path / "payload.sh"
    payload.write_text(f"#!/bin/sh\ntouch '{sentinel}'\nprintf 'y\\n'\n")
    payload.chmod(0o700)
    subprocess.run(
        [str(GIT), "config", "filter.pwn.clean", str(payload)],
        cwd=repo,
        env=git_env(home),
        check=True,
    )
    os.utime(repo / "tracked.txt", None)
    control = subprocess.run(
        [str(GIT), "diff", "--name-only"],
        cwd=repo,
        env=git_env(home),
        capture_output=True,
        text=True,
        check=True,
    )
    sentinel.unlink()
    assert "tracked.txt" in control.stdout

    ns = observer_namespace("hermes-busdriver-deliver")
    returncode, stdout, stderr = ns["git_output"](repo, "diff", "--name-only")

    assert returncode == 126
    assert stdout == ""
    assert stderr == "git_observation_stderr"
    assert not sentinel.exists()


def test_delivery_commit_routes_batched_status_and_diff_through_observation_helpers():
    source = (ROOT / "scripts" / "hermes-busdriver-deliver").read_text()
    commit_source = source[source.index("def commit_staged_index("):source.index("def push_remote_safety(")]

    assert 'git_raw_pathspec_batches(["status"' not in commit_source
    assert 'run_safe_pathspec_batches(["git", "diff"' not in commit_source


@pytest.mark.parametrize("script", OBSERVERS)
def test_every_observer_uses_a_pinned_deny_by_default_sandbox(script: str):
    ns = observer_namespace(script)
    sources = ns["TRUSTED_EXECUTABLE_SOURCES"]
    profile = ns["GIT_OBSERVATION_SANDBOX_PROFILE"]
    argv = ns["git_observation_argv"]("rev-parse", "HEAD")

    assert sources["sandbox-exec"] == Path("/usr/bin/sandbox-exec")
    assert sources["git-real"] == Path("/Library/Developer/CommandLineTools/usr/bin/git")
    assert argv[:3] == [str(sources["sandbox-exec"]), "-p", profile]
    assert argv[3] == str(sources["git-real"])
    assert "(deny network*)" in profile
    assert "(deny process-exec)" in profile
    assert f'(allow process-exec (literal "{sources["git-real"]}"))' in profile
    assert "/bin/sh" not in profile and "/usr/bin/env" not in profile

    pinned = {argv[index + 1].split("=", 1)[0] for index, item in enumerate(argv) if item == "-c"}
    assert PROGRAM_KEYS <= pinned


@pytest.mark.parametrize("script", OBSERVERS)
def test_every_observer_disables_lazy_fetch_and_all_transports(script: str, tmp_path: Path):
    ns = observer_namespace(script)
    env = ns["git_observation_env"]({"HOME": str(tmp_path)})

    assert env["GIT_NO_LAZY_FETCH"] == "1"
    assert env["GIT_ALLOW_PROTOCOL"] == ""
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_OPTIONAL_LOCKS"] == "0"


def test_litmus_timestamp_cannot_dispatch_repo_selected_signature_program(tmp_path: Path):
    repo, home, sentinel = init_repo(tmp_path, hostile_key="gpg.program")
    ns = observer_namespace("hermes-busdriver-litmus-status")

    cp = subprocess.run(
        ns["git_observation_argv"]("log", "-1", "--format=%ct"),
        cwd=repo,
        env=ns["git_observation_env"]({"HOME": str(home)}),
        capture_output=True,
        text=True,
    )

    assert cp.returncode == 0, cp.stderr
    assert cp.stdout.strip().isdigit()
    assert not sentinel.exists(), "litmus timestamp executed repository-selected gpg.program"


@pytest.mark.parametrize("script", OBSERVERS)
def test_status_argv_forces_complete_untracked_and_submodule_observation(script: str):
    ns = observer_namespace(script)
    argv = ns["git_observation_argv"](
        "status", "--porcelain=v1", "--untracked-files=no", "--ignore-submodules=all"
    )

    assert "--untracked-files=all" in argv
    assert "--ignore-submodules=none" in argv
    assert "--untracked-files=no" not in argv
    assert "--ignore-submodules=all" not in argv


@pytest.mark.parametrize("script", OBSERVERS)
def test_repo_config_cannot_hide_untracked_files_from_status_authority(script: str, tmp_path: Path):
    repo, home, _sentinel = init_repo(tmp_path, hostile_key="core.editor")
    subprocess.run(
        [str(GIT), "config", "status.showUntrackedFiles", "no"],
        cwd=repo, env=git_env(home), capture_output=True, text=True, check=True,
    )
    (repo / "untracked-authority-probe.txt").write_text("must remain visible\n")

    returncode, stdout, stderr = invoke_production_status(script, observer_namespace(script), repo)

    assert returncode == 0, stderr
    rendered_stdout = stdout.decode("utf-8", "replace") if isinstance(stdout, bytes) else stdout
    assert "untracked-authority-probe.txt" in rendered_stdout


@pytest.mark.parametrize("script", STATUS_SCRIPT_OBSERVERS)
def test_repo_config_cannot_hide_mode_only_drift_from_status_authority(script: str, tmp_path: Path):
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    repo.mkdir()
    home.mkdir()
    env = git_env(home)

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(GIT), *args], cwd=repo, env=env,
            capture_output=True, text=True, check=True,
        )

    git("init", "-q", ".")
    git("config", "user.email", "t@example.test")
    git("config", "user.name", "t")
    tool = repo / "tool.sh"
    tool.write_text("#!/bin/sh\nexit 0\n")
    tool.chmod(0o644)
    git("add", "tool.sh")
    git("commit", "-qm", "init")
    git("config", "core.fileMode", "false")
    tool.chmod(0o755)

    assert git("status", "--porcelain=v1").stdout == "", "hostile fixture did not hide mode drift"
    control = git("-c", "core.fileMode=true", "status", "--porcelain=v1").stdout
    assert "tool.sh" in control, "mode-only control did not expose drift"

    returncode, stdout, stderr = invoke_production_status(script, observer_namespace(script), repo)

    assert returncode == 0, stderr
    rendered_stdout = stdout.decode("utf-8", "replace") if isinstance(stdout, bytes) else stdout
    assert "tool.sh" in rendered_stdout, f"{script}: repo core.fileMode=false hid mode-only drift"


def test_status_authority_reports_a_dirty_submodule_worktree(tmp_path: Path):
    home = tmp_path / "home"
    child = tmp_path / "child"
    repo = tmp_path / "repo"
    home.mkdir()
    child.mkdir()
    repo.mkdir()
    env = git_env(home)

    def git(cwd: Path, *args: str) -> None:
        cp = subprocess.run([str(GIT), *args], cwd=cwd, env=env, capture_output=True, text=True)
        assert cp.returncode == 0, cp.stderr

    for directory in (child, repo):
        git(directory, "init", "-q", ".")
        git(directory, "config", "user.email", "t@example.test")
        git(directory, "config", "user.name", "t")
    (child / "tracked.txt").write_text("committed\n")
    git(child, "add", "tracked.txt")
    git(child, "commit", "-qm", "child")
    (repo / "root.txt").write_text("root\n")
    git(repo, "add", "root.txt")
    git(repo, "commit", "-qm", "root")
    env["GIT_ALLOW_PROTOCOL"] = "file"
    try:
        git(repo, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(child), "nested")
    finally:
        env["GIT_ALLOW_PROTOCOL"] = ""
    git(repo, "commit", "-qam", "add submodule")
    (repo / "nested" / "tracked.txt").write_text("dirty\n")

    returncode, stdout, stderr = invoke_production_status(
        "hermes-busdriver-status", observer_namespace("hermes-busdriver-status"), repo
    )

    assert returncode == 0, stderr
    rendered_stdout = stdout.decode("utf-8", "replace") if isinstance(stdout, bytes) else stdout
    assert "nested" in rendered_stdout


def test_delivery_hash_and_marker_helpers_reject_partial_stdout_from_failed_observation():
    ns = observer_namespace("hermes-busdriver-deliver")
    staged_diff_hash = ns["staged_diff_hash"]
    reviewed_tree_diff_hash = ns["reviewed_tree_diff_hash"]
    diff_hash = ns["diff_hash"]
    staged_marker_entries = ns["staged_marker_entries"]
    calls: list[tuple[Path, tuple[str, ...]]] = []

    def failed_observation(repo: Path, *git_args: str) -> tuple[int, bytes, str]:
        calls.append((repo, git_args))
        return 126, b"attacker-partial-output", "git_observation_stderr"

    def forbidden_bounded_run(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("direct _bounded_run reached")

    production_globals = staged_diff_hash.__globals__
    production_globals["git_observation_raw"] = failed_observation
    production_globals["_bounded_run"] = forbidden_bounded_run

    repo = Path("/repo")
    assert staged_diff_hash(repo) is None
    assert reviewed_tree_diff_hash(repo, "parent", "tree") is None
    assert diff_hash(repo, "base..head") is None
    assert staged_marker_entries(repo, (".claude",)) == ["<staged marker check failed>"]
    assert len(calls) == 4
