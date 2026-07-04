import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "hermes-busdriver-relay-brief"
BLOCKED_AUTHORITY_FLAGS = [
    "finalization_allowed",
    "commit_allowed",
    "push_allowed",
    "pr_allowed",
    "merge_allowed",
    "deploy_allowed",
    "release_allowed",
    "publish_allowed",
    "marker_write_allowed",
    "mutation_allowed",
    "programmatic_execution_allowed",
    "non_codex_agent_enablement_allowed",
]
EXPECTED_TASKS = {
    "adr0005-unlock-contract",
    "mutating-pr-grind-fix-loop",
    "marker-interop-contract",
    "opencode-adapter-proof",
    "status-ux-layer",
}


def init_git_repo(repo: Path, tracked_file: Path | None = None) -> None:
    subprocess.run(["git", "init"], cwd=repo, text=True, capture_output=True, check=True)
    if tracked_file is not None:
        subprocess.run(["git", "add", str(tracked_file.relative_to(repo))], cwd=repo, text=True, capture_output=True, check=True)
    else:
        subprocess.run(["git", "add", "."], cwd=repo, text=True, capture_output=True, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "init"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )


def run_brief(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        check=True,
        env=full_env,
    )


def test_relay_brief_reports_requested_roadmap_tasks_read_only_and_authority_false(tmp_path):
    installed_skill = tmp_path / "installed-skill"
    installed_skill.mkdir()

    proc = run_brief("--pretty", "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["schema"] == "hermes-busdriver-relay-brief/v0"
    assert data["read_only"] is True
    assert data["ok"] is True
    assert data["finalization_contract_status"]["read_only"] is True
    assert data["finalization_contract_status"]["decision_status"] == "policy_blocked"
    assert data["finalization_contract_status"]["capability_allowed_count"] == 0
    assert {task["id"] for task in data["roadmap_tasks"]} == EXPECTED_TASKS

    for flag in BLOCKED_AUTHORITY_FLAGS:
        assert data["authority"][flag] is False
        assert data["decision"][flag] is False

    task_by_id = {task["id"]: task for task in data["roadmap_tasks"]}
    assert task_by_id["adr0005-unlock-contract"]["status"] == "contract_complete_authority_policy_blocked"
    assert task_by_id["mutating-pr-grind-fix-loop"]["status"] == "read_only_design_complete_mutating_loop_policy_blocked"
    assert task_by_id["marker-interop-contract"]["status"] == "design_contract_complete_marker_write_policy_blocked"
    assert task_by_id["opencode-adapter-proof"]["status"] == "candidate_only_requires_separate_smoke_contract"
    assert task_by_id["status-ux-layer"]["status"] == "implemented_by_hermes_busdriver_relay_brief"


def test_relay_brief_text_is_telegram_friendly_and_does_not_claim_authority(tmp_path):
    installed_skill = tmp_path / "installed-skill"
    installed_skill.mkdir()

    proc = run_brief("--brief", "--installed-skill", str(installed_skill))
    text = proc.stdout

    assert "Hermes Busdriver Relay brief" in text
    assert "skill-sync:" in text
    assert "contract: policy_blocked" in text
    assert "OpenCode candidate proof" in text
    assert "Status/UX" in text
    assert "authority: all false" in text
    assert "next:" in text


def test_relay_brief_reports_installed_skill_drift_without_mutation(tmp_path):
    repo = tmp_path / "repo"
    repo_skill = repo / "skills" / "busdriver-relay"
    repo_skill.mkdir(parents=True)
    (repo_skill / "SKILL.md").write_text("# repo skill\n")
    init_git_repo(repo)

    installed_skill = tmp_path / "installed-skill"
    reference_dir = installed_skill / "references"
    reference_dir.mkdir(parents=True)
    (installed_skill / "SKILL.md").write_text("# divergent installed skill\n")
    (reference_dir / "extra.md").write_text("installed-only\n")

    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["repo"]["dirty"] is False
    assert data["skill_sync"]["checked"] is True
    assert data["skill_sync"]["clean"] is False
    assert "SKILL.md" in data["skill_sync"]["diffs"]
    assert "references/extra.md" in data["skill_sync"]["missing"]
    assert data["decision"]["status"] == "needs_skill_source_sync"
    assert data["decision"]["next_safe_slice"] == "sync_installed_skill_reference_back_to_repo"
    for flag in BLOCKED_AUTHORITY_FLAGS:
        assert data["decision"][flag] is False

    brief = run_brief("--brief", "--repo", str(repo), "--installed-skill", str(installed_skill)).stdout
    assert "skill-sync: drift missing=1 extra=0 diffs=1" in brief


def test_relay_brief_preserves_git_short_status_columns(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("before\n")
    init_git_repo(repo, tracked)
    tracked.write_text("after\n")

    installed_skill = tmp_path / "installed-skill"
    installed_skill.mkdir()
    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["repo"]["dirty"] is True
    assert data["repo"]["porcelain"] == [" M tracked.txt"]
    assert data["decision"]["status"] == "needs_local_reconciliation"


def test_relay_brief_blocks_when_installed_skill_unverified(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("content\n")
    init_git_repo(repo, tracked)

    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(tmp_path / "missing-skill"))
    data = json.loads(proc.stdout)

    assert data["ok"] is False
    assert data["skill_sync"]["checked"] is False
    assert data["skill_sync"]["reason"] == "installed_skill_missing"
    assert data["decision"]["status"] == "blocked_unverified_skill_sync"
    assert data["decision"]["next_safe_slice"] == "inspect_installed_skill_path"
    for flag in BLOCKED_AUTHORITY_FLAGS:
        assert data["decision"][flag] is False
