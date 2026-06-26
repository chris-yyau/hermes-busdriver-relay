import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "scripts" / "hermes-busdriver-pr-grind-check"


def run_check(tmp_path: Path, checks: str, comments: list[dict], head: str = "abc123def456", view_extra: dict | None = None):
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text(checks)
    comments_file.write_text(json.dumps(comments))
    view = {
        "number": 7,
        "url": "https://example.test/pull/7",
        "state": "OPEN",
        "mergeable": "MERGEABLE",
        "headRefOid": head,
        "baseRefName": "main",
        "headRefName": "feature",
    }
    if view_extra:
        view.update(view_extra)
    view_file.write_text(json.dumps(view))
    cp = subprocess.run(
        [
            sys.executable,
            str(CHECK),
            "--repo",
            str(repo),
            "--pr",
            "7",
            "--checks-file",
            str(checks_file),
            "--review-comments-file",
            str(comments_file),
            "--view-json-file",
            str(view_file),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    return json.loads(cp.stdout)


def test_clean_when_relevant_checks_pass_and_no_current_head_findings(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="CodeRabbit\tpass\t1m\turl\nunit\tpass\t1m\turl\n",
        comments=[{"commit_id": "oldsha", "body": "Please change old code", "path": "x.py", "line": 1}],
    )

    assert data["status"] == "clean"
    assert data["clean"] is True
    assert data["checks"]["failed"] == 0
    assert data["checks"]["pending"] == 0
    assert data["actionable_comments"] == []


def test_waits_when_relevant_checks_are_pending(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpending\t1m\turl\nCodeRabbit\tpass\t1m\turl\n",
        comments=[],
    )

    assert data["status"] == "wait"
    assert data["clean"] is False
    assert data["checks"]["pending"] == 1


def test_needs_fix_for_actionable_comment_on_current_head(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[{"commit_id": "abc123def456", "body": "This can crash on empty input", "path": "src/app.py", "line": 12, "user": {"login": "codex"}}],
    )

    assert data["status"] == "needs_fix"
    assert data["clean"] is False
    assert len(data["actionable_comments"]) == 1
    assert data["actionable_comments"][0]["path"] == "src/app.py"


def test_blocks_when_pr_is_not_mergeable_even_if_checks_pass(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[],
        view_extra={"mergeable": "CONFLICTING"},
    )

    assert data["status"] == "blocked"
    assert "mergeable=CONFLICTING" in data["blockers"]


def test_blocks_when_review_decision_requests_changes(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[],
        view_extra={"reviewDecision": "CHANGES_REQUESTED", "mergeStateStatus": "CLEAN", "isDraft": False},
    )

    assert data["status"] == "blocked"
    assert "reviewDecision=CHANGES_REQUESTED" in data["blockers"]


def test_negative_fixed_phrase_is_still_actionable(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[{"commit_id": "abc123def456", "body": "Thanks, but this is not fixed and still crashes", "path": "src/app.py", "line": 12}],
    )

    assert data["status"] == "needs_fix"
    assert len(data["actionable_comments"]) == 1


def test_ignores_malformed_short_comment_sha(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[{"commit_id": "a", "body": "This should not bind to HEAD", "path": "src/app.py", "line": 12}],
    )

    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_external_relevant_script_controls_pending_rows(tmp_path: Path):
    script = tmp_path / "relevant-check-status.sh"
    script.write_text("#!/bin/sh\nprintf '0 0 required 1\\n'\n")
    script.chmod(0o755)
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("advisory\tpending\t1m\turl\nunit\tpass\t1m\turl\n")
    comments_file.write_text("[]")
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [
            sys.executable,
            str(CHECK),
            "--repo", str(repo),
            "--pr", "7",
            "--checks-file", str(checks_file),
            "--review-comments-file", str(comments_file),
            "--view-json-file", str(view_file),
            "--relevant-check-script", str(script),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["checks"]["pending_rows"] == []


def test_resolved_current_head_comment_is_not_actionable(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[{"commit_id": "abc123def456", "body": "This used to need a fix", "path": "src/app.py", "line": 12, "resolved": True}],
    )

    assert data["status"] == "clean"
    assert data["actionable_comments"] == []
