import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / "scripts" / "hermes-busdriver-agent-draft"
LOCK = ROOT / "scripts" / "hermes-busdriver-lock"


def sh(cmd, cwd=None, check=True):
    cp = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
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
    sh(["git", "commit", "-m", "init"], cwd=path)


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
    assert data["agent_result"]["returncode"] == 126
    assert "blocked git commit" in data["agent_result"]["stderr_tail"]
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
