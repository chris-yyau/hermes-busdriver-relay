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
BLOCKED_KEYS = [
    "finalization_allowed",
    "commit_allowed",
    "push_allowed",
    "pr_allowed",
    "merge_allowed",
    "deploy_allowed",
    "release_allowed",
    "publish_allowed",
    "marker_write_allowed",
]


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


def safe_loop_decision(status: str = "clean", reason: str = "latest_pr_head_clean_read_only") -> dict:
    return {
        "status": status,
        "reason": reason,
        "pr_grind_clean": status == "clean",
        "fixing_allowed": False,
        "fix_rounds_attempted": 0,
        "ack_ledger_policy": "delegated_to_pr_grind_check_read_only; no ack or Busdriver marker writes",
        **{key: False for key in BLOCKED_KEYS},
    }


def safe_loop_payload(status: str = "clean", ok: bool = True, clean: bool = True, decision: dict | None = None) -> dict:
    reason = "latest_pr_head_clean_read_only" if status == "clean" else "actionable_feedback_present_read_only_no_fix"
    return {
        "schema": "hermes-busdriver-pr-grind-loop/v0",
        "version": 1,
        "ok": ok,
        "read_only": True,
        "status": status,
        "clean": clean,
        "latest_head": "abc123",
        "decision": decision or safe_loop_decision(status, reason),
        "iterations": [{"iteration": 1, "status": status, "head": "abc123"}],
    }


def invoke_with_pr_grind_loop(
    monkeypatch,
    capsys,
    repo: Path,
    plugin: Path,
    payload: dict,
    returncode: int = 0,
    *extra: str,
    artifact_dir: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    ns = runpy.run_path(str(DELIVER))
    ns["main"].__globals__["run_pr_grind_loop"] = lambda _repo, _args: (payload, returncode)
    if artifact_dir:
        monkeypatch.setenv(ARTIFACT_ENV, str(artifact_dir))
    monkeypatch.setattr(
        sys,
        "argv",
        [sys.executable, "--repo", str(repo), "--plugin-root", str(plugin), "--mode", "execute", "--operation", "pr-grind", "--pr", "7", *extra],
    )
    rc = ns["main"]()
    captured = capsys.readouterr()
    cp = subprocess.CompletedProcess(sys.argv, rc, stdout=captured.out, stderr=captured.err)
    return cp, json.loads(captured.out)


def assert_finalization_blocked(decision: dict) -> None:
    for key in BLOCKED_KEYS:
        assert decision[key] is False


def assert_run_authority_blocked(run: dict) -> None:
    authority = run["authority"]
    for key in BLOCKED_KEYS:
        assert authority[key] is False


def assert_delivery_run_envelope(run: dict, run_id: str, phase: str, status: str, reason: str) -> None:
    assert run["schema"] == "hermes-busdriver-delivery-run/v0"
    assert run["run_id"] == run_id
    assert run["phase"] == phase
    assert run["status"] == status
    assert run["reason"] == reason
    assert isinstance(run["created_at"], str)
    assert run["version"] == 1
    assert_run_authority_blocked(run)


def test_verifier_help_warns_commands_execute_locally():
    cp = run([sys.executable, str(DELIVER), "--help"])

    assert cp.returncode == 0
    assert "shell=False" in cp.stdout
    assert "launch errors fail closed" in cp.stdout
    assert "--pr-grind-loop-script" not in cp.stdout


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


def test_plan_mode_emits_durable_delivery_run_envelope_without_artifact(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")

    cp, data = invoke(repo, plugin, "--run-id", "plan-123")

    assert cp.returncode == 0
    assert_delivery_run_envelope(data["run"], "plan-123", "plan", "plan_only", "read_only_plan")
    assert data["run"]["repo_root"] == str(repo)
    assert data["run"]["pr_number"] is None
    assert data["run"]["artifacts"] == []
    assert data["run_artifact_path"] is None
    assert_finalization_blocked(data["decision"])


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


def test_execute_verify_without_verifiers_writes_handoff_artifact(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"

    cp, data = invoke(repo, plugin, "--mode", "execute", "--operation", "verify", "--run-id", "verify-noop", artifact_dir=artifact_dir)

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "no_verifiers"
    assert_finalization_blocked(data["decision"])
    assert_delivery_run_envelope(data["run"], "verify-noop", "verify", "blocked", "no_verifiers")
    artifact = Path(data["run_artifact_path"])
    assert artifact.exists()
    assert json.loads(artifact.read_text())["decision"]["reason"] == "no_verifiers"


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


def test_tail_zero_limit_returns_empty_string():
    ns = runpy.run_path(str(DELIVER))

    assert ns["tail"]("abcdef", 0) == ""
    assert ns["tail"](b"abcdef", 0) == ""


def test_tail_redacts_common_secret_shapes():
    ns = runpy.run_path(str(DELIVER))
    secret = "ghp_" + "A" * 36

    redacted = ns["tail"](f"Authorization: Bearer {secret}\napi_key={secret}\n")

    assert secret not in redacted
    assert "Authorization: Bearer [REDACTED]" in redacted
    assert "api_key=[REDACTED]" in redacted


def test_execute_verify_redacts_verifier_command_output_and_artifact(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    secret = "plain-secret-value-1234567890"
    verifier_code = f'import sys; print("Authorization: Bearer {secret}"); sys.stderr.write("api_key={secret}\\n")'
    verifier_cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote(verifier_code)} --token {secret}"

    cp, data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--verifier",
        f"redaction={verifier_cmd}",
        artifact_dir=artifact_dir,
    )

    serialized = json.dumps(data)
    assert cp.returncode == 0
    assert data["ok"] is True
    assert secret not in serialized
    verifier = data["verifiers"][0]
    assert verifier["command"].endswith("--token [REDACTED]")
    assert verifier["stdout_tail"] == "Authorization: Bearer [REDACTED]\n"
    assert verifier["stderr_tail"] == "api_key=[REDACTED]\n"
    artifact = Path(data["run_artifact_path"])
    assert secret not in artifact.read_text()
    assert_finalization_blocked(data["decision"])


def test_delivery_status_error_tails_are_redacted(monkeypatch):
    ns = runpy.run_path(str(DELIVER))
    secret = "ghp_" + "C" * 36

    class CP:
        stdout = f"not-json {secret}"
        stderr = f"Authorization: Bearer {secret}"
        returncode = 0

    monkeypatch.setattr(ns["subprocess"], "run", lambda *args, **kwargs: CP())
    data, _rc = ns["run_delivery_status"](type("Args", (), {"repo": None, "plugin_root": None, "pr": None, "pr_grind_result_file": None, "delivery_status_timeout": 180})())

    serialized = json.dumps(data)
    assert secret not in serialized
    assert "Authorization: Bearer [REDACTED]" in data["stderr"]


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


def test_default_delivery_status_timeout_covers_pr_grind_and_litmus_budget(monkeypatch):
    ns = runpy.run_path(str(DELIVER))
    monkeypatch.setattr(
        sys,
        "argv",
        [str(DELIVER), "--repo", "/tmp/repo", "--plugin-root", "/tmp/plugin", "--pr", "7"],
    )
    args = ns["parse_args"]()
    captured = {"cmd": None, "timeout": None}

    class CP:
        stdout = "{}"
        stderr = ""
        returncode = 0

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["timeout"] = kwargs["timeout"]
        return CP()

    monkeypatch.setattr(ns["subprocess"], "run", fake_run)

    ns["run_delivery_status"](args)

    assert captured["timeout"] == 180 + 60 + 30
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert "--pr-grind-timeout" in cmd
    assert cmd[cmd.index("--pr-grind-timeout") + 1] == "180"
    assert "--litmus-status-timeout" in cmd
    assert cmd[cmd.index("--litmus-status-timeout") + 1] == "60"


def test_delivery_status_timeout_covers_custom_pr_grind_and_litmus_budget(monkeypatch):
    ns = runpy.run_path(str(DELIVER))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(DELIVER),
            "--repo",
            "/tmp/repo",
            "--plugin-root",
            "/tmp/plugin",
            "--pr",
            "7",
            "--pr-grind-timeout",
            "240",
            "--litmus-status-timeout",
            "90",
        ],
    )
    args = ns["parse_args"]()
    captured = {"cmd": None, "timeout": None}

    class CP:
        stdout = "{}"
        stderr = ""
        returncode = 0

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["timeout"] = kwargs["timeout"]
        return CP()

    monkeypatch.setattr(ns["subprocess"], "run", fake_run)

    ns["run_delivery_status"](args)

    assert captured["timeout"] == 240 + 90 + 30
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[cmd.index("--pr-grind-timeout") + 1] == "240"
    assert cmd[cmd.index("--litmus-status-timeout") + 1] == "90"


def test_clean_pr_grind_fixture_still_does_not_authorize_merge(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    assert run(["git", "config", "user.email", "test@example.test"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "README.md").write_text("# test\n")
    assert run(["git", "add", "README.md"], repo).returncode == 0
    assert run(["git", "commit", "-m", "init"], repo).returncode == 0
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


def test_execute_pr_grind_runs_read_only_loop_and_writes_artifact(monkeypatch, capsys, tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"

    cp, data = invoke_with_pr_grind_loop(
        monkeypatch,
        capsys,
        repo,
        plugin,
        safe_loop_payload(),
        0,
        "--run-id",
        "prgrind-123",
        "--max-wait-seconds",
        "1",
        "--poll-interval",
        "0",
        "--max-polls",
        "2",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode == 0
    assert data["ok"] is True
    assert data["operation"] == "pr-grind"
    assert data["decision"]["status"] == "pr_grind_clean"
    assert data["decision"]["reason"] == "latest_pr_head_clean_read_only"
    assert_finalization_blocked(data["decision"])
    assert data["pr_grind_loop"]["status"] == "clean"
    assert data["pr_grind_loop"]["clean"] is True
    assert data["verifiers"] == []
    assert_delivery_run_envelope(data["run"], "prgrind-123", "pr_grind", "pr_grind_clean", "latest_pr_head_clean_read_only")
    artifact = Path(data["run_artifact_path"])
    assert artifact.exists()
    artifact_data = json.loads(artifact.read_text())
    assert artifact_data["pr_grind_loop"]["status"] == "clean"
    assert artifact_data["run"]["artifacts"] == [{"kind": "result", "path": str(artifact)}]
    assert not (repo / ".claude").exists()
    assert not (repo / ".opencode").exists()


def test_execute_pr_grind_needs_fix_fails_closed_and_writes_artifact(monkeypatch, capsys, tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"

    cp, data = invoke_with_pr_grind_loop(
        monkeypatch,
        capsys,
        repo,
        plugin,
        safe_loop_payload(status="needs_fix", ok=False, clean=False),
        1,
        "--run-id",
        "prgrind-needs-fix",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "pr_grind_needs_fix"
    assert_finalization_blocked(data["decision"])
    assert data["pr_grind_loop"]["status"] == "needs_fix"
    assert data["steps"][0] == {"name": "pr_grind", "status": "blocked", "reason": "pr_grind_needs_fix"}
    assert Path(data["run_artifact_path"]).exists()


def test_execute_pr_grind_rejects_malformed_loop_output(monkeypatch, capsys, tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"

    cp, data = invoke_with_pr_grind_loop(
        monkeypatch,
        capsys,
        repo,
        plugin,
        {"ok": True, "status": "clean", "clean": True},
        0,
        "--run-id",
        "prgrind-malformed-loop",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode != 0
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "pr_grind_loop_failed"
    assert_finalization_blocked(data["decision"])
    assert Path(data["run_artifact_path"]).exists()


def test_run_pr_grind_loop_timeout_bytes_are_json_safe(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))

    def raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["slow-loop"], timeout=1, output=b"partial", stderr=b"slow")

    monkeypatch.setattr(ns["subprocess"], "run", raise_timeout)
    args = type(
        "Args",
        (),
        {
            "pr": "7",
            "max_wait_seconds": 1.0,
            "poll_interval": 0.0,
            "max_polls": 1,
            "check_timeout": 1.0,
            "plugin_root": None,
        },
    )()

    data, rc = ns["run_pr_grind_loop"](tmp_path, args)

    assert rc == 124
    assert data["stdout_tail"] == "partial"
    assert data["stderr_tail"] == "slow"
    json.dumps(data)


def test_execute_pr_grind_rejects_mismatched_loop_decision_status(monkeypatch, capsys, tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    mismatched_decision = safe_loop_decision(status="blocked", reason="checker_failed")

    cp, data = invoke_with_pr_grind_loop(
        monkeypatch,
        capsys,
        repo,
        plugin,
        safe_loop_payload(status="clean", ok=True, clean=True, decision=mismatched_decision),
        0,
        "--run-id",
        "prgrind-mismatched-decision",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "pr_grind_loop_failed"
    assert_finalization_blocked(data["decision"])
    assert data["pr_grind_loop"]["status"] == "clean"
    assert data["pr_grind_loop"]["decision"]["status"] == "blocked"
    assert Path(data["run_artifact_path"]).exists()


def test_execute_pr_grind_rejects_clean_payload_with_nonzero_exit(monkeypatch, capsys, tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"

    cp, data = invoke_with_pr_grind_loop(
        monkeypatch,
        capsys,
        repo,
        plugin,
        safe_loop_payload(),
        1,
        "--run-id",
        "prgrind-clean-nonzero",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "pr_grind_loop_failed"
    assert_finalization_blocked(data["decision"])
    assert data["pr_grind_loop"]["clean"] is True
    assert Path(data["run_artifact_path"]).exists()


def test_execute_pr_grind_rejects_unsafe_loop_authority(monkeypatch, capsys, tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    unsafe_decision = safe_loop_decision()
    unsafe_decision["merge_allowed"] = True

    cp, data = invoke_with_pr_grind_loop(
        monkeypatch,
        capsys,
        repo,
        plugin,
        safe_loop_payload(decision=unsafe_decision),
        0,
        "--run-id",
        "prgrind-unsafe-clean",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "pr_grind_loop_failed"
    assert_finalization_blocked(data["decision"])
    assert data["pr_grind_loop"]["decision"]["merge_allowed"] is True
    assert Path(data["run_artifact_path"]).exists()


def test_execute_pr_grind_delivery_status_failure_writes_handoff_artifact(tmp_path: Path):
    missing_repo = tmp_path / "missing-repo"
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"

    cp, data = invoke(
        missing_repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "pr-grind",
        "--pr",
        "7",
        "--run-id",
        "prgrind-preflight-failed",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode != 0
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "delivery_status_failed"
    assert data["pr_grind_loop"] is None
    assert data["steps"][0] == {"name": "delivery_status", "status": "blocked", "reason": "helper_failed"}
    assert data["steps"][1] == {"name": "pr_grind", "status": "skipped", "reason": "delivery_status_failed"}
    assert_finalization_blocked(data["decision"])
    assert Path(data["run_artifact_path"]).exists()


def test_execute_pr_grind_requires_pr_and_writes_no_artifact(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"

    cp, data = invoke(repo, plugin, "--mode", "execute", "--operation", "pr-grind", artifact_dir=artifact_dir)

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "pr_required"
    assert_finalization_blocked(data["decision"])
    assert data["run_artifact_path"] is None
    assert not artifact_dir.exists()


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
        "--run-id",
        "verify-123",
        "--verifier",
        f"smoke={verifier_cmd}",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode == 0
    assert data["ok"] is True
    assert data["operation"] == "verify"
    assert data["decision"]["status"] == "verified"
    assert_delivery_run_envelope(data["run"], "verify-123", "verify", "verified", "verified")
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
    assert "verify-123" in artifact.name
    assert data["run"]["artifacts"] == [{"kind": "result", "path": str(artifact)}]
    assert repo not in artifact.parents
    artifact_data = json.loads(artifact.read_text())
    assert artifact_data["run_artifact_path"] == str(artifact)
    assert artifact_data["run"]["run_id"] == "verify-123"
    assert artifact_data["run"]["artifacts"] == [{"kind": "result", "path": str(artifact)}]
    assert artifact_data["verifiers"][0]["name"] == "smoke"
    assert not (repo / ".claude").exists()
    assert not (repo / ".opencode").exists()


def test_status_mode_reads_latest_valid_artifact_for_run_id_without_writing(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    verifier_cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote('print(1)')}"
    cp_first, first_data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--run-id",
        "lookup-123",
        "--verifier",
        f"first={verifier_cmd}",
        artifact_dir=artifact_dir,
    )
    cp_second, second_data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--run-id",
        "lookup-123",
        "--verifier",
        f"second={verifier_cmd}",
        artifact_dir=artifact_dir,
    )
    first_artifact = Path(first_data["run_artifact_path"])
    second_artifact = Path(second_data["run_artifact_path"])
    second_payload = json.loads(second_artifact.read_text())
    second_payload["run"]["artifacts"][0]["verifier_tail"] = "do-not-echo"
    second_artifact.write_text(json.dumps(second_payload))
    spoof = artifact_dir / "zz-spoof.json"
    spoof.write_text(json.dumps({"run": {"run_id": "lookup-123", "schema": "wrong"}}))
    schema_spoof = artifact_dir / "zzz-schema-spoof.json"
    schema_spoof.write_text(json.dumps({"schema": "hermes-busdriver-deliver/v0", "run": {"schema": "hermes-busdriver-delivery-run/v0", "run_id": "lookup-123"}}))
    authority_positive = artifact_dir / "zzzz-authority-positive.json"
    false_flags = {key: False for key in BLOCKED_KEYS}
    authority_positive.write_text(json.dumps({
        "schema": "hermes-busdriver-deliver/v0",
        "version": 1,
        "ok": True,
        "decision": {"status": "verified", "reason": "verified", **false_flags, "merge_allowed": True, "secret": "do-not-echo"},
        "run": {
            "schema": "hermes-busdriver-delivery-run/v0",
            "version": 1,
            "run_id": "lookup-123",
            "phase": "verify",
            "status": "verified",
            "reason": "verified",
            "repo_root": str(repo),
            "authority": {**false_flags, "merge_allowed": True},
            "secret": "do-not-echo",
        },
    }))
    malformed_identity = artifact_dir / "zzzzz-malformed-identity.json"
    malformed_identity.write_text(json.dumps({
        "schema": "hermes-busdriver-deliver/v0",
        "version": 1,
        "ok": True,
        "mode": "execute",
        "operation": "verify",
        "repo": {"root": ["not", "a", "string"]},
        "pr": {"number": {"bad": True}},
        "decision": {"status": "verified", "reason": "verified", **false_flags},
        "run": {
            "schema": "hermes-busdriver-delivery-run/v0",
            "version": 1,
            "run_id": "lookup-123",
            "created_at": 123,
            "phase": "surprise",
            "status": "verified",
            "reason": "verified",
            "repo_root": ["not", "a", "string"],
            "pr_number": {"bad": True},
            "authority": false_flags,
            "artifacts": "not-a-list",
        },
    }))
    corrupt = artifact_dir / "zzzzzz-corrupt.json"
    corrupt.write_bytes(b"\xff\xfe\x00not-json")
    os.utime(first_artifact, (10, 10))
    os.utime(second_artifact, (20, 20))
    os.utime(spoof, (30, 30))
    os.utime(schema_spoof, (40, 40))
    os.utime(authority_positive, (50, 50))
    os.utime(malformed_identity, (60, 60))
    os.utime(corrupt, (70, 70))
    before = {
        path.name: {
            "bytes": path.read_bytes(),
            "mtime_ns": path.stat().st_mtime_ns,
        }
        for path in artifact_dir.iterdir()
    }

    cp, data = invoke(repo, plugin, "--mode", "status", "--run-id", "lookup-123", artifact_dir=artifact_dir)
    after = {
        path.name: {
            "bytes": path.read_bytes(),
            "mtime_ns": path.stat().st_mtime_ns,
        }
        for path in artifact_dir.iterdir()
    }

    assert cp_first.returncode == 0
    assert cp_second.returncode == 0
    assert cp.returncode == 0
    assert before == after
    assert data["ok"] is True
    assert data["mode"] == "status"
    assert data["operation"] == "status"
    assert data["run_artifact_path"] is None
    assert data["status_lookup"]["found"] is True
    assert data["status_lookup"]["run_id"] == "lookup-123"
    assert data["status_lookup"]["artifact_path"] == str(second_artifact)
    assert data["status_lookup"]["artifact_run"]["run_id"] == "lookup-123"
    assert data["status_lookup"]["artifact_schema"] == "hermes-busdriver-deliver/v0"
    assert data["status_lookup"]["artifact_ok"] is True
    assert data["status_lookup"]["artifact_run"]["artifacts"] == [{"kind": "result", "path": str(second_artifact)}]
    assert "artifact" not in data["status_lookup"]
    assert "verifiers" not in data["status_lookup"]
    assert "do-not-echo" not in json.dumps(data["status_lookup"])
    assert data["status_lookup"]["artifact_decision"]["status"] == "verified"
    assert_delivery_run_envelope(data["run"], "lookup-123", "status", "found", "run_found")
    assert data["run"]["repo_root"] == str(repo)
    assert data["run"]["artifacts"] == [{"kind": "result", "path": str(second_artifact)}]
    assert_finalization_blocked(data["decision"])


def test_status_mode_accepts_legacy_v1_artifact_without_marker_write_flag(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    verifier_cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote('print(1)')}"
    cp_verify, verify_data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--run-id",
        "legacy-123",
        "--verifier",
        f"ok={verifier_cmd}",
        artifact_dir=artifact_dir,
    )
    artifact = Path(verify_data["run_artifact_path"])
    legacy_payload = json.loads(artifact.read_text())
    legacy_payload["decision"].pop("marker_write_allowed")
    legacy_payload["run"]["authority"].pop("marker_write_allowed")
    artifact.write_text(json.dumps(legacy_payload))

    cp, data = invoke(repo, plugin, "--mode", "status", "--run-id", "legacy-123", artifact_dir=artifact_dir)

    assert cp_verify.returncode == 0
    assert cp.returncode == 0
    assert data["status_lookup"]["found"] is True
    assert data["status_lookup"]["artifact_path"] == str(artifact)
    assert data["status_lookup"]["artifact_decision"]["marker_write_allowed"] is False
    assert data["status_lookup"]["artifact_run"]["authority"]["marker_write_allowed"] is False
    assert_finalization_blocked(data["decision"])


def test_status_mode_returns_latest_valid_failed_delivery_status_artifact(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    missing_repo = tmp_path / "missing-repo"
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    verifier_cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote('print(1)')}"

    cp_ok, ok_data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--run-id",
        "lookup-failed-latest",
        "--verifier",
        f"ok={verifier_cmd}",
        artifact_dir=artifact_dir,
    )
    cp_failed, failed_data = invoke(
        missing_repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "verify",
        "--run-id",
        "lookup-failed-latest",
        "--verifier",
        f"skip={verifier_cmd}",
        artifact_dir=artifact_dir,
    )
    ok_artifact = Path(ok_data["run_artifact_path"])
    failed_artifact = Path(failed_data["run_artifact_path"])
    os.utime(ok_artifact, (10, 10))
    os.utime(failed_artifact, (20, 20))

    cp, data = invoke(repo, plugin, "--mode", "status", "--run-id", "lookup-failed-latest", artifact_dir=artifact_dir)

    assert cp_ok.returncode == 0
    assert cp_failed.returncode != 0
    assert cp.returncode == 0
    assert data["status_lookup"]["found"] is True
    assert data["status_lookup"]["artifact_path"] == str(failed_artifact)
    assert data["status_lookup"]["artifact_run"]["phase"] == "delivery_status"
    assert data["status_lookup"]["artifact_run"]["status"] == "blocked"
    assert data["status_lookup"]["artifact_run"]["reason"] == "delivery_status_failed"
    assert data["run"]["phase"] == "status"
    assert data["run"]["artifacts"] == [{"kind": "result", "path": str(failed_artifact)}]
    assert_finalization_blocked(data["decision"])


def test_status_mode_fails_closed_when_run_id_missing_or_unknown(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"

    cp_missing, missing = invoke(repo, plugin, "--mode", "status", artifact_dir=artifact_dir)
    cp_unknown, unknown = invoke(repo, plugin, "--mode", "status", "--run-id", "missing-run", artifact_dir=artifact_dir)

    assert cp_missing.returncode == 2
    assert missing["ok"] is False
    assert missing["operation"] == "status"
    assert missing["decision"] == {"status": "blocked", "reason": "run_id_required", **{key: False for key in BLOCKED_KEYS}}
    assert missing["status_lookup"] == {"found": False, "reason": "run_id_required"}
    assert missing["run"]["run_id"] is None
    assert missing["run"]["phase"] == "status"
    assert cp_unknown.returncode == 1
    assert unknown["ok"] is False
    assert unknown["decision"]["status"] == "blocked"
    assert unknown["decision"]["reason"] == "run_not_found"
    assert unknown["status_lookup"] == {"found": False, "reason": "run_not_found", "run_id": "missing-run"}
    assert_finalization_blocked(unknown["decision"])


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


def test_timeout_verifier_stderr_tail_stays_bounded(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))

    def raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["slow"], timeout=5, output="partial", stderr="e" * 5005)

    monkeypatch.setattr(ns["subprocess"], "run", raise_timeout)
    result = ns["run_verifiers"](tmp_path, ["slow=python -c pass"], 5)[0]

    assert result["returncode"] == 124
    assert result["ok"] is False
    assert result["stdout_tail"] == "partial"
    assert result["stderr_tail"].startswith("timeout after 5s\n")
    assert len(result["stderr_tail"]) <= 4000


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
    assert data["decision"]["status"] == "blocked"
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
    assert data["decision"]["status"] == "blocked"
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
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "verifier_failed"
    assert data["verifiers"][0]["name"] == "empty"
    assert data["verifiers"][0]["ok"] is False
    assert data["verifiers"][0]["stderr_tail"] == "empty verifier command"
    assert Path(data["run_artifact_path"]).exists()
    assert_finalization_blocked(data["decision"])


def test_artifact_write_failure_cleans_temp_file_and_clears_path(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    artifact_dir = tmp_path / "delivery-runs"
    monkeypatch.setenv(ARTIFACT_ENV, str(artifact_dir))

    def fail_replace(_src, _dst):
        raise OSError("replace failed")

    monkeypatch.setattr(ns["os"], "replace", fail_replace)
    result = {"schema": "test", "run_artifact_path": None}

    try:
        ns["write_artifact"](result)
    except OSError as e:
        assert str(e) == "replace failed"
    else:  # pragma: no cover - defensive
        raise AssertionError("expected write_artifact to raise")

    assert result["run_artifact_path"] is None
    assert list(artifact_dir.iterdir()) == []


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
    assert data["run"]["phase"] == "verify"
    assert data["run"]["status"] == "blocked"
    assert data["run"]["reason"] == "artifact_write_failed"
    assert data["run"]["artifacts"] == []
    assert data["decision"] == {"status": "blocked", "reason": "artifact_write_failed", **{key: False for key in BLOCKED_KEYS}}
    assert data["steps"][0] == {"name": "write_artifact", "status": "blocked", "reason": "artifact_write_failed"}
    assert_finalization_blocked(data["decision"])


def test_malformed_verifier_command_preserves_user_label(tmp_path: Path):
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
        "quoted=python -c 'unterminated",
        artifact_dir=artifact_dir,
    )

    verifier = data["verifiers"][0]
    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "verifier_failed"
    assert verifier["name"] == "quoted"
    assert verifier["returncode"] == 2
    assert verifier["ok"] is False
    assert "No closing quotation" in verifier["stderr_tail"]
    assert Path(data["run_artifact_path"]).exists()
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
