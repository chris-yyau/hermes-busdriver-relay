import argparse
import json
import os
import runpy
import stat
import subprocess
import sys
import threading
from pathlib import Path

import pytest


LOCK = Path(__file__).resolve().parents[2] / "scripts" / "hermes-busdriver-lock"


def run_lock(*args: str, check: bool = True, timeout: float = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LOCK), *args], text=True, capture_output=True, check=check, timeout=timeout,
    )


def init_repo(path: Path) -> None:
    path.mkdir()
    subprocess.run(["git", "init"], cwd=path, text=True, capture_output=True, check=True)


def tree_snapshot(path: Path) -> list[str]:
    return sorted(p.relative_to(path).as_posix() for p in path.rglob("*"))


def test_lock_acquire_blocks_second_and_release_requires_token(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"
    before = tree_snapshot(repo)

    first = run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test")
    data = json.loads(first.stdout)
    assert data["acquired"] is True
    token = data["token"]

    second = run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test", check=False)
    assert second.returncode == 2
    assert json.loads(second.stdout)["reason"] == "lock-active"

    wrong_release = run_lock("release", "--repo", str(repo), "--state-dir", str(state), "--operation", "test", "--token", "wrong", check=False)
    assert wrong_release.returncode == 3
    assert json.loads(wrong_release.stdout)["reason"] == "token-mismatch"

    release = run_lock("release", "--repo", str(repo), "--state-dir", str(state), "--operation", "test", "--token", token)
    release_data = json.loads(release.stdout)
    assert release_data["released"] is True
    retired = Path(release_data["retired_path"])
    assert retired.exists()
    assert retired.parent == Path(data["path"]).parent
    assert json.loads((retired / "lock.json").read_text())["token"] == token
    assert not Path(data["path"]).exists()
    assert tree_snapshot(repo) == before


def test_lock_release_cli_has_no_force_bypass(tmp_path):
    repo = tmp_path / "repo-force"
    init_repo(repo)
    state = tmp_path / "state-force"
    acquired = json.loads(run_lock("acquire", "--repo", str(repo), "--state-dir", str(state)).stdout)

    forced = run_lock(
        "release", "--repo", str(repo), "--state-dir", str(state),
        "--token", acquired["token"], "--force", check=False,
    )

    assert forced.returncode == 2
    assert "unrecognized arguments: --force" in forced.stderr
    assert json.loads((Path(acquired["path"]) / "lock.json").read_text())["token"] == acquired["token"]


@pytest.mark.parametrize("ttl", ["0", "-1"])
def test_lock_acquire_rejects_non_positive_ttl_without_state(tmp_path, ttl):
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"

    blocked = run_lock(
        "acquire", "--repo", str(repo), "--state-dir", str(state),
        "--operation", "test", "--ttl-seconds", ttl, check=False,
    )

    assert blocked.returncode == 2
    assert json.loads(blocked.stdout)["reason"] == "invalid-ttl"
    assert not state.exists()


def test_stale_lock_requires_explicit_manual_recovery(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"
    acquired = json.loads(run_lock(
        "acquire", "--repo", str(repo), "--state-dir", str(state),
        "--operation", "test", "--ttl-seconds", "1",
    ).stdout)
    lock_file = Path(acquired["path"]) / "lock.json"
    payload = json.loads(lock_file.read_text())
    payload["created_at_epoch"] = 0
    lock_file.write_text(json.dumps(payload))

    status = run_lock("status", "--state-dir", str(state), "--pretty")
    assert json.loads(status.stdout)["locks"][0]["stale"] is True

    blocked = run_lock(
        "acquire", "--repo", str(repo), "--state-dir", str(state),
        "--operation", "test", "--ttl-seconds", "100", check=False,
    )
    data = json.loads(blocked.stdout)
    assert blocked.returncode == 2
    assert data["acquired"] is False
    assert data["reason"] == "lock-stale-manual-recovery"
    assert json.loads(lock_file.read_text())["token"] == acquired["token"]


@pytest.mark.parametrize(("first_operation", "second_operation"), [("agent-draft", "finalization"), ("finalization", "agent-draft")])
def test_same_worktree_operations_share_one_mutation_lock(tmp_path, first_operation, second_operation):
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"

    first = run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", first_operation)
    second = run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", second_operation, check=False)

    assert second.returncode == 2
    assert json.loads(second.stdout)["reason"] == "lock-active"
    acquired = json.loads(first.stdout)
    run_lock("release", "--repo", str(repo), "--state-dir", str(state), "--operation", second_operation, "--token", acquired["token"])


def test_branch_switch_does_not_orphan_acquired_lock(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    subprocess.run(["git", "switch", "-c", "before"], cwd=repo, check=True, capture_output=True)
    state = tmp_path / "state"
    acquired = json.loads(run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "agent-draft").stdout)

    subprocess.run(["git", "switch", "-c", "after"], cwd=repo, check=True, capture_output=True)
    released = run_lock("release", "--repo", str(repo), "--state-dir", str(state), "--operation", "agent-draft", "--token", acquired["token"])

    assert json.loads(released.stdout)["released"] is True


def test_malformed_canonical_lock_fails_closed(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"
    acquired = json.loads(run_lock("acquire", "--repo", str(repo), "--state-dir", str(state)).stdout)
    Path(acquired["path"], "lock.json").write_text("{partial")

    blocked = run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), check=False)

    assert blocked.returncode == 2
    assert json.loads(blocked.stdout)["reason"] == "lock-state-invalid"


@pytest.mark.parametrize("attack", ["symlink", "fifo", "hardlink", "oversized"])
def test_lock_reader_refuses_untrusted_leaf_shapes_without_blocking(tmp_path, attack):
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"
    acquired = json.loads(run_lock("acquire", "--repo", str(repo), "--state-dir", str(state)).stdout)
    lock_file = Path(acquired["path"], "lock.json")
    original = lock_file.read_bytes()
    outside = tmp_path / "outside-lock.json"
    outside.write_bytes(original)
    lock_file.unlink()

    if attack == "symlink":
        lock_file.symlink_to(outside)
    elif attack == "fifo":
        os.mkfifo(lock_file)
    elif attack == "hardlink":
        os.link(outside, lock_file)
    else:
        lock_file.write_bytes(b"{" + b"x" * (64 * 1024))

    blocked = run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), check=False, timeout=3)

    assert blocked.returncode == 2
    assert json.loads(blocked.stdout)["reason"] == "lock-state-invalid"
    assert acquired["token"] not in blocked.stdout


def test_lock_reader_revalidates_the_name_after_read(monkeypatch, tmp_path):
    ns = runpy.run_path(str(LOCK))
    lock_dir = tmp_path / "generation.lock"
    lock_dir.mkdir()
    lock_file = lock_dir / "lock.json"
    payload = {
        "schema": ns["SCHEMA"], "token": "secret", "lock_id": "id",
        "created_at_epoch": 1, "ttl_seconds": 60, "operation": "test", "repo": {},
    }
    lock_file.write_text(json.dumps(payload))
    real_read = os.read
    swapped = []

    def read_then_replace(fd, count):
        data = real_read(fd, count)
        if data and not swapped:
            swapped.append(True)
            lock_file.rename(lock_dir / "old-lock.json")
            lock_file.write_text(json.dumps(payload))
        return data

    monkeypatch.setattr(ns["read_lock"].__globals__["os"], "read", read_then_replace)

    assert ns["read_lock"](lock_dir) is None
    assert swapped, "the identity swap was not injected"


def test_publish_and_competing_acquire_are_serialized(monkeypatch, tmp_path):
    ns = runpy.run_path(str(LOCK))
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"
    args = lambda operation: argparse.Namespace(repo=str(repo), state_dir=str(state), operation=operation, ttl_seconds=100, note="")
    entered = threading.Event()
    publish = threading.Event()
    loser_waiting = threading.Event()
    original_replace = ns["publish_lock"].__globals__["os"].replace
    original_flock = ns["acquire"].__globals__["fcntl"].flock
    first = True

    def paused_replace(source, target):
        nonlocal first
        if first and str(target).endswith(".lock"):
            first = False
            entered.set()
            assert publish.wait(5)
        return original_replace(source, target)

    monkeypatch.setattr(ns["publish_lock"].__globals__["os"], "replace", paused_replace)
    def observed_flock(fd, operation):
        if threading.current_thread().name == "loser":
            loser_waiting.set()
        return original_flock(fd, operation)

    monkeypatch.setattr(ns["acquire"].__globals__["fcntl"], "flock", observed_flock)
    results = []
    winner = threading.Thread(name="winner", target=lambda: results.append(ns["acquire"](args("agent-draft"))))
    loser = threading.Thread(name="loser", target=lambda: results.append(ns["acquire"](args("finalization"))))
    winner.start()
    assert entered.wait(5)
    loser.start()
    assert loser_waiting.wait(5)
    assert loser.is_alive()
    publish.set()
    winner.join(5)
    loser.join(5)

    assert sorted(results) == [0, 2]
    assert len(list((state / "locks").glob("*.lock"))) == 1


def test_release_compare_delete_preserves_noncooperative_replacement(monkeypatch, tmp_path):
    ns = runpy.run_path(str(LOCK))
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"
    base = dict(repo=str(repo), state_dir=str(state), operation="agent-draft", ttl_seconds=100)
    acquire_args = argparse.Namespace(**base, note="")
    assert ns["acquire"](acquire_args) == 0
    path = ns["lock_dir"](state, ns["canonical_repo"](str(repo)), "agent-draft")
    old_payload = json.loads((path / "lock.json").read_text())
    detached_old = path.parent / "detached-old-generation.lock"
    replacement_payload = dict(old_payload, token="replacement-token", owner_pid=99999)
    original_rename = ns["release"].__globals__["os"].rename
    raced = False

    def replace_path_before_quarantine(source, target):
        nonlocal raced
        if not raced and Path(source) == path:
            raced = True
            original_rename(path, detached_old)
            path.mkdir(mode=0o700)
            (path / "lock.json").write_text(json.dumps(replacement_payload))
        return original_rename(source, target)

    monkeypatch.setattr(ns["release"].__globals__["os"], "rename", replace_path_before_quarantine)
    release_args = argparse.Namespace(**base, token=old_payload["token"], lock_path=str(path))

    rc = ns["release"](release_args)

    assert rc == 3
    assert raced is True
    assert json.loads((path / "lock.json").read_text())["token"] == "replacement-token"
    assert json.loads((detached_old / "lock.json").read_text())["token"] == old_payload["token"]


def test_linked_worktrees_have_distinct_mutation_locks(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "tracked").write_text("one\n")
    subprocess.run(["git", "add", "tracked"], cwd=repo, check=True)
    env = os.environ | {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "commit.gpgSign", "GIT_CONFIG_VALUE_0": "false"}
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, env=env, check=True, capture_output=True)
    linked = tmp_path / "linked"
    subprocess.run(["git", "worktree", "add", "-b", "linked", str(linked)], cwd=repo, check=True, capture_output=True)
    state = tmp_path / "state"

    first = json.loads(run_lock("acquire", "--repo", str(repo), "--state-dir", str(state)).stdout)
    second = json.loads(run_lock("acquire", "--repo", str(linked), "--state-dir", str(state)).stdout)

    assert first["acquired"] is second["acquired"] is True
    assert first["path"] != second["path"]


def test_lock_canonical_repo_dispatches_validated_root_owned_git_inside_sandbox(monkeypatch, tmp_path: Path):
    """v16-r34c: replaces test_lock_canonical_repo_uses_authenticated_private_git.

    Same inversion as the gate's sibling, and it matters more here: this git decides which repo the
    lock is FOR, so substituting it forges the identity single-flight is keyed on. The old design
    answered that with a private 0500 copy, which only moved the substitutable name somewhere this
    UID can still write — and macOS re-resolves that name at exec time. The source is now fixed and
    root-owned, so the assertions are the ones no private copy could satisfy.
    """
    ns = runpy.run_path(str(LOCK))
    resolved = ns["trusted_git_path"]()
    assert resolved == ns["TRUSTED_EXECUTABLE_SOURCES"]["git"] == Path("/usr/bin/git")
    sandbox = ns["trusted_executable_path"]("sandbox-exec")
    git_real = ns["trusted_executable_path"]("git-real")
    st = os.lstat(resolved)
    assert not stat.S_ISLNK(st.st_mode), "a symlinked name is a name someone else can re-point"
    assert st.st_uid == 0, "a git this UID owns is a git this UID can replace"
    assert not (st.st_mode & (stat.S_IWGRP | stat.S_IWOTH))
    assert st.st_flags & ns["SF_RESTRICTED"], "SIP replaces nlink==1 for the shim-backed source"
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        stdout = str(tmp_path) + "\n" if "--show-toplevel" in cmd else "main\n"
        return ns["BoundedOutput"](0, stdout, "", False, False)

    # The launch is bounded and the two metadata observations are OS-sandboxed before real Git.
    monkeypatch.setitem(ns["run"].__globals__, "run_bounded", fake_run)
    info = ns["canonical_repo"](str(tmp_path))
    assert info["is_git_repo"] is True
    assert len(seen) == 2
    assert all(Path(cmd[0]) == sandbox for cmd in seen)
    assert all(cmd[1:4] == ["-p", ns["GIT_OBSERVATION_SANDBOX_PROFILE"], str(git_real)] for cmd in seen)


# --- v16-r24 A1: a held lock's release token is a capability, never published evidence ---


def _fake_git(bin_dir: Path, body: str) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    git = bin_dir / "git"
    git.write_text(body)
    git.chmod(0o755)
    return git


def test_contending_acquire_never_publishes_holder_token(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"
    acquired = json.loads(run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test").stdout)
    token = acquired["token"]

    contender = run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test", check=False)

    assert contender.returncode == 2
    data = json.loads(contender.stdout)
    assert data["reason"] == "lock-active"
    assert token not in contender.stdout
    assert "token" not in data["lock"]
    assert data["lock"]["token_redacted"] is True
    # The holder still owns the capability it was handed.
    assert json.loads(run_lock("release", "--repo", str(repo), "--state-dir", str(state), "--operation", "test", "--token", token).stdout)["released"] is True


def test_stale_contending_acquire_never_publishes_holder_token(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"
    acquired = json.loads(run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test", "--ttl-seconds", "1").stdout)
    lock_file = Path(acquired["path"]) / "lock.json"
    payload = json.loads(lock_file.read_text())
    payload["created_at_epoch"] = 0
    lock_file.write_text(json.dumps(payload))

    blocked = run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test", "--ttl-seconds", "100", check=False)

    data = json.loads(blocked.stdout)
    assert data["reason"] == "lock-stale-manual-recovery"
    assert acquired["token"] not in blocked.stdout
    assert "token" not in data["lock"]


def test_status_never_publishes_tokens(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"
    acquired = json.loads(run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test").stdout)

    status = run_lock("status", "--state-dir", str(state))

    assert acquired["token"] not in status.stdout
    entry = json.loads(status.stdout)["locks"][0]
    assert "token" not in entry
    assert entry["token_redacted"] is True
    assert entry["lock_id"] == acquired["lock_id"]


def test_acquire_returns_token_only_to_the_acquiring_holder(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"

    acquired = json.loads(run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test").stdout)

    # The acquiring caller IS the holder, so it gets the capability once, at the top level only.
    assert acquired["token"]
    assert "token" not in acquired["lock"]
    assert json.loads((Path(acquired["path"]) / "lock.json").read_text())["token"] == acquired["token"]


# --- v16-r24 A2: canonical repo resolution runs pinned git under a strict sanitized env ---


@pytest.mark.parametrize("ambient", [
    {"GIT_WORK_TREE": "/tmp"},
    {"GIT_CEILING_DIRECTORIES": "/"},
    {"GIT_DIR": "/tmp/elsewhere/.git"},
])
def test_ambient_git_env_cannot_split_the_lock_key(tmp_path, ambient):
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"
    clean = json.loads(run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test").stdout)
    run_lock("release", "--repo", str(repo), "--state-dir", str(state), "--operation", "test", "--token", clean["token"])

    env = {**os.environ, **ambient}
    poisoned = subprocess.run(
        [sys.executable, str(LOCK), "acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test"],
        text=True, capture_output=True, env=env, check=True,
    )

    assert json.loads(poisoned.stdout)["lock_id"] == clean["lock_id"]


def test_subdir_and_root_cannot_split_the_lock_key(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    sub = repo / "nested" / "deeper"
    sub.mkdir(parents=True)
    state = tmp_path / "state"

    root_lock = json.loads(run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test").stdout)
    sub_lock = run_lock("acquire", "--repo", str(sub), "--state-dir", str(state), "--operation", "test", check=False)

    assert sub_lock.returncode == 2
    assert json.loads(sub_lock.stdout)["reason"] == "lock-active"
    assert root_lock["lock_id"]


# `run()` funnels timeout, OSError and a non-zero git into one fail-closed branch, so the two
# cases below (unusable cwd -> OSError; plain dir -> git rc 128) cover the branch that a timeout
# also reaches. Injecting a slow git would need a caller-nameable git path, which is the trust
# hole the pinned digest exists to close, so it is deliberately not testable that way.
@pytest.mark.parametrize("subject", ["missing", "not-a-repo"])
def test_git_failure_never_falls_back_to_the_input_path(tmp_path, subject):
    state = tmp_path / "state"
    if subject == "missing":
        target = tmp_path / "gone"
    else:
        target = tmp_path / "plain"
        target.mkdir()

    blocked = run_lock("acquire", "--repo", str(target), "--state-dir", str(state), "--operation", "test", check=False)

    assert blocked.returncode == 2
    data = json.loads(blocked.stdout)
    assert data["acquired"] is False
    assert data["reason"] == "lock-repo-resolution-failed"
    assert not list((state / "locks").glob("*.lock")) if (state / "locks").exists() else True


def test_git_failure_also_fails_closed_for_release_and_never_removes_a_lock(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"
    acquired = json.loads(run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test").stdout)

    blocked = run_lock("release", "--repo", str(tmp_path / "gone"), "--state-dir", str(state), "--operation", "test", "--token", acquired["token"], check=False)

    assert blocked.returncode == 2
    assert json.loads(blocked.stdout)["reason"] == "lock-repo-resolution-failed"
    assert Path(acquired["path"]).exists()
