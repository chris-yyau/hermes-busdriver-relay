import argparse
import ast
import hashlib
import json
import os
import re
import runpy
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from pr_grind_fixtures import GITHUB_ORIGIN, bind_github_origin, pr_grind_payload

# Mirrors ENTRY_LIST_BYTE_LIMIT in scripts/hermes-busdriver-delivery-status.
DELIVERY_STATUS_ENTRY_LIST_BYTE_LIMIT = 16000


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "scripts" / "hermes-busdriver-delivery-status"
# Source-separated, never installed: the only entrypoint that can inject a helper double.
STATUS_HARNESS = ROOT / "tests" / "fixtures" / "delivery-status-test-harness"
PHASE0_STATUS = ROOT / "scripts" / "hermes-busdriver-status"
LOCK = ROOT / "scripts" / "hermes-busdriver-lock"


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=False)


def patch_bounded_run(monkeypatch, mod: dict[str, Any], fake_run) -> None:
    """Bind a subprocess.run-shaped test double to the bounded production seam.

    The double replaces the primitive, so it also replaces the primitive's CONTRACT — and the two
    halves it used to drop are the two this repo cares about.

    `limit` was a named sink: declared so the call would not TypeError, then never read. Production
    spells it `limit: int = MAX_CAPTURED_BYTES`, and a default is frozen at def time, so a double
    that lets it default to `None` is not a lenient double — it is a different contract, one under
    which a production caller that dropped the bound still passes. Defaulting to the module's own
    constant means a site omitting `limit` is exercised against exactly the number production would
    have used, and a site that WEAKENS it is exercised against the weakened one, where the overflow
    assertion below can see it.

    And `overflowed` was hardcoded `False`, so no test reaching this seam could ever observe the
    refusal — `_bounded_run`'s `RuntimeError("child_output_too_large")` and `git_raw`'s
    `git_output_too_large` were unreachable through the fake, and a double could hand back oversized
    bytes as though they had arrived, which is the one shape production cannot produce. Production
    bounds at the pipe and REFUSES over it rather than slicing (a slice cuts the `token:` prefix off
    a secret and emits the remainder as ordinary text), so the double refuses the same way.
    """
    BoundedOutput = mod["BoundedOutput"]

    def bounded(cmd, *, cwd=None, env=None, timeout=None, stdin_bytes=None, limit=None, text=True):
        # Production's default, not None: a caller that omits the bound must still be bound.
        effective_limit = mod["MAX_CAPTURED_BYTES"] if limit is None else limit
        kwargs = {
            "cwd": str(cwd) if cwd else None,
            "env": env,
            "timeout": timeout,
            "text": text,
            "capture_output": True,
            "check": False,
        }
        if stdin_bytes is not None:
            kwargs["input"] = stdin_bytes.decode() if text else stdin_bytes
        try:
            cp = fake_run(cmd, **kwargs)
        except subprocess.TimeoutExpired as exc:
            empty = "" if text else b""
            stdout = exc.output if exc.output is not None else empty
            stderr = exc.stderr if exc.stderr is not None else empty
            return BoundedOutput(124, stdout, stderr, False, True)
        # Production counts what the child SAID and refuses BOTH streams if either exceeded the
        # bound. `>` not `>=`: exactly `limit` bytes is not an overflow.
        measured = max(
            len(cp.stdout) if cp.stdout is not None else 0,
            len(cp.stderr) if cp.stderr is not None else 0,
        )
        if measured > effective_limit:
            return BoundedOutput(cp.returncode, "" if text else b"", "" if text else b"", True, False)
        return BoundedOutput(cp.returncode, cp.stdout, cp.stderr, False, False)

    monkeypatch.setitem(mod["run"].__globals__, "run_bounded", bounded)


def init_repo(path: Path) -> Path:
    path.mkdir()
    assert run(["git", "init"], path).returncode == 0
    assert run(["git", "config", "user.email", "test@example.test"], path).returncode == 0
    assert run(["git", "config", "user.name", "Test User"], path).returncode == 0
    (path / "README.md").write_text("# test\n")
    assert run(["git", "add", "README.md"], path).returncode == 0
    assert run(["git", "commit", "-m", "init"], path).returncode == 0
    return path


def fake_busdriver(path: Path) -> Path:
    files = {
        "package.json": '{"version":"1.71.0"}\n',
        "scripts/relevant-check-status.sh": "#!/bin/sh\ncat >/dev/null\nprintf '0 0 all 1\\n'\n",
        "scripts/ack-ledger.sh": "#!/bin/sh\nprintf 'none\\n'\n",
        "scripts/fetch-pr-state.sh": "#!/bin/sh\ntrue\n",
        "hooks/gate-scripts/pre-pr-gate.sh": "#!/bin/sh\ntrue\n",
        "hooks/gate-scripts/pre-merge-gate.sh": "#!/bin/sh\ntrue\n",
        "opencode/skills/pr-grind/SKILL.md": "# pr-grind\n",
        "opencode/agents/pr-grinder.md": "# pr-grinder\n",
    }
    for rel, content in files.items():
        p = path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        if rel.startswith("scripts/") or rel.startswith("hooks/"):
            p.chmod(0o755)
    return path


CUSTOM_HELPER_SCRIPT_FLAGS = ("--pr-grind-check-script", "--litmus-status-script", "--relay-role-script")
# v16-r33 A: a caller-supplied RESULT file is the same declaration of a double as a caller-named
# script — the bytes are authored by whoever wrote them either way — so it routes to the harness too.
FIXTURE_RESULT_FLAGS = ("--pr-grind-result-file", "--litmus-status-result-file")
FIXTURE_ROUTED_FLAGS = CUSTOM_HELPER_SCRIPT_FLAGS + FIXTURE_RESULT_FLAGS


def status_entrypoint(extra: tuple[str, ...]) -> Path:
    """Naming a helper script IS declaring a fixture double, so these helpers route accordingly.

    v16-r32 item 1: production delivery-status has no path to a caller-named executable at all —
    not even behind a flag, because the caller that names the program is the caller that would
    pass the flag. The doubles live behind the source-separated harness instead. Every test that
    names a helper is by definition testing a double, so the routing happens here rather than at
    ~15 call sites. Tests that mean to exercise the production refusal build their argv against
    STATUS directly and therefore never pass through here.
    """
    if any(flag in extra for flag in FIXTURE_ROUTED_FLAGS):
        return STATUS_HARNESS
    return STATUS


def invoke(repo: Path, plugin: Path, *extra: str, cwd: Path | None = None) -> dict:
    cp = run([sys.executable, str(status_entrypoint(extra)), "--repo", str(repo), "--plugin-root", str(plugin), "--no-lock-status", "--no-agent-runs", *extra], cwd=cwd)
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return json.loads(cp.stdout)


def invoke_with_lock_status(repo: Path, plugin: Path, state: Path, *extra: str) -> dict:
    cp = run([sys.executable, str(status_entrypoint(extra)), "--repo", str(repo), "--plugin-root", str(plugin), "--state-dir", str(state), "--no-agent-runs", *extra])
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return json.loads(cp.stdout)


def litmus_status_fixture(
    path: Path,
    *,
    repo: Path | None = None,
    status: str = "stale_or_missing",
    ok: object = True,
    authority_safe: bool = True,
    authority_true_key: str = "finalization_allowed",
    malicious_sentinel: str | None = None,
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
    if not authority_safe:
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
        "litmus_passed": {"path": str(state_dir / "litmus-passed.local"), "exists": False, "fresh_for_head": False},
        "pr_codex_lead": {"path": str(state_dir / "pr-codex-lead.local.json"), "exists": False, "fresh_for_branch_diff": False},
        "pr_backstop_verdict": {"path": str(state_dir / "pr-backstop-verdict.local.json"), "exists": False, "fresh_for_branch_diff": False},
        "pr_review_passed": {"path": str(state_dir / "pr-review-passed.local"), "exists": False, "fresh_for_branch_diff": False},
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


def assert_no_delivery_authority(authority: dict) -> None:
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
        assert authority[key] is False


def relay_config(path: Path, route: object) -> Path:
    path.write_text(json.dumps({
        "coding_agent": "opencode",
        "avoid_coding_agent_for_review": True,
        "routes": {"relay.pr.backstop": route},
    }))
    return path


def snapshot_files(path: Path) -> dict[str, str]:
    out = {}
    for root, _dirs, files in os.walk(path):
        for name in files:
            p = Path(root) / name
            out[str(p.relative_to(path))] = p.read_text(errors="ignore")
    return out


def test_dirty_draft_status_is_read_only_and_non_finalizing(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    before_repo = snapshot_files(repo)
    before_plugin = snapshot_files(plugin)

    data = invoke(repo, plugin)

    assert data["schema"] == "hermes-busdriver-delivery-status/v0"
    assert data["read_only"] is True
    assert data["repo"]["dirty"] is True
    assert data["decision"]["status"] == "draft_changes_need_busdriver_finalization"
    assert_no_delivery_authority(data["decision"])
    assert snapshot_files(repo) == before_repo
    assert snapshot_files(plugin) == before_plugin


def test_untracked_files_are_not_reported_as_unstaged(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "new.txt").write_text("new\n")

    data = invoke(repo, plugin)

    assert data["repo"]["untracked_entries"] == ["?? new.txt"]
    assert data["repo"]["unstaged_entries"] == []


def test_dirty_draft_includes_read_only_litmus_status_stale_warning(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "litmus-status.json", repo=repo)

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    # r24: the fixture blocks the envelope on provenance, but its stale/missing signal still
    # propagates as a warning and the summary is still sanitized and readable as a diagnostic.
    assert data["decision"]["status"] == "blocked"
    assert "fixture_evidence_not_authoritative" in data["decision"]["blockers"]
    assert "litmus_pre_pr_stale_or_missing" in data["decision"]["warnings"]
    assert data["litmus_status"]["available"] is True
    assert data["litmus_status"]["ok"] is True
    assert data["litmus_status"]["summary"]["schema"] == "hermes-busdriver-litmus-status/v0"
    assert data["litmus_status"]["summary"]["read_only"] is True
    assert data["litmus_status"]["summary"]["decision"]["status"] == "stale_or_missing"
    assert data["litmus_status"]["summary"]["decision"]["finalization_allowed"] is False
    assert data["litmus_status"]["summary"]["decision"]["marker_write_allowed"] is False
    assert data["litmus_status"]["summary"]["markers"]["litmus_passed"]["exists"] is False
    assert_no_delivery_authority(data["decision"])


def test_delivery_status_accepts_compatible_drift_baseline_as_phase0_evidence(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    baseline = drift_baseline_fixture(tmp_path / "baseline.json", plugin)

    data = invoke(repo, plugin, "--drift-baseline", str(baseline))

    drift = data["phase0_status"]["busdriver_drift"]
    assert drift["status"] == "compatible"
    assert drift["finalization_compatible"] is True
    assert "busdriver_drift_incompatible" not in data["decision"]["blockers"]
    assert data["decision"]["status"] == "draft_changes_need_busdriver_finalization"
    assert_no_delivery_authority(data["decision"])


def test_phase0_status_forwards_requested_repo_even_when_parent_repo_status_failed(monkeypatch, tmp_path: Path):
    mod = __import__("runpy").run_path(str(STATUS))
    plugin = fake_busdriver(tmp_path / "busdriver")
    requested_repo = tmp_path / "not-a-git-repo"
    requested_repo.mkdir()
    baseline = tmp_path / "baseline.json"
    baseline.write_text("{}\n")
    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], cwd: Path | None = None, timeout: int = 60, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        payload = {
            "status_schema": "hermes-busdriver-status/v0",
            "read_only": True,
            "repo": {"path": str(requested_repo), "is_git_repo": False},
            "plugin_root": {"path": str(plugin), "exists": True},
            "busdriver_drift": {"status": "baseline_invalid", "finalization_compatible": False},
        }
        return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")

    monkeypatch.setitem(mod["run_phase0_status"].__globals__, "run", fake_run)
    args = __import__("types").SimpleNamespace(
        repo=str(requested_repo),
        drift_baseline=str(baseline),
        phase0_status_timeout=7,
        busdriver_state_dir_name=None,
        state_dir=None,
    )

    data = mod["run_phase0_status"](args, {"ok": False, "path": str(requested_repo)}, {"ok": True, "plugin_root": str(plugin)})

    cmd = captured["cmd"]
    assert data["status_schema"] == "hermes-busdriver-status/v0"
    assert "--repo" in cmd
    assert cmd[cmd.index("--repo") + 1] == str(requested_repo)
    assert captured["cwd"] is None
    assert captured["timeout"] == 7


def test_delivery_status_preserves_relative_drift_baseline_cwd_semantics(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    caller = tmp_path / "caller"
    caller.mkdir()
    (repo / "src.txt").write_text("draft\n")
    drift_baseline_fixture(caller / "baseline.json", plugin)
    (repo / "baseline.json").write_text("{not-json\n")

    data = invoke(repo, plugin, "--drift-baseline", "baseline.json", cwd=caller)

    drift = data["phase0_status"]["busdriver_drift"]
    assert drift["baseline_path"] == str(caller / "baseline.json")
    assert drift["status"] == "compatible"
    assert drift["finalization_compatible"] is True
    assert data["decision"]["status"] == "draft_changes_need_busdriver_finalization"
    assert "busdriver_drift_incompatible" not in data["decision"]["blockers"]


def test_delivery_status_blocks_when_drift_baseline_is_drifted(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    baseline = drift_baseline_fixture(tmp_path / "baseline.json", plugin)
    (plugin / "package.json").write_text('{"version":"9.99.0"}\n')

    data = invoke(repo, plugin, "--drift-baseline", str(baseline))

    drift = data["phase0_status"]["busdriver_drift"]
    assert drift["status"] == "drifted"
    assert drift["finalization_compatible"] is False
    assert data["decision"]["status"] == "blocked"
    assert "busdriver_drift_incompatible" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


@pytest.mark.parametrize("baseline_name, baseline_content, expected_status", [
    ("invalid-baseline.json", "{not-json\n", "baseline_invalid"),
    ("missing-baseline.json", None, "baseline_missing"),
])
def test_delivery_status_blocks_when_drift_baseline_is_invalid_or_missing(tmp_path: Path, baseline_name: str, baseline_content: str | None, expected_status: str):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    baseline = tmp_path / baseline_name
    if baseline_content is not None:
        baseline.write_text(baseline_content)

    data = invoke(repo, plugin, "--drift-baseline", str(baseline))

    drift = data["phase0_status"]["busdriver_drift"]
    assert drift["status"] == expected_status
    assert drift["finalization_compatible"] is False
    assert data["decision"]["status"] == "blocked"
    assert "busdriver_drift_incompatible" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


@pytest.mark.parametrize("identity_error", ["root", "branch", "head", "missing_branch", "missing_head"])
def test_litmus_status_repo_identity_mismatch_fails_closed(tmp_path: Path, identity_error: str):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
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

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_schema_invalid"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_schema_invalid" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_unavailable_blocks_delivery_handoff(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    missing_litmus = tmp_path / "missing-litmus-status"

    data = invoke(repo, plugin, "--litmus-status-script", str(missing_litmus))

    assert data["litmus_status"]["available"] is False
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_unavailable" in data["decision"]["blockers"]
    assert "litmus_status_unavailable" not in data["decision"]["warnings"]
    assert_no_delivery_authority(data["decision"])


def test_blocked_litmus_status_blocks_delivery_handoff(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "blocked-litmus-status.json", repo=repo, status="blocked")

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is True
    assert data["litmus_status"]["summary"]["decision"]["status"] == "blocked"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_not_fresh" in data["decision"]["blockers"]
    assert "litmus_status_not_fresh" not in data["decision"]["warnings"]
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_ok_false_blocks_delivery_handoff(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "not-ok-litmus-status.json", repo=repo, status="commit_litmus_fresh", ok=False)

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["summary"]["decision"]["status"] == "commit_litmus_fresh"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_not_fresh" in data["decision"]["blockers"]
    assert "litmus_status_not_fresh" not in data["decision"]["warnings"]
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_non_boolean_ok_fails_closed_even_when_fresh(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "malformed-ok-litmus-status.json", repo=repo, status="commit_litmus_fresh", ok="false")

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_schema_invalid"
    assert data["litmus_status"]["summary"]["ok"] is False
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_schema_invalid" in data["decision"]["blockers"]
    assert "litmus_status_not_fresh" not in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_unrecognized_decision_status_fails_closed_even_when_ok(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "unknown-status-litmus-status.json", repo=repo, status="surprise_fresh", ok=True)

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_schema_invalid"
    assert data["litmus_status"]["summary"]["decision"]["status"] == "surprise_fresh"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_schema_invalid" in data["decision"]["blockers"]
    assert "litmus_status_not_fresh" not in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


def test_unsafe_litmus_status_output_blocks_delivery_handoff(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "unsafe-litmus-status.json", repo=repo, authority_safe=False)

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_authority_flags_unsafe"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_authority_flags_unsafe" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


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
def test_delivery_rejects_litmus_status_with_finalization_authority(tmp_path: Path, authority_key: str):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(
        tmp_path / f"unsafe-{authority_key}-litmus-status.json",
        repo=repo,
        authority_safe=False,
        authority_true_key=authority_key,
    )

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_authority_flags_unsafe"
    assert data["litmus_status"]["summary"]["decision"][authority_key] is False
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_authority_flags_unsafe" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


@pytest.mark.parametrize(
    "payload_update",
    [
        lambda payload: payload.update({"commit_allowed": True}),
        lambda payload: payload["markers"]["pr_codex_lead"].update({"merge_allowed": True}),
        lambda payload: payload["markers"]["pr_backstop_verdict"].update({"authority": {"pr_allowed": True}}),
        lambda payload: payload["markers"]["pr_review_passed"].update({"nested": [{"authority": {"push_allowed": True}}]}),
        lambda payload: payload.update({"programmatic_execution_allowed": True}),
    ],
)
def test_delivery_rejects_litmus_status_with_nested_or_top_level_authority(
    tmp_path: Path,
    payload_update,
):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "nested-authority-litmus-status.json", repo=repo)
    payload = json.loads(litmus.read_text())
    payload_update(payload)
    litmus.write_text(json.dumps(payload))

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_authority_flags_unsafe"
    assert data["litmus_status"]["summary"]["authority_safe"] is False
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_authority_flags_unsafe" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


def test_delivery_rejects_fresh_litmus_status_with_recursive_authority(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "fresh-recursive-authority-litmus-status.json", repo=repo, status="pr_review_fresh")
    payload = json.loads(litmus.read_text())
    payload["markers"]["pr_codex_lead"].update({"exists": True, "fresh_for_branch_diff": True})
    payload["markers"]["pr_backstop_verdict"].update({"exists": True, "fresh_for_branch_diff": True})
    payload["markers"]["pr_review_passed"].update({"exists": True, "fresh_for_branch_diff": True})
    payload["markers"]["pr_backstop_verdict"]["authority"] = {"pr_allowed": True}
    litmus.write_text(json.dumps(payload))

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_authority_flags_unsafe"
    assert data["litmus_status"]["summary"]["authority_safe"] is False
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_authority_flags_unsafe" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


def test_litmus_authority_scan_fails_closed_on_excessive_list_depth() -> None:
    mod = __import__("runpy").run_path(str(STATUS))
    payload: dict[str, Any] = {"nested": []}
    cursor = payload["nested"]
    for _ in range(1105):
        child: list[Any] = []
        cursor.append(child)
        cursor = child

    assert mod["payload_authority_flags_false"](payload) is False


def test_litmus_authority_scan_rejects_authority_nested_in_list() -> None:
    mod = __import__("runpy").run_path(str(STATUS))
    payload: dict[str, Any] = {"nested": [{"authority": {"pr_allowed": True}}]}

    assert mod["payload_authority_flags_false"](payload) is False


def test_litmus_authority_scan_fails_closed_on_excessive_depth() -> None:
    mod = __import__("runpy").run_path(str(STATUS))
    payload: dict[str, Any] = {}
    cursor = payload
    for _ in range(1105):
        child: dict[str, Any] = {}
        cursor["nested"] = child
        cursor = child

    assert mod["payload_authority_flags_false"]({"root": payload}) is False


def test_delivery_litmus_status_summary_sanitizes_untrusted_evidence(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    sentinel = "ghp_" + "D" * 36
    litmus = litmus_status_fixture(tmp_path / "malicious-litmus-status.json", repo=repo, malicious_sentinel=sentinel)

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    payload = json.dumps(data)
    summary = data["litmus_status"]["summary"]
    litmus_marker = summary["markers"]["litmus_passed"]
    assert sentinel not in payload
    assert set(summary["repo"]) == {"root", "branch", "head", "head_timestamp", "base_ref", "branch_diff_hash"}
    assert set(summary["state_dir"]) == {"path", "exists", "is_symlink", "has_symlink_component"}
    assert set(summary["markers"]) == {"litmus_passed", "pr_codex_lead", "pr_backstop_verdict", "pr_review_passed"}
    assert "unknown_secret" not in litmus_marker
    assert "[REDACTED]" in summary["repo"]["root"]
    assert "[REDACTED]" in summary["state_dir"]["path"]
    assert "[REDACTED]" in litmus_marker["path"]
    assert litmus_marker["read_error"] == "password=[REDACTED]"
    assert litmus_marker["stat_error"] == "stat token=[REDACTED]"
    assert summary["decision"]["warnings"] == []
    assert summary["decision"]["blockers"] == []
    assert "unexpected_secret" not in summary["decision"]
    assert summary["decision"]["not_busdriver_native_claude_runtime"] is True
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_summary_sanitizes_invalid_native_runtime_flag(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    sentinel = "ghp_" + "F" * 36
    litmus = litmus_status_fixture(tmp_path / "malicious-native-runtime-litmus-status.json", repo=repo)
    payload = json.loads(litmus.read_text())
    payload["decision"]["not_busdriver_native_claude_runtime"] = f"token={sentinel}"
    litmus.write_text(json.dumps(payload))

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    serialized = json.dumps(data)
    assert sentinel not in serialized
    assert data["litmus_status"]["summary"]["decision"]["not_busdriver_native_claude_runtime"] is False
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_summary_normalizes_untrusted_top_level_primitives(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    sentinel = "ghp_" + "G" * 36
    litmus = litmus_status_fixture(tmp_path / "malicious-top-level-litmus-status.json", repo=repo)
    payload = json.loads(litmus.read_text())
    payload["schema"] = f"schema token={sentinel}"
    payload["read_only"] = {"secret": sentinel}
    payload["ok"] = f"ok token={sentinel}"
    payload["decision"]["not_busdriver_native_claude_runtime"] = f"token={sentinel}"
    litmus.write_text(json.dumps(payload))

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    serialized = json.dumps(data)
    summary = data["litmus_status"]["summary"]
    assert sentinel not in serialized
    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_schema_invalid"
    assert summary["schema"] is None
    assert summary["read_only"] is False
    assert summary["ok"] is False
    assert summary["decision"]["not_busdriver_native_claude_runtime"] is False
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_parse_error_tails_are_redacted_and_bounded(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    sentinel = "ghp_" + "A" * 36
    script = tmp_path / "malformed-litmus-status.py"
    stdout_payload = "x" * 5005 + f" api_key={sentinel}\n"
    stderr_payload = "e" * 5005 + f" Authorization: Bearer {sentinel}\n"
    script.write_text(
        "import sys\n"
        f"sys.stdout.write({stdout_payload!r})\n"
        f"sys.stderr.write({stderr_payload!r})\n"
    )

    data = invoke(repo, plugin, "--litmus-status-script", str(script))

    litmus = data["litmus_status"]
    serialized = json.dumps(data)
    assert litmus["ok"] is False
    assert litmus["reason"] == "litmus_status_malformed"
    assert sentinel not in serialized
    assert len(litmus["stdout_tail"]) <= 4000
    assert len(litmus["stderr"]) <= 4000
    assert "api_key=[REDACTED]" in litmus["stdout_tail"]
    assert "Authorization: Bearer [REDACTED]" in litmus["stderr"]


def test_litmus_status_timeout_with_bytes_output_is_sanitized(monkeypatch, tmp_path: Path):
    mod = __import__("runpy").run_path(str(STATUS))
    script = tmp_path / "slow-litmus-status.py"
    script.write_text("import time\ntime.sleep(60)\n")
    sentinel = "ghp_" + "C" * 36

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd, 1, output=f"partial api_key={sentinel}\n".encode(), stderr=f"token={sentinel}\n".encode())

    patch_bounded_run(monkeypatch, mod, fake_run)
    args = __import__("types").SimpleNamespace(litmus_status_result_file=None, litmus_status_script=str(script), litmus_status_timeout=1)

    data = mod["run_litmus_status"](args, {"ok": True, "root": str(tmp_path), "branch": "main", "head": "abc123"})

    serialized = json.dumps(data)
    assert data["ok"] is False
    assert data["returncode"] == 124
    assert data["reason"] == "litmus_status_subprocess_failed"
    assert data["timeout_seconds"] == 1
    assert sentinel not in serialized
    assert len(data["stdout_tail"]) <= 4000
    assert len(data["stderr"]) <= 4000
    assert "api_key=[REDACTED]" in data["stdout_tail"]
    assert "token=[REDACTED]" in data["stderr"]


def test_delivery_status_git_disables_fsmonitor_and_global_git_config(monkeypatch, tmp_path: Path):
    mod = __import__("runpy").run_path(str(STATUS))
    repo = tmp_path / "repo"
    captured: dict[str, Any] = {}

    class CP:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env")
        return CP()  # type: ignore[return-value]

    patch_bounded_run(monkeypatch, mod, fake_run)

    mod["git"](repo, "status", "--porcelain=v1")

    cmd = captured["cmd"]
    assert cmd[:4] == [
        str(mod["TRUSTED_EXECUTABLE_SOURCES"]["sandbox-exec"]),
        "-p",
        mod["GIT_OBSERVATION_SANDBOX_PROFILE"],
        str(mod["TRUSTED_EXECUTABLE_SOURCES"]["git-real"]),
    ]
    assert "core.fsmonitor=false" in cmd
    assert "--ignore-submodules=none" in cmd
    assert "--untracked-files=all" in cmd
    assert cmd[cmd.index("-C"):cmd.index("-C") + 2] == ["-C", str(repo)]
    # Both launcher and real Git are frozen root-owned sources executed in place.
    for dispatched in (Path(cmd[0]), Path(cmd[3])):
        assert os.lstat(dispatched).st_uid == 0
        assert not (os.lstat(dispatched).st_mode & (stat.S_IWGRP | stat.S_IWOTH))
    assert captured["env"]["GIT_CONFIG_GLOBAL"] == os.devnull
    assert captured["env"]["GIT_CONFIG_NOSYSTEM"] == "1"


def test_run_litmus_status_forwards_state_dir_name_and_base_ref(monkeypatch, tmp_path: Path):
    mod = __import__("runpy").run_path(str(STATUS))
    script = tmp_path / "litmus-status.py"
    script.write_text("# fake litmus helper\n")
    captured: dict[str, list[str]] = {}
    payload = {
        "schema": "hermes-busdriver-litmus-status/v0",
        "read_only": True,
        "ok": True,
        "repo": {"root": str(tmp_path), "branch": "main", "head": "abc123", "head_timestamp": 1, "base_ref": None, "branch_diff_hash": None},
        "state_dir": {"path": str(tmp_path / ".opencode"), "exists": False, "is_symlink": False, "has_symlink_component": False},
        "markers": {},
        "decision": {
            "status": "stale_or_missing",
            "warnings": [],
            "blockers": [],
            "finalization_allowed": False,
            "commit_allowed": False,
            "push_allowed": False,
            "pr_allowed": False,
            "merge_allowed": False,
            "deploy_allowed": False,
            "release_allowed": False,
            "publish_allowed": False,
            "marker_write_allowed": False,
            "not_busdriver_native_claude_runtime": True,
        },
    }

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")

    patch_bounded_run(monkeypatch, mod, fake_run)
    args = __import__("types").SimpleNamespace(
        litmus_status_result_file=None,
        litmus_status_script=str(script),
        litmus_status_timeout=10,
        litmus_base_ref="origin/release",
        busdriver_state_dir_name=".opencode",
    )

    data = mod["run_litmus_status"](args, {"ok": True, "root": str(tmp_path), "branch": "main", "head": "abc123"})

    cmd = captured["cmd"]
    assert data["ok"] is True
    assert "--base-ref" in cmd
    assert cmd[cmd.index("--base-ref") + 1] == "origin/release"
    assert "--state-dir-name" in cmd
    assert cmd[cmd.index("--state-dir-name") + 1] == ".opencode"


def test_litmus_status_nonzero_valid_json_stderr_is_redacted_and_bounded(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "litmus-status.json", repo=repo)
    sentinel = "ghp_" + "B" * 36
    script = tmp_path / "failing-litmus-status.py"
    script.write_text(
        "import pathlib, sys\n"
        f"print(pathlib.Path({str(litmus)!r}).read_text())\n"
        "sys.stderr.write('e' * 5005)\n"
        f"sys.stderr.write(' token={sentinel}\\n')\n"
        "sys.exit(2)\n"
    )

    data = invoke(repo, plugin, "--litmus-status-script", str(script))

    litmus_status = data["litmus_status"]
    serialized = json.dumps(data)
    assert litmus_status["returncode"] == 2
    assert litmus_status["ok"] is False
    assert litmus_status["reason"] == "litmus_status_subprocess_failed"
    assert sentinel not in serialized
    assert len(litmus_status["stderr"]) <= 4000
    assert "token=[REDACTED]" in litmus_status["stderr"]


def test_litmus_status_subprocess_nonzero_fails_closed_even_with_valid_json(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "litmus-status.json", repo=repo)
    script = tmp_path / "litmus-status-wrapper.py"
    script.write_text(
        "import pathlib, sys\n"
        f"print(pathlib.Path({str(litmus)!r}).read_text())\n"
        "sys.exit(2)\n"
    )

    data = invoke(repo, plugin, "--litmus-status-script", str(script))

    assert data["litmus_status"]["returncode"] == 2
    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_subprocess_failed"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_subprocess_failed" in data["decision"]["blockers"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["commit_allowed"] is False
    assert data["decision"]["push_allowed"] is False
    assert data["decision"]["pr_allowed"] is False
    assert data["decision"]["merge_allowed"] is False
    assert data["decision"]["marker_write_allowed"] is False


def test_litmus_status_subprocess_nonzero_fails_closed_even_with_valid_json_ok_false(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "litmus-status.json", repo=repo, status="commit_litmus_fresh", ok=False)
    script = tmp_path / "litmus-status-wrapper.py"
    script.write_text(
        "import pathlib, sys\n"
        f"print(pathlib.Path({str(litmus)!r}).read_text())\n"
        "sys.exit(2)\n"
    )

    data = invoke(repo, plugin, "--litmus-status-script", str(script))

    assert data["litmus_status"]["returncode"] == 2
    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_subprocess_failed"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_subprocess_failed" in data["decision"]["blockers"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["commit_allowed"] is False
    assert data["decision"]["push_allowed"] is False
    assert data["decision"]["pr_allowed"] is False
    assert data["decision"]["merge_allowed"] is False
    assert data["decision"]["marker_write_allowed"] is False


@pytest.mark.parametrize(
    ("mutate_payload", "expected_reason"),
    [
        (lambda _payload: ["not", "an", "object"], "litmus_status_malformed"),
        (lambda payload: {**payload, "read_only": False}, "litmus_status_read_only_unsafe"),
        (lambda payload: {**payload, "ok": "true"}, "litmus_status_schema_invalid"),
    ],
    ids=["non_object", "read_only_false", "ok_non_boolean"],
)
def test_litmus_status_fixture_malformed_or_invalid_top_level_fields_fail_closed(tmp_path: Path, mutate_payload, expected_reason: str):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "litmus-status.json", repo=repo)
    payload = json.loads(litmus.read_text())
    litmus.write_text(json.dumps(mutate_payload(payload)))

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == expected_reason
    assert data["decision"]["status"] == "blocked"
    assert expected_reason in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


def test_litmus_status_fixture_invalid_json_fails_closed(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = tmp_path / "litmus-status.json"
    litmus.write_text("{not-json\n")

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert data["litmus_status"]["ok"] is False
    assert data["litmus_status"]["reason"] == "litmus_status_malformed"
    assert data["decision"]["status"] == "blocked"
    assert "litmus_status_malformed" in data["decision"]["blockers"]
    assert_no_delivery_authority(data["decision"])


def assert_capability_entry_is_metadata_only(entry: dict[str, Any]) -> None:
    assert set(entry) == {"path", "available"}
    assert isinstance(entry["path"], str)
    assert isinstance(entry["available"], bool)


def test_delivery_status_can_resolve_requested_relay_role_read_only(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    cfg = relay_config(tmp_path / "relay-config.json", ["opencode", "codex"])

    data = invoke(repo, plugin, "--relay-role", "relay.pr.backstop", "--relay-config", str(cfg))

    public_helpers = {
        "agent_balance_plan",
        "agent_smoke",
        "deliver",
        "delivery_status",
        "finalization_contract_status",
        "finalization_readiness",
        "relay_role",
        "smoke",
    }
    assert public_helpers <= set(data["relay_capabilities"])
    for entry in data["relay_capabilities"].values():
        assert_capability_entry_is_metadata_only(entry)
    for helper in public_helpers:
        assert data["relay_capabilities"][helper]["available"] is True
    role = data["relay_role_resolution"]
    assert role["available"] is True
    assert role["ok"] is True
    assert role["returncode"] == 0
    assert role["result"]["role"] == "relay.pr.backstop"
    assert role["result"]["selected"]["selected_agent"] == "codex"
    assert role["result"]["dispatch_allowed"] is True
    assert role["result"]["mutation_allowed"] is False
    assert role["result"]["finalization_allowed"] is False
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["merge_allowed"] is False
    assert "relay_role_not_dispatchable" not in data["decision"]["warnings"]


def test_delivery_status_reports_unresolved_relay_role_as_warning(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    cfg = relay_config(tmp_path / "relay-config.json", [])

    data = invoke(repo, plugin, "--relay-role", "relay.pr.backstop", "--relay-config", str(cfg))

    role = data["relay_role_resolution"]
    assert role["available"] is True
    assert role["ok"] is False
    assert role["returncode"] == 2
    assert role["reason"] == "relay_role_not_dispatchable"
    assert role["result"]["dispatch_allowed"] is False
    assert role["result"]["selected"]["config_error"] == "empty_route"
    assert "relay_role_not_dispatchable" in data["decision"]["warnings"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["merge_allowed"] is False


def test_delivery_status_rejects_authority_positive_relay_role_output(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    unsafe = tmp_path / "unsafe-relay-role.py"
    unsafe.write_text(
        "import json\n"
        "print(json.dumps({\n"
        "  'schema': 'hermes-busdriver-relay-role/v0',\n"
        "  'role': 'relay.pr.backstop',\n"
        "  'read_only': True,\n"
        "  'ok': True,\n"
        "  'dispatch_allowed': True,\n"
        "  'mutation_allowed': True,\n"
        "  'finalization_allowed': True,\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'decision': {'dispatch_allowed': True, 'mutation_allowed': True, 'finalization_allowed': True, 'not_busdriver_native_claude_runtime': True}\n"
        "}))\n"
    )

    data = invoke(repo, plugin, "--relay-role", "relay.pr.backstop", "--relay-role-script", str(unsafe))

    role = data["relay_role_resolution"]
    assert role["returncode"] == 0
    assert role["ok"] is False
    assert role["reason"] == "relay_role_authority_flags_unsafe"
    assert "relay_role_not_dispatchable" in data["decision"]["warnings"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["merge_allowed"] is False


def test_delivery_status_rejects_mismatched_relay_role_output(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    wrong_role = tmp_path / "wrong-role.py"
    wrong_role.write_text(
        "import json\n"
        "print(json.dumps({\n"
        "  'schema': 'hermes-busdriver-relay-role/v0',\n"
        "  'role': 'relay.council.skeptic',\n"
        "  'read_only': True,\n"
        "  'ok': True,\n"
        "  'dispatch_allowed': True,\n"
        "  'mutation_allowed': False,\n"
        "  'finalization_allowed': False,\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'decision': {'dispatch_allowed': True, 'mutation_allowed': False, 'finalization_allowed': False, 'not_busdriver_native_claude_runtime': True}\n"
        "}))\n"
    )

    data = invoke(repo, plugin, "--relay-role", "relay.pr.backstop", "--relay-role-script", str(wrong_role))

    role = data["relay_role_resolution"]
    assert role["returncode"] == 0
    assert role["ok"] is False
    assert role["reason"] == "relay_role_authority_flags_unsafe"
    assert role["result"]["role"] == "relay.council.skeptic"
    assert "relay_role_not_dispatchable" in data["decision"]["warnings"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["merge_allowed"] is False


def _private_runtime_root(tmp_path: Path, script_name: str, trusted_source: str) -> Path:
    root = tmp_path / f"private-{script_name}"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    script = scripts / script_name
    script.write_text(trusted_source)
    script.chmod(0o500)
    return root


def test_lock_status_executes_retained_bytes_not_swappable_private_path(monkeypatch, tmp_path: Path):
    mod = __import__("runpy").run_path(str(STATUS))
    private_root = _private_runtime_root(
        tmp_path,
        "hermes-busdriver-lock",
        "import json\nprint(json.dumps({'ok': False, 'locks': [{'repo': {'root': '/trusted'}, 'stale': False}]}))\n",
    )
    monkeypatch.setitem(mod["load_lock_status"].__globals__, "ROOT", private_root)

    def swap_lock_then_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        script = next(Path(arg) for arg in cmd if Path(str(arg)).name == "hermes-busdriver-lock")
        script.chmod(0o700)
        script.write_text("import json\nprint(json.dumps({'ok': True, 'locks': []}))\n")
        script.chmod(0o500)
        return subprocess.run(cmd, **kwargs)

    patch_bounded_run(monkeypatch, mod, swap_lock_then_run)
    result = mod["load_lock_status"](argparse.Namespace(no_lock_status=False, state_dir=None))

    assert result.get("ok") is not True, "attacker-replaced lock helper forged an unlocked state"


def test_relay_role_executes_retained_bytes_not_swappable_private_path(monkeypatch, tmp_path: Path):
    mod = __import__("runpy").run_path(str(STATUS))
    private_root = _private_runtime_root(
        tmp_path,
        "hermes-busdriver-relay-role",
        "import json\nprint(json.dumps({'schema':'hermes-busdriver-relay-role/v0','role':'relay.pr.backstop','read_only':True,'ok':False,'dispatch_allowed':False,'mutation_allowed':False,'finalization_allowed':False,'not_busdriver_native_claude_runtime':True,'decision':{'dispatch_allowed':False,'mutation_allowed':False,'finalization_allowed':False,'not_busdriver_native_claude_runtime':True}}))\n",
    )
    monkeypatch.setitem(mod["run_relay_role_resolution"].__globals__, "ROOT", private_root)

    def swap_role_then_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        script = next(Path(arg) for arg in cmd if Path(str(arg)).name == "hermes-busdriver-relay-role")
        script.chmod(0o700)
        script.write_text("import json\nprint(json.dumps({'schema':'hermes-busdriver-relay-role/v0','role':'relay.pr.backstop','read_only':True,'ok':True,'dispatch_allowed':True,'mutation_allowed':False,'finalization_allowed':False,'not_busdriver_native_claude_runtime':True,'decision':{'dispatch_allowed':True,'mutation_allowed':False,'finalization_allowed':False,'not_busdriver_native_claude_runtime':True}}))\n")
        script.chmod(0o500)
        return subprocess.run(cmd, **kwargs)

    patch_bounded_run(monkeypatch, mod, swap_role_then_run)
    args = argparse.Namespace(relay_role="relay.pr.backstop", relay_role_script=None, relay_config=None, state_dir=None, relay_role_timeout=10)
    result = mod["run_relay_role_resolution"](args)

    assert result.get("ok") is not True, "attacker-replaced relay-role helper forged dispatchability"


def test_relay_role_status_probe_executes_retained_bytes_not_swappable_path(monkeypatch, tmp_path: Path):
    mod = __import__("runpy").run_path(str(ROOT / "scripts" / "hermes-busdriver-relay-role"))
    status = tmp_path / "hermes-busdriver-status"
    trusted_payload = {
        "relay_config": {"path": "fixture"},
        "relay_equivalent_roles": {
            "roles": {
                "relay.pr.backstop": {
                    "degraded": False,
                    "selected_agent": "codex",
                    "programmatic_dispatch_allowed": True,
                    "adapter_verified": True,
                    "dispatch_blocker": None,
                }
            }
        },
    }
    trusted = f"import json\nprint(json.dumps({trusted_payload!r}))\n".encode()
    status.write_bytes(trusted)
    status.chmod(0o500)
    globals_ = mod["load_status_payload"].__globals__
    monkeypatch.setitem(globals_, "STATUS_SCRIPT", status)
    monkeypatch.setitem(globals_, "TRUSTED_STATUS_SHA256", hashlib.sha256(trusted).hexdigest())

    BoundedOutput = mod["BoundedOutput"]

    def swap_status_then_run(cmd: list[str], **kwargs: Any):
        script = next(Path(arg) for arg in cmd if Path(str(arg)).name == "hermes-busdriver-status")
        script.chmod(0o700)
        script.write_text("import json\nprint(json.dumps({'relay_config':{}, 'relay_equivalent_roles': {'roles': {}}}))\n")
        script.chmod(0o500)
        cp = subprocess.run(
            cmd,
            input=kwargs.get("stdin_bytes", b"").decode(),
            text=True,
            capture_output=True,
            check=False,
            env=kwargs.get("env"),
        )
        return BoundedOutput(cp.returncode, cp.stdout, cp.stderr, False, False)

    monkeypatch.setitem(globals_, "run_bounded", swap_status_then_run)
    args = argparse.Namespace(role="relay.pr.backstop", list_roles=False, relay_config=None, relay_state_dir=None)

    payload, code = mod["build_payload"](args)

    assert code == 0
    assert payload["status"] == "resolved"
    assert payload["selected"]["selected_agent"] == "codex"


def test_phase0_status_executes_retained_bytes_not_swappable_private_path(monkeypatch, tmp_path: Path):
    mod = __import__("runpy").run_path(str(STATUS))
    private_root = _private_runtime_root(
        tmp_path,
        "hermes-busdriver-status",
        "import json\nprint(json.dumps({'schema':'hermes-busdriver-status/v0','busdriver_drift':{'status':'drifted','finalization_compatible':False},'decision':{'finalization_allowed':False,'merge_allowed':False}}))\n",
    )
    monkeypatch.setitem(mod["run_phase0_status"].__globals__, "ROOT", private_root)

    def swap_status_then_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        script = next(Path(arg) for arg in cmd if Path(str(arg)).name == "hermes-busdriver-status")
        script.chmod(0o700)
        script.write_text("import json\nprint(json.dumps({'schema':'hermes-busdriver-status/v0','busdriver_drift':{'status':'compatible','finalization_compatible':True},'decision':{'finalization_allowed':False,'merge_allowed':False}}))\n")
        script.chmod(0o500)
        return subprocess.run(cmd, **kwargs)

    patch_bounded_run(monkeypatch, mod, swap_status_then_run)
    args = argparse.Namespace(repo=str(tmp_path), drift_baseline="baseline.json", phase0_status_timeout=10, busdriver_state_dir_name=None, state_dir=None)
    result = mod["run_phase0_status"](args, {"ok": True, "root": str(tmp_path)}, {"ok": False})

    assert result.get("busdriver_drift", {}).get("status") != "compatible", "attacker-replaced phase0 helper forged compatible drift"


def test_pr_status_blocks_when_pr_grind_checker_missing(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    missing_checker = tmp_path / "missing-pr-grind-check"

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-check-script", str(missing_checker))

    assert data["decision"]["status"] == "blocked"
    assert "hermes_pr_grind_checker_unavailable" in data["decision"]["blockers"]
    assert "PR #3" not in data["decision"]["next_action"]
    assert "PR-grind readiness checker" in data["decision"]["next_action"]
    assert data["pr_grind"]["available"] is False
    assert data["decision"]["merge_allowed"] is False


def test_pr_clean_fixture_is_still_read_only_not_merge_authority(tmp_path: Path):
    repo = bind_github_origin(init_repo(tmp_path / "repo"))
    plugin = fake_busdriver(tmp_path / "busdriver")
    pr_result = tmp_path / "pr-grind-result.json"
    pr_result.write_text(json.dumps(pr_grind_payload()))

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    # r24: a clean fixture is a diagnostic, so it cannot even reach pr_clean_read_only, let alone
    # merge authority. The authority flags stay negative either way.
    assert data["decision"]["status"] == "blocked"
    assert "fixture_evidence_not_authoritative" in data["decision"]["blockers"]
    assert data["pr_grind"]["result"]["clean"] is True
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["merge_allowed"] is False
    assert "read-only" in data["decision"]["policy"].lower()


def test_forged_minimal_pr_grind_result_never_reports_pr_clean(tmp_path: Path):
    # r23: `{"status": "clean", "clean": true}` is two keys any writer can type. Accepting it as
    # a clean PR-grind result hands an unbound, unauthenticated file merge-handoff standing.
    repo = bind_github_origin(init_repo(tmp_path / "repo-forged-pr-grind"))
    plugin = fake_busdriver(tmp_path / "busdriver-forged-pr-grind")
    pr_result = tmp_path / "forged-pr-grind-result.json"
    pr_result.write_text(json.dumps({"status": "clean", "clean": True}))

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert data["decision"]["status"] == "blocked"
    assert "pr_grind_result_invalid" in data["decision"]["blockers"]
    assert data["pr_grind"]["ok"] is False
    assert data["pr_grind"]["reason"] == "pr_grind_result_invalid"
    assert data["decision"]["merge_allowed"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", "hermes-busdriver-pr-grind-check/v1"),
        ("version", 2),
        ("ok", False),
        ("read_only", False),
        ("repository", "attacker/other-repo"),
        ("pr", 8),
        ("pr", "7"),
        ("url", "https://github.com/attacker/other-repo/pull/7"),
        ("head", "not-a-sha"),
        ("base_sha", ""),
        ("base_repository", "attacker/other-repo"),
        ("base", "UNKNOWN"),
        ("head_ref", ""),
        ("status", "definitely_clean"),
        ("clean", False),
    ],
)
def test_pr_grind_result_field_tampering_fails_closed(tmp_path: Path, field: str, value: Any):
    repo = bind_github_origin(init_repo(tmp_path / f"repo-tamper-{field}-{abs(hash(str(value)))}"))
    plugin = fake_busdriver(tmp_path / f"busdriver-tamper-{field}-{abs(hash(str(value)))}")
    pr_result = tmp_path / f"tampered-{field}-{abs(hash(str(value)))}.json"
    pr_result.write_text(json.dumps(pr_grind_payload(**{field: value})))

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert data["decision"]["status"] != "pr_clean_read_only"
    assert "pr_grind_result_invalid" in data["decision"]["blockers"]


@pytest.mark.parametrize("decision_override", [
    {"merge_allowed": True},
    {"pr_grind_clean": False},
    {"status": "wait"},
    {"blocked": True},
])
def test_pr_grind_decision_authority_tampering_fails_closed(tmp_path: Path, decision_override: dict):
    key = abs(hash(json.dumps(decision_override, sort_keys=True)))
    repo = bind_github_origin(init_repo(tmp_path / f"repo-decision-{key}"))
    plugin = fake_busdriver(tmp_path / f"busdriver-decision-{key}")
    payload = pr_grind_payload()
    payload["decision"].update(decision_override)
    pr_result = tmp_path / f"decision-{key}.json"
    pr_result.write_text(json.dumps(payload))

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert data["decision"]["status"] != "pr_clean_read_only"
    assert "pr_grind_result_invalid" in data["decision"]["blockers"]


def test_pr_grind_clean_result_is_rejected_without_a_github_origin_binding(tmp_path: Path):
    # No origin remote: nothing binds this result to the repo under test, so a clean claim about
    # "some PR #7 somewhere" cannot be accepted for this one.
    repo = init_repo(tmp_path / "repo-no-origin")
    plugin = fake_busdriver(tmp_path / "busdriver-no-origin")
    pr_result = tmp_path / "pr-grind-no-origin.json"
    pr_result.write_text(json.dumps(pr_grind_payload()))

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert data["repo"]["github_repository"] is None
    assert data["decision"]["status"] == "blocked"
    assert "pr_grind_result_invalid" in data["decision"]["blockers"]


@pytest.mark.parametrize("url", [
    f"https://github.com/{GITHUB_ORIGIN}.git",
    f"https://github.com/{GITHUB_ORIGIN}",
    f"git@github.com:{GITHUB_ORIGIN}.git",
    f"ssh://git@github.com/{GITHUB_ORIGIN}.git",
])
def test_repo_status_canonicalizes_standard_github_origin_urls(tmp_path: Path, url: str):
    repo = bind_github_origin(init_repo(tmp_path / f"repo-origin-{abs(hash(url))}"), url)
    plugin = fake_busdriver(tmp_path / f"busdriver-origin-{abs(hash(url))}")

    data = invoke(repo, plugin)

    assert data["repo"]["github_repository"] == GITHUB_ORIGIN


def test_repo_status_reports_no_binding_for_a_non_github_origin(tmp_path: Path):
    repo = bind_github_origin(init_repo(tmp_path / "repo-gitlab-origin"), "https://gitlab.com/chris-yyau/relay.git")
    plugin = fake_busdriver(tmp_path / "busdriver-gitlab-origin")

    data = invoke(repo, plugin)

    assert data["repo"]["github_repository"] is None


def test_repo_status_entry_lists_are_bounded_and_declare_their_truncation(tmp_path: Path):
    """`git status --porcelain` output was embedded whole, then re-emitted twice downstream.

    r23/M9: a stray `node_modules` produces hundreds of MB of JSON through an envelope whose every
    other tail is bounded to 2000-4000 chars. Bounding it must not cost the truth: `dirty` stays
    a fact, the totals stay exact, and the truncation is declared rather than silent.
    """
    repo = bind_github_origin(init_repo(tmp_path / "repo-many-dirty-paths"))
    plugin = fake_busdriver(tmp_path / "busdriver-many-dirty-paths")
    for index in range(600):
        (repo / f"untracked-{index:04d}.txt").write_text("x" * 200)

    data = invoke(repo, plugin)
    repo_status = data["repo"]

    assert repo_status["dirty"] is True
    # The counts are the whole truth even though the lists are not.
    assert repo_status["dirty_entries_total_count"] == 600
    assert repo_status["untracked_entries_total_count"] == 600
    assert repo_status["dirty_entries_truncated"] is True
    assert repo_status["untracked_entries_truncated"] is True
    for key in ("dirty_entries", "untracked_entries"):
        assert len(repo_status[key]) < 600
        assert len(json.dumps(repo_status[key])) <= DELIVERY_STATUS_ENTRY_LIST_BYTE_LIMIT * 2
    # The whole envelope stays a readable document rather than an amplifier.
    assert len(json.dumps(data)) < 400_000
    # An untruncated repo must not claim truncation.
    clean_repo = bind_github_origin(init_repo(tmp_path / "repo-few-dirty-paths"))
    (clean_repo / "one.txt").write_text("x")
    clean_data = invoke(clean_repo, fake_busdriver(tmp_path / "busdriver-few-dirty-paths"))
    assert clean_data["repo"]["dirty_entries_truncated"] is False
    assert clean_data["repo"]["dirty_entries_total_count"] == 1
    assert len(clean_data["repo"]["dirty_entries"]) == 1


def test_structurally_valid_non_clean_pr_grind_result_keeps_its_diagnostic_blocker(tmp_path: Path):
    repo = bind_github_origin(init_repo(tmp_path / "repo-valid-wait"))
    plugin = fake_busdriver(tmp_path / "busdriver-valid-wait")
    pr_result = tmp_path / "pr-grind-wait.json"
    pr_result.write_text(json.dumps(pr_grind_payload(status="wait", checks={"failed": 0, "pending": 1})))

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert data["pr_grind"]["source"] == "fixture"
    assert data["pr_grind"]["result"]["status"] == "wait"
    assert "pr_grind_result_invalid" not in data["decision"]["blockers"]


def test_default_pr_grind_checker_executes_retained_bytes_not_swappable_private_path(monkeypatch, tmp_path: Path):
    """The default checker's private retained pathname is not the execution identity."""
    import runpy

    ns = runpy.run_path(str(STATUS))
    globals_ = ns["run_pr_grind_check"].__globals__
    repo_path = bind_github_origin(init_repo(tmp_path / "repo-default-pr-grind-toctou"))
    trusted_root = tmp_path / "trusted-root"
    relative = "scripts/hermes-busdriver-pr-grind-check"
    trusted = trusted_root / relative
    trusted.parent.mkdir(parents=True)
    payload = pr_grind_payload(pr=7, status="clean")
    trusted.write_text("import json\nprint(json.dumps(%r))\n" % payload)
    trusted.chmod(0o500)
    attacker_ran = tmp_path / "default-pr-grind-attacker-ran"
    attacker = (
        "import json, pathlib\n"
        f"pathlib.Path({str(attacker_ran)!r}).write_text('pwned')\n"
        f"print(json.dumps({payload!r}))\n"
    )

    monkeypatch.setitem(globals_, "ROOT", trusted_root)
    monkeypatch.setitem(globals_, "TRUSTED_RELAY_HELPER_DIGESTS", {relative: hashlib.sha256(trusted.read_bytes()).hexdigest()})
    monkeypatch.setitem(globals_, "trusted_executable_path", lambda name: Path(sys.executable) if name == "python3" else pytest.fail(f"unexpected trusted executable {name}"))
    identity = {
        "expected-repository": GITHUB_ORIGIN,
        "expected-head-repository": GITHUB_ORIGIN,
        "expected-head-ref": "feature-branch",
        "expected-base-repository": GITHUB_ORIGIN,
        "expected-base-ref": "main",
        "expected-head-sha": "a" * 40,
        "expected-base-sha": "b" * 40,
    }
    monkeypatch.setitem(globals_, "expected_checker_identity", lambda *_args: (identity, None))
    original_run_bounded = globals_["run_bounded"]

    def swap_retained_path_then_exec(cmd, *args, **kwargs):
        for value in cmd:
            candidate = Path(str(value))
            if candidate.name == "hermes-busdriver-pr-grind-check" and candidate.exists():
                candidate.unlink()
                candidate.write_text(attacker)
                candidate.chmod(0o500)
                break
        return original_run_bounded(cmd, *args, **kwargs)

    monkeypatch.setitem(globals_, "run_bounded", swap_retained_path_then_exec)
    args = argparse.Namespace(pr="7", pr_grind_check_script=None, pr_grind_timeout=10)
    repo = {"ok": True, "root": str(repo_path), "github_repository": GITHUB_ORIGIN}
    busdriver = {"ok": False}

    result = ns["run_pr_grind_check"](args, repo, busdriver)

    assert result["ok"] is True
    assert not attacker_ran.exists(), "default pr-grind checker executed attacker-replaced retained path"


def test_invalid_pr_grind_result_fixture_does_not_crash(tmp_path: Path):
    repo = bind_github_origin(init_repo(tmp_path / "repo"))
    plugin = fake_busdriver(tmp_path / "busdriver")
    pr_result = tmp_path / "bad-pr-grind-result.json"
    pr_result.write_text("not-json\n")

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(pr_result))

    assert data["pr_grind"]["ok"] is False
    assert data["pr_grind"]["reason"] == "pr_grind_result_invalid"
    assert data["decision"]["status"] == "blocked"
    assert "pr_grind_result_invalid" in data["decision"]["blockers"]


def test_timed_out_pr_grind_checker_reports_structured_blocker(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    checker = tmp_path / "slow_checker.py"
    checker.write_text('import time\nprint("partial stdout", flush=True)\ntime.sleep(5)\n')

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-check-script", str(checker), "--pr-grind-timeout", "1")

    assert data["pr_grind"]["ok"] is False
    assert data["pr_grind"]["returncode"] == 124
    assert data["pr_grind"]["stdout_tail"] == "partial stdout\n"
    assert "timeout after 1s" in data["pr_grind"]["stderr"]
    assert data["decision"]["status"] == "blocked"
    assert "pr_grind_checker_failed" in data["decision"]["blockers"]


def test_blocking_marker_blocks_delivery(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    marker = repo / ".claude" / "freeze.local"
    marker.parent.mkdir()
    marker.write_text("freeze\n")

    data = invoke(repo, plugin)

    assert data["decision"]["status"] == "blocked"
    assert "blocking_busdriver_marker_present" in data["decision"]["blockers"]
    assert data["markers"]["blocking"][0]["name"] == "freeze.local"


def test_blocking_marker_with_dirty_tree_keeps_blocker_next_action(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    marker = repo / ".claude" / "freeze.local"
    marker.parent.mkdir()
    marker.write_text("freeze\n")
    (repo / "draft.txt").write_text("draft\n")

    data = invoke(repo, plugin)

    assert data["decision"]["status"] == "blocked"
    assert "blocking_busdriver_marker_present" in data["decision"]["blockers"]
    assert data["decision"]["next_action"] == "Resolve blocking status before delivery."


def test_active_finalization_lock_blocks_delivery_status_handoff(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    state = tmp_path / "relay-state"
    assert run([sys.executable, str(LOCK), "acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "finalization"]).returncode == 0
    (repo / "draft.txt").write_text("draft\n")

    data = invoke_with_lock_status(repo, plugin, state)

    assert data["finalization_lock"]["operation"] == "finalization"
    assert data["finalization_lock"]["active_for_repo_count"] == 1
    assert data["decision"]["status"] == "blocked"
    assert "relay_finalization_lock_active" in data["decision"]["blockers"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["commit_allowed"] is False
    assert data["decision"]["push_allowed"] is False
    assert data["decision"]["pr_allowed"] is False
    assert data["decision"]["merge_allowed"] is False


def test_stale_finalization_lock_blocks_delivery_status_handoff(tmp_path: Path):
    """r23: `acquire` refuses a stale lock until an operator recovers it manually.

    Reporting the stale entry while leaving the decision unblocked promises a handoff that the
    finalization executor is guaranteed to refuse with `finalization_lock_not_acquired`.
    """
    repo = init_repo(tmp_path / "repo-stale-lock")
    plugin = fake_busdriver(tmp_path / "busdriver-stale-lock")
    state = tmp_path / "relay-state-stale-lock"
    assert run([
        sys.executable, str(LOCK), "acquire", "--repo", str(repo),
        "--state-dir", str(state), "--operation", "finalization", "--ttl-seconds", "1",
    ]).returncode == 0
    time.sleep(1.5)
    (repo / "draft.txt").write_text("draft\n")

    data = invoke_with_lock_status(repo, plugin, state)

    assert data["finalization_lock"]["stale_for_repo_count"] == 1
    # A stale lock is not an active holder; the counts keep their existing meanings.
    assert data["finalization_lock"]["active_for_repo_count"] == 0
    assert data["decision"]["status"] == "blocked"
    assert "relay_finalization_lock_stale_manual_recovery" in data["decision"]["blockers"]
    assert "relay_finalization_lock_active" not in data["decision"]["blockers"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["merge_allowed"] is False


def test_active_agent_draft_lock_blocks_delivery_status_handoff(tmp_path: Path):
    """The physical relay lock is repo-wide; operation metadata must not hide conflicts."""
    repo = init_repo(tmp_path / "repo-agent-draft-lock")
    plugin = fake_busdriver(tmp_path / "busdriver-agent-draft-lock")
    state = tmp_path / "relay-state-agent-draft-lock"
    assert run([
        sys.executable, str(LOCK), "acquire", "--repo", str(repo),
        "--state-dir", str(state), "--operation", "agent-draft",
    ]).returncode == 0
    (repo / "draft.txt").write_text("draft\n")

    data = invoke_with_lock_status(repo, plugin, state)

    assert data["finalization_lock"]["active_for_repo_count"] == 1
    assert data["finalization_lock"]["active_for_repo"][0]["operation"] == "agent-draft"
    assert data["decision"]["status"] == "blocked"
    assert "relay_finalization_lock_active" in data["decision"]["blockers"]
    assert data["decision"]["finalization_allowed"] is False
    assert data["decision"]["commit_allowed"] is False
    assert data["decision"]["push_allowed"] is False
    assert data["decision"]["pr_allowed"] is False
    assert data["decision"]["merge_allowed"] is False


def test_finalization_lock_matches_when_repo_is_invoked_through_symlink(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    state = tmp_path / "relay-state"
    repo_link = tmp_path / "repo-link"
    repo_link.symlink_to(repo, target_is_directory=True)
    assert run([sys.executable, str(LOCK), "acquire", "--repo", str(repo), "--state-dir", str(state), "--operation", "finalization"]).returncode == 0

    data = invoke_with_lock_status(repo_link, plugin, state)

    assert data["repo"]["root"] == str(repo.resolve())
    assert data["finalization_lock"]["active_for_repo_count"] == 1
    assert "relay_finalization_lock_active" in data["decision"]["blockers"]


def test_invalid_finalization_lock_status_blocks_delivery_handoff(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    state = tmp_path / "relay-state"
    bad_lock = state / "locks" / "bad.lock" / "lock.json"
    bad_lock.parent.mkdir(parents=True)
    bad_lock.write_text("{not-json\n")
    (repo / "draft.txt").write_text("draft\n")

    data = invoke_with_lock_status(repo, plugin, state)

    assert data["finalization_lock"]["ok"] is False
    assert data["finalization_lock"]["status"] == "invalid_lock_entry"
    assert data["decision"]["status"] == "blocked"
    assert "relay_finalization_lock_status_unavailable" in data["decision"]["blockers"]
    assert data["decision"]["finalization_allowed"] is False


# --- v16-r21: ambient execution containment + structured OSError fail-closed ---

R21_LOADER_INJECTION_ENV = {
    "PYTHONPATH": "/tmp/evil-pythonpath",
    "PYTHONHOME": "/tmp/evil-pythonhome",
    "BASH_ENV": "/tmp/evil-bash-env",
    "ENV": "/tmp/evil-env",
    "ZDOTDIR": "/tmp/evil-zdotdir",
    "LD_PRELOAD": "/tmp/evil.so",
    "DYLD_INSERT_LIBRARIES": "/tmp/evil.dylib",
    "GIT_DIR": "/tmp/evil-git-dir",
}


def test_delivery_status_git_env_is_allowlisted_and_drops_loader_injection(monkeypatch):
    import runpy

    ns = runpy.run_path(str(STATUS))
    for key, value in R21_LOADER_INJECTION_ENV.items():
        monkeypatch.setenv(key, value)

    env = ns["git_env"]()

    assert env["PATH"] == ns["CONTAINED_PATH"]
    for key in ("PYTHONPATH", "PYTHONHOME", "BASH_ENV", "ENV", "ZDOTDIR", "LD_PRELOAD", "DYLD_INSERT_LIBRARIES"):
        assert key not in env, f"{key} leaked into the delivery-status git child environment"
    assert {k: v for k, v in env.items() if k.startswith("GIT_")} == {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_PAGER": "cat",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_ALLOW_PROTOCOL": "",
    }


def test_delivery_status_run_helper_returns_rc_127_on_launch_oserror(tmp_path):
    import runpy

    ns = runpy.run_path(str(STATUS))
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x\n")

    cp = ns["run"](["git", "rev-parse", "HEAD"], cwd=not_a_dir)

    assert cp.returncode == 127
    assert cp.stderr


def test_delivery_status_repo_pointing_at_a_file_fails_closed_without_traceback(tmp_path):
    not_a_dir = tmp_path / "regular-file.txt"
    not_a_dir.write_text("x\n")

    cp = subprocess.run(
        [sys.executable, str(STATUS), "--repo", str(not_a_dir)],
        text=True,
        capture_output=True,
    )

    assert "Traceback" not in cp.stderr
    payload = json.loads(cp.stdout)
    assert payload["repo"]["ok"] is False
    assert payload["repo"]["error"]


def test_delivery_status_never_executes_git_from_the_caller_path(tmp_path):
    ambient_bin = tmp_path / "ambient-bin"
    ambient_bin.mkdir()
    sentinel = tmp_path / "ambient-git-ran"
    ambient_git = ambient_bin / "git"
    ambient_git.write_text(f"#!/bin/sh\nprintf ran > {sentinel}\nexit 0\n")
    ambient_git.chmod(0o700)
    repo = init_repo(tmp_path / "repo")

    subprocess.run(
        [sys.executable, str(STATUS), "--repo", str(repo)],
        text=True,
        capture_output=True,
        env={"PATH": str(ambient_bin), "HOME": str(tmp_path)},
    )

    assert not sentinel.exists(), "delivery-status executed git from the caller-controlled PATH"


def test_delivery_status_python_children_run_isolated(monkeypatch, tmp_path):
    import runpy

    ns = runpy.run_path(str(STATUS))
    captured: list[list[str]] = []

    def fake_run(cmd, cwd=None, timeout=60, env=None):
        captured.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    monkeypatch.setitem(ns["load_lock_status"].__globals__, "run", fake_run)
    ns["load_lock_status"](argparse.Namespace(state_dir=None, no_lock_status=False))

    assert captured
    for cmd in captured:
        assert cmd[0] == "/usr/bin/python3", cmd
        assert cmd[1] == "-I", cmd


def test_lock_status_envelope_never_carries_a_release_token(tmp_path):
    """r24 H1: delivery-status republishes lock payloads; a token in them is a leaked capability."""
    repo = init_repo(tmp_path / "repo-token-leak")
    plugin = fake_busdriver(tmp_path / "busdriver-token-leak")
    state = tmp_path / "relay-state-token-leak"
    acquired = json.loads(run([
        sys.executable, str(LOCK), "acquire", "--repo", str(repo),
        "--state-dir", str(state), "--operation", "finalization",
    ]).stdout)
    token = acquired["token"]

    cp = run([sys.executable, str(STATUS), "--repo", str(repo), "--plugin-root", str(plugin), "--state-dir", str(state), "--no-agent-runs"])
    data = json.loads(cp.stdout)

    assert token not in cp.stdout
    assert data["finalization_lock"]["active_for_repo_count"] == 1
    holder = data["finalization_lock"]["active_for_repo"][0]
    assert "token" not in holder
    assert holder["token_redacted"] is True
    for entry in data["lock_status"]["locks"]:
        assert "token" not in entry


# --- v16-r24 B4: every authority-negative flag must be negative, not just merge_allowed ---

AUTHORITY_NEGATIVE_KEYS = [
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


@pytest.mark.parametrize("flag", AUTHORITY_NEGATIVE_KEYS)
def test_authority_positive_pr_grind_fixture_cannot_launder_into_clean(tmp_path, flag):
    """A forged payload that is otherwise perfectly bound must not promote pr_clean_read_only.

    r23 only rejected decision.merge_allowed, so a payload asserting its own
    finalization_allowed=true still validated and reached ready_for_merge_handoff.
    """
    repo = bind_github_origin(init_repo(tmp_path / f"repo-{flag}"))
    plugin = fake_busdriver(tmp_path / f"busdriver-{flag}")
    payload = pr_grind_payload(pr=7, status="clean")
    payload["decision"][flag] = True
    result_file = tmp_path / f"{flag}.json"
    result_file.write_text(json.dumps(payload))

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(result_file))

    assert data["pr_grind"]["ok"] is False
    assert data["pr_grind"]["reason"] == "pr_grind_result_invalid"
    assert data["decision"]["status"] == "blocked"
    assert "pr_grind_result_invalid" in data["decision"]["blockers"]


@pytest.mark.parametrize("flag", AUTHORITY_NEGATIVE_KEYS)
def test_authority_negative_flag_must_be_present_and_false(tmp_path, flag):
    """Absent is not negative: the canonical set must be asserted, not assumed."""
    repo = bind_github_origin(init_repo(tmp_path / f"repo-missing-{flag}"))
    plugin = fake_busdriver(tmp_path / f"busdriver-missing-{flag}")
    payload = pr_grind_payload(pr=7, status="clean")
    del payload["decision"][flag]
    result_file = tmp_path / f"missing-{flag}.json"
    result_file.write_text(json.dumps(payload))

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(result_file))

    assert data["pr_grind"]["reason"] == "pr_grind_result_invalid"
    assert data["decision"]["status"] == "blocked"


# --- v16-r24 B7: the redaction machinery exists; the pr-grind failure paths skipped it ---

LEAKY_CHILD = '''#!/usr/bin/env python3
import sys
sys.stderr.write("gh: Authorization: bearer ghp_{t}\\n")
sys.stdout.write("{out}")
sys.exit({rc})
'''


def _leaky_script(path: Path, rc: int, out: str) -> Path:
    path.write_text(LEAKY_CHILD.format(t="A" * 36, out=out, rc=rc))
    path.chmod(0o755)
    return path


def test_pr_grind_nonzero_exit_redacts_child_output(tmp_path):
    repo = bind_github_origin(init_repo(tmp_path / "repo-redact-rc"))
    plugin = fake_busdriver(tmp_path / "busdriver-redact-rc")
    script = _leaky_script(tmp_path / "leaky-rc.py", rc=1, out="Authorization: bearer ghp_" + "A" * 36)

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-check-script", str(script))

    blob = json.dumps(data)
    assert "ghp_" not in blob
    assert "[REDACTED]" in data["pr_grind"]["stderr"]
    assert data["pr_grind"]["ok"] is False


def test_pr_grind_parse_error_redacts_child_output(tmp_path):
    repo = bind_github_origin(init_repo(tmp_path / "repo-redact-parse"))
    plugin = fake_busdriver(tmp_path / "busdriver-redact-parse")
    script = _leaky_script(tmp_path / "leaky-parse.py", rc=0, out="not json: token=ghp_" + "A" * 36)

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-check-script", str(script))

    blob = json.dumps(data)
    assert "ghp_" not in blob
    assert "[REDACTED]" in data["pr_grind"]["stdout_tail"]
    assert data["pr_grind"]["ok"] is False


# --- v16-r24 C8: result-file fixtures are diagnostics, never finalization evidence ---


def test_valid_clean_pr_grind_fixture_cannot_produce_pr_clean_read_only(tmp_path):
    """Structural validity is not provenance.

    A result file is authored by whoever names it: every field pr_grind_result_valid() binds is
    content that author controls. It stays readable as a diagnostic, but it must never be the
    evidence that promotes pr_clean_read_only -> ready_for_merge_handoff.
    """
    repo = bind_github_origin(init_repo(tmp_path / "repo-fixture-clean"))
    plugin = fake_busdriver(tmp_path / "busdriver-fixture-clean")
    result_file = tmp_path / "clean.json"
    result_file.write_text(json.dumps(pr_grind_payload(pr=7, status="clean")))

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(result_file))

    assert data["pr_grind"]["ok"] is True
    assert data["pr_grind"]["source"] == "fixture"
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["status"] != "pr_clean_read_only"
    assert "fixture_evidence_not_authoritative" in data["decision"]["blockers"]


def test_clean_pr_grind_fixture_keeps_its_diagnostic_result(tmp_path):
    """Blocked on provenance, not silenced: the fixture is still readable as a diagnostic."""
    repo = bind_github_origin(init_repo(tmp_path / "repo-fixture-diag"))
    plugin = fake_busdriver(tmp_path / "busdriver-fixture-diag")
    result_file = tmp_path / "clean.json"
    result_file.write_text(json.dumps(pr_grind_payload(pr=7, status="clean")))

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-result-file", str(result_file))

    assert data["pr_grind"]["result"]["status"] == "clean"
    assert data["pr_grind"]["source"] == "fixture"


def test_litmus_status_fixture_is_not_authoritative_evidence(tmp_path):
    repo = init_repo(tmp_path / "repo-litmus-fixture")
    plugin = fake_busdriver(tmp_path / "busdriver-litmus-fixture")
    result_file = litmus_status_fixture(tmp_path / "litmus.json", repo=repo, status="pr_review_fresh")

    data = invoke(repo, plugin, "--litmus-status-result-file", str(result_file))

    assert data["litmus_status"]["source"] == "fixture"
    assert data["decision"]["status"] == "blocked"
    assert "fixture_evidence_not_authoritative" in data["decision"]["blockers"]


def test_custom_checker_script_is_non_authoritative_fixture_provenance(tmp_path):
    """Any caller-supplied checker executable is test-double evidence, never live authority."""
    repo = bind_github_origin(init_repo(tmp_path / "repo-live-source"))
    plugin = fake_busdriver(tmp_path / "busdriver-live-source")
    payload = pr_grind_payload(pr=7, status="clean")
    script = tmp_path / "checker.py"
    script.write_text("#!/usr/bin/env python3\nimport json\nprint(json.dumps(%r))\n" % (payload,))
    script.chmod(0o755)

    data = invoke(repo, plugin, "--pr", "7", "--pr-grind-check-script", str(script))

    assert data["pr_grind"]["source"] == "fixture"
    assert data["decision"]["status"] == "blocked"
    assert "fixture_evidence_not_authoritative" in data["decision"]["blockers"]


# --- v16-r25 B6: a failed git observation must never be reported as clean repo truth ---


def _repo_status_with_git(monkeypatch, responses):
    """Drive repo_status() with a scripted git, keyed by the git subcommand."""
    import runpy

    ns = runpy.run_path(str(STATUS))

    def fake_git(repo, *args):
        for key, cp in responses.items():
            if key in args:
                return cp
        return subprocess.CompletedProcess(["git"], 0, "", "")

    def fake_git_status_records(_repo):
        """The status read is NUL-framed now, so the scripted porcelain is reframed, not re-split.

        One scripted line stays one record — these names are the test's own, not an attacker's —
        while production keeps taking its framing from real `-z` NUL bytes.
        """
        cp = responses.get("--porcelain=v1", subprocess.CompletedProcess(["git"], 0, "", ""))
        if cp.returncode != 0:
            return cp.returncode, [], cp
        raw = b"".join(line.encode() + b"\0" for line in cp.stdout.splitlines() if line)
        return 0, ns["parse_porcelain_z"](raw), cp

    monkeypatch.setitem(ns["repo_status"].__globals__, "git", fake_git)
    monkeypatch.setitem(ns["repo_status"].__globals__, "git_status_records", fake_git_status_records)
    monkeypatch.setitem(ns["repo_status"].__globals__, "github_repository", lambda _root: "owner/repo")
    return ns


OK_TOPLEVEL = subprocess.CompletedProcess(["git"], 0, "/tmp/repo\n", "")


@pytest.mark.parametrize("failing", ["--git-dir", "--show-current", "--porcelain=v1"])
def test_repo_status_fails_closed_when_any_git_observation_fails(monkeypatch, tmp_path: Path, failing: str):
    """r24 checked only --show-toplevel's return code.

    Every later git call had its stdout consumed regardless of exit status, so a timeout or a
    failure produced empty stdout, which reads as a clean tree: dirty=false, no entries, ok=true.
    The envelope then reported a synthesized clean repository that was never observed.
    """
    responses = {
        "--show-toplevel": OK_TOPLEVEL,
        failing: subprocess.CompletedProcess(["git"], 128, "", "fatal: broken"),
    }
    ns = _repo_status_with_git(monkeypatch, responses)

    status = ns["repo_status"](str(tmp_path))

    assert status["ok"] is False
    assert status["error"] == "git_observation_failed"
    assert status.get("dirty") is not False


def test_repo_status_unborn_head_is_observed_not_a_failure(monkeypatch, tmp_path: Path):
    """`git init` with no commits has no HEAD; that is a fact and must not block.

    rev-parse --verify --quiet exits 1 saying nothing on an unborn branch. Treating every
    non-zero HEAD read as a failure would block every fresh repository.
    """
    responses = {
        "--show-toplevel": OK_TOPLEVEL,
        "--git-dir": subprocess.CompletedProcess(["git"], 0, "/tmp/repo/.git\n", ""),
        "--show-current": subprocess.CompletedProcess(["git"], 0, "main\n", ""),
        "--verify": subprocess.CompletedProcess(["git"], 1, "", ""),
        "--porcelain=v1": subprocess.CompletedProcess(["git"], 0, "", ""),
    }
    ns = _repo_status_with_git(monkeypatch, responses)

    status = ns["repo_status"](str(tmp_path))

    assert status["ok"] is True
    assert status["head"] == ""
    assert status["dirty"] is False


@pytest.mark.parametrize("cp", [
    subprocess.CompletedProcess(["git"], 124, "", "timeout after 60s"),
    subprocess.CompletedProcess(["git"], 128, "", "fatal: not a valid object name"),
    subprocess.CompletedProcess(["git"], 1, "", "fatal: broken"),
])
def test_repo_status_head_read_failure_is_not_mistaken_for_an_unborn_branch(monkeypatch, tmp_path: Path, cp):
    """A timed-out or broken HEAD read produces the same empty stdout an unborn branch does.

    Only rc 1 with NO stderr means "no commit yet"; everything else is an unanswered question.
    """
    responses = {
        "--show-toplevel": OK_TOPLEVEL,
        "--git-dir": subprocess.CompletedProcess(["git"], 0, "/tmp/repo/.git\n", ""),
        "--show-current": subprocess.CompletedProcess(["git"], 0, "main\n", ""),
        "--verify": cp,
        "--porcelain=v1": subprocess.CompletedProcess(["git"], 0, "", ""),
    }
    ns = _repo_status_with_git(monkeypatch, responses)

    status = ns["repo_status"](str(tmp_path))

    assert status["ok"] is False
    assert status["error"] == "git_observation_failed"
    assert status["observation"] == "head"


def test_repo_status_fails_closed_on_git_timeout(monkeypatch, tmp_path: Path):
    """run() turns a timeout into rc 124 with partial stdout; partial is not observed truth."""
    responses = {
        "--show-toplevel": OK_TOPLEVEL,
        "--porcelain=v1": subprocess.CompletedProcess(["git"], 124, " M partial\n", "timeout after 60s"),
    }
    ns = _repo_status_with_git(monkeypatch, responses)

    status = ns["repo_status"](str(tmp_path))

    assert status["ok"] is False
    assert status["error"] == "git_observation_failed"


# Escapes, never literals: a literal U+2028 in this source is invisible and does not survive an
# editor round-trip, which silently turns the case that actually reproduced into a space.
@pytest.mark.parametrize(
    "separator",
    ["\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"],
    ids=["LF", "CR", "VT", "FF", "FS", "GS", "RS", "NEL", "LS", "PS"],
)
def test_hostile_pathname_never_fabricates_an_entry_in_the_envelope(tmp_path: Path, separator: str):
    """One untracked file must produce exactly one entry, whatever it is named.

    Measured against real git: with a repo-local `core.quotePath=false` (which
    GIT_CONFIG_NOSYSTEM does not reach), NEL/LS/PS reach the output raw, and `splitlines()` split
    one record into two — the second a fabricated ` M .claude/...` marker record that readiness and
    deliver read as real evidence.
    """
    import runpy

    ns = runpy.run_path(str(STATUS))
    repo = init_repo(tmp_path / f"repo-framing-{ord(separator):04x}")
    assert run(["git", "config", "core.quotePath", "false"], repo).returncode == 0
    hostile = repo / f"evil{separator} M .claude"
    hostile.mkdir()
    (hostile / "litmus-passed.local").write_text("fabricator\n")

    status = ns["repo_status"](str(repo))

    assert status["ok"] is True
    assert status["dirty"] is True
    assert status["dirty_entries_total_count"] == 1
    assert status["untracked_entries_total_count"] == 1
    assert status["staged_entries_total_count"] == 0
    assert status["unstaged_entries_total_count"] == 0
    # No raw separator survives into the envelope for the next parser to re-split.
    assert separator not in status["dirty_entries"][0]
    assert len(status["dirty_entries"][0].splitlines()) == 1


def test_repo_status_keeps_full_dirty_truth_when_every_observation_succeeds(monkeypatch, tmp_path: Path):
    """The fix must not cost the r24 win: exact totals plus bounded arrays on the success path."""
    lines = "".join(f" M file{i}.py\n" for i in range(500))
    responses = {
        "--show-toplevel": OK_TOPLEVEL,
        "--git-dir": subprocess.CompletedProcess(["git"], 0, "/tmp/repo/.git\n", ""),
        "--show-current": subprocess.CompletedProcess(["git"], 0, "main\n", ""),
        "--verify": subprocess.CompletedProcess(["git"], 0, "a" * 40 + "\n", ""),
        "--porcelain=v1": subprocess.CompletedProcess(["git"], 0, lines, ""),
    }
    ns = _repo_status_with_git(monkeypatch, responses)

    status = ns["repo_status"](str(tmp_path))

    assert status["ok"] is True
    assert status["dirty"] is True
    assert status["dirty_entries_total_count"] == 500
    assert status["dirty_entries_truncated"] is True
    assert len(status["dirty_entries"]) < 500


def test_repo_status_upstream_absence_is_not_an_observation_failure(monkeypatch, tmp_path: Path):
    """`@{u}` legitimately exits non-zero on a branch with no upstream; that is a fact, not a failure."""
    responses = {
        "--show-toplevel": OK_TOPLEVEL,
        "--git-dir": subprocess.CompletedProcess(["git"], 0, "/tmp/repo/.git\n", ""),
        "--show-current": subprocess.CompletedProcess(["git"], 0, "main\n", ""),
        "--verify": subprocess.CompletedProcess(["git"], 0, "a" * 40 + "\n", ""),
        "@{u}": subprocess.CompletedProcess(["git"], 128, "", "fatal: no upstream"),
        "--porcelain=v1": subprocess.CompletedProcess(["git"], 0, "", ""),
    }
    ns = _repo_status_with_git(monkeypatch, responses)

    status = ns["repo_status"](str(tmp_path))

    assert status["ok"] is True
    assert status["upstream"] is None
    assert status["dirty"] is False


def test_repo_status_observation_failure_blocks_the_top_level_envelope(monkeypatch, tmp_path: Path):
    import runpy

    ns = runpy.run_path(str(STATUS))
    decision = ns["delivery_decision"](
        {"ok": False, "error": "git_observation_failed"},
        {"ok": True, "plugin_root": "/x"}, {}, {"ok": True}, None, None, {"ok": True}, None, None,
    )

    assert "repo_not_available" in decision["blockers"]
    assert decision["status"] == "blocked"


# --- v16-r25 B5: delivery-status bypasses of its own redaction machinery ---


def test_lock_status_failure_is_redacted(monkeypatch, tmp_path: Path):
    import runpy

    ns = runpy.run_path(str(STATUS))
    secret = "ghp_" + "d" * 36
    monkeypatch.setitem(ns["load_lock_status"].__globals__, "run", lambda *_a, **_k: subprocess.CompletedProcess(["lock"], 1, "", f"{secret} " + "x" * 9000))
    args = type("Args", (), {"no_lock_status": False, "state_dir": None})()

    result = ns["load_lock_status"](args)

    assert secret not in json.dumps(result)
    assert len(result["stderr"]) <= 4000


def test_lock_status_parse_error_stdout_tail_is_redacted(monkeypatch, tmp_path: Path):
    import runpy

    ns = runpy.run_path(str(STATUS))
    secret = "ghp_" + "e" * 36
    monkeypatch.setitem(ns["load_lock_status"].__globals__, "run", lambda *_a, **_k: subprocess.CompletedProcess(["lock"], 0, f"not json {secret}", ""))
    args = type("Args", (), {"no_lock_status": False, "state_dir": None})()

    result = ns["load_lock_status"](args)

    assert result["ok"] is False
    assert secret not in json.dumps(result)


def test_repo_status_not_a_git_repo_stderr_is_redacted(monkeypatch, tmp_path: Path):
    responses = {"--show-toplevel": subprocess.CompletedProcess(["git"], 128, "", "fatal: ghp_" + "f" * 36)}
    ns = _repo_status_with_git(monkeypatch, responses)

    status = ns["repo_status"](str(tmp_path))

    assert status["ok"] is False
    assert "ghp_" not in json.dumps(status)


# --- v16-r26A item 6: latest_agent_runs must validate and redact before it becomes evidence ---


AGENT_DRAFT_SCHEMA = "hermes-busdriver-agent-draft/v0"


def _write_agent_run(state: Path, name: str, payload: dict) -> Path:
    run_dir = state / "agent-runs" / name
    run_dir.mkdir(parents=True)
    report = run_dir / "final-report.json"
    report.write_text(json.dumps(payload))
    return report


def _valid_agent_run(repo_root: str, **overrides: Any) -> dict:
    payload = {
        "schema": AGENT_DRAFT_SCHEMA,
        "ok": False,
        "status": "needs_busdriver_review",
        "agent": "pi",
        "repo": repo_root,
        "run_dir": "/tmp/run",
        "decision": {
            "status": "needs_busdriver_review",
            "finalization_allowed": False,
            "commit_allowed": False,
            "push_allowed": False,
            "pr_allowed": False,
            "merge_allowed": False,
            "deploy_allowed": False,
            "release_allowed": False,
            "publish_allowed": False,
            "marker_write_allowed": False,
        },
    }
    payload.update(overrides)
    return payload


def _agent_runs(repo: Path, plugin: Path, state: Path) -> list[dict]:
    cp = run([
        sys.executable, str(STATUS), "--repo", str(repo), "--plugin-root", str(plugin),
        "--state-dir", str(state), "--no-lock-status",
    ])
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return json.loads(cp.stdout)["recent_agent_runs"]


def test_agent_run_with_authority_positive_decision_is_not_valid_evidence(tmp_path):
    """This probe's own invariant: every result it reads carries the authority flags false."""
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "plugin")
    state = tmp_path / "state"
    forged = _valid_agent_run(str(repo.resolve()))
    forged["decision"] = {"status": "done", "finalization_allowed": True, "merge_allowed": True}
    _write_agent_run(state, "forged", forged)

    runs = _agent_runs(repo, plugin, state)

    assert len(runs) == 1
    entry = runs[0]
    assert entry.get("valid") is False
    assert entry.get("reason") == "agent_run_authority_flags_unsafe"
    assert entry.get("decision") is None, "authority-positive decision surfaced as evidence"


def test_agent_run_with_wrong_schema_is_not_valid_evidence(tmp_path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "plugin")
    state = tmp_path / "state"
    _write_agent_run(state, "wrong", _valid_agent_run(str(repo.resolve()), schema="totally-other/v9"))

    runs = _agent_runs(repo, plugin, state)

    assert runs[0]["valid"] is False
    assert runs[0]["reason"] == "agent_run_schema_invalid"
    assert runs[0].get("decision") is None


def test_agent_run_secret_is_redacted_before_inclusion(tmp_path):
    """The only envelope path that bypassed redaction; a token in a report was emitted raw."""
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "plugin")
    state = tmp_path / "state"
    payload = _valid_agent_run(str(repo.resolve()))
    payload["decision"]["reason"] = "push failed for https://" + "x-access-token:" + "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAA@github.com/o/r"
    _write_agent_run(state, "secret", payload)

    cp = run([
        sys.executable, str(STATUS), "--repo", str(repo), "--plugin-root", str(plugin),
        "--state-dir", str(state), "--no-lock-status",
    ])
    assert cp.returncode == 0, cp.stderr

    assert "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAA" not in cp.stdout, "agent run leaked a token into the envelope"
    runs = json.loads(cp.stdout)["recent_agent_runs"]
    assert runs[0]["valid"] is True
    assert "[REDACTED]" in json.dumps(runs[0])


def test_agent_run_malformed_type_is_not_valid_evidence(tmp_path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "plugin")
    state = tmp_path / "state"
    _write_agent_run(state, "malformed", _valid_agent_run(str(repo.resolve()), status={"nested": "object"}))

    runs = _agent_runs(repo, plugin, state)

    assert runs[0]["valid"] is False
    assert runs[0]["reason"] == "agent_run_schema_invalid"


def test_valid_agent_run_is_still_reported_as_evidence(tmp_path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "plugin")
    state = tmp_path / "state"
    _write_agent_run(state, "good", _valid_agent_run(str(repo.resolve())))

    runs = _agent_runs(repo, plugin, state)

    assert runs[0]["valid"] is True
    assert runs[0]["status"] == "needs_busdriver_review"
    assert runs[0]["agent"] == "pi"
    assert runs[0]["decision"]["finalization_allowed"] is False


# --- v16-r26A item 5: default checker live path is reachable; helpers run from retained bytes ---


def test_default_pr_grind_checker_binds_expected_identity_from_trusted_evidence(tmp_path, monkeypatch):
    """The authoritative path must be able to complete a live invocation.

    r25 launched the default checker with only --repo/--pr/--plugin-root, but the checker requires
    expected repository/head/base/ref/SHA in live mode — so the ONLY authoritative path always
    exited `expected_repository_required`, making pr_clean_read_only and merge handoff
    structurally unreachable. The binding comes from trusted local origin + live GitHub evidence.
    """
    import runpy

    repo = init_repo(tmp_path / "repo")
    bind_github_origin(repo)
    plugin = fake_busdriver(tmp_path / "plugin")
    ns = runpy.run_path(str(STATUS))
    captured: dict[str, Any] = {}

    snapshot = {
        "number": 7,
        "html_url": f"https://github.com/{GITHUB_ORIGIN}/pull/7",
        "head": {"sha": "a" * 40, "ref": "feature-branch", "repo": {"full_name": GITHUB_ORIGIN}},
        "base": {"sha": "b" * 40, "ref": "main", "repo": {"full_name": GITHUB_ORIGIN}},
    }
    monkeypatch.setitem(ns["run_pr_grind_check"].__globals__, "github_pr_snapshot", lambda *a, **k: (snapshot, None))

    def fake_run(cmd, cwd=None, timeout=60, env=None):
        captured["cmd"] = list(cmd)
        return subprocess.CompletedProcess(cmd, 0, json.dumps(pr_grind_payload(pr=7)), "")

    monkeypatch.setitem(ns["run_pr_grind_check"].__globals__, "run", fake_run)

    args = argparse.Namespace(
        pr_grind_result_file=None, pr="7", pr_grind_check_script=None, pr_grind_timeout=60,
    )
    repo_state = {"ok": True, "root": str(repo.resolve()), "github_repository": GITHUB_ORIGIN}
    result = ns["run_pr_grind_check"](args, repo_state, {"ok": False})

    cmd = captured["cmd"]
    for flag, value in (
        ("--expected-repository", GITHUB_ORIGIN),
        ("--expected-head-repository", GITHUB_ORIGIN),
        ("--expected-head-ref", "feature-branch"),
        ("--expected-base-repository", GITHUB_ORIGIN),
        ("--expected-base-ref", "main"),
        ("--expected-head-sha", "a" * 40),
        ("--expected-base-sha", "b" * 40),
    ):
        assert flag in cmd, f"{flag} was never passed to the default checker"
        assert cmd[cmd.index(flag) + 1] == value
    assert result["ok"] is True
    assert result["source"] == "script"


def test_default_pr_grind_checker_runs_from_retained_stdin_bytes_not_source_path(tmp_path, monkeypatch):
    """Hash-then-path leaves a TOCTOU window: the retained bytes must be what execute."""
    import runpy

    repo = init_repo(tmp_path / "repo")
    bind_github_origin(repo)
    ns = runpy.run_path(str(STATUS))
    captured: dict[str, Any] = {}

    snapshot = {
        "number": 7,
        "html_url": f"https://github.com/{GITHUB_ORIGIN}/pull/7",
        "head": {"sha": "a" * 40, "ref": "feature-branch", "repo": {"full_name": GITHUB_ORIGIN}},
        "base": {"sha": "b" * 40, "ref": "main", "repo": {"full_name": GITHUB_ORIGIN}},
    }
    monkeypatch.setitem(ns["run_pr_grind_check"].__globals__, "github_pr_snapshot", lambda *a, **k: (snapshot, None))

    def fake_run(cmd, cwd=None, timeout=60, env=None):
        captured["cmd"] = list(cmd)
        captured["stdin_bytes"] = getattr(cmd, "stdin_bytes", None)
        return subprocess.CompletedProcess(cmd, 0, json.dumps(pr_grind_payload(pr=7)), "")

    monkeypatch.setitem(ns["run_pr_grind_check"].__globals__, "run", fake_run)

    args = argparse.Namespace(pr_grind_result_file=None, pr="7", pr_grind_check_script=None, pr_grind_timeout=60)
    ns["run_pr_grind_check"](args, {"ok": True, "root": str(repo.resolve()), "github_repository": GITHUB_ORIGIN}, {"ok": False})

    cmd = captured["cmd"]
    executed = next(Path(str(value)) for value in cmd if Path(str(value)).name == "hermes-busdriver-pr-grind-check")
    assert executed == ROOT / "scripts" / "hermes-busdriver-pr-grind-check"
    assert "-c" in cmd
    assert "sys.stdin.buffer.read" in cmd[cmd.index("-c") + 1]
    stdin_bytes = captured["stdin_bytes"]
    assert isinstance(stdin_bytes, bytes)
    assert hashlib.sha256(stdin_bytes).hexdigest() == ns["TRUSTED_RELAY_HELPER_DIGESTS"]["scripts/hermes-busdriver-pr-grind-check"]


def test_default_pr_grind_checker_snapshot_failure_fails_closed(tmp_path, monkeypatch):
    import runpy

    repo = init_repo(tmp_path / "repo")
    bind_github_origin(repo)
    ns = runpy.run_path(str(STATUS))
    monkeypatch.setitem(
        ns["run_pr_grind_check"].__globals__, "github_pr_snapshot",
        lambda *a, **k: (None, "github_pr_snapshot_unavailable"),
    )

    args = argparse.Namespace(pr_grind_result_file=None, pr="7", pr_grind_check_script=None, pr_grind_timeout=60)
    result = ns["run_pr_grind_check"](args, {"ok": True, "root": str(repo.resolve()), "github_repository": GITHUB_ORIGIN}, {"ok": False})

    assert result["ok"] is False
    assert "snapshot" in result["reason"] or "identity" in result["reason"]


# --- v16-r27 item 1: a caller-named helper is an arbitrary executable, so it gets no credentials ---

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


def credential_env(**extra: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update({key: SENTINEL_TOKEN for key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN")})
    env.update(extra)
    return env


def invoke_with_credentials(repo: Path, plugin: Path, *extra: str) -> dict:
    cp = subprocess.run(
        [sys.executable, str(status_entrypoint(extra)), "--repo", str(repo), "--plugin-root", str(plugin), "--no-lock-status", "--no-agent-runs", *extra],
        text=True, capture_output=True, check=False, env=credential_env(),
    )
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return json.loads(cp.stdout)


def assert_no_credentials(dump: Path) -> None:
    assert dump.exists(), "the custom helper never ran, so the test proves nothing"
    handed = json.loads(dump.read_text())
    leaked = sorted(key for key, value in handed.items() if SENTINEL_TOKEN in value)
    assert not leaked, f"custom helper received GitHub credentials via {leaked}"


def test_custom_pr_grind_check_script_receives_no_credentials(tmp_path):
    repo = init_repo(tmp_path / "repo")
    bind_github_origin(repo)
    dump = tmp_path / "pr-env.json"
    script = env_dump_helper(tmp_path / "checker", dump, json.dumps(pr_grind_payload(pr=7, status="clean")))

    invoke_with_credentials(repo, fake_busdriver(tmp_path / "plugin"), "--pr", "7", "--pr-grind-check-script", str(script))

    assert_no_credentials(dump)


def test_custom_litmus_status_script_receives_no_credentials(tmp_path):
    repo = init_repo(tmp_path / "repo")
    dump = tmp_path / "litmus-env.json"
    script = env_dump_helper(
        tmp_path / "litmus",
        dump,
        json.dumps({"schema": "hermes-busdriver-litmus-status/v0", "ok": True, "read_only": True, "decision": {"status": "stale_or_missing"}}),
    )

    invoke_with_credentials(repo, fake_busdriver(tmp_path / "plugin"), "--litmus-status-script", str(script))

    assert_no_credentials(dump)


def test_custom_relay_role_script_receives_no_credentials(tmp_path):
    repo = init_repo(tmp_path / "repo")
    dump = tmp_path / "role-env.json"
    script = env_dump_helper(tmp_path / "role", dump, json.dumps({"ok": True, "role": "relay.pr.backstop"}))

    invoke_with_credentials(
        repo, fake_busdriver(tmp_path / "plugin"),
        "--relay-role", "relay.pr.backstop", "--relay-role-script", str(script),
    )

    assert_no_credentials(dump)


# --- v16-r27 item 2: the authenticated live PR snapshot IS the call the token exists for ---


def fake_gh(path: Path, dump: Path, pr: int, *, fail_with: str | None = None) -> Path:
    """A stand-in `gh` that records its environment and answers `gh api repos/o/r/pulls/N`."""
    snapshot = {
        "number": pr,
        "html_url": f"https://github.com/{GITHUB_ORIGIN}/pull/{pr}",
        "head": {"ref": "feature-branch", "sha": "a" * 40, "repo": {"full_name": GITHUB_ORIGIN}},
        "base": {"ref": "main", "sha": "b" * 40, "repo": {"full_name": GITHUB_ORIGIN}},
    }
    body = (
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"open({str(dump)!r}, 'w').write(json.dumps(dict(os.environ)))\n"
    )
    if fail_with:
        body += f"sys.stderr.write({fail_with!r})\nsys.exit(1)\n"
    else:
        body += f"print(json.dumps({snapshot!r}))\n"
    path.write_text(body)
    path.chmod(0o755)
    return path


def test_default_pr_snapshot_receives_credentials_in_token_only_ci(tmp_path, monkeypatch):
    """Token-only/headless CI has no disk-backed `gh auth login` to fall back on.

    r26 handed this call a credential-free environment, so the snapshot always failed and the only
    authoritative checker path was structurally unreachable wherever a token was the ONLY auth.
    """
    import runpy

    ns = runpy.run_path(str(STATUS))
    dump = tmp_path / "gh-env.json"
    gh = fake_gh(tmp_path / "gh", dump, 7)
    monkeypatch.setitem(ns["github_pr_snapshot"].__globals__, "trusted_executable_path", lambda name: gh)
    monkeypatch.setenv("GH_TOKEN", SENTINEL_TOKEN)
    monkeypatch.setenv("GITHUB_TOKEN", SENTINEL_TOKEN)

    snapshot, error = ns["github_pr_snapshot"](tmp_path, GITHUB_ORIGIN, 7)

    assert error is None and snapshot["number"] == 7
    handed = json.loads(dump.read_text())
    assert handed.get("GH_TOKEN") == SENTINEL_TOKEN
    assert handed.get("GITHUB_TOKEN") == SENTINEL_TOKEN
    assert handed["PATH"] == ns["CONTAINED_PATH"], "credentials must not come with an ambient PATH"


def test_default_pr_snapshot_still_redacts_a_credential_it_echoes(tmp_path, monkeypatch):
    """Credentials reaching `gh` must not become credentials reaching the envelope."""
    import runpy

    ns = runpy.run_path(str(STATUS))
    gh = fake_gh(tmp_path / "gh", tmp_path / "gh-env.json", 7, fail_with=f"HTTP 401 using {SENTINEL_TOKEN}\n")
    monkeypatch.setitem(ns["github_pr_snapshot"].__globals__, "trusted_executable_path", lambda name: gh)
    monkeypatch.setenv("GH_TOKEN", SENTINEL_TOKEN)

    snapshot, error = ns["github_pr_snapshot"](tmp_path, GITHUB_ORIGIN, 7)

    assert snapshot is None and error == "github_pr_snapshot_unavailable"
    assert SENTINEL_TOKEN not in ns["sanitized_tail"](f"HTTP 401 using {SENTINEL_TOKEN}")


# --- v16-r27 item 7: an untrusted state dir must not be able to abort the whole probe ---


def invoke_with_agent_runs(repo: Path, plugin: Path, state: Path) -> dict:
    cp = run([sys.executable, str(STATUS), "--repo", str(repo), "--plugin-root", str(plugin), "--no-lock-status", "--state-dir", str(state)])
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return json.loads(cp.stdout)


def agent_run_report(runs_dir: Path, name: str, payload: dict) -> Path:
    run_dir = runs_dir / name
    run_dir.mkdir(parents=True)
    report = run_dir / "final-report.json"
    report.write_text(json.dumps(payload))
    return report


def valid_agent_run(repo: Path) -> dict:
    return {
        "schema": "hermes-busdriver-agent-draft/v0",
        "ok": True,
        "status": "needs_busdriver_review",
        "repo": str(repo.resolve()),
        **{key: False for key in [
            "finalization_allowed", "commit_allowed", "push_allowed", "pr_allowed", "merge_allowed",
            "deploy_allowed", "release_allowed", "publish_allowed", "marker_write_allowed",
        ]},
    }


def test_broken_report_symlink_does_not_abort_the_status_probe(tmp_path):
    """r26 Low: `p.stat()` sat in the sort key, outside the handler, so one dangling link raised.

    The state dir is declared untrusted; a single broken symlink inside it taking down every
    unrelated reading is an availability defect, not a filter.
    """
    repo = init_repo(tmp_path / "repo")
    state = tmp_path / "state"
    runs = state / "agent-runs"
    agent_run_report(runs, "good", valid_agent_run(repo))
    broken_dir = runs / "broken"
    broken_dir.mkdir()
    (broken_dir / "final-report.json").symlink_to(tmp_path / "nowhere-at-all.json")

    data = invoke_with_agent_runs(repo, fake_busdriver(tmp_path / "plugin"), state)

    reports = data["recent_agent_runs"]
    assert reports, "the valid run was lost with the broken one"
    assert any(row.get("valid") for row in reports)


def test_report_symlink_is_not_followed(tmp_path):
    """A symlinked report is an egress primitive: it reads a file the operator never offered."""
    repo = init_repo(tmp_path / "repo")
    state = tmp_path / "state"
    runs = state / "agent-runs"
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps({**valid_agent_run(repo), "status": "exfiltrated-secret-marker"}))
    run_dir = runs / "linked"
    run_dir.mkdir(parents=True)
    (run_dir / "final-report.json").symlink_to(secret)

    data = invoke_with_agent_runs(repo, fake_busdriver(tmp_path / "plugin"), state)

    assert "exfiltrated-secret-marker" not in json.dumps(data)
    for row in data["recent_agent_runs"]:
        assert row.get("valid") is not True


def test_symlinked_run_directory_is_not_followed(tmp_path):
    repo = init_repo(tmp_path / "repo")
    state = tmp_path / "state"
    runs = state / "agent-runs"
    runs.mkdir(parents=True)
    outside = tmp_path / "outside-run"
    outside.mkdir()
    (outside / "final-report.json").write_text(
        json.dumps({**valid_agent_run(repo), "status": "symlinked-run-secret-marker"})
    )
    (runs / "linked").symlink_to(outside, target_is_directory=True)

    data = invoke_with_agent_runs(repo, fake_busdriver(tmp_path / "plugin"), state)

    assert "symlinked-run-secret-marker" not in json.dumps(data)
    assert not any(row.get("valid") is True for row in data["recent_agent_runs"])


def test_non_regular_report_is_refused(tmp_path):
    repo = init_repo(tmp_path / "repo")
    state = tmp_path / "state"
    runs = state / "agent-runs"
    run_dir = runs / "fifo"
    run_dir.mkdir(parents=True)
    os.mkfifo(run_dir / "final-report.json")

    data = invoke_with_agent_runs(repo, fake_busdriver(tmp_path / "plugin"), state)

    for row in data["recent_agent_runs"]:
        assert row.get("valid") is not True


def test_untrusted_report_reader_refuses_hardlinks(tmp_path):
    ns = runpy.run_path(str(STATUS))
    secret = tmp_path / "secret.json"
    secret.write_text('{"secret":"must-not-be-read"}\n')
    report = tmp_path / "final-report.json"
    os.link(secret, report)

    with pytest.raises(OSError, match="refusing_to_read_linked_file"):
        ns["read_untrusted_report"](report)


def test_untrusted_report_reader_completes_short_reads(tmp_path, monkeypatch):
    ns = runpy.run_path(str(STATUS))
    read_report = ns["read_untrusted_report"]
    runtime_os = read_report.__globals__["os"]
    report = tmp_path / "final-report.json"
    expected = b'{"schema":"hermes-busdriver-agent-draft/v0"}\n'
    report.write_bytes(expected)
    real_read = runtime_os.read

    def one_byte_read(fd, count):
        return real_read(fd, min(count, 1))

    monkeypatch.setattr(runtime_os, "read", one_byte_read)

    data, _mtime = read_report(report)

    assert data == expected


def test_untrusted_report_reader_revalidates_pathname_identity(tmp_path, monkeypatch):
    ns = runpy.run_path(str(STATUS))
    read_report = ns["read_untrusted_report"]
    runtime_os = read_report.__globals__["os"]
    report = tmp_path / "final-report.json"
    report.write_bytes(b'{"generation":"reviewed"}\n')
    detached = tmp_path / "detached.json"
    real_read = runtime_os.read
    swapped = []

    def read_then_replace(fd, count):
        data = real_read(fd, count)
        if data and not swapped:
            swapped.append(True)
            report.rename(detached)
            report.write_bytes(b'{"generation":"replacement"}\n')
        return data

    monkeypatch.setattr(runtime_os, "read", read_then_replace)

    with pytest.raises(OSError, match="untrusted_report_changed_during_read"):
        read_report(report)
    assert swapped


# --- v16-r28 item 2: a caller-selected helper is a fixture double, so it never runs live ---
#
# r27 codex-correctness Medium: custom helpers kept the operator's real HOME, so disk-backed
# GitHub auth was readable regardless of which env vars were stripped. Env stripping and a HOME
# override do not sandbox same-UID arbitrary Python — nothing here claims they do. The boundary
# is that the caller's program is never spawned in a live run at all.

CUSTOM_HELPER_INVOCATIONS = {
    "pr_grind_check": ("--pr", "7", "--pr-grind-check-script"),
    "litmus_status": ("--litmus-status-script",),
    "relay_role": ("--relay-role", "relay.pr.backstop", "--relay-role-script"),
}


def spawn_witness(path: Path, witness: Path) -> Path:
    """A helper whose only job is to prove, by side effect, whether it was ever executed."""
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        f"open({str(witness)!r}, 'w').write('spawned')\n"
        "print(json.dumps({'ok': True}))\n"
    )
    path.chmod(0o755)
    return path


@pytest.mark.parametrize("helper", sorted(CUSTOM_HELPER_INVOCATIONS))
def test_custom_helper_is_never_spawned_in_live_mode(tmp_path, helper):
    repo = init_repo(tmp_path / "repo")
    bind_github_origin(repo)
    witness = tmp_path / f"{helper}-spawned"
    script = spawn_witness(tmp_path / helper, witness)
    *flags, script_flag = CUSTOM_HELPER_INVOCATIONS[helper]

    cp = run(
        [
            sys.executable, str(STATUS), "--repo", str(repo),
            "--plugin-root", str(fake_busdriver(tmp_path / "plugin")),
            "--no-lock-status", "--no-agent-runs", *flags, script_flag, str(script),
        ]
    )

    assert cp.returncode == 2, "production accepted a caller-selected helper"
    error = json.loads(cp.stdout)
    assert error["ok"] is False
    assert error["error"] == "custom_helper_execution_not_permitted"
    assert not witness.exists(), "the caller's program was spawned by production"


@pytest.mark.parametrize("helper", sorted(CUSTOM_HELPER_INVOCATIONS))
def test_production_refuses_custom_helper_under_every_flag_combination(tmp_path, helper):
    """r32 item 1: no argv reaches a caller-named executable through the production entrypoint.

    r28's --fixture-mode is the specific bypass this closes, so it leads the list — but the point
    is that production offers no opt-in at all, not that one particular spelling is refused.
    """
    repo = init_repo(tmp_path / "repo")
    bind_github_origin(repo)
    *flags, script_flag = CUSTOM_HELPER_INVOCATIONS[helper]

    for index, combination in enumerate((
        ["--fixture-mode"],
        ["--fixture-mode=true"],
        ["--fixture-mode", "--pretty"],
        ["--pretty"],
        [],
    )):
        witness = tmp_path / f"{helper}-{index}-spawned"
        script = spawn_witness(tmp_path / f"{helper}-probe-{index}", witness)
        cp = run(
            [
                sys.executable, str(STATUS), "--repo", str(repo),
                "--plugin-root", str(fake_busdriver(tmp_path / "plugin")),
                "--no-lock-status", "--no-agent-runs", *combination,
                *flags, script_flag, str(script),
            ]
        )

        assert cp.returncode == 2, f"production accepted {combination}: {cp.stdout}"
        assert not witness.exists(), f"the caller's program was spawned under {combination}"


def test_production_cli_does_not_expose_fixture_mode(tmp_path):
    """The flag is gone from the surface, not merely ignored — argparse must not know it."""
    cp = run([sys.executable, str(STATUS), "--help"])

    assert cp.returncode == 0, cp.stderr
    assert "--fixture-mode" not in cp.stdout
    assert "fixture_mode" not in cp.stdout


@pytest.mark.parametrize("helper", sorted(CUSTOM_HELPER_INVOCATIONS))
def test_custom_helper_runs_only_through_the_source_separated_harness(tmp_path, helper):
    repo = init_repo(tmp_path / "repo")
    bind_github_origin(repo)
    witness = tmp_path / f"{helper}-spawned"
    script = spawn_witness(tmp_path / helper, witness)
    *flags, script_flag = CUSTOM_HELPER_INVOCATIONS[helper]

    cp = run(
        [
            sys.executable, str(STATUS_HARNESS), "--repo", str(repo),
            "--plugin-root", str(fake_busdriver(tmp_path / "plugin")),
            "--no-lock-status", "--no-agent-runs",
            *flags, script_flag, str(script),
        ]
    )

    assert cp.returncode in (0, 2), cp.stderr + cp.stdout
    assert witness.exists(), "the harness should still run the fixture double"


def test_fixture_mode_envelope_is_authority_negative(tmp_path):
    """Running as a fixture must never buy authority: the envelope stays blocked and labeled."""
    repo = init_repo(tmp_path / "repo")
    bind_github_origin(repo)
    script = env_dump_helper(tmp_path / "checker", tmp_path / "env.json", json.dumps(pr_grind_payload(pr=7, status="clean")))

    data = invoke(repo, fake_busdriver(tmp_path / "plugin"), "--pr", "7", "--pr-grind-check-script", str(script))

    assert data["pr_grind"]["source"] == "fixture"
    # The helper printed a forged-clean payload; provenance must keep it out of the verdict.
    assert data["decision"]["status"] != "pr_clean_read_only"
    assert "fixture_evidence_not_authoritative" in data["decision"]["blockers"]
    assert data["fixture_mode"] is True


@pytest.mark.parametrize("helper", sorted(CUSTOM_HELPER_INVOCATIONS))
def test_fixture_mode_helper_receives_no_real_credential_env(tmp_path, helper):
    """Authority-negative is not enough on its own: the fixture double also gets no token."""
    repo = init_repo(tmp_path / "repo")
    bind_github_origin(repo)
    dump = tmp_path / f"{helper}-env.json"
    payloads = {
        "pr_grind_check": json.dumps(pr_grind_payload(pr=7, status="clean")),
        "litmus_status": json.dumps({"schema": "hermes-busdriver-litmus-status/v0", "ok": True, "read_only": True, "decision": {"status": "stale_or_missing"}}),
        "relay_role": json.dumps({"ok": True, "role": "relay.pr.backstop"}),
    }
    script = env_dump_helper(tmp_path / helper, dump, payloads[helper])
    *flags, script_flag = CUSTOM_HELPER_INVOCATIONS[helper]

    cp = subprocess.run(
        [
            sys.executable, str(STATUS_HARNESS), "--repo", str(repo),
            "--plugin-root", str(fake_busdriver(tmp_path / "plugin")),
            "--no-lock-status", "--no-agent-runs",
            *flags, script_flag, str(script),
        ],
        text=True, capture_output=True, check=False, env=credential_env(),
    )

    assert cp.returncode in (0, 2), cp.stderr + cp.stdout
    assert_no_credentials(dump)


# --- v16-r33 A: production cannot regain a caller-supplied evidence parser ---


PRODUCTION_EVIDENCE_ENTRYPOINTS = [
    "scripts/hermes-busdriver-delivery-status",
    "scripts/hermes-busdriver-finalization-readiness",
    "scripts/hermes-busdriver-pr-grind-loop",
    "scripts/hermes-busdriver-pr-grind-check",
]

# Spelled as fragments rather than whole flags so a rename cannot slip past: `--pr-grind-result-file`
# and `--pr-grind-result-path` are the same affordance, and the enumeration is here to survive the
# next person who needs "just one" injected result.
FORBIDDEN_INJECTION_FRAGMENTS = ("-result-file", "-result-path", "--fixture-mode", "-fixture-result")


@pytest.mark.parametrize("module_path", PRODUCTION_EVIDENCE_ENTRYPOINTS)
def test_no_production_parser_accepts_an_injected_result_or_fixture_argument(module_path: str):
    """The static enumeration, so the affordance cannot come back one flag at a time.

    A caller-supplied result file proves SHAPE, never provenance: validation binds schema, origin,
    PR number and authority flags, and every one of those bytes is authored by whoever wrote the
    file. Labelling it `fixture` afterwards does not change what production is: an entrypoint that
    parses caller-authored evidence. The doubles live in tests/fixtures/*-test-harness, which is
    source-separated and never installed, so this asserts on the production source itself rather
    than on any behaviour a flag could re-enable.
    """
    # Read the add_argument CALLS out of the AST rather than matching lines. pr-grind-loop spells
    # its parser over several lines, so a line-oriented check finds `add_argument(` and the flag
    # name on different lines and reports a pass it did not earn — the exact vacuous-test shape
    # this file's other enumerations exist to avoid.
    tree = ast.parse((ROOT / module_path).read_text())
    offenders = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "add_argument":
            continue
        for argument in node.args:
            if not (isinstance(argument, ast.Constant) and isinstance(argument.value, str)):
                continue
            if any(fragment in argument.value for fragment in FORBIDDEN_INJECTION_FRAGMENTS):
                offenders.append(f"line {node.lineno}: {argument.value}")

    assert offenders == [], (
        f"{module_path} parses caller-supplied evidence again:\n" + "\n".join(offenders)
    )


def test_the_delivery_status_harness_is_not_reachable_from_production():
    """Source separation is the whole mechanism, so it gets its own assertion."""
    for module_path in PRODUCTION_EVIDENCE_ENTRYPOINTS:
        tree = ast.parse((ROOT / module_path).read_text())
        # Prose naming the harness is the boundary being DOCUMENTED, and that documentation is the
        # point — the refusals are only auditable if they say where the doubles went. What must not
        # exist is a string production could ACT on, so docstrings are excluded by identity rather
        # than by a grep that cannot tell an explanation from a path.
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and ast.get_docstring(node) is not None
        }
        offenders = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and ("tests/fixtures" in node.value or "test-harness" in node.value)
        ]
        assert offenders == [], f"{module_path} reaches a test harness: {offenders}"


# --- v16-r33 B2a / r32 High 1: every child object is untrusted, so nothing it nests is emitted ---
#
# The r32 chain: `pr_grind_result_valid` binds the fields it REQUIRES and says nothing about the
# ones it does not, so a fully-bound result carrying an extra nested `token` was accepted, retained
# under `result`, and printed. The same hole exists in every other child path — relay-role, phase0,
# lock, the agent-run reports — because `redact_value` matches VALUE SHAPES (`ghp_…`, `token: x`, a
# URL userinfo) and an opaque enterprise credential under an opaque key has no shape to match. The
# key is the only thing that names it, so the key is what has to be read.

# Matches no SENSITIVE_PATTERN by design: shape-based redaction cannot see this, which is the point.
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
        "apikey": sentinel,
        "password": sentinel,
        "private_key": sentinel,
        "unknown_extra_field": {"list_of": [{"token": sentinel}, [{"secret": sentinel}]]},
    }


def sanitizer(name: str = "sanitized_payload"):
    return __import__("runpy").run_path(str(STATUS))[name]


def relay_role_double(path: Path, stdout: str) -> Path:
    """A caller-named relay-role helper. Production refuses these; the harness is how tests get one."""
    path.write_text(f"import sys\nsys.stdout.write({stdout!r})\n")
    path.chmod(0o755)
    return path


def relay_role_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "hermes-busdriver-relay-role/v0",
        "role": "relay.pr.backstop",
        "read_only": True,
        "ok": True,
        "dispatch_allowed": True,
        "mutation_allowed": False,
        "finalization_allowed": False,
        "not_busdriver_native_claude_runtime": True,
        "decision": {
            "dispatch_allowed": True,
            "mutation_allowed": False,
            "finalization_allowed": False,
            "not_busdriver_native_claude_runtime": True,
        },
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("sentinel", [OPAQUE_CAPABILITY, SHAPED_CAPABILITY])
def test_sanitizer_redacts_capability_shaped_keys_at_every_depth(sentinel: str):
    """Unknown nested data must not bypass the funnel — including keys nobody enumerated."""
    out = sanitizer()(hostile_capabilities(sentinel))

    assert sentinel not in json.dumps(out)
    assert out["token"] == "[REDACTED]"
    assert out["unknown_extra_field"]["list_of"][0]["token"] == "[REDACTED]"


def test_sanitizer_keeps_facts_about_capabilities_typed():
    """`token_redacted: true` is a fact ABOUT a capability, not one: no secret fits in one bit.

    hermes-busdriver-lock publishes exactly that as its proof it stripped the release token, and
    blanket-redacting every key that merely says "token" would replace the proof with a string.
    """
    out = sanitizer()({"token_redacted": True, "has_secret": False, "token": None, "value_length": 12})

    assert out["token_redacted"] is True
    assert out["has_secret"] is False
    assert out["token"] is None
    assert out["value_length"] == 12


def test_sanitizer_keeps_required_typed_and_decision_fields_useful():
    """The envelope's own contract fields must survive the funnel intact and typed."""
    envelope = {
        "schema": "hermes-busdriver-delivery-status/v0",
        "read_only": True,
        "ok": False,
        "relay_capabilities": {"gate": {"path": "/x/scripts/hermes-busdriver-gate", "available": True}},
        "decision": {"status": "blocked", "blockers": ["repo_not_available"], "merge_allowed": False},
        "pr_grind": {"result": {"pr": 7, "clean": True, "status": "clean"}},
    }

    out = sanitizer()(envelope)

    assert out == envelope, "the funnel rewrote a field the envelope's readers depend on"


def test_sanitizer_redacts_our_own_credential_env_values_under_unknown_keys(monkeypatch):
    """An opaque env credential matches no shape pattern, but we know our own value."""
    monkeypatch.setenv("GH_TOKEN", "an-opaque-enterprise-credential-value")

    out = sanitizer()({"unknown": {"nested": ["remote: rejected using an-opaque-enterprise-credential-value"]}})

    assert "an-opaque-enterprise-credential-value" not in json.dumps(out)


@pytest.mark.parametrize("sentinel", [OPAQUE_CAPABILITY, SHAPED_CAPABILITY])
def test_valid_pr_grind_result_never_carries_nested_capabilities_into_stdout(tmp_path: Path, sentinel: str):
    """r32 High 1, exactly: a fully-bound result with one extra nested `token` was printed raw."""
    repo = bind_github_origin(init_repo(tmp_path / "repo"))
    plugin = fake_busdriver(tmp_path / "busdriver")
    payload = pr_grind_payload(pr=7, status="clean", **hostile_capabilities(sentinel))
    result_file = tmp_path / "pr-grind.json"
    result_file.write_text(json.dumps(payload))

    cp = run([
        sys.executable, str(STATUS_HARNESS), "--repo", str(repo), "--plugin-root", str(plugin),
        "--no-lock-status", "--no-agent-runs", "--pr", "7", "--pr-grind-result-file", str(result_file),
    ])
    data = json.loads(cp.stdout)

    assert sentinel not in cp.stdout
    result = data["pr_grind"]["result"]
    assert result["schema"] == "hermes-busdriver-pr-grind-check/v0"
    assert result["pr"] == 7
    assert result["clean"] is True
    assert result["decision"]["merge_allowed"] is False
    assert_no_delivery_authority(data["decision"])


def test_invalid_pr_grind_result_never_carries_nested_capabilities_into_stdout(tmp_path: Path):
    """A REJECTED result is the one most likely to be hostile, and it is echoed as a diagnostic."""
    repo = bind_github_origin(init_repo(tmp_path / "repo"))
    plugin = fake_busdriver(tmp_path / "busdriver")
    payload = pr_grind_payload(pr=7, status="clean", schema="wrong", **hostile_capabilities(OPAQUE_CAPABILITY))
    result_file = tmp_path / "pr-grind-invalid.json"
    result_file.write_text(json.dumps(payload))

    cp = run([
        sys.executable, str(STATUS_HARNESS), "--repo", str(repo), "--plugin-root", str(plugin),
        "--no-lock-status", "--no-agent-runs", "--pr", "7", "--pr-grind-result-file", str(result_file),
    ])
    data = json.loads(cp.stdout)

    assert OPAQUE_CAPABILITY not in cp.stdout
    assert data["pr_grind"]["reason"] == "pr_grind_result_invalid"
    assert "pr_grind_result_invalid" in data["decision"]["blockers"]


def test_litmus_status_never_carries_nested_capabilities_into_stdout(tmp_path: Path):
    """The allowlist bounds WHICH keys survive; it says nothing about what they nest."""
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    (repo / "src.txt").write_text("draft\n")
    litmus = litmus_status_fixture(tmp_path / "litmus.json", repo=repo)
    payload = json.loads(litmus.read_text())
    payload["markers"]["litmus_passed"]["value_sha256"] = {"token": OPAQUE_CAPABILITY}
    payload["repo"]["branch_diff_hash"] = {"nested": {"credential": OPAQUE_CAPABILITY}}
    payload["decision"]["status"] = "stale_or_missing"
    payload.update(hostile_capabilities(OPAQUE_CAPABILITY))
    litmus.write_text(json.dumps(payload))

    data = invoke(repo, plugin, "--litmus-status-result-file", str(litmus))

    assert OPAQUE_CAPABILITY not in json.dumps(data)
    summary = data["litmus_status"]["summary"]
    assert summary["decision"]["status"] == "stale_or_missing"
    assert summary["read_only"] is True
    assert_no_delivery_authority(data["decision"])


def test_relay_role_result_never_carries_nested_capabilities_into_stdout(tmp_path: Path):
    """`redact_value(result)` retained the WHOLE caller-authored object; only shapes were caught."""
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    payload = relay_role_payload(**hostile_capabilities(OPAQUE_CAPABILITY))
    double = relay_role_double(tmp_path / "relay-role-double", json.dumps(payload))

    data = invoke(
        repo, plugin,
        "--relay-role", "relay.pr.backstop", "--relay-role-script", str(double),
    )

    assert OPAQUE_CAPABILITY not in json.dumps(data)
    resolution = data["relay_role_resolution"]
    assert resolution["ok"] is True
    assert resolution["result"]["dispatch_allowed"] is True
    assert resolution["result"]["finalization_allowed"] is False
    assert_no_delivery_authority(data["decision"])


def test_relay_role_non_object_result_never_carries_capabilities_into_stdout(tmp_path: Path):
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    double = relay_role_double(tmp_path / "relay-role-list", json.dumps([{"token": OPAQUE_CAPABILITY}]))

    data = invoke(repo, plugin, "--relay-role", "relay.pr.backstop", "--relay-role-script", str(double))

    assert OPAQUE_CAPABILITY not in json.dumps(data)
    assert data["relay_role_resolution"]["reason"] == "relay_role_result_not_object"


def namespace(**overrides: Any) -> argparse.Namespace:
    defaults = dict(
        no_lock_status=False, no_agent_runs=True, state_dir=None, repo=".", drift_baseline=None,
        busdriver_state_dir_name=None, phase0_status_timeout=60, max_agent_runs=3,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def child_stdout(payload: object):
    """Stand in for one child process, so the ingestion boundary is what is under test."""
    def fake_run(cmd, cwd=None, timeout=60, env=None, text=True):
        return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
    return fake_run


def test_lock_status_child_object_is_sanitized_at_ingestion(monkeypatch):
    """delivery-status republishes lock payloads verbatim; it must not trust the lock to strip."""
    mod = __import__("runpy").run_path(str(STATUS))
    locks = [{"repo": {"root": "/x"}, "operation": "finalization", "stale": False, **hostile_capabilities(OPAQUE_CAPABILITY)}]
    monkeypatch.setitem(mod["load_lock_status"].__globals__, "run", child_stdout({"ok": True, "locks": locks}))

    out = mod["load_lock_status"](namespace())

    assert OPAQUE_CAPABILITY not in json.dumps(out)
    assert out["locks"][0]["repo"]["root"] == "/x", "the lock's repo binding must survive to be matched"
    assert out["locks"][0]["stale"] is False


def test_phase0_status_child_object_is_sanitized_at_ingestion(monkeypatch):
    """The whole hermes-busdriver-status envelope is embedded; r32 item 7 shows what it can carry."""
    mod = __import__("runpy").run_path(str(STATUS))
    payload = {
        "status_schema": "hermes-busdriver-status/v0",
        "busdriver_drift": {"finalization_compatible": True},
        "markers": {"preview_lines": [f"token={OPAQUE_CAPABILITY}", OPAQUE_CAPABILITY]},
        **hostile_capabilities(OPAQUE_CAPABILITY),
    }
    monkeypatch.setitem(mod["run_phase0_status"].__globals__, "run", child_stdout(payload))

    out = mod["run_phase0_status"](namespace(drift_baseline="/x/baseline.json"), {"ok": False}, {"ok": False})

    assert OPAQUE_CAPABILITY not in json.dumps(out)
    assert out["status_schema"] == "hermes-busdriver-status/v0"
    assert out["busdriver_drift"]["finalization_compatible"] is True


def test_agent_run_reports_are_sanitized_before_they_reach_the_envelope(tmp_path: Path):
    """`decision` is copied wholesale out of a report under a state dir this probe does not own."""
    repo = init_repo(tmp_path / "repo")
    plugin = fake_busdriver(tmp_path / "busdriver")
    run_dir = tmp_path / "state" / "agent-runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "final-report.json").write_text(json.dumps({
        "schema": "hermes-busdriver-agent-draft/v0",
        "status": "needs_busdriver_review",
        "ok": True,
        "agent": "opencode",
        "run_dir": str(run_dir),
        "repo": str(repo.resolve()),
        "decision": {"finalization_allowed": False, **hostile_capabilities(OPAQUE_CAPABILITY)},
    }))

    cp = run([
        sys.executable, str(STATUS), "--repo", str(repo), "--plugin-root", str(plugin),
        "--no-lock-status", "--state-dir", str(tmp_path / "state"),
    ])
    data = json.loads(cp.stdout)

    assert OPAQUE_CAPABILITY not in cp.stdout
    entry = data["recent_agent_runs"][0]
    assert entry["valid"] is True
    assert entry["status"] == "needs_busdriver_review"
    assert entry["decision"]["finalization_allowed"] is False
