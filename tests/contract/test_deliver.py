import argparse
import hashlib
import json
import os
import runpy
import shlex
import subprocess
import pytest
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


def delivery_status_for_mutation(repo: Path, decision_status: str, litmus_decision_status: str = "pr_review_fresh") -> dict:
    decision = {"status": decision_status, "blockers": [], **{key: False for key in BLOCKED_KEYS}}
    litmus_decision = {"status": litmus_decision_status, **{key: False for key in BLOCKED_KEYS}}
    return {
        "schema": "hermes-busdriver-delivery-status/v0",
        "read_only": True,
        "ok": True,
        "repo": {"root": str(repo)},
        "markers": {"blocking": []},
        "decision": decision,
        "litmus_status": {
            "available": True,
            "ok": True,
            "summary": {
                "schema": "hermes-busdriver-litmus-status/v0",
                "read_only": True,
                "ok": True,
                "authority_safe": True,
                "decision_status_recognized": True,
                "decision": litmus_decision,
                "markers": {"litmus_passed": {"diff_hash": "0" * 64}},
                "repo": {"base_ref": "origin/main", "branch_diff_hash": "b" * 64, "head": "abc123"},
            },
        },
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
    assert "--relay-role" not in cmd
    assert "--relay-config" not in cmd
    assert "--relay-role-timeout" not in cmd
    assert "--litmus-base-ref" not in cmd


def test_delivery_status_forwards_requested_litmus_base_ref(monkeypatch):
    ns = runpy.run_path(str(DELIVER))
    monkeypatch.setattr(
        sys,
        "argv",
        [str(DELIVER), "--repo", "/tmp/repo", "--plugin-root", "/tmp/plugin", "--base", "origin/release"],
    )
    args = ns["parse_args"]()
    captured = {"cmd": None}

    class CP:
        stdout = "{}"
        stderr = ""
        returncode = 0

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return CP()

    monkeypatch.setattr(ns["subprocess"], "run", fake_run)

    ns["run_delivery_status"](args)

    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[cmd.index("--litmus-base-ref") + 1] == "origin/release"


def test_delivery_status_forwards_relay_role_config_and_includes_default_relay_budget(monkeypatch):
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
            "--relay-role",
            "relay.pr.backstop",
            "--relay-config",
            "/tmp/relay-config.json",
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

    assert captured["timeout"] == 180 + 60 + 90 + 30
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[cmd.index("--relay-role") + 1] == "relay.pr.backstop"
    assert cmd[cmd.index("--relay-config") + 1] == "/tmp/relay-config.json"
    assert cmd[cmd.index("--relay-role-timeout") + 1] == "90"


def test_delivery_status_forwards_custom_relay_role_timeout_and_budget(monkeypatch):
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
            "--pr-grind-timeout",
            "240",
            "--litmus-status-timeout",
            "90",
            "--relay-role",
            "relay.pr.backstop",
            "--relay-config",
            "/tmp/relay-config.json",
            "--relay-role-timeout",
            "45",
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

    assert captured["timeout"] == 240 + 90 + 45 + 30
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[cmd.index("--relay-role") + 1] == "relay.pr.backstop"
    assert cmd[cmd.index("--relay-config") + 1] == "/tmp/relay-config.json"
    assert cmd[cmd.index("--relay-role-timeout") + 1] == "45"


def test_delivery_status_relay_config_without_role_does_not_include_relay_timeout_budget(monkeypatch):
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
            "--relay-config",
            "/tmp/relay-config.json",
            "--relay-role-timeout",
            "45",
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

    assert captured["timeout"] == 180 + 60 + 30
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[cmd.index("--relay-config") + 1] == "/tmp/relay-config.json"
    assert "--relay-role" not in cmd
    assert "--relay-role-timeout" not in cmd


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
            "--busdriver-state-dir-name",
            ".opencode",
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
    assert cmd[cmd.index("--busdriver-state-dir-name") + 1] == ".opencode"
    assert "--drift-baseline" not in cmd
    assert "--phase0-status-timeout" not in cmd


def test_delivery_status_forwards_drift_baseline_and_includes_phase0_budget(monkeypatch):
    ns = runpy.run_path(str(DELIVER))

    def exercise(extra_args: list[str], expected_phase0_timeout: int) -> None:
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
                "--drift-baseline",
                "/tmp/drift-baseline.json",
                *extra_args,
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

        assert captured["timeout"] == 240 + 90 + expected_phase0_timeout + 30
        cmd = captured["cmd"]
        assert isinstance(cmd, list)
        assert cmd[cmd.index("--drift-baseline") + 1] == "/tmp/drift-baseline.json"
        assert cmd[cmd.index("--phase0-status-timeout") + 1] == str(expected_phase0_timeout)

    exercise([], 60)
    exercise(["--phase0-status-timeout", "45"], 45)


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


def test_artifact_write_failure_after_completed_mutation_preserves_side_effect_status(monkeypatch, capsys, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo")
    globals_ = ns["main"].__globals__
    delivery_status = {
        "schema": "hermes-busdriver-delivery-status/v0", "read_only": True, "ok": True,
        "repo": {"root": str(repo)}, "markers": {"blocking": []},
        "decision": {"status": "draft_changes_need_busdriver_finalization", "blockers": [], **{key: False for key in BLOCKED_KEYS}},
    }
    mutation_result = {
        "ok": True,
        "decision": {"status": "committed_release_failed", "reason": "finalization_lock_release_failed", **{key: False for key in BLOCKED_KEYS}},
        "mutating_run": {"status": "committed_release_failed", "reason": "finalization_lock_release_failed", "side_effects": [{"name": "git_commit", "ok": True}]},
        "steps": [{"name": "git_commit", "status": "completed", "reason": "committed"}],
    }
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args: (delivery_status, 0))
    monkeypatch.setitem(globals_, "execute_mutating_operation", lambda _args, _status: (mutation_result, 0))
    monkeypatch.setitem(globals_, "write_artifact", lambda _result: (_ for _ in ()).throw(OSError("artifact disk full")))
    monkeypatch.setattr(sys, "argv", [str(DELIVER), "--repo", str(repo), "--plugin-root", str(fake_busdriver(tmp_path / "busdriver")), "--mode", "execute", "--operation", "commit", "--commit-message", "msg"])

    rc = ns["main"]()
    data = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert data["ok"] is False
    assert data["decision"]["status"] == data["mutating_run"]["status"] == "committed_release_failed"
    assert data["decision"]["reason"] == data["steps"][0]["reason"] == "artifact_write_failed_after_side_effect"
    assert data["mutating_run"]["artifact_write_error"] == "artifact disk full"


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


def test_git_output_disables_fsmonitor_and_global_git_config(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo")
    captured = {}

    class FakeCompleted:
        returncode = 0
        stdout = " M .claude/litmus-passed.local\n"
        stderr = " warning with leading space\n"

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env")
        return FakeCompleted()

    monkeypatch.setattr(ns["git_output"].__globals__["subprocess"], "run", fake_run)

    rc, out, err = ns["git_output"](repo, "status", "--porcelain=v1", "--untracked-files=all")

    assert rc == 0
    assert out == " M .claude/litmus-passed.local"
    assert err == " warning with leading space"
    assert captured["cmd"][:5] == ["git", "-C", str(repo), "-c", "core.fsmonitor=false"]
    assert captured["env"]["GIT_CONFIG_GLOBAL"] == os.devnull
    assert captured["env"]["GIT_CONFIG_NOSYSTEM"] == "1"


def test_staged_diff_hash_uses_full_diff_bytes(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo")
    (repo / "tracked.txt").write_text("changed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    diff = run(["git", "diff", "--cached", "--no-ext-diff", "--no-textconv", "--no-color"], repo).stdout
    assert ns["staged_diff_hash"](repo) == __import__("hashlib").sha256(diff.encode()).hexdigest()


def test_live_remote_branch_head_preserves_credentials_env(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    captured = {}

    class CP:
        returncode = 0; stdout = "abc123\trefs/heads/feature\n"; stderr = ""

    def fake_run(_cmd, **kwargs):
        captured.update(env=kwargs.get("env")); return CP()

    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/agent.sock")
    monkeypatch.setattr(ns["live_remote_branch_head"].__globals__["subprocess"], "run", fake_run)
    assert ns["live_remote_branch_head"](init_repo(tmp_path / "repo"), "feature", "origin") == ("abc123", None)
    assert {k: captured["env"][k] for k in ("SSH_AUTH_SOCK", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")} == {"SSH_AUTH_SOCK": "/tmp/agent.sock", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def test_commit_marker_state_dirs_include_default_claude_and_opencode(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo")
    markers = [".claude/pr-backstop-verdict.local.json", ".claude/pr-grind-clean.local", ".opencode/pr-backstop-verdict.local.json", ".opencode/skip-litmus.local"]
    for path in markers:
        marker = repo / path; marker.parent.mkdir(exist_ok=True); marker.write_text("{}\n")
        assert run(["git", "add", path], repo).returncode == 0

    args = type("Args", (), {"busdriver_state_dir_name": None})()
    assert ns["busdriver_marker_state_dirs"](args) == (".claude", ".opencode")
    assert ns["staged_marker_entries"](repo, ns["busdriver_marker_state_dirs"](args)) == markers


def test_staged_marker_entries_detects_marker_renames_with_rename_detection_enabled(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo")
    for key, value in (("user.email", "test@example.test"), ("user.name", "Test User")):
        assert run(["git", "config", key, value], repo).returncode == 0
    marker = repo / ".claude" / "litmus-passed.local"; marker.parent.mkdir(); marker.write_text("reviewed\n")
    assert run(["git", "add", ".claude/litmus-passed.local"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    assert run(["git", "config", "--local", "diff.renames", "true"], repo).returncode == 0
    assert run(["git", "mv", ".claude/litmus-passed.local", "moved.txt"], repo).returncode == 0
    assert ns["staged_marker_entries"](repo, (".claude", ".opencode")) == [".claude/litmus-passed.local"]


def test_push_command_keeps_hooks_enabled_with_exact_remote_lease(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo")

    cmd = ns["push_command"](repo, "origin", "feature", None, "abc123")

    assert "--no-verify" not in cmd
    assert "--no-follow-tags" in cmd
    assert "--force-with-lease=refs/heads/feature:" in cmd
    assert cmd[-2:] == ["origin", "abc123:refs/heads/feature"]


def test_commit_staged_index_restores_reviewed_tree_when_hook_fails_after_mutation(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-hook-fail")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    before = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'hook-mutated-before-fail\n' > tracked.txt\ngit add tracked.txt\nexit 1\n")
    hook.chmod(0o755)
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "hook fails", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is False
    assert effect["error"] == "git_commit_failed_or_hook_drift"
    assert effect["restore_reviewed_index_ok"] is True
    assert effect["restore_reviewed_worktree_ok"] is True
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == before
    assert run(["git", "write-tree"], repo).stdout.strip() == effect["expected_tree"]
    assert (repo / "tracked.txt").read_text() == "reviewed\n"


def test_commit_staged_index_blocks_preexisting_untracked_reviewed_deletion_replacement(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-reviewed-untracked-replacement")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    before = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    assert run(["git", "rm", "tracked.txt"], repo).returncode == 0
    (repo / "tracked.txt").write_text("user replacement\n")

    effect = ns["commit_staged_index"](repo, "delete tracked", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is False
    assert effect["error"] == "pre_commit_reviewed_untracked_worktree"
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == before
    assert (repo / "tracked.txt").read_text() == "user replacement\n"
    assert any(substep["name"] == "git_pre_commit_reviewed_untracked_worktree_check" for substep in effect["substeps"])


def test_commit_staged_index_cleans_untracked_reviewed_deletion_after_failed_hook(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-hook-delete-untracked")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'hook-recreated-untracked\n' > tracked.txt\nexit 1\n")
    hook.chmod(0o755)
    assert run(["git", "rm", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "delete file", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is False
    assert effect["restore_reviewed_worktree_ok"] is True
    assert not (repo / "tracked.txt").exists()
    assert any(substep["name"] in {"git_clean_reviewed_untracked_failed_commit_drift", "git_clean_reviewed_deleted_paths_from_worktree"} for substep in effect["substeps"])


def test_commit_staged_index_restores_reviewed_deletion_when_hook_recreates_file(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-hook-delete")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    before = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'hook-recreated\n' > tracked.txt\ngit add tracked.txt\nexit 1\n")
    hook.chmod(0o755)
    assert run(["git", "rm", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "delete file", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is False
    assert effect["restore_reviewed_index_ok"] is True
    assert effect["restore_reviewed_worktree_ok"] is True
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == before
    assert run(["git", "write-tree"], repo).stdout.strip() == effect["expected_tree"]
    assert not (repo / "tracked.txt").exists()


def test_commit_staged_index_restores_reviewed_deletion_without_combined_restore_pathspec_abort(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-hook-delete-pathspec-abort")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    before = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'hook-recreated\n' > tracked.txt\ngit add tracked.txt\nexit 1\n")
    hook.chmod(0o755)
    assert run(["git", "rm", "tracked.txt"], repo).returncode == 0

    original_run_safe = ns["commit_staged_index"].__globals__["run_safe"]

    def fake_run_safe(cmd, *args, **kwargs):
        if cmd[:2] == ["git", "restore"] and "--staged" in cmd and ":(literal)tracked.txt" in cmd:
            return {"cmd": cmd, "returncode": 1, "ok": False, "stdout_tail": "", "stderr_tail": "error: pathspec 'tracked.txt' did not match any file(s) known to git"}
        return original_run_safe(cmd, *args, **kwargs)

    monkeypatch.setitem(ns["commit_staged_index"].__globals__, "run_safe", fake_run_safe)

    effect = ns["commit_staged_index"](repo, "delete file", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is False
    assert effect["restore_reviewed_index_ok"] is True
    assert effect["restore_reviewed_worktree_ok"] is True
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == before
    assert run(["git", "write-tree"], repo).stdout.strip() == effect["expected_tree"]
    assert not (repo / "tracked.txt").exists()


def test_commit_staged_index_batches_many_reviewed_path_restores(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-many-reviewed-paths")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    for index in range(105):
        path = repo / f"file-{index:03d}.txt"
        path.write_text("one\n")
        assert run(["git", "add", path.name], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    for index in range(105):
        (repo / f"file-{index:03d}.txt").write_text("reviewed\n")
    assert run(["git", "add", "-A"], repo).returncode == 0
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)

    effect = ns["commit_staged_index"](repo, "many paths", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is False
    assert effect["restore_reviewed_index_ok"] is True
    assert effect["restore_reviewed_worktree_ok"] is True
    restore_index = next(substep for substep in effect["substeps"] if substep["name"] == "git_restore_reviewed_index")
    assert restore_index["batch_count"] > 1
    restore_batches = [substep for substep in effect["substeps"] if substep["name"] == "git_restore_reviewed_index_batch"]
    assert restore_batches
    assert all(substep["path_count"] <= 100 for substep in restore_batches)


def test_commit_staged_index_detects_modified_preexisting_untracked_file(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-preexisting-untracked-modified")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    (repo / "note.tmp").write_text("untracked note\n")
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\nprintf 'modified untracked note\n' > note.tmp\n")
    hook.chmod(0o755)
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "detect untracked modification", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is True
    assert effect["warning"] == "post_commit_untracked_dirty"
    assert (repo / "note.tmp").read_text() == "modified untracked note\n"


def test_commit_staged_index_allows_preexisting_unrelated_untracked_file(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-preexisting-untracked")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    (repo / "note.tmp").write_text("untracked note\n")
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "allow unrelated untracked", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is True
    assert (repo / "note.tmp").read_text() == "untracked note\n"
    assert run(["git", "log", "-1", "--format=%s"], repo).stdout.strip() == "allow unrelated untracked"


def test_commit_staged_index_allows_large_preexisting_unrelated_untracked_file(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-large-preexisting-untracked")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    (repo / "large.tmp").write_bytes(b"x" * (ns["MARKER_FINGERPRINT_MAX_BYTES"] + 1))
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "allow large unrelated untracked", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is True
    assert "warning" not in effect
    assert (repo / "large.tmp").stat().st_size == ns["MARKER_FINGERPRINT_MAX_BYTES"] + 1
    assert run(["git", "log", "-1", "--format=%s"], repo).stdout.strip() == "allow large unrelated untracked"


def test_commit_staged_index_does_not_fingerprint_unrelated_preexisting_untracked_file(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-unrelated-untracked-no-fingerprint")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    (repo / "note.tmp").write_text("untracked note\n")
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    original_fingerprint = ns["commit_staged_index"].__globals__["marker_file_fingerprint"]

    def fake_marker_file_fingerprint(repo_arg, path):
        if path == "note.tmp":
            raise AssertionError("unrelated pre-existing untracked files must not be content-hashed")
        return original_fingerprint(repo_arg, path)

    monkeypatch.setitem(ns["commit_staged_index"].__globals__, "marker_file_fingerprint", fake_marker_file_fingerprint)

    effect = ns["commit_staged_index"](repo, "allow unrelated untracked", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is True
    assert "warning" not in effect
    assert (repo / "note.tmp").read_text() == "untracked note\n"


def test_commit_staged_index_detects_marker_drift_without_generic_untracked_identity(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-marker-drift-no-untracked-identity")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    marker = repo / ".claude" / "litmus-passed.local"
    marker.parent.mkdir()
    marker.write_text("marker-before\n")
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\nprintf 'marker-after\\n' > .claude/litmus-passed.local\n")
    hook.chmod(0o755)
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    original_identity = ns["commit_staged_index"].__globals__["untracked_file_identity"]

    def fake_untracked_file_identity(repo_arg, path):
        if path == ".claude/litmus-passed.local":
            raise AssertionError("marker drift must be handled before generic untracked identity checks")
        return original_identity(repo_arg, path)

    monkeypatch.setitem(ns["commit_staged_index"].__globals__, "untracked_file_identity", fake_untracked_file_identity)

    effect = ns["commit_staged_index"](repo, "marker drift", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is True
    assert effect["warning"] == "post_commit_untracked_dirty"
    assert ".claude/litmus-passed.local" in effect["post_commit_dirty_paths"]


def test_commit_staged_index_blocks_preexisting_unstaged_reviewed_file_dirty(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-preexisting-unstaged")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    (repo / "tracked.txt").write_text("user-unstaged\n")

    effect = ns["commit_staged_index"](repo, "must not overwrite unstaged", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is False
    assert effect["error"] == "pre_commit_non_marker_dirty_worktree"
    assert (repo / "tracked.txt").read_text() == "user-unstaged\n"
    assert run(["git", "log", "-1", "--format=%s"], repo).stdout.strip() == "init"


def test_commit_staged_index_cleans_untracked_reviewed_deletion_after_post_commit_hook(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-post-commit-delete-untracked")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\nprintf 'post-commit-recreated-untracked\n' > tracked.txt\n")
    hook.chmod(0o755)
    assert run(["git", "rm", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "delete file", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is True
    assert not (repo / "tracked.txt").exists()
    assert any(substep["name"] == "git_clean_reviewed_untracked_post_commit_drift" for substep in effect["substeps"])


def test_commit_staged_index_restores_reviewed_deletion_after_post_commit_index_drift_without_pathspec_abort(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-post-commit-delete-index-drift")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\nprintf 'post-commit-recreated-and-staged\n' > tracked.txt\ngit add tracked.txt\n")
    hook.chmod(0o755)
    assert run(["git", "rm", "tracked.txt"], repo).returncode == 0

    original_run_safe = ns["commit_staged_index"].__globals__["run_safe"]

    def fake_run_safe(cmd, *args, **kwargs):
        if cmd[:2] == ["git", "restore"] and "--staged" in cmd and ":(literal)tracked.txt" in cmd:
            return {"cmd": cmd, "returncode": 1, "ok": False, "stdout_tail": "", "stderr_tail": "error: pathspec 'tracked.txt' did not match any file(s) known to git"}
        return original_run_safe(cmd, *args, **kwargs)

    monkeypatch.setitem(ns["commit_staged_index"].__globals__, "run_safe", fake_run_safe)

    effect = ns["commit_staged_index"](repo, "delete file", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is True
    assert not (repo / "tracked.txt").exists()
    assert run(["git", "diff", "--quiet"], repo).returncode == 0
    assert run(["git", "diff", "--cached", "--quiet"], repo).returncode == 0
    assert any(substep["name"] == "git_restore_reviewed_paths_after_post_commit_drift" for substep in effect["substeps"])


def test_commit_staged_index_cleans_tracked_post_commit_hook_drift(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-post-commit-drift")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\nprintf 'post-commit-drift\n' > tracked.txt\n")
    hook.chmod(0o755)
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "post commit drift", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is True
    assert (repo / "tracked.txt").read_text() == "reviewed\n"
    assert run(["git", "diff", "--quiet"], repo).returncode == 0
    assert run(["git", "diff", "--cached", "--quiet"], repo).returncode == 0
    assert any(substep["name"] == "git_restore_reviewed_paths_after_post_commit_drift" for substep in effect["substeps"])


def test_commit_staged_index_detects_hook_created_invalid_marker(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-invalid-marker-post-commit")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    (repo / ".claude").mkdir()
    outside = tmp_path / "outside-marker-target"
    outside.write_text("outside\n")
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text(f"#!/bin/sh\nln -s {shlex.quote(str(outside))} .claude/litmus-passed.local\n")
    hook.chmod(0o755)
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "invalid marker", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is True
    assert effect["warning"] == "post_commit_untracked_dirty"
    assert (repo / ".claude" / "litmus-passed.local").is_symlink()


def test_commit_staged_index_fails_closed_when_post_commit_status_unavailable(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-post-commit-status-failed")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    before = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    real_git_output = ns["git_output"]
    status_calls = {"count": 0}

    def fake_git_output(repo_arg, *args):
        if args[:1] == ("status",):
            status_calls["count"] += 1
            if status_calls["count"] > 2:
                return 128, "", "status unavailable"
        return real_git_output(repo_arg, *args)

    monkeypatch.setitem(ns["commit_staged_index"].__globals__, "git_output", fake_git_output)

    effect = ns["commit_staged_index"](repo, "status unavailable", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is False
    assert effect["error"] == "post_commit_status_failed"
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() != before


def test_commit_staged_index_fails_without_overwriting_external_post_commit_drift(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-post-commit-external-drift")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    (repo / "external.txt").write_text("external-before\n")
    assert run(["git", "add", "tracked.txt", "external.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\nprintf 'external-drift\n' > external.txt\n")
    hook.chmod(0o755)
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "external post commit drift", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is True
    assert effect["warning"] == "post_commit_external_dirty_drift"
    assert (repo / "external.txt").read_text() == "external-drift\n"
    assert any(substep["name"] == "git_non_marker_tracked_post_commit_drift_left_for_operator" for substep in effect["substeps"])


def test_commit_staged_index_preserves_absolute_marker_state_dir_dirty(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-absolute-marker")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    state_dir = repo / ".custom-state"
    state_dir.mkdir()
    (state_dir / "litmus-passed.local").write_text("tracked-marker\n")
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", ".custom-state/litmus-passed.local", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'hook-mutated\n' > tracked.txt\ngit add tracked.txt\nexit 1\n")
    hook.chmod(0o755)
    (state_dir / "litmus-passed.local").write_text("allowed-absolute-marker-dirty\n")
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "preserve abs marker", {"BUSDRIVER_STATE_DIR": str(state_dir)})

    assert effect["ok"] is False
    assert (repo / "tracked.txt").read_text() == "reviewed\n"
    assert (state_dir / "litmus-passed.local").read_text() == "allowed-absolute-marker-dirty\n"


def test_commit_staged_index_detects_hook_rewritten_preexisting_marker_dirty(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-marker-rewrite")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / ".claude").mkdir()
    (repo / ".claude" / "litmus-passed.local").write_text("tracked-marker\n")
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", ".claude/litmus-passed.local", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'hook-rewrote-marker\n' > .claude/litmus-passed.local\nprintf 'hook-mutated\n' > tracked.txt\ngit add tracked.txt\nexit 1\n")
    hook.chmod(0o755)
    (repo / ".claude" / "litmus-passed.local").write_text("allowed-marker-dirty\n")
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "detect marker rewrite", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is False
    assert effect["restore_reviewed_worktree_ok"] is False
    assert (repo / ".claude" / "litmus-passed.local").read_text() == "hook-rewrote-marker\n"
    assert any(substep["name"] == "git_non_marker_tracked_failed_commit_drift_left_for_operator" for substep in effect["substeps"])


def test_commit_staged_index_detects_deleted_preexisting_untracked_marker(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-marker-delete")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / ".claude").mkdir()
    (repo / ".claude" / "litmus-passed.local").write_text("untracked-marker\n")
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nrm -f .claude/litmus-passed.local\nprintf 'hook-mutated\n' > tracked.txt\ngit add tracked.txt\nexit 1\n")
    hook.chmod(0o755)
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "detect marker delete", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is False
    assert effect["restore_reviewed_worktree_ok"] is False
    assert not (repo / ".claude" / "litmus-passed.local").exists()
    assert any(substep["name"] == "git_non_marker_tracked_failed_commit_drift_left_for_operator" for substep in effect["substeps"])


def test_commit_staged_index_preserves_preexisting_marker_dirty_on_hook_failure(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-marker-preserve")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / ".claude").mkdir()
    (repo / ".opencode").mkdir()
    (repo / ".claude" / "litmus-passed.local").write_text("tracked-marker\n")
    (repo / ".opencode" / "pr-review-passed.local").write_text("tracked-opencode-marker\n")
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", ".claude/litmus-passed.local", ".opencode/pr-review-passed.local", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'hook-mutated\n' > tracked.txt\ngit add tracked.txt\nexit 1\n")
    hook.chmod(0o755)
    (repo / ".claude" / "litmus-passed.local").write_text("allowed-marker-dirty\n")
    (repo / ".opencode" / "pr-review-passed.local").write_text("allowed-opencode-marker-dirty\n")
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "preserve marker", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is False
    assert (repo / "tracked.txt").read_text() == "reviewed\n"
    assert (repo / ".claude" / "litmus-passed.local").read_text() == "allowed-marker-dirty\n"
    assert (repo / ".opencode" / "pr-review-passed.local").read_text() == "allowed-opencode-marker-dirty\n"


def test_push_success_requires_remote_head_to_match_local_head(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-push-mismatch")
    plugin = fake_busdriver(tmp_path / "busdriver-push-mismatch")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")
    live_head_calls = {"count": 0}

    def fake_live_remote_branch_head(_repo, _branch, _remote):
        live_head_calls["count"] += 1
        if live_head_calls["count"] == 1:
            return None, "remote_branch_not_found"
        return "older-remote-head", None

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "repo_blocking_dirty_entries", lambda _repo, _dirs: [])
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args: True)
    monkeypatch.setitem(globals_, "remote_head_ancestor_status", lambda *_args: (True, None))
    monkeypatch.setitem(globals_, "live_remote_branch_head", fake_live_remote_branch_head)
    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return 0, "reviewed-local-head", ""
        if args[:1] == ("status",):
            return 0, "", ""
        return 0, "origin/main", ""
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    monkeypatch.setitem(globals_, "run_safe", lambda _cmd, _repo, **_kwargs: {"ok": True, "returncode": 0})
    args = argparse.Namespace(
        operation="push",
        mode="execute",
        repo=str(repo),
        plugin_root=str(plugin),
        state_dir=None,
        run_id="run-push-mismatch",
        pr=None,
        commit_message="title",
        pr_title="title",
        pr_body="body",
        push_remote="origin",
        push_branch=None,
        head=None,
        base="main",
        merge_method="squash",
        delete_branch=True,
        busdriver_state_dir_name=None,
        verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 1
    assert result["ok"] is False
    assert result["decision"]["reason"] == "remote_head_post_push_mismatch"
    assert any(effect["name"] == "git_push_remote_post_verify" and effect["ok"] is False for effect in result["mutating_run"]["side_effects"])


def test_commit_staged_index_uses_git_commit_hooks(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    marker = tmp_path / "hook-ran"
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(f"#!/bin/sh\nprintf ran > {shlex.quote(str(marker))}\n")
    hook.chmod(0o755)
    (repo / "tracked.txt").write_text("two\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "hooked commit", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is True
    assert marker.read_text() == "ran"
    assert effect["cmd"][:4] == ["git", "-c", "commit.gpgsign=false", "commit"]
    assert "--cleanup=verbatim" in effect["cmd"]
    assert "--no-verify" not in effect["cmd"]
    assert all("commit-tree" not in substep["cmd"] and "update-ref" not in substep["cmd"] for substep in effect["substeps"])


def test_commit_staged_index_rejects_commit_msg_hook_message_rewrite(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-commit-msg")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    before = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    hook = repo / ".git" / "hooks" / "commit-msg"
    hook.write_text("#!/bin/sh\nprintf 'altered message\n' > \"$1\"\n")
    hook.chmod(0o755)
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "expected message", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is False
    assert effect["error"] == "committed_message_mismatch_after_hooks"
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == before
    assert (repo / "tracked.txt").read_text() == "reviewed\n"
    assert any(substep["name"] == "git_log_message_after_commit" for substep in effect["substeps"])


def test_commit_staged_index_rejects_hook_modified_index(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    before = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'hook-mutated\n' > tracked.txt\ngit add tracked.txt\n")
    hook.chmod(0o755)
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "hook mutation", {"BUSDRIVER_STATE_DIR": ".claude"})

    assert effect["ok"] is False
    assert effect["error"] == "committed_tree_or_parent_mismatch_after_hooks"
    assert effect["reset_to_before_ok"] is True
    assert effect["restore_reviewed_index_ok"] is True
    assert effect["restore_reviewed_worktree_ok"] is True
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == before
    assert run(["git", "write-tree"], repo).stdout.strip() == effect["expected_tree"]
    assert (repo / "tracked.txt").read_text() == "reviewed\n"
    assert any(substep["name"] == "git_update_ref_before_after_hook_drift" for substep in effect["substeps"])
    assert any(substep["name"] == "git_restore_reviewed_tree" for substep in effect["substeps"])


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        (" M dir/file with space.txt", ["dir/file with space.txt"]),
        ("R  old name.txt -> new name.txt", ["old name.txt", "new name.txt"]),
        (' M "dir/file\\nname.txt"', ["dir/file\nname.txt"]),
        ('C  "old\\tname.txt" -> "new\\tname.txt"', ["old\tname.txt", "new\tname.txt"]),
        (' M "\\303\\251.txt"', ["é.txt"]),
        ('R  "old -> name.txt" -> "new.txt"', ["old -> name.txt", "new.txt"]),
        ('R  "old.txt" -> "new -> name.txt"', ["old.txt", "new -> name.txt"]),
        ('R  old_file.txt -> "new -> name.txt"', ["old_file.txt", "new -> name.txt"]),
        ('R  old -> name.txt -> new.txt', ["old -> name.txt", "new.txt"]),
        ('R  old -> name.txt -> "new -> name.txt"', ["old -> name.txt", "new -> name.txt"]),
        ("?? path/with\\backslash.txt", ["path/with\\backslash.txt"]),
    ],
)
def test_porcelain_entry_paths_handles_spaces_renames_and_c_quoting(entry: str, expected: list[str]):
    ns = runpy.run_path(str(DELIVER))

    assert ns["porcelain_entry_paths"](entry) == expected


def test_porcelain_entry_paths_property_style_quoted_rename_round_trip():
    ns = runpy.run_path(str(DELIVER))

    def quote(path: str) -> str:
        return '"' + path.replace("\\", "\\\\").replace('"', '\\"').replace("\t", "\\t").replace("\n", "\\n") + '"'

    old_paths = ["old -> name.txt", "old spaced.txt", "old\tname.txt"]
    new_paths = ["new -> name.txt", "new spaced.txt", "new\nname.txt"]
    for old_path in old_paths:
        for new_path in new_paths:
            entry = f"R  {quote(old_path)} -> {quote(new_path)}"
            assert ns["porcelain_entry_paths"](entry) == [old_path, new_path]


def test_marker_file_fingerprint_does_not_follow_symlink_swapped_after_lstat(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = tmp_path / "repo-marker-swap"
    marker_dir = repo / ".claude"
    marker_dir.mkdir(parents=True)
    marker = marker_dir / "litmus-passed.local"
    marker.write_text("safe marker\n")
    outside = tmp_path / "outside-marker-target"
    outside.write_text("outside secret\n")
    real_open = os.open
    swapped = {"done": False}

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        if Path(path) == marker and not swapped["done"]:
            swapped["done"] = True
            marker.unlink()
            marker.symlink_to(outside)
        if dir_fd is None:
            return real_open(path, flags, mode)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(ns["os"], "open", swapping_open)

    fingerprint = ns["marker_file_fingerprint"](repo, ".claude/litmus-passed.local")

    assert swapped["done"] is True
    assert fingerprint == "<read-error>"
    assert marker.is_symlink()


def test_marker_file_fingerprint_does_not_follow_symlink(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = tmp_path / "repo-marker-symlink"
    repo.mkdir()
    outside = tmp_path / "outside-large-secret"
    outside.write_text("outside-secret-content")
    marker_dir = repo / ".claude"
    marker_dir.mkdir()
    marker = marker_dir / "litmus-passed.local"
    marker.symlink_to(outside)

    fingerprint = ns["marker_file_fingerprint"](repo, ".claude/litmus-passed.local")

    assert fingerprint.startswith("<symlink>:")
    assert fingerprint != hashlib.sha256(outside.read_bytes()).hexdigest()


def test_marker_snapshot_rejects_marker_that_disappears_before_fingerprint(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = tmp_path / "repo-marker-missing-during-snapshot"
    marker_dir = repo / ".claude"
    marker_dir.mkdir(parents=True)
    marker = marker_dir / "litmus-passed.local"
    marker.write_text("marker\n")

    monkeypatch.setitem(ns["marker_evidence_snapshot_from_status"].__globals__, "marker_file_fingerprint", lambda _repo, _path: "<missing>")

    snapshot = ns["marker_evidence_snapshot_from_status"](repo, "?? .claude/litmus-passed.local\n", {".claude/litmus-passed.local"})

    assert snapshot == {}
    assert ns["marker_fingerprint_valid"]("<missing>") is False


def test_marker_evidence_snapshot_excludes_too_large_marker(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = tmp_path / "repo-large-marker"
    repo.mkdir()
    marker_dir = repo / ".claude"
    marker_dir.mkdir()
    marker = marker_dir / "litmus-passed.local"
    marker.write_bytes(b"x" * (ns["MARKER_FINGERPRINT_MAX_BYTES"] + 1))

    snapshot = ns["marker_evidence_snapshot_from_status"](repo, "?? .claude/litmus-passed.local\n", {".claude/litmus-passed.local"})

    assert snapshot == {}
    assert ns["marker_file_fingerprint"](repo, ".claude/litmus-passed.local").startswith("<too-large:")


def test_push_remote_safety_rejects_local_push_modifiers(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))

    cases = [
        ("remote.origin.mirror", "true", "remote_mirror_blocked_for_push"),
        ("remote.origin.push", "refs/heads/*:refs/heads/*", "remote_push_refspec_blocked_for_push"),
        ("push.followTags", "true", "push_follow_tags_blocked_for_push"),
        ("push.pushOption", "ci.skip", "push_option_blocked_for_push"),
    ]
    for index, (key, value, reason) in enumerate(cases):
        repo = init_repo(tmp_path / f"repo-{index}")
        assert run(["git", "remote", "add", "origin", "https://github.com/octo/repo.git"], repo).returncode == 0
        assert run(["git", "config", "--local", key, value], repo).returncode == 0

        assert ns["push_remote_safety"](repo, "origin") == (False, reason)


def test_pr_create_checks_push_remote_safety_before_remote_head_lookup(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo")
    globals_ = ns["execute_mutating_operation"].__globals__
    calls = {"remote_head": 0}
    decision = {"status": "pr_review_fresh", "blockers": [], **{key: False for key in BLOCKED_KEYS}}
    delivery_status = {
        "schema": "hermes-busdriver-delivery-status/v0", "read_only": True, "ok": True,
        "repo": {"root": str(repo)}, "markers": {"blocking": []}, "decision": decision,
        "litmus_status": {"available": True, "ok": True, "summary": {"schema": "hermes-busdriver-litmus-status/v0", "read_only": True, "ok": True, "authority_safe": True, "decision_status_recognized": True, "decision": {"status": "pr_review_fresh", **{key: False for key in BLOCKED_KEYS}}}},
    }
    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "t"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "normalized_pr_head_arg", lambda _repo, _head, _branch, _remote: (None, None))
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (False, "url_rewrite_blocked_for_push"))
    monkeypatch.setitem(globals_, "live_remote_branch_head", lambda *_args: calls.__setitem__("remote_head", calls["remote_head"] + 1) or ("abc", None))
    args = argparse.Namespace(operation="pr-create", mode="execute", repo=str(repo), plugin_root=str(fake_busdriver(tmp_path / "busdriver")), state_dir=None, run_id=None, pr=None, commit_message="title", pr_title=None, pr_body="body", push_remote="origin", push_branch=None, head=None, base=None, busdriver_state_dir_name=None)

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 2
    assert result["decision"]["reason"] == "url_rewrite_blocked_for_push"
    assert calls["remote_head"] == 0


def test_execute_commit_requires_message_and_writes_blocked_artifact(tmp_path: Path):
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
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    assert cp.stderr == ""
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "commit_message_required"
    assert_finalization_blocked(data["decision"])
    assert Path(data["run_artifact_path"]).exists()


def test_failed_push_existing_remote_unchanged_remains_git_push_failed(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-failed-push-remote-unchanged")
    plugin = fake_busdriver(tmp_path / "busdriver-failed-push-remote-unchanged")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")

    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return 0, "reviewed-local-head", ""
        if args[:1] == ("status",):
            return 0, "", ""
        return 0, "origin/main", ""

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "repo_blocking_dirty_entries", lambda _repo, _dirs: [])
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args: True)
    monkeypatch.setitem(globals_, "remote_head_ancestor_status", lambda *_args: (True, None))
    monkeypatch.setitem(globals_, "live_remote_branch_head", lambda _repo, _branch, _remote: ("old-remote-head", None))
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    monkeypatch.setitem(globals_, "run_safe", lambda _cmd, _repo, **_kwargs: {"ok": False, "returncode": 1})
    args = argparse.Namespace(
        operation="push", mode="execute", repo=str(repo), plugin_root=str(plugin), state_dir=None, run_id="run-failed-push-remote-unchanged",
        pr=None, commit_message="title", pr_title="title", pr_body="body", push_remote="origin", push_branch=None, head=None,
        base="main", merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 1
    assert result["ok"] is False
    assert result["decision"]["reason"] == "git_push_failed"


def test_failed_push_rechecks_existing_remote_and_accepts_verified_update(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-failed-push-remote-updated")
    plugin = fake_busdriver(tmp_path / "busdriver-failed-push-remote-updated")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")
    live_head_calls = {"count": 0}

    def fake_live_remote_branch_head(_repo, _branch, _remote):
        live_head_calls["count"] += 1
        if live_head_calls["count"] == 1:
            return "old-remote-head", None
        return "reviewed-local-head", None

    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return 0, "reviewed-local-head", ""
        if args[:1] == ("status",):
            return 0, "", ""
        return 0, "origin/main", ""

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "repo_blocking_dirty_entries", lambda _repo, _dirs: [])
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args: True)
    monkeypatch.setitem(globals_, "remote_head_ancestor_status", lambda *_args: (True, None))
    monkeypatch.setitem(globals_, "live_remote_branch_head", fake_live_remote_branch_head)
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    monkeypatch.setitem(globals_, "run_safe", lambda _cmd, _repo, **_kwargs: {"ok": False, "returncode": 1})
    args = argparse.Namespace(
        operation="push", mode="execute", repo=str(repo), plugin_root=str(plugin), state_dir=None, run_id="run-failed-push-remote-updated",
        pr=None, commit_message="title", pr_title="title", pr_body="body", push_remote="origin", push_branch=None, head=None,
        base="main", merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 1
    assert result["ok"] is False
    assert result["decision"]["status"] == result["mutating_run"]["status"] == "pushed"
    assert result["decision"]["reason"] == "pushed_after_failed_push_remote_verified"
    assert [step["status"] for step in result["steps"]] == ["passed", "passed", "failed"]
    assert any(effect["name"] == "git_push_remote_recheck" and effect["remote_head"] == "reviewed-local-head" for effect in result["mutating_run"]["side_effects"])


def test_failed_push_remote_updated_preserves_pushed_status_when_local_postcheck_dirty(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-failed-push-remote-updated-local-dirty")
    plugin = fake_busdriver(tmp_path / "busdriver-failed-push-remote-updated-local-dirty")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")
    live_head_calls = {"count": 0}

    def fake_live_remote_branch_head(_repo, _branch, _remote):
        live_head_calls["count"] += 1
        if live_head_calls["count"] == 1:
            return "old-remote-head", None
        return "reviewed-local-head", None

    status_calls = {"count": 0}
    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return 0, "reviewed-local-head", ""
        if args[:1] == ("status",):
            status_calls["count"] += 1
            return (0, "", "") if status_calls["count"] == 1 else (0, "?? hook-output.txt\n", "")
        return 0, "origin/main", ""

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    dirty_calls = {"count": 0}
    def fake_repo_blocking_dirty_entries(_repo, _dirs):
        dirty_calls["count"] += 1
        return ["?? hook-output.txt"]
    monkeypatch.setitem(globals_, "repo_blocking_dirty_entries", fake_repo_blocking_dirty_entries)
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args: True)
    monkeypatch.setitem(globals_, "remote_head_ancestor_status", lambda *_args: (True, None))
    monkeypatch.setitem(globals_, "live_remote_branch_head", fake_live_remote_branch_head)
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    monkeypatch.setitem(globals_, "run_safe", lambda _cmd, _repo, **_kwargs: {"ok": False, "returncode": 1})
    args = argparse.Namespace(
        operation="push", mode="execute", repo=str(repo), plugin_root=str(plugin), state_dir=None, run_id="run-failed-push-remote-updated-local-dirty",
        pr=None, commit_message="title", pr_title="title", pr_body="body", push_remote="origin", push_branch=None, head=None,
        base="main", merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 1
    assert result["ok"] is False
    assert result["decision"]["status"] == result["mutating_run"]["status"] == "pushed"
    assert result["decision"]["reason"] == "post_push_local_drift_after_failed_push"
    assert [step["status"] for step in result["steps"]] == ["passed", "passed", "failed"]
    assert any(effect["name"] == "git_push_remote_recheck" and effect["remote_head"] == "reviewed-local-head" for effect in result["mutating_run"]["side_effects"])


def test_failed_push_local_postcheck_dirty_without_remote_completion_stays_blocked(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-failed-push-local-dirty-no-remote")
    plugin = fake_busdriver(tmp_path / "busdriver-failed-push-local-dirty-no-remote")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")

    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return 0, "reviewed-local-head", ""
        if args[:1] == ("status",):
            return 0, "", ""
        return 0, "origin/main", ""

    dirty_calls = {"count": 0}
    def fake_repo_blocking_dirty_entries(_repo, _dirs):
        dirty_calls["count"] += 1
        return ["?? hook-output.txt"]

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "repo_blocking_dirty_entries", fake_repo_blocking_dirty_entries)
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args: True)
    monkeypatch.setitem(globals_, "remote_head_ancestor_status", lambda *_args: (True, None))
    monkeypatch.setitem(globals_, "live_remote_branch_head", lambda _repo, _branch, _remote: ("old-remote-head", None))
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    monkeypatch.setitem(globals_, "run_safe", lambda _cmd, _repo, **_kwargs: {"ok": False, "returncode": 1})
    args = argparse.Namespace(
        operation="push", mode="execute", repo=str(repo), plugin_root=str(plugin), state_dir=None, run_id="run-failed-push-local-dirty-no-remote",
        pr=None, commit_message="title", pr_title="title", pr_body="body", push_remote="origin", push_branch=None, head=None,
        base="main", merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 1
    assert result["ok"] is False
    assert result["decision"]["status"] == result["mutating_run"]["status"] == "blocked"
    assert result["decision"]["reason"] == "post_push_local_drift_after_failed_push_unverified"
    assert [step["status"] for step in result["steps"]] == ["checked", "blocked", "skipped"]


def test_push_blocks_dirty_worktree_at_pre_push_snapshot(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-pre-push-dirty")
    plugin = fake_busdriver(tmp_path / "busdriver-pre-push-dirty")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")

    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return 0, "reviewed-local-head", ""
        if args[:1] == ("status",):
            return 0, "?? stray.txt\n", ""
        return 0, "origin/main", ""

    push_called = {"value": False}
    def fake_run_safe(cmd, _repo, **_kwargs):
        if len(cmd) >= 2 and cmd[0:2] == ["git", "push"]:
            push_called["value"] = True
        return {"ok": True, "returncode": 0}

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "repo_blocking_dirty_entries", lambda _repo, _dirs: [])
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args: True)
    monkeypatch.setitem(globals_, "remote_head_ancestor_status", lambda *_args: (True, None))
    monkeypatch.setitem(globals_, "live_remote_branch_head", lambda _repo, _branch, _remote: (None, "remote_branch_not_found"))
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    monkeypatch.setitem(globals_, "run_safe", fake_run_safe)
    args = argparse.Namespace(
        operation="push", mode="execute", repo=str(repo), plugin_root=str(plugin), state_dir=None, run_id="run-pre-push-dirty",
        pr=None, commit_message="title", pr_title="title", pr_body="body", push_remote="origin", push_branch=None, head=None,
        base="main", merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 2
    assert result["ok"] is False
    assert result["decision"]["reason"] == "pre_push_dirty_worktree"
    assert push_called["value"] is False


def test_push_success_detects_preexisting_marker_content_rewrite(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-push-marker-drift")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "litmus-passed.local").write_text("before-marker\n")
    plugin = fake_busdriver(tmp_path / "busdriver-push-marker-drift")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")
    live_head_calls = {"count": 0}

    def fake_live_remote_branch_head(_repo, _branch, _remote):
        live_head_calls["count"] += 1
        if live_head_calls["count"] == 1:
            return None, "remote_branch_not_found"
        return "reviewed-local-head", None

    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return 0, "reviewed-local-head", ""
        if args[:1] == ("status",):
            return 0, " M .claude/litmus-passed.local\n", ""
        return 0, "origin/main", ""

    def fake_run_safe(cmd, _repo, **_kwargs):
        if len(cmd) >= 2 and cmd[0:2] == ["git", "push"]:
            (repo / ".claude" / "litmus-passed.local").write_text("after-marker\n")
        return {"ok": True, "returncode": 0}

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "repo_blocking_dirty_entries", lambda _repo, _dirs: [])
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args: True)
    monkeypatch.setitem(globals_, "remote_head_ancestor_status", lambda *_args: (True, None))
    monkeypatch.setitem(globals_, "live_remote_branch_head", fake_live_remote_branch_head)
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    monkeypatch.setitem(globals_, "run_safe", fake_run_safe)
    args = argparse.Namespace(
        operation="push",
        mode="execute",
        repo=str(repo),
        plugin_root=str(plugin),
        state_dir=None,
        run_id="run-push-marker-drift",
        pr=None,
        commit_message="title",
        pr_title="title",
        pr_body="body",
        push_remote="origin",
        push_branch=None,
        head=None,
        base="main",
        merge_method="squash",
        delete_branch=True,
        busdriver_state_dir_name=None,
        verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 1
    assert result["ok"] is False
    assert result["decision"]["status"] == result["mutating_run"]["status"] == "pushed"
    assert result["decision"]["reason"] == "pushed_with_post_push_dirty_worktree"
    assert [step["status"] for step in result["steps"]] == ["passed", "passed", "failed"]
    assert any(effect["name"] == "post_push_dirty_check" and effect["marker_unchanged"] is False for effect in result["mutating_run"]["side_effects"])


def test_push_success_reports_completed_local_head_mismatch_as_postflight_failure(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-push-local-head-mismatch")
    plugin = fake_busdriver(tmp_path / "busdriver-push-local-head-mismatch")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")
    live_head_calls = {"count": 0}

    def fake_live_remote_branch_head(_repo, _branch, _remote):
        live_head_calls["count"] += 1
        if live_head_calls["count"] == 1:
            return None, "remote_branch_not_found"
        return "reviewed-local-head", None

    local_head_calls = {"count": 0}

    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            local_head_calls["count"] += 1
            if local_head_calls["count"] == 1:
                return 0, "reviewed-local-head", ""
            return 0, "different-local-head", ""
        if args[:1] == ("status",):
            return 0, "", ""
        return 0, "origin/main", ""

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "repo_blocking_dirty_entries", lambda _repo, _dirs: [])
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args: True)
    monkeypatch.setitem(globals_, "remote_head_ancestor_status", lambda *_args: (True, None))
    monkeypatch.setitem(globals_, "live_remote_branch_head", fake_live_remote_branch_head)
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    monkeypatch.setitem(globals_, "run_safe", lambda _cmd, _repo, **_kwargs: {"ok": True, "returncode": 0})
    args = argparse.Namespace(
        operation="push", mode="execute", repo=str(repo), plugin_root=str(plugin), state_dir=None, run_id="run-push-local-head-mismatch",
        pr=None, commit_message="title", pr_title="title", pr_body="body", push_remote="origin", push_branch=None, head="reviewed-local-head",
        base="main", merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 1
    assert result["ok"] is False
    assert result["decision"]["status"] == result["mutating_run"]["status"] == "pushed"
    assert result["decision"]["reason"] == "local_head_post_push_mismatch"
    assert [step["status"] for step in result["steps"]] == ["passed", "passed", "failed"]


def test_push_success_fails_closed_when_post_push_status_unavailable(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-push-status-failed")
    plugin = fake_busdriver(tmp_path / "busdriver-push-status-failed")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")
    live_head_calls = {"count": 0}
    status_calls = {"count": 0}

    def fake_live_remote_branch_head(_repo, _branch, _remote):
        live_head_calls["count"] += 1
        if live_head_calls["count"] == 1:
            return None, "remote_branch_not_found"
        return "reviewed-local-head", None

    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return 0, "reviewed-local-head", ""
        if args[:1] == ("status",):
            status_calls["count"] += 1
            if status_calls["count"] == 1:
                return 0, "", ""
            return 128, "", "status unavailable"
        return 0, "origin/main", ""

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "repo_blocking_dirty_entries", lambda _repo, _dirs: [])
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args: True)
    monkeypatch.setitem(globals_, "remote_head_ancestor_status", lambda *_args: (True, None))
    monkeypatch.setitem(globals_, "live_remote_branch_head", fake_live_remote_branch_head)
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    monkeypatch.setitem(globals_, "run_safe", lambda _cmd, _repo, **_kwargs: {"ok": True, "returncode": 0})
    args = argparse.Namespace(
        operation="push", mode="execute", repo=str(repo), plugin_root=str(plugin), state_dir=None, run_id="run-push-status-failed",
        pr=None, commit_message="title", pr_title="title", pr_body="body", push_remote="origin", push_branch=None, head=None,
        base="main", merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 1
    assert result["ok"] is False
    assert result["decision"]["status"] == result["mutating_run"]["status"] == "pushed"
    assert result["decision"]["reason"] == "post_push_status_failed"
    assert [step["status"] for step in result["steps"]] == ["passed", "passed", "failed"]
    assert any(effect["name"] == "post_push_dirty_check" and effect["returncode"] == 128 for effect in result["mutating_run"]["side_effects"])


def test_push_success_requires_clean_post_push_worktree(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-push-dirty")
    plugin = fake_busdriver(tmp_path / "busdriver-push-dirty")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")
    live_head_calls = {"count": 0}

    def fake_live_remote_branch_head(_repo, _branch, _remote):
        live_head_calls["count"] += 1
        if live_head_calls["count"] == 1:
            return None, "remote_branch_not_found"
        return "reviewed-local-head", None

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    dirty_calls = {"count": 0}
    def fake_repo_blocking_dirty_entries(_repo, _dirs):
        dirty_calls["count"] += 1
        return ["?? hook-output.txt"]
    monkeypatch.setitem(globals_, "repo_blocking_dirty_entries", fake_repo_blocking_dirty_entries)
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args: True)
    monkeypatch.setitem(globals_, "remote_head_ancestor_status", lambda *_args: (True, None))
    monkeypatch.setitem(globals_, "live_remote_branch_head", fake_live_remote_branch_head)
    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return 0, "reviewed-local-head", ""
        if args[:1] == ("status",):
            return 0, "", ""
        return 0, "origin/main", ""
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    monkeypatch.setitem(globals_, "run_safe", lambda _cmd, _repo, **_kwargs: {"ok": True, "returncode": 0})
    args = argparse.Namespace(
        operation="push",
        mode="execute",
        repo=str(repo),
        plugin_root=str(plugin),
        state_dir=None,
        run_id="run-push-dirty",
        pr=None,
        commit_message="title",
        pr_title="title",
        pr_body="body",
        push_remote="origin",
        push_branch=None,
        head=None,
        base="main",
        merge_method="squash",
        delete_branch=True,
        busdriver_state_dir_name=None,
        verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 1
    assert result["ok"] is False
    assert result["decision"]["status"] == result["mutating_run"]["status"] == "pushed"
    assert result["decision"]["reason"] == "pushed_with_post_push_dirty_worktree"
    assert [step["status"] for step in result["steps"]] == ["passed", "passed", "failed"]
    assert any(effect["name"] == "post_push_dirty_check" and effect["ok"] is False for effect in result["mutating_run"]["side_effects"])


def test_execute_commit_preserves_committed_status_when_post_commit_check_fails(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-commit-postcheck-failed")
    plugin = fake_busdriver(tmp_path / "busdriver-commit-postcheck-failed")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "draft_changes_need_busdriver_finalization", "commit_litmus_fresh")
    git_rev_parse_calls = {"count": 0}

    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            git_rev_parse_calls["count"] += 1
            return 0, "before" if git_rev_parse_calls["count"] == 1 else "after", ""
        if args[:1] == ("status",):
            return 0, "", ""
        return 0, "origin/main", ""

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "staged_changes_status", lambda _repo: (True, None))
    monkeypatch.setitem(globals_, "commit_blocking_dirty_entries", lambda _status, _args: [])
    monkeypatch.setitem(globals_, "commit_litmus_staged_diff_blocker", lambda _status, _repo: None)
    monkeypatch.setitem(globals_, "commit_staged_index", lambda _repo, _message, _env_extra=None: {"ok": False, "returncode": 1, "error": "post_commit_status_failed"})
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    args = argparse.Namespace(
        operation="commit", mode="execute", repo=str(repo), plugin_root=str(plugin), state_dir=None, run_id="run-commit-postcheck-failed",
        pr=None, commit_message="title", pr_title="title", pr_body="body", push_remote="origin", push_branch=None, head=None,
        base="main", merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 1
    assert result["ok"] is False
    assert result["decision"]["status"] == result["mutating_run"]["status"] == "committed"
    assert result["decision"]["reason"] == result["mutating_run"]["reason"] == "post_commit_status_failed"
    assert [step["status"] for step in result["steps"]] == ["passed", "passed", "failed"]


def test_execute_commit_surfaces_completed_commit_dirty_warning(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-commit-warning")
    plugin = fake_busdriver(tmp_path / "busdriver-commit-warning")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "draft_changes_need_busdriver_finalization", "commit_litmus_fresh")
    git_rev_parse_calls = {"count": 0}

    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            git_rev_parse_calls["count"] += 1
            return 0, "before" if git_rev_parse_calls["count"] == 1 else "after", ""
        if args[:1] == ("status",):
            return 0, "", ""
        return 0, "origin/main", ""

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "staged_changes_status", lambda _repo: (True, None))
    monkeypatch.setitem(globals_, "commit_blocking_dirty_entries", lambda _status, _args: [])
    monkeypatch.setitem(globals_, "commit_litmus_staged_diff_blocker", lambda _status, _repo: None)
    monkeypatch.setitem(globals_, "commit_staged_index", lambda _repo, _message, _env_extra=None: {"ok": True, "returncode": 0, "warning": "post_commit_external_dirty_drift"})
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    args = argparse.Namespace(
        operation="commit", mode="execute", repo=str(repo), plugin_root=str(plugin), state_dir=None, run_id="run-commit-warning",
        pr=None, commit_message="title", pr_title="title", pr_body="body", push_remote="origin", push_branch=None, head=None,
        base="main", merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 0
    assert result["ok"] is True
    assert result["decision"]["status"] == result["mutating_run"]["status"] == "committed"
    assert result["decision"]["reason"] == result["mutating_run"]["reason"] == "post_commit_external_dirty_drift"
    assert [step["status"] for step in result["steps"]] == ["passed", "passed", "failed"]


@pytest.mark.parametrize(
    ("operation", "decision_status", "litmus_decision_status", "expected_status", "expected_reason", "expected_effect", "allowed_flag"),
    [
        ("pre-pr-review", "no_local_delivery_candidate", "stale_or_missing", "pre_pr_review_complete", "busdriver_pre_pr_review_marker_written", "busdriver_write_pr_marker", None),
        ("commit", "draft_changes_need_busdriver_finalization", "commit_litmus_fresh", "committed", "committed", "git_commit", "commit_allowed"),
        ("push", "pr_review_fresh", "pr_review_fresh", "pushed", "pushed", "git_push", "push_allowed"),
        ("pr-create", "pr_review_fresh", "pr_review_fresh", "pr_created", "pr_created", "gh_pr_create", "pr_allowed"),
        ("merge", "pr_clean_read_only", "pr_review_fresh", "merged", "merged", "gh_pr_merge", "merge_allowed"),
    ],
)
def test_mutating_operation_success_paths_record_lock_release_authority_and_side_effects(
    monkeypatch,
    tmp_path: Path,
    operation: str,
    decision_status: str,
    litmus_decision_status: str,
    expected_status: str,
    expected_reason: str,
    expected_effect: str,
    allowed_flag: str | None,
):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / f"repo-{operation}")
    plugin = fake_busdriver(tmp_path / f"busdriver-{operation}")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, decision_status, litmus_decision_status)
    git_rev_parse_calls = {"count": 0}

    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            if operation == "commit":
                git_rev_parse_calls["count"] += 1
                return 0, "before" if git_rev_parse_calls["count"] == 1 else "after", ""
            return 0, "after", ""
        if args[:1] == ("status",):
            return 0, "", ""
        return 0, "origin/main", ""

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "repo_blocking_dirty_entries", lambda _repo, _dirs: [])
    monkeypatch.setitem(globals_, "staged_changes_status", lambda _repo: (True, None))
    monkeypatch.setitem(globals_, "commit_blocking_dirty_entries", lambda _status, _args: [])
    monkeypatch.setitem(globals_, "commit_litmus_staged_diff_blocker", lambda _status, _repo: None)
    monkeypatch.setitem(globals_, "commit_staged_index", lambda _repo, _message, _env_extra=None: {"ok": True, "returncode": 0})
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args: True)
    monkeypatch.setitem(globals_, "remote_head_ancestor_status", lambda *_args: (True, None))
    monkeypatch.setitem(globals_, "normalized_pr_head_arg", lambda _repo, _head, _branch, _remote: (_head, None))
    monkeypatch.setitem(globals_, "github_repo_slug", lambda _repo, _remote: "owner/repo")
    monkeypatch.setitem(globals_, "pr_base_ref", lambda _repo, _base=None: "origin/main")
    monkeypatch.setitem(globals_, "remote_branch_name_from_ref", lambda _ref: "main")
    monkeypatch.setitem(globals_, "git_output", fake_git_output)

    if operation == "pre-pr-review":
        monkeypatch.setitem(
            globals_,
            "run_busdriver_pre_pr_review",
            lambda _repo, _args: ({"ok": True, "reason": "busdriver_pre_pr_review_marker_written", "side_effects": [{"name": "busdriver_write_pr_marker", "ok": True}]}, 0),
        )
    elif operation == "push":
        live_head_calls = {"count": 0}
        def fake_live_remote_branch_head(_repo, _branch, _remote):
            live_head_calls["count"] += 1
            if live_head_calls["count"] == 1:
                return None, "remote_branch_not_found"
            return "after", None
        monkeypatch.setitem(globals_, "live_remote_branch_head", fake_live_remote_branch_head)
        monkeypatch.setitem(globals_, "run_safe", lambda _cmd, _repo, **_kwargs: {"ok": True, "returncode": 0})
    elif operation == "pr-create":
        monkeypatch.setitem(globals_, "live_remote_branch_head", lambda _repo, _branch, _remote: ("after", None))
        monkeypatch.setitem(globals_, "run_safe", lambda _cmd, _repo, **_kwargs: {"ok": True, "returncode": 0})
    elif operation == "merge":
        monkeypatch.setitem(globals_, "run_pr_grind_loop", lambda _repo, _args: (safe_loop_payload(), 0))
        monkeypatch.setitem(globals_, "pr_grind_loop_envelope_safe", lambda _loop: True)
        monkeypatch.setitem(globals_, "run_safe", lambda _cmd, _repo, **_kwargs: {"ok": True, "returncode": 0})

    args = argparse.Namespace(
        operation=operation,
        mode="execute",
        repo=str(repo),
        plugin_root=str(plugin),
        state_dir=None,
        run_id=f"run-{operation}",
        pr=7 if operation == "merge" else None,
        commit_message="title",
        pr_title="title",
        pr_body="body",
        push_remote="origin",
        push_branch=None,
        head="feature" if operation == "pr-create" else None,
        base="main",
        merge_method="squash",
        delete_branch=True,
        busdriver_state_dir_name=None,
        verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 0
    assert result["ok"] is True
    assert result["decision"] == {"status": expected_status, "reason": expected_reason, **{key: False for key in BLOCKED_KEYS}}
    mutating_run = result["mutating_run"]
    assert mutating_run["schema"] == "hermes-busdriver-mutating-delivery-run/v0"
    assert mutating_run["status"] == expected_status
    assert mutating_run["reason"] == expected_reason
    assert mutating_run["repo_root"] == str(repo)
    assert mutating_run["lock_acquire"]["acquired"] is True
    assert mutating_run["lock_release"]["released"] is True
    assert mutating_run["authority"]["allowed"] is True
    assert mutating_run["authority"]["finalization_allowed"] is True
    assert mutating_run["authority"]["marker_write_allowed"] is False
    if allowed_flag:
        assert mutating_run["authority"][allowed_flag] is True
    assert [step["status"] for step in result["steps"]] == ["passed", "passed", "passed"]
    effect_names = [effect["name"] for effect in mutating_run["side_effects"]]
    assert effect_names[0] == "delivery_status_after_lock"
    assert expected_effect in effect_names


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
