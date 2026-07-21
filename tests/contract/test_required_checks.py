"""Contract tests for scripts/check-required-checks.sh surface (a).

Invokes the script as a subprocess (like the other contract tests) against a
tmp repo, asserting the job_name parser:
  - accepts a required name that IS the job's own direct `name:` field,
  - does NOT false-pass when only a nested step `with: name:` matches,
  - treats regex metacharacters in a required name literally.
Run with --local-only so surface (b) makes no GitHub API calls (hermetic).
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-required-checks.sh"
APPLE_REDIRECT_ENV = (
    "DEVELOPER_DIR", "SDKROOT", "XCODE_DEVELOPER_DIR_PATH", "TOOLCHAINS", "XCRUN_CACHE_PATH",
)


def _run(tmp_path: Path, lock: dict, workflows: dict[str, str], *, env=None):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "required-checks.lock").write_text(json.dumps(lock))
    for name, body in workflows.items():
        (tmp_path / ".github" / "workflows" / name).write_text(body)
    return subprocess.run(
        [str(SCRIPT), "--local-only"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )


def test_direct_job_name_matches_is_clean(tmp_path):
    wf = "jobs:\n  scan:\n    name: Code security\n    steps:\n      - run: true\n"
    r = _run(
        tmp_path,
        {"required": [{"name": "Code security", "source_app": "github-actions",
                       "workflow": ".github/workflows/security.yml", "job": "scan"}]},
        {"security.yml": wf},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "required-checks: clean" in r.stdout


def test_repository_required_checks_lock_matches_current_workflow_source():
    cp = subprocess.run(
        [str(SCRIPT), "--local-only"], cwd=ROOT,
        capture_output=True, text=True,
    )
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "required-checks: clean" in cp.stdout


def test_repository_required_checks_lock_pins_reporter_app_identity():
    lock = json.loads((ROOT / ".github" / "required-checks.lock").read_text())
    app_ids = {row.get("app_id") for row in lock["required"]}
    assert len(app_ids) == 1
    app_id = next(iter(app_ids))
    assert isinstance(app_id, int) and not isinstance(app_id, bool) and app_id > 0


def test_pull_request_workflow_has_only_portable_ci_and_no_self_hosted_execution():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text()
    assert "name: test" in workflow
    portable_job = workflow.split("  test:\n", 1)[1].split("\n  compliance:\n", 1)[0]
    assert "pytest tests/contract -q" not in portable_job
    assert "--ignore=tests/contract/" not in portable_job
    assert "tests/contract/test_stack_portable_smoke.py" in portable_job
    for introduced_later in (
        "tests/contract/test_required_checks_portable.py",
        "tests/contract/test_docs_inventory_closure.py",
        "tests/contract/test_finalization_unlock_contract_docs.py",
        "tests/contract/test_skill_references.py",
    ):
        assert introduced_later not in portable_job
    assert "python -B -I -m pytest -q -p no:cacheprovider" in portable_job
    assert "host-runtime-contract" not in workflow
    assert "self-hosted" not in workflow
    assert "busdriver-trusted-runtime" not in workflow
    assert "PYTHONDONTWRITEBYTECODE" not in workflow
    lock = json.loads((ROOT / ".github" / "required-checks.lock").read_text())
    assert any(row["name"] == "test" and row["job"] == "test" for row in lock["required"])
    assert not any(row["name"] == "Host runtime contract" for row in lock["required"])
    assert not any(row["name"] == "Host runtime contract" for row in lock["advisory"])


def test_nested_step_with_name_does_not_false_pass(tmp_path):
    # The job's OWN name is "scan"; the required check name "artifact-x" appears
    # only as a step's `with: name:` value. That must NOT satisfy surface (a).
    wf = (
        "jobs:\n"
        "  scan:\n"
        "    steps:\n"
        "      - uses: actions/upload-artifact@de0fac2e4500dabe0009e67214ff5f5447ce83dd\n"
        "        with:\n"
        "          name: artifact-x\n"
    )
    r = _run(
        tmp_path,
        {"required": [{"name": "artifact-x", "source_app": "github-actions",
                       "workflow": ".github/workflows/security.yml", "job": "scan"}]},
        {"security.yml": wf},
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "DRIFT (a)" in r.stdout


def test_entrypoint_and_local_validation_ignore_malicious_path(tmp_path):
    assert SCRIPT.read_text().startswith("#!/bin/bash -p\n")
    planted = tmp_path / "planted"
    planted.mkdir()
    for name in ("jq", "gh", "bash"):
        candidate = planted / name
        candidate.write_text("#!/bin/sh\necho MALICIOUS >&2\nexit 99\n")
        candidate.chmod(0o755)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "required-checks.lock").write_text(json.dumps({"required": []}))
    env = dict(os.environ, PATH=str(planted), GH_TOKEN="credential-must-not-reach-path")
    cp = subprocess.run([str(SCRIPT), "--local-only"], cwd=tmp_path, env=env,
                        capture_output=True, text=True)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "MALICIOUS" not in cp.stdout + cp.stderr


def test_executable_entrypoint_does_not_import_exported_awk_function(tmp_path):
    marker = tmp_path / "exported-awk-ran"
    workflow = "jobs:\n  scan:\n    name: WRONG NAME\n    steps:\n      - run: true\n"
    environment = dict(os.environ)
    environment["BASH_FUNC_awk%%"] = (
        "() { /usr/bin/printf '1\\nCode security\\n'; "
        f"/usr/bin/touch {shlex.quote(str(marker))}; }}"
    )
    cp = _run(
        tmp_path,
        {"required": [{"name": "Code security", "source_app": "github-actions",
                       "workflow": ".github/workflows/security.yml", "job": "scan"}]},
        {"security.yml": workflow},
        env=environment,
    )
    assert cp.returncode == 1, cp.stdout + cp.stderr
    assert "DRIFT (a)" in cp.stdout
    assert "required-checks: clean" not in cp.stdout
    assert not marker.exists(), "entrypoint imported and executed ambient Bash function"


def test_remote_validation_requires_an_explicit_complete_repo_identity(tmp_path):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "required-checks.lock").write_text(json.dumps({"required": []}))
    for args in ([], ["--owner", "o"], ["--repo", "r"]):
        cp = subprocess.run(
            [str(SCRIPT), *args], cwd=tmp_path,
            env=dict(os.environ, GH_TOKEN="credential-target-sentinel"),
            capture_output=True, text=True,
        )
        assert cp.returncode == 2
        assert "remote validation requires both --owner and --repo" in cp.stderr
        assert "trusted gh unavailable" not in cp.stdout + cp.stderr
        assert "credential-target-sentinel" not in cp.stdout + cp.stderr


def test_remote_validation_fails_closed_before_missing_gh_can_receive_credentials(tmp_path):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "required-checks.lock").write_text(json.dumps({"required": []}))
    cp = subprocess.run([str(SCRIPT), "--owner", "o", "--repo", "r"], cwd=tmp_path,
                        env=dict(os.environ, GH_TOKEN="credential-order-sentinel"), capture_output=True, text=True)
    assert cp.returncode == 2
    assert "reason=trusted_root_owned_gh_unavailable" in cp.stdout
    assert "credential-order-sentinel" not in cp.stdout + cp.stderr


@pytest.mark.parametrize("redirect_key", APPLE_REDIRECT_ENV)
def test_prevalidator_cannot_be_redirected_or_receive_credentials(tmp_path, redirect_key):
    """Exercise the real Apple shim boundary, not a Python-level approximation of it."""
    developer = tmp_path / "attacker-developer"
    planted = developer / "usr" / "bin" / "xcrun"
    planted.parent.mkdir(parents=True)
    marker = tmp_path / "attacker-ran"
    capture = tmp_path / "attacker-environment"
    planted.write_text(
        "#!/bin/bash\n"
        f"/usr/bin/printf ran > {marker!s}\n"
        f"/usr/bin/env > {capture!s}\n"
        "exit 97\n"
    )
    planted.chmod(0o755)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "required-checks.lock").write_text(json.dumps({"required": []}))
    env = dict(
        os.environ,
        **{
            redirect_key: str(developer),
            "GH_TOKEN": "gh-token-prevalidator-sentinel",
            "GITHUB_TOKEN": "github-token-prevalidator-sentinel",
            "GH_ENTERPRISE_TOKEN": "ghe-token-prevalidator-sentinel",
            "UNRELATED_CALLER_VARIABLE": "unrelated-prevalidator-sentinel",
        },
    )
    cp = subprocess.run(
        [str(SCRIPT), "--local-only"], cwd=tmp_path, env=env,
        capture_output=True, text=True,
    )
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert not marker.exists(), f"{redirect_key} executed attacker xcrun"
    assert not capture.exists(), f"{redirect_key} exposed the pre-validator environment"


def test_prevalidator_environment_is_built_empty_before_python_dispatch():
    source = SCRIPT.read_text()
    unset = source.index('unset "$environment_name"')
    scrub = source.index("compgen -e")
    python = source.index("/usr/bin/python3 -I -c")
    assert unset < scrub < python
    assert "export PATH LC_ALL" in source[scrub:python]


def _shell_function(source: str, name: str) -> str:
    match = re.search(rf"(?ms)^{re.escape(name)}\(\) \(\n.*?^\)\n", source)
    assert match, f"missing production shell function: {name}"
    return match.group(0)


def test_credential_bearing_dispatch_preserves_only_explicit_github_tokens(tmp_path):
    source = SCRIPT.read_text()
    function = _shell_function(source, "credential_bearing_exec")
    env = {
        **os.environ,
        "GH_TOKEN": "gh-token-sentinel",
        "GITHUB_TOKEN": "github-token-sentinel",
        "GH_ENTERPRISE_TOKEN": "ghe-token-sentinel",
        "GITHUB_ENTERPRISE_TOKEN": "github-enterprise-token-sentinel",
        "GH_HOST": "attacker.invalid",
        "GH_REPO": "attacker/repo",
        "HTTPS_PROXY": "http://attacker.invalid",
        "PYTHONPATH": str(tmp_path / "python-injection"),
        "BASH_ENV": str(tmp_path / "shell-injection"),
        "GIT_CONFIG_GLOBAL": str(tmp_path / "git-injection"),
        "DYLD_INSERT_LIBRARIES": str(tmp_path / "loader-injection"),
    }
    cp = subprocess.run(
        ["/bin/bash", "-c", function + "\ncredential_bearing_exec /usr/bin/env"],
        env=env, capture_output=True, text=True, check=True,
    )
    child = dict(line.split("=", 1) for line in cp.stdout.splitlines() if "=" in line)

    assert child["GH_TOKEN"] == "gh-token-sentinel"
    assert child["GITHUB_TOKEN"] == "github-token-sentinel"
    assert child["GH_ENTERPRISE_TOKEN"] == "ghe-token-sentinel"
    assert child["GITHUB_ENTERPRISE_TOKEN"] == "github-enterprise-token-sentinel"
    for forbidden in ("GH_HOST", "GH_REPO", "HTTPS_PROXY", "PYTHONPATH", "BASH_ENV", "GIT_CONFIG_GLOBAL", "DYLD_INSERT_LIBRARIES"):
        assert forbidden not in child


def test_credential_capture_bounds_api_stdout_before_command_substitution():
    source = SCRIPT.read_text()
    functions = _shell_function(source, "credential_bearing_exec") + _shell_function(source, "bounded_credential_capture")
    cp = subprocess.run(
        [
            "/bin/bash", "-p", "-c", functions
            + "\nset +e\nout=$(bounded_credential_capture 32 /usr/bin/python3 -c 'print(\"x\"*1048576)')"
            + "\nrc=$?\n/usr/bin/printf '%s\\n%s' \"$rc\" \"$out\"",
        ],
        capture_output=True, text=True, check=True,
    )
    rc, output = cp.stdout.split("\n", 1)
    assert rc != "0"
    assert len(output) <= 33


def test_credential_request_bounds_api_stdout_and_stderr(tmp_path):
    source = SCRIPT.read_text()
    functions = (
        _shell_function(source, "credential_bearing_exec")
        + _shell_function(source, "bounded_credential_request")
    )
    stdout_path = tmp_path / "stdout"
    stderr_path = tmp_path / "stderr"
    program = "import os; os.write(1,b'x'*1048576); os.write(2,b'y'*1048576)"
    command = (
        functions
        + "\nset +e\nbounded_credential_request 32 32 "
        + f"{shlex.quote(str(stdout_path))} {shlex.quote(str(stderr_path))} "
        + f"/usr/bin/python3 -I -c {shlex.quote(program)}"
        + "\nrc=$?\n/usr/bin/printf '%s\\n' \"$rc\""
    )
    cp = subprocess.run(
        ["/bin/bash", "-p", "-c", command],
        capture_output=True, text=True, check=True,
    )
    assert cp.stdout.strip() != "0"
    assert stdout_path.stat().st_size <= 33
    assert stderr_path.stat().st_size <= 33


def test_branch_protection_inventory_normalizes_legacy_and_app_bound_checks():
    source = SCRIPT.read_text()
    match = re.search(r"(?m)^PROTECTION_INVENTORY_JQ='([^']+)'$", source)
    assert match, "production must expose one reviewed normalization expression"
    payload = {
        "contexts": ["legacy", "app-bound"],
        "checks": [
            {"context": "app-bound", "app_id": 15368},
            {"context": "any-app", "app_id": None},
        ],
    }
    cp = subprocess.run(
        ["/usr/bin/jq", "-c", match.group(1)], input=json.dumps(payload),
        capture_output=True, text=True, check=True,
    )
    assert json.loads(cp.stdout) == [
        {"context": "any-app", "app_id": None},
        {"context": "app-bound", "app_id": 15368},
        {"context": "legacy", "app_id": None},
    ]


def test_branch_protection_404_with_nonempty_lock_is_drift(tmp_path):
    """Inject only the already-validated gh path; exercise production remote adjudication."""
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "required-checks.lock").write_text(json.dumps({
        "required": [{"name": "Code security", "source_app": "external", "app_id": 15368}],
    }))
    fake_gh = tmp_path / "fake-gh"
    fake_gh.write_text(
        "#!/bin/bash\n"
        "if [[ \"$*\" == *\"repos/o/r --jq .default_branch\"* ]]; then\n"
        "  /usr/bin/printf 'main\\n'; exit 0\n"
        "fi\n"
        "/usr/bin/printf 'HTTP 404 Not Found\\n' >&2\n"
        "exit 1\n"
    )
    fake_gh.chmod(0o755)
    source = SCRIPT.read_text()
    injected, count = re.subn(
        r"GH=\$\(trusted_tool /usr/local/bin/gh [0-9a-f]{64} gh\) \|\| \{",
        f"GH={shlex.quote(str(fake_gh))} || {{",
        source,
        count=1,
    )
    assert count == 1, "production trusted-gh seam changed"
    test_script = tmp_path / "check-required-checks"
    test_script.write_text(injected)
    test_script.chmod(0o755)

    cp = subprocess.run(
        [str(test_script), "--owner", "o", "--repo", "r"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert cp.returncode == 1, cp.stdout + cp.stderr
    assert "DRIFT (b)" in cp.stdout
    assert "required-checks: clean" not in cp.stdout


def test_every_external_command_before_gh_validation_is_credential_free():
    source = SCRIPT.read_text()
    before_gh = source[:source.index("GH=$(trusted_tool")]
    assert 'credential_free_exec "$JQ" empty' in before_gh
    assert 'credential_free_exec "$JQ" -r' in before_gh
    assert 'credential_free_exec /usr/bin/awk -v' in before_gh


def test_job_id_lock_entry_is_drift_when_job_has_name(tmp_path):
    # Job declares `name: Code security`, so GitHub's check context is that
    # name, NOT the job id "scan". A lock entry naming the job id must be flagged
    # as drift — branch protection could never satisfy a "scan" context.
    wf = "jobs:\n  scan:\n    name: Code security\n    steps:\n      - run: true\n"
    r = _run(
        tmp_path,
        {"required": [{"name": "scan", "source_app": "github-actions",
                       "workflow": ".github/workflows/security.yml", "job": "scan"}]},
        {"security.yml": wf},
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "DRIFT (a)" in r.stdout


def test_job_id_lock_entry_is_clean_when_no_job_name(tmp_path):
    # No direct `name:`, so the effective check context IS the job id "test".
    wf = "jobs:\n  test:\n    steps:\n      - run: true\n"
    r = _run(
        tmp_path,
        {"required": [{"name": "test", "source_app": "github-actions",
                       "workflow": ".github/workflows/tests.yml", "job": "test"}]},
        {"tests.yml": wf},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "required-checks: clean" in r.stdout


def test_regex_metacharacters_in_name_are_literal(tmp_path):
    # "a.b" must match only the literal job name, not "axb" via regex `.`.
    wf = "jobs:\n  scan:\n    name: axb\n    steps:\n      - run: true\n"
    r = _run(
        tmp_path,
        {"required": [{"name": "a.b", "source_app": "github-actions",
                       "workflow": ".github/workflows/security.yml", "job": "scan"}]},
        {"security.yml": wf},
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "DRIFT (a)" in r.stdout


@pytest.mark.parametrize("job", [".*", "s.*", "scan$"])
def test_regex_metacharacters_in_job_id_cannot_match_a_real_job(tmp_path, job):
    wf = "jobs:\n  scan:\n    name: Code security\n    steps:\n      - run: true\n"
    r = _run(
        tmp_path,
        {"required": [{"name": "Code security", "source_app": "github-actions",
                       "workflow": ".github/workflows/security.yml", "job": job}]},
        {"security.yml": wf},
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "DRIFT (a)" in r.stdout
    assert "required-checks: clean" not in r.stdout


def test_portable_ci_contract_rejects_unpinned_reporter_identity(tmp_path):
    portable = Path("tests/contract/test_required_checks_portable.py")
    (tmp_path / portable.parent).mkdir(parents=True)
    shutil.copy2(ROOT / portable, tmp_path / portable)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    shutil.copy2(ROOT / ".github" / "workflows" / "tests.yml", tmp_path / ".github" / "workflows" / "tests.yml")
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text()
    for relative in set(re.findall(r"tests/contract/test_[A-Za-z0-9_]+\.py", workflow)):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    lock = json.loads((ROOT / ".github" / "required-checks.lock").read_text())
    for row in lock["required"]:
        row["app_id"] = None
    (tmp_path / ".github" / "required-checks.lock").write_text(json.dumps(lock))

    cp = subprocess.run(
        [sys.executable, "-B", "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider", str(portable)],
        cwd=tmp_path, capture_output=True, text=True,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"),
    )
    assert cp.returncode != 0, cp.stdout + cp.stderr
    assert "pins_reporter_app_identity" in cp.stdout + cp.stderr
