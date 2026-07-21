import hashlib
import json
import importlib.machinery
import importlib.util
from pathlib import Path


SMOKE = Path(__file__).resolve().parents[2] / "scripts" / "hermes-busdriver-smoke"


def load_smoke_module():
    import sys

    loader = importlib.machinery.SourceFileLoader("hermes_busdriver_smoke", str(SMOKE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def test_summary_parse_error_marks_check_failed():
    smoke = load_smoke_module()

    for initial_returncode, expected_returncode in [(0, 1), (42, 42)]:
        check = {"returncode": initial_returncode, "ok": True}
        smoke.mark_summary_parse_error(check, ValueError("bad json"))

        assert check["ok"] is False
        assert check["returncode"] == expected_returncode
        assert "bad json" in check["summary_parse_error"]


def test_smoke_pins_every_live_python_helper():
    smoke = load_smoke_module()

    assert set(smoke.TRUSTED_HELPER_DIGESTS) == {"status", "runtime", "finalization_readiness", "gate"}


def test_smoke_executes_authenticated_bytes_after_helper_path_replacement(tmp_path, monkeypatch):
    smoke = load_smoke_module()
    helper = tmp_path / "helper.py"
    helper.write_text("import json\nprint(json.dumps({'source':'reviewed'}))\n")
    digest = hashlib.sha256(helper.read_bytes()).hexdigest()
    witness = tmp_path / "attacker-ran"
    smoke.TRUSTED_HELPER_DIGESTS["status"] = digest
    smoke.TRUSTED_HELPER_PATHS["status"] = helper
    real_run = smoke.run
    swapped = []

    def replace_then_run(cmd, cwd=smoke.ROOT, timeout=120, stdin_bytes=None):
        if stdin_bytes is not None and not swapped:
            swapped.append(True)
            helper.write_text(
                "import json\n"
                f"open({str(witness)!r}, 'w').write('ran')\n"
                "print(json.dumps({'source':'attacker'}))\n"
            )
        return real_run(cmd, cwd=cwd, timeout=timeout, stdin_bytes=stdin_bytes)

    monkeypatch.setattr(smoke, "run", replace_then_run)

    result = smoke.run_python_helper("status", timeout=30)

    assert swapped
    assert result["ok"] is True
    assert json.loads(result["stdout"])["source"] == "reviewed"
    assert not witness.exists()


def test_run_timeout_returns_structured_failure():
    smoke = load_smoke_module()

    result = smoke.run(["python3", "-c", "import time; time.sleep(2)"], timeout=1)

    assert result["ok"] is False
    assert result["returncode"] == 124
    assert "timed out" in result["stderr"]


def test_default_pytest_timeout_has_runtime_margin():
    smoke = load_smoke_module()

    assert smoke.DEFAULT_PYTEST_TIMEOUT >= 600


def test_smoke_py_compile_covers_all_relay_scripts():
    smoke = load_smoke_module()
    scripts_dir = SMOKE.parent
    expected = sorted(scripts_dir.glob("hermes-busdriver-*"))

    assert sorted(smoke.PY_COMPILE_SCRIPTS) == expected


def test_finalization_readiness_summary_includes_guardrails_contract():
    smoke = load_smoke_module()

    summary = smoke.summarize_finalization_readiness({
        "readiness": {
            "status": "blocked",
            "ready": False,
            "commit_allowed": False,
            "merge_allowed": False,
        },
        "handoff_envelope": {"schema": "hermes-busdriver-handoff/v0"},
        "finalization_guardrails": {
            "schema": "hermes-busdriver-finalization-guardrails/v0",
            "read_only": True,
        },
        "dual_review_readiness": {
            "schema": "hermes-busdriver-dual-review-readiness/v0",
            "programmatic_execution_allowed": False,
        },
        "finalization_contract_status": {
            "schema": "hermes-busdriver-finalization-contract-status/v0",
            "read_only": True,
            "current_policy": "gated_delivery_mode_executor",
            "summary": {"capability_allowed_count": 0},
            "authority": {
                "finalization_allowed": False,
                "marker_write_allowed": False,
                "programmatic_execution_allowed": False,
            },
        },
    })

    assert summary["handoff_schema"] == "hermes-busdriver-handoff/v0"
    assert summary["finalization_guardrails"]["schema"] == "hermes-busdriver-finalization-guardrails/v0"
    assert summary["finalization_guardrails"]["read_only"] is True
    assert summary["dual_review_readiness"]["schema"] == "hermes-busdriver-dual-review-readiness/v0"
    assert summary["dual_review_readiness"]["programmatic_execution_allowed"] is False
    assert summary["finalization_contract_status"]["schema"] == "hermes-busdriver-finalization-contract-status/v0"
    assert summary["finalization_contract_status"]["read_only"] is True
    assert summary["finalization_contract_status"]["current_policy"] == "gated_delivery_mode_executor"
    assert summary["finalization_contract_status"]["summary"] == {"capability_allowed_count": 0}
    assert summary["finalization_contract_status"]["authority"]["finalization_allowed"] is False
    assert summary["finalization_contract_status"]["authority"]["marker_write_allowed"] is False
    assert summary["finalization_contract_status"]["authority"]["programmatic_execution_allowed"] is False

    missing_authority_summary = smoke.summarize_finalization_readiness({"finalization_contract_status": {}})
    assert missing_authority_summary["finalization_contract_status"]["authority"] == {
        "finalization_allowed": False,
        "marker_write_allowed": False,
        "programmatic_execution_allowed": False,
    }


def test_smoke_status_child_argv_disables_the_external_resolver(monkeypatch, tmp_path):
    # r20 defense in depth: smoke has no need for resolver bytes, so it must not ask for them.
    import sys

    smoke = load_smoke_module()
    calls = []

    def fake_run(cmd, cwd=None, timeout=None, stdin_bytes=None):
        calls.append((list(cmd), stdin_bytes))
        return {"ok": False, "returncode": 1, "stdout": "", "stderr": "", "cmd": list(cmd)}

    monkeypatch.setattr(smoke, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["hermes-busdriver-smoke", "--plugin-root", str(tmp_path)])
    smoke.main()

    status_calls = [
        (cmd, source) for cmd, source in calls
        if (
            len(cmd) > 5
            and cmd[3] == "-c"
            and cmd[4] == smoke.TRUSTED_HELPER_STDIN_LOADER
            and cmd[5] == str(smoke.STATUS)
        )
    ]
    assert status_calls, "smoke never invoked the status probe"
    cmd, source = status_calls[0]
    assert cmd[:4] == ["/usr/bin/python3", "-B", "-I", "-c"]
    assert cmd[5:] == [str(smoke.STATUS), "--plugin-root", str(tmp_path), "--no-external-resolver"]
    assert source == smoke.STATUS.read_bytes()


# --- v16-r21: ambient execution containment ---

import os
import subprocess
import sys


def test_smoke_child_env_is_allowlisted_and_drops_loader_injection(monkeypatch):
    smoke = load_smoke_module()
    for key, value in {
        "PYTHONPATH": "/tmp/evil-pythonpath",
        "PYTHONHOME": "/tmp/evil-pythonhome",
        "BASH_ENV": "/tmp/evil-bash-env",
        "ENV": "/tmp/evil-env",
        "ZDOTDIR": "/tmp/evil-zdotdir",
        "LD_PRELOAD": "/tmp/evil.so",
        "DYLD_INSERT_LIBRARIES": "/tmp/evil.dylib",
        "GIT_DIR": "/tmp/evil-git-dir",
    }.items():
        monkeypatch.setenv(key, value)

    env = smoke.child_env()

    assert env["PATH"] == smoke.CONTAINED_PATH
    for key in ("PYTHONPATH", "PYTHONHOME", "BASH_ENV", "ENV", "ZDOTDIR", "LD_PRELOAD", "DYLD_INSERT_LIBRARIES"):
        assert key not in env
    assert not [key for key in env if key.startswith("GIT_")]


def test_smoke_pytest_cmd_never_comes_from_the_caller_path(monkeypatch, tmp_path):
    smoke = load_smoke_module()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name in ("pytest", "uvx"):
        binary = fake_bin / name
        binary.write_text("#!/bin/sh\nexit 0\n")
        binary.chmod(0o700)
    monkeypatch.setenv("PATH", str(fake_bin))

    cmd = smoke.pytest_cmd()

    assert cmd is None or cmd == [
        "/usr/bin/python3", "-B", "-I", "-m", "pytest", "-p", "no:cacheprovider",
    ]
    if cmd is not None:
        assert str(fake_bin) not in " ".join(cmd)


def test_smoke_fails_closed_when_pytest_is_unavailable(monkeypatch):
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "pytest_cmd", lambda: None)
    monkeypatch.setattr(sys, "argv", ["hermes-busdriver-smoke"])
    monkeypatch.setattr(smoke, "run", lambda *a, **k: {"cmd": list(a[0]), "returncode": 0, "ok": True, "stdout": "", "stderr": ""})

    import io
    import contextlib

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = smoke.main()

    payload = json.loads(buffer.getvalue())
    assert code == 1
    assert payload["ok"] is False
    pytest_checks = [c for c in payload["checks"] if c.get("error") == "pytest_unavailable"]
    assert pytest_checks, payload["checks"]
    assert pytest_checks[0]["returncode"] == 127


def test_smoke_python_children_run_isolated(monkeypatch, tmp_path):
    smoke = load_smoke_module()
    captured: list[list[str]] = []

    def fake_run(cmd, cwd=None, timeout=120):
        captured.append(list(cmd))
        return {"cmd": list(cmd), "returncode": 0, "ok": True, "stdout": "{}", "stderr": ""}

    monkeypatch.setattr(smoke, "run", fake_run)
    monkeypatch.setattr(
        smoke,
        "pytest_cmd",
        lambda: [sys.executable, "-B", "-I", "-m", "pytest", "-p", "no:cacheprovider"],
    )
    monkeypatch.setattr(sys, "argv", ["hermes-busdriver-smoke"])

    import io
    import contextlib

    with contextlib.redirect_stdout(io.StringIO()):
        smoke.main()

    assert captured
    for cmd in captured:
        if cmd[1:5] == ["-B", "-I", "-m", "pytest"]:
            assert cmd[0] == sys.executable, cmd  # pytest belongs to the invoking test environment.
            assert cmd[5:7] == ["-p", "no:cacheprovider"], cmd
        else:
            assert cmd[0] == "/usr/bin/python3", cmd
        assert cmd[1:3] == ["-B", "-I"], cmd


def test_smoke_python_child_py_compile_does_not_create_bytecode_cache(tmp_path):
    smoke = load_smoke_module()
    probe = tmp_path / "probe.py"
    probe.write_text("VALUE = 1\n")

    cp = subprocess.run(
        smoke.python_syntax_check(probe),
        env=smoke.child_env(), capture_output=True, text=True, check=False,
    )

    assert cp.returncode == 0, cp.stderr
    assert not (tmp_path / "__pycache__").exists()
