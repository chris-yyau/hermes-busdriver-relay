import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
READINESS = ROOT / "scripts" / "hermes-busdriver-finalization-readiness"
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
]


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=False, timeout=timeout)


def init_repo(path: Path) -> Path:
    path.mkdir()
    assert run(["git", "init"], path).returncode == 0
    assert run(["git", "config", "user.email", "test@example.test"], path).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], path).returncode == 0
    (path / "README.md").write_text("# test\n")
    assert run(["git", "add", "README.md"], path).returncode == 0
    assert run(["git", "commit", "-m", "init"], path).returncode == 0
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


def test_readiness_handoff_includes_machine_readable_remaining_finalization_work(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    (repo / "work.txt").write_text("draft\n")

    cp, data = invoke(repo, plugin, user_config)

    assert cp.returncode == 0, cp.stderr
    guardrails = data["finalization_guardrails"]
    work = guardrails["remaining_work"]
    assert guardrails["schema"] == "hermes-busdriver-finalization-guardrails/v0"
    assert guardrails["version"] == 0
    assert guardrails["read_only"] is True
    assert guardrails["status"] == "non_mutating_relay_only"
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
    assert all(item["status"] == "not_implemented" for item in work)
    assert all(item["safe_to_execute_by_this_helper"] is False for item in work)
    assert set(guardrails["unsupported_mutating_operations"]) == {
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


def test_readiness_handoff_includes_read_only_dual_review_status_envelope(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    user_config = fake_user_config(tmp_path / "busdriver.json")
    relay_cfg = tmp_path / "relay-config.json"
    relay_cfg.write_text(json.dumps({
        "coding_agent": "codex",
        "avoid_coding_agent_for_review": True,
        "routes": {
            "relay.litmus.reviewer": ["gpt-5.5", "codex"],
            "relay.pr.lead": ["gpt-5.5", "codex"],
            "relay.pr.backstop": ["gpt-5.5", "codex"],
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
        assert entry["selected_agent"] == "gpt-5.5"
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
    assert data["readiness"]["status"] == "ready_for_commit_or_pr_handoff"
    assert "litmus_pre_pr_stale_or_missing" in data["readiness"]["warnings"]
    litmus_summary = data["delivery_status"]["litmus_status"]["summary"]
    handoff_litmus = data["handoff_envelope"]["evidence"]["litmus_status"]
    assert handoff_litmus == litmus_summary
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
        **{key: False for key in ["finalization_allowed", "commit_allowed", "push_allowed", "pr_allowed", "merge_allowed", "deploy_allowed", "release_allowed", "publish_allowed", "marker_write_allowed"]},
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

    def fake_run_json(cmd: list[str], timeout: int) -> tuple[dict, int]:
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        return {"ok": True}, 0

    mod["load_delivery_status"].__globals__["run_json"] = fake_run_json

    mod["load_delivery_status"](args)

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

    def fake_run_json(cmd: list[str], timeout: int) -> tuple[dict, int]:
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        return {"ok": True}, 0

    mod["load_delivery_status"].__globals__["run_json"] = fake_run_json

    mod["load_delivery_status"](args)

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

    def fake_run_json(cmd: list[str], timeout: int) -> tuple[dict, int]:
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        return {"ok": True}, 0

    mod["load_delivery_status"].__globals__["run_json"] = fake_run_json

    mod["load_delivery_status"](args)

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
