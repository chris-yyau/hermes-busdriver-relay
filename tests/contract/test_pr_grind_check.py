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


def test_waits_for_pending_checks_before_acting_on_comments(tmp_path: Path):
    data = run_check(
        tmp_path,
        checks="unit\tpending\t1m\turl\n",
        comments=[{"commit_id": "abc123def456", "body": "This can crash on empty input", "path": "src/app.py", "line": 12}],
    )
    assert data["status"] == "wait"
    assert data["actionable_comments"]


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


def test_active_prior_round_thread_before_latest_head_is_actionable_when_not_outdated():
    ns = runpy.run_path(str(CHECK))
    head_time = ns["parse_github_time"]("2026-01-01T00:01:00Z")
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "oldsha123", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z", "body": "Old but still unresolved active thread", "path": "src/app.py", "line": 4, "user": {"login": "reviewer"}}]
    out = ns["actionable_comments"](comments, "abc123def456", head_time, set(), {123}, {9}, set())
    assert len(out) == 1
    assert out[0]["source"] == "review_comment"


def test_active_thread_from_dismissed_review_is_ignored():
    ns = runpy.run_path(str(CHECK))
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "oldsha123", "body": "Dismissed unresolved thread", "path": "src/app.py", "line": 4, "user": {"login": "reviewer"}}]
    out = ns["actionable_comments"](comments, "abc123def456", None, set(), {123}, {9}, {9})
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
    out = ns["actionable_comments"](comments, "abc123def456", None, set(), {123}, {9}, set())
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


def test_ack_value_matches_exact_head_prefix_or_longer_prefix():
    ns = runpy.run_path(str(CHECK))
    assert ns["ack_matches_head"]("abc123de:E", "abc123def456") is True
    assert ns["ack_matches_head"]("abc123de", "abc123def456") is True
    assert ns["ack_matches_head"]("abc123def:E", "abc123def456") is True
    assert ns["ack_matches_head"]("abc123d0:E", "abc123def456") is False
    assert ns["ack_matches_head"]("abc123dezzz:E", "abc123def456") is False
    assert ns["ack_matches_head"]("abc123def4560:E", "abc123def456") is False


def test_load_acked_bot_logins_uses_env_plugin_roots(tmp_path: Path, monkeypatch):
    ns = runpy.run_path(str(CHECK))
    plugin = tmp_path / "plugin"
    scripts = plugin / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "fetch-pr-state.sh").write_text("FETCH_OK=1; export FETCH_OK\n")
    (scripts / "ack-ledger.sh").write_text("#!/usr/bin/env bash\necho abc123de:E\n")
    (scripts / "ack-ledger.sh").chmod(0o755)
    monkeypatch.setenv("BUSDRIVER_PLUGIN_ROOT", str(plugin))
    args = type("Args", (), {"fixture_mode": False, "plugin_root": None, "pr": "7"})()
    assert "coderabbitai[bot]" in ns["load_acked_bot_logins"](args, tmp_path, "abc123def456")



def test_acked_coderabbit_rate_limit_comment_does_not_block():
    ns = runpy.run_path(str(CHECK))
    comments = [{"body": "Review limit reached: rate limited by CodeRabbit", "created_at": "2026-01-01T00:01:00Z", "user": {"login": "coderabbitai[bot]"}}]
    head_time = ns["parse_github_time"]("2026-01-01T00:00:00Z")
    out = ns["actionable_issue_comments"](comments, head_time, {"coderabbitai[bot]"})
    assert out == []


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


def test_cubic_no_issues_review_body_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "**No issues found** across 5 files\n\n<sub>[Re-trigger cubic](https://www.cubic.dev/action/re-review/pr/owner/repo/5)</sub>", "user": {"login": "cubic-dev-ai[bot]"}}]))
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


def test_cubic_no_issues_single_file_review_body_is_not_actionable():
    ns = runpy.run_path(str(CHECK))
    reviews = [{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "**No issues found** across 1 file reviewed.", "user": {"login": "cubic-dev-ai[bot]"}}]
    assert ns["actionable_reviews"](reviews, "abc123def456") == []


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


def test_approved_review_body_with_harmless_text_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "APPROVED", "body": "Ship it", "user": {"login": "bot"}}]))
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


def test_approved_review_body_with_great_work_is_not_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "APPROVED", "body": "Great work!", "user": {"login": "human"}}]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"


def test_approved_review_body_with_actionable_text_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "APPROVED", "body": "Approved overall, but please fix the fallback before merging", "user": {"login": "bot"}}]))
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


def test_approved_review_body_with_broken_regression_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "APPROVED", "body": "Approved, but this regression is broken", "user": {"login": "human"}}]))
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


def test_approved_review_body_with_please_update_migration_is_actionable(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([{"commit_id": "abc123def456", "state": "APPROVED", "body": "Please update the migration", "user": {"login": "human"}}]))
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


def test_non_actionable_commented_review_does_not_supersede_prior_actionable_review(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([
        {"id": 1, "commit_id": "abc123def456", "state": "COMMENTED", "body": "Please update the migration", "user": {"login": "reviewer"}, "submitted_at": "2026-01-01T00:00:00Z"},
        {"id": 2, "commit_id": "abc123def456", "state": "COMMENTED", "body": "thanks", "user": {"login": "reviewer"}, "submitted_at": "2026-01-01T00:01:00Z"},
    ]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "needs_fix"


def test_pending_review_does_not_supersede_prior_actionable_review(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([
        {"id": 1, "commit_id": "abc123def456", "state": "COMMENTED", "body": "Please update the migration", "user": {"login": "reviewer"}, "submitted_at": "2026-01-01T00:00:00Z"},
        {"id": 2, "commit_id": "abc123def456", "state": "PENDING", "body": "Draft note", "user": {"login": "reviewer"}, "submitted_at": "2026-01-01T00:01:00Z"},
    ]))
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


def test_latest_same_reviewer_approval_supersedes_prior_review_body(tmp_path: Path):
    checks_file = tmp_path / "checks.txt"
    review_comments_file = tmp_path / "review-comments.json"
    reviews_file = tmp_path / "reviews.json"
    view_file = tmp_path / "view.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    checks_file.write_text("unit\tpass\t1m\turl\n")
    review_comments_file.write_text("[]")
    reviews_file.write_text(json.dumps([
        {"id": 1, "commit_id": "abc123def456", "state": "COMMENTED", "body": "Please update the migration", "user": {"login": "reviewer"}, "submitted_at": "2026-01-01T00:00:00Z"},
        {"id": 2, "commit_id": "abc123def456", "state": "APPROVED", "body": "Looks good", "user": {"login": "reviewer"}, "submitted_at": "2026-01-01T00:01:00Z"},
    ]))
    view_file.write_text(json.dumps({"number": 7, "state": "OPEN", "mergeable": "MERGEABLE", "headRefOid": "abc123def456"}))

    cp = subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--pr", "7", "--fixture-mode", "--checks-file", str(checks_file), "--review-comments-file", str(review_comments_file), "--reviews-file", str(reviews_file), "--view-json-file", str(view_file)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)
    assert data["status"] == "clean"


def test_current_head_bot_inline_comment_not_superseded_by_same_review():
    ns = runpy.run_path(str(CHECK))
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "abc123def456", "body": "Current bot finding", "path": "src/app.py", "line": 4, "user": {"login": "chatgpt-codex-connector[bot]"}}]
    out = ns["actionable_comments"](comments, "abc123def456", None, set(), {123}, {9}, set(), {"chatgpt-codex-connector[bot]"})
    assert len(out) == 1
    assert out[0]["source"] == "review_comment"


def test_later_current_head_bot_review_supersedes_rest_comment_retargeted_to_head():
    ns = runpy.run_path(str(CHECK))
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "abc123def456", "original_commit_id": "oldsha123", "body": "Old bot finding", "path": "src/app.py", "line": 4, "user": {"login": "chatgpt-codex-connector[bot]"}}]
    out = ns["actionable_comments"](comments, "abc123def456", None, set(), {123}, {9}, set(), {"chatgpt-codex-connector[bot]"})
    assert out == []


def test_later_current_head_bot_review_supersedes_prior_round_bot_inline_comment():
    ns = runpy.run_path(str(CHECK))
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "oldsha123", "body": "Old bot finding", "path": "src/app.py", "line": 4, "user": {"login": "chatgpt-codex-connector[bot]"}}]
    out = ns["actionable_comments"](comments, "abc123def456", None, set(), {123}, {9}, set(), {"chatgpt-codex-connector[bot]"})
    assert out == []


def test_current_head_bot_review_is_not_hidden_by_later_stale_review():
    ns = runpy.run_path(str(CHECK))
    reviews = [
        {"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "Current-head summary", "user": {"login": "chatgpt-codex-connector[bot]"}, "submitted_at": "2026-01-01T00:00:00Z"},
        {"id": 10, "commit_id": "oldsha123", "state": "COMMENTED", "body": "Stale summary", "user": {"login": "chatgpt-codex-connector[bot]"}, "submitted_at": "2026-01-01T00:01:00Z"},
    ]
    assert "chatgpt-codex-connector[bot]" in ns["current_head_bot_review_logins"](reviews, "abc123def456")



def test_head_changed_check_counts_keeps_stable_schema():
    ns = runpy.run_path(str(CHECK))
    counts = ns["head_changed_check_counts"]()
    assert counts["source"] == "head_changed"
    assert counts["relevance_unavailable"] is False



def test_unresolved_outdated_thread_comment_is_not_actionable_when_not_live():
    ns = runpy.run_path(str(CHECK))
    comments = [{"id": 123, "pull_request_review_id": 9, "commit_id": "oldsha123", "body": "Unresolved outdated feedback", "path": "src/app.py", "line": 4, "user": {"login": "reviewer"}}]
    out = ns["actionable_comments"](comments, "abc123def456", None, set(), set(), {9}, set())
    assert out == []



def test_unresolved_outdated_thread_id_is_ignored_like_resolved(tmp_path: Path):
    ns = runpy.run_path(str(CHECK))
    repo = tmp_path / "repo"
    repo.mkdir()
    ns["owner_repo"] = lambda _repo: "owner/name"

    def fake_run(cmd, cwd=None, check=False):
        payload = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False},
                            "nodes": [
                                {"isResolved": False, "isOutdated": True, "comments": {"pageInfo": {"hasNextPage": False}, "nodes": [{"databaseId": 123}]}}
                            ],
                        }
                    }
                }
            }
        }
        return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")

    ns["load_review_thread_comment_states"].__globals__["run"] = fake_run
    ns["load_review_thread_comment_states"].__globals__["owner_repo"] = lambda _repo: "owner/name"
    resolved, active = ns["load_review_thread_comment_states"](type("Args", (), {"resolved_review_comment_ids_file": None, "fixture_mode": False, "pr": "7"})(), repo)
    assert resolved == {123}
    assert active == set()



def test_devin_review_summary_without_live_inline_issue_is_not_actionable():
    ns = runpy.run_path(str(CHECK))
    reviews = [{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "**Devin Review** found 1 new potential issue.\n\n<!-- devin-review-badge-begin -->", "user": {"login": "devin-ai-integration[bot]"}}]
    assert ns["actionable_reviews"](reviews, "abc123def456") == []


def test_devin_review_summary_plural_without_live_inline_issue_is_not_actionable():
    ns = runpy.run_path(str(CHECK))
    reviews = [{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "**Devin Review** found 2 new potential issues.\n\n<!-- devin-review-badge-begin -->", "user": {"login": "devin-ai-integration[bot]"}}]
    assert ns["actionable_reviews"](reviews, "abc123def456") == []


def test_devin_no_issues_review_body_is_not_actionable():
    ns = runpy.run_path(str(CHECK))
    reviews = [{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "## ✅ Devin Review: No Issues Found\n\nDevin Review analyzed this PR and found no bugs or issues to report.", "user": {"login": "devin-ai-integration[bot]"}}]
    assert ns["actionable_reviews"](reviews, "abc123def456") == []


def test_devin_no_issues_substring_does_not_hide_actionable_body():
    ns = runpy.run_path(str(CHECK))
    reviews = [{"id": 9, "commit_id": "abc123def456", "state": "COMMENTED", "body": "Please fix this bug before merging. Previous text said Devin Review: No Issues Found, but this body is actionable.", "user": {"login": "devin-ai-integration[bot]"}}]
    assert ns["actionable_reviews"](reviews, "abc123def456")



def test_fallback_check_counts_treats_failing_as_failed():
    ns = runpy.run_path(str(CHECK))
    counts = ns["fallback_check_counts"]("unit\tfailing\t1m\turl\n", "CodeScene")
    assert counts["failed"] == 1
    assert counts["failed_rows"] == ["unit\tfailing\t1m\turl"]



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


def test_select_head_time_without_push_anchor_is_unbound_even_with_check_time():
    ns = runpy.run_path(str(CHECK))
    commit_time = ns["parse_github_time"]("2026-01-01T00:00:00Z")
    check_time = ns["parse_github_time"]("2026-01-02T03:05:00Z")
    assert ns["select_head_time"](commit_time, check_time, None) is None



def test_select_head_time_without_server_anchor_is_unbound():
    ns = runpy.run_path(str(CHECK))
    commit_time = ns["parse_github_time"]("2026-01-01T00:00:00Z")
    fallback_time = ns["parse_github_time"]("2026-01-01T00:00:00Z")
    assert ns["select_head_time"](commit_time, None, fallback_time) is None



def test_select_head_time_prefers_pr_push_time_over_backdated_commit_time():
    ns = runpy.run_path(str(CHECK))
    commit_time = ns["parse_github_time"]("2026-01-01T00:00:00Z")
    push_time = ns["parse_github_time"]("2026-01-02T03:04:05Z")
    check_time = ns["parse_github_time"]("2026-01-02T03:05:00Z")
    assert ns["select_head_time"](commit_time, check_time, None, push_time=push_time) == push_time



def test_push_events_head_time_filters_head_and_branch():
    ns = runpy.run_path(str(CHECK))
    stdout = json.dumps([
        [
            {"type": "PushEvent", "created_at": "2026-01-02T03:03:00Z", "payload": {"head": "abc123def456", "ref": "refs/heads/other"}},
            {"type": "PushEvent", "created_at": "2026-01-02T03:04:05Z", "payload": {"head": "abc123def456", "ref": "refs/heads/feature"}},
            {"type": "PushEvent", "created_at": "2026-01-02T03:06:00Z", "payload": {"head": "different", "ref": "refs/heads/feature"}},
        ]
    ])
    assert ns["push_events_head_time"](stdout, "abc123def456", "feature") == ns["parse_github_time"]("2026-01-02T03:04:05Z")





def test_same_head_fresh_view_collects_feedback_once_after_refresh(tmp_path: Path, monkeypatch):
    ns = runpy.run_path(str(CHECK))
    calls = []
    view = {"number": 7, "url": "https://example.test/pull/7", "state": "OPEN", "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN", "headRefOid": "abc123def456", "baseRefName": "main", "headRefName": "feature"}

    def fake_load_view(args, repo):
        return dict(view)

    def fake_collect(args, repo, current_view, head):
        calls.append(current_view)
        return [{"id": 99, "source": "review_comment", "body_preview": "new same-head feedback"}]

    ns["main"].__globals__["load_view"] = fake_load_view
    parse_calls = []
    ns["main"].__globals__["load_checks"] = lambda args, repo: "unit\tpass\t1m\turl\n"
    ns["main"].__globals__["resolve_relevant_script"] = lambda args: None
    def fake_parse(script, repo, checks, advisory):
        parse_calls.append(checks)
        return {"failed": 0, "pending": 0, "mode": "all", "kept": 1, "failed_rows": [], "pending_rows": [], "source": "test", "relevance_unavailable": False}
    ns["main"].__globals__["parse_relevant_counts"] = fake_parse
    ns["main"].__globals__["collect_actionable_feedback"] = fake_collect
    monkeypatch.setattr(sys, "argv", [str(CHECK), "--repo", str(tmp_path), "--pr", "7"] )
    rc = ns["main"]()
    assert rc == 0
    assert len(calls) == 2
    assert len(parse_calls) == 2



def test_same_head_recollect_rechecks_head_after_feedback_collection(tmp_path: Path, monkeypatch, capsys):
    ns = runpy.run_path(str(CHECK))
    heads = ["abc123def456", "abc123def456", "def456abc789"]

    def fake_load_view(args, repo):
        head = heads.pop(0)
        return {"number": 7, "url": "https://example.test/pull/7", "state": "OPEN", "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN", "headRefOid": head, "baseRefName": "main", "headRefName": "feature"}

    ns["main"].__globals__["load_view"] = fake_load_view
    ns["main"].__globals__["load_checks"] = lambda args, repo: "unit\tpass\t1m\turl\n"
    ns["main"].__globals__["resolve_relevant_script"] = lambda args: None
    ns["main"].__globals__["parse_relevant_counts"] = lambda script, repo, checks, advisory: {"failed": 0, "pending": 0, "mode": "all", "kept": 1, "failed_rows": [], "pending_rows": [], "source": "test", "relevance_unavailable": False}
    ns["main"].__globals__["collect_actionable_feedback"] = lambda args, repo, view, head: []
    monkeypatch.setattr(sys, "argv", [str(CHECK), "--repo", str(tmp_path), "--pr", "7"] )
    assert ns["main"]() == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "blocked"
    assert data["decision"]["reason"] == "head_changed"




def test_same_head_rechecks_head_after_final_feedback_refresh(tmp_path: Path, monkeypatch, capsys):
    ns = runpy.run_path(str(CHECK))
    heads = ["abc123def456", "abc123def456", "abc123def456", "def456abc789"]

    def fake_load_view(args, repo):
        head = heads.pop(0)
        return {"number": 7, "url": "https://example.test/pull/7", "state": "OPEN", "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN", "headRefOid": head, "baseRefName": "main", "headRefName": "feature"}

    ns["main"].__globals__["load_view"] = fake_load_view
    ns["main"].__globals__["load_checks"] = lambda args, repo: "unit\tpass\t1m\turl\n"
    ns["main"].__globals__["resolve_relevant_script"] = lambda args: None
    ns["main"].__globals__["parse_relevant_counts"] = lambda script, repo, checks, advisory: {"failed": 0, "pending": 0, "mode": "all", "kept": 1, "failed_rows": [], "pending_rows": [], "source": "test", "relevance_unavailable": False}
    ns["main"].__globals__["collect_actionable_feedback"] = lambda args, repo, view, head: []
    monkeypatch.setattr(sys, "argv", [str(CHECK), "--repo", str(tmp_path), "--pr", "7"] )
    assert ns["main"]() == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "blocked"
    assert data["decision"]["reason"] == "head_changed"


def test_invalid_pr_number_is_rejected():
    ns = runpy.run_path(str(CHECK))
    try:
        ns["validate_pr_number"]("3; rm -rf /")
    except SystemExit as exc:
        assert "invalid_pr_number" in str(exc)
    else:
        raise AssertionError("expected invalid PR number to fail")


def test_parse_paginated_check_runs_flattens_slurped_pages():
    ns = runpy.run_path(str(CHECK))
    stdout = json.dumps([
        {"check_runs": [{"name": "late", "started_at": "2026-01-02T03:05:00Z"}]},
        {"check_runs": [{"name": "early", "started_at": "2026-01-02T03:04:00Z"}]},
    ])
    rows = ns["parse_paginated_check_runs"](stdout)
    assert [r["name"] for r in rows] == ["late", "early"]
    assert ns["check_runs_head_time"]({"check_runs": rows}) == ns["parse_github_time"]("2026-01-02T03:04:00Z")


def test_check_runs_head_time_uses_earliest_check_start():
    ns = runpy.run_path(str(CHECK))
    parsed = ns["check_runs_head_time"]({"check_runs": [
        {"created_at": "2026-01-02T03:05:00Z"},
        {"started_at": "2026-01-02T03:04:05Z"},
    ]})
    assert parsed == ns["parse_github_time"]("2026-01-02T03:04:05Z")


def test_commit_json_time_prefers_committer_date():
    ns = runpy.run_path(str(CHECK))
    parsed = ns["commit_json_time"]({"commit": {"committer": {"date": "2026-01-02T03:04:05Z"}, "author": {"date": "2026-01-01T00:00:00Z"}}})
    assert parsed == ns["parse_github_time"]("2026-01-02T03:04:05Z")


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
