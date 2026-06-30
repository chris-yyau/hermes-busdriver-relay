import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "scripts" / "hermes-busdriver-delivery-status"
PHASE0_STATUS = ROOT / "scripts" / "hermes-busdriver-status"
LOCK = ROOT / "scripts" / "hermes-busdriver-lock"


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


def invoke(repo: Path, plugin: Path, *extra: str, cwd: Path | None = None) -> dict:
    cp = run([sys.executable, str(STATUS), "--repo", str(repo), "--plugin-root", str(plugin), "--no-lock-status", "--no-agent-runs", *extra], cwd=cwd)
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return json.loads(cp.stdout)


def invoke_with_lock_status(repo: Path, plugin: Path, state: Path, *extra: str) -> dict:
    cp = run([sys.executable, str(STATUS), "--repo", str(repo), "--plugin-root", str(plugin), "--state-dir", str(state), "--no-agent-runs", *extra])
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return json.loads(cp.stdout)


def litmus_status_fixture(
    path: Path,
    *,
    repo: Path | None = None,
    status: str = "stale_or_missing",
    ok: object = True,
    authority_safe: bool = True,
    authority_true_key: str = "finalization_allowed",
    malicious_sentinel: str | None = None,
) -> Path:
    false_flags = {
        "finalization_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pr_allowed": False,
        "merge_allowed": False,
        "deploy_allowed": False,
        "release_allowed": False,
        "publish_allowed": False,
        "marker_write_allowed": False,
    }
    decision_flags = dict(false_flags)
    if not authority_safe:
        decision_flags[authority_true_key] = True
    state_dir = path.parent / ".claude"

    def git_value(*args: str) -> str:
        if repo is None:
            return ""
        return run(["git", *args], repo).stdout.strip()

    repo_summary = {
        "root": str(repo.resolve()) if repo is not None else str(path.parent),
        "branch": git_value("branch", "--show-current") or "main",
        "head": git_value("rev-parse", "HEAD") or "abc123",
        "head_timestamp": 1,
        "base_ref": "origin/main",
        "branch_diff_hash": None,
    }
    state_summary = {"path": str(state_dir), "exists": False, "is_symlink": False, "has_symlink_component": False}
    markers = {
        "litmus_passed": {"path": str(state_dir / "litmus-passed.local"), "exists": False, "fresh_for_head": False},
        "pr_codex_lead": {"path": str(state_dir / "pr-codex-lead.local.json"), "exists": False, "fresh_for_branch_diff": False},
        "pr_backstop_verdict": {"path": str(state_dir / "pr-backstop-verdict.local.json"), "exists": False, "fresh_for_branch_diff": False},
        "pr_review_passed": {"path": str(state_dir / "pr-review-passed.local"), "exists": False, "fresh_for_branch_diff": False},
    }
    warnings: list[str] = []
    blockers: list[str] = []
    if malicious_sentinel:
        repo_summary["root"] = f"{path.parent}/repo-token={malicious_sentinel}"
        repo_summary["unknown_secret"] = malicious_sentinel
        state_summary["path"] = f"{state_dir}/api_key={malicious_sentinel}"
        state_summary["unknown_secret"] = malicious_sentinel
        markers["unknown_marker_secret"] = {"path": malicious_sentinel, "exists": True, "secret": malicious_sentinel}
        markers["litmus_passed"]["path"] = f"{state_dir}/litmus-passed.local?token={malicious_sentinel}"
        markers["litmus_passed"]["read_error"] = f"password={malicious_sentinel}"
        markers["litmus_passed"]["stat_error"] = f"stat token={malicious_sentinel}"
        markers["litmus_passed"]["unknown_secret"] = malicious_sentinel
        warnings = [f"warning {malicious_sentinel}"]
        blockers = [f"blocker {malicious_sentinel}"]
    path.write_text(json.dumps({
        "schema": "hermes-busdriver-litmus-status/v0",
        "read_only": True,
        "ok": ok,
        "repo": repo_summary,
        "state_dir": state_summary,
        "markers": markers,
        "decision": {"status": status, "warnings": warnings, "blockers": blockers, **decision_flags, "not_busdriver_native_claude_runtime": True, "unexpected_secret": malicious_sentinel},
    }))
    return path


def drift_baseline_fixture(path: Path, plugin: Path) -> Path:
    cp = run([sys.executable, str(PHASE0_STATUS), "--plugin-root", str(plugin)])
    assert cp.returncode == 0, cp.stderr + cp.stdout
    current = json.loads(cp.stdout)
    path.write_text(json.dumps({
        "status_schema": "hermes-busdriver-status/v0",
        "package": {"version": current["package"]["version"]},
        "critical_file_hashes": current["critical_file_hashes"],
    }))
    return path


def assert_no_delivery_authority(authority: dict) -> None:
    for key in [
        "finalization_allowed",
        "commit_allowed",
        "push_allowed",
        "pr_allowed",
        "merge_allowed",
        "deploy_allowed",
        "release_allowed",
        "publish_allowed",
        "marker_write_allowed",
    ]:
        assert authority[key] is False


def relay_config(path: Path, route: object) -> Path:
    path.write_text(json.dumps({
        "coding_agent": "opencode",
        "avoid_coding_agent_for_review": True,
        "routes": {"relay.pr.backstop": route},
    }))
    return path


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
    assert_no_delivery_authority(data["decision"])
    assert snapshot_files(repo) == before_repo
    assert snapshot_files(plugin) == before_plugin


def test_untracked_files_are_not_reported_as_unstaged(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "new.txt").write_text("new\n")

    data = invoke(repo, plugin)

    assert data["repo"]["untracked_entries"] == ["?? new.txt"]
    assert data["repo"]["unstaged_entries"] == []


def test_dirty_draft_includes_read_only_litmus_status_stale_warning(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "litmus-status.json", repo=repo)

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["decision"]["status"] == "draft_changes_need_busdriver_finalization"
    assert "litmus_pre_pr_stale_or_missing" in data["decision"]["warnings"]
    assert data["litmus_status"]["available"] is True
    assert data["litmus_status"]["ok"] is True
    assert data["litmus_status"]["summary"]["schema"] == "hermes-busdriver-litmus-status/v0"
    assert data["litmus_status"]["summary"]["read_only"] is True
    assert data["litmus_status"]["summary"]["decision"]["status"] == "stale_or_missing"
    assert data["litmus_status"]["summary"]["decision"]["finalization_allowed"] is False
    assert data["litmus_status"]["summary"]["decision"]["marker_write_allowed"] is False
    assert data["litmus_status"]["summary"]["markers"]["litmus_passed"]["exists"] is False
    assert_no_delivery_authority(data["decision"])


def test_delivery_status_accepts_compatible_drift_baseline_as_phase0_evidence(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    baseline = drift_baseline_fixture(tmp_path / "baseline.json", plugin)

    data = invoke(repo, plugin, "--drift-baseline", str(baseline))

    drift = data["phase0_status"]["busdriver_drift"]
    assert drift["status"] == "compatible"
    assert drift["finalization_compatible"] is True
    assert "busdriver_drift_incompatible" not in data["decision"]["blockers"]
    assert data["decision"]["status"] == "draft_changes_need_busdriver_finalization"
    assert_no_delivery_authority(data["decision"])


def test_phase0_status_forwards_requested_repo_even_when_parent_repo_status_failed(monkeypatch, tmp_path: Path):
    mod = __import__("runpy").run_path(str(STATUS))
    plugin = fake_busdriver(tmp_path / "busdriver")
    requested_repo = tmp_path / "not-a-git-repo"
    requested_repo.mkdir()
    baseline = tmp_path / "baseline.json"
    baseline.write_text("{}\n")
    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        payload = {
            "status_schema": "hermes-busdriver-status/v0",
            "read_only": True,
            "repo": {"path": str(requested_repo), "is_git_repo": False},
            "plugin_root": {"path": str(plugin), "exists": True},
            "busdriver_drift": {"status": "baseline_invalid", "finalization_compatible": False},
        }
        return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")

    monkeypatch.setitem(mod["run_phase0_status"].__globals__, "run", fake_run)
    args = __import__("types").SimpleNamespace(
        repo=str(requested_repo),
        drift_baseline=str(baseline),
        phase0_status_timeout=7,
        busdriver_state_dir_name=None,
        state_dir=None,
    )

    data = mod["run_phase0_status"](args, {"ok": False, "path": str(requested_repo)}, {"ok": True, "plugin_root": str(plugin)})

    cmd = captured["cmd"]
    assert data["status_schema"] == "hermes-busdriver-status/v0"
    assert "--repo" in cmd
    assert cmd[cmd.index("--repo") + 1] == str(requested_repo)
    assert captured["cwd"] is None
    assert captured["timeout"] == 7


def test_delivery_status_preserves_relative_drift_baseline_cwd_semantics(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    caller = tmp_path / "caller"
    caller.mkdir()
    (repo / "src.txt").write_text("draft\n")
    drift_baseline_fixture(caller / "baseline.json", plugin)
    (repo / "baseline.json").write_text("{not-json\n")

    data = invoke(repo, plugin, "--drift-baseline", "baseline.json", cwd=caller)

    drift = data["phase0_status"]["busdriver_drift"]
    assert drift["baseline_path"] == str(caller / "baseline.json")
    assert drift["status"] == "compatible"
    assert drift["finalization_compatible"] is True
    assert data["decision"]["status"] == "draft_changes_need_busdriver_finalization"
    assert "busdriver_drift_incompatible" not in data["decision"]["blockers"]


def test_delivery_status_blocks_when_drift_baseline_is_drifted(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    baseline = drift_baseline_fixture(tmp_path / "baseline.json", plugin)
    (plugin / "package.json").write_text('{"version":"9.99.0"}\n')

    data = invoke(repo, plugin, "--drift-baseline", str(baseline))

    drift = data["phase0_status"]["busdriver_drift"]
    assert drift["status"] == "drifted"
    assert drift["finalization_compatible"] is False
    assert data["decision"]["status"] == "blocked"
    assert "busdriver_drift_incompatible" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


@pytest.mark.parametrize("baseline_name, baseline_content, expected_status", [
    ("invalid-baseline.json", "{not-json\n", "baseline_invalid"),
    ("missing-baseline.json", None, "baseline_missing"),
])
def test_delivery_status_blocks_when_drift_baseline_is_invalid_or_missing(tmp_path: Path, baseline_name: str, baseline_content: str | None, expected_status: str):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    baseline = tmp_path / baseline_name
    if baseline_content is not None:
        baseline.write_text(baseline_content)

    data = invoke(repo, plugin, "--drift-baseline", str(baseline))

    drift = data["phase0_status"]["busdriver_drift"]
    assert drift["status"] == expected_status
    assert drift["finalization_compatible"] is False
    assert data["decision"]["status"] == "blocked"
    assert "busdriver_drift_incompatible" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


@pytest.mark.parametrize("identity_error", ["root", "branch", "head", "missing_branch", "missing_head"])
def test_litmus_status_repo_identity_mismatch_fails_closed(tmp_path: Path, identity_error: str):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "wrong-repo-litmus-status.json", repo=repo, status="commit_litmus_fresh")
    payload = json.loads(litmus.read_text())
    if identity_error == "root":
        payload["repo"]["root"] = str(tmp_path / "other-repo")
    elif identity_error == "branch":
        payload["repo"]["branch"] = "other-branch"
    elif identity_error == "head":
        payload["repo"]["head"] = "deadbeef"
    elif identity_error == "missing_branch":
        payload["repo"].pop("branch")
    elif identity_error == "missing_head":
        payload["repo"].pop("head")
    litmus.write_text(json.dumps(payload))

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_schema_invalid"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_schema_invalid" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_unavailable_blocks_delivery_handoff(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    missing_litmus = tmp_path / "missing-litmus-status"

    data = invoke(repo, plugin, "--litmus-status-script", str(missing_litmus))

    assert data["litmus_status"]["available"] is False
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_unavailable" in data["decision"]["blockers"]
    assert "litmus_status_unavailable" not in data["decision"]["warnings"]
    assert_no_delivery_authority(data["decision"])


def test_blocked_litmus_status_blocks_delivery_handoff(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "blocked-litmus-status.json", repo=repo, status="blocked")

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is True
    assert data["litmus_status"]["summary"]["decision"]["status"] == "blocked"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_not_fresh" in data["decision"]["blockers"]
    assert "litmus_status_not_fresh" not in data["decision"]["warnings"]
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_ok_false_blocks_delivery_handoff(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "not-ok-litmus-status.json", repo=repo, status="commit_litmus_fresh", ok=False)

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["summary"]["decision"]["status"] == "commit_litmus_fresh"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_not_fresh" in data["decision"]["blockers"]
    assert "litmus_status_not_fresh" not in data["decision"]["warnings"]
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_non_boolean_ok_fails_closed_even_when_fresh(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "malformed-ok-litmus-status.json", repo=repo, status="commit_litmus_fresh", ok="false")

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_schema_invalid"
    assert data["litmus_status"]["summary"]["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_schema_invalid" in data["decision"]["blockers"]
    assert "litmus_status_not_fresh" not in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_unrecognized_decision_status_fails_closed_even_when_ok(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "unknown-status-litmus-status.json", repo=repo, status="surprise_fresh", ok=True)

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_schema_invalid"
    assert data["litmus_status"]["summary"]["decision"]["status"] == "surprise_fresh"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_schema_invalid" in data["decision"]["blockers"]
    assert "litmus_status_not_fresh" not in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


def test_unsafe_litmus_status_output_blocks_delivery_handoff(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "unsafe-litmus-status.json", repo=repo, authority_safe=False)

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_authority_flags_unsafe"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_authority_flags_unsafe" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


@pytest.mark.parametrize(
    "authority_key",
    [
        "finalization_allowed",
        "commit_allowed",
        "push_allowed",
        "pr_allowed",
        "merge_allowed",
        "deploy_allowed",
        "release_allowed",
        "publish_allowed",
        "marker_write_allowed",
    ],
)
def test_delivery_rejects_litmus_status_with_finalization_authority(tmp_path: Path, authority_key: str):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(
        tmp_path / f"unsafe-{authority_key}-litmus-status.json",
        repo=repo,
        authority_safe=False,
        authority_true_key=authority_key,
    )

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_authority_flags_unsafe"
    assert data["litmus_status"]["summary"]["decision"][authority_key] is False
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_authority_flags_unsafe" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


@pytest.mark.parametrize(
    "payload_update",
    [
        lambda payload: payload.update({"commit_allowed": True}),
        lambda payload: payload["markers"]["pr_codex_lead"].update({"merge_allowed": True}),
        lambda payload: payload["markers"]["pr_backstop_verdict"].update({"authority": {"pr_allowed": True}}),
        lambda payload: payload["markers"]["pr_review_passed"].update({"nested": [{"authority": {"push_allowed": True}}]}),
        lambda payload: payload.update({"programmatic_execution_allowed": True}),
    ],
)
def test_delivery_rejects_litmus_status_with_nested_or_top_level_authority(
    tmp_path: Path,
    payload_update,
):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "nested-authority-litmus-status.json", repo=repo)
    payload = json.loads(litmus.read_text())
    payload_update(payload)
    litmus.write_text(json.dumps(payload))

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_authority_flags_unsafe"
    assert data["litmus_status"]["summary"]["authority_safe"] is False
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_authority_flags_unsafe" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


def test_delivery_rejects_fresh_litmus_status_with_recursive_authority(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "fresh-recursive-authority-litmus-status.json", repo=repo, status="pr_review_fresh")
    payload = json.loads(litmus.read_text())
    payload["markers"]["pr_codex_lead"].update({"exists": True, "fresh_for_branch_diff": True})
    payload["markers"]["pr_backstop_verdict"].update({"exists": True, "fresh_for_branch_diff": True})
    payload["markers"]["pr_review_passed"].update({"exists": True, "fresh_for_branch_diff": True})
    payload["markers"]["pr_backstop_verdict"]["authority"] = {"pr_allowed": True}
    litmus.write_text(json.dumps(payload))

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_authority_flags_unsafe"
    assert data["litmus_status"]["summary"]["authority_safe"] is False
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_authority_flags_unsafe" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


def test_litmus_authority_scan_fails_closed_on_excessive_list_depth() -> None:
    mod = __import__("runpy").run_path(str(STATUS))
    payload: dict[str, Any] = {"nested": []}
    cursor = payload["nested"]
    for _ in range(1105):
        child: list[Any] = []
        cursor.append(child)
        cursor = child

    assert mod["litmus_payload_authority_flags_false"](payload) is False


def test_litmus_authority_scan_rejects_authority_nested_in_list() -> None:
    mod = __import__("runpy").run_path(str(STATUS))
    payload: dict[str, Any] = {"nested": [{"authority": {"pr_allowed": True}}]}

    assert mod["litmus_payload_authority_flags_false"](payload) is False


def test_litmus_authority_scan_fails_closed_on_excessive_depth() -> None:
    mod = __import__("runpy").run_path(str(STATUS))
    payload: dict[str, Any] = {}
    cursor = payload
    for _ in range(1105):
        child: dict[str, Any] = {}
        cursor["nested"] = child
        cursor = child

    assert mod["litmus_payload_authority_flags_false"]({"root": payload}) is False


def test_delivery_litmus_status_summary_sanitizes_untrusted_evidence(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    sentinel = "ghp_" + "D" * 36
    litmus = litmus_status_fixture(tmp_path / "malicious-litmus-status.json", repo=repo, malicious_sentinel=sentinel)

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    payload = json.dumps(data)
    summary = data["litmus_status"]["summary"]
    litmus_marker = summary["markers"]["litmus_passed"]
    assert sentinel not in payload
    assert set(summary["repo"]) == {"root", "branch", "head", "head_timestamp", "base_ref", "branch_diff_hash"}
    assert set(summary["state_dir"]) == {"path", "exists", "is_symlink", "has_symlink_component"}
    assert set(summary["markers"]) == {"litmus_passed", "pr_codex_lead", "pr_backstop_verdict", "pr_review_passed"}
    assert "unknown_secret" not in litmus_marker
    assert "[REDACTED]" in summary["repo"]["root"]
    assert "[REDACTED]" in summary["state_dir"]["path"]
    assert "[REDACTED]" in litmus_marker["path"]
    assert litmus_marker["read_error"] == "password=[REDACTED]"
    assert litmus_marker["stat_error"] == "stat token=[REDACTED]"
    assert summary["decision"]["warnings"] == []
    assert summary["decision"]["blockers"] == []
    assert "unexpected_secret" not in summary["decision"]
    assert summary["decision"]["not_busdriver_native_claude_runtime"] is True
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_summary_sanitizes_invalid_native_runtime_flag(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    sentinel = "ghp_" + "F" * 36
    litmus = litmus_status_fixture(tmp_path / "malicious-native-runtime-litmus-status.json", repo=repo)
    payload = json.loads(litmus.read_text())
    payload["decision"]["not_busdriver_native_claude_runtime"] = f"token={sentinel}"
    litmus.write_text(json.dumps(payload))

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    serialized = json.dumps(data)
    assert sentinel not in serialized
    assert data["litmus_status"]["summary"]["decision"]["not_busdriver_native_claude_runtime"] is False
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_summary_normalizes_untrusted_top_level_primitives(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    sentinel = "ghp_" + "G" * 36
    litmus = litmus_status_fixture(tmp_path / "malicious-top-level-litmus-status.json", repo=repo)
    payload = json.loads(litmus.read_text())
    payload["schema"] = f"schema token={sentinel}"
    payload["read_only"] = {"secret": sentinel}
    payload["ok"] = f"ok token={sentinel}"
    payload["decision"]["not_busdriver_native_claude_runtime"] = f"token={sentinel}"
    litmus.write_text(json.dumps(payload))

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    serialized = json.dumps(data)
    summary = data["litmus_status"]["summary"]
    assert sentinel not in serialized
    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_schema_invalid"
    assert summary["schema"] is None
    assert summary["read_only"] is False
    assert summary["ok"] is False
    assert summary["decision"]["not_busdriver_native_claude_runtime"] is False
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_parse_error_tails_are_redacted_and_bounded(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    sentinel = "ghp_" + "A" * 36
    script = tmp_path / "malformed-litmus-status.py"
    stdout_payload = "x" * 5005 + f" api_key={sentinel}\n"
    stderr_payload = "e" * 5005 + f" Authorization: Bearer {sentinel}\n"
    script.write_text(
        "import sys\n"
        f"sys.stdout.write({stdout_payload!r})\n"
        f"sys.stderr.write({stderr_payload!r})\n"
    )

    data = invoke(repo, plugin, "--litmus-status-script", str(script))

    litmus = data["litmus_status"]
    serialized = json.dumps(data)
    assert litmus["ok"] is False
    assert litmus["reason"] == "litmus_status_malformed"
    assert sentinel not in serialized
    assert len(litmus["stdout_tail"]) <= 4000
    assert len(litmus["stderr"]) <= 4000
    assert "api_key=[REDACTED]" in litmus["stdout_tail"]
    assert "Authorization: Bearer [REDACTED]" in litmus["stderr"]


def test_litmus_status_timeout_with_bytes_output_is_sanitized(monkeypatch, tmp_path: Path):
    mod = __import__("runpy").run_path(str(STATUS))
    script = tmp_path / "slow-litmus-status.py"
    script.write_text("import time\ntime.sleep(60)\n")
    sentinel = "ghp_" + "C" * 36

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd, 1, output=f"partial api_key={sentinel}\n".encode(), stderr=f"token={sentinel}\n".encode())

    monkeypatch.setattr(mod["subprocess"], "run", fake_run)
    args = __import__("types").SimpleNamespace(litmus_status_result_file=None, litmus_status_script=str(script), litmus_status_timeout=1)

    data = mod["run_litmus_status"](args, {"ok": True, "root": str(tmp_path), "branch": "main", "head": "abc123"})

    serialized = json.dumps(data)
    assert data["ok"] is False
    assert data["returncode"] == 124
    assert data["reason"] == "litmus_status_subprocess_failed"
    assert data["timeout_seconds"] == 1
    assert sentinel not in serialized
    assert len(data["stdout_tail"]) <= 4000
    assert len(data["stderr"]) <= 4000
    assert "api_key=[REDACTED]" in data["stdout_tail"]
    assert "token=[REDACTED]" in data["stderr"]


def test_run_litmus_status_forwards_busdriver_state_dir_name(monkeypatch, tmp_path: Path):
    mod = __import__("runpy").run_path(str(STATUS))
    script = tmp_path / "litmus-status.py"
    script.write_text("# fake litmus helper\n")
    captured: dict[str, list[str]] = {}
    payload = {
        "schema": "hermes-busdriver-litmus-status/v0",
        "read_only": True,
        "ok": True,
        "repo": {"root": str(tmp_path), "branch": "main", "head": "abc123", "head_timestamp": 1, "base_ref": None, "branch_diff_hash": None},
        "state_dir": {"path": str(tmp_path / ".opencode"), "exists": False, "is_symlink": False, "has_symlink_component": False},
        "markers": {},
        "decision": {
            "status": "stale_or_missing",
            "warnings": [],
            "blockers": [],
            "finalization_allowed": False,
            "commit_allowed": False,
            "push_allowed": False,
            "pr_allowed": False,
            "merge_allowed": False,
            "deploy_allowed": False,
            "release_allowed": False,
            "publish_allowed": False,
            "marker_write_allowed": False,
            "not_busdriver_native_claude_runtime": True,
        },
    }

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")

    monkeypatch.setattr(mod["subprocess"], "run", fake_run)
    args = __import__("types").SimpleNamespace(
        litmus_status_result_file=None,
        litmus_status_script=str(script),
        litmus_status_timeout=10,
        busdriver_state_dir_name=".opencode",
    )

    data = mod["run_litmus_status"](args, {"ok": True, "root": str(tmp_path), "branch": "main", "head": "abc123"})

    cmd = captured["cmd"]
    assert data["ok"] is True
    assert "--state-dir-name" in cmd
    assert cmd[cmd.index("--state-dir-name") + 1] == ".opencode"


def test_litmus_status_nonzero_valid_json_stderr_is_redacted_and_bounded(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "litmus-status.json", repo=repo)
    sentinel = "ghp_" + "B" * 36
    script = tmp_path / "failing-litmus-status.py"
    script.write_text(
        "import pathlib, sys\n"
        f"print(pathlib.Path({str(litmus)!r}).read_text())\n"
        "sys.stderr.write('e' * 5005)\n"
        f"sys.stderr.write(' token={sentinel}\\n')\n"
        "sys.exit(2)\n"
    )

    data = invoke(repo, plugin, "--litmus-status-script", str(script))

    litmus_status = data["litmus_status"]
    serialized = json.dumps(data)
    assert litmus_status["returncode"] == 2
    assert litmus_status["ok"] is False
    assert litmus_status["reason"] == "litmus_status_subprocess_failed"
    assert sentinel not in serialized
    assert len(litmus_status["stderr"]) <= 4000
    assert "token=[REDACTED]" in litmus_status["stderr"]


def test_litmus_status_subprocess_nonzero_fails_closed_even_with_valid_json(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "litmus-status.json", repo=repo)
    script = tmp_path / "litmus-status-wrapper.py"
    script.write_text(
        "import pathlib, sys\n"
        f"print(pathlib.Path({str(litmus)!r}).read_text())\n"
        "sys.exit(2)\n"
    )

    data = invoke(repo, plugin, "--litmus-status-script", str(script))

    assert data["litmus_status"]["returncode"] == 2
    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_subprocess_failed"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_subprocess_failed" in data["decision"]["blockers"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["commit_allowed"] is False
    assert data["decision"]["push_allowed"] is False
    assert data["decision"]["pr_allowed"] is False
    assert data["decision"]["merge_allowed"] is False
    assert data["decision"]["marker_write_allowed"] is False


def test_litmus_status_subprocess_nonzero_fails_closed_even_with_valid_json_ok_false(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "litmus-status.json", repo=repo, status="commit_litmus_fresh", ok=False)
    script = tmp_path / "litmus-status-wrapper.py"
    script.write_text(
        "import pathlib, sys\n"
        f"print(pathlib.Path({str(litmus)!r}).read_text())\n"
        "sys.exit(2)\n"
    )

    data = invoke(repo, plugin, "--litmus-status-script", str(script))

    assert data["litmus_status"]["returncode"] == 2
    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_subprocess_failed"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_subprocess_failed" in data["decision"]["blockers"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["commit_allowed"] is False
    assert data["decision"]["push_allowed"] is False
    assert data["decision"]["pr_allowed"] is False
    assert data["decision"]["merge_allowed"] is False
    assert data["decision"]["marker_write_allowed"] is False



def test_delivery_status_can_resolve_requested_relay_role_read_only(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    cfg = relay_config(tmp_path / "relay-config.json", ["opencode", "codex"])

    data = invoke(repo, plugin, "--relay-role", "relay.pr.backstop", "--relay-config", str(cfg))

    assert data["relay_capabilities"]["relay_role"]["available"] is True
    assert data["relay_capabilities"]["delivery_status"]["available"] is True
    assert data["relay_capabilities"]["finalization_readiness"]["available"] is True
    assert data["relay_capabilities"]["finalization_contract_status"]["available"] is True
    role = data["relay_role_resolution"]
    assert role["available"] is True
    assert role["ok"] is True
    assert role["returncode"] == 0
    assert role["result"]["role"] == "relay.pr.backstop"
    assert role["result"]["selected"]["selected_agent"] == "codex"
    assert role["result"]["dispatch_allowed"] is True
    assert role["result"]["mutation_allowed"] is False
    assert role["result"]["finalization_allowed"] is False
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["merge_allowed"] is False
    assert "relay_role_not_dispatchable" not in data["decision"]["warnings"]


def test_delivery_status_reports_unresolved_relay_role_as_warning(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    cfg = relay_config(tmp_path / "relay-config.json", [])

    data = invoke(repo, plugin, "--relay-role", "relay.pr.backstop", "--relay-config", str(cfg))

    role = data["relay_role_resolution"]
    assert role["available"] is True
    assert role["ok"] is False
    assert role["returncode"] == 2
    assert role["reason"] == "relay_role_not_dispatchable"
    assert role["result"]["dispatch_allowed"] is False
    assert role["result"]["selected"]["config_error"] == "empty_route"
    assert "relay_role_not_dispatchable" in data["decision"]["warnings"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["merge_allowed"] is False


def test_delivery_status_rejects_authority_positive_relay_role_output(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    unsafe = tmp_path / "unsafe-relay-role.py"
    unsafe.write_text(
        "import json\n"
        "print(json.dumps({\n"
        "  'schema': 'hermes-busdriver-relay-role/v0',\n"
        "  'role': 'relay.pr.backstop',\n"
        "  'read_only': True,\n"
        "  'ok': True,\n"
        "  'dispatch_allowed': True,\n"
        "  'mutation_allowed': True,\n"
        "  'finalization_allowed': True,\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'decision': {'dispatch_allowed': True, 'mutation_allowed': True, 'finalization_allowed': True, 'not_busdriver_native_claude_runtime': True}\n"
        "}))\n"
    )

    data = invoke(repo, plugin, "--relay-role", "relay.pr.backstop", "--relay-role-script", str(unsafe))

    role = data["relay_role_resolution"]
    assert role["returncode"] == 0
    assert role["ok"] is False
    assert role["reason"] == "relay_role_authority_flags_unsafe"
    assert "relay_role_not_dispatchable" in data["decision"]["warnings"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["merge_allowed"] is False


def test_delivery_status_rejects_mismatched_relay_role_output(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    wrong_role = tmp_path / "wrong-role.py"
    wrong_role.write_text(
        "import json\n"
        "print(json.dumps({\n"
        "  'schema': 'hermes-busdriver-relay-role/v0',\n"
        "  'role': 'relay.council.skeptic',\n"
        "  'read_only': True,\n"
        "  'ok': True,\n"
        "  'dispatch_allowed': True,\n"
        "  'mutation_allowed': False,\n"
        "  'finalization_allowed': False,\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'decision': {'dispatch_allowed': True, 'mutation_allowed': False, 'finalization_allowed': False, 'not_busdriver_native_claude_runtime': True}\n"
        "}))\n"
    )

    data = invoke(repo, plugin, "--relay-role", "relay.pr.backstop", "--relay-role-script", str(wrong_role))

    role = data["relay_role_resolution"]
    assert role["returncode"] == 0
    assert role["ok"] is False
    assert role["reason"] == "relay_role_authority_flags_unsafe"
    assert role["result"]["role"] == "relay.council.skeptic"
    assert "relay_role_not_dispatchable" in data["decision"]["warnings"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["merge_allowed"] is False


def test_pr_status_blocks_when_pr_grind_checker_missing(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    missing_checker = tmp_path / "missing-pr-grind-check"

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-check-script", str(missing_checker))

    assert data["decision"]["status"] == "blocked"
    assert "hermes_pr_grind_checker_unavailable" in data["decision"]["blockers"]
    assert "PR #3" not in data["decision"]["next_action"]
    assert "PR-grind readiness checker" in data["decision"]["next_action"]
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


def test_blocking_marker_with_dirty_tree_keeps_blocker_next_action(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    marker = repo / ".claude" / "freeze.local"
    marker.parent.mkdir()
    marker.write_text("freeze\n")
    (repo / "draft.txt").write_text("draft\n")

    data = invoke(repo, plugin)

    assert data["decision"]["status"] == "blocked"
    assert "blocking_busdriver_marker_present" in data["decision"]["blockers"]
    assert data["decision"]["next_action"] == "Resolve blocking status before delivery."


def test_active_finalization_lock_blocks_delivery_status_handoff(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    state = tmp_path / "relay-state"
    assert run([sys.executable, str(LOCK), "acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "finalization"]).returncode == 0
    (repo / "draft.txt").write_text("draft\n")

    data = invoke_with_lock_status(repo, plugin, state)

    assert data["finalization_lock"]["operation"] == "finalization"
    assert data["finalization_lock"]["active_for_repo_count"] == 1
    assert data["decision"]["status"] == "blocked"
    assert "relay_finalization_lock_active" in data["decision"]["blockers"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["commit_allowed"] is False
    assert data["decision"]["push_allowed"] is False
    assert data["decision"]["pr_allowed"] is False
    assert data["decision"]["merge_allowed"] is False


def test_finalization_lock_matches_when_repo_is_invoked_through_symlink(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    state = tmp_path / "relay-state"
    repo_link = tmp_path / "repo-link"
    repo_link.symlink_to(repo, target_is_directory=True)
    assert run([sys.executable, str(LOCK), "acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "finalization"]).returncode == 0

    data = invoke_with_lock_status(repo_link, plugin, state)

    assert data["repo"]["root"] == str(repo.resolve())
    assert data["finalization_lock"]["active_for_repo_count"] == 1
    assert "relay_finalization_lock_active" in data["decision"]["blockers"]


def test_invalid_finalization_lock_status_blocks_delivery_handoff(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    state = tmp_path / "relay-state"
    bad_lock = state / "locks" / "bad.lock" / "lock.json"
    bad_lock.parent.mkdir(parents=True)
    bad_lock.write_text("{not-json\n")
    (repo / "draft.txt").write_text("draft\n")

    data = invoke_with_lock_status(repo, plugin, state)

    assert data["finalization_lock"]["ok"] is False
    assert data["finalization_lock"]["status"] == "invalid_lock_entry"
    assert data["decision"]["status"] == "blocked"
    assert "relay_finalization_lock_status_unavailable" in data["decision"]["blockers"]
    assert data["decision"]["finalization_allowed"] is False
