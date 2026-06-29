import hashlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "hermes-busdriver-litmus-status"


def load_litmus_status_module():
    loader = importlib.machinery.SourceFileLoader("hermes_busdriver_litmus_status", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def init_repo(path: Path, *, branch: bool = False) -> Path:
    path.mkdir()
    assert run(["git", "init"], path).returncode == 0
    assert run(["git", "config", "user.email", "test@example.test"], path).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], path).returncode == 0
    (path / "README.md").write_text("# test\n")
    assert run(["git", "add", "README.md"], path).returncode == 0
    assert run(["git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "init"], path).returncode == 0
    assert run(["git", "branch", "-M", "main"], path).returncode == 0
    if branch:
        assert run(["git", "checkout", "-b", "topic"], path).returncode == 0
        (path / "feature.txt").write_text("feature\n")
        assert run(["git", "add", "feature.txt"], path).returncode == 0
        assert run(["git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "feature"], path).returncode == 0
    return path


def invoke_raw(repo: Path, *extra: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--base-ref", "main", *extra],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def invoke_raw_no_base(repo: Path, *extra: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), *extra],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def invoke(repo: Path, *extra: str, env: dict[str, str] | None = None) -> dict:
    cp = invoke_raw(repo, *extra, env=env)
    assert cp.returncode == 0, cp.stderr
    return json.loads(cp.stdout)


def isolated_git_env(**overrides: str) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {
            "GIT_CONFIG_GLOBAL",
            "GIT_CONFIG_NOSYSTEM",
            "GIT_EXTERNAL_DIFF",
            "GIT_DIFF_OPTS",
            "XDG_CONFIG_HOME",
        }
    }
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env.update(overrides)
    return env


def branch_diff_hash(repo: Path, base_ref: str = "main") -> str:
    merge_base = run(["git", "merge-base", base_ref, "HEAD"], repo).stdout.strip()
    diff = run(["git", "diff", f"{merge_base}...HEAD"], repo).stdout.rstrip("\n")
    return hashlib.sha256(diff.encode()).hexdigest()


def head_timestamp(repo: Path) -> int:
    cp = run(["git", "log", "-1", "--format=%ct"], repo)
    assert cp.returncode == 0
    return int(cp.stdout.strip())


def repo_snapshot(repo: Path) -> list[str]:
    return sorted(
        p.relative_to(repo).as_posix()
        for p in repo.rglob("*")
        if ".git" not in p.relative_to(repo).parts
    )


def assert_no_authority(decision: dict) -> None:
    for key in [
        "finalization_allowed",
        "commit_allowed",
        "push_allowed",
        "pr_allowed",
        "merge_allowed",
        "deploy_allowed",
        "release_allowed",
        "publish_allowed",
        "marker_write_allowed",
    ]:
        assert decision[key] is False


def test_git_probe_timeout_returns_json_fail_closed_envelope(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    state = repo / ".claude"
    state.mkdir()
    (state / "pr-review-passed.local").write_text("stale\n")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text("#!/bin/sh\nsleep 2\nexit 0\n")
    fake_git.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "HERMES_BUSDRIVER_LITMUS_GIT_TIMEOUT_SECONDS": "0.2",
    }

    cp = invoke_raw(repo, env=env)

    assert cp.returncode == 2
    data = json.loads(cp.stdout)
    assert data["ok"] is False
    assert data["repo"]["head"] is None
    assert data["decision"]["status"] == "blocked"
    assert any("git command timed out" in blocker for blocker in data["decision"]["blockers"])
    assert_no_authority(data["decision"])


def test_branch_diff_subprocess_timeout_fails_closed_when_pr_state_exists(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    state = repo / ".claude"
    state.mkdir()
    (state / "pr-review-passed.local").write_text("stale\n")
    real_git = shutil.which("git")
    assert real_git is not None
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text(
        "#!/bin/sh\n"
        "if [ \"$3\" = diff ]; then\n"
        "    sleep 2\n"
        "    exit 0\n"
        "fi\n"
        f"exec {real_git!r} \"$@\"\n"
    )
    fake_git.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "HERMES_BUSDRIVER_LITMUS_GIT_TIMEOUT_SECONDS": "0.2",
    }
    assert subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    ).returncode == 0

    cp = invoke_raw(repo, env=env)

    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert data["decision"]["status"] == "blocked"
    assert any("git command timed out" in blocker for blocker in data["decision"]["blockers"])
    assert_no_authority(data["decision"])


def test_safety_probe_timeout_fails_closed_when_pr_state_exists(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    state = repo / ".claude"
    state.mkdir()
    (state / "pr-review-passed.local").write_text("stale\n")
    real_git = shutil.which("git")
    assert real_git is not None
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text(
        "#!/bin/sh\n"
        "if [ \"$3\" = config ] && [ \"$4\" = --get ] && [ \"$5\" = diff.external ]; then\n"
        "    sleep 2\n"
        "    exit 0\n"
        "fi\n"
        f"exec {real_git!r} \"$@\"\n"
    )
    fake_git.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "HERMES_BUSDRIVER_LITMUS_GIT_TIMEOUT_SECONDS": "0.2",
    }
    assert subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    ).returncode == 0

    cp = invoke_raw(repo, env=env)

    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert data["decision"]["status"] == "blocked"
    assert any("git command timed out" in blocker for blocker in data["decision"]["blockers"])
    assert_no_authority(data["decision"])


def test_invalid_cli_invocation_emits_json_fail_closed_envelope():
    cp = subprocess.run(
        [sys.executable, str(SCRIPT), "--pr-artifact-max-age-seconds", "not-an-int"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode == 2
    data = json.loads(cp.stdout)
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert any("invalid_cli" in blocker for blocker in data["decision"]["blockers"])
    assert_no_authority(data["decision"])


def test_default_base_ref_uses_origin_head_before_origin_main(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    assert run(["git", "update-ref", "refs/remotes/origin/trunk", "main"], repo).returncode == 0
    assert run(["git", "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk"], repo).returncode == 0

    cp = invoke_raw_no_base(repo)
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)

    assert data["repo"]["base_ref"] == "origin/trunk"
    assert data["repo"]["branch_diff_hash"] == branch_diff_hash(repo, "origin/trunk")
    assert_no_authority(data["decision"])


def test_empty_repo_blocks_without_head(tmp_path: Path):
    repo = tmp_path / "empty"
    repo.mkdir()
    assert run(["git", "init"], repo).returncode == 0

    cp = invoke_raw(repo)

    assert cp.returncode == 2
    data = json.loads(cp.stdout)
    assert data["ok"] is False
    assert data["repo"]["head"] is None
    assert data["decision"]["status"] == "blocked"
    assert any("not_git_repo" in blocker for blocker in data["decision"]["blockers"])
    assert_no_authority(data["decision"])


def test_git_identity_env_does_not_override_repo_argument(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    other = init_repo(tmp_path / "other")
    env = {**os.environ, "GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other)}

    data = invoke(repo, env=env)

    assert data["repo"]["root"] == str(repo.resolve())
    assert data["repo"]["branch"] == "topic"
    assert data["repo"]["branch_diff_hash"] == branch_diff_hash(repo)
    assert_no_authority(data["decision"])


def test_missing_state_dir_is_read_only_stale_or_missing(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    before = repo_snapshot(repo)

    data = invoke(repo)

    assert before == repo_snapshot(repo)
    assert not (repo / ".claude").exists()
    assert data["schema"] == "hermes-busdriver-litmus-status/v0"
    assert data["read_only"] is True
    assert data["state_dir"]["exists"] is False
    assert data["decision"]["status"] == "stale_or_missing"
    assert_no_authority(data["decision"])


def test_commit_marker_newer_than_head_is_commit_litmus_fresh_without_authority(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    state = repo / ".claude"
    state.mkdir()
    marker = state / "litmus-passed.local"
    marker.write_text("external-review-pass\n")
    newer = head_timestamp(repo) + 2
    os.utime(marker, (newer, newer))

    data = invoke(repo)

    assert data["markers"]["litmus_passed"]["accepted_by_commit_gate"] is True
    assert data["markers"]["litmus_passed"]["fresh_for_head"] is True
    assert "value" not in data["markers"]["litmus_passed"]
    assert data["decision"]["status"] == "commit_litmus_fresh"
    assert_no_authority(data["decision"])


def test_unrecognized_commit_marker_newer_than_head_stays_stale_or_missing(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    state = repo / ".claude"
    state.mkdir()
    marker = state / "litmus-passed.local"
    marker.write_text("FAILED corrupted marker payload\n")
    newer = head_timestamp(repo) + 2
    os.utime(marker, (newer, newer))

    data = invoke(repo)

    litmus = data["markers"]["litmus_passed"]
    assert litmus["accepted_by_commit_gate"] is False
    assert litmus["fresh_for_head"] is False
    assert litmus["recognized_format"] == "unrecognized"
    assert data["decision"]["status"] == "stale_or_missing"
    assert_no_authority(data["decision"])


@pytest.mark.parametrize(
    "marker_text",
    ["SKIPPED-NONE-123", "BUILTIN-abc123", "PASS-123", "PASS-MERGE-123", "a" * 64],
)
def test_known_commit_marker_formats_remain_accepted(tmp_path: Path, marker_text: str):
    repo = init_repo(tmp_path / "repo")
    state = repo / ".claude"
    state.mkdir()
    marker = state / "litmus-passed.local"
    marker.write_text(f"{marker_text}\n")
    newer = head_timestamp(repo) + 2
    os.utime(marker, (newer, newer))

    data = invoke(repo)

    litmus = data["markers"]["litmus_passed"]
    assert litmus["accepted_by_commit_gate"] is True
    assert litmus["fresh_for_head"] is True
    assert data["decision"]["status"] == "commit_litmus_fresh"
    assert_no_authority(data["decision"])


def test_commit_marker_same_second_as_head_is_not_fresh(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    state = repo / ".claude"
    state.mkdir()
    marker = state / "litmus-passed.local"
    marker.write_text("external-review-pass\n")
    same_second = head_timestamp(repo)
    os.utime(marker, (same_second, same_second))

    data = invoke(repo)

    assert data["markers"]["litmus_passed"]["accepted_by_commit_gate"] is True
    assert data["markers"]["litmus_passed"]["fresh_for_head"] is False
    assert data["decision"]["status"] == "stale_or_missing"
    assert_no_authority(data["decision"])


def test_stale_commit_marker_is_not_commit_litmus_fresh(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    state = repo / ".claude"
    state.mkdir()
    marker = state / "litmus-passed.local"
    marker.write_text("external-review-pass\n")
    old = int(time.time()) - 7200
    os.utime(marker, (old, old))

    data = invoke(repo)

    assert data["markers"]["litmus_passed"]["accepted_by_commit_gate"] is True
    assert data["markers"]["litmus_passed"]["fresh_for_head"] is False
    assert data["decision"]["status"] == "stale_or_missing"
    assert_no_authority(data["decision"])


def test_all_pr_markers_matching_branch_diff_are_pr_review_fresh_without_authority(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    state = repo / ".claude"
    state.mkdir()
    diff_hash = branch_diff_hash(repo)
    now = int(time.time())
    (state / "pr-codex-lead.local.json").write_text(json.dumps({"status": "PASS", "diff_hash": diff_hash, "ts": now}))
    (state / "pr-backstop-verdict.local.json").write_text(json.dumps({"status": "PASS", "diff_hash": diff_hash, "ts": now}))
    (state / "pr-review-passed.local").write_text(f"{diff_hash}\n")

    data = invoke(repo)

    assert data["repo"]["branch_diff_hash"] == diff_hash
    assert data["markers"]["pr_codex_lead"]["fresh_for_branch_diff"] is True
    assert data["markers"]["pr_backstop_verdict"]["fresh_for_branch_diff"] is True
    assert data["markers"]["pr_review_passed"]["fresh_for_branch_diff"] is True
    assert data["decision"]["status"] == "pr_review_fresh"
    assert_no_authority(data["decision"])


def test_pr_hash_marker_with_extra_spaces_is_not_fresh(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    state = repo / ".claude"
    state.mkdir()
    diff_hash = branch_diff_hash(repo)
    now = int(time.time())
    (state / "pr-codex-lead.local.json").write_text(json.dumps({"status": "PASS", "diff_hash": diff_hash, "ts": now}))
    (state / "pr-backstop-verdict.local.json").write_text(json.dumps({"status": "PASS", "diff_hash": diff_hash, "ts": now}))
    (state / "pr-review-passed.local").write_text(f" {diff_hash} \n")

    data = invoke(repo)

    assert data["markers"]["pr_review_passed"]["fresh_for_branch_diff"] is False
    assert data["markers"]["pr_review_passed"]["recognized_format"] == "unrecognized"
    assert data["decision"]["status"] == "stale_or_missing"
    assert_no_authority(data["decision"])


def test_marker_values_are_not_emitted_and_symlinks_are_not_followed(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    state = repo / ".claude"
    state.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("local secret that must not leak\n")
    (state / "litmus-passed.local").symlink_to(secret)

    data = invoke(repo)

    marker = data["markers"]["litmus_passed"]
    assert marker["exists"] is True
    assert marker["is_symlink"] is True
    assert marker["accepted_by_commit_gate"] is False
    assert "value" not in marker
    assert "local secret" not in json.dumps(data)
    assert data["decision"]["status"] == "stale_or_missing"
    assert_no_authority(data["decision"])


def test_marker_non_regular_and_large_files_are_not_read(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    state = repo / ".claude"
    state.mkdir()
    os.mkfifo(state / "litmus-passed.local")
    (state / "pr-codex-lead.local.json").write_text("x" * 70000)

    data = invoke(repo)

    litmus = data["markers"]["litmus_passed"]
    lead = data["markers"]["pr_codex_lead"]
    assert litmus["exists"] is True
    assert litmus["read_error"] == "refusing_to_read_non_regular_file"
    assert lead["read_error"] == "refusing_to_read_large_marker"
    assert data["decision"]["status"] == "blocked"
    assert any("empty diff" in blocker for blocker in data["decision"]["blockers"])
    assert_no_authority(data["decision"])


def test_state_dir_symlink_is_not_followed(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    outside = tmp_path / "outside-state"
    outside.mkdir()
    (outside / "litmus-passed.local").write_text("external-review-pass\n")
    (repo / ".claude").symlink_to(outside)

    data = invoke(repo)

    assert data["state_dir"]["is_symlink"] is True
    assert data["markers"]["litmus_passed"]["state_dir_unsafe"] is True
    assert data["markers"]["litmus_passed"]["accepted_by_commit_gate"] is False
    assert data["decision"]["status"] == "stale_or_missing"
    assert_no_authority(data["decision"])


def test_json_pr_artifact_raw_fields_are_not_emitted(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    state = repo / ".claude"
    state.mkdir()
    diff_hash = branch_diff_hash(repo)
    payload_text = "marker-payload-that-must-not-leak"
    now = int(time.time())
    (state / "pr-codex-lead.local.json").write_text(json.dumps({"status": payload_text, "diff_hash": {"leak": payload_text}, "ts": payload_text}))
    (state / "pr-backstop-verdict.local.json").write_text(json.dumps({"status": "PASS", "diff_hash": diff_hash, "ts": now}))
    (state / "pr-review-passed.local").write_text(f"{diff_hash}\n")

    data = invoke(repo)
    payload = json.dumps(data)

    marker = data["markers"]["pr_codex_lead"]
    assert marker["fresh_for_branch_diff"] is False
    assert marker["status_is_pass"] is False
    assert marker["diff_hash_matches"] is False
    assert marker["ts_valid"] is False
    assert "status" not in marker
    assert "diff_hash" not in marker
    assert "ts" not in marker
    assert payload_text not in payload
    assert_no_authority(data["decision"])


def test_state_dir_parent_symlink_component_is_not_followed(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    outside = tmp_path / "outside-state"
    outside_state = outside / ".claude"
    outside_state.mkdir(parents=True)
    (outside_state / "litmus-passed.local").write_text("external-review-pass\n")
    (repo / "state-link").symlink_to(outside)

    data = invoke(repo, "--state-dir-name", "state-link/.claude")

    assert data["state_dir"]["exists"] is False
    assert data["state_dir"]["has_symlink_component"] is True
    assert data["markers"]["litmus_passed"]["state_dir_unsafe"] is True
    assert data["markers"]["litmus_passed"]["accepted_by_commit_gate"] is False
    assert data["decision"]["status"] == "stale_or_missing"
    assert_no_authority(data["decision"])


def test_pr_artifacts_require_fresh_integer_ts(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    state = repo / ".claude"
    state.mkdir()
    diff_hash = branch_diff_hash(repo)
    expired = int(time.time()) - 7200
    (state / "pr-codex-lead.local.json").write_text(json.dumps({"status": "PASS", "diff_hash": diff_hash, "ts": expired}))
    (state / "pr-backstop-verdict.local.json").write_text(json.dumps({"status": "PASS", "diff_hash": diff_hash, "ts": int(time.time())}))
    (state / "pr-review-passed.local").write_text(f"{diff_hash}\n")

    data = invoke(repo, "--pr-artifact-max-age-seconds", "3600")

    assert data["markers"]["pr_codex_lead"]["fresh_for_branch_diff"] is False
    assert data["markers"]["pr_codex_lead"]["age_seconds"] >= 3600
    assert data["decision"]["status"] == "stale_or_missing"
    assert_no_authority(data["decision"])


def test_branch_diff_hash_blocks_ambient_git_diff_opts_when_pr_state_exists(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    state = repo / ".claude"
    state.mkdir()
    diff_hash = branch_diff_hash(repo)
    now = int(time.time())
    payload_text = "ambient-git-diff-opts-marker-payload-that-must-not-leak"
    lead_marker = {"status": "PASS", "diff_hash": diff_hash, "ts": now, "note": payload_text}
    backstop_marker = {"status": "PASS", "diff_hash": diff_hash, "ts": now, "note": payload_text}
    (state / "pr-codex-lead.local.json").write_text(json.dumps(lead_marker))
    (state / "pr-backstop-verdict.local.json").write_text(json.dumps(backstop_marker))
    (state / "pr-review-passed.local").write_text(f"{diff_hash}\n")
    env = isolated_git_env(GIT_DIFF_OPTS="--unified=0")

    data = invoke(repo, env=env)
    output = json.dumps(data)

    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert data["decision"]["status"] == "blocked"
    assert any(
        "GIT_DIFF_OPTS" in blocker or "diff opts configured" in blocker
        for blocker in data["decision"]["blockers"]
    )
    assert payload_text not in output
    assert_no_authority(data["decision"])


def test_branch_diff_hash_blocks_without_executing_external_diff(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "pr-review-passed.local").write_text("stale\n")
    sentinel = tmp_path / "external-diff-ran"
    external = tmp_path / "external-diff.sh"
    external.write_text(f"#!/bin/sh\ntouch {sentinel}\nexit 0\n")
    external.chmod(0o755)
    env = {**os.environ, "GIT_EXTERNAL_DIFF": str(external)}

    data = invoke(repo, env=env)

    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert any("external diff configured" in blocker for blocker in data["decision"]["blockers"])
    assert not sentinel.exists()
    assert data["decision"]["status"] == "blocked"
    assert_no_authority(data["decision"])


def test_branch_diff_hash_blocks_external_diff_driver_command(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "pr-review-passed.local").write_text("stale\n")
    sentinel = tmp_path / "driver-command-ran"
    driver = tmp_path / "driver.sh"
    driver.write_text(f"#!/bin/sh\ntouch {sentinel}\nexit 0\n")
    driver.chmod(0o755)
    assert run(["git", "config", "diff.pwn.command", str(driver)], repo).returncode == 0
    (repo / ".gitattributes").write_text("*.txt diff=pwn\n")

    data = invoke(repo)

    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert any("external diff configured" in blocker for blocker in data["decision"]["blockers"])
    assert not sentinel.exists()
    assert data["decision"]["status"] == "blocked"
    assert_no_authority(data["decision"])


def test_branch_diff_hash_blocks_global_external_diff_config(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "pr-review-passed.local").write_text("stale\n")
    global_config = tmp_path / "gitconfig"
    global_config.write_text("[diff \"pwn\"]\n\tcommand = /tmp/should-not-run\n")
    env = {**os.environ, "GIT_CONFIG_GLOBAL": str(global_config)}

    data = invoke(repo, env=env)

    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert any("external diff configured" in blocker for blocker in data["decision"]["blockers"])
    assert data["decision"]["status"] == "blocked"
    assert_no_authority(data["decision"])


def test_branch_diff_hash_blocks_ignored_untracked_gitattributes(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "pr-review-passed.local").write_text("stale\n")
    (repo / ".gitignore").write_text(".gitattributes\n")
    (repo / ".gitattributes").write_text("*.txt diff=word\n")

    data = invoke(repo)

    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert any("diff attributes configured" in blocker for blocker in data["decision"]["blockers"])
    assert data["decision"]["status"] == "blocked"
    assert_no_authority(data["decision"])


def test_branch_diff_hash_blocks_gitattributes_diff_selection(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "pr-review-passed.local").write_text("stale\n")
    (repo / ".gitattributes").write_text("*.txt diff=word\n")

    data = invoke(repo)

    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert any("diff attributes configured" in blocker for blocker in data["decision"]["blockers"])
    assert data["decision"]["status"] == "blocked"
    assert_no_authority(data["decision"])


def test_branch_diff_hash_blocks_nested_gitattributes_when_pathspec_env_is_set(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "pr-review-passed.local").write_text("stale\n")
    nested = repo / "nested"
    nested.mkdir()
    (nested / ".gitattributes").write_text("*.txt diff=word\n")
    env = {**os.environ, "GIT_LITERAL_PATHSPECS": "1"}

    data = invoke(repo, env=env)

    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert any("diff attributes configured" in blocker for blocker in data["decision"]["blockers"])
    assert data["decision"]["status"] == "blocked"
    assert_no_authority(data["decision"])


def test_branch_diff_hash_blocks_git_info_attributes(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "pr-review-passed.local").write_text("stale\n")
    git_dir = run(["git", "rev-parse", "--git-dir"], repo).stdout.strip()
    info_attrs = repo / git_dir / "info" / "attributes"
    info_attrs.write_text("*.txt diff=word\n")

    data = invoke(repo)

    assert data["ok"] is False
    assert any("diff attributes configured" in blocker for blocker in data["decision"]["blockers"])
    assert data["decision"]["status"] == "blocked"
    assert_no_authority(data["decision"])


def test_branch_diff_hash_blocks_empty_git_info_attributes(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "pr-review-passed.local").write_text("stale\n")
    git_dir = run(["git", "rev-parse", "--git-dir"], repo).stdout.strip()
    info_attrs = repo / git_dir / "info" / "attributes"
    info_attrs.write_text("")

    data = invoke(repo)

    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert any("diff attributes configured" in blocker for blocker in data["decision"]["blockers"])
    assert data["decision"]["status"] == "blocked"
    assert_no_authority(data["decision"])


def test_branch_diff_hash_blocks_fifo_git_info_attributes_without_hanging(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "pr-review-passed.local").write_text("stale\n")
    git_dir = run(["git", "rev-parse", "--git-dir"], repo).stdout.strip()
    info_attrs = repo / git_dir / "info" / "attributes"
    os.mkfifo(info_attrs)

    cp = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--base-ref", "main"],
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    assert cp.returncode == 0, cp.stderr
    data = json.loads(cp.stdout)

    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert any("diff attributes configured" in blocker for blocker in data["decision"]["blockers"])
    assert data["decision"]["status"] == "blocked"
    assert_no_authority(data["decision"])


def test_branch_diff_hash_blocks_core_attributes_file(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "pr-review-passed.local").write_text("stale\n")
    attrs = tmp_path / "attrs"
    attrs.write_text("*.txt diff=word\n")
    assert run(["git", "config", "core.attributesFile", str(attrs)], repo).returncode == 0

    data = invoke(repo)

    assert data["ok"] is False
    assert any("diff attributes configured" in blocker for blocker in data["decision"]["blockers"])
    assert data["decision"]["status"] == "blocked"
    assert_no_authority(data["decision"])


def test_branch_diff_hash_blocks_default_home_git_attributes_when_core_attributes_unset(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "pr-review-passed.local").write_text("stale\n")
    home = tmp_path / "home"
    attrs = home / ".config" / "git" / "attributes"
    attrs.parent.mkdir(parents=True)
    payload_text = "home-attributes-payload-must-not-leak"
    attrs.write_text(f"*.txt diff={payload_text}\n")
    env = isolated_git_env(HOME=str(home), GIT_CONFIG_GLOBAL=str(tmp_path / "empty-global-config"))

    data = invoke(repo, env=env)

    payload = json.dumps(data)
    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert any("diff attributes configured" in blocker for blocker in data["decision"]["blockers"])
    assert payload_text not in payload
    assert str(attrs) not in payload
    assert data["decision"]["status"] == "blocked"
    assert_no_authority(data["decision"])


def test_branch_diff_hash_blocks_default_xdg_git_attributes_when_core_attributes_unset(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "pr-review-passed.local").write_text("stale\n")
    home = tmp_path / "home"
    home.mkdir()
    xdg = tmp_path / "xdg"
    attrs = xdg / "git" / "attributes"
    attrs.parent.mkdir(parents=True)
    payload_text = "xdg-attributes-payload-must-not-leak"
    attrs.write_text(f"*.txt diff={payload_text}\n")
    env = isolated_git_env(
        HOME=str(home),
        XDG_CONFIG_HOME=str(xdg),
        GIT_CONFIG_GLOBAL=str(tmp_path / "empty-global-config"),
    )

    data = invoke(repo, env=env)

    payload = json.dumps(data)
    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert any("diff attributes configured" in blocker for blocker in data["decision"]["blockers"])
    assert payload_text not in payload
    assert str(attrs) not in payload
    assert data["decision"]["status"] == "blocked"
    assert_no_authority(data["decision"])


def test_default_global_attributes_detection_uses_sanitized_git_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = init_repo(tmp_path / "repo", branch=True)
    ambient_home = tmp_path / "ambient-home"
    attrs = ambient_home / ".config" / "git" / "attributes"
    attrs.parent.mkdir(parents=True)
    attrs.write_text("*.txt diff=ambient\n")
    monkeypatch.setenv("HOME", str(ambient_home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    module = load_litmus_status_module()

    def sanitized_without_home(extra_remove: set[str] | None = None) -> dict[str, str]:
        remove = {"HOME", "XDG_CONFIG_HOME"}
        if extra_remove:
            remove |= extra_remove
        return {key: value for key, value in os.environ.items() if key not in remove}

    monkeypatch.setattr(module, "sanitized_git_env", sanitized_without_home)

    configured, safety_error = module.diff_attributes_configured(repo)

    assert safety_error is None
    assert configured is False


@pytest.mark.parametrize(
    "marker_text",
    [
        "",
        "secret-marker-payload-must-not-leak",
        "PASS-FAST-secret-marker-payload-must-not-leak-123",
        "PASS-FAST-" + ("0" * 64),
        "PASS-SLOW-" + ("0" * 64) + "-123",
        "A" * 64,
        "0" * 63,
        " " + ("0" * 64),
        ("0" * 64) + " extra",
        '{"diff_hash":"secret-marker-payload-must-not-leak"}',
    ],
)
def test_unrecognized_pr_marker_strings_never_leak_or_freshen(tmp_path: Path, marker_text: str):
    repo = init_repo(tmp_path / "repo", branch=True)
    state = repo / ".claude"
    state.mkdir()
    diff_hash = branch_diff_hash(repo)
    now = int(time.time())
    (state / "pr-codex-lead.local.json").write_text(json.dumps({"status": "PASS", "diff_hash": diff_hash, "ts": now}))
    (state / "pr-backstop-verdict.local.json").write_text(json.dumps({"status": "PASS", "diff_hash": diff_hash, "ts": now}))
    (state / "pr-review-passed.local").write_text(marker_text)

    data = invoke(repo)

    payload = json.dumps(data)
    marker = data["markers"]["pr_review_passed"]
    assert marker["fresh_for_branch_diff"] is False
    assert marker["recognized_format"] == "unrecognized"
    if marker_text:
        assert marker_text not in payload
    assert "secret-marker-payload-must-not-leak" not in payload
    assert data["decision"]["status"] == "stale_or_missing"
    assert_no_authority(data["decision"])


@pytest.mark.parametrize(
    ("input_payload", "status_is_pass", "diff_hash_matches", "ts_valid"),
    [
        ("not-json secret-json-payload-must-not-leak", False, False, False),
        (["secret-json-payload-must-not-leak"], False, False, False),
        ({"status": "FAIL secret-json-payload-must-not-leak", "diff_hash": "MATCH", "ts": "NOW"}, False, True, True),
        ({"status": "PASS", "diff_hash": "secret-json-payload-must-not-leak", "ts": "NOW"}, True, False, True),
        ({"status": "PASS", "diff_hash": "MATCH", "ts": "secret-json-payload-must-not-leak"}, True, True, False),
        ({"status": "PASS", "diff_hash": "MATCH", "ts": True}, True, True, False),
        ({"status": "PASS", "diff_hash": "MATCH", "ts": "FUTURE"}, True, True, True),
    ],
)
def test_randomish_pr_json_payloads_never_leak_and_only_exact_freshen(
    tmp_path: Path, input_payload: object, status_is_pass: bool, diff_hash_matches: bool, ts_valid: bool
):
    repo = init_repo(tmp_path / "repo", branch=True)
    state = repo / ".claude"
    state.mkdir()
    diff_hash = branch_diff_hash(repo)
    now = int(time.time())
    future = now + 7200
    if isinstance(input_payload, dict):
        materialized = {
            key: (diff_hash if value == "MATCH" else now if value == "NOW" else future if value == "FUTURE" else value)
            for key, value in input_payload.items()
        }
        payload_text = json.dumps(materialized)
    elif isinstance(input_payload, str):
        payload_text = input_payload
    else:
        payload_text = json.dumps(input_payload)
    (state / "pr-codex-lead.local.json").write_text(payload_text)
    (state / "pr-backstop-verdict.local.json").write_text(json.dumps({"status": "PASS", "diff_hash": diff_hash, "ts": now}))
    (state / "pr-review-passed.local").write_text(f"{diff_hash}\n")

    data = invoke(repo)

    output = json.dumps(data)
    marker = data["markers"]["pr_codex_lead"]
    assert marker["fresh_for_branch_diff"] is False
    assert marker["status_is_pass"] is status_is_pass
    assert marker["diff_hash_matches"] is diff_hash_matches
    assert marker["ts_valid"] is ts_valid
    assert "status" not in marker
    assert "diff_hash" not in marker
    assert "ts" not in marker
    assert payload_text not in output
    assert "secret-json-payload-must-not-leak" not in output
    assert data["decision"]["status"] == "stale_or_missing"
    assert_no_authority(data["decision"])


def test_stale_and_malformed_pr_markers_stay_stale_or_missing(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    state = repo / ".claude"
    state.mkdir()
    (state / "pr-codex-lead.local.json").write_text("{bad json")
    (state / "pr-backstop-verdict.local.json").write_text(json.dumps({"status": "PASS", "diff_hash": "stale", "ts": int(time.time())}))
    (state / "pr-review-passed.local").write_text("stale\n")

    data = invoke(repo)

    assert data["markers"]["pr_codex_lead"]["fresh_for_branch_diff"] is False
    assert data["markers"]["pr_codex_lead"]["parse_error"]
    assert data["markers"]["pr_backstop_verdict"]["fresh_for_branch_diff"] is False
    assert data["markers"]["pr_review_passed"]["fresh_for_branch_diff"] is False
    assert data["decision"]["status"] == "stale_or_missing"
    assert_no_authority(data["decision"])


def test_base_ref_failure_blocks_when_pr_marker_state_exists(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    state = repo / ".claude"
    state.mkdir()
    (state / "pr-review-passed.local").write_text("stale\n")
    cp = invoke_raw(repo, "--base-ref", "does-not-exist")

    assert cp.returncode == 0
    data = json.loads(cp.stdout)
    assert data["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert any("branch_diff_hash_unavailable" in blocker for blocker in data["decision"]["blockers"])
    assert data["repo"]["branch_diff_hash"] is None
    assert_no_authority(data["decision"])


def test_base_ref_failure_does_not_block_fresh_commit_marker(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    state = repo / ".claude"
    state.mkdir()
    marker = state / "litmus-passed.local"
    marker.write_text("external-review-pass\n")
    newer = head_timestamp(repo) + 2
    os.utime(marker, (newer, newer))

    data = invoke(repo, "--base-ref", "does-not-exist")

    assert data["ok"] is True
    assert data["repo"]["branch_diff_hash"] is None
    assert any("branch_diff_hash_unavailable" in warning for warning in data["decision"]["warnings"])
    assert data["markers"]["litmus_passed"]["fresh_for_head"] is True
    assert data["decision"]["status"] == "commit_litmus_fresh"
    assert_no_authority(data["decision"])


def test_git_trace_env_does_not_write_trace_files(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    trace = tmp_path / "git-trace.log"
    trace2 = tmp_path / "git-trace2-event.log"
    env = {**os.environ, "GIT_TRACE": str(trace), "GIT_TRACE2_EVENT": str(trace2)}

    data = invoke(repo, env=env)

    assert data["repo"]["branch_diff_hash"] == branch_diff_hash(repo)
    assert not trace.exists()
    assert not trace2.exists()
    assert_no_authority(data["decision"])


def test_empty_branch_diff_blocks_without_empty_hash(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    state = repo / ".claude"
    state.mkdir()
    empty_hash = hashlib.sha256(b"").hexdigest()
    now = int(time.time())
    (state / "pr-codex-lead.local.json").write_text(json.dumps({"status": "PASS", "diff_hash": empty_hash, "ts": now}))
    (state / "pr-backstop-verdict.local.json").write_text(json.dumps({"status": "PASS", "diff_hash": empty_hash, "ts": now}))
    (state / "pr-review-passed.local").write_text(f"{empty_hash}\n")

    data = invoke(repo)

    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert data["decision"]["status"] == "blocked"
    assert any("empty diff" in blocker for blocker in data["decision"]["blockers"])
    assert_no_authority(data["decision"])
