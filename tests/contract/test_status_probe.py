import json
import os
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
    data = run_status("--plugin-root", str(fake), "--user-config", str(user_config), "--relay-config", str(tmp_path / "missing-relay-config.json"))
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
    assert data["relay_config"]["exists"] is False
    assert data["relay_config"]["route_keys"] == []
    relay = data["relay_equivalent_roles"]
    assert relay["coding_agent"] == "pi"
    assert relay["role_policy"] == "pi_default_relay_equivalents"
    assert relay["review_independence_policy"] == "same_pi_adapter_allowed_by_current_user_directive"
    assert relay["avoid_coding_agent_for_review"] is False
    assert set(relay["roles"]) == {
        "relay.litmus.reviewer",
        "relay.blueprint.reviewer_1",
        "relay.blueprint.reviewer_2",
        "relay.blueprint.reviewer_3",
        "relay.blueprint.arbiter",
        "relay.pr.lead",
        "relay.pr.backstop",
        "relay.council.architect",
        "relay.council.pragmatist",
        "relay.council.critic",
        "relay.council.researcher",
        "relay.council.skeptic",
    }
    arbiter = relay["roles"]["relay.blueprint.arbiter"]
    assert arbiter["native_busdriver_role"] == "blueprint arbiter"
    for entry in relay["roles"].values():
        assert entry["configured_route"] == ["pi"]
        assert entry["default_route"] == ["pi"]
        assert entry["source"] == "default"
        assert entry["selected_agent"] == "pi"
        assert entry["same_as_coding_agent"] is True
        assert entry["degraded"] is False
        assert entry["configurable"] is True
        assert entry["not_busdriver_native_claude_runtime"] is True
        assert entry["finalization_allowed"] is False
        assert entry["mutation_allowed"] is False


def test_status_probe_relay_equivalents_avoid_configured_coding_agent(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    user_config = tmp_path / "busdriver.json"
    relay_config = tmp_path / "relay-config.json"
    role_names = [
        "relay.litmus.reviewer",
        "relay.blueprint.reviewer_1",
        "relay.blueprint.reviewer_2",
        "relay.blueprint.reviewer_3",
        "relay.blueprint.arbiter",
        "relay.pr.lead",
        "relay.pr.backstop",
        "relay.council.architect",
        "relay.council.pragmatist",
        "relay.council.critic",
        "relay.council.researcher",
        "relay.council.skeptic",
    ]
    user_config.write_text(json.dumps({"version": "1", "routes": {"council.pragmatist": ["agy", "droid"]}}))
    relay_config.write_text(json.dumps({
            "coding_agent": "opencode",
            "avoid_coding_agent_for_review": True,
            "routes": {role: ["opencode", "codex"] for role in role_names},
    }))

    data = run_status("--plugin-root", str(fake), "--user-config", str(user_config), "--relay-config", str(relay_config))

    assert data["user_config"]["route_keys"] == ["council.pragmatist"]
    assert data["relay_config"]["path"] == str(relay_config)
    assert data["relay_config"]["route_keys"] == sorted(role_names)
    assert set(data["effective_routes"]) == {
        "litmus.reviewer",
        "blueprint-review.reviewer_1",
        "blueprint-review.reviewer_2",
        "blueprint-review.reviewer_3",
        "council.pragmatist",
        "council.critic",
        "council.researcher",
    }
    relay = data["relay_equivalent_roles"]
    assert relay["coding_agent"] == "opencode"
    assert relay["coding_agent_source"] == "relay_config"
    for role in role_names:
        entry = relay["roles"][role]
        assert entry["configured_route"] == ["opencode", "codex"]
        assert entry["source"] == "relay_config"
        assert entry["selected_agent"] == "codex"
        assert entry["same_as_coding_agent"] is False
        assert entry["degraded"] is False
        assert entry["config_error"] is None
        assert entry["finalization_allowed"] is False
        assert entry["mutation_allowed"] is False


def test_status_probe_marks_pi_default_relay_equivalents_degraded_when_independence_is_explicitly_requested(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text(json.dumps({
        "coding_agent": "pi",
        "avoid_coding_agent_for_review": True,
    }))

    data = run_status("--plugin-root", str(fake), "--relay-config", str(relay_config))

    relay = data["relay_equivalent_roles"]
    assert relay["role_policy"] == "pi_default_relay_equivalents"
    assert relay["review_independence_policy"] == "same_pi_adapter_allowed_by_current_user_directive"
    assert relay["avoid_coding_agent_for_review"] is True
    for entry in relay["roles"].values():
        assert entry["configured_route"] == ["pi"]
        assert entry["selected_agent"] == "pi"
        assert entry["same_as_coding_agent"] is True
        assert entry["degraded"] is True
        assert entry["config_error"] is None
        assert entry["finalization_allowed"] is False
        assert entry["mutation_allowed"] is False


def test_status_probe_marks_empty_relay_equivalent_route_degraded(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text(json.dumps({
        "coding_agent": "codex",
        "routes": {"relay.pr.backstop": []},
    }))

    data = run_status("--plugin-root", str(fake), "--relay-config", str(relay_config))

    backstop = data["relay_equivalent_roles"]["roles"]["relay.pr.backstop"]
    assert backstop["configured_route"] == []
    assert backstop["selected_agent"] is None
    assert backstop["degraded"] is True
    assert backstop["config_error"] == "empty_route"
    assert backstop["finalization_allowed"] is False
    assert backstop["mutation_allowed"] is False


def test_status_probe_marks_invalid_relay_equivalent_route_entries_degraded(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text(json.dumps({
        "coding_agent": {"bad": "type"},
        "avoid_coding_agent_for_review": "false",
        "routes": {"relay.pr.backstop": [None, "", "codex"]},
    }))

    data = run_status("--plugin-root", str(fake), "--relay-config", str(relay_config))

    relay = data["relay_equivalent_roles"]
    assert relay["coding_agent"] == "pi"
    assert relay["avoid_coding_agent_for_review"] is False
    assert relay["coding_agent_config_error"] == "coding_agent_must_be_non_empty_string"
    assert relay["avoid_coding_agent_for_review_config_error"] == "avoid_coding_agent_for_review_must_be_boolean"
    assert relay["coding_agent_source"] == "default"
    assert relay["avoid_coding_agent_for_review_source"] == "default"
    backstop = relay["roles"]["relay.pr.backstop"]
    assert backstop["configured_route"] == []
    assert backstop["selected_agent"] is None
    assert backstop["degraded"] is True
    assert backstop["config_error"] == "route_entries_must_be_non_empty_strings"
    assert backstop["finalization_allowed"] is False
    assert backstop["mutation_allowed"] is False


def test_status_probe_marks_invalid_relay_equivalent_route_type_degraded(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text(json.dumps({
        "coding_agent": "codex",
        "routes": {"relay.pr.backstop": {"bad": "type"}},
    }))

    data = run_status("--plugin-root", str(fake), "--relay-config", str(relay_config))

    backstop = data["relay_equivalent_roles"]["roles"]["relay.pr.backstop"]
    assert backstop["configured_route"] == []
    assert backstop["selected_agent"] is None
    assert backstop["degraded"] is True
    assert backstop["config_error"] == "route_must_be_string_or_array"
    assert backstop["finalization_allowed"] is False
    assert backstop["mutation_allowed"] is False


def test_status_probe_marks_invalid_relay_routes_container_degraded(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text(json.dumps({
        "coding_agent": "codex",
        "routes": [],
    }))

    data = run_status("--plugin-root", str(fake), "--relay-config", str(relay_config))

    relay = data["relay_equivalent_roles"]
    assert relay["routes_config_error"] == "routes_must_be_object"
    for entry in relay["roles"].values():
        assert entry["configured_route"] == []
        assert entry["selected_agent"] is None
        assert entry["degraded"] is True
        assert entry["config_error"] == "routes_must_be_object"
        assert entry["finalization_allowed"] is False
        assert entry["mutation_allowed"] is False


def test_status_probe_marks_malformed_relay_config_degraded(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text("{not json")

    data = run_status("--plugin-root", str(fake), "--relay-config", str(relay_config))

    relay = data["relay_equivalent_roles"]
    assert data["relay_config"]["parse_error"]
    assert relay["relay_config_parse_error"]
    assert relay["routes_config_error"] == "config_parse_error"
    for entry in relay["roles"].values():
        assert entry["configured_route"] == []
        assert entry["selected_agent"] is None
        assert entry["degraded"] is True
        assert entry["config_error"] == "config_parse_error"
        assert entry["finalization_allowed"] is False
        assert entry["mutation_allowed"] is False


def test_status_probe_marks_invalid_relay_config_shape_degraded(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text(json.dumps([]))

    data = run_status("--plugin-root", str(fake), "--relay-config", str(relay_config))

    relay = data["relay_equivalent_roles"]
    assert data["relay_config"]["shape_error"] == "config_must_be_object"
    assert relay["relay_config_shape_error"] == "config_must_be_object"
    assert relay["routes_config_error"] == "config_must_be_object"
    for entry in relay["roles"].values():
        assert entry["configured_route"] == []
        assert entry["selected_agent"] is None
        assert entry["degraded"] is True
        assert entry["config_error"] == "config_must_be_object"
        assert entry["finalization_allowed"] is False
        assert entry["mutation_allowed"] is False


def test_status_probe_relay_config_unexpected_values_do_not_raise(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    cases = [
        {"coding_agent": 1, "avoid_coding_agent_for_review": "false", "routes": []},
        {"coding_agent": "", "avoid_coding_agent_for_review": None, "routes": {"relay.pr.backstop": [None]}},
        {"routes": {"relay.pr.backstop": {"bad": "type"}}},
    ]
    for index, payload in enumerate(cases):
        relay_config = tmp_path / f"relay-config-{index}.json"
        relay_config.write_text(json.dumps(payload))
        data = run_status("--plugin-root", str(fake), "--relay-config", str(relay_config))
        assert data["relay_equivalent_roles"]["roles"]
        assert any(entry["degraded"] for entry in data["relay_equivalent_roles"]["roles"].values())


def test_status_probe_reports_active_markers_without_writing(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, text=True, capture_output=True)
    (repo / "README.md").write_text("fixture\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, text=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )
    head_time = int(
        subprocess.run(
            ["git", "show", "-s", "--format=%ct", "HEAD"],
            cwd=repo,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    )
    state = repo / ".claude"
    state.mkdir()
    (state / "litmus-passed.local").write_text("PASS-test\n")
    (state / "design-review-needed.local.md").write_text("PLAN.md\n")
    os.utime(state / "litmus-passed.local", (head_time, head_time))
    os.utime(state / "design-review-needed.local.md", (head_time + 1, head_time + 1))
    before = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*"))
    data = run_status("--plugin-root", str(fake), "--repo", str(repo))
    after = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*"))
    assert before == after
    markers = data["active_markers"]
    repo_status = data["repo"]
    assert markers["active_count"] == 2
    litmus_marker = markers["files"]["litmus-passed.local"]
    design_marker = markers["files"]["design-review-needed.local.md"]
    assert litmus_marker["exists"] is True
    assert markers["files"]["design-review-needed.local.md"]["preview_lines"] == ["PLAN.md"]
    assert "freshness" in litmus_marker
    assert "freshness" in design_marker
    freshness = litmus_marker["freshness"]
    assert freshness["compared_to_repo_head"] == repo_status["head"]
    assert freshness["repo_branch"] == repo_status["branch"]
    assert freshness["repo_dirty"] == repo_status["dirty"]
    assert freshness["marker_mtime"] == litmus_marker["mtime"]
    assert freshness["marker_age_sec"] == litmus_marker["age_sec"]
    assert freshness["repo_head_commit_time"] == repo_status["head_commit_time"]
    assert freshness["marker_mtime_after_repo_head_commit_time"] is False
    assert design_marker["freshness"]["marker_mtime_after_repo_head_commit_time"] is True


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


def test_status_probe_accepts_supported_drift_baseline_schemas(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    current = run_status("--plugin-root", str(fake))

    for key, value in [
        ("status_schema", "hermes-busdriver-status/v0"),
        ("schema", "hermes-busdriver-drift/v0"),
    ]:
        baseline = tmp_path / f"{key}.json"
        baseline.write_text(
            json.dumps(
                {
                    key: value,
                    "package": {"version": current["package"]["version"]},
                    "critical_file_hashes": current["critical_file_hashes"],
                }
            )
        )

        data = run_status("--plugin-root", str(fake), "--drift-baseline", str(baseline))

        assert data["busdriver_drift"]["status"] == "compatible"
        assert data["busdriver_drift"]["finalization_compatible"] is True
        assert_no_finalization_flags(data["busdriver_drift"])


def test_status_probe_rejects_unsupported_drift_baseline_schema(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    current = run_status("--plugin-root", str(fake))
    for key, value in [
        ("status_schema", "hermes-busdriver-status/v999"),
        ("schema", "hermes-busdriver-drift/v999"),
    ]:
        baseline = tmp_path / f"bad-{key}.json"
        baseline.write_text(
            json.dumps(
                {
                    key: value,
                    "package": {"version": current["package"]["version"]},
                    "critical_file_hashes": current["critical_file_hashes"],
                }
            )
        )

        data = run_status("--plugin-root", str(fake), "--drift-baseline", str(baseline))

        assert data["busdriver_drift"]["status"] == "baseline_invalid"
        assert data["busdriver_drift"]["finalization_compatible"] is False
        assert_no_finalization_flags(data["busdriver_drift"])
        assert "baseline_invalid" in data["busdriver_drift"]["finalization_disabled_reasons"]
        assert data["busdriver_drift"]["parse_error"] == f"unsupported {key}: {value}"


def test_status_probe_reports_missing_drift_baseline_as_unknown(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    data = run_status("--plugin-root", str(fake), "--drift-baseline", str(tmp_path / "missing.json"))

    assert data["busdriver_drift"]["status"] == "baseline_missing"
    assert data["busdriver_drift"]["finalization_compatible"] is False
    assert_no_finalization_flags(data["busdriver_drift"])
    assert "baseline_missing" in data["busdriver_drift"]["finalization_disabled_reasons"]
