import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from pr_grind_fixtures import bind_github_origin, pr_grind_payload


ROOT = Path(__file__).resolve().parents[2]
READINESS = ROOT / "scripts" / "hermes-busdriver-finalization-readiness"
# Source-separated, never installed: the only entrypoint that can inject a helper double.
READINESS_HARNESS = ROOT / "tests" / "fixtures" / "finalization-readiness-test-harness"
PHASE0_STATUS = ROOT / "scripts" / "hermes-busdriver-status"
LOCK = ROOT / "scripts" / "hermes-busdriver-lock"
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
    "repo_mutation_allowed",
    "external_agents_called",
    "subprocess_dispatch_called",
    "codex_called",
    "github_called",
    "marker_writes_performed",
    "repo_mutations_performed",
    "safe_to_execute_by_this_helper",
]


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 30, env_override: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=False, timeout=timeout, env=env_override)


def init_repo(path: Path) -> Path:
    path.mkdir()
    assert run(["git", "init"], path).returncode == 0
    assert run(["git", "config", "user.email", "test@example.test"], path).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], path).returncode == 0
    (path / "README.md").write_text("# test\n")
    assert run(["git", "add", "README.md"], path).returncode == 0
    assert run(["git", "commit", "-m", "init"], path).returncode == 0
    return path


def init_uncommitted_repo(path: Path) -> Path:
    path.mkdir()
    assert run(["git", "init"], path).returncode == 0
    assert run(["git", "config", "user.email", "test@example.test"], path).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], path).returncode == 0
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


def litmus_status_fixture(
    path: Path,
    *,
    repo: Path | None = None,
    status: str = "stale_or_missing",
    ok: object = True,
    authority_true_key: str | None = None,
    malicious_sentinel: str | None = None,
    litmus_fresh_for_head: bool = False,
    pr_codex_lead_fresh_for_branch_diff: bool = False,
    pr_backstop_verdict_fresh_for_branch_diff: bool = False,
    pr_review_passed_fresh_for_branch_diff: bool = False,
) -> Path:
    false_flags = {
        "finalization_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pr_allowed": False,
        "merge_allowed": False,
        "deploy_allowed": False,
        "release_allowed": False,
        "publish_allowed": False,
        "marker_write_allowed": False,
    }
    decision_flags = dict(false_flags)
    if authority_true_key:
        decision_flags[authority_true_key] = True
    state_dir = path.parent / ".claude"

    def git_value(*args: str) -> str:
        if repo is None:
            return ""
        return run(["git", *args], repo).stdout.strip()

    repo_summary = {
        "root": str(repo.resolve()) if repo is not None else str(path.parent),
        "branch": git_value("branch", "--show-current") or "main",
        "head": git_value("rev-parse", "HEAD") or "abc123",
        "head_timestamp": 1,
        "base_ref": "origin/main",
        "branch_diff_hash": None,
    }
    state_summary = {"path": str(state_dir), "exists": False, "is_symlink": False, "has_symlink_component": False}
    markers = {
        "litmus_passed": {"path": str(state_dir / "litmus-passed.local"), "exists": litmus_fresh_for_head, "fresh_for_head": litmus_fresh_for_head},
        "pr_codex_lead": {"path": str(state_dir / "pr-codex-lead.local.json"), "exists": pr_codex_lead_fresh_for_branch_diff, "fresh_for_branch_diff": pr_codex_lead_fresh_for_branch_diff},
        "pr_backstop_verdict": {"path": str(state_dir / "pr-backstop-verdict.local.json"), "exists": pr_backstop_verdict_fresh_for_branch_diff, "fresh_for_branch_diff": pr_backstop_verdict_fresh_for_branch_diff},
        "pr_review_passed": {"path": str(state_dir / "pr-review-passed.local"), "exists": pr_review_passed_fresh_for_branch_diff, "fresh_for_branch_diff": pr_review_passed_fresh_for_branch_diff},
    }
    warnings: list[str] = []
    blockers: list[str] = []
    if malicious_sentinel:
        repo_summary["root"] = f"{path.parent}/repo-token={malicious_sentinel}"
        repo_summary["unknown_secret"] = malicious_sentinel
        state_summary["path"] = f"{state_dir}/api_key={malicious_sentinel}"
        state_summary["unknown_secret"] = malicious_sentinel
        markers["unknown_marker_secret"] = {"path": malicious_sentinel, "exists": True, "secret": malicious_sentinel}
        markers["litmus_passed"]["path"] = f"{state_dir}/litmus-passed.local?token={malicious_sentinel}"
        markers["litmus_passed"]["read_error"] = f"password={malicious_sentinel}"
        markers["litmus_passed"]["stat_error"] = f"stat token={malicious_sentinel}"
        markers["litmus_passed"]["unknown_secret"] = malicious_sentinel
        warnings = [f"warning {malicious_sentinel}"]
        blockers = [f"blocker {malicious_sentinel}"]
    path.write_text(json.dumps({
        "schema": "hermes-busdriver-litmus-status/v0",
        "read_only": True,
        "ok": ok,
        "repo": repo_summary,
        "state_dir": state_summary,
        "markers": markers,
        "decision": {"status": status, "warnings": warnings, "blockers": blockers, **decision_flags, "not_busdriver_native_claude_runtime": True, "unexpected_secret": malicious_sentinel},
    }))
    return path


def drift_baseline_fixture(path: Path, plugin: Path) -> Path:
    cp = run([sys.executable, str(PHASE0_STATUS), "--plugin-root", str(plugin)])
    assert cp.returncode == 0, cp.stderr + cp.stdout
    current = json.loads(cp.stdout)
    path.write_text(json.dumps({
        "status_schema": "hermes-busdriver-status/v0",
        "package": {"version": current["package"]["version"]},
        "critical_file_hashes": current["critical_file_hashes"],
    }))
    return path


CUSTOM_HELPER_SCRIPT_FLAGS = ("--pr-grind-check-script", "--litmus-status-script", "--agent-balance-plan-script")
# v16-r33 A: a caller-supplied RESULT file is the same declaration of a double as a caller-named
# script, so it routes to the harness too. Production no longer parses OR forwards these.
FIXTURE_RESULT_FLAGS = ("--pr-grind-result-file", "--litmus-status-result-file")
FIXTURE_ROUTED_FLAGS = CUSTOM_HELPER_SCRIPT_FLAGS + FIXTURE_RESULT_FLAGS


def readiness_entrypoint(extra: tuple[str, ...]) -> Path:
    """Naming a helper script IS declaring a fixture double, so these helpers route accordingly.

    v16-r32 item 1: production readiness has no path to a caller-named executable — not its own
    --agent-balance-plan-script, and not the ones it forwards to delivery-status. The doubles live
    behind the source-separated harness instead. Tests that mean to exercise the production
    refusal build their argv against READINESS directly and never pass through here.
    """
    if any(flag in extra for flag in FIXTURE_ROUTED_FLAGS):
        return READINESS_HARNESS
    return READINESS


def invoke(repo: Path, plugin: Path, user_config: Path, *extra: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    cp = run(
        [
            sys.executable,
            str(readiness_entrypoint(extra)),
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
    for key in AUTHORITY_KEYS:
        assert authority[key] is False


def assert_no_positive_finalization_authority(payload: object) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in UNSAFE_BOOLEAN_KEYS:
                assert value is False
            assert_no_positive_finalization_authority(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_positive_finalization_authority(item)


def load_readiness_module():
    return __import__("runpy").run_path(str(READINESS))


@pytest.mark.parametrize(
    "delivery_overrides",
    [
        {"schema": "wrong/v0", "read_only": True, "ok": True},
        {"schema": "hermes-busdriver-delivery-status/v0", "read_only": False, "ok": True},
        {"schema": "hermes-busdriver-delivery-status/v0", "read_only": True, "ok": "true"},
    ],
    ids=["wrong_schema", "read_only_false", "ok_non_boolean"],
)
def test_readiness_blocks_invalid_delivery_status_helper_envelope(delivery_overrides: dict[str, object]):
    mod = load_readiness_module()
    args = type("Args", (), {"target": "auto", "pr": None})()
    delivery = {
        "schema": "hermes-busdriver-delivery-status/v0",
        "read_only": True,
        "ok": True,
        "repo": {"dirty": True},
        "decision": {"blockers": [], "warnings": []},
        **delivery_overrides,
    }
    phase0 = {
        "status_schema": "hermes-busdriver-status/v0",
        "plugin_root": {"exists": True},
        "hooks": {"exists": True},
        "repo": {"is_git_repo": True},
        "relay_locks": {"active_for_repo_count": 0},
    }
    contract_status = {"ok": True}
    agent_balance_plan = {"ok": True}

    ready = mod["readiness"](args, delivery, phase0, contract_status, agent_balance_plan)

    assert ready["ready"] is False
    assert ready["status"] == "blocked"
    assert "delivery_status_schema_invalid" in ready["blockers"]
    assert_no_positive_finalization_authority(ready)


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


def test_clean_idle_repo_reports_no_finalization_candidate_despite_stale_litmus(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(tmp_path / "blocked-litmus-status.json", repo=repo, status="blocked")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    assert data["delivery_status"]["decision"]["stage"] == "no_local_changes"
    assert data["delivery_status"]["repo"]["dirty"] is False
    assert data["readiness"]["ready"] is False
    # r24: the idle-repo rule still strips litmus_status_not_fresh; the fixture provenance
    # blocker is a separate concern and survives it.
    assert data["readiness"]["status"] == "blocked"
    assert "litmus_status_not_fresh" in data["delivery_status"]["decision"]["blockers"]
    assert "litmus_status_not_fresh" not in data["readiness"]["blockers"]
    assert data["readiness"]["blockers"] == ["fixture_evidence_not_authoritative"]
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert data["decision"]["status"] == "blocked"
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])
    assert_no_positive_finalization_authority(data)


def test_readiness_handoff_includes_machine_readable_remaining_finalization_work(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config)

    assert cp.returncode == 0, cp.stderr
    guardrails = data["finalization_guardrails"]
    contract = data["finalization_contract_status"]
    work = guardrails["remaining_work"]
    contract_by_id = {item["id"]: item for item in contract["remaining_work"]}
    assert guardrails["schema"] == "hermes-busdriver-finalization-guardrails/v0"
    assert guardrails["version"] == 0
    assert guardrails["read_only"] is True
    assert guardrails["status"] == "gated_delivery_mode_executor"
    assert contract["schema"] == "hermes-busdriver-finalization-contract-status/v0"
    assert contract["read_only"] is True
    assert contract["current_policy"] == "gated_delivery_mode_executor"
    assert contract["contract_adrs"] == [
        "ADRs/0005-finalization-authority-integration-contract.md",
        "ADRs/0006-programmatic-dual-review-marker-interop.md",
    ]
    assert contract["related_design_adrs"] == ["ADRs/0006-programmatic-dual-review-marker-interop.md"]
    assert contract["summary"] == {
        "remaining_work_count": 5,
        "policy_blocked_count": 3,
        "implemented_count": 2,
        "retired_count": 0,
        "capability_allowed_count": 0,
        "finalization_flags_policy": "gated_delivery_mode_executor",
    }
    assert data["finalization_contract_status_returncode"] == 0
    assert data["handoff_envelope"]["finalization_contract_status"] == contract
    assert data["handoff_envelope"]["evidence"]["finalization_contract_status"] == contract
    assert {item["id"] for item in contract["remaining_work"]} == {item["id"] for item in work}
    assert data["read_only"] is True
    assert data["handoff_envelope"]["read_only"] is True
    assert data["handoff_envelope"]["finalization_guardrails"] == guardrails
    assert data["readiness"]["finalization_guardrail_status"] == guardrails["status"]
    assert {item["id"] for item in work} == {
        "deliver-mutating-executor",
        "mutating-final-result-envelope",
        "programmatic-litmus-pre-pr-dual-review",
        "mutating-pr-grind-fix-push-loop",
        "busdriver-marker-interop",
    }
    assert contract_by_id["programmatic-litmus-pre-pr-dual-review"]["contract_adrs"] == contract["contract_adrs"]
    assert contract_by_id["busdriver-marker-interop"]["contract_adrs"] == contract["contract_adrs"]
    guardrail_by_id = {item["id"]: item for item in work}
    assert guardrail_by_id["deliver-mutating-executor"]["status"] == "implemented_gated"
    assert guardrail_by_id["deliver-mutating-executor"]["implemented"] is True
    assert guardrail_by_id["mutating-final-result-envelope"]["status"] == "implemented_gated"
    assert guardrail_by_id["mutating-final-result-envelope"]["implemented"] is True
    assert all(
        item["status"] == "policy_blocked"
        for item in work
        if item["id"] not in {"deliver-mutating-executor", "mutating-final-result-envelope"}
    )
    assert all(item["safe_to_execute_by_this_helper"] is False for item in work)
    assert set(guardrails["unsupported_mutating_operations"]) == {
        "pre_pr_review",
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
    assert set(data["handoff_envelope"]["forbidden_by_this_helper"]) == set(guardrails["unsupported_mutating_operations"])
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])
    assert_no_positive_finalization_authority(data)


def test_readiness_embeds_agent_balance_plan_evidence(tmp_path: Path):
    repo = init_uncommitted_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config)

    assert cp.returncode == 0, cp.stderr
    plan = data["agent_balance_plan"]
    assert plan["schema"] == "hermes-busdriver-agent-balance-plan/v0"
    assert plan["read_only"] is True
    assert plan["ok"] is True
    assert plan["execution"]["subprocess_dispatch_called"] is False
    assert plan["execution"]["repo_mutations_performed"] is False
    assert data["handoff_envelope"]["agent_balance_plan"] == plan
    assert data["handoff_envelope"]["evidence"]["agent_balance_plan"] == plan
    assert_no_positive_finalization_authority(plan)
    assert_no_positive_finalization_authority(data)


def test_readiness_blocks_when_agent_balance_plan_schema_invalid(tmp_path: Path):
    repo = init_uncommitted_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    bad_plan = tmp_path / "bad-agent-balance-plan"
    bad_plan.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "print(json.dumps({'schema': 'wrong/v0', 'ok': True, 'read_only': True}))\n"
    )
    bad_plan.chmod(0o755)
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--agent-balance-plan-script", str(bad_plan))

    assert cp.returncode == 1, cp.stderr
    assert data["ok"] is False
    assert data["agent_balance_plan_returncode"] == 1
    plan = data["agent_balance_plan"]
    assert plan["ok"] is False
    assert plan["read_only"] is True
    assert plan["reason"] == "agent_balance_plan_schema_invalid"
    assert_no_finalization_authority(plan["authority"])
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert "agent_balance_plan_unavailable" in data["readiness"]["blockers"]
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert data["handoff_envelope"]["agent_balance_plan"] == plan
    assert data["handoff_envelope"]["evidence"]["agent_balance_plan"] == plan
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])
    assert_no_positive_finalization_authority(data)


def test_readiness_blocks_when_agent_balance_plan_authority_flags_unsafe(tmp_path: Path):
    repo = init_uncommitted_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    bad_plan = tmp_path / "unsafe-agent-balance-plan"
    bad_plan.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "print(json.dumps({\n"
        "  'schema': 'hermes-busdriver-agent-balance-plan/v0',\n"
        "  'ok': True,\n"
        "  'read_only': True,\n"
        "  'authority': {'finalization_allowed': True},\n"
        "  'execution': {'codex_called': True}\n"
        "}))\n"
    )
    bad_plan.chmod(0o755)
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--agent-balance-plan-script", str(bad_plan))

    assert cp.returncode == 1, cp.stderr
    assert data["ok"] is False
    assert data["agent_balance_plan_returncode"] == 1
    plan = data["agent_balance_plan"]
    assert plan["ok"] is False
    assert plan["reason"] == "agent_balance_plan_authority_flags_unsafe"
    assert "agent_balance_plan_unavailable" in data["readiness"]["blockers"]
    assert data["handoff_envelope"]["agent_balance_plan"] == plan
    assert data["handoff_envelope"]["evidence"]["agent_balance_plan"] == plan
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])
    assert_no_positive_finalization_authority(data)


def test_readiness_blocks_when_agent_balance_plan_subprocess_failed(tmp_path: Path):
    repo = init_uncommitted_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    bad_plan = tmp_path / "failed-agent-balance-plan"
    bad_plan.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "print(json.dumps({'schema': 'hermes-busdriver-agent-balance-plan/v0', 'ok': False, 'read_only': True}))\n"
        "sys.exit(2)\n"
    )
    bad_plan.chmod(0o755)
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--agent-balance-plan-script", str(bad_plan))

    assert cp.returncode == 2, cp.stderr
    assert data["ok"] is False
    assert data["agent_balance_plan_returncode"] == 2
    plan = data["agent_balance_plan"]
    assert plan["ok"] is False
    assert plan["reason"] == "agent_balance_plan_subprocess_failed"
    assert "agent_balance_plan_unavailable" in data["readiness"]["blockers"]
    assert data["handoff_envelope"]["agent_balance_plan"] == plan
    assert data["handoff_envelope"]["evidence"]["agent_balance_plan"] == plan
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])
    assert_no_positive_finalization_authority(data)


def test_readiness_blocks_when_agent_balance_plan_times_out(tmp_path: Path):
    repo = init_uncommitted_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    bad_plan = tmp_path / "slow-agent-balance-plan"
    bad_plan.write_text(
        "#!/usr/bin/env python3\n"
        "import time\n"
        "time.sleep(2)\n"
    )
    bad_plan.chmod(0o755)
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(
        repo,
        plugin,
        user_config,
        "--agent-balance-plan-script",
        str(bad_plan),
        "--agent-balance-plan-timeout",
        "1",
    )

    assert cp.returncode == 124, cp.stderr
    assert data["ok"] is False
    assert data["agent_balance_plan_returncode"] == 124
    plan = data["agent_balance_plan"]
    assert plan["ok"] is False
    assert plan["reason"] == "agent_balance_plan_subprocess_failed"
    assert "agent_balance_plan_unavailable" in data["readiness"]["blockers"]
    assert data["handoff_envelope"]["agent_balance_plan"] == plan
    assert data["handoff_envelope"]["evidence"]["agent_balance_plan"] == plan
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])
    assert_no_positive_finalization_authority(data)


def test_readiness_handoff_includes_read_only_dual_review_status_envelope(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    relay_cfg = tmp_path / "relay-config.json"
    relay_cfg.write_text(json.dumps({
        "coding_agent": "codex",
        "avoid_coding_agent_for_review": False,
        "routes": {
            "relay.litmus.reviewer": ["codex"],
            "relay.pr.lead": ["codex"],
            "relay.pr.backstop": ["codex"],
        },
    }))
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--relay-config", str(relay_cfg))

    assert cp.returncode == 0, cp.stderr
    dual = data["dual_review_readiness"]
    assert dual["schema"] == "hermes-busdriver-dual-review-readiness/v0"
    assert dual["version"] == 0
    assert dual["read_only"] is True
    assert dual["status"] == "unsupported_in_this_relay"
    assert dual["ok"] is False
    assert dual["programmatic_execution_supported"] is False
    assert dual["programmatic_execution_allowed"] is False
    assert dual["not_busdriver_native_claude_runtime"] is True
    assert dual["required_roles"] == [
        "relay.litmus.reviewer",
        "relay.pr.lead",
        "relay.pr.backstop",
    ]
    assert [item["role"] for item in dual["role_requirements"]] == dual["required_roles"]
    assert dual["role_requirements"][0]["gate"] == "litmus_pre_commit"
    assert dual["role_requirements"][1]["gate"] == "pre_pr_lead_review"
    assert dual["role_requirements"][2]["gate"] == "pre_pr_backstop_review"
    assert set(dual["configured_relay_roles"]) == set(dual["required_roles"])
    for role, entry in dual["configured_relay_roles"].items():
        assert entry["role"] == role
        assert entry["configured"] is True
        assert entry["selected_agent"] == "codex"
        assert entry["source"] == "relay_config"
        assert entry["dispatch_allowed"] is False
        assert entry["mutation_allowed"] is False
        assert entry["finalization_allowed"] is False
        assert entry["not_busdriver_native_claude_runtime"] is True
    assert_no_finalization_authority(dual["authority"])
    assert data["handoff_envelope"]["evidence"]["dual_review_readiness"] == dual
    assert data["handoff_envelope"]["dual_review_readiness"] == dual
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])
    assert_no_positive_finalization_authority(data)


def test_readiness_handoff_includes_fresh_read_only_pre_pr_dual_review_evidence(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(
        tmp_path / "pre-pr-fresh-litmus-status.json",
        repo=repo,
        status="pr_review_fresh",
        pr_codex_lead_fresh_for_branch_diff=True,
        pr_backstop_verdict_fresh_for_branch_diff=True,
        pr_review_passed_fresh_for_branch_diff=True,
    )
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    evidence = data["pre_pr_dual_review_evidence"]
    assert evidence["schema"] == "hermes-busdriver-pre-pr-dual-review-evidence/v0"
    assert evidence["version"] == 0
    assert evidence["read_only"] is True
    assert evidence["advisory_only"] is True
    assert evidence["source"] == "delivery_status.litmus_status.summary"
    assert evidence["status"] == "fresh_read_only"
    assert evidence["ok"] is True
    assert evidence["litmus_decision_status"] == "pr_review_fresh"
    assert evidence["freshness"] == {
        "litmus_passed_fresh_for_head": False,
        "pr_codex_lead_fresh_for_branch_diff": True,
        "pr_backstop_verdict_fresh_for_branch_diff": True,
        "pr_review_passed_fresh_for_branch_diff": True,
    }
    assert "path" not in json.dumps(evidence)
    assert data["handoff_envelope"]["pre_pr_dual_review_evidence"] == evidence
    assert data["handoff_envelope"]["evidence"]["pre_pr_dual_review_evidence"] == evidence
    assert_no_finalization_authority(evidence)
    assert_no_positive_finalization_authority(data)


@pytest.mark.parametrize(
    "litmus_kwargs, expected_status",
    [
        ({"status": "commit_litmus_fresh", "litmus_fresh_for_head": True}, "commit_litmus_only"),
        ({"status": "stale_or_missing"}, "stale_or_missing"),
        ({"status": "blocked"}, "blocked"),
        (
            {
                "status": "pr_review_fresh",
                "pr_codex_lead_fresh_for_branch_diff": True,
                "pr_backstop_verdict_fresh_for_branch_diff": True,
                "pr_review_passed_fresh_for_branch_diff": False,
            },
            "stale_or_missing",
        ),
    ],
)
def test_readiness_pre_pr_dual_review_evidence_classifies_non_fresh_summaries(
    tmp_path: Path,
    litmus_kwargs: dict[str, Any],
    expected_status: str,
):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(tmp_path / "litmus-status.json", repo=repo, **litmus_kwargs)
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    evidence = data["pre_pr_dual_review_evidence"]
    assert evidence["status"] == expected_status
    assert evidence["ok"] is False
    assert evidence["read_only"] is True
    assert evidence["programmatic_execution_allowed"] is False
    assert evidence["dispatch_allowed"] is False
    assert data["handoff_envelope"]["evidence"]["pre_pr_dual_review_evidence"] == evidence
    assert_no_finalization_authority(evidence)
    assert_no_positive_finalization_authority(data)


def test_readiness_pre_pr_dual_review_evidence_fails_closed_on_unsafe_summary(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(
        tmp_path / "unsafe-litmus-status.json",
        repo=repo,
        status="pr_review_fresh",
        authority_true_key="finalization_allowed",
        pr_codex_lead_fresh_for_branch_diff=True,
        pr_backstop_verdict_fresh_for_branch_diff=True,
        pr_review_passed_fresh_for_branch_diff=True,
    )
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    assert data["delivery_status"]["litmus_status"]["reason"] == "litmus_status_authority_flags_unsafe"
    evidence = data["pre_pr_dual_review_evidence"]
    assert evidence["status"] == "unavailable"
    assert evidence["ok"] is False
    assert evidence["reason"] == "litmus_summary_unsafe_or_malformed"
    assert_no_finalization_authority(evidence)
    assert_no_positive_finalization_authority(data)


@pytest.mark.parametrize(
    "payload_update",
    [
        lambda payload: payload.update({"commit_allowed": True}),
        lambda payload: payload["markers"]["pr_codex_lead"].update({"merge_allowed": True}),
        lambda payload: payload["markers"]["pr_backstop_verdict"].update({"authority": {"pr_allowed": True}}),
        lambda payload: payload["markers"]["pr_review_passed"].update({"nested": [{"authority": {"push_allowed": True}}]}),
    ],
)
def test_readiness_pre_pr_dual_review_evidence_fails_closed_on_nested_authority(
    tmp_path: Path,
    payload_update,
):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(
        tmp_path / "nested-authority-litmus-status.json",
        repo=repo,
        status="pr_review_fresh",
        pr_codex_lead_fresh_for_branch_diff=True,
        pr_backstop_verdict_fresh_for_branch_diff=True,
        pr_review_passed_fresh_for_branch_diff=True,
    )
    payload = json.loads(litmus.read_text())
    payload_update(payload)
    litmus.write_text(json.dumps(payload))
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    assert data["delivery_status"]["litmus_status"]["reason"] == "litmus_status_authority_flags_unsafe"
    assert data["delivery_status"]["litmus_status"]["summary"]["authority_safe"] is False
    evidence = data["pre_pr_dual_review_evidence"]
    assert evidence["status"] == "unavailable"
    assert evidence["ok"] is False
    assert evidence["reason"] == "litmus_summary_unsafe_or_malformed"
    assert_no_finalization_authority(evidence)
    assert_no_positive_finalization_authority(data)


def test_readiness_pre_pr_evidence_rejects_fresh_litmus_with_recursive_authority(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(
        tmp_path / "fresh-recursive-authority-litmus-status.json",
        repo=repo,
        status="pr_review_fresh",
        pr_codex_lead_fresh_for_branch_diff=True,
        pr_backstop_verdict_fresh_for_branch_diff=True,
        pr_review_passed_fresh_for_branch_diff=True,
    )
    payload = json.loads(litmus.read_text())
    payload["markers"]["pr_backstop_verdict"]["authority"] = {"pr_allowed": True}
    litmus.write_text(json.dumps(payload))
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    assert data["delivery_status"]["litmus_status"]["reason"] == "litmus_status_authority_flags_unsafe"
    assert data["delivery_status"]["litmus_status"]["summary"]["authority_safe"] is False
    evidence = data["pre_pr_dual_review_evidence"]
    assert evidence["status"] == "unavailable"
    assert evidence["status"] != "fresh_read_only"
    assert evidence["ok"] is False
    assert evidence["reason"] == "litmus_summary_unsafe_or_malformed"
    assert_no_finalization_authority(evidence)
    assert_no_positive_finalization_authority(data)


def test_readiness_handoff_propagates_litmus_status_evidence(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(tmp_path / "litmus-status.json", repo=repo)
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    # r24: fixture-sourced evidence blocks handoff, but the litmus summary still propagates
    # verbatim into the envelope — now WITH the provenance the summary alone dropped.
    assert data["readiness"]["status"] == "blocked"
    assert "litmus_pre_pr_stale_or_missing" in data["readiness"]["warnings"]
    litmus_summary = data["delivery_status"]["litmus_status"]["summary"]
    handoff_litmus = data["handoff_envelope"]["evidence"]["litmus_status"]
    assert handoff_litmus == litmus_summary
    assert data["handoff_envelope"]["evidence"]["litmus_status_source"] == "fixture"
    assert handoff_litmus["decision"]["status"] == "stale_or_missing"
    assert handoff_litmus["decision"]["finalization_allowed"] is False
    assert handoff_litmus["decision"]["marker_write_allowed"] is False
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_readiness_accepts_and_forwards_compatible_drift_baseline(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    (repo / "work.txt").write_text("draft\n")
    baseline = drift_baseline_fixture(tmp_path / "baseline.json", plugin)

    cp, data = invoke(repo, plugin, user_config, "--drift-baseline", str(baseline))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["ready"] is True
    assert data["readiness"]["status"] == "ready_for_commit_or_pr_handoff"
    delivery_drift = data["delivery_status"]["phase0_status"]["busdriver_drift"]
    handoff_drift = data["handoff_envelope"]["evidence"]["busdriver_drift"]
    assert delivery_drift["status"] == "compatible"
    assert delivery_drift["finalization_compatible"] is True
    assert handoff_drift["finalization_compatible"] is True
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_readiness_blocks_when_drift_baseline_is_drifted(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    (repo / "work.txt").write_text("draft\n")
    baseline = drift_baseline_fixture(tmp_path / "baseline.json", plugin)
    (plugin / "package.json").write_text('{"name":"busdriver","version":"9.99.0"}\n')

    cp, data = invoke(repo, plugin, user_config, "--drift-baseline", str(baseline))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    drift = data["handoff_envelope"]["evidence"]["busdriver_drift"]
    assert drift["status"] == "drifted"
    assert drift["finalization_compatible"] is False
    assert "busdriver_drift_incompatible" in data["readiness"]["blockers"]
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


@pytest.mark.parametrize("baseline_name, baseline_content, expected_status", [
    ("invalid-baseline.json", "{not-json\n", "baseline_invalid"),
    ("missing-baseline.json", None, "baseline_missing"),
])
def test_readiness_blocks_when_drift_baseline_is_invalid_or_missing(tmp_path: Path, baseline_name: str, baseline_content: str | None, expected_status: str):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    (repo / "work.txt").write_text("draft\n")
    baseline = tmp_path / baseline_name
    if baseline_content is not None:
        baseline.write_text(baseline_content)

    cp, data = invoke(repo, plugin, user_config, "--drift-baseline", str(baseline))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    drift = data["handoff_envelope"]["evidence"]["busdriver_drift"]
    assert drift["status"] == expected_status
    assert drift["finalization_compatible"] is False
    assert "busdriver_drift_incompatible" in data["readiness"]["blockers"]
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


@pytest.mark.parametrize("identity_error", ["root", "branch", "head", "missing_branch", "missing_head"])
def test_readiness_handoff_blocks_on_litmus_status_repo_identity_mismatch(tmp_path: Path, identity_error: str):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(tmp_path / "wrong-repo-litmus-status.json", repo=repo, status="commit_litmus_fresh")
    payload = json.loads(litmus.read_text())
    if identity_error == "root":
        payload["repo"]["root"] = str(tmp_path / "other-repo")
    elif identity_error == "branch":
        payload["repo"]["branch"] = "other-branch"
    elif identity_error == "head":
        payload["repo"]["head"] = "deadbeef"
    elif identity_error == "missing_branch":
        payload["repo"].pop("branch")
    elif identity_error == "missing_head":
        payload["repo"].pop("head")
    litmus.write_text(json.dumps(payload))
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert data["delivery_status"]["litmus_status"]["reason"] == "litmus_status_schema_invalid"
    assert "litmus_status_schema_invalid" in data["readiness"]["blockers"]
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_readiness_handoff_blocks_when_litmus_status_is_unavailable(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    missing_litmus = tmp_path / "missing-litmus-status"
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-script", str(missing_litmus))

    assert cp.returncode == 0, cp.stderr
    assert data["delivery_status"]["litmus_status"]["available"] is False
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert "litmus_status_unavailable" in data["readiness"]["blockers"]
    assert "litmus_status_unavailable" not in data["readiness"]["warnings"]
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_readiness_handoff_blocks_when_litmus_status_subprocess_failed(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(tmp_path / "litmus-status.json", repo=repo, status="commit_litmus_fresh")
    script = tmp_path / "failing-litmus-status.py"
    script.write_text(
        "import pathlib, sys\n"
        f"print(pathlib.Path({str(litmus)!r}).read_text())\n"
        "sys.exit(2)\n"
    )
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-script", str(script))

    assert cp.returncode == 0, cp.stderr
    assert data["delivery_status"]["litmus_status"]["ok"] is False
    assert data["delivery_status"]["litmus_status"]["reason"] == "litmus_status_subprocess_failed"
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert "litmus_status_subprocess_failed" in data["readiness"]["blockers"]
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_readiness_handoff_blocks_when_litmus_status_is_blocked(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(tmp_path / "blocked-litmus-status.json", repo=repo, status="blocked")
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert "litmus_status_not_fresh" in data["readiness"]["blockers"]
    assert "litmus_status_not_fresh" not in data["readiness"]["warnings"]
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert data["handoff_envelope"]["readiness_status"] == "blocked"
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_readiness_handoff_blocks_when_litmus_status_ok_false(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(tmp_path / "not-ok-litmus-status.json", repo=repo, status="commit_litmus_fresh", ok=False)
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert "litmus_status_not_fresh" in data["readiness"]["blockers"]
    assert "litmus_status_not_fresh" not in data["readiness"]["warnings"]
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert data["handoff_envelope"]["readiness_status"] == "blocked"
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_readiness_handoff_blocks_when_litmus_status_ok_is_non_boolean(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(tmp_path / "malformed-ok-litmus-status.json", repo=repo, status="commit_litmus_fresh", ok="false")
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert data["delivery_status"]["litmus_status"]["ok"] is False
    assert data["delivery_status"]["litmus_status"]["reason"] == "litmus_status_schema_invalid"
    assert "litmus_status_schema_invalid" in data["readiness"]["blockers"]
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert data["handoff_envelope"]["readiness_status"] == "blocked"
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_readiness_handoff_blocks_when_litmus_decision_status_is_unrecognized(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(tmp_path / "unknown-status-litmus-status.json", repo=repo, status="surprise_fresh", ok=True)
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert data["delivery_status"]["litmus_status"]["ok"] is False
    assert data["delivery_status"]["litmus_status"]["reason"] == "litmus_status_schema_invalid"
    assert data["handoff_envelope"]["evidence"]["litmus_status"]["decision"]["status"] == "surprise_fresh"
    assert "litmus_status_schema_invalid" in data["readiness"]["blockers"]
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert data["handoff_envelope"]["readiness_status"] == "blocked"
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


@pytest.mark.parametrize(
    "authority_key",
    [
        "finalization_allowed",
        "commit_allowed",
        "push_allowed",
        "pr_allowed",
        "merge_allowed",
        "deploy_allowed",
        "release_allowed",
        "publish_allowed",
        "marker_write_allowed",
    ],
)
def test_readiness_blocks_when_litmus_status_has_finalization_authority(tmp_path: Path, authority_key: str):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(tmp_path / f"unsafe-{authority_key}-litmus-status.json", repo=repo, authority_true_key=authority_key)
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert "litmus_status_authority_flags_unsafe" in data["readiness"]["blockers"]
    assert data["delivery_status"]["litmus_status"]["reason"] == "litmus_status_authority_flags_unsafe"
    assert data["handoff_envelope"]["evidence"]["litmus_status"]["decision"][authority_key] is False
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_readiness_handoff_litmus_status_evidence_sanitizes_untrusted_fields(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    sentinel = "ghp_" + "E" * 36
    litmus = litmus_status_fixture(tmp_path / "malicious-litmus-status.json", repo=repo, malicious_sentinel=sentinel)
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    payload = json.dumps(data)
    handoff_litmus = data["handoff_envelope"]["evidence"]["litmus_status"]
    litmus_marker = handoff_litmus["markers"]["litmus_passed"]
    assert cp.returncode == 0, cp.stderr
    assert sentinel not in payload
    assert set(handoff_litmus["repo"]) == {"root", "branch", "head", "head_timestamp", "base_ref", "branch_diff_hash"}
    assert set(handoff_litmus["state_dir"]) == {"path", "exists", "is_symlink", "has_symlink_component"}
    assert set(handoff_litmus["markers"]) == {"litmus_passed", "pr_codex_lead", "pr_backstop_verdict", "pr_review_passed"}
    assert "unknown_secret" not in litmus_marker
    assert "[REDACTED]" in handoff_litmus["repo"]["root"]
    assert "[REDACTED]" in handoff_litmus["state_dir"]["path"]
    assert "[REDACTED]" in litmus_marker["path"]
    assert litmus_marker["read_error"] == "password=[REDACTED]"
    assert litmus_marker["stat_error"] == "stat token=[REDACTED]"
    assert handoff_litmus["decision"]["warnings"] == []
    assert handoff_litmus["decision"]["blockers"] == []
    assert set(handoff_litmus["decision"]) == {
        "status",
        "warnings",
        "blockers",
        "finalization_allowed",
        "commit_allowed",
        "push_allowed",
        "pr_allowed",
        "merge_allowed",
        "deploy_allowed",
        "release_allowed",
        "publish_allowed",
        "marker_write_allowed",
        "not_busdriver_native_claude_runtime",
    }
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_readiness_handoff_litmus_status_evidence_normalizes_untrusted_top_level_fields(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    sentinel = "ghp_" + "H" * 36
    litmus = litmus_status_fixture(tmp_path / "malicious-top-level-litmus-status.json", repo=repo)
    payload = json.loads(litmus.read_text())
    payload["schema"] = f"schema token={sentinel}"
    payload["read_only"] = {"secret": sentinel}
    payload["ok"] = f"ok token={sentinel}"
    payload["decision"]["not_busdriver_native_claude_runtime"] = f"token={sentinel}"
    litmus.write_text(json.dumps(payload))
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    payload_text = json.dumps(data)
    handoff_litmus = data["handoff_envelope"]["evidence"]["litmus_status"]
    assert cp.returncode == 0, cp.stderr
    assert sentinel not in payload_text
    assert data["delivery_status"]["litmus_status"]["ok"] is False
    assert data["delivery_status"]["litmus_status"]["reason"] == "litmus_status_schema_invalid"
    assert handoff_litmus["schema"] is None
    assert handoff_litmus["read_only"] is False
    assert handoff_litmus["ok"] is False
    assert handoff_litmus["decision"]["not_busdriver_native_claude_runtime"] is False
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


@pytest.mark.parametrize(
    ("mutate_payload", "expected_reason"),
    [
        (lambda _payload: ["not", "an", "object"], "litmus_status_malformed"),
        (lambda payload: {**payload, "read_only": False}, "litmus_status_read_only_unsafe"),
        (lambda payload: {**payload, "ok": "true"}, "litmus_status_schema_invalid"),
    ],
    ids=["non_object", "read_only_false", "ok_non_boolean"],
)
def test_readiness_handoff_litmus_status_malformed_or_invalid_top_level_fields_fail_closed(
    tmp_path: Path,
    mutate_payload,
    expected_reason: str,
):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = litmus_status_fixture(tmp_path / "litmus-status.json", repo=repo)
    payload = json.loads(litmus.read_text())
    litmus.write_text(json.dumps(mutate_payload(payload)))
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    assert data["delivery_status"]["litmus_status"]["ok"] is False
    assert data["delivery_status"]["litmus_status"]["reason"] == expected_reason
    assert data["readiness"]["status"] == "blocked"
    assert expected_reason in data["readiness"]["blockers"]
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_readiness_handoff_litmus_status_invalid_json_fails_closed(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    litmus = tmp_path / "litmus-status.json"
    litmus.write_text("{not-json\n")
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--litmus-status-result-file", str(litmus))

    assert cp.returncode == 0, cp.stderr
    assert data["delivery_status"]["litmus_status"]["ok"] is False
    assert data["delivery_status"]["litmus_status"]["reason"] == "litmus_status_malformed"
    assert data["handoff_envelope"]["evidence"]["litmus_status"] is None
    assert data["readiness"]["status"] == "blocked"
    assert "litmus_status_malformed" in data["readiness"]["blockers"]
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


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


def test_readiness_handoff_includes_non_dispatchable_relay_role_warning(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    cfg = relay_config(tmp_path / "relay-config.json", [])
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
    handoff = data["handoff_envelope"]
    handoff_role = handoff["evidence"]["relay_role_resolution"]
    assert handoff_role["ok"] is False
    assert handoff_role["result"]["dispatch_allowed"] is False
    assert "relay_role_not_dispatchable" in handoff["evidence"]["delivery_decision"]["warnings"]
    assert data["readiness"]["ready"] is True
    assert data["readiness"]["status"] == "ready_for_commit_or_pr_handoff"
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_clean_pr_grind_fixture_generates_merge_handoff_but_no_merge_authority(tmp_path: Path):
    repo = bind_github_origin(init_repo(tmp_path / "repo"))
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    pr_result = tmp_path / "pr-clean.json"
    pr_result.write_text(json.dumps(pr_grind_payload()))

    cp, data = invoke(repo, plugin, user_config, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert cp.returncode == 0, cp.stderr
    # r24: a --pr-grind-result-file is a test diagnostic. However well it validates, it is
    # content its own author wrote, so it must never reach ready_for_merge_handoff. The PR
    # summary stays readable as a diagnostic and provenance is stated in the envelope.
    assert data["readiness"]["status"] == "blocked"
    assert "fixture_evidence_not_authoritative" in data["readiness"]["blockers"]
    assert data["readiness"]["target"] == "merge"
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert data["handoff_envelope"]["pr"]["number"] == "7"
    assert data["handoff_envelope"]["pr"]["status"] == "clean"
    assert data["handoff_envelope"]["evidence"]["pr_grind_source"] == "fixture"
    assert data["handoff_envelope"]["evidence"]["fixture_sourced_evidence"] is True
    assert data["decision"] == {
        "status": "blocked",
        "reason": "read_only_finalization_readiness",
        **{key: False for key in ["finalization_allowed", "commit_allowed", "push_allowed", "pr_allowed", "merge_allowed", "deploy_allowed", "release_allowed", "publish_allowed", "marker_write_allowed"]},
    }
    assert_no_finalization_authority(data["handoff_envelope"]["authority"])
    assert not (repo / ".claude").exists()
    assert not (repo / ".opencode").exists()


def test_non_clean_pr_fixture_reports_delivery_blocker(tmp_path: Path):
    repo = bind_github_origin(init_repo(tmp_path / "repo"))
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    pr_result = tmp_path / "pr-wait.json"
    pr_result.write_text(json.dumps(pr_grind_payload(status="wait", checks={"failed": 0, "pending": 1})))

    cp, data = invoke(repo, plugin, user_config, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert "pr_checks_or_reviewer_bots_pending" in data["readiness"]["blockers"]
    assert_no_finalization_authority(data["readiness"])


def test_forged_pr_grind_fixture_cannot_reach_merge_handoff(tmp_path: Path):
    # r23: readiness inherits the delivery decision, so an unvalidated clean claim would be
    # laundered all the way into `ready_for_merge_handoff` — the last state before a human or a
    # finalizer is told the PR is good to merge.
    repo = bind_github_origin(init_repo(tmp_path / "repo-forged-merge-handoff"))
    plugin = fake_busdriver(tmp_path / "busdriver-forged-merge-handoff")
    user_config = fake_user_config(tmp_path / "busdriver-forged.json")
    pr_result = tmp_path / "pr-forged.json"
    pr_result.write_text(json.dumps({"status": "clean", "clean": True}))

    cp, data = invoke(repo, plugin, user_config, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["status"] == "blocked"
    assert data["readiness"]["status"] != "ready_for_merge_handoff"
    assert data["readiness"]["ready"] is False
    assert "pr_grind_result_invalid" in data["readiness"]["blockers"]
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_stale_finalization_lock_blocks_handoff_readiness(tmp_path: Path):
    # r23: `acquire` refuses a stale lock until manual recovery, so readiness over one promises a
    # handoff that will fail closed with `finalization_lock_not_acquired`.
    repo = init_repo(tmp_path / "repo-stale-lock-readiness")
    plugin = fake_busdriver(tmp_path / "busdriver-stale-lock-readiness")
    user_config = fake_user_config(tmp_path / "busdriver-stale-lock.json")
    relay_state = tmp_path / "relay-state-stale-lock"
    assert run([
        sys.executable, str(LOCK), "acquire", "--repo", str(repo),
        "--state-dir", str(relay_state), "--operation", "finalization", "--ttl-seconds", "1",
    ]).returncode == 0
    time.sleep(1.5)
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--relay-state-dir", str(relay_state))

    assert cp.returncode == 0, cp.stderr
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] == "blocked"
    assert "relay_finalization_lock_stale_manual_recovery" in data["readiness"]["blockers"]
    assert data["delivery_status"]["finalization_lock"]["stale_for_repo_count"] == 1
    assert data["delivery_status"]["finalization_lock"]["active_for_repo_count"] == 0
    assert_no_finalization_authority(data["readiness"])
    assert_no_finalization_authority(data["decision"])


def test_pr_supplied_without_blockers_gets_pr_not_clean_next_action():
    mod = __import__("runpy").run_path(str(READINESS))
    args = __import__("types").SimpleNamespace(pr="7", target="auto")
    delivery = {
        "schema": "hermes-busdriver-delivery-status/v0",
        "read_only": True,
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

    contract_status = {
        "schema": "hermes-busdriver-finalization-contract-status/v0",
        "ok": True,
        "read_only": True,
    }

    agent_balance_plan = {
        "schema": "hermes-busdriver-agent-balance-plan/v0",
        "ok": True,
        "read_only": True,
    }

    data = mod["readiness"](args, delivery, phase0, contract_status, agent_balance_plan)

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


def test_default_delivery_status_timeout_covers_forwarded_pr_grind_and_litmus_budgets(monkeypatch):
    mod = __import__("runpy").run_path(str(READINESS))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(READINESS),
            "--repo",
            "/tmp/repo",
            "--plugin-root",
            "/tmp/plugin",
            "--user-config",
            "/tmp/busdriver.json",
            "--pr",
            "7",
            "--state-dir",
            ".opencode",
        ],
    )
    args = mod["parse_args"]()
    captured = {"cmd": [], "timeout": 0}

    def fake_run_json(cmd: list[str], timeout: int, *, credentials: bool = False) -> tuple[dict, int]:
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        return {"ok": True}, 0

    mod["load_delivery_status"].__globals__["run_json"] = fake_run_json

    mod["load_delivery_status"](args, Path("/private/copy/hermes-busdriver-delivery-status"))

    assert "--pr-grind-timeout" in captured["cmd"]
    assert "--litmus-status-timeout" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--busdriver-state-dir-name") + 1] == ".opencode"
    assert captured["timeout"] == args.pr_grind_timeout + args.litmus_status_timeout + 30


def test_delivery_status_timeout_covers_and_forwards_nested_phase0_status_budget_for_drift_baseline(monkeypatch):
    mod = __import__("runpy").run_path(str(READINESS))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(READINESS),
            "--repo",
            "/tmp/repo",
            "--plugin-root",
            "/tmp/plugin",
            "--user-config",
            "/tmp/busdriver.json",
            "--drift-baseline",
            "/tmp/baseline.json",
            "--phase0-status-timeout",
            "17",
        ],
    )
    args = mod["parse_args"]()
    captured = {"cmd": [], "timeout": 0}

    def fake_run_json(cmd: list[str], timeout: int, *, credentials: bool = False) -> tuple[dict, int]:
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        return {"ok": True}, 0

    mod["load_delivery_status"].__globals__["run_json"] = fake_run_json

    mod["load_delivery_status"](args, Path("/private/copy/hermes-busdriver-delivery-status"))

    assert captured["cmd"][captured["cmd"].index("--phase0-status-timeout") + 1] == "17"
    assert captured["timeout"] == args.pr_grind_timeout + args.litmus_status_timeout + args.phase0_status_timeout + 30


@pytest.mark.parametrize("extra_args, expected_timeout", [
    ([], "90"),
    (["--relay-role-timeout", "17"], "17"),
])
def test_delivery_status_timeout_covers_and_forwards_nested_relay_role_budget(monkeypatch, extra_args: list[str], expected_timeout: str):
    mod = __import__("runpy").run_path(str(READINESS))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(READINESS),
            "--repo",
            "/tmp/repo",
            "--plugin-root",
            "/tmp/plugin",
            "--user-config",
            "/tmp/busdriver.json",
            "--relay-role",
            "relay.pr.backstop",
            *extra_args,
        ],
    )
    args = mod["parse_args"]()
    captured = {"cmd": [], "timeout": 0}

    def fake_run_json(cmd: list[str], timeout: int, *, credentials: bool = False) -> tuple[dict, int]:
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        return {"ok": True}, 0

    mod["load_delivery_status"].__globals__["run_json"] = fake_run_json

    mod["load_delivery_status"](args, Path("/private/copy/hermes-busdriver-delivery-status"))

    assert captured["cmd"][captured["cmd"].index("--relay-role-timeout") + 1] == expected_timeout
    assert captured["timeout"] == args.pr_grind_timeout + args.litmus_status_timeout + args.relay_role_timeout + 30


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


def test_phase0_status_child_argv_disables_the_external_resolver(tmp_path):
    # r20 defense in depth: readiness reads Phase-0 status; it never needs resolver bytes run.
    import runpy

    mod = runpy.run_path(str(READINESS))
    captured: dict[str, Any] = {}

    def fake_run_json(cmd: list[str], timeout: int, *, credentials: bool = False) -> tuple[dict, int]:
        captured["cmd"] = list(cmd)
        return {}, 0

    mod["load_phase0_status"].__globals__["run_json"] = fake_run_json
    args = __import__("argparse").Namespace(
        repo=str(tmp_path), state_dir=".claude", relay_state_dir=None, plugin_root=None,
        user_config=None, relay_config=None, drift_baseline=None, phase0_status_timeout=60,
    )

    private_copy = tmp_path / "private" / "hermes-busdriver-status"
    mod["load_phase0_status"](args, private_copy)

    # The script is now a retained private copy of the authenticated bytes rather than the source
    # path (v16-r26A item 1), so assert the identity and the flags, not the source pathname.
    assert captured["cmd"][0] == "/usr/bin/python3"
    assert captured["cmd"][1] == "-I"
    assert Path(captured["cmd"][2]).name == PHASE0_STATUS.name
    assert Path(captured["cmd"][2]) != PHASE0_STATUS
    assert captured["cmd"][3:] == [
        "--repo", str(tmp_path), "--state-dir", ".claude",
        "--operation", "repo-mutation", "--no-external-resolver",
    ]


# --- v16-r21: ambient execution containment ---

def test_finalization_readiness_child_env_is_allowlisted_and_drops_loader_injection(monkeypatch):
    import runpy

    ns = runpy.run_path(str(READINESS))
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

    env = ns["child_env"]()

    assert env["PATH"] == ns["CONTAINED_PATH"]
    for key in ("PYTHONPATH", "PYTHONHOME", "BASH_ENV", "ENV", "ZDOTDIR", "LD_PRELOAD", "DYLD_INSERT_LIBRARIES"):
        assert key not in env
    assert not [key for key in env if key.startswith("GIT_")]


def test_finalization_readiness_python_children_run_isolated(monkeypatch, tmp_path):
    import runpy

    ns = runpy.run_path(str(READINESS))
    captured: list[list[str]] = []

    def fake_run_json(cmd, timeout, *, credentials=False):
        captured.append(list(cmd))
        return {"ok": False, "error": "stub"}, 1

    monkeypatch.setitem(ns["main"].__globals__, "run_json", fake_run_json)
    monkeypatch.setattr(sys, "argv", ["hermes-busdriver-finalization-readiness", "--repo", str(tmp_path)])
    try:
        ns["main"]()
    except SystemExit:
        pass

    assert captured, "no child commands were dispatched"
    for cmd in captured:
        assert cmd[0] == "/usr/bin/python3", f"child not launched via frozen production Python: {cmd}"
        assert cmd[1] == "-I", f"child not isolated with -I: {cmd}"


def test_finalization_readiness_run_json_returns_rc_127_on_launch_oserror(tmp_path):
    import runpy

    ns = runpy.run_path(str(READINESS))
    not_a_program = tmp_path / "file.txt"
    not_a_program.write_text("x\n")

    payload, code = ns["run_json"]([str(not_a_program)], timeout=10)

    assert code == 127
    assert payload["ok"] is False


def test_handoff_envelope_never_carries_a_release_token(tmp_path: Path):
    """r24 H1: the envelope is designed to be handed to another actor as evidence.

    Publishing the holder's release capability alongside that evidence hands every downstream
    reader — and every log and transcript the envelope lands in — the ability to release it.
    """
    repo = init_repo(tmp_path / "repo-token")
    plugin = fake_busdriver(tmp_path / "busdriver-token")
    user_config = fake_user_config(tmp_path / "busdriver-token.json")
    relay_state = tmp_path / "relay-state-token"
    acquired = json.loads(run([
        sys.executable, str(LOCK), "acquire", "--repo", str(repo),
        "--state-dir", str(relay_state), "--operation", "finalization",
    ]).stdout)
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--relay-state-dir", str(relay_state))

    assert acquired["token"] not in cp.stdout
    lock_evidence = data["handoff_envelope"]["evidence"]["finalization_lock"]
    assert lock_evidence["active_for_repo_count"] == 1
    assert "token" not in lock_evidence["active_for_repo"][0]


# --- v16-r25 B5: readiness forwards GitHub tokens to children, so its tails must redact ---


def test_readiness_tail_redacts_and_bounds():
    ns = load_readiness_module()
    secret = "ghp_" + "r" * 36

    out = ns["tail"]("child failed: " + secret + " " + "x" * 9000)

    assert secret not in out
    assert len(out) <= 4000


@pytest.mark.parametrize("prefix_len", [0, 3990, 3999, 4000, 4200])
def test_readiness_secrets_redacted_across_truncation_boundary(prefix_len: int):
    ns = load_readiness_module()
    secret = "ghp_" + "s" * 36

    out = ns["tail"]("p" * prefix_len + " " + secret + " " + "z" * 50)

    assert "ghp_" not in out


def test_readiness_tail_redacts_credential_env_values(monkeypatch):
    ns = load_readiness_module()
    monkeypatch.setenv("GH_ENTERPRISE_TOKEN", "opaque-readiness-credential")

    assert "opaque-readiness-credential" not in ns["tail"]("boom: opaque-readiness-credential")


def test_readiness_child_failure_envelope_redacts_stderr(tmp_path: Path, monkeypatch):
    """run_json copies child stderr into the envelope; r24 bounded it but never redacted."""
    ns = load_readiness_module()
    secret = "ghp_" + "p" * 36
    script = tmp_path / "child.py"
    script.write_text(
        "import sys\n"
        f"sys.stderr.write('auth failed {secret}')\n"
        "print('{}')\n"
        "sys.exit(3)\n"
    )

    data, code = ns["run_json"]([sys.executable, str(script)], 30)

    assert code == 3
    assert secret not in json.dumps(data)


# --- v16-r26A item 1: helper authentication + balance-plan fixture provenance ---


VALID_BALANCE_PLAN_SOURCE = (
    "#!/usr/bin/env python3\n"
    "import json, os\n"
    "print(json.dumps({\n"
    "    'schema': 'hermes-busdriver-agent-balance-plan/v0',\n"
    "    'ok': True,\n"
    "    'read_only': True,\n"
    "    'execution': {'subprocess_dispatch_called': False, 'repo_mutations_performed': False},\n"
    "    'saw_token': os.environ.get('GH_TOKEN'),\n"
    "}))\n"
)


def _custom_plan(tmp_path: Path, source: str = VALID_BALANCE_PLAN_SOURCE) -> Path:
    plan = tmp_path / "custom-agent-balance-plan"
    plan.write_text(source)
    plan.chmod(0o755)
    return plan


def test_forged_valid_balance_plan_cannot_clear_blockers_or_reach_handoff(tmp_path: Path):
    """A caller-named script that merely PRINTS the right shape is provenance-free.

    r25 accepted it as authoritative: structural validation proves shape, never origin, so a
    forged-but-valid plan cleared `agent_balance_plan_unavailable` and let readiness reach a
    ready handoff state. This is the same demotion delivery-status already applies to a
    caller-named --pr-grind-check-script.
    """
    repo = init_uncommitted_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config, "--agent-balance-plan-script", str(_custom_plan(tmp_path)))

    plan = data["agent_balance_plan"]
    assert plan["source"] == "fixture"
    assert plan["authoritative"] is False
    assert "agent_balance_plan_fixture_not_authoritative" in data["readiness"]["blockers"]
    assert data["readiness"]["ready"] is False
    assert data["readiness"]["status"] != "ready_for_commit_or_pr_handoff"
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert_no_positive_finalization_authority(data)


def test_custom_balance_plan_script_receives_no_github_credentials(tmp_path: Path):
    """child_env() forwarded GH_TOKEN to an arbitrary caller-named executable."""
    repo = init_uncommitted_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    (repo / "work.txt").write_text("draft\n")

    env = dict(os.environ)
    env["GH_TOKEN"] = "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    cp = run(
        [
            sys.executable, str(READINESS_HARNESS), "--repo", str(repo), "--plugin-root", str(plugin),
            "--user-config", str(user_config),
            "--agent-balance-plan-script", str(_custom_plan(tmp_path)),
        ],
        env_override=env,
    )
    data = json.loads(cp.stdout)

    assert data["agent_balance_plan"].get("saw_token") in (None, "[REDACTED]"), "GH_TOKEN reached a custom script"
    assert "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" not in cp.stdout


def test_custom_balance_plan_successful_json_is_redacted(tmp_path: Path):
    """r25 redacted only failure tails; a successful custom payload was emitted verbatim."""
    repo = init_uncommitted_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    (repo / "work.txt").write_text("draft\n")
    leaky = _custom_plan(tmp_path, (
        "#!/usr/bin/env python3\n"
        "import json\n"
        "print(json.dumps({\n"
        "    'schema': 'hermes-busdriver-agent-balance-plan/v0',\n"
        "    'ok': True,\n"
        "    'read_only': True,\n"
        "    'note': 'pushed via https://" + "x-access-token:" + "ghp_BBBBBBBBBBBBBBBBBBBBBBBB@github.com/o/r',\n"
        "}))\n"
    ))

    cp, data = invoke(repo, plugin, user_config, "--agent-balance-plan-script", str(leaky))

    assert "ghp_BBBBBBBBBBBBBBBBBBBBBBBB" not in cp.stdout, "custom plan JSON leaked a token"


def test_default_helpers_are_digest_authenticated(tmp_path: Path):
    import runpy

    ns = runpy.run_path(str(READINESS))

    for relative in (
        "scripts/hermes-busdriver-delivery-status",
        "scripts/hermes-busdriver-status",
        "scripts/hermes-busdriver-finalization-contract-status",
        "scripts/hermes-busdriver-agent-balance-plan",
    ):
        assert relative in ns["TRUSTED_READINESS_HELPER_DIGESTS"], f"{relative} is not pinned"


def test_default_helper_integrity_failure_fails_closed(tmp_path: Path, monkeypatch):
    import runpy

    ns = runpy.run_path(str(READINESS))
    # @contextmanager wraps the function, so its __globals__ is contextlib's; reach the original.
    globals_ = ns["authenticated_helper"].__wrapped__.__globals__
    monkeypatch.setitem(
        globals_,
        "TRUSTED_READINESS_HELPER_DIGESTS",
        {key: "0" * 64 for key in ns["TRUSTED_READINESS_HELPER_DIGESTS"]},
    )

    with pytest.raises(OSError):
        with ns["authenticated_helper"]("scripts/hermes-busdriver-agent-balance-plan"):
            pass


def test_default_balance_plan_executes_retained_bytes_not_swappable_private_path(monkeypatch, tmp_path: Path):
    """Readiness default helper execution identity is retained bytes, not its private pathname."""
    import runpy

    ns = runpy.run_path(str(READINESS))
    helper_globals = ns["authenticated_helper"].__wrapped__.__globals__
    run_globals = ns["run_json"].__globals__
    trusted_root = tmp_path / "trusted-readiness-root"
    relative = "scripts/hermes-busdriver-agent-balance-plan"
    trusted = trusted_root / relative
    trusted.parent.mkdir(parents=True)
    payload = {"schema": ns["AGENT_BALANCE_PLAN_SCHEMA"], "ok": True, "read_only": True}
    trusted.write_text("import json\nprint(json.dumps(%r))\n" % payload)
    trusted.chmod(0o500)
    attacker_ran = tmp_path / "readiness-balance-plan-attacker-ran"
    attacker = (
        "import json, pathlib\n"
        f"pathlib.Path({str(attacker_ran)!r}).write_text('pwned')\n"
        f"print(json.dumps({payload!r}))\n"
    )

    monkeypatch.setitem(helper_globals, "ROOT", trusted_root)
    monkeypatch.setitem(helper_globals, "TRUSTED_READINESS_HELPER_DIGESTS", {relative: hashlib.sha256(trusted.read_bytes()).hexdigest()})
    monkeypatch.setitem(run_globals, "trusted_executable_path", lambda name: Path(sys.executable) if name == "python3" else pytest.fail(f"unexpected trusted executable {name}"))
    original_run_bounded = run_globals["run_bounded"]

    def swap_retained_path_then_exec(cmd, *args, **kwargs):
        for value in cmd:
            candidate = Path(str(value))
            if candidate.name == "hermes-busdriver-agent-balance-plan" and candidate.exists():
                candidate.unlink()
                candidate.write_text(attacker)
                candidate.chmod(0o500)
                break
        return original_run_bounded(cmd, *args, **kwargs)

    monkeypatch.setitem(run_globals, "run_bounded", swap_retained_path_then_exec)
    args = __import__("argparse").Namespace(agent_balance_plan_script=None, agent_balance_plan_timeout=10)

    with ns["authenticated_helper"](relative) as retained:
        plan, rc = ns["load_agent_balance_plan"](args, retained)

    assert rc == 0
    assert plan["ok"] is True
    assert not attacker_ran.exists(), "readiness executed attacker-replaced default helper path"


# --- v16-r27 item 1: forwarding a caller-named helper must not forward the credentials with it ---

SENTINEL_TOKEN = "ghp_" + "s3nt1nel" * 5


def env_dump_helper(path: Path, dump: Path, stdout: str) -> Path:
    """A custom helper that records the environment it was handed, then prints a valid payload."""
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        f"open({str(dump)!r}, 'w').write(json.dumps(dict(os.environ)))\n"
        f"print({stdout!r})\n"
    )
    path.chmod(0o755)
    return path


def credential_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update({key: SENTINEL_TOKEN for key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN")})
    return env


def assert_no_credentials(dump: Path) -> None:
    assert dump.exists(), "the custom helper never ran, so the test proves nothing"
    handed = json.loads(dump.read_text())
    leaked = sorted(key for key, value in handed.items() if SENTINEL_TOKEN in value)
    assert not leaked, f"custom helper received GitHub credentials via {leaked}"


def invoke_with_credentials(repo: Path, plugin: Path, user_config: Path, *extra: str) -> dict:
    cp = run(
        [sys.executable, str(readiness_entrypoint(extra)), "--repo", str(repo), "--plugin-root", str(plugin), "--user-config", str(user_config), *extra],
        timeout=120,
        env_override=credential_env(),
    )
    return json.loads(cp.stdout)


def test_custom_balance_plan_script_receives_no_credentials(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    dump = tmp_path / "balance-env.json"
    script = env_dump_helper(
        tmp_path / "balance",
        dump,
        json.dumps({"schema": "hermes-busdriver-agent-balance-plan/v0", "ok": True, "read_only": True}),
    )

    invoke_with_credentials(
        repo, fake_busdriver(tmp_path / "busdriver"), fake_user_config(tmp_path / "busdriver.json"),
        "--agent-balance-plan-script", str(script),
    )

    assert_no_credentials(dump)


def test_forwarded_custom_pr_grind_check_script_receives_no_credentials(tmp_path: Path):
    """Readiness hands delivery-status the credentials AND the caller's `--pr-grind-check-script`.

    The boundary has to hold at the point of execution, not at the point of forwarding: r26's
    delivery-status passed its own credential-bearing environment straight to that arbitrary
    executable, so readiness leaked the operator's token through a child it never ran itself.
    """
    repo = init_repo(tmp_path / "repo")
    bind_github_origin(repo)
    dump = tmp_path / "pr-env.json"
    script = env_dump_helper(tmp_path / "checker", dump, json.dumps(pr_grind_payload(pr=7, status="clean")))

    invoke_with_credentials(
        repo, fake_busdriver(tmp_path / "busdriver"), fake_user_config(tmp_path / "busdriver.json"),
        "--pr", "7", "--pr-grind-check-script", str(script),
    )

    assert_no_credentials(dump)


def test_forwarded_custom_litmus_status_script_receives_no_credentials(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    dump = tmp_path / "litmus-env.json"
    script = env_dump_helper(
        tmp_path / "litmus",
        dump,
        json.dumps({"schema": "hermes-busdriver-litmus-status/v0", "ok": True, "read_only": True, "decision": {"status": "stale_or_missing"}}),
    )

    invoke_with_credentials(
        repo, fake_busdriver(tmp_path / "busdriver"), fake_user_config(tmp_path / "busdriver.json"),
        "--litmus-status-script", str(script),
    )

    assert_no_credentials(dump)


# --- v16-r28 item 2: caller-selected helpers are fixture doubles, never live children ---


def _spawn_witness(path: Path, witness: Path, payload: dict) -> Path:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        f"open({str(witness)!r}, 'w').write('spawned')\n"
        f"print(json.dumps({payload!r}))\n"
    )
    path.chmod(0o755)
    return path


READINESS_CUSTOM_HELPERS = {
    "agent_balance_plan": ("--agent-balance-plan-script",),
    "pr_grind_check": ("--pr", "7", "--pr-grind-check-script"),
    "litmus_status": ("--litmus-status-script",),
}


@pytest.mark.parametrize("helper", sorted(READINESS_CUSTOM_HELPERS))
def test_readiness_never_spawns_a_custom_helper_in_live_mode(tmp_path: Path, helper: str):
    """The gate must precede the spawn, including for the flags readiness only forwards."""
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "plugin")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    witness = tmp_path / f"{helper}-spawned"
    script = _spawn_witness(tmp_path / helper, witness, {"ok": True})
    *flags, script_flag = READINESS_CUSTOM_HELPERS[helper]

    cp = run(
        [
            sys.executable, str(READINESS), "--repo", str(repo), "--plugin-root", str(plugin),
            "--user-config", str(user_config), *flags, script_flag, str(script),
        ]
    )

    assert cp.returncode == 2, "production readiness accepted a caller-selected helper"
    error = json.loads(cp.stdout)
    assert error["ok"] is False
    assert error["error"] == "custom_helper_execution_not_permitted"
    assert not witness.exists(), "the caller's program was spawned by production readiness"


def test_production_readiness_refuses_custom_helper_under_every_flag_combination(tmp_path: Path):
    """r32 item 1: no argv reaches a caller-named executable through production readiness.

    r28's --fixture-mode is the specific bypass this closes, so it leads the list — but the point
    is that production offers no opt-in at all, not that one particular spelling is refused.
    """
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "plugin")
    user_config = fake_user_config(tmp_path / "busdriver.json")

    for index, combination in enumerate((["--fixture-mode"], ["--fixture-mode=true"], ["--pretty"], [])):
        witness = tmp_path / f"combination-{index}-spawned"
        script = _spawn_witness(tmp_path / f"probe-{index}", witness, {"ok": True})
        cp = run(
            [
                sys.executable, str(READINESS), "--repo", str(repo), "--plugin-root", str(plugin),
                "--user-config", str(user_config), *combination,
                "--agent-balance-plan-script", str(script),
            ]
        )

        assert cp.returncode == 2, f"production readiness accepted {combination}: {cp.stdout}"
        assert not witness.exists(), f"the caller's program was spawned under {combination}"


def test_production_readiness_cli_does_not_expose_fixture_mode(tmp_path: Path):
    """The flag is gone from the surface, not merely ignored — argparse must not know it."""
    cp = run([sys.executable, str(READINESS), "--help"])

    assert cp.returncode == 0, cp.stderr
    assert "--fixture-mode" not in cp.stdout


def test_readiness_harness_reaches_the_delivery_status_double(tmp_path: Path):
    """A forwarded helper flag only means something to a child that honours it.

    Production forwards nothing (it refuses the flags outright), so this proves the harness's
    child routing works end to end — the double runs, and the child envelope says it was a
    fixture run.
    """
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "plugin")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    witness = tmp_path / "forwarded-spawned"
    script = _spawn_witness(tmp_path / "litmus", witness, {"ok": True})

    cp, data = invoke(
        repo, plugin, user_config, "--litmus-status-script", str(script)
    )

    assert witness.exists(), "the forwarded double never ran"
    assert data["delivery_status"]["fixture_mode"] is True


def test_readiness_fixture_mode_is_authority_negative(tmp_path: Path):
    """Fixture mode buys the double the right to run, never the right to be believed."""
    repo = init_uncommitted_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(
        repo, plugin, user_config,
        "--agent-balance-plan-script", str(_custom_plan(tmp_path)),
    )

    assert data["fixture_mode"] is True
    assert data["agent_balance_plan"]["source"] == "fixture"
    assert data["agent_balance_plan"]["authoritative"] is False
    assert "agent_balance_plan_fixture_not_authoritative" in data["readiness"]["blockers"]
    assert data["readiness"]["ready"] is False
    assert data["handoff_envelope"]["ready_for_handoff"] is False
    assert_no_positive_finalization_authority(data)


# --- v16-r33g / r32 High 1: every child object crosses one recursive sanitizing funnel ---
#
# These are deliberately in-process (runpy + injected children) rather than end-to-end `invoke()`:
# three pinned helpers are stale on this branch, so every subprocess path fails closed at
# `readiness_runtime_integrity_failed` and could never witness a redaction either way.

OPAQUE_CAPABILITY = "opaque-enterprise-capability-value-no-shape"
SHAPED_CAPABILITY = "ghp_" + "H" * 36


def hostile_capabilities(sentinel: str) -> dict[str, Any]:
    """Every shape an unknown capability can arrive in, none of which a value pattern can see."""
    return {
        "token": sentinel,
        "access_token": sentinel,
        "secret": sentinel,
        "secrets": [sentinel, {"credential": sentinel}],
        "credentials": {"deeply": {"nested": {"capability": sentinel}}},
        "authorization": sentinel,
        "api_key": sentinel,
        "password": sentinel,
        "private_key": sentinel,
        "unknown_extra_field": {"list_of": [{"token": sentinel}, [{"secret": sentinel}]]},
    }


def echoing_child(path: Path, payload: dict[str, Any], *, exit_code: int = 0, stderr: str = "") -> Path:
    """A child that authors its own stdout — the whole reason its payload is untrusted."""
    path.write_text(
        "import json, sys\n"
        f"sys.stderr.write({stderr!r})\n"
        f"print(json.dumps({payload!r}))\n"
        f"sys.exit({exit_code})\n"
    )
    return path


def sanitizer(name: str = "sanitized_payload"):
    return load_readiness_module()[name]


# --- the funnel itself ---


@pytest.mark.parametrize("sentinel", [OPAQUE_CAPABILITY, SHAPED_CAPABILITY])
def test_sanitizer_redacts_capability_shaped_keys_at_every_depth(sentinel: str):
    """Unknown nested data must not bypass the funnel — including keys nobody enumerated."""
    out = sanitizer()(hostile_capabilities(sentinel))

    assert sentinel not in json.dumps(out)
    assert out["token"] == "[REDACTED]"
    assert out["unknown_extra_field"]["list_of"][0]["token"] == "[REDACTED]"
    assert out["credentials"] == "[REDACTED]"


def test_sanitizer_redacts_an_opaque_capability_duplicated_under_ordinary_keys():
    """The collect-before-strip requirement, and the whole reason one pass is not enough.

    An opaque credential matches no shape pattern. The KEY that names it is the only thing that
    identifies it — so stripping that key first destroys the evidence needed to find the copies
    sitting under keys that name nothing.
    """
    out = sanitizer()({
        "config": {"token": OPAQUE_CAPABILITY},
        "note": f"worker failed while using {OPAQUE_CAPABILITY}",
        "trace": ["ordinary", [{"detail": OPAQUE_CAPABILITY}]],
    })

    assert OPAQUE_CAPABILITY not in json.dumps(out)
    assert out["config"]["token"] == "[REDACTED]"
    assert out["note"] == "worker failed while using [REDACTED]"
    assert out["trace"][1][0]["detail"] == "[REDACTED]"


def test_sanitizer_keeps_facts_about_capabilities_typed():
    """`token_redacted: true` is a fact ABOUT a capability, not one: no secret fits in one bit."""
    out = sanitizer()({"token_redacted": True, "has_secret": False, "token": None, "value_length": 12})

    assert out["token_redacted"] is True
    assert out["has_secret"] is False
    assert out["token"] is None
    assert out["value_length"] == 12


def test_sanitizer_keeps_authority_negative_capability_counts_typed():
    """`capability_allowed_count: 0` is the contract's authority-negative signal, not a credential.

    It is capability-shaped by key and numeric by value, so the funnel must carve it out explicitly
    or the envelope loses the one field that says no capability is allowed.
    """
    out = sanitizer()({
        "summary": {"capability_allowed_count": 0, "remaining_work_count": 5},
        "capability_allowed": False,
    })

    assert out["summary"]["capability_allowed_count"] == 0
    assert out["summary"]["remaining_work_count"] == 5
    assert out["capability_allowed"] is False


def test_sanitizer_keeps_required_typed_and_decision_fields_useful():
    """The envelope's own contract fields must survive the funnel intact and typed."""
    envelope = {
        "schema": "hermes-busdriver-finalization-readiness/v0",
        "read_only": True,
        "ok": False,
        "relay_capabilities": {"gate": {"path": "/x/scripts/hermes-busdriver-gate", "available": True}},
        "readiness": {"ready": False, "status": "blocked", "blockers": ["phase0_status_failed"]},
        "decision": {"status": "blocked", "merge_allowed": False},
        "delivery_status_returncode": 0,
    }

    assert sanitizer()(envelope) == envelope, "the funnel rewrote a field the envelope's readers depend on"


def test_sanitizer_redacts_our_own_credential_env_values_under_unknown_keys(monkeypatch):
    """An opaque env credential matches no shape pattern, but we know our own value."""
    monkeypatch.setenv("GH_TOKEN", "an-opaque-enterprise-credential-value")

    out = sanitizer()({"unknown": {"nested": ["remote: rejected using an-opaque-enterprise-credential-value"]}})

    assert "an-opaque-enterprise-credential-value" not in json.dumps(out)


def test_sanitizer_is_bounded_against_a_hostile_depth_bomb():
    """A child authors this structure, so its depth is the child's choice, not ours."""
    bomb: dict[str, Any] = {"token": OPAQUE_CAPABILITY}
    for _ in range(400):
        bomb = {"nest": bomb}

    out = sanitizer()(bomb)

    assert OPAQUE_CAPABILITY not in json.dumps(out)


# --- ingestion boundary: run_json is the single funnel every child crosses ---


@pytest.mark.parametrize("sentinel", [OPAQUE_CAPABILITY, SHAPED_CAPABILITY])
def test_run_json_sanitizes_a_hostile_child_payload(tmp_path: Path, sentinel: str):
    """Every load_* helper reaches its child through run_json, so the guard belongs there."""
    payload = {"schema": "x/v0", "ok": True, "read_only": True, **hostile_capabilities(sentinel)}
    child = echoing_child(tmp_path / "child.py", payload)

    data, rc = load_readiness_module()["run_json"]([sys.executable, str(child)], 10)

    assert rc == 0
    assert sentinel not in json.dumps(data)
    assert data["schema"] == "x/v0"
    assert data["ok"] is True
    assert data["read_only"] is True


def test_run_json_sanitizes_the_invalid_json_error_path(tmp_path: Path):
    """The rejected payload is the one most likely to be hostile, and it is echoed as a diagnostic."""
    child = tmp_path / "child.py"
    child.write_text(
        "import sys\n"
        f"sys.stdout.write('not json, token: {OPAQUE_CAPABILITY} {SHAPED_CAPABILITY}')\n"
        f"sys.stderr.write('boom {SHAPED_CAPABILITY}')\n"
        "sys.exit(3)\n"
    )

    data, rc = load_readiness_module()["run_json"]([sys.executable, str(child)], 10)

    assert rc == 3
    assert data["error"] == "invalid_json"
    assert SHAPED_CAPABILITY not in json.dumps(data)
    assert OPAQUE_CAPABILITY not in json.dumps(data)


def test_run_json_sanitizes_a_nonzero_child_that_still_returned_json(tmp_path: Path):
    """rc != 0 rewrites ok/returncode/stderr onto the child's own object — which is still untrusted."""
    payload = {"schema": "x/v0", "ok": True, "detail": {"token": SHAPED_CAPABILITY}}
    child = echoing_child(tmp_path / "child.py", payload, exit_code=2, stderr=f"fail {SHAPED_CAPABILITY}")

    data, rc = load_readiness_module()["run_json"]([sys.executable, str(child)], 10)

    assert rc == 2
    assert data["ok"] is False
    assert data["returncode"] == 2
    assert SHAPED_CAPABILITY not in json.dumps(data)


# --- final envelope / stdout boundary ---


def readiness_stdout(monkeypatch, capsys, children: dict[str, Any] | None = None, raise_os_error: str | None = None):
    """Run main() in-process over injected children, returning its parsed stdout.

    load_all() is the seam: it owns the authenticated bundle, which is exactly what a stale pin
    makes unavailable, so doubling it is what keeps this test about redaction.
    """
    mod = load_readiness_module()
    monkeypatch.setattr(sys, "argv", [str(READINESS), "--repo", "/tmp/repo"])
    children = children or {}

    def fake_load_all(args):
        if raise_os_error is not None:
            raise OSError(raise_os_error)
        return (
            (children.get("delivery", {"schema": "hermes-busdriver-delivery-status/v0", "read_only": True, "ok": True}), 0),
            (children.get("phase0", {"status_schema": "hermes-busdriver-status/v0", "ok": True}), 0),
            (children.get("contract", {"schema": "hermes-busdriver-finalization-contract-status/v0", "read_only": True, "ok": True}), 0),
            (children.get("plan", {"schema": "hermes-busdriver-agent-balance-plan/v0", "read_only": True, "ok": True}), 0),
        )

    mod["main"].__globals__["load_all"] = fake_load_all
    mod["main"]()
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("sentinel", [OPAQUE_CAPABILITY, SHAPED_CAPABILITY])
@pytest.mark.parametrize("child", ["delivery", "phase0", "contract", "plan"])
def test_main_stdout_never_carries_any_child_capability(monkeypatch, capsys, child: str, sentinel: str):
    """r32 High 1: a fully-bound child payload with one extra nested `token` was printed raw."""
    base = {
        "delivery": {"schema": "hermes-busdriver-delivery-status/v0", "read_only": True, "ok": True},
        "phase0": {"status_schema": "hermes-busdriver-status/v0", "ok": True},
        "contract": {"schema": "hermes-busdriver-finalization-contract-status/v0", "read_only": True, "ok": True},
        "plan": {"schema": "hermes-busdriver-agent-balance-plan/v0", "read_only": True, "ok": True},
    }
    base[child] = {**base[child], **hostile_capabilities(sentinel)}

    data = readiness_stdout(monkeypatch, capsys, {child: base[child]})

    assert sentinel not in json.dumps(data)
    assert data["schema"] == "hermes-busdriver-finalization-readiness/v0"
    assert data["read_only"] is True
    assert_no_positive_finalization_authority(data)


def test_main_stdout_redacts_a_capability_one_child_named_and_another_duplicated(monkeypatch, capsys):
    """Cross-child duplication: only the child that NAMES the value can identify it.

    delivery-status embeds its own phase-0 view, so the same opaque bytes genuinely do arrive twice
    — once under a key that names them, once under a key that says nothing. Stripping the naming
    key at ingestion is what leaves the second copy unfindable unless what was learned is retained.
    """
    data = readiness_stdout(monkeypatch, capsys, {
        "delivery": {
            "schema": "hermes-busdriver-delivery-status/v0", "read_only": True, "ok": True,
            "lock": {"token": OPAQUE_CAPABILITY},
        },
        "phase0": {
            "status_schema": "hermes-busdriver-status/v0", "ok": True,
            "active_markers": {"preview": f"marker says {OPAQUE_CAPABILITY}"},
        },
    })

    assert OPAQUE_CAPABILITY not in json.dumps(data)


def test_main_stdout_sanitizes_the_runtime_integrity_error_path(monkeypatch, capsys):
    """The failure that fires when a pin is stale still prints an OS message we did not author."""
    data = readiness_stdout(monkeypatch, capsys, raise_os_error=f"helper_digest_invalid token={SHAPED_CAPABILITY}")

    assert SHAPED_CAPABILITY not in json.dumps(data)
    assert data["ok"] is False
    assert data["readiness"]["ready"] is False
    assert_no_positive_finalization_authority(data)


def test_main_stdout_keeps_the_contract_summary_counts_typed_and_useful(monkeypatch, capsys):
    """Sanitizing must not cost the reader the authority-negative counters it exists to publish."""
    data = readiness_stdout(monkeypatch, capsys, {
        "contract": {
            "schema": "hermes-busdriver-finalization-contract-status/v0", "read_only": True, "ok": True,
            "summary": {"capability_allowed_count": 0, "remaining_work_count": 5, "policy_blocked_count": 3},
        },
    })

    summary = data["finalization_contract_status"]["summary"]
    assert summary["capability_allowed_count"] == 0
    assert summary["remaining_work_count"] == 5
    assert summary["policy_blocked_count"] == 3


@pytest.mark.parametrize("sentinel", [OPAQUE_CAPABILITY, SHAPED_CAPABILITY])
def test_handoff_envelope_never_carries_child_capabilities(sentinel: str):
    """The handoff envelope re-projects child objects, so it is a second place to leak them."""
    mod = load_readiness_module()
    args = type("Args", (), {"target": "auto", "pr": None})()
    delivery = {
        "schema": "hermes-busdriver-delivery-status/v0", "read_only": True, "ok": True,
        "repo": {"root": "/tmp/repo", "dirty": True},
        "litmus_status": {"summary": {"markers": hostile_capabilities(sentinel)}},
    }
    phase0 = {"status_schema": "hermes-busdriver-status/v0", "ok": True, "active_markers": hostile_capabilities(sentinel)}
    ready = mod["readiness"](args, delivery, phase0, {"ok": True}, {"ok": True})

    envelope = mod["sanitized_payload"](
        mod["handoff_envelope"](args, delivery, phase0, ready, {"ok": True}, {"ok": True}, {}, {})
    )

    assert sentinel not in json.dumps(envelope)
