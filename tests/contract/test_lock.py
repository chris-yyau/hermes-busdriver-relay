import json
import subprocess
import sys
from pathlib import Path


LOCK = Path(__file__).resolve().parents[2] / "scripts" / "hermes-busdriver-lock"


def run_lock(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LOCK), *args], text=True, capture_output=True, check=check)


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
    assert json.loads(release.stdout)["released"] is True
    assert tree_snapshot(repo) == before


def test_lock_status_and_stale_reacquire(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    state = tmp_path / "state"
    run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test", "--ttl-seconds", "0")
    status = run_lock("status", "--state-dir", str(state), "--ttl-seconds", "0", "--pretty")
    data = json.loads(status.stdout)
    assert data["count"] == 1
    assert data["locks"][0]["stale"] is True
    reacquire = run_lock("acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "test", "--ttl-seconds", "100")
    assert json.loads(reacquire.stdout)["acquired"] is True
