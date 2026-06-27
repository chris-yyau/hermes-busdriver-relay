import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "scripts" / "hermes-busdriver-pr-grind-loop"


def fixture(tmp_path: Path, name: str, status: str, *, head: str = "abc123def456", clean: bool | None = None, reason: str | None = None) -> Path:
    if clean is None:
        clean = status == "clean"
    blockers = []
    if reason == "head_changed":
        blockers = ["head_changed_during_collection:oldhead123456->abc123def456"]
    data = {
        "schema": "hermes-busdriver-pr-grind-check/v0",
        "ok": True,
        "pr": 7,
        "url": "https://example.test/pull/7",
        "head": head,
        "base": "main",
        "status": status,
        "clean": clean,
        "blockers": blockers,
        "checks": {"failed": 0, "pending": 1 if status == "wait" else 0, "mode": "all", "kept": 1, "failed_rows": [], "pending_rows": [], "source": "fixture", "relevance_unavailable": False},
        "actionable_comments": [{"body_preview": "fix this"}] if status == "needs_fix" else [],
        "decision": {"merge_allowed": status == "clean", "needs_fix": status == "needs_fix", "wait": status == "wait", "blocked": status == "blocked", "reason": reason or status},
    }
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


def run_loop(tmp_path: Path, *fixtures: Path, extra: list[str] | None = None) -> tuple[subprocess.CompletedProcess[str], dict]:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    cmd = [
        sys.executable,
        str(LOOP),
        "--repo",
        str(repo),
        "--pr",
        "7",
        "--poll-interval",
        "0",
        "--max-wait-seconds",
        "5",
    ]
    for item in fixtures:
        cmd += ["--fixture-result-file", str(item)]
    if extra:
        cmd += extra
    cp = subprocess.run(cmd, text=True, capture_output=True, check=False)
    assert cp.stdout, cp.stderr
    return cp, json.loads(cp.stdout)


def assert_no_finalization_authority(decision: dict) -> None:
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
        assert decision[key] is False
    assert decision["fixing_allowed"] is False
    assert decision["fix_rounds_attempted"] == 0
    assert decision["marker_write_allowed"] is False


def test_clean_result_emits_read_only_envelope_without_merge_authority(tmp_path: Path):
    cp, data = run_loop(tmp_path, fixture(tmp_path, "clean.json", "clean"))

    assert cp.returncode == 0
    assert data["schema"] == "hermes-busdriver-pr-grind-loop/v0"
    assert data["ok"] is True
    assert data["status"] == "clean"
    assert data["clean"] is True
    assert data["read_only"] is True
    assert data["decision"]["pr_grind_clean"] is True
    assert data["decision"]["marker_write_allowed"] is False
    assert_no_finalization_authority(data["decision"])
    assert len(data["iterations"]) == 1


def test_wait_status_polls_until_clean_with_bounded_budget(tmp_path: Path):
    cp, data = run_loop(
        tmp_path,
        fixture(tmp_path, "wait.json", "wait"),
        fixture(tmp_path, "clean.json", "clean", head="def456abc789"),
    )

    assert cp.returncode == 0
    assert data["status"] == "clean"
    assert [item["status"] for item in data["iterations"]] == ["wait", "clean"]
    assert data["latest_head"] == "def456abc789"
    assert_no_finalization_authority(data["decision"])


def test_needs_fix_bails_without_attempting_fix_rounds(tmp_path: Path):
    cp, data = run_loop(tmp_path, fixture(tmp_path, "needs-fix.json", "needs_fix"))

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["status"] == "needs_fix"
    assert data["decision"]["reason"] == "actionable_feedback_present_read_only_no_fix"
    assert data["decision"]["fixing_allowed"] is False
    assert data["decision"]["fix_rounds_attempted"] == 0
    assert len(data["iterations"]) == 1
    assert_no_finalization_authority(data["decision"])


def test_head_changed_block_repolls_latest_head_before_deciding(tmp_path: Path):
    cp, data = run_loop(
        tmp_path,
        fixture(tmp_path, "head-changed.json", "blocked", reason="head_changed"),
        fixture(tmp_path, "clean.json", "clean", head="fedcba987654"),
    )

    assert cp.returncode == 0
    assert [item["decision_reason"] for item in data["iterations"]] == ["head_changed", "clean"]
    assert data["status"] == "clean"
    assert data["latest_head"] == "fedcba987654"


def test_wait_exhaustion_fails_closed(tmp_path: Path):
    cp, data = run_loop(
        tmp_path,
        fixture(tmp_path, "wait.json", "wait"),
        extra=["--max-wait-seconds", "0", "--max-polls", "3"],
    )

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["status"] == "wait"
    assert data["decision"]["reason"] == "max_wait_exhausted"
    assert len(data["iterations"]) == 1
    assert_no_finalization_authority(data["decision"])


def test_unrecognized_checker_status_is_policy_gap(tmp_path: Path):
    cp, data = run_loop(tmp_path, fixture(tmp_path, "mystery.json", "mystery"))

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["decision"]["reason"] == "policy_gap"
    assert data["policy_gaps"] == ["unrecognized_status:mystery"]
    assert len(data["iterations"]) == 1
    assert_no_finalization_authority(data["decision"])


def test_nonzero_fix_round_request_is_rejected_before_loop(tmp_path: Path):
    cp = subprocess.run(
        [
            sys.executable,
            str(LOOP),
            "--repo",
            str(tmp_path),
            "--pr",
            "7",
            "--max-fix-rounds",
            "1",
            "--fixture-result-file",
            str(fixture(tmp_path, "clean.json", "clean")),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode != 0
    data = json.loads(cp.stderr.strip())
    assert data == {"ok": False, "error": "fix_rounds_not_supported_in_read_only_loop"}
