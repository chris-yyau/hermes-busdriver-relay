import json
import subprocess
import sys
from pathlib import Path


PLAN = Path(__file__).resolve().parents[2] / "scripts" / "hermes-busdriver-agent-balance-plan"

AUTHORITY_FALSE_KEYS = [
    "commit_allowed",
    "push_allowed",
    "pr_allowed",
    "merge_allowed",
    "deploy_allowed",
    "release_allowed",
    "publish_allowed",
    "marker_write_allowed",
    "repo_mutation_allowed",
    "mutation_allowed",
    "finalization_allowed",
    "dispatch_allowed",
    "programmatic_execution_allowed",
]

EXECUTION_FALSE_KEYS = {
    "external_agents_called",
    "subprocess_dispatch_called",
    "codex_called",
    "github_called",
    "marker_writes_performed",
    "repo_mutations_performed",
}


def assert_recursive_authority_safe(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("_allowed") or key in EXECUTION_FALSE_KEYS:
                assert child is False, f"{key} must be strict false"
            assert_recursive_authority_safe(child)
    elif isinstance(value, list):
        for child in value:
            assert_recursive_authority_safe(child)


def run_plan(*args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    cp = subprocess.run([sys.executable, str(PLAN), *args], text=True, capture_output=True, check=False, timeout=30)
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return cp, json.loads(cp.stdout)


def test_agent_balance_plan_emits_read_only_balanced_planning_envelope():
    _cp, data = run_plan()

    assert data["schema"] == "hermes-busdriver-agent-balance-plan/v0"
    assert data["read_only"] is True
    assert data["ok"] is True
    assert data["policy"]["id"] == "single_mutating_worker_multi_readonly_reviewers"
    assert data["policy"]["metadata_only"] is True
    assert data["policy"]["planning_only"] is True
    assert data["policy"]["max_mutating_draft_workers"] == 1
    assert data["policy"]["read_only_lanes_parallelizable"] is True
    assert data["policy"]["main_hermes_role"] == "operator_verifier_finalizer"
    assert data["policy"]["delivery_mode_required_for_finalization"] is True

    authority = data["authority"]
    for key in AUTHORITY_FALSE_KEYS:
        assert authority[key] is False

    lanes = {lane["id"]: lane for lane in data["lanes"]}
    assert {"implementation_draft", "readonly_review", "readonly_status"} <= set(lanes)

    implementation = lanes["implementation_draft"]
    assert implementation["max_parallel"] == 1
    assert implementation["mode"] == "mutating_draft"
    assert implementation["requires_gate"] is True
    assert implementation["selected_agent"] == "codex"
    assert implementation["current_agent"] == "codex"
    assert implementation["repo_mutation_allowed"] is False

    for lane_id in ["readonly_review", "readonly_status"]:
        lane = lanes[lane_id]
        assert lane["mode"].startswith("read_only")
        assert lane["max_parallel"] > 1
        assert lane["parallelizable"] is True
        assert lane["repo_mutation_allowed"] is False
        assert lane["requires_gate"] is False

    assert_recursive_authority_safe(data)


def test_agent_balance_plan_is_metadata_only_and_does_not_dispatch():
    _cp, data = run_plan()

    execution = data["execution"]
    assert execution["metadata_only"] is True
    assert execution["planning_only"] is True
    assert execution["external_agents_called"] is False
    assert execution["subprocess_dispatch_called"] is False
    assert execution["codex_called"] is False
    assert execution["github_called"] is False
    assert execution["marker_writes_performed"] is False
    assert execution["repo_mutations_performed"] is False


def test_agent_balance_plan_supports_pretty_output():
    cp, data = run_plan("--pretty")

    assert cp.stdout.startswith("{\n")
    assert '\n  "authority"' in cp.stdout
    assert data["schema"] == "hermes-busdriver-agent-balance-plan/v0"
