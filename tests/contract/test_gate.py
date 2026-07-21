import hashlib
import json
import os
import runpy
import stat
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tests" / "fixtures" / "verifier" / "hermes-busdriver-gate-test-harness"
PRODUCTION_GATE = ROOT / "scripts" / "hermes-busdriver-gate"


@pytest.fixture(autouse=True)
def private_home(tmp_path_factory, monkeypatch):
    """Point the default baseline parent (~/.hermes/...) at a private per-test home.

    The gate now requires that parent to be 0700 and ours, so tests must not inherit whatever mode
    the developer's real ~/.hermes/busdriver-relay/gates happens to carry — nor keep writing
    baselines into it.
    """
    home = tmp_path_factory.mktemp("home")
    home.chmod(0o700)
    monkeypatch.setenv("HOME", str(home))
    return home


def run(*args: str, cwd: Path | None = None, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    if env is None:
        env = os.environ.copy()
        env["HERMES_GATE_BASELINE_HMAC_KEY"] = "contract-test-hmac-key"
    cp = subprocess.run([sys.executable, str(GATE), *args], cwd=cwd, text=True, capture_output=True, env=env)
    if check and cp.returncode != 0:
        raise AssertionError(f"gate failed rc={cp.returncode}\nSTDOUT={cp.stdout}\nSTDERR={cp.stderr}")
    return cp


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    (path / "src").mkdir()
    (path / "src" / "app.txt").write_text("hello\n")
    (path / ".gitignore").write_text(".env\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def fake_busdriver(path: Path) -> Path:
    root = path / "busdriver"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [], "PostToolUse": [], "Stop": []}}))
    (root / "package.json").write_text(json.dumps({"version": "test"}))
    return root


def test_preflight_passes_for_clean_repo_and_writes_baseline(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    baseline = tmp_path / "baseline.json"

    cp = run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline), "--scope-include", "src/**")
    data = json.loads(cp.stdout)

    assert data["ok"] is True
    assert Path(data["baseline_file"]).exists()
    assert data["decision"]["agent_implementation_draft_allowed"] is True
    for key in (
        "finalization_allowed", "commit_allowed", "push_allowed", "pr_allowed",
        "merge_allowed", "deploy_allowed", "release_allowed", "publish_allowed", "marker_write_allowed",
    ):
        assert data["decision"][key] is False


def test_preflight_blocks_dirty_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    (repo / "src" / "app.txt").write_text("dirty\n")

    cp = run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    assert data["ok"] is False
    repo_clean = next(c for c in data["checks"] if c["name"] == "repo_clean")
    assert repo_clean["ok"] is False


def test_postflight_scope_pass_and_verifier_pass(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    baseline = tmp_path / "baseline.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline), "--scope-include", "src/**")

    (repo / "src" / "app.txt").write_text("changed\n")
    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), "--verifier", "check=test -f src/app.txt")
    data = json.loads(cp.stdout)

    assert data["ok"] is True
    assert data["changed_files"] == ["src/app.txt"]
    assert data["decision"]["agent_implementation_draft_allowed"] is True
    assert data["decision"]["commit_allowed"] is False


def test_production_preflight_blocks_agent_dispatch_even_when_state_checks_pass(tmp_path: Path):
    repo = tmp_path / "repo-production-agent-policy"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-production-agent-policy")
    baseline = tmp_path / "baseline-production-agent-policy.json"
    env = os.environ.copy()
    env["HERMES_GATE_BASELINE_HMAC_KEY"] = "test-auth-key"

    cp = subprocess.run(
        [
            sys.executable, str(PRODUCTION_GATE), "preflight",
            "--plugin-root", str(plugin),
            "--repo", str(repo),
            "--baseline-file", str(baseline),
        ],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode == 2
    data = json.loads(cp.stdout)
    assert data["ok"] is False
    assert data["decision"]["agent_implementation_draft_allowed"] is False
    assert data["decision"]["status"] == "blocked"
    assert data["decision"]["reason"] == "agent_containment_and_credential_broker_unavailable"


def test_postflight_blocks_out_of_scope_change(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    baseline = tmp_path / "baseline.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline), "--scope-include", "src/**")

    (repo / "README.md").write_text("oops\n")
    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    assert data["ok"] is False
    scope = next(c for c in data["checks"] if c["name"] == "changed_files_within_scope")
    assert scope["ok"] is False
    assert "README.md" in scope["detail"]["out_of_scope"]


def test_postflight_single_star_does_not_cross_path_segment(tmp_path: Path):
    repo = tmp_path / "repo-single-star"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-single-star")
    baseline = tmp_path / "baseline-single-star.json"
    run(
        "preflight", "--plugin-root", str(plugin), "--repo", str(repo),
        "--baseline-file", str(baseline), "--scope-include", "src/*.txt",
    )
    nested = repo / "src" / "nested" / "blocked.txt"
    nested.parent.mkdir()
    nested.write_text("outside one segment\n")

    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    scope = next(c for c in data["checks"] if c["name"] == "changed_files_within_scope")
    assert scope["detail"]["out_of_scope"] == ["src/nested/blocked.txt"]


def test_postflight_double_star_may_cross_path_segment(tmp_path: Path):
    repo = tmp_path / "repo-double-star"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-double-star")
    baseline = tmp_path / "baseline-double-star.json"
    run(
        "preflight", "--plugin-root", str(plugin), "--repo", str(repo),
        "--baseline-file", str(baseline), "--scope-include", "src/**/*.txt",
    )
    nested = repo / "src" / "nested" / "allowed.txt"
    nested.parent.mkdir()
    nested.write_text("inside recursive scope\n")

    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline))
    data = json.loads(cp.stdout)

    assert data["ok"] is True
    assert data["changed_files"] == ["src/nested/allowed.txt"]


def test_postflight_blocks_git_hook_tamper(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    baseline = tmp_path / "baseline.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline))

    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho bad\n")
    hook.chmod(0o755)
    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    hooks = next(c for c in data["checks"] if c["name"] == "git_hooks_untampered")
    assert hooks["ok"] is False
    assert ".git/hooks/pre-commit" in hooks["detail"]["added"]


def test_postflight_blocks_new_or_changed_authority_marker(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    marker_dir = repo / ".claude"
    marker_dir.mkdir()
    marker = marker_dir / "litmus-passed.local"
    marker.write_text("before\n")
    baseline = tmp_path / "baseline.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline), "--allow-dirty")

    marker.write_text("forged-after-preflight\n")
    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    marker_check = next(c for c in data["checks"] if c["name"] == "authority_markers_untampered")
    assert marker_check["ok"] is False
    assert ".claude/litmus-passed.local" in marker_check["detail"]["changed"]


@pytest.mark.parametrize(
    ("mutation", "bucket"),
    [("added", "added"), ("removed", "removed"), ("symlink", "changed"), ("fifo", "changed")],
)
def test_postflight_blocks_authority_marker_type_and_presence_tamper(tmp_path: Path, mutation: str, bucket: str):
    repo = tmp_path / "repo-marker-types"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-marker-types")
    marker_dir = repo / ".claude"
    marker_dir.mkdir()
    marker = marker_dir / "litmus-passed.local"
    if mutation != "added":
        marker.write_text("before\n")
    baseline = tmp_path / f"baseline-{mutation}.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline), "--allow-dirty")

    if mutation == "added":
        marker.write_text("forged\n")
    elif mutation == "removed":
        marker.unlink()
    elif mutation == "symlink":
        marker.unlink()
        marker.symlink_to(repo / "src" / "app.txt")
    else:
        marker.unlink()
        os.mkfifo(marker)
    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    marker_check = next(c for c in data["checks"] if c["name"] == "authority_markers_untampered")
    assert marker_check["ok"] is False
    assert ".claude/litmus-passed.local" in marker_check["detail"][bucket]


def test_fingerprint_refuses_a_regular_file_swapped_to_a_symlink_after_lstat(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_GATE))
    fingerprint = ns["path_fingerprint"]
    runtime_os = fingerprint.__globals__["os"]
    target = tmp_path / "tracked.txt"
    outside = tmp_path / "outside-secret.txt"
    target.write_text("tracked\n")
    outside.write_text("SECRET-OUTSIDE\n")
    outside_hash = hashlib.sha256(outside.read_bytes()).hexdigest()
    real_lstat = runtime_os.lstat
    swapped = []

    def lstat_then_swap(path, *args, **kwargs):
        st = real_lstat(path, *args, **kwargs)
        if Path(path) == target and not swapped:
            swapped.append(True)
            target.unlink()
            target.symlink_to(outside)
        return st

    monkeypatch.setattr(runtime_os, "lstat", lstat_then_swap)

    result = fingerprint(target)

    assert swapped
    assert result["kind"] == "lookup_error"
    assert outside_hash not in json.dumps(result)


def test_fingerprint_refuses_a_regular_file_swapped_to_fifo_without_blocking(tmp_path: Path):
    target = tmp_path / "tracked.txt"
    target.write_text("tracked\n")
    code = f"""
import json, os, runpy
from pathlib import Path
ns = runpy.run_path({str(PRODUCTION_GATE)!r})
fingerprint = ns['path_fingerprint']
runtime_os = fingerprint.__globals__['os']
target = Path({str(target)!r})
real_lstat = runtime_os.lstat
swapped = []
def lstat_then_swap(path, *args, **kwargs):
    st = real_lstat(path, *args, **kwargs)
    if Path(path) == target and not swapped:
        swapped.append(True)
        target.unlink()
        os.mkfifo(target)
    return st
runtime_os.lstat = lstat_then_swap
print(json.dumps(fingerprint(target)))
"""

    cp = subprocess.run([sys.executable, "-c", code], text=True, capture_output=True, timeout=3, check=True)

    assert json.loads(cp.stdout)["kind"] == "lookup_error"


def test_fingerprint_revalidates_the_name_after_hash(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_GATE))
    fingerprint = ns["path_fingerprint"]
    runtime_os = fingerprint.__globals__["os"]
    target = tmp_path / "tracked.txt"
    target.write_text("tracked\n")
    real_read = runtime_os.read
    swapped = []

    def read_then_replace(fd, count):
        data = real_read(fd, count)
        if data and not swapped:
            swapped.append(True)
            target.rename(tmp_path / "old-tracked.txt")
            target.write_text("replacement\n")
        return data

    monkeypatch.setattr(runtime_os, "read", read_then_replace)

    result = fingerprint(target)

    assert swapped
    assert result["kind"] == "lookup_error"


@pytest.mark.parametrize("marker_name", ["pr-codex-lead.local.json", "pr-backstop-verdict.local.json", "pr-grind-clean.local"])
def test_postflight_blocks_all_finalization_authority_markers(tmp_path: Path, marker_name: str):
    repo = tmp_path / "repo-finalization-markers"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-finalization-markers")
    baseline = tmp_path / f"baseline-{marker_name}.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline))
    marker_dir = repo / ".claude"
    marker_dir.mkdir(exist_ok=True)
    (marker_dir / marker_name).write_text("forged\n")
    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)
    data = json.loads(cp.stdout)
    assert cp.returncode == 2
    marker_check = next(c for c in data["checks"] if c["name"] == "authority_markers_untampered")
    assert f".claude/{marker_name}" in marker_check["detail"]["added"]


def test_preflight_requires_parent_hmac_key(tmp_path: Path, private_home: Path):
    repo = tmp_path / "repo-missing-hmac"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-missing-hmac")
    # HOME is kept: an empty env would send the default baseline path at the real home, whose
    # parent mode is not this test's subject.
    cp = run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), check=False,
             env={"HOME": str(private_home), "PATH": os.environ.get("PATH", "")})
    data = json.loads(cp.stdout)
    assert cp.returncode == 2
    key_check = next(c for c in data["checks"] if c["name"] == "baseline_hmac_key_present")
    assert key_check["ok"] is False


def test_linked_worktree_preflight_detects_common_git_hooks(tmp_path: Path):
    primary = tmp_path / "primary"
    primary.mkdir()
    init_repo(primary)
    linked = tmp_path / "linked"
    assert subprocess.run(["git", "-C", str(primary), "worktree", "add", "-q", "-b", "linked-test", str(linked)], text=True, capture_output=True).returncode == 0
    plugin = fake_busdriver(tmp_path / "plugin-linked")
    hook = primary / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o700)
    cp = run("preflight", "--plugin-root", str(plugin), "--repo", str(linked), check=False)
    data = json.loads(cp.stdout)
    assert cp.returncode == 2
    hooks = next(c for c in data["checks"] if c["name"] == "git_hooks_safe")
    assert hooks["ok"] is False


def test_postflight_rejects_forged_marker_baseline_without_parent_hmac_key(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    marker_dir = repo / ".claude"
    marker_dir.mkdir()
    marker = marker_dir / "litmus-passed.local"
    marker.write_text("before\n")
    baseline = tmp_path / "baseline.json"
    gate_env = os.environ.copy()
    gate_env["HERMES_GATE_BASELINE_HMAC_KEY"] = "parent-only-test-key"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline), "--allow-dirty", env=gate_env)

    marker.write_text("forged\n")
    forged = json.loads(baseline.read_text())
    forged["markers"] = {}
    baseline.write_text(json.dumps(forged))
    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False, env=gate_env)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    integrity = next(c for c in data["checks"] if c["name"] == "baseline_integrity_authenticated")
    assert integrity["ok"] is False


def test_postflight_verifier_cannot_read_parent_hmac_key_or_startup_injection(tmp_path: Path):
    repo = tmp_path / "repo-verifier-env"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-verifier-env")
    baseline = tmp_path / "baseline-verifier-env.json"
    gate_env = os.environ.copy()
    gate_env["HERMES_GATE_BASELINE_HMAC_KEY"] = "parent-only-test-key"
    gate_env["BASH_ENV"] = str(tmp_path / "attacker-bash-env")
    (tmp_path / "attacker-bash-env").write_text("export STARTUP_INJECTION_RAN=1\n")
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline), env=gate_env)

    cp = run(
        "postflight",
        "--repo", str(repo),
        "--baseline-file", str(baseline),
        "--verifier", "env=test -z \"$HERMES_GATE_BASELINE_HMAC_KEY\" && test -z \"$STARTUP_INJECTION_RAN\"",
        check=False,
        env=gate_env,
    )
    data = json.loads(cp.stdout)

    assert cp.returncode == 0
    verifier = next(c for c in data["checks"] if c["name"] == "verifiers_pass")
    assert verifier["ok"] is True


def test_production_postflight_blocks_verifier_before_sentinel_launch(tmp_path: Path):
    repo = tmp_path / "repo-verifier-policy"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-verifier-policy")
    baseline = tmp_path / "baseline-verifier-policy.json"
    sentinel = tmp_path / "verifier-ran"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline))

    cp = subprocess.run(
        [
            sys.executable, str(PRODUCTION_GATE), "postflight", "--repo", str(repo),
            "--baseline-file", str(baseline), "--verifier", f"sentinel=touch {sentinel}",
        ],
        text=True, capture_output=True, check=False,
        env={**os.environ, "HERMES_GATE_BASELINE_HMAC_KEY": "contract-test-hmac-key"},
    )
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["decision"]["agent_implementation_draft_allowed"] is False
    assert data["decision"]["reason"] == "verifier_containment_unavailable"
    assert data["verifiers"] == []
    assert not sentinel.exists()


def test_postflight_blocks_new_ignored_file(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    baseline = tmp_path / "baseline.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline))

    (repo / ".env").write_text("SECRET=bad\n")
    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    ignored = next(c for c in data["checks"] if c["name"] == "no_new_or_changed_ignored_files")
    assert ignored["ok"] is False
    assert ".env" in ignored["detail"]["added"]


def test_postflight_returns_fresh_snapshot_after_verifier_adds_out_of_scope_file(tmp_path: Path):
    repo = tmp_path / "repo-verifier-scope"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-verifier-scope")
    baseline = tmp_path / "baseline-verifier-scope.json"
    run(
        "preflight", "--plugin-root", str(plugin), "--repo", str(repo),
        "--baseline-file", str(baseline), "--scope-include", "src/**",
    )

    cp = run(
        "postflight", "--repo", str(repo), "--baseline-file", str(baseline),
        "--verifier", "mutate=printf bad > README.md", check=False,
    )
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["changed_files"] == ["README.md"]
    scope = next(c for c in data["checks"] if c["name"] == "changed_files_within_scope")
    assert scope["ok"] is False


@pytest.mark.parametrize(
    ("name", "command", "drift_key"),
    [
        ("tracked", "printf changed > src/app.txt", "tracked_files"),
        ("mode", "git config core.fileMode false && chmod 755 src/app.txt", "tracked_files"),
        ("hook", "printf '#!/bin/sh\\n' > .git/hooks/pre-commit", "hooks"),
        ("marker", "mkdir -p .claude && printf forged > .claude/litmus-passed.local", "markers"),
        ("ignored", "printf secret > .env", "ignored"),
        (
            "head",
            "printf committed > src/app.txt && git add src/app.txt && "
            "git -c user.name=Verifier -c user.email=verifier@example.com -c commit.gpgsign=false commit -m verifier",
            "repo",
        ),
        ("branch", "git switch -q -c verifier-branch", "repo"),
    ],
)
def test_postflight_blocks_each_verifier_repository_mutation(
    tmp_path: Path, name: str, command: str, drift_key: str
):
    repo = tmp_path / f"repo-verifier-{name}"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / f"plugin-verifier-{name}")
    baseline = tmp_path / f"baseline-verifier-{name}.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline))

    cp = run(
        "postflight", "--repo", str(repo), "--baseline-file", str(baseline),
        "--verifier", f"mutate={command}", check=False,
    )
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    assert data["ok"] is False
    drift = next(c for c in data["checks"] if c["name"] == "verifiers_preserve_repository_snapshot")
    assert drift["ok"] is False
    assert drift_key in drift["detail"]
    assert data["snapshot"]
    if name == "tracked":
        assert data["changed_files"] == ["src/app.txt"]
        assert data["snapshot"]["tracked_files"]["src/app.txt"]["sha256"] != json.loads(baseline.read_text())["snapshot"]["tracked_files"]["src/app.txt"]["sha256"]
    elif name == "mode":
        before = json.loads(baseline.read_text())["snapshot"]["tracked_files"]["src/app.txt"]
        after = data["snapshot"]["tracked_files"]["src/app.txt"]
        assert data["changed_files"] == ["src/app.txt"]
        assert before["sha256"] == after["sha256"]
        assert before["mode"] != after["mode"]
    elif name == "hook":
        assert any(path.endswith(".git/hooks/pre-commit") for path in data["snapshot"]["hooks"])
    elif name == "marker":
        assert ".claude/litmus-passed.local" in data["snapshot"]["markers"]
    elif name == "ignored":
        assert ".env" in data["snapshot"]["ignored"]["files"]
    elif name == "head":
        assert data["repo"]["head"] != json.loads(baseline.read_text())["snapshot"]["repo"]["head"]
    elif name == "branch":
        assert data["repo"]["head_identity"] == "refs/heads/verifier-branch"


def test_postflight_clean_verifier_preserves_snapshot_and_passes(tmp_path: Path):
    repo = tmp_path / "repo-clean-verifier"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-clean-verifier")
    baseline = tmp_path / "baseline-clean-verifier.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline))

    cp = run(
        "postflight", "--repo", str(repo), "--baseline-file", str(baseline),
        "--verifier", "clean=test -f src/app.txt",
    )
    data = json.loads(cp.stdout)

    assert data["ok"] is True
    assert data["changed_files"] == []
    drift = next(c for c in data["checks"] if c["name"] == "verifiers_preserve_repository_snapshot")
    assert drift["ok"] is True


def test_preflight_fails_closed_when_head_identity_and_oid_lookup_fail(tmp_path: Path):
    repo = tmp_path / "repo-unborn"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    plugin = fake_busdriver(tmp_path / "plugin-unborn")

    cp = run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    snapshot = next(c for c in data["checks"] if c["name"] == "repository_snapshot_complete")
    assert snapshot["ok"] is False
    assert "head_oid_lookup_failed" in snapshot["detail"]


def test_postflight_blocks_same_oid_branch_switch_before_verifier(tmp_path: Path):
    repo = tmp_path / "repo-same-oid-branch"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-same-oid-branch")
    baseline = tmp_path / "baseline-same-oid-branch.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline))
    subprocess.run(["git", "switch", "-q", "-c", "same-oid"], cwd=repo, check=True)

    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    assert data["repo"]["head"] == json.loads(baseline.read_text())["snapshot"]["repo"]["head"]
    identity = next(c for c in data["checks"] if c["name"] == "same_head_identity_as_baseline")
    assert identity["ok"] is False
    assert identity["detail"]["current"] == "refs/heads/same-oid"


def linked_worktree(tmp_path: Path, name: str) -> tuple[Path, Path]:
    primary = tmp_path / f"primary-{name}"
    primary.mkdir()
    init_repo(primary)
    linked = tmp_path / f"linked-{name}"
    subprocess.run(
        ["git", "-C", str(primary), "worktree", "add", "-q", "-b", f"linked-{name}", str(linked)],
        check=True,
    )
    return primary, linked


def create_worktree_git_state(repo: Path, name: str) -> None:
    cp = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-path", name],
        text=True, capture_output=True, check=True,
    )
    path = Path(cp.stdout.strip())
    if not path.is_absolute():
        path = repo / path
    if name in {"rebase-merge", "rebase-apply", "sequencer"}:
        path.mkdir(parents=True)
        (path / "state").write_text("active\n")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("active\n")


@pytest.mark.parametrize(
    "state_name",
    [
        "MERGE_HEAD", "REBASE_HEAD", "rebase-merge", "rebase-apply",
        "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_START", "BISECT_LOG", "sequencer",
    ],
)
def test_linked_worktree_preflight_detects_operation_state(tmp_path: Path, state_name: str):
    _, linked = linked_worktree(tmp_path, f"pre-{state_name.lower()}")
    plugin = fake_busdriver(tmp_path / f"plugin-pre-{state_name.lower()}")
    create_worktree_git_state(linked, state_name)

    cp = run("preflight", "--plugin-root", str(plugin), "--repo", str(linked), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    state = next(c for c in data["checks"] if c["name"] == "no_merge_rebase_cherry_pick")
    assert state["ok"] is False
    assert state_name in state["detail"]


@pytest.mark.parametrize(
    "state_name",
    [
        "MERGE_HEAD", "REBASE_HEAD", "rebase-merge", "rebase-apply",
        "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_START", "BISECT_LOG", "sequencer",
    ],
)
def test_linked_worktree_postflight_detects_operation_state(tmp_path: Path, state_name: str):
    _, linked = linked_worktree(tmp_path, f"post-{state_name.lower()}")
    plugin = fake_busdriver(tmp_path / f"plugin-post-{state_name.lower()}")
    baseline = tmp_path / f"baseline-post-{state_name.lower()}.json"
    run("preflight", "--plugin-root", str(plugin), "--repo", str(linked), "--baseline-file", str(baseline))
    create_worktree_git_state(linked, state_name)

    cp = run("postflight", "--repo", str(linked), "--baseline-file", str(baseline), check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    state = next(c for c in data["checks"] if c["name"] == "no_merge_rebase_cherry_pick")
    assert state["ok"] is False
    assert state_name in state["detail"]


def test_ignored_snapshot_overflow_blocks_preflight_and_postflight_at_boundary(tmp_path: Path):
    repo = tmp_path / "repo-ignored-overflow"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-ignored-overflow")
    baseline = tmp_path / "baseline-ignored-overflow.json"
    (repo / ".git" / "info" / "exclude").write_text("ignored-*.txt\n")
    for index in range(501):
        (repo / f"ignored-{index:03}.txt").write_text(f"before-{index}\n")

    pre = run(
        "preflight", "--plugin-root", str(plugin), "--repo", str(repo),
        "--baseline-file", str(baseline), check=False,
    )
    pre_data = json.loads(pre.stdout)
    assert pre.returncode == 2
    pre_limit = next(c for c in pre_data["checks"] if c["name"] == "ignored_files_within_snapshot_limit")
    assert pre_limit["ok"] is False
    assert json.loads(baseline.read_text())["snapshot"]["ignored"]["overflow"] is True

    (repo / "ignored-500.txt").write_text("mutated-at-boundary\n")
    post = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)
    post_data = json.loads(post.stdout)
    assert post.returncode == 2
    post_limit = next(c for c in post_data["checks"] if c["name"] == "ignored_files_within_snapshot_limit")
    assert post_limit["ok"] is False
    assert post_limit["detail"]["post_verifier"] is True


def test_ignored_snapshot_overflow_counts_broken_symlinks_fail_closed(tmp_path: Path):
    repo = tmp_path / "repo-ignored-symlink-overflow"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-ignored-symlink-overflow")
    baseline = tmp_path / "baseline-ignored-symlink-overflow.json"
    (repo / ".git" / "info" / "exclude").write_text("ignored-link-*\n")
    for index in range(501):
        (repo / f"ignored-link-{index:03}").symlink_to("missing-target")

    pre = run(
        "preflight", "--plugin-root", str(plugin), "--repo", str(repo),
        "--baseline-file", str(baseline), check=False,
    )
    data = json.loads(pre.stdout)

    assert pre.returncode == 2
    limit = next(c for c in data["checks"] if c["name"] == "ignored_files_within_snapshot_limit")
    assert limit["ok"] is False
    ignored = json.loads(baseline.read_text())["snapshot"]["ignored"]
    assert ignored["overflow"] is True
    assert len(ignored["files"]) == 500
    assert all(value["kind"] == "symlink" for value in ignored["files"].values())


def baseline_error(cp: subprocess.CompletedProcess[str]) -> dict:
    """The fail-closed baseline envelopes exit via SystemExit(json), so they land on stderr."""
    assert cp.returncode == 1, f"expected fail-closed exit\nSTDOUT={cp.stdout}\nSTDERR={cp.stderr}"
    return json.loads(cp.stderr)


def preflight_ok(tmp_path: Path, name: str, baseline: Path) -> Path:
    repo = tmp_path / f"repo-{name}"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / f"plugin-{name}")
    run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline))
    return repo


def test_preflight_rejects_group_or_other_accessible_baseline_parent(tmp_path: Path):
    repo = tmp_path / "repo-shared-parent"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-shared-parent")
    shared = tmp_path / "shared-gates"
    shared.mkdir(mode=0o755)

    cp = run("preflight", "--plugin-root", str(plugin), "--repo", str(repo),
             "--baseline-file", str(shared / "baseline.json"), check=False)

    assert baseline_error(cp)["error"] == "baseline_directory_invalid"
    assert not (shared / "baseline.json").exists()


def test_preflight_rejects_symlink_component_in_baseline_parent_chain(tmp_path: Path):
    repo = tmp_path / "repo-symlink-parent"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-symlink-parent")
    # The symlink sits ABOVE the parent: an is_symlink() check on path.parent alone never sees it,
    # which is the redirect the descriptor walk has to catch.
    real = tmp_path / "real-mid"
    (real / "gates").mkdir(mode=0o700, parents=True)
    link = tmp_path / "link-mid"
    link.symlink_to(real, target_is_directory=True)

    cp = run("preflight", "--plugin-root", str(plugin), "--repo", str(repo),
             "--baseline-file", str(link / "gates" / "baseline.json"), check=False)

    assert baseline_error(cp)["error"] == "baseline_directory_invalid"
    assert not (real / "gates" / "baseline.json").exists()


def test_preflight_creates_missing_baseline_parent_private(tmp_path: Path):
    repo = tmp_path / "repo-created-parent"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path / "plugin-created-parent")
    baseline = tmp_path / "created" / "gates" / "baseline.json"

    cp = run("preflight", "--plugin-root", str(plugin), "--repo", str(repo), "--baseline-file", str(baseline))

    assert json.loads(cp.stdout)["ok"] is True
    assert stat.S_IMODE(baseline.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(baseline.stat().st_mode) == 0o600


def test_postflight_rejects_baseline_replaced_by_symlink_to_authenticated_bytes(tmp_path: Path):
    baseline = tmp_path / "baseline-symlink-swap.json"
    repo = preflight_ok(tmp_path, "symlink-swap", baseline)
    # The decoy holds the SAME bytes preflight wrote, so its HMAC authenticates: only the
    # no-follow open can tell the anchor apart from a symlink pointing at valid content.
    decoy = tmp_path / "decoy-baseline.json"
    decoy.write_bytes(baseline.read_bytes())
    decoy.chmod(0o600)
    baseline.unlink()
    baseline.symlink_to(decoy)

    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)

    assert baseline_error(cp)["error"] == "baseline_path_is_symlink"


def test_postflight_rejects_non_regular_baseline(tmp_path: Path):
    baseline = tmp_path / "baseline-fifo.json"
    repo = preflight_ok(tmp_path, "fifo", baseline)
    baseline.unlink()
    os.mkfifo(baseline, 0o600)

    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)

    assert baseline_error(cp)["error"] == "baseline_file_invalid"


def test_postflight_rejects_hardlinked_baseline(tmp_path: Path):
    baseline = tmp_path / "baseline-hardlink.json"
    repo = preflight_ok(tmp_path, "hardlink", baseline)
    os.link(baseline, tmp_path / "baseline-hardlink-alias.json")

    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)

    assert baseline_error(cp)["error"] == "baseline_file_invalid"


def test_postflight_rejects_over_permissive_baseline(tmp_path: Path):
    baseline = tmp_path / "baseline-permissive.json"
    repo = preflight_ok(tmp_path, "permissive", baseline)
    baseline.chmod(0o644)

    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)

    assert baseline_error(cp)["error"] == "baseline_file_invalid"


def test_postflight_rejects_wrong_owner_baseline(tmp_path: Path):
    """Owner drift is unforgeable without root, so drive the check through the module namespace."""
    baseline = tmp_path / "baseline-owner.json"
    preflight_ok(tmp_path, "owner", baseline)
    ns = runpy.run_path(str(PRODUCTION_GATE))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(os, "geteuid", lambda: os.getuid() + 1)
        with pytest.raises(SystemExit) as excinfo:
            ns["read_baseline_file"](baseline)
    # The parent is checked before the file, so foreign ownership stops at the directory.
    assert json.loads(str(excinfo.value))["error"] == "baseline_directory_invalid"


# --- v16-r30 A: the CLOSING fstat must reassert every property, not just inode identity ---


class _MutatingOs:
    """Proxy the real `os`, firing `on_read` once at the first read of the baseline body.

    The window this closes is between the opening fstat and the closing one, so a wall-clock race
    would be the wrong instrument: the mutation is injected at the exact point a same-UID writer
    would land, and the test is then a deterministic assertion rather than a timing hope.
    """

    def __init__(self, real, on_read):
        self._real = real
        self._on_read = on_read
        self._fired = False

    def __getattr__(self, name):
        return getattr(self._real, name)

    def read(self, fd, length):
        if not self._fired:
            self._fired = True
            self._on_read()
        return self._real.read(fd, length)


def read_baseline_while(baseline: Path, mutate) -> dict:
    """Run the production read with `mutate` applied mid-read; return its fail-closed envelope."""
    ns = runpy.run_path(str(PRODUCTION_GATE))
    read_baseline_file = ns["read_baseline_file"]
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(read_baseline_file.__globals__, "os", _MutatingOs(os, mutate))
        with pytest.raises(SystemExit) as excinfo:
            read_baseline_file(baseline)
    return json.loads(str(excinfo.value))


def test_postflight_rejects_baseline_chmodded_after_the_read(tmp_path: Path):
    """Bytes read while private, world-readable by the time the descriptor closed."""
    baseline = tmp_path / "baseline-post-chmod.json"
    preflight_ok(tmp_path, "post-chmod", baseline)

    error = read_baseline_while(baseline, lambda: baseline.chmod(0o644))

    assert error["error"] == "baseline_file_invalid"


def test_postflight_rejects_baseline_appended_after_the_read(tmp_path: Path):
    """The opening fstat proved the size; only the closing one can prove it did not grow."""
    baseline = tmp_path / "baseline-post-append.json"
    preflight_ok(tmp_path, "post-append", baseline)

    def append() -> None:
        with open(baseline, "ab") as handle:
            handle.write(b"x" * 4096)

    error = read_baseline_while(baseline, append)

    assert error["error"] == "baseline_file_invalid"


def test_postflight_rejects_baseline_whose_mtime_moved_under_the_read(tmp_path: Path):
    """Same inode, same size, same mode — only the timestamps witness the rewrite."""
    baseline = tmp_path / "baseline-post-mtime.json"
    preflight_ok(tmp_path, "post-mtime", baseline)
    stamp = baseline.stat()

    error = read_baseline_while(
        baseline, lambda: os.utime(baseline, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))
    )

    assert error["error"] == "baseline_file_invalid"


def test_postflight_rejects_baseline_rewritten_with_its_mtime_restored(tmp_path: Path):
    """The strongest form: in-place rewrite, same length, mtime put back — only ctime_ns survives it.

    An attacker who can write the file can also restore its mtime, and the replacement bytes can be
    a real baseline from another repo, so they carry a real HMAC. dev/ino/nlink/uid/mode/size and
    mtime are all identical afterwards; ctime is the one field a same-UID writer cannot forge.
    """
    baseline = tmp_path / "baseline-post-ctime.json"
    preflight_ok(tmp_path, "post-ctime", baseline)
    stamp = baseline.stat()
    swapped = b"{" + b" " * (stamp.st_size - 2) + b"}"

    def rewrite_and_restore_mtime() -> None:
        with open(baseline, "r+b") as handle:
            handle.write(swapped)
        os.utime(baseline, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))

    error = read_baseline_while(baseline, rewrite_and_restore_mtime)

    assert error["error"] == "baseline_file_invalid"
    assert baseline.stat().st_size == stamp.st_size, "the rewrite must be size-preserving to be a ctime-only test"


def test_postflight_reads_an_untouched_baseline(tmp_path: Path):
    """The guard rejects drift, not reading: an unmolested baseline still comes back whole.

    This is what proves the added mtime_ns/ctime_ns comparison is safe — an ordinary read updates
    atime, never mtime or ctime, so the closing fstat matches the opening one.
    """
    baseline = tmp_path / "baseline-untouched.json"
    preflight_ok(tmp_path, "untouched", baseline)
    ns = runpy.run_path(str(PRODUCTION_GATE))

    assert ns["read_baseline_file"](baseline) == baseline.read_bytes()


def test_postflight_rejects_unparseable_baseline_without_leaking_contents(tmp_path: Path):
    baseline = tmp_path / "baseline-garbage.json"
    repo = preflight_ok(tmp_path, "garbage", baseline)
    baseline.write_text("not json: SECRETVALUE\n")
    baseline.chmod(0o600)

    cp = run("postflight", "--repo", str(repo), "--baseline-file", str(baseline), check=False)

    payload = baseline_error(cp)
    assert payload["error"] == "baseline_unreadable"
    assert "SECRETVALUE" not in cp.stderr + cp.stdout


def test_production_gate_git_dispatches_the_validated_root_owned_source(monkeypatch, tmp_path: Path):
    """v16-r34c: replaces test_production_gate_git_uses_authenticated_private_copy.

    The old test asserted that the git the gate runs is a private 0500 copy, distinct from the
    source. That design is gone, and the assertions here are its inverse rather than its absence.

    Why it inverted: the copy relocated the substitutable name instead of removing it. macOS has no
    fexecve and will not exec /dev/fd/N, so the kernel re-resolves a PATHNAME at exec time — and the
    copy lived somewhere this UID can write, which is exactly what r34's two-rename ABA walked
    through while every descriptor-visible field still checked out. `mode == 0o500` was never a
    boundary against a writer who owns the directory.

    So the properties below are the ones a private copy could not have had at all: the executable is
    the frozen table's path, root-owned, not group/world-writable, and SIP-restricted — which is
    what stands in for nlink==1 on the CommandLineTools shim, and is strictly stronger, since SIP
    denies even root. The one property carried over unchanged is the one that always mattered: what
    reaches argv[0] is what was validated.
    """
    ns = runpy.run_path(str(PRODUCTION_GATE))
    resolved = ns["trusted_git_path"]()
    assert resolved == ns["TRUSTED_EXECUTABLE_SOURCES"]["git"] == Path("/usr/bin/git")
    st = os.lstat(resolved)
    assert not stat.S_ISLNK(st.st_mode), "a symlinked name is a name someone else can re-point"
    assert st.st_uid == 0, "a git this UID owns is a git this UID can replace"
    assert not (st.st_mode & (stat.S_IWGRP | stat.S_IWOTH))
    assert st.st_flags & ns["SF_RESTRICTED"], "SIP replaces nlink==1 for the shim-backed source"
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return ns["BoundedOutput"](0, "", "", False, False)

    # r74: the validated sandbox launcher is argv[0], and the independently validated real Git is
    # its literal child argv. This binds the observation to deny-exec/deny-network policy.
    monkeypatch.setitem(ns["run"].__globals__, "run_bounded", fake_run)
    ns["git"](tmp_path, "status", "--porcelain=v1")
    assert Path(captured["cmd"][0]) == ns["TRUSTED_EXECUTABLE_SOURCES"]["sandbox-exec"]
    assert captured["cmd"][1:3] == ["-p", ns["GIT_OBSERVATION_SANDBOX_PROFILE"]]
    assert Path(captured["cmd"][3]) == ns["TRUSTED_EXECUTABLE_SOURCES"]["git-real"]
    assert "--ignore-submodules=none" in captured["cmd"]
    assert "--untracked-files=all" in captured["cmd"]
