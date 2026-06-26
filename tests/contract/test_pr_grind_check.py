import json
import runpy
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
            "--fixture-mode",
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


def test_unstable_merge_state_with_pending_checks_waits(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpending\t1m\turl\n",
        comments=[],
        view_extra={"mergeStateStatus": "UNSTABLE"},
    )

    assert data["status"] == "wait"
    assert data["clean"] is False


def test_unknown_merge_state_with_passed_checks_still_waits(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[],
        view_extra={"mergeStateStatus": "UNKNOWN"},
    )

    assert data["status"] == "wait"
    assert data["clean"] is False


def test_unstable_merge_state_with_passed_checks_still_waits(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[],
        view_extra={"mergeStateStatus": "UNSTABLE"},
    )

    assert data["status"] == "wait"
    assert data["clean"] is False


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


def test_advisory_pattern_is_literal_not_regex(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    comments_file.write_text("[]")
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--view-json-file", str(view_file), "--advisory-pattern", ".*"],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["checks"]["kept"] == 1


def test_fixture_comments_with_review_id_are_actionable_without_reviews_file(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[{"id": 123, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Current fixture finding", "path": "src/app.py", "line": 12}],
    )

    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["path"] == "src/app.py"


def test_active_thread_from_dismissed_review_is_ignored():
    ns = runpy.run_path(str(CHECK))
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "oldsha123", "body": "Dismissed unresolved thread", "path": "src/app.py", "line": 4, "user": {"login": "reviewer"}}]
    out = ns["actionable_comments"](comments, "abc123def456", set(), {123}, {9}, {9})
    assert out == []


def test_ignores_comments_from_dismissed_current_review(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    comments_file.write_text(json.dumps([{"id": 123, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Dismissed finding", "path": "src/app.py", "line": 12}]))
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "abc123def456", "state": "DISMISSED", "body": "Old review"}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_active_prior_round_thread_comment_is_actionable():
    ns = runpy.run_path(str(CHECK))
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "oldsha123", "body": "Still unresolved", "path": "src/app.py", "line": 4, "user": {"login": "reviewer"}}]
    out = ns["actionable_comments"](comments, "abc123def456", set(), {123}, {9}, set())
    assert len(out) == 1
    assert out[0]["source"] == "review_comment"


def test_ignores_comments_from_previous_review_round(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    comments_file.write_text(json.dumps([{"id": 123, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Old round finding", "path": "src/app.py", "line": 12}]))
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "old123456789", "state": "COMMENTED", "body": "Old review"}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_ignores_resolved_review_comment_ids(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    resolved_file = tmp_path / "resolved.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    comments_file.write_text(json.dumps([{"id": 123, "commit_id": "abc123def456", "body": "Please fix this", "path": "src/app.py", "line": 12}]))
    resolved_file.write_text(json.dumps([123]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--resolved-review-comment-ids-file", str(resolved_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_review_progress_issue_comment_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("CodeRabbit\tpending\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "Currently processing new changes in this PR. This may take a few minutes, please wait...", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "coderabbitai[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "wait"
    assert data["actionable_comments"][0]["source"] == "bot_progress"


def test_coderabbit_summary_issue_comment_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "<!-- This is an auto-generated comment: summarize by coderabbit.ai --> ## Summary by CodeRabbit", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "coderabbitai[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_coderabbit_rate_limit_comment_blocks_clean(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "Review limit reached: rate limited by CodeRabbit", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "coderabbitai[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "issue_comment_after_head"


def test_rate_limit_comment_with_progress_phrase_is_not_wait(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "Currently processing new changes, but review limit reached and rate limited by CodeRabbit", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "coderabbitai[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "issue_comment_after_head"


def test_please_wait_actionable_issue_comment_is_not_suppressed(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "Please wait to merge until this null dereference is fixed", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "reviewer"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "issue_comment_after_head"


def test_missing_explicit_relevant_script_blocks_without_traceback(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    comments_file.write_text("[]")
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--view-json-file", str(view_file), "--relevant-check-script", str(tmp_path / "missing.sh")],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "blocked"
    assert data["checks"]["error"] == "script_not_found"
    assert "Traceback" not in cp.stderr


def test_relevant_script_parse_failure_blocks(tmp_path: Path):
    script = tmp_path / "relevant-check-status.sh"
    script.write_text("#!/bin/sh\nprintf 'not parseable\\n'\n")
    script.chmod(0o755)
    checks_file = tmp_path / "checks.txt"
    comments_file = tmp_path / "comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    comments_file.write_text("[]")
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--view-json-file", str(view_file), "--relevant-check-script", str(script)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "blocked"
    assert "relevant_check_status_unavailable" in data["blockers"]


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
            "--fixture-mode",
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


def test_external_relevant_script_reports_pending_diagnostic_rows(tmp_path: Path):
    script = tmp_path / "relevant-check-status.sh"
    script.write_text("#!/bin/sh\nprintf '0 1 required 1\\npending-required\\tpending\\t1m\\turl\\n'\n")
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
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(comments_file), "--view-json-file", str(view_file), "--relevant-check-script", str(script)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "wait"
    assert data["checks"]["pending_rows"] == ["pending-required\tpending\t1m\turl"]


def test_resolved_current_head_comment_is_not_actionable(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpass\t1m\turl\n",
        comments=[{"commit_id": "abc123def456", "body": "This used to need a fix", "path": "src/app.py", "line": 12, "resolved": True}],
    )

    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_generic_bot_review_summary_without_inline_comment_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "### 💡 Codex Review\nHere are some automated review suggestions for this pull request.\n**Reviewed commit:** `abc123def456`\n<details><summary>ℹ️ About Codex in GitHub</summary>Boilerplate</details>", "user": {"login": "chatgpt-codex-connector[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_generic_bot_review_summary_with_inline_comment_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text(json.dumps([{"id": 1, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Resolved inline detail", "resolved": True, "path": "x.py", "line": 1}]))
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "### 💡 Codex Review\nHere are some automated review suggestions for this pull request.\n**Reviewed commit:** `abc123def456`\n<details><summary>ℹ️ About Codex in GitHub</summary>Boilerplate</details>", "user": {"login": "chatgpt-codex-connector[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_bot_review_summary_with_actionable_details_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text(json.dumps([{"id": 1, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Resolved inline detail", "resolved": True, "path": "x.py", "line": 1}]))
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "### 💡 Codex Review\nHere are some automated review suggestions for this pull request.\n**Reviewed commit:** `abc123def456`\n<details><summary>Actionable details</summary>Please update the migration before merging.</details>", "user": {"login": "chatgpt-codex-connector[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "review"


def test_bot_review_summary_with_actionable_extra_text_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text(json.dumps([{"id": 1, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Resolved inline detail", "resolved": True, "path": "x.py", "line": 1}]))
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "### 💡 Codex Review\nHere are some automated review suggestions for this pull request.\nPlease update the migration before merging.\n**Reviewed commit:** `abc123def456`\n<details><summary>ℹ️ About Codex in GitHub</summary>Boilerplate</details>", "user": {"login": "chatgpt-codex-connector[bot]"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "review"


def test_review_body_on_current_head_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "COMMENTED", "body": "Please handle the edge case", "user": {"login": "bot"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "review"


def test_dismissed_review_body_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "DISMISSED", "body": "Old request changes", "user": {"login": "bot"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_issue_comment_without_head_time_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "Do not merge until X is fixed", "user": {"login": "reviewer"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "issue_comment_unbound"


def test_issue_comment_is_conservative_actionable_signal(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "This still needs a fix", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "reviewer"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"
    assert data["actionable_comments"][0]["source"] == "issue_comment_after_head"


def test_old_issue_comment_before_latest_head_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    issue_comments_file = tmp_path / "issue-comments.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    issue_comments_file.write_text(json.dumps([{"body": "This used to need a fix", "created_at": "2025-12-31T23:59:00Z", "user": {"login": "reviewer"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456", "commits": [{"committedDate": "2026-01-01T00:00:00Z"}]}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--issue-comments-file", str(issue_comments_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"
    assert data["actionable_comments"] == []


def test_parse_paginated_json_flattens_slurped_pages():
    ns = runpy.run_path(str(CHECK))
    parse_paginated_json = ns["parse_paginated_json"]

    data = parse_paginated_json(json.dumps([[{"id": 1}], [{"id": 2}], []]))

    assert data == [{"id": 1}, {"id": 2}]
