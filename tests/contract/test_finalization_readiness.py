import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
READINESS = ROOT / "scripts" / "hermes-busdriver-finalization-readiness"


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=False)


def init_repo(path: Path) -> Path:
    path.mkdir()
    assert run(["git", "init"], path).returncode == 0
    return path


def fake_busdriver(path: Path, *, hooks: bool = True) -> Path:
    files = {
        "package.json": '{"name":"busdriver","version":"1.71.0"}\n',
        "scripts/relevant-check-status.sh": "#!/bin/sh\ncat >/dev/null\nprintf '0 0 all 1\\n'\n",
        "scripts/ack-ledger.sh": "#!/bin/sh\nprintf 'none\\n'\n",
        "scripts/fetch-pr-state.sh": "#!/bin/sh\ntrue\n",
        "scripts/lib/resolve-cli.sh": '#!/bin/sh\nprintf %s \'{"clis":{"codex":{"available":true},"droid":{"available":false},"agy":{"available":false},"grok":{"available":false}}}\'\n',
        "hooks/gate-scripts/careful-guard.sh": "#!/bin/sh\ntrue\n",
        "hooks/gate-scripts/pre-commit-gate.sh": "#!/bin/sh\ntrue\n",
        "hooks/gate-scripts/pre-pr-gate.sh": "#!/bin/sh\ntrue\n",
        "hooks/gate-scripts/pre-merge-gate.sh": "#!/bin/sh\ntrue\n",
        "hooks/gate-scripts/pre-implementation-gate.sh": "#!/bin/sh\ntrue\n",
        "hooks/gate-scripts/freeze-guard.sh": "#!/bin/sh\ntrue\n",
        "hooks/gate-scripts/check-design-document.sh": "#!/bin/sh\ntrue\n",
        "hooks/gate-scripts/load-orchestrator.sh": "#!/bin/sh\ntrue\n",
        "scripts/hooks/block-no-verify.js": "#!/usr/bin/env node\nprocess.exit(0)\n",
        "skills/pr-grind/SKILL.md": "# pr-grind\n",
        "agents/pr-grinder.md": "# pr-grinder\n",
        "opencode/skills/pr-grind/SKILL.md": "# pr-grind\n",
        "opencode/agents/pr-grinder.md": "# pr-grinder\n",
    }
    if hooks:
        files["hooks/hooks.json"] = json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "Bash", "description": "pre commit", "hooks": [{"type": "command", "command": "hooks/gate-scripts/pre-commit-gate.sh"}]}
                    ],
                    "PostToolUse": [],
                }
            }
        )
    for rel, content in files.items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        if rel.startswith(("scripts/", "hooks/")):
            target.chmod(0o755)
    return path


def fake_user_config(path: Path) -> Path:
    path.write_text(json.dumps({"routes": {"litmus.reviewer": ["codex"]}}))
    return path


def invoke(repo: Path, plugin: Path, user_config: Path, *extra: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    cp = run(
        [
            sys.executable,
            str(READINESS),
            "--repo",
            str(repo),
            "--plugin-root",
            str(plugin),
            "--user-config",
            str(user_config),
            *extra,
        ]
    )
    return cp, json.loads(cp.stdout)


def assert_no_finalization_authority(authority: dict) -> None:
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
        assert authority[key] is False


def test_dirty_tree_generates_read_only_commit_or_pr_handoff_without_side_effects(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    (repo / "work.txt").write_text("draft\n")
    before = run(["git", "status", "--porcelain=v1"], repo).stdout

    cp, data = invoke(repo, plugin, user_config)
    after = run(["git", "status", "--porcelain=v1"], repo).stdout

    assert cp.returncode == 0, cp.stderr
    assert before == after
    assert data["schema"] == "hermes-busdriver-finalization-readiness/v0"
    assert data["read_only"] is True
    assert data["ok"] is True
    assert data["readiness"]["status"] == "ready_for_commit_or_pr_handoff"
    assert data["readiness"]["ready"] is True
    assert_no_finalization_authority(data["readiness"])
    handoff = data["handoff_envelope"]
    assert handoff["schema"] == "hermes-busdriver-handoff/v0"
    assert handoff["read_only"] is True
    assert handoff["repo"]["dirty"] is True
    assert handoff["busdriver_phase0"]["hooks"]["exists"] is True
    assert "commit" in handoff["forbidden_by_this_helper"]
    assert "busdriver_marker_write" in handoff["forbidden_by_this_helper"]
    assert_no_finalization_authority(handoff["authority"])
    assert not (repo / ".claude").exists()
    assert not (repo / ".opencode").exists()


def test_clean_pr_grind_fixture_generates_merge_handoff_but_no_merge_authority(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    pr_result = tmp_path / "pr-clean.json"
    pr_result.write_text(json.dumps({"status": "clean", "clean": True, "checks": {"failed": 0, "pending": 0}, "actionable_comments": []}))

    cp, data = invoke(repo, plugin, user_config, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["status"] == "ready_for_merge_handoff"
    assert data["readiness"]["target"] == "merge"
    assert data["handoff_envelope"]["ready_for_handoff"] is True
    assert data["handoff_envelope"]["pr"]["number"] == "7"
    assert data["handoff_envelope"]["pr"]["status"] == "clean"
    assert data["decision"] == {
        "status": "ready_for_merge_handoff",
        "reason": "read_only_finalization_readiness",
        **{key: False for key in ["finalization_allowed", "commit_allowed", "push_allowed", "pr_allowed", "merge_allowed", "deploy_allowed", "release_allowed", "publish_allowed"]},
    }
    assert_no_finalization_authority(data["handoff_envelope"]["authority"])
    assert not (repo / ".claude").exists()
    assert not (repo / ".opencode").exists()


def test_missing_phase0_hooks_block_handoff_even_when_worktree_dirty(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver", hooks=False)
    user_config = fake_user_config(tmp_path / "busdriver.json")
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config)

    assert cp.returncode == 0, cp.stderr
    assert data["ok"] is True
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert "phase0_hooks_unavailable" in data["readiness"]["blockers"]
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])
