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
    "pi-adapter-proof",
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
    assert data["finalization_contract_status"]["decision_status"] == "partial_policy_blocked"
    assert data["finalization_contract_status"]["capability_allowed_count"] == 0
    assert {task["id"] for task in data["roadmap_tasks"]} == EXPECTED_TASKS

    for flag in BLOCKED_AUTHORITY_FLAGS:
        assert data["authority"][flag] is False
        assert data["decision"][flag] is False

    task_by_id = {task["id"]: task for task in data["roadmap_tasks"]}
    assert task_by_id["adr0005-unlock-contract"]["status"] == "gated_executor_slice_implemented_remaining_authority_policy_blocked"
    assert task_by_id["mutating-pr-grind-fix-loop"]["status"] == "read_only_design_complete_mutating_loop_policy_blocked"
    assert task_by_id["marker-interop-contract"]["status"] == "design_contract_complete_marker_write_policy_blocked"
    assert task_by_id["pi-adapter-proof"]["status"] == "historical_pi_adapter_proof_retained_codex_primary_metadata_only"
    assert task_by_id["pi-adapter-proof"]["safe_next"] == "use_codex_primary_metadata_only_keep_agent_dispatch_blocked"
    assert task_by_id["status-ux-layer"]["status"] == "implemented_by_hermes_busdriver_relay_brief"


def test_relay_brief_text_is_telegram_friendly_and_does_not_claim_authority(tmp_path):
    installed_skill = tmp_path / "installed-skill"
    installed_skill.mkdir()

    proc = run_brief("--brief", "--installed-skill", str(installed_skill))
    text = proc.stdout

    assert "Hermes Busdriver Relay brief" in text
    assert "skill-sync:" in text
    assert "contract: partial_policy_blocked" in text
    assert "Pi adapter proof" in text
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


def test_relay_brief_contract_status_does_not_come_from_requested_repo(tmp_path):
    """The contract helper answers for THIS relay, so a bare --repo cannot make it unavailable.

    Replaces the r25 test that asserted the opposite. It expected `contract_status_missing`
    whenever the target repo had no scripts/ dir — which only held because the brief resolved the
    helper under the untrusted --repo. That expectation was the trust-boundary bug written down
    as a contract.
    """
    repo, installed_skill = make_repo_with_skill(tmp_path)
    init_git_repo(repo)

    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["repo"]["git_root"] == str(repo)
    assert data["skill_sync"]["clean"] is True
    assert data["finalization_contract_status"]["ok"] is True
    assert data["finalization_contract_status"]["schema"] == "hermes-busdriver-finalization-contract-status/v0"
    assert data["ok"] is True
    assert data["decision"]["status"].startswith("idle_clean")


def test_relay_brief_contract_status_helper_ignores_repo_root_cwd(tmp_path):
    """A subdirectory --repo still reports the same trusted contract state."""
    repo, installed_skill = make_repo_with_skill(tmp_path)
    subdir = repo / "subdir"
    subdir.mkdir()
    (subdir / "keep.txt").write_text("x\n")
    init_git_repo(repo)

    proc = run_brief("--pretty", "--repo", str(subdir), "--installed-skill", str(installed_skill))
    data = json.loads(proc.stdout)

    assert data["repo"]["git_root"] == str(repo)
    assert data["repo"]["dirty"] is False
    assert data["finalization_contract_status"]["ok"] is True
    assert data["finalization_contract_status"]["decision_status"]
    assert data["ok"] is True


def test_relay_brief_rejects_unknown_contract_status_schema():
    """Schema rejection is now unreachable via a repo-authored helper, so drive the validator.

    r25 proved this by planting a fake helper under --repo and letting the brief execute it. The
    coverage is still worth keeping; the delivery mechanism was the vulnerability.
    """
    import runpy

    ns = runpy.run_path(str(SCRIPT))
    proc = subprocess.CompletedProcess(
        ["helper"],
        0,
        json.dumps({
            "ok": True,
            "schema": "fake-contract-status/v0",
            "read_only": True,
            "decision": {"status": "policy_blocked"},
            "summary": {"remaining_work_count": 1, "policy_blocked_count": 1, "capability_allowed_count": 0},
        }),
        "",
    )

    result = ns["_contract_status_payload"](proc)

    assert result["ok"] is False
    assert result["error"] == "contract_status_schema_invalid"
    assert result["schema"] == "fake-contract-status/v0"
    assert result["expected_schema"] == "hermes-busdriver-finalization-contract-status/v0"
    assert ns["decide"](
        {"git_ok": True, "observed": True, "status_available": True, "dirty": False},
        {"checked": True, "clean": True},
        result,
    )["status"] == "blocked_unknown_contract_state"


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


# --- v16-r26A item 2: --repo is untrusted; never execute its scripts, never idle-clean unobserved ---


def test_relay_brief_never_executes_contract_helper_from_untrusted_repo(tmp_path):
    """`--repo` names a repository this helper does not trust. Its scripts/ is attacker code."""
    repo, installed_skill = make_repo_with_skill(tmp_path)
    scripts = repo / "scripts"
    scripts.mkdir()
    sentinel = tmp_path / "pwned"
    hostile = scripts / "hermes-busdriver-finalization-contract-status"
    hostile.write_text(
        "import json, pathlib\n"
        f"pathlib.Path({str(sentinel)!r}).write_text('executed')\n"
        "print(json.dumps({\n"
        "    'ok': True,\n"
        "    'schema': 'hermes-busdriver-finalization-contract-status/v0',\n"
        "    'read_only': True,\n"
        "    'decision': {'status': 'policy_blocked'},\n"
        "    'summary': {'remaining_work_count': 1, 'policy_blocked_count': 1,\n"
        "                'implemented_count': 0, 'capability_allowed_count': 0},\n"
        "}))\n"
    )
    hostile.chmod(0o755)
    init_git_repo(repo)

    proc = run_brief("--pretty", "--repo", str(repo), "--installed-skill", str(installed_skill))

    assert not sentinel.exists(), "relay-brief executed a script from the untrusted --repo"
    data = json.loads(proc.stdout)
    contract = data["finalization_contract_status"]
    assert contract.get("helper_path") != str(hostile)
    # The trusted sibling is this checkout's own, and it answers for THIS relay's contract.
    assert contract["ok"] is True
    assert contract["schema"] == "hermes-busdriver-finalization-contract-status/v0"


def test_relay_brief_contract_helper_integrity_failure_fails_closed(tmp_path, monkeypatch):
    import runpy

    ns = runpy.run_path(str(SCRIPT))
    globals_ = ns["contract_status_summary"].__globals__
    monkeypatch.setitem(globals_, "TRUSTED_CONTRACT_STATUS_SHA256", "0" * 64)

    result = ns["contract_status_summary"]()

    assert result["ok"] is False
    assert result["error"] == "contract_status_integrity_failed"


def test_relay_brief_executes_verified_contract_bytes_after_retained_path_replacement(tmp_path, monkeypatch):
    import runpy

    ns = runpy.run_path(str(SCRIPT))
    globals_ = ns["contract_status_summary"].__globals__
    real_run = globals_["run"]
    attacker_ran = tmp_path / "attacker-ran"
    attacker = (
        "import json, pathlib\n"
        f"pathlib.Path({str(attacker_ran)!r}).write_text('executed')\n"
        "print(json.dumps({'ok': True, 'schema': 'hermes-busdriver-finalization-contract-status/v0', "
        "'read_only': True, 'decision': {'status': 'policy_blocked'}, "
        "'summary': {'remaining_work_count': 1, 'policy_blocked_count': 1, "
        "'implemented_count': 0, 'capability_allowed_count': 0}}))\n"
    )
    swapped = []

    def replace_retained_then_run(argv, cwd, timeout=20, stdin_bytes=None):
        for value in argv:
            candidate = Path(str(value))
            if candidate.name == "hermes-busdriver-finalization-contract-status" and candidate.exists():
                swapped.append(True)
                candidate.unlink()
                candidate.write_text(attacker)
                candidate.chmod(0o500)
                break
        if stdin_bytes is None:
            return real_run(argv, cwd, timeout)
        return real_run(argv, cwd, timeout, stdin_bytes=stdin_bytes)

    monkeypatch.setitem(globals_, "run", replace_retained_then_run)

    result = ns["contract_status_summary"]()

    assert swapped, "the retained-path replacement was not injected"
    assert result["ok"] is True
    assert not attacker_ran.exists(), "relay-brief executed attacker-replaced retained pathname"


def _brief_run_failing(label: str, returncode: int, stderr: str, real_run):
    def fake_run(argv, cwd, timeout=20):
        if label in argv:
            return subprocess.CompletedProcess(argv, returncode, "", stderr)
        return real_run(argv, cwd, timeout)
    return fake_run


def test_relay_brief_failed_head_observation_never_reports_idle_clean(tmp_path, monkeypatch):
    import runpy

    repo, installed_skill = make_repo_with_skill(tmp_path)
    init_git_repo(repo)

    ns = runpy.run_path(str(SCRIPT))
    globals_ = ns["repo_summary"].__globals__
    monkeypatch.setitem(globals_, "run", _brief_run_failing("HEAD", 128, "fatal: bad object", globals_["run"]))

    state = ns["repo_summary"](repo)

    assert state.get("observed") is not True, "HEAD failure left the repo marked observed"
    decision = ns["decide"](state, {"checked": True, "clean": True}, {"ok": True, "policy_blocked_count": 1})
    assert not str(decision["status"]).startswith("idle_clean"), "idle-clean decided on an unobserved HEAD"


def test_relay_brief_failed_origin_observation_never_reports_idle_clean(tmp_path, monkeypatch):
    import runpy

    repo, installed_skill = make_repo_with_skill(tmp_path)
    init_git_repo(repo)

    ns = runpy.run_path(str(SCRIPT))
    globals_ = ns["repo_summary"].__globals__
    monkeypatch.setitem(globals_, "run", _brief_run_failing("--show-current", 124, "timed out after 20s", globals_["run"]))

    state = ns["repo_summary"](repo)

    assert state.get("observed") is not True
    decision = ns["decide"](state, {"checked": True, "clean": True}, {"ok": True, "policy_blocked_count": 1})
    assert not str(decision["status"]).startswith("idle_clean")
