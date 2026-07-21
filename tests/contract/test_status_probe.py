import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from relay_role_constants import (
    FULL_RELAY_ROLE_MAP,
    NON_PROGRAMMATIC_RELAY_ROLES,
    REVIEW_SENSITIVE_RELAY_ROLES,
    UNVERIFIED_ADAPTER_RELAY_ROLES,
)


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


FULL_RELAY_ROLE_MAP = {
    "relay.impl.primary": "pi",
    "relay.impl.secondary": "opencode",
    "relay.impl.fallback": "opencode",
    "relay.review.fast": "grok",
    "relay.review.long_context": "gemini",
    "relay.ide.manual": "zed",
    "relay.expert_witness.ultraoracle": "ultraoracle",
    "relay.litmus.reviewer": "codex",
    "relay.blueprint.reviewer_1": "agy",
    "relay.blueprint.reviewer_2": "claude-code",
    "relay.blueprint.reviewer_3": "grok",
    "relay.blueprint.arbiter": "codex",
    "relay.pr.lead": "codex",
    "relay.pr.backstop": "claude-code",
    "relay.council.architect": "inline",
    "relay.council.pragmatist": "agy",
    "relay.council.critic": "codex",
    "relay.council.researcher": "grok",
    "relay.council.skeptic": "claude-code",
}


REVIEW_SENSITIVE_RELAY_ROLES = {
    role
    for role in FULL_RELAY_ROLE_MAP
    if not role.startswith("relay.impl.") and role != "relay.ide.manual"
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
    # r20: a tmp_path fixture root is not the canonical install, so its resolver is never run.
    # Presence/shape reporting still works; only live CLI availability degrades.
    assert data["resolve_cli"]["ok"] is False
    assert data["resolve_cli"]["error"] == "plugin_root_untrusted"
    assert data["critical_file_hashes"]["hooks/hooks.json"]["sha256"]
    assert data["effective_routes"]["council.pragmatist"]["route"] == ["agy", "droid"]
    assert data["effective_routes"]["council.pragmatist"]["resolved"] is None
    assert data["effective_routes"]["council.pragmatist"]["available"] is False
    assert data["effective_routes"]["blueprint-review.reviewer_3"]["route"] == ["grok", "droid"]
    assert data["relay_config"]["exists"] is False
    assert data["relay_config"]["route_keys"] == []
    relay = data["relay_equivalent_roles"]
    assert relay["coding_agent"] == "pi"
    assert relay["role_policy"] == "pi_primary_opencode_fallback_codex_review"
    assert relay["review_independence_policy"] == "avoid_coding_agent_for_review_roles"
    assert relay["avoid_coding_agent_for_review"] is True
    assert set(relay["roles"]) == set(FULL_RELAY_ROLE_MAP)
    arbiter = relay["roles"]["relay.blueprint.arbiter"]
    assert arbiter["native_busdriver_role"] == "blueprint arbiter"
    for role, entry in relay["roles"].items():
        assert entry["configured_route"] == [FULL_RELAY_ROLE_MAP[role]]
        assert entry["default_route"] == [FULL_RELAY_ROLE_MAP[role]]
        assert entry["source"] == "default"
        assert entry["selected_agent"] == FULL_RELAY_ROLE_MAP[role]
        assert entry["same_as_coding_agent"] is (FULL_RELAY_ROLE_MAP[role] == "pi")
        assert entry["degraded"] is False
        assert entry["review_independence_sensitive"] is (role in REVIEW_SENSITIVE_RELAY_ROLES)
        assert entry["programmatic_dispatch_allowed"] is (role not in NON_PROGRAMMATIC_RELAY_ROLES)
        assert entry["adapter_verified"] is (role not in UNVERIFIED_ADAPTER_RELAY_ROLES)
        if role in UNVERIFIED_ADAPTER_RELAY_ROLES:
            assert entry["dispatch_blocker"] == "agent_containment_and_credential_broker_unavailable"
        assert entry["configurable"] is True
        assert entry["not_busdriver_native_claude_runtime"] is True
        assert entry["finalization_allowed"] is False
        assert entry["mutation_allowed"] is False


def test_default_relay_role_permission_metadata_is_explicit_and_boolean():
    ns = runpy.run_path(str(SCRIPT))

    for role, metadata in ns["DEFAULT_RELAY_EQUIVALENT_ROUTES"].items():
        assert "programmatic_dispatch_allowed" in metadata, role
        assert isinstance(metadata["programmatic_dispatch_allowed"], bool), role
        assert "adapter_verified" in metadata, role
        assert isinstance(metadata["adapter_verified"], bool), role


def test_relay_role_metadata_omission_degrades_instead_of_synthesizing_permission(monkeypatch):
    ns = runpy.run_path(str(SCRIPT))
    role = "relay.pr.lead"

    for missing_key, expected_error in (
        ("programmatic_dispatch_allowed", "default_role_metadata_missing_programmatic_dispatch_allowed"),
        ("adapter_verified", "default_role_metadata_missing_adapter_verified"),
    ):
        defaults = json.loads(json.dumps(ns["DEFAULT_RELAY_EQUIVALENT_ROUTES"]))
        defaults[role].pop(missing_key)
        monkeypatch.setitem(ns["relay_equivalent_roles"].__globals__, "DEFAULT_RELAY_EQUIVALENT_ROUTES", defaults)

        entry = ns["relay_equivalent_roles"]({})["roles"][role]

        assert entry["programmatic_dispatch_allowed"] is False
        assert entry["adapter_verified"] is False
        assert entry["degraded"] is True
        assert entry["config_error"] == expected_error
        assert entry["dispatch_blocker"] == "default_role_metadata_invalid"


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


def test_status_probe_review_independence_does_not_block_implementation_primary(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text(json.dumps({
        "coding_agent": "pi",
        "avoid_coding_agent_for_review": True,
        "routes": {
            "relay.impl.primary": ["pi"],
            "relay.pr.backstop": ["pi"],
        },
    }))

    data = run_status("--plugin-root", str(fake), "--relay-config", str(relay_config))

    relay = data["relay_equivalent_roles"]
    assert relay["role_policy"] == "pi_primary_opencode_fallback_codex_review"
    assert relay["review_independence_policy"] == "avoid_coding_agent_for_review_roles"
    assert relay["avoid_coding_agent_for_review"] is True
    primary = relay["roles"]["relay.impl.primary"]
    assert primary["selected_agent"] == "pi"
    assert primary["same_as_coding_agent"] is True
    assert primary["review_independence_sensitive"] is False
    assert primary["degraded"] is False
    backstop = relay["roles"]["relay.pr.backstop"]
    assert backstop["selected_agent"] == "pi"
    assert backstop["same_as_coding_agent"] is True
    assert backstop["review_independence_sensitive"] is True
    assert backstop["degraded"] is True
    assert backstop["finalization_allowed"] is False
    assert backstop["mutation_allowed"] is False


def test_status_probe_resolves_full_live_relay_role_map_without_degradation(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text(json.dumps({
        "coding_agent": "pi",
        "avoid_coding_agent_for_review": True,
        "routes": {role: [agent] for role, agent in FULL_RELAY_ROLE_MAP.items()},
    }))

    data = run_status("--plugin-root", str(fake), "--relay-config", str(relay_config))

    assert data["relay_config"]["route_keys"] == sorted(FULL_RELAY_ROLE_MAP)
    relay = data["relay_equivalent_roles"]
    assert set(relay["roles"]) == set(FULL_RELAY_ROLE_MAP)
    for role, expected_agent in FULL_RELAY_ROLE_MAP.items():
        entry = relay["roles"][role]
        assert entry["configured_route"] == [expected_agent]
        assert entry["selected_agent"] == expected_agent
        assert entry["source"] == "relay_config"
        assert entry["degraded"] is False
        assert entry["programmatic_dispatch_allowed"] is (role not in NON_PROGRAMMATIC_RELAY_ROLES)
        assert entry["adapter_verified"] is (role not in UNVERIFIED_ADAPTER_RELAY_ROLES)
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
    assert relay["avoid_coding_agent_for_review"] is True
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


def test_status_refuses_to_execute_resolver_bytes_from_an_untrusted_plugin_root(tmp_path):
    # r20: --plugin-root is caller-controlled. Executing whatever resolve-cli.sh happens to sit
    # under it hands arbitrary code execution to whoever can drop a file on disk.
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    sentinel = tmp_path / "resolver-executed-sentinel"
    resolver = fake / "scripts" / "lib" / "resolve-cli.sh"
    resolver.write_text(f"#!/usr/bin/env bash\ntouch {sentinel}\nprintf '{{}}\\n'\n")
    resolver.chmod(0o755)

    data = run_status("--plugin-root", str(fake))

    assert not sentinel.exists(), "status executed attacker-supplied resolver bytes"
    assert data["resolve_cli"]["ok"] is False
    assert data["resolve_cli"]["error"] in {"plugin_root_untrusted", "plugin_root_integrity_failed"}


def test_status_refuses_untrusted_resolver_root_from_environment(tmp_path, monkeypatch):
    fake = tmp_path / "busdriver-env"
    make_fake_busdriver(fake)
    sentinel = tmp_path / "env-resolver-sentinel"
    resolver = fake / "scripts" / "lib" / "resolve-cli.sh"
    resolver.write_text(f"#!/usr/bin/env bash\ntouch {sentinel}\nprintf '{{}}\\n'\n")
    resolver.chmod(0o755)

    env = dict(os.environ, BUSDRIVER_PLUGIN_ROOT=str(fake))
    proc = subprocess.run([sys.executable, str(SCRIPT), "--pretty"], text=True, capture_output=True, check=True, env=env)
    data = json.loads(proc.stdout)

    assert not sentinel.exists(), "status executed resolver bytes from an env-supplied root"
    if data["resolve_cli"]["ok"] is False:
        assert data["resolve_cli"]["error"] in {"plugin_root_untrusted", "plugin_root_integrity_failed", "external_resolver_disabled"}


def test_status_rejects_symlinked_resolver_at_the_canonical_root(tmp_path, monkeypatch):
    ns = runpy.run_path(str(SCRIPT))
    canonical = tmp_path / "canonical"
    (canonical / "scripts" / "lib").mkdir(parents=True)
    sentinel = tmp_path / "symlink-resolver-sentinel"
    real = tmp_path / "attacker-resolver.sh"
    real.write_text(f"#!/usr/bin/env bash\ntouch {sentinel}\nprintf '{{}}\\n'\n")
    (canonical / "scripts" / "lib" / "resolve-cli.sh").symlink_to(real)
    monkeypatch.setitem(ns["resolve_cli"].__globals__, "CANONICAL_PLUGIN_ROOT", canonical)

    result = ns["resolve_cli"](canonical)

    assert not sentinel.exists()
    assert result["ok"] is False
    assert result["error"] == "plugin_root_integrity_failed"


def test_status_rejects_resolver_whose_digest_does_not_match(tmp_path, monkeypatch):
    ns = runpy.run_path(str(SCRIPT))
    canonical = tmp_path / "canonical-digest"
    (canonical / "scripts" / "lib").mkdir(parents=True)
    sentinel = tmp_path / "digest-resolver-sentinel"
    resolver = canonical / "scripts" / "lib" / "resolve-cli.sh"
    resolver.write_text(f"#!/usr/bin/env bash\ntouch {sentinel}\nprintf '{{}}\\n'\n")
    monkeypatch.setitem(ns["resolve_cli"].__globals__, "CANONICAL_PLUGIN_ROOT", canonical)

    result = ns["resolve_cli"](canonical)

    assert not sentinel.exists()
    assert result["ok"] is False
    assert result["error"] == "plugin_root_integrity_failed"


def test_status_executes_resolver_bytes_that_match_the_bound_digest(tmp_path, monkeypatch):
    # Positive control: binding a temp root + digest proves the verified path really runs, so the
    # negatives above are rejecting untrusted bytes rather than failing for an unrelated reason.
    import hashlib

    ns = runpy.run_path(str(SCRIPT))
    canonical = tmp_path / "canonical-trusted"
    (canonical / "scripts" / "lib").mkdir(parents=True)
    body = '#!/usr/bin/env bash\nprintf \'{"clis":{"codex":{"available":true,"version":"bound"}}}\\n\'\n'
    resolver = canonical / "scripts" / "lib" / "resolve-cli.sh"
    resolver.write_text(body)
    monkeypatch.setitem(ns["resolve_cli"].__globals__, "CANONICAL_PLUGIN_ROOT", canonical)
    monkeypatch.setitem(ns["resolve_cli"].__globals__, "TRUSTED_RESOLVER_SHA256", hashlib.sha256(body.encode()).hexdigest())

    result = ns["resolve_cli"](canonical)

    assert result["ok"] is True
    assert result["data"]["clis"]["codex"]["available"] is True


def test_status_trusted_resolver_digest_matches_the_installed_canonical_resolver():
    ns = runpy.run_path(str(SCRIPT))
    assert ns["TRUSTED_RESOLVER_SHA256"] == "994d4176a802f08a49b65117fa9295e1eac45563b457b50979a886b723f97de9"
    assert ns["CANONICAL_PLUGIN_ROOT"] == Path.home() / ".claude/plugins/marketplaces/busdriver"


# --- v16-r21: ambient execution containment + structured OSError fail-closed ---

LOADER_INJECTION_ENV = {
    "PYTHONPATH": "/tmp/evil-pythonpath",
    "PYTHONHOME": "/tmp/evil-pythonhome",
    "PYTHONSTARTUP": "/tmp/evil-start.py",
    "BASH_ENV": "/tmp/evil-bash-env",
    "ENV": "/tmp/evil-env",
    "ZDOTDIR": "/tmp/evil-zdotdir",
    "LD_PRELOAD": "/tmp/evil.so",
    "LD_LIBRARY_PATH": "/tmp/evil-lib",
    "DYLD_INSERT_LIBRARIES": "/tmp/evil.dylib",
    "DYLD_LIBRARY_PATH": "/tmp/evil-dyld",
    "GIT_DIR": "/tmp/evil-git-dir",
    "GIT_INDEX_FILE": "/tmp/evil-index",
    "GIT_SSH_COMMAND": "/tmp/evil-ssh",
    "GIT_EXTERNAL_DIFF": "/tmp/evil-diff",
}


def test_status_child_env_is_allowlisted_and_drops_loader_injection(monkeypatch):
    ns = runpy.run_path(str(SCRIPT))
    for key, value in LOADER_INJECTION_ENV.items():
        monkeypatch.setenv(key, value)

    env = ns["child_env"]()

    assert env["PATH"] == ns["CONTAINED_PATH"]
    for key in LOADER_INJECTION_ENV:
        if key in {"GIT_DIR", "GIT_INDEX_FILE", "GIT_SSH_COMMAND", "GIT_EXTERNAL_DIFF"}:
            continue
        assert key not in env, f"{key} leaked into the child environment"
    # GIT_* may only appear as explicitly rebuilt safe values.
    assert {k: v for k, v in env.items() if k.startswith("GIT_")} == {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_PAGER": "cat",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_ALLOW_PROTOCOL": "",
    }


def test_status_never_executes_git_from_the_caller_path(tmp_path):
    ambient_bin = tmp_path / "ambient-bin"
    ambient_bin.mkdir()
    sentinel = tmp_path / "ambient-git-ran"
    ambient_git = ambient_bin / "git"
    ambient_git.write_text(f"#!/bin/sh\nprintf ran > {sentinel}\nexit 0\n")
    ambient_git.chmod(0o700)
    repo = tmp_path / "repo"
    repo.mkdir()

    cp = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--no-external-resolver"],
        text=True,
        capture_output=True,
        env={"PATH": str(ambient_bin), "HOME": str(tmp_path)},
    )

    assert not sentinel.exists(), "status executed git from the caller-controlled PATH"
    assert cp.returncode == 0, cp.stderr


def test_status_repo_pointing_at_a_file_fails_closed_without_traceback(tmp_path):
    not_a_dir = tmp_path / "regular-file.txt"
    not_a_dir.write_text("not a directory\n")

    cp = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(not_a_dir), "--no-external-resolver"],
        text=True,
        capture_output=True,
    )

    assert "Traceback" not in cp.stderr
    assert cp.returncode == 0, cp.stderr
    payload = json.loads(cp.stdout)
    assert payload["repo"]["is_git_repo"] is False
    assert payload["repo"]["error"]


def test_status_run_helper_returns_rc_127_on_launch_oserror(tmp_path):
    ns = runpy.run_path(str(SCRIPT))
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x\n")

    result = ns["run"](["git", "rev-parse", "HEAD"], cwd=not_a_dir)

    assert result["ok"] is False
    assert result["returncode"] == 127
    assert result["stderr"]


# --- v16-r26A item 3: fail-closed git observations + marker symlink bounds ---


def _git_init(repo: Path) -> None:
    for argv in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "t"],
        ["git", "commit", "-q", "--allow-empty", "-m", "init"],
    ):
        subprocess.run(argv, cwd=repo, check=True, capture_output=True)


def _failing_observation_run(label: str, returncode: int, stderr: str):
    """Wrap `run` so exactly one git observation fails, the way a timeout or broken repo does."""
    def factory(real_run):
        def fake_run(cmd, cwd=None, timeout=10, stdin_bytes=None, env=None):
            if label in cmd:
                return {"ok": False, "returncode": returncode, "stdout": "", "stderr": stderr}
            return real_run(cmd, cwd=cwd, timeout=timeout, stdin_bytes=stdin_bytes, env=env)
        return fake_run
    return factory


def test_status_git_status_timeout_never_reports_clean_worktree(tmp_path, monkeypatch):
    """A timed-out `git status` yields empty stdout — byte-identical to a clean tree. Must block."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init(repo)
    (repo / "dirty.txt").write_text("uncommitted\n")

    ns = runpy.run_path(str(SCRIPT))
    globals_ = ns["git_status"].__globals__
    monkeypatch.setitem(
        globals_, "run", _failing_observation_run("status", 124, "timeout after 10s")(globals_["run"])
    )

    result = ns["git_status"](str(repo))

    assert result["dirty"] is not False, "unobserved worktree reported as clean"
    assert result.get("observation_failed") or result.get("error"), "no failure surfaced"
    assert result.get("is_git_repo") is not True or result.get("observed") is False


def test_status_head_and_branch_nonzero_never_synthesize_empty_identity(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init(repo)

    ns = runpy.run_path(str(SCRIPT))
    globals_ = ns["git_status"].__globals__
    monkeypatch.setitem(
        globals_, "run", _failing_observation_run("--show-current", 128, "fatal: broken")(globals_["run"])
    )

    result = ns["git_status"](str(repo))

    assert result.get("branch") != "", "failed branch observation emitted as empty-string truth"
    assert result.get("observation_failed") or result.get("error")


def test_status_marker_preview_does_not_follow_symlink_to_secret(tmp_path):
    secret = tmp_path / "id_rsa"
    secret.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nSUPERSECRETKEYMATERIAL\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init(repo)
    state = repo / ".claude"
    state.mkdir()
    (state / "litmus-passed.local").symlink_to(secret)

    cp = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--no-external-resolver"],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    assert "SUPERSECRETKEYMATERIAL" not in cp.stdout, "status previewed a symlinked secret"

    payload = json.loads(cp.stdout)
    entry = payload["active_markers"]["files"]["litmus-passed.local"]
    assert entry.get("preview_lines") in (None, []), "symlinked marker was previewed"
    assert entry.get("is_symlink") is True or entry.get("read_error")


def test_status_marker_preview_refuses_hardlink_to_secret(tmp_path):
    secret = tmp_path / "token.txt"
    secret.write_text("SUPERSECRETHARDLINKMATERIAL\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init(repo)
    state = repo / ".claude"
    state.mkdir()
    os.link(secret, state / "litmus-passed.local")

    cp = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--no-external-resolver"],
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert cp.returncode == 0, cp.stderr
    assert "SUPERSECRETHARDLINKMATERIAL" not in cp.stdout
    entry = json.loads(cp.stdout)["active_markers"]["files"]["litmus-passed.local"]
    assert entry.get("preview_lines") in (None, [])
    assert entry.get("read_error") == "refusing_to_read_linked_file"


def test_status_marker_reader_stays_on_opened_state_generation_after_parent_swap(tmp_path, monkeypatch):
    ns = runpy.run_path(str(SCRIPT))
    active_markers = ns["active_markers"]
    runtime_os = active_markers.__globals__["os"]
    repo = tmp_path / "repo"
    repo.mkdir()
    state = repo / ".claude"
    state.mkdir()
    (state / "litmus-passed.local").write_text("SAFE-MARKER\n")
    hostile_state = tmp_path / "hostile-state"
    hostile_state.mkdir()
    (hostile_state / "litmus-passed.local").write_text("SECRET-FROM-REPLACEMENT\n")
    detached = repo / ".claude-old"
    real_lstat = runtime_os.lstat
    swapped = []

    def lstat_after_parent_swap(path, *args, **kwargs):
        if path == "litmus-passed.local" and kwargs.get("dir_fd") is not None and not swapped:
            swapped.append(True)
            state.rename(detached)
            state.symlink_to(hostile_state, target_is_directory=True)
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(runtime_os, "lstat", lstat_after_parent_swap)
    repo_status = {
        "is_git_repo": True, "root": str(repo), "observed": True,
        "head": "a" * 40, "branch": "main", "dirty": False, "head_commit_time": 0,
    }

    result = active_markers(repo_status, ".claude")

    assert swapped
    assert result is not None
    assert result["files"]["litmus-passed.local"]["preview_lines"] == ["SAFE-MARKER"]
    assert "SECRET-FROM-REPLACEMENT" not in json.dumps(result)


# --- v16-r27 item 7: a lock payload is only evidence if it is an object ---


def test_relay_lock_json_array_does_not_crash_the_status_probe(tmp_path: Path):
    """r26 Low: `payload["path"] = str(path)` assumed a dict after the parse handler.

    A valid JSON array parses fine and then raises TypeError on that assignment — uncaught, so the
    whole probe dies. Readiness forwards the caller's --relay-state-dir straight into this path.
    """
    ns = runpy.run_path(str(SCRIPT))
    locks = tmp_path / "locks"
    (locks / "array.lock").mkdir(parents=True)
    (locks / "array.lock" / "lock.json").write_text('["not", "an", "object"]')

    summary = ns["relay_lock_summary"]({"root": str(tmp_path)}, "finalization", str(tmp_path))

    assert summary["count"] == 1
    assert summary["active_for_repo"] == []
    assert summary["active_for_repo_count"] == 0


@pytest.mark.parametrize("payload", ['"a string"', "42", "null", "true", '["a"]'])
def test_non_object_relay_lock_payloads_are_reported_not_trusted(tmp_path: Path, payload: str):
    ns = runpy.run_path(str(SCRIPT))
    locks = tmp_path / "locks"
    (locks / "scalar.lock").mkdir(parents=True)
    (locks / "scalar.lock" / "lock.json").write_text(payload)

    summary = ns["relay_lock_summary"]({"root": str(tmp_path)}, "finalization", str(tmp_path))

    assert summary["active_for_repo"] == []
    assert all(isinstance(lock, dict) for lock in [*summary["active_for_repo"]])


# --- v16-r28 item 1: status must never publish the lock's release capability ---

LOCK_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "hermes-busdriver-lock"


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)
    return path


def _acquired_lock(state_dir: Path, repo: Path, operation: str) -> dict:
    cp = subprocess.run(
        [
            sys.executable,
            str(LOCK_SCRIPT),
            "acquire",
            "--state-dir",
            str(state_dir),
            "--repo",
            str(repo),
            "--operation",
            operation,
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    return json.loads(cp.stdout)


def test_relay_lock_summary_strips_the_release_token(tmp_path: Path):
    """r27 codex-correctness HIGH: status read lock.json raw and republished `token`.

    `token` is the ONLY authenticator `release` checks, so publishing it in a read-only probe
    hands every status consumer the capability to release someone else's lock.
    """
    ns = runpy.run_path(str(SCRIPT))
    repo = _git_repo(tmp_path / "repo")
    state = tmp_path / "state"
    acquired = _acquired_lock(state, repo, "finalization")

    summary = ns["relay_lock_summary"]({"root": str(repo.resolve())}, "finalization", str(state))

    assert summary["active_for_repo_count"] == 1
    holder = summary["active_for_repo"][0]
    assert "token" not in holder
    assert holder["token_redacted"] is True
    assert acquired["token"] not in json.dumps(summary)


def test_relay_lock_summary_keeps_owner_diagnostics(tmp_path: Path):
    """Stripping the capability must not strip the evidence a caller needs to see the holder."""
    ns = runpy.run_path(str(SCRIPT))
    repo = _git_repo(tmp_path / "repo")
    state = tmp_path / "state"
    _acquired_lock(state, repo, "finalization")

    summary = ns["relay_lock_summary"]({"root": str(repo.resolve())}, "finalization", str(state))
    holder = summary["active_for_repo"][0]

    assert holder["operation"] == "finalization"
    assert holder["repo"]["root"] == str(repo.resolve())
    assert isinstance(holder["owner_pid"], int)
    assert holder["lock_id"]
    assert holder["path"]
    assert holder["created_at_epoch"]


def test_status_json_carries_no_token_anywhere(tmp_path: Path):
    """Whole-envelope check: no `token` key survives at any depth, and the literal never appears."""
    repo = _git_repo(tmp_path / "repo")
    state = tmp_path / "state"
    acquired = _acquired_lock(state, repo, "repo-mutation")

    cp = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--no-external-resolver",
            "--relay-state-dir",
            str(state),
            "--operation",
            "repo-mutation",
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    assert acquired["token"] not in cp.stdout

    def token_keys(node):
        if isinstance(node, dict):
            return ("token" in node) or any(token_keys(v) for v in node.values())
        if isinstance(node, list):
            return any(token_keys(v) for v in node)
        return False

    assert not token_keys(json.loads(cp.stdout))


def test_status_output_cannot_release_the_lock(tmp_path: Path):
    """The end-to-end property: whatever status publishes must not authenticate a release."""
    repo = _git_repo(tmp_path / "repo")
    state = tmp_path / "state"
    acquired = _acquired_lock(state, repo, "finalization")

    ns = runpy.run_path(str(SCRIPT))
    summary = ns["relay_lock_summary"]({"root": str(repo.resolve())}, "finalization", str(state))
    published = summary["active_for_repo"][0]

    def release(token: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(LOCK_SCRIPT),
                "release",
                "--state-dir",
                str(state),
                "--repo",
                str(repo),
                "--operation",
                "finalization",
                "--token",
                token,
            ],
            text=True,
            capture_output=True,
        )

    # Every string a status consumer can scrape out of the published payload, tried as a token.
    candidates = [v for v in published.values() if isinstance(v, str)]
    assert candidates, "sanity: the payload should still carry string diagnostics"
    for candidate in candidates:
        cp = release(candidate)
        assert cp.returncode != 0, f"status published a working release token: {candidate!r}"
        assert json.loads(cp.stdout)["released"] is False

    # ...and the real token still works, proving the lock was never released along the way.
    cp = release(acquired["token"])
    assert cp.returncode == 0, cp.stderr
    assert json.loads(cp.stdout)["released"] is True


def test_nested_lock_token_is_stripped_recursively(tmp_path: Path):
    """A token nested below the top level is the same capability; depth is not a defence."""
    ns = runpy.run_path(str(SCRIPT))
    repo = tmp_path / "repo"
    repo.mkdir()
    locks = tmp_path / "locks"
    (locks / "nested.lock").mkdir(parents=True)
    (locks / "nested.lock" / "lock.json").write_text(
        json.dumps(
            {
                "token": "TOPLEVELTOKEN",
                "lock_id": "nested",
                "operation": "finalization",
                "repo": {"root": str(repo.resolve())},
                "owner_pid": 1,
                "owner": {"carried": {"token": "NESTEDTOKEN"}},
                "history": [{"token": "LISTTOKEN"}],
            }
        )
    )

    summary = ns["relay_lock_summary"]({"root": str(repo.resolve())}, "finalization", str(tmp_path))

    blob = json.dumps(summary)
    assert "TOPLEVELTOKEN" not in blob
    assert "NESTEDTOKEN" not in blob
    assert "LISTTOKEN" not in blob
