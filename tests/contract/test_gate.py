import json
import os
import subprocess
import sys
from pathlib import Path


GATE = Path(__file__).resolve().parents[2] / "scripts" / "hermes-busdriver-gate"


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run([sys.executable, str(GATE), *args], cwd=cwd, text=True, capture_output=True)
    if check and cp.returncode != 0:
        raise AssertionError(f"gate failed rc={cp.returncode}\nSTDOUT={cp.stdout}\nSTDERR={cp.stderr}")
    return cp


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    (path / "src").mkdir()
    (path / "src" / "app.txt").write_text("hello\n")
    (path / ".gitignore").write_text(".env\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def fake_busdriver(path: Path) -> Path:
    root = path / "busdriver"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [], "PostToolUse": [], "Stop": []}}))
    (root / "package.json").write_text(json.dumps({"version": "test"}))
    return root


def test_preflight_passes_for_clean_repo_and_writes_baseline(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    baseline = tmp_path / "baseline.json"

    cp = run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline), "--scope-include", "src/**")
    data = json.loads(cp.stdout)

    assert data["ok"] is True
    assert Path(data["baseline_file"]).exists()
    assert data["decision"]["agent_implementation_draft_allowed"] is True
    assert data["decision"]["commit_allowed"] is False
    assert data["decision"]["pr_allowed"] is False


def test_preflight_blocks_dirty_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    (repo / "src" / "app.txt").write_text("dirty\n")

    cp = run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    assert data["ok"] is False
    repo_clean = next(c for c in data["checks"] if c["name"] == "repo_clean")
    assert repo_clean["ok"] is False


def test_postflight_scope_pass_and_verifier_pass(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    baseline = tmp_path / "baseline.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline), "--scope-include", "src/**")

    (repo / "src" / "app.txt").write_text("changed\n")
    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), "--verifier", "check=test -f src/app.txt")
    data = json.loads(cp.stdout)

    assert data["ok"] is True
    assert data["changed_files"] == ["src/app.txt"]
    assert data["decision"]["agent_implementation_draft_allowed"] is True
    assert data["decision"]["commit_allowed"] is False


def test_postflight_blocks_out_of_scope_change(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    baseline = tmp_path / "baseline.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline), "--scope-include", "src/**")

    (repo / "README.md").write_text("oops\n")
    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    assert data["ok"] is False
    scope = next(c for c in data["checks"] if c["name"] == "changed_files_within_scope")
    assert scope["ok"] is False
    assert "README.md" in scope["detail"]["out_of_scope"]


def test_postflight_blocks_git_hook_tamper(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    baseline = tmp_path / "baseline.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline))

    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho bad\n")
    hook.chmod(0o755)
    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    hooks = next(c for c in data["checks"] if c["name"] == "git_hooks_untampered")
    assert hooks["ok"] is False
    assert ".git/hooks/pre-commit" in hooks["detail"]["added"]


def test_postflight_blocks_new_ignored_file(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    baseline = tmp_path / "baseline.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline))

    (repo / ".env").write_text("SECRET=bad\n")
    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    ignored = next(c for c in data["checks"] if c["name"] == "no_new_or_changed_ignored_files")
    assert ignored["ok"] is False
    assert ".env" in ignored["detail"]["added"]
