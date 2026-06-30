import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "hermes-busdriver-relay-role"


def run_role(*args: str, check: bool = True) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--pretty"],
        text=True,
        capture_output=True,
        check=check,
    )
    return proc.returncode, json.loads(proc.stdout)


def run_role_with_fake_status(tmp_path: Path, status_payload: dict, *args: str) -> tuple[int, dict]:
    scripts = tmp_path / "scripts"
    scripts.mkdir(parents=True)
    role_script = scripts / "hermes-busdriver-relay-role"
    role_script.write_text(SCRIPT.read_text())
    role_script.chmod(0o755)
    status_script = scripts / "hermes-busdriver-status"
    status_script.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        f"print(json.dumps({status_payload!r}))\n"
    )
    status_script.chmod(0o755)
    proc = subprocess.run(
        [sys.executable, str(role_script), *args, "--pretty"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.stderr == ""
    return proc.returncode, json.loads(proc.stdout)


def status_payload_for_role(entry):
    return {
        "relay_config": {"exists": True, "parse_error": None, "shape_error": None},
        "relay_equivalent_roles": {
            "roles": {"relay.pr.backstop": entry},
            "relay_config_parse_error": None,
            "relay_config_shape_error": None,
            "routes_config_error": None,
            "coding_agent_config_error": None,
            "avoid_coding_agent_for_review_config_error": None,
        },
    }


def test_relay_role_lists_known_roles_without_config(tmp_path):
    code, data = run_role("--list-roles", "--relay-config", str(tmp_path / "missing.json"))

    assert code == 0
    assert data["schema"] == "hermes-busdriver-relay-role/v0"
    assert data["read_only"] is True
    assert data["ok"] is True
    assert data["dispatch_allowed"] is False
    assert data["not_busdriver_native_claude_runtime"] is True
    assert "relay.pr.backstop" in data["roles"]
    assert "relay.blueprint.arbiter" in data["roles"]
    assert data["mutation_allowed"] is False
    assert data["finalization_allowed"] is False


def test_relay_role_invokes_status_script_as_subprocess():
    source = SCRIPT.read_text()
    assert "subprocess.run" in source
    assert "SourceFileLoader" not in source
    assert "importlib" not in source


def test_relay_role_resolves_configured_non_coding_reviewer(tmp_path):
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text(json.dumps({
        "coding_agent": "opencode",
        "avoid_coding_agent_for_review": True,
        "routes": {"relay.pr.backstop": ["opencode", "codex"]},
    }))

    code, data = run_role("--role", "relay.pr.backstop", "--relay-config", str(relay_config))

    assert code == 0
    assert data["status"] == "resolved"
    assert data["ok"] is True
    assert data["dispatch_allowed"] is True
    assert data["mutation_allowed"] is False
    assert data["finalization_allowed"] is False
    assert data["not_busdriver_native_claude_runtime"] is True
    assert data["coding_agent"] == "opencode"
    assert data["selected"]["configured_route"] == ["opencode", "codex"]
    assert data["selected"]["selected_agent"] == "codex"
    assert data["selected"]["same_as_coding_agent"] is False
    assert data["selected"]["degraded"] is False
    assert data["decision"] == {
        "dispatch_allowed": True,
        "mutation_allowed": False,
        "finalization_allowed": False,
        "not_busdriver_native_claude_runtime": True,
        "reason": "selected_agent_available",
    }


def test_relay_role_fails_closed_for_malformed_status_role_entry(tmp_path):
    for idx, (entry, reason) in enumerate([
        ([], "status_probe_invalid_role_shape"),
        ({"degraded": False, "selected_agent": True}, "status_probe_invalid_selected_agent_shape"),
        ({"degraded": "false", "selected_agent": "codex"}, "status_probe_invalid_role_degraded_shape"),
    ]):
        code, data = run_role_with_fake_status(
            tmp_path / f"case-{idx}",
            status_payload_for_role(entry),
            "--role",
            "relay.pr.backstop",
        )
        assert code == 2
        assert data["status"] == "degraded"
        assert data["ok"] is False
        assert data["dispatch_allowed"] is False
        assert data["reason"] == reason
        assert data["decision"]["dispatch_allowed"] is False


def test_relay_role_fails_closed_for_malformed_status_roles_container(tmp_path):
    payload = {
        "relay_config": {"exists": True, "parse_error": None, "shape_error": None},
        "relay_equivalent_roles": {
            "roles": ["relay.pr.backstop"],
        },
    }

    code, data = run_role_with_fake_status(tmp_path, payload, "--role", "relay.pr.backstop")

    assert code == 2
    assert data["status"] == "invalid_args"
    assert data["ok"] is False
    assert data["dispatch_allowed"] is False
    assert data["reason"] == "status_probe_invalid_roles_shape"


def test_relay_role_fails_closed_for_degraded_route(tmp_path):
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text(json.dumps({
        "coding_agent": "codex",
        "routes": {"relay.pr.backstop": []},
    }))

    code, data = run_role("--role", "relay.pr.backstop", "--relay-config", str(relay_config), check=False)

    assert code == 2
    assert data["status"] == "degraded"
    assert data["ok"] is False
    assert data["dispatch_allowed"] is False
    assert data["mutation_allowed"] is False
    assert data["finalization_allowed"] is False
    assert data["not_busdriver_native_claude_runtime"] is True
    assert data["selected"]["selected_agent"] is None
    assert data["selected"]["degraded"] is True
    assert data["selected"]["config_error"] == "empty_route"
    assert data["decision"]["dispatch_allowed"] is False
    assert data["decision"]["mutation_allowed"] is False
    assert data["decision"]["finalization_allowed"] is False


def test_relay_role_fails_closed_for_malformed_config(tmp_path):
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text("{not json")

    code, data = run_role("--role", "relay.pr.backstop", "--relay-config", str(relay_config), check=False)

    assert code == 2
    assert data["status"] == "degraded"
    assert data["relay_config"]["parse_error"]
    assert data["dispatch_allowed"] is False
    assert data["selected"]["config_error"] == "config_parse_error"
    assert data["selected"]["selected_agent"] is None


def test_relay_role_fails_closed_for_invalid_top_level_config_values(tmp_path):
    relay_config = tmp_path / "relay-config.json"
    relay_config.write_text(json.dumps({
        "coding_agent": "",
        "avoid_coding_agent_for_review": "false",
        "routes": {"relay.pr.backstop": ["codex"]},
    }))

    code, data = run_role("--role", "relay.pr.backstop", "--relay-config", str(relay_config), check=False)

    assert code == 2
    assert data["status"] == "degraded"
    assert data["ok"] is False
    assert data["dispatch_allowed"] is False
    assert data["reason"] == "coding_agent_must_be_non_empty_string"
    assert data["coding_agent_config_error"] == "coding_agent_must_be_non_empty_string"
    assert data["avoid_coding_agent_for_review_config_error"] == "avoid_coding_agent_for_review_must_be_boolean"
    assert data["selected"]["selected_agent"] == "codex"
    assert data["selected"]["degraded"] is False
    assert data["decision"]["dispatch_allowed"] is False
    assert data["decision"]["mutation_allowed"] is False
    assert data["decision"]["finalization_allowed"] is False


def test_relay_role_unknown_role_is_not_dispatchable(tmp_path):
    code, data = run_role("--role", "relay.unknown", "--relay-config", str(tmp_path / "missing.json"), check=False)

    assert code == 64
    assert data["status"] == "unknown_role"
    assert data["ok"] is False
    assert data["dispatch_allowed"] is False
    assert data["mutation_allowed"] is False
    assert data["finalization_allowed"] is False
    assert data["not_busdriver_native_claude_runtime"] is True
    assert data["selected"] is None
    assert data["decision"]["dispatch_allowed"] is False
    assert "relay.pr.backstop" in data["known_roles"]


def test_relay_role_invalid_invocations_return_json_fail_closed():
    cases = [
        (["--pretty"], "role_required_unless_list_roles"),
        (["--role", "relay.pr.backstop", "--list-roles", "--pretty"], "role_and_list_roles_are_mutually_exclusive"),
        (["--unknown", "value", "--pretty"], "unknown_arguments"),
        (["--relay", "value", "--pretty"], "unknown_arguments"),
        (["--role", "--pretty"], "argument_parse_error"),
    ]
    for args, reason in cases:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
        )
        assert proc.returncode == 64
        assert proc.stderr == ""
        data = json.loads(proc.stdout)
        assert data["schema"] == "hermes-busdriver-relay-role/v0"
        assert data["status"] == "invalid_args"
        assert data["ok"] is False
        assert data["reason"] == reason
        assert data["dispatch_allowed"] is False
        assert data["mutation_allowed"] is False
        assert data["finalization_allowed"] is False
        assert data["not_busdriver_native_claude_runtime"] is True
        assert data["selected"] is None
        assert data["decision"]["dispatch_allowed"] is False
