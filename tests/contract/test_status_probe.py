import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "hermes-busdriver-status"


def make_fake_busdriver(root: Path) -> None:
    (root / "hooks" / "gate-scripts").mkdir(parents=True)
    (root / "scripts" / "hooks").mkdir(parents=True)
    (root / "scripts" / "lib").mkdir(parents=True)
    (root / "scripts" / "codex").mkdir(parents=True)
    (root / "skills" / "orchestrator" / "references").mkdir(parents=True)
    (root / "skills" / "supplements").mkdir(parents=True)
    (root / "package.json").write_text(json.dumps({"name": "busdriver", "version": "0.test"}))
    hooks = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/gate-scripts/pre-commit-gate.sh"',
                        }
                    ],
                    "description": "gate",
                }
            ]
        }
    }
    (root / "hooks" / "hooks.json").write_text(json.dumps(hooks))
    for rel in [
        "hooks/gate-scripts/careful-guard.sh",
        "hooks/gate-scripts/pre-commit-gate.sh",
        "hooks/gate-scripts/pre-pr-gate.sh",
        "hooks/gate-scripts/pre-merge-gate.sh",
        "hooks/gate-scripts/pre-implementation-gate.sh",
        "hooks/gate-scripts/freeze-guard.sh",
        "hooks/gate-scripts/check-design-document.sh",
        "hooks/gate-scripts/load-orchestrator.sh",
        "scripts/hooks/block-no-verify.js",
        "scripts/codex/codex-goal-dispatch.sh",
        "scripts/codex/goal-result.schema.json",
        "scripts/lib/ultra-oracle.sh",
        "scripts/lib/ultra-oracle-config.sh",
        "scripts/doctor.js",
        "skills/orchestrator/SKILL.md",
        "skills/orchestrator/tasks-catalog.md",
        "skills/orchestrator/domain-supplements.md",
        "skills/orchestrator/references/hooks-reference.md",
        "skills/orchestrator/references/gate-recovery.md",
        "skills/supplements/MANIFEST.md",
    ]:
        (root / rel).write_text("# fixture\n")
    resolver = root / "scripts" / "lib" / "resolve-cli.sh"
    resolver.write_text(
        """#!/usr/bin/env bash
printf '{"configured":"auto","resolved":"codex","version":"test","clis":{"codex":{"available":true,"version":"test"},"agy":{"available":false,"version":"n/a"},"droid":{"available":true,"version":"test"},"grok":{"available":true,"version":"test"}}}\\n'
"""
    )
    resolver.chmod(0o755)


def run_status(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--pretty"],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def assert_no_finalization_flags(drift: dict) -> None:
    assert drift["finalization_flags"] == {
        "commit_allowed": False,
        "push_allowed": False,
        "pr_allowed": False,
        "merge_allowed": False,
        "deploy_allowed": False,
        "marker_write_allowed": False,
    }


def test_status_probe_is_read_only_and_reports_hooks(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    user_config = tmp_path / "busdriver.json"
    user_config.write_text(json.dumps({"version": "1", "routes": {"council.pragmatist": ["agy", "droid"]}}))
    before = sorted(p.relative_to(fake).as_posix() for p in fake.rglob("*"))
    data = run_status("--plugin-root", str(fake), "--user-config", str(user_config))
    after = sorted(p.relative_to(fake).as_posix() for p in fake.rglob("*"))
    assert before == after
    assert data["read_only"] is True
    assert data["plugin_root"]["exists"] is True
    assert data["hooks"]["events"]["PreToolUse"]["entries"] == 1
    assert data["minimum_gate_scripts"]["hooks/gate-scripts/pre-commit-gate.sh"] is True
    assert data["resolve_cli"]["ok"] is True
    assert data["critical_file_hashes"]["hooks/hooks.json"]["sha256"]
    assert data["effective_routes"]["council.pragmatist"]["resolved"] == "droid"
    assert data["effective_routes"]["blueprint-review.reviewer_3"]["resolved"] == "grok"


def test_status_probe_reports_active_markers_without_writing(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, text=True, capture_output=True)
    state = repo / ".claude"
    state.mkdir()
    (state / "litmus-passed.local").write_text("PASS-test\n")
    (state / "design-review-needed.local.md").write_text("PLAN.md\n")
    before = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*"))
    data = run_status("--plugin-root", str(fake), "--repo", str(repo))
    after = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*"))
    assert before == after
    markers = data["active_markers"]
    assert markers["active_count"] == 2
    assert markers["files"]["litmus-passed.local"]["exists"] is True
    assert markers["files"]["design-review-needed.local.md"]["preview_lines"] == ["PLAN.md"]


def test_status_probe_compares_drift_baseline_without_writing(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    baseline = tmp_path / "baseline.json"
    current = run_status("--plugin-root", str(fake))
    baseline.write_text(
        json.dumps(
            {
                "package": {"version": current["package"]["version"]},
                "critical_file_hashes": current["critical_file_hashes"],
            }
        )
    )
    before = baseline.read_text()

    compatible = run_status("--plugin-root", str(fake), "--drift-baseline", str(baseline))

    assert baseline.read_text() == before
    assert compatible["busdriver_drift"]["status"] == "compatible"
    assert compatible["busdriver_drift"]["finalization_compatible"] is True
    assert_no_finalization_flags(compatible["busdriver_drift"])
    assert compatible["busdriver_drift"]["changed"] == []

    (fake / "hooks" / "gate-scripts" / "pre-commit-gate.sh").write_text("# changed\n")
    drifted = run_status("--plugin-root", str(fake), "--drift-baseline", str(baseline))

    assert drifted["busdriver_drift"]["status"] == "drifted"
    assert drifted["busdriver_drift"]["finalization_compatible"] is False
    assert_no_finalization_flags(drifted["busdriver_drift"])
    assert "hooks/gate-scripts/pre-commit-gate.sh" in drifted["busdriver_drift"]["changed"]
    assert "baseline_drift" in drifted["busdriver_drift"]["finalization_disabled_reasons"]


def test_status_probe_reports_missing_drift_baseline_as_unknown(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    data = run_status("--plugin-root", str(fake), "--drift-baseline", str(tmp_path / "missing.json"))

    assert data["busdriver_drift"]["status"] == "baseline_missing"
    assert data["busdriver_drift"]["finalization_compatible"] is False
    assert_no_finalization_flags(data["busdriver_drift"])
    assert "baseline_missing" in data["busdriver_drift"]["finalization_disabled_reasons"]
