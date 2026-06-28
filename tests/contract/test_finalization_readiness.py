import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
READINESS = ROOT / "scripts" / "hermes-busdriver-finalization-readiness"
LOCK = ROOT / "scripts" / "hermes-busdriver-lock"


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=False, timeout=timeout)


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


def relay_config(path: Path, route: object) -> Path:
    path.write_text(json.dumps({
        "coding_agent": "opencode",
        "avoid_coding_agent_for_review": True,
        "routes": {"relay.pr.backstop": route},
    }))
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
    try:
        data = json.loads(cp.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"readiness output was not JSON (returncode={cp.returncode})\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}") from e
    return cp, data


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


def test_readiness_handoff_includes_optional_relay_role_resolution(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    cfg = relay_config(tmp_path / "relay-config.json", ["opencode", "codex"])
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(
        repo,
        plugin,
        user_config,
        "--relay-role",
        "relay.pr.backstop",
        "--relay-config",
        str(cfg),
    )

    assert cp.returncode == 0, cp.stderr
    role = data["delivery_status"]["relay_role_resolution"]
    assert role["ok"] is True
    assert role["result"]["selected"]["selected_agent"] == "codex"
    assert role["result"]["dispatch_allowed"] is True
    handoff_role = data["handoff_envelope"]["evidence"]["relay_role_resolution"]
    assert handoff_role["ok"] is True
    assert handoff_role["result"]["mutation_allowed"] is False
    assert handoff_role["result"]["finalization_allowed"] is False
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


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


def test_non_clean_pr_fixture_reports_delivery_blocker(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    pr_result = tmp_path / "pr-wait.json"
    pr_result.write_text(json.dumps({"status": "wait", "clean": False, "checks": {"failed": 0, "pending": 1}, "actionable_comments": []}))

    cp, data = invoke(repo, plugin, user_config, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert "pr_checks_or_reviewer_bots_pending" in data["readiness"]["blockers"]
    assert_no_finalization_authority(data["readiness"])


def test_pr_supplied_without_blockers_gets_pr_not_clean_next_action():
    mod = __import__("runpy").run_path(str(READINESS))
    args = __import__("types").SimpleNamespace(pr="7", target="auto")
    delivery = {
        "ok": True,
        "decision": {"status": "no_local_delivery_candidate", "blockers": [], "warnings": []},
        "repo": {"dirty": False},
    }
    phase0 = {
        "status_schema": "hermes-busdriver-status/v0",
        "plugin_root": {"exists": True},
        "hooks": {"exists": True},
        "repo": {"is_git_repo": True},
        "relay_locks": {"active_for_repo_count": 0},
        "user_config": {"exists": True},
        "resolve_cli": {"ok": True},
        "minimum_gate_scripts": {},
    }

    data = mod["readiness"](args, delivery, phase0)

    assert data["ready"] is False
    assert data["status"] == "pr_not_clean_read_only"
    assert "pr-grind is not clean" in data["next_action"]
    assert_no_finalization_authority(data)


def test_explicit_delivery_target_does_not_emit_commit_handoff_for_dirty_repo(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--target", "delivery")

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["target"] == "delivery"
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "no_finalization_candidate"
    assert_no_finalization_authority(data["readiness"])


def test_phase0_nonzero_json_blocks_readiness():
    mod = __import__("runpy").run_path(str(READINESS))
    phase0 = {
        "status_schema": "hermes-busdriver-status/v0",
        "ok": False,
        "returncode": 2,
        "plugin_root": {"exists": True},
        "hooks": {"exists": True},
        "repo": {"is_git_repo": True},
        "relay_locks": {"active_for_repo_count": 0},
    }

    blockers = mod["phase0_blockers"](phase0)

    assert "phase0_status_failed" in blockers


def test_child_nonzero_json_is_forced_to_not_ok(tmp_path: Path):
    child = tmp_path / "child.py"
    child.write_text("import json, sys\nprint(json.dumps({'ok': True}))\nsys.exit(2)\n")

    data, returncode = __import__("runpy").run_path(str(READINESS))["run_json"]([sys.executable, str(child)], 10)

    assert returncode == 2
    assert data["ok"] is False


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


def test_active_finalization_lock_blocks_handoff_readiness(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    relay_state = tmp_path / "relay-state"
    assert run([sys.executable, str(LOCK), "acquire", "--repo", str(repo), "--state-dir", str(relay_state), "--operation", "finalization"]).returncode == 0
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--relay-state-dir", str(relay_state))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert "relay_finalization_lock_active" in data["readiness"]["blockers"]
    assert data["delivery_status"]["finalization_lock"]["active_for_repo_count"] == 1
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])
