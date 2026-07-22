import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SMOKE = Path(__file__).resolve().parents[2] / "scripts" / "hermes-busdriver-agent-smoke"
SMOKE_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "pi" / "agent-smoke-test-harness"


def fake_busdriver(path: Path) -> Path:
    root = path / "busdriver"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [], "PostToolUse": [], "Stop": []}}))
    (root / "package.json").write_text(json.dumps({"version": "test"}))
    return root


def test_production_agent_smoke_rejects_custom_wrapper(tmp_path: Path):
    plugin = fake_busdriver(tmp_path)
    cp = subprocess.run(
        [
            sys.executable,
            str(SMOKE),
            "--plugin-root",
            str(plugin),
            "--agent",
            "custom",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert cp.returncode == 2
    assert cp.stdout == ""
    assert "invalid choice" in cp.stderr
    assert "custom" in cp.stderr


def test_production_agent_smoke_blocks_before_ambient_git(tmp_path: Path):
    ambient_bin = tmp_path / "bin"
    ambient_bin.mkdir()
    sentinel = tmp_path / "ambient-git-ran"
    git = ambient_bin / "git"
    git.write_text(f"#!/bin/sh\nprintf ran > {sentinel}\nexit 99\n")
    git.chmod(0o700)

    cp = subprocess.run(
        [sys.executable, str(SMOKE), "--plugin-root", str(tmp_path / "missing-plugin"), "--agent", "pi"],
        env={**os.environ, "PATH": str(ambient_bin)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode == 2
    assert json.loads(cp.stdout)["reason"] == "agent_containment_and_credential_broker_unavailable"
    assert not sentinel.exists()


def test_production_agent_smoke_requires_explicit_supported_agent(tmp_path: Path):
    cp = subprocess.run(
        [sys.executable, str(SMOKE), "--plugin-root", str(tmp_path / "missing-plugin")],
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode == 2
    assert cp.stdout == ""
    assert "the following arguments are required: --agent" in cp.stderr


def test_agent_smoke_help_renders_fixed_production_policy_blocker():
    cp = subprocess.run(
        [sys.executable, str(SMOKE), "--help"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode == 0
    assert "policy_blocked" in cp.stdout
    assert "agent_containment_and_credential_broker_unavailable" in cp.stdout
    assert "production never dispatches" in cp.stdout.lower()


def test_agent_smoke_fixture_routes_opencode_to_test_launcher(tmp_path: Path):
    plugin = fake_busdriver(tmp_path)
    cp = subprocess.run(
        [
            sys.executable,
            str(SMOKE_FIXTURE),
            "--plugin-root",
            str(plugin),
            "--agent",
            "opencode",
            "--opencode-bin",
            str(tmp_path / "missing-opencode"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode == 2
    data = json.loads(cp.stdout)
    assert data["summary"]["agent"] == "opencode"
    assert data["target"] == "src/opencode_smoke.txt"
    assert data["target_content"] is None


def test_agent_smoke_fixture_keep_repo_preserves_failed_run_for_diagnostics(tmp_path: Path):
    plugin = fake_busdriver(tmp_path)
    cp = subprocess.run(
        [
            sys.executable,
            str(SMOKE_FIXTURE),
            "--plugin-root",
            str(plugin),
            "--agent",
            "opencode",
            "--opencode-bin",
            str(tmp_path / "missing-opencode"),
            "--keep-repo",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert cp.returncode != 0
    data = json.loads(cp.stdout)
    repo = Path(data["repo"])
    try:
        assert data["kept_repo"] is True
        assert repo.is_dir()
        assert (repo / ".git").is_dir()
    finally:
        shutil.rmtree(repo, ignore_errors=True)
