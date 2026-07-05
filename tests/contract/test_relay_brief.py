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




def make_repo_with_skill(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo_skill = repo / "skills" / "busdriver-relay"
    repo_skill.mkdir(parents=True)
    (repo_skill / "SKILL.md").write_text("# repo skill\n")

    installed_skill = tmp_path / "installed-skill"
    installed_skill.mkdir()
    (installed_skill / "SKILL.md").write_text("# repo skill\n")
    return repo, installed_skill


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

    subdir = repo / "subdir"
    subdir.mkdir()

    proc = run_brief("--pretty", "--repo", str(subdir), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["repo"]["dirty"] is False
    assert data["skill_sync"]["checked"] is True
    assert data["skill_sync"]["clean"] is False
    assert "SKILL.md" in data["skill_sync"]["diffs"]
    assert "references/extra.md" in data["skill_sync"]["missing"]
    assert data["decision"]["status"] == "needs_skill_source_sync"
    assert data["decision"]["next_safe_slice"] == "reconcile_skill_source_drift"
    for flag in BLOCKED_AUTHORITY_FLAGS:
        assert data["decision"][flag] is False

    brief = run_brief("--brief", "--repo", str(repo), "--installed-skill", str(installed_skill)).stdout
    assert "skill-sync: drift missing=1 extra=0 diffs=1" in brief


def test_relay_brief_reports_repo_only_skill_drift_with_repo_to_installed_hint(tmp_path):
    repo = tmp_path / "repo"
    repo_skill = repo / "skills" / "busdriver-relay"
    repo_skill.mkdir(parents=True)
    (repo_skill / "SKILL.md").write_text("# repo skill\n")
    (repo_skill / "repo-only.md").write_text("repo-only\n")
    init_git_repo(repo)

    installed_skill = tmp_path / "installed-skill"
    installed_skill.mkdir()
    (installed_skill / "SKILL.md").write_text("# repo skill\n")
    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["skill_sync"]["missing"] == []
    assert data["skill_sync"]["extra"] == ["repo-only.md"]
    assert data["decision"]["status"] == "needs_skill_source_sync"
    assert data["decision"]["next_safe_slice"] == "sync_repo_skill_reference_to_installed_skill"


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


def test_relay_brief_status_probe_uses_colorless_porcelain(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("before\n")
    init_git_repo(repo, tracked)
    subprocess.run(["git", "config", "color.status", "always"], cwd=repo, text=True, capture_output=True, check=True)
    untracked = repo / "new.txt"
    untracked.write_text("new\n")

    installed_skill = tmp_path / "installed-skill"
    installed_skill.mkdir()
    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["repo"]["dirty"] is True
    assert data["repo"]["porcelain"] == ["?? new.txt"]
    assert "\x1b[" not in "".join(data["repo"]["porcelain"])


def test_relay_brief_strips_inherited_git_identity_environment(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    other_file = other / "other.txt"
    other_file.write_text("clean\n")
    init_git_repo(other, other_file)

    target = tmp_path / "target"
    repo_skill = target / "skills" / "busdriver-relay"
    repo_skill.mkdir(parents=True)
    (repo_skill / "SKILL.md").write_text("# repo skill\n")
    tracked = target / "tracked.txt"
    tracked.write_text("before\n")
    init_git_repo(target)
    tracked.write_text("after\n")

    installed_skill = tmp_path / "installed-skill"
    installed_skill.mkdir()
    (installed_skill / "SKILL.md").write_text("# repo skill\n")

    proc = run_brief(
        "--pretty",
        "--repo",
        str(target),
        "--installed-skill",
        str(installed_skill),
        env={"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other)},
    )
    data = json.loads(proc.stdout)

    assert data["repo"]["git_root"] == str(target)
    assert data["repo"]["dirty"] is True
    assert data["decision"]["status"] == "needs_local_reconciliation"


def test_relay_brief_blocks_when_installed_skill_unverified(tmp_path):
    repo = tmp_path / "repo"
    repo_skill = repo / "skills" / "busdriver-relay"
    repo_skill.mkdir(parents=True)
    (repo_skill / "SKILL.md").write_text("# repo skill\n")
    init_git_repo(repo)

    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(tmp_path / "missing-skill"))
    data = json.loads(proc.stdout)

    assert data["ok"] is False
    assert data["skill_sync"]["checked"] is False
    assert data["skill_sync"]["reason"] == "installed_skill_missing"
    assert data["decision"]["status"] == "blocked_unverified_skill_sync"
    assert data["decision"]["next_safe_slice"] == "inspect_installed_skill_path"
    for flag in BLOCKED_AUTHORITY_FLAGS:
        assert data["decision"][flag] is False


def test_relay_brief_blocks_when_installed_skill_path_is_not_directory(tmp_path):
    repo = tmp_path / "repo"
    repo_skill = repo / "skills" / "busdriver-relay"
    repo_skill.mkdir(parents=True)
    (repo_skill / "SKILL.md").write_text("# repo skill\n")
    init_git_repo(repo)

    installed_skill_file = tmp_path / "installed-skill-file"
    installed_skill_file.write_text("not a directory\n")
    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(installed_skill_file))
    data = json.loads(proc.stdout)

    assert data["ok"] is False
    assert data["skill_sync"]["checked"] is False
    assert data["skill_sync"]["reason"] == "installed_skill_not_directory"
    assert data["decision"]["status"] == "blocked_unverified_skill_sync"
    assert data["decision"]["next_safe_slice"] == "inspect_installed_skill_path"


def test_relay_brief_mixed_missing_and_diff_skill_drift_requires_reconcile(tmp_path):
    repo = tmp_path / "repo"
    repo_skill = repo / "skills" / "busdriver-relay"
    repo_skill.mkdir(parents=True)
    (repo_skill / "SKILL.md").write_text("# repo skill\n")
    init_git_repo(repo)

    installed_skill = tmp_path / "installed-skill"
    reference_dir = installed_skill / "references"
    reference_dir.mkdir(parents=True)
    (installed_skill / "SKILL.md").write_text("# divergent installed skill\n")
    (reference_dir / "installed-only.md").write_text("installed-only\n")

    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["skill_sync"]["missing"] == ["references/installed-only.md"]
    assert data["skill_sync"]["diffs"] == ["SKILL.md"]
    assert data["decision"]["status"] == "needs_skill_source_sync"
    assert data["decision"]["next_safe_slice"] == "reconcile_skill_source_drift"


def test_relay_brief_blocks_when_repo_skill_source_missing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("content\n")
    init_git_repo(repo, tracked)

    installed_skill = tmp_path / "installed-skill"
    installed_skill.mkdir()
    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["ok"] is False
    assert data["skill_sync"]["checked"] is False
    assert data["skill_sync"]["reason"] == "repo_skill_missing"
    assert data["decision"]["status"] == "blocked_unverified_skill_sync"
    assert data["decision"]["next_safe_slice"] == "inspect_repo_skill_source"


def test_relay_brief_uses_git_root_for_skill_sync_when_repo_is_subdirectory(tmp_path):
    repo = tmp_path / "repo"
    repo_skill = repo / "skills" / "busdriver-relay"
    repo_skill.mkdir(parents=True)
    (repo_skill / "SKILL.md").write_text("# repo skill\n")
    subdir = repo / "subdir"
    subdir.mkdir()
    init_git_repo(repo)

    installed_skill = tmp_path / "installed-skill"
    installed_skill.mkdir()
    (installed_skill / "SKILL.md").write_text("# repo skill\n")
    proc = run_brief("--pretty", "--repo", str(subdir), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["repo"]["git_ok"] is True
    assert data["repo"]["git_root"] == str(repo)
    assert data["skill_sync"]["checked"] is True
    assert data["skill_sync"]["clean"] is True


def test_relay_brief_contract_status_comes_from_requested_repo(tmp_path):
    repo, installed_skill = make_repo_with_skill(tmp_path)
    init_git_repo(repo)

    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["repo"]["git_root"] == str(repo)
    assert data["skill_sync"]["clean"] is True
    assert data["finalization_contract_status"]["ok"] is False
    assert data["finalization_contract_status"]["error"] == "contract_status_missing"
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked_unknown_contract_state"


def test_relay_brief_contract_status_helper_runs_from_requested_repo_root(tmp_path):
    repo, installed_skill = make_repo_with_skill(tmp_path)
    scripts = repo / "scripts"
    scripts.mkdir()
    contract_helper = scripts / "hermes-busdriver-finalization-contract-status"
    contract_helper.write_text(
        "import json\n"
        "from pathlib import Path\n"
        "cwd = str(Path.cwd())\n"
        "print(json.dumps({\n"
        "    'ok': True,\n"
        "    'schema': 'hermes-busdriver-finalization-contract-status/v0',\n"
        "    'read_only': True,\n"
        "    'current_policy': cwd,\n"
        "    'decision': {'status': 'policy_blocked'},\n"
        "    'remaining_work': [{'status': 'policy_blocked', 'capability_allowed': False}],\n"
        "    'summary': {\n"
        "        'remaining_work_count': 1,\n"
        "        'policy_blocked_count': 1,\n"
        "        'capability_allowed_count': 0,\n"
        "    },\n"
        "}))\n"
    )
    subdir = repo / "subdir"
    subdir.mkdir()
    init_git_repo(repo)

    proc = run_brief("--pretty", "--repo", str(subdir), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["repo"]["git_root"] == str(repo)
    assert data["repo"]["dirty"] is False
    assert data["skill_sync"]["clean"] is True
    assert data["finalization_contract_status"] == {
        "ok": True,
        "schema": "hermes-busdriver-finalization-contract-status/v0",
        "read_only": True,
        "current_policy": str(repo),
        "decision_status": "policy_blocked",
        "remaining_work_count": 1,
        "policy_blocked_count": 1,
        "capability_allowed_count": 0,
    }
    assert data["ok"] is True
    assert data["decision"]["status"] == "idle_clean_policy_blocked_finalization"


def test_relay_brief_rejects_unknown_contract_status_schema(tmp_path):
    repo, installed_skill = make_repo_with_skill(tmp_path)
    scripts = repo / "scripts"
    scripts.mkdir()
    contract_helper = scripts / "hermes-busdriver-finalization-contract-status"
    contract_helper.write_text(
        "import json\n"
        "print(json.dumps({\n"
        "    'ok': True,\n"
        "    'schema': 'fake-contract-status/v0',\n"
        "    'read_only': True,\n"
        "    'decision': {'status': 'policy_blocked'},\n"
        "    'summary': {\n"
        "        'remaining_work_count': 1,\n"
        "        'policy_blocked_count': 1,\n"
        "        'capability_allowed_count': 0,\n"
        "    },\n"
        "}))\n"
    )
    init_git_repo(repo)

    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["finalization_contract_status"]["ok"] is False
    assert data["finalization_contract_status"]["error"] == "contract_status_schema_invalid"
    assert data["finalization_contract_status"]["schema"] == "fake-contract-status/v0"
    assert data["finalization_contract_status"]["expected_schema"] == "hermes-busdriver-finalization-contract-status/v0"
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked_unknown_contract_state"


def test_relay_brief_blocks_when_repo_git_state_unverified(tmp_path):
    repo = tmp_path / "not-a-repo"
    repo.mkdir()
    installed_skill = tmp_path / "installed-skill"
    installed_skill.mkdir()

    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["ok"] is False
    assert data["repo"]["git_ok"] is False
    assert data["repo"]["status_available"] is False
    assert data["decision"]["status"] == "blocked_unverified_repo_state"
    assert data["decision"]["next_safe_slice"] == "inspect_repo_git_status"


def test_relay_brief_ok_false_when_repo_git_unverified_even_if_skill_sync_checked(tmp_path):
    repo = tmp_path / "not-a-git-repo"
    repo_skill = repo / "skills" / "busdriver-relay"
    repo_skill.mkdir(parents=True)
    (repo_skill / "SKILL.md").write_text("# repo skill\n")

    installed_skill = tmp_path / "installed-skill"
    installed_skill.mkdir()
    (installed_skill / "SKILL.md").write_text("# repo skill\n")

    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["repo"]["git_ok"] is False
    assert data["skill_sync"]["checked"] is True
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked_unverified_repo_state"


def test_relay_brief_missing_repo_path_returns_structured_unverified_repo_state(tmp_path):
    installed_skill = tmp_path / "installed-skill"
    installed_skill.mkdir()

    proc = run_brief("--pretty", "--repo", str(tmp_path / "missing-repo"), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["ok"] is False
    assert data["repo"]["git_ok"] is False
    assert data["repo"]["status_available"] is False
    assert data["decision"]["status"] == "blocked_unverified_repo_state"


def test_relay_brief_treats_empty_installed_skill_env_as_unset():
    proc = run_brief("--pretty", env={"HERMES_BUSDRIVER_INSTALLED_SKILL_DIR": ""})
    data = json.loads(proc.stdout)

    assert data["skill_sync"]["path"].endswith("/.hermes/skills/autonomous-ai-agents/busdriver-relay")
    assert data["skill_sync"]["path"] != data["repo"]["path"]
