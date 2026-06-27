import json
import os
import runpy
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DELIVER = ROOT / "scripts" / "hermes-busdriver-deliver"
ARTIFACT_ENV = "HERMES_BUSDRIVER_DELIVERY_RUNS_DIR"


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, text=True, capture_output=True, check=False)


def init_repo(path: Path) -> Path:
    path.mkdir()
    assert run(["git", "init"], path).returncode == 0
    return path


def fake_busdriver(path: Path) -> Path:
    files = {
        "package.json": '{"version":"1.71.0"}\n',
        "scripts/relevant-check-status.sh": "#!/bin/sh\ncat >/dev/null\nprintf '0 0 all 1\\n'\n",
        "scripts/ack-ledger.sh": "#!/bin/sh\nprintf 'none\\n'\n",
        "scripts/fetch-pr-state.sh": "#!/bin/sh\ntrue\n",
        "hooks/gate-scripts/pre-pr-gate.sh": "#!/bin/sh\ntrue\n",
        "hooks/gate-scripts/pre-merge-gate.sh": "#!/bin/sh\ntrue\n",
        "skills/pr-grind/SKILL.md": "# pr-grind\n",
        "agents/pr-grinder.md": "# pr-grinder\n",
        "opencode/skills/pr-grind/SKILL.md": "# pr-grind\n",
        "opencode/agents/pr-grinder.md": "# pr-grinder\n",
    }
    for rel, content in files.items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        if rel.startswith("scripts/") or rel.startswith("hooks/"):
            target.chmod(0o755)
    return path


def invoke(
    repo: Path,
    plugin: Path,
    *extra: str,
    artifact_dir: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    env = os.environ.copy()
    if artifact_dir:
        env[ARTIFACT_ENV] = str(artifact_dir)
    cp = run([sys.executable, str(DELIVER), "--repo", str(repo), "--plugin-root", str(plugin), *extra], env=env)
    return cp, json.loads(cp.stdout)


def assert_finalization_blocked(decision: dict) -> None:
    for key in [
        "finalization_allowed",
        "commit_allowed",
        "push_allowed",
        "pr_allowed",
        "merge_allowed",
        "deploy_allowed",
        "release_allowed",
        "publish_allowed",
    ]:
        assert decision[key] is False


def test_verifier_help_warns_commands_execute_locally():
    cp = run([sys.executable, str(DELIVER), "--help"])

    assert cp.returncode == 0
    assert "shell=False" in cp.stdout
    assert "launch errors fail closed" in cp.stdout


def test_default_plan_mode_is_read_only_status_envelope(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")

    cp, data = invoke(repo, plugin)

    assert cp.returncode == 0
    assert os.access(DELIVER, os.X_OK)
    assert data["schema"] == "hermes-busdriver-deliver/v0"
    assert data["ok"] is True
    assert data["mode"] == "plan"
    assert data["operation"] == "plan"
    assert data["repo"]["root"] == str(repo)
    assert data["pr"] is None
    assert data["verifiers"] == []
    assert data["run_artifact_path"] is None
    assert data["delivery_status"]["schema"] == "hermes-busdriver-delivery-status/v0"
    assert data["decision"]["status"] == "plan_only"
    assert_finalization_blocked(data["decision"])
    assert [step["status"] for step in data["steps"]] == ["pending", "blocked", "blocked", "blocked", "blocked", "blocked"]
    assert not (repo / ".claude").exists()
    assert not (repo / ".opencode").exists()


def test_execute_mode_without_verify_operation_is_blocked_and_has_no_repo_side_effects(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")

    cp, data = invoke(repo, plugin, "--mode", "execute")

    assert cp.returncode != 0
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "unsupported_operation"
    assert_finalization_blocked(data["decision"])
    assert data["steps"][0] == {"name": "execute", "status": "blocked", "reason": "unsupported_operation"}
    assert data["verifiers"] == []
    assert data["run_artifact_path"] is None
    assert not (repo / ".claude").exists()
    assert not (repo / ".opencode").exists()


def test_plan_mode_never_authorizes_clean_status(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")

    cp, data = invoke(repo, plugin)

    assert cp.returncode == 0
    assert data["ok"] is True
    assert data["delivery_status"]["repo"]["dirty"] is False
    assert data["mode"] == "plan"
    assert data["decision"]["status"] == "plan_only"
    assert_finalization_blocked(data["decision"])


def test_delivery_status_non_object_json_fails_closed(monkeypatch):
    ns = runpy.run_path(str(DELIVER))

    class CP:
        stdout = "[]"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(ns["subprocess"], "run", lambda *args, **kwargs: CP())
    data, rc = ns["run_delivery_status"](type("Args", (), {"repo": None, "plugin_root": None, "pr": None, "pr_grind_result_file": None, "delivery_status_timeout": 180})())

    assert rc == 0
    assert data["ok"] is False
    assert data["error"] == "delivery_status_invalid_json_type"
    assert data["returncode"] == 0


def test_delivery_status_invalid_json_stderr_is_bounded(monkeypatch):
    ns = runpy.run_path(str(DELIVER))

    class CP:
        stdout = "not-json"
        stderr = "e" * 5005
        returncode = 0

    monkeypatch.setattr(ns["subprocess"], "run", lambda *args, **kwargs: CP())
    data, rc = ns["run_delivery_status"](type("Args", (), {"repo": None, "plugin_root": None, "pr": None, "pr_grind_result_file": None, "delivery_status_timeout": 180})())

    assert rc == 0
    assert data["ok"] is False
    assert data["error"] == "delivery_status_invalid_json"
    assert len(data["stderr"]) <= 4000


def test_delivery_status_timeout_fails_closed(monkeypatch):
    ns = runpy.run_path(str(DELIVER))

    def raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["helper"], timeout=180, output="partial", stderr="slow")

    monkeypatch.setattr(ns["subprocess"], "run", raise_timeout)
    data, rc = ns["run_delivery_status"](type("Args", (), {"repo": None, "plugin_root": None, "pr": None, "pr_grind_result_file": None, "delivery_status_timeout": 5})())

    assert rc == 124
    assert data["ok"] is False
    assert data["error"] == "delivery_status_timeout"
    assert data["returncode"] == 124
    assert data["timeout_seconds"] == 5
    assert data["stdout_tail"] == "partial"
    assert data["stderr"] == "slow"


def test_clean_pr_grind_fixture_still_does_not_authorize_merge(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    pr_result = tmp_path / "pr-grind-clean.json"
    pr_result.write_text(json.dumps({"status": "clean", "clean": True, "checks": {"failed": 0, "pending": 0}, "actionable_comments": []}))

    cp, data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert cp.returncode == 0
    assert data["ok"] is True
    assert data["pr"] == {"number": "7", "available": True, "ok": True, "status": "clean", "clean": True}
    assert data["delivery_status"]["decision"]["status"] == "pr_clean_read_only"
    assert data["decision"]["status"] == "plan_only"
    assert_finalization_blocked(data["decision"])


def test_delivery_status_failure_blocks_finalization(tmp_path: Path):
    repo = tmp_path / "not-git"
    repo.mkdir()
    plugin = fake_busdriver(tmp_path / "busdriver")

    cp, data = invoke(repo, plugin)

    assert cp.returncode != 0
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "delivery_status_failed"
    assert data["delivery_status"]["ok"] is False
    assert data["steps"][0] == {"name": "delivery_status", "status": "blocked", "reason": "helper_failed"}
    assert_finalization_blocked(data["decision"])


def test_execute_verify_runs_verifier_and_writes_hermes_artifact(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"

    verifier_code = 'import sys; print("ok"); sys.stderr.write("err\\n")'
    verifier_cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote(verifier_code)}"

    cp, data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--verifier",
        f"smoke={verifier_cmd}",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode == 0
    assert data["ok"] is True
    assert data["operation"] == "verify"
    assert data["decision"]["status"] == "verified"
    assert_finalization_blocked(data["decision"])
    assert data["verifiers"] == [
        {
            "name": "smoke",
            "command": verifier_cmd,
            "returncode": 0,
            "ok": True,
            "stdout_tail": "ok\n",
            "stderr_tail": "err\n",
        }
    ]
    artifact = Path(data["run_artifact_path"])
    assert artifact.parent == artifact_dir
    assert artifact.exists()
    assert repo not in artifact.parents
    artifact_data = json.loads(artifact.read_text())
    assert artifact_data["run_artifact_path"] == str(artifact)
    assert artifact_data["verifiers"][0]["name"] == "smoke"
    assert not (repo / ".claude").exists()
    assert not (repo / ".opencode").exists()


def test_failing_verifier_fails_closed_with_bounded_tails(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    code = "import sys; print('x' * 5005); sys.stderr.write('e' * 5005); raise SystemExit(7)"

    cp, data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--verifier",
        f"fail={shlex.quote(sys.executable)} -c {shlex.quote(code)}",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "verifier_failed"
    assert_finalization_blocked(data["decision"])
    assert data["verifiers"][0]["returncode"] == 7
    assert data["verifiers"][0]["ok"] is False
    assert len(data["verifiers"][0]["stdout_tail"]) <= 4000
    assert len(data["verifiers"][0]["stderr_tail"]) <= 4000
    assert Path(data["run_artifact_path"]).exists()


def test_missing_verifier_command_fails_closed_with_structured_error(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"

    cp, data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--verifier",
        "missing=definitely-missing-hermes-verifier-command",
        artifact_dir=artifact_dir,
    )

    verifier = data["verifiers"][0]
    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["decision"]["reason"] == "verifier_failed"
    assert verifier["name"] == "missing"
    assert verifier["returncode"] == 127
    assert verifier["ok"] is False
    assert verifier["stdout_tail"] == ""
    assert "FileNotFoundError" in verifier["stderr_tail"]
    assert len(verifier["stderr_tail"]) <= 4000
    assert Path(data["run_artifact_path"]).exists()
    assert_finalization_blocked(data["decision"])


def test_non_executable_verifier_fails_closed_with_structured_error(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    verifier = tmp_path / "not-executable"
    verifier.write_text("#!/bin/sh\necho should-not-run\n")
    verifier.chmod(0o644)

    cp, data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--verifier",
        f"permission={verifier}",
        artifact_dir=artifact_dir,
    )

    verifier_result = data["verifiers"][0]
    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["decision"]["reason"] == "verifier_failed"
    assert verifier_result["name"] == "permission"
    assert verifier_result["returncode"] == 127
    assert verifier_result["ok"] is False
    assert verifier_result["stdout_tail"] == ""
    assert "PermissionError" in verifier_result["stderr_tail"]
    assert Path(data["run_artifact_path"]).exists()
    assert_finalization_blocked(data["decision"])


def test_verifier_command_with_equals_not_at_label_prefix_is_not_split(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    code = "value='foo=bar'; print(value)"
    verifier_cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"

    cp, data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--verifier",
        verifier_cmd,
        artifact_dir=artifact_dir,
    )

    assert cp.returncode == 0
    assert data["ok"] is True
    assert data["verifiers"][0]["name"] == "verifier_1"
    assert data["verifiers"][0]["command"] == verifier_cmd
    assert data["verifiers"][0]["stdout_tail"] == "foo=bar\n"
    assert_finalization_blocked(data["decision"])


def test_empty_verifier_command_fails_closed(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"

    cp, data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--verifier",
        "empty=",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["decision"]["reason"] == "verifier_failed"
    assert data["verifiers"][0]["ok"] is False
    assert data["verifiers"][0]["stderr_tail"] == "empty verifier command"
    assert Path(data["run_artifact_path"]).exists()
    assert_finalization_blocked(data["decision"])


def test_artifact_write_failure_does_not_publish_phantom_path(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir_file = tmp_path / "not-a-directory"
    artifact_dir_file.write_text("occupied")

    cp, data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--verifier",
        f"ok={shlex.quote(sys.executable)} -c {shlex.quote('print(1)')}",
        artifact_dir=artifact_dir_file,
    )

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["run_artifact_path"] is None
    assert data["decision"] == {"status": "blocked", "reason": "artifact_write_failed", **{key: False for key in ["finalization_allowed", "commit_allowed", "push_allowed", "pr_allowed", "merge_allowed", "deploy_allowed", "release_allowed", "publish_allowed"]}}
    assert data["steps"][0] == {"name": "write_artifact", "status": "blocked", "reason": "artifact_write_failed"}
    assert_finalization_blocked(data["decision"])


def test_unsupported_execute_operation_fails_closed_without_verifier(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    marker = tmp_path / "verifier-ran"

    cp, data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "plan",
        "--verifier",
        f"trip=printf ran > {shlex.quote(str(marker))}",
    )

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "unsupported_operation"
    assert data["verifiers"] == []
    assert data["run_artifact_path"] is None
    assert not marker.exists()
    assert_finalization_blocked(data["decision"])


def test_invalid_operation_is_rejected_by_argparse_without_artifact(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    env = os.environ.copy()
    env[ARTIFACT_ENV] = str(artifact_dir)

    cp = run(
        [
            sys.executable,
            str(DELIVER),
            "--repo",
            str(repo),
            "--plugin-root",
            str(plugin),
            "--mode",
            "execute",
            "--operation",
            "commit",
        ],
        env=env,
    )

    assert cp.returncode == 2
    assert cp.stdout == ""
    assert "invalid choice" in cp.stderr
    assert "commit" in cp.stderr
    assert not artifact_dir.exists()


def test_delivery_status_failure_prevents_verifier_execution(tmp_path: Path):
    missing_repo = tmp_path / "missing"
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    marker = tmp_path / "verifier-ran"

    cp, data = invoke(
        missing_repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--verifier",
        f"trip=printf ran > {shlex.quote(str(marker))}",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode != 0
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "delivery_status_failed"
    assert data["verifiers"] == []
    assert not marker.exists()
    assert Path(data["run_artifact_path"]).exists()
    assert_finalization_blocked(data["decision"])
