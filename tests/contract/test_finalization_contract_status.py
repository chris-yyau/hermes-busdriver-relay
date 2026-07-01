import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_STATUS = ROOT / "scripts" / "hermes-busdriver-finalization-contract-status"
AUTHORITY_KEYS = [
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
UNSAFE_BOOLEAN_KEYS = [
    *AUTHORITY_KEYS,
    "dispatch_allowed",
    "mutation_allowed",
    "programmatic_execution_allowed",
    "marker_interop_allowed",
    "raw_codex_exec_allowed",
    "non_codex_agent_enablement_allowed",
    "capability_allowed",
    "safe_to_execute_by_this_helper",
    "implemented",
    "retired",
]
EXPECTED_REMAINING_WORK_IDS = {
    "deliver-mutating-executor",
    "mutating-final-result-envelope",
    "programmatic-litmus-pre-pr-dual-review",
    "mutating-pr-grind-fix-push-loop",
    "busdriver-marker-interop",
}


def run_contract_status(*extra: str, cwd: Path | None = None) -> tuple[subprocess.CompletedProcess[str], dict]:
    cp = subprocess.run(
        [sys.executable, str(CONTRACT_STATUS), *extra],
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    try:
        data = json.loads(cp.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"contract-status output was not JSON (returncode={cp.returncode})\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
        ) from e
    return cp, data


def assert_no_positive_finalization_authority(payload: object) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in UNSAFE_BOOLEAN_KEYS:
                assert value is False
            assert_no_positive_finalization_authority(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_positive_finalization_authority(item)


def test_contract_status_emits_read_only_policy_blocked_matrix():
    cp, data = run_contract_status("--pretty")

    assert cp.returncode == 0, cp.stderr
    assert data["schema"] == "hermes-busdriver-finalization-contract-status/v0"
    assert data["version"] == 0
    assert data["ok"] is True
    assert data["read_only"] is True
    assert data["contract_adr"] == "ADRs/0005-finalization-authority-integration-contract.md"
    assert data["contract_adrs"] == [
        "ADRs/0005-finalization-authority-integration-contract.md",
        "ADRs/0006-programmatic-dual-review-marker-interop.md",
    ]
    assert data["related_design_adrs"] == ["ADRs/0006-programmatic-dual-review-marker-interop.md"]
    assert data["source_remaining_work"] == "scripts/hermes-busdriver-finalization-readiness:finalization_guardrails.remaining_work"
    assert data["current_policy"] == "non_mutating_relay_only"
    assert data["guardrails_schema"] == "hermes-busdriver-finalization-guardrails/v0"
    assert data["retired_remaining_work"] == []
    assert data["summary"] == {
        "remaining_work_count": 5,
        "policy_blocked_count": 5,
        "retired_count": 0,
        "capability_allowed_count": 0,
        "finalization_flags_policy": "non_mutating_relay_only",
    }
    assert {item["id"] for item in data["remaining_work"]} == EXPECTED_REMAINING_WORK_IDS
    assert set(data["unsupported_mutating_operations"]) == {
        "commit",
        "push",
        "pr_create",
        "merge",
        "deploy",
        "release",
        "publish",
        "busdriver_marker_write",
        "gate_bypass",
        "raw_codex_exec",
        "non_codex_agent_enablement",
        "autonomous_git_github_mutation",
    }
    for key in AUTHORITY_KEYS:
        assert data["authority"][key] is False
        assert data["decision"][key] is False
    assert data["decision"]["status"] == "policy_blocked"
    assert_no_positive_finalization_authority(data)


def test_contract_status_records_adr_0005_unlock_criteria_by_surface():
    _, data = run_contract_status()
    by_id = {item["id"]: item for item in data["remaining_work"]}

    for item in by_id.values():
        assert item["status"] == "policy_blocked"
        assert item["retired"] is False
        assert item["implemented"] is False
        assert item["safe_to_execute_by_this_helper"] is False
        assert item["capability_allowed"] is False
        assert item["missing_unlock_criteria"]
        assert item["missing_authority_sources"] == data["required_authority_sources"]
        assert item["authority"] == data["authority"]
        assert item["adr_sections"]

    assert "busdriver_approved_seam" in by_id["deliver-mutating-executor"]["missing_unlock_criteria"]
    assert "mutating_schema" in by_id["deliver-mutating-executor"]["missing_unlock_criteria"]
    assert "hook_runtime_or_equivalent_proof" in by_id["deliver-mutating-executor"]["missing_unlock_criteria"]
    assert "schema_authority" in by_id["mutating-final-result-envelope"]["missing_unlock_criteria"]
    assert "busdriver_approved_reviewer_role_mappings_or_native_invocation_seam" in by_id[
        "programmatic-litmus-pre-pr-dual-review"
    ]["missing_unlock_criteria"]
    assert "reviewer_role_mapping_contract" in by_id[
        "programmatic-litmus-pre-pr-dual-review"
    ]["missing_unlock_criteria"]
    assert "model_provider_session_independence" in by_id[
        "programmatic-litmus-pre-pr-dual-review"
    ]["missing_unlock_criteria"]
    assert "timestamps_and_freshness" in by_id[
        "programmatic-litmus-pre-pr-dual-review"
    ]["missing_unlock_criteria"]
    assert "data_egress_and_redaction" in by_id[
        "programmatic-litmus-pre-pr-dual-review"
    ]["missing_unlock_criteria"]
    assert "marker_write_separation_contract" in by_id["programmatic-litmus-pre-pr-dual-review"]["missing_unlock_criteria"]
    assert by_id["programmatic-litmus-pre-pr-dual-review"]["related_design_adrs"] == [
        "ADRs/0006-programmatic-dual-review-marker-interop.md"
    ]
    assert "busdriver_approved_pr_grind_seam" in by_id["mutating-pr-grind-fix-push-loop"]["missing_unlock_criteria"]
    assert "latest_pr_head_tracking" in by_id["mutating-pr-grind-fix-push-loop"]["missing_unlock_criteria"]
    assert "marker_ownership_contract" in by_id["busdriver-marker-interop"]["missing_unlock_criteria"]
    assert "busdriver_approved_writer_identity" in by_id["busdriver-marker-interop"]["missing_unlock_criteria"]
    assert "busdriver_trusted_writer_commands" in by_id["busdriver-marker-interop"]["missing_unlock_criteria"]
    assert "atomic_write_contract" in by_id["busdriver-marker-interop"]["missing_unlock_criteria"]
    assert "atomic_fsync_rename_contract" in by_id["busdriver-marker-interop"]["missing_unlock_criteria"]
    assert "allowed_marker_paths_and_symlink_safety" in by_id["busdriver-marker-interop"]["missing_unlock_criteria"]
    assert "marker_freshness_windows" in by_id["busdriver-marker-interop"]["missing_unlock_criteria"]
    assert by_id["busdriver-marker-interop"]["related_design_adrs"] == [
        "ADRs/0006-programmatic-dual-review-marker-interop.md"
    ]
    assert "hermes-busdriver-mutating-delivery-run/v0" in by_id["mutating-final-result-envelope"]["missing_future_schemas"]
    assert "hermes-busdriver-marker-interop/v0" in by_id["busdriver-marker-interop"]["missing_future_schemas"]


def test_contract_status_is_read_only_and_does_not_create_repo_state(tmp_path: Path):
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

    cp, data = run_contract_status(cwd=tmp_path)

    after = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    assert cp.returncode == 0, cp.stderr
    assert data["read_only"] is True
    assert before == after == []
    assert not (tmp_path / ".claude").exists()
    assert not (tmp_path / ".hermes").exists()
    assert not (tmp_path / ".git").exists()
