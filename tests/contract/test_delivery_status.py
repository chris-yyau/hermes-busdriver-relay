import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "scripts" / "hermes-busdriver-delivery-status"


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=False)


def init_repo(path: Path) -> Path:
    path.mkdir()
    assert run(["git", "init"], path).returncode == 0
    assert run(["git", "config", "user.email", "test@example.test"], path).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], path).returncode == 0
    (path / "README.md").write_text("# test\n")
    assert run(["git", "add", "README.md"], path).returncode == 0
    assert run(["git", "commit", "-m", "init"], path).returncode == 0
    return path


def fake_busdriver(path: Path) -> Path:
    files = {
        "package.json": '{"version":"1.71.0"}\n',
        "scripts/relevant-check-status.sh": "#!/bin/sh\ncat >/dev/null\nprintf '0 0 all 1\\n'\n",
        "scripts/ack-ledger.sh": "#!/bin/sh\nprintf 'none\\n'\n",
        "scripts/fetch-pr-state.sh": "#!/bin/sh\ntrue\n",
        "hooks/gate-scripts/pre-pr-gate.sh": "#!/bin/sh\ntrue\n",
        "hooks/gate-scripts/pre-merge-gate.sh": "#!/bin/sh\ntrue\n",
        "opencode/skills/pr-grind/SKILL.md": "# pr-grind\n",
        "opencode/agents/pr-grinder.md": "# pr-grinder\n",
    }
    for rel, content in files.items():
        p = path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        if rel.startswith("scripts/") or rel.startswith("hooks/"):
            p.chmod(0o755)
    return path


def invoke(repo: Path, plugin: Path, *extra: str) -> dict:
    cp = run([sys.executable, str(STATUS), "--repo", str(repo), "--plugin-root", str(plugin), "--no-lock-status", "--no-agent-runs", *extra])
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return json.loads(cp.stdout)


def snapshot_files(path: Path) -> dict[str, str]:
    out = {}
    for root, _dirs, files in os.walk(path):
        for name in files:
            p = Path(root) / name
            out[str(p.relative_to(path))] = p.read_text(errors="ignore")
    return out


def test_dirty_draft_status_is_read_only_and_non_finalizing(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    before_repo = snapshot_files(repo)
    before_plugin = snapshot_files(plugin)

    data = invoke(repo, plugin)

    assert data["schema"] == "hermes-busdriver-delivery-status/v0"
    assert data["repo"]["dirty"] is True
    assert data["decision"]["status"] == "draft_changes_need_busdriver_finalization"
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["commit_allowed"] is False
    assert data["decision"]["pr_allowed"] is False
    assert data["decision"]["merge_allowed"] is False
    assert snapshot_files(repo) == before_repo
    assert snapshot_files(plugin) == before_plugin


def test_untracked_files_are_not_reported_as_unstaged(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "new.txt").write_text("new\n")

    data = invoke(repo, plugin)

    assert data["repo"]["untracked_entries"] == ["?? new.txt"]
    assert data["repo"]["unstaged_entries"] == []


def test_pr_status_blocks_when_pr_grind_checker_missing(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    missing_checker = tmp_path / "missing-pr-grind-check"

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-check-script", str(missing_checker))

    assert data["decision"]["status"] == "blocked"
    assert "hermes_pr_grind_checker_unavailable" in data["decision"]["blockers"]
    assert data["pr_grind"]["available"] is False
    assert data["decision"]["merge_allowed"] is False


def test_pr_clean_fixture_is_still_read_only_not_merge_authority(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    pr_result = tmp_path / "pr-grind-result.json"
    pr_result.write_text(json.dumps({"status": "clean", "clean": True, "checks": {"failed": 0, "pending": 0}, "actionable_comments": []}))

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert data["decision"]["status"] == "pr_clean_read_only"
    assert data["pr_grind"]["result"]["clean"] is True
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["merge_allowed"] is False
    assert "read-only" in data["decision"]["policy"].lower()


def test_invalid_pr_grind_result_fixture_does_not_crash(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    pr_result = tmp_path / "bad-pr-grind-result.json"
    pr_result.write_text("not-json\n")

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert data["pr_grind"]["ok"] is True
    assert data["pr_grind"]["result"] == {}
    assert data["decision"]["status"] == "blocked"
    assert "pr_not_clean" in data["decision"]["blockers"]


def test_timed_out_pr_grind_checker_reports_structured_blocker(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    checker = tmp_path / "slow_checker.py"
    checker.write_text('import time\nprint("partial stdout", flush=True)\ntime.sleep(5)\n')

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-check-script", str(checker), "--pr-grind-timeout", "1")

    assert data["pr_grind"]["ok"] is False
    assert data["pr_grind"]["returncode"] == 124
    assert data["pr_grind"]["stdout_tail"] == "partial stdout\n"
    assert "timeout after 1s" in data["pr_grind"]["stderr"]
    assert data["decision"]["status"] == "blocked"
    assert "pr_grind_checker_failed" in data["decision"]["blockers"]


def test_blocking_marker_blocks_delivery(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    marker = repo / ".claude" / "freeze.local"
    marker.parent.mkdir()
    marker.write_text("freeze\n")

    data = invoke(repo, plugin)

    assert data["decision"]["status"] == "blocked"
    assert "blocking_busdriver_marker_present" in data["decision"]["blockers"]
    assert data["markers"]["blocking"][0]["name"] == "freeze.local"
