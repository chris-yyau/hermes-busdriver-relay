"""Contract tests for scripts/check-required-checks.sh surface (a).

Invokes the script as a subprocess (like the other contract tests) against a
tmp repo, asserting the job_name parser:
  - accepts a required name that IS the job's own direct `name:` field,
  - does NOT false-pass when only a nested step `with: name:` matches,
  - treats regex metacharacters in a required name literally.
Run with --local-only so surface (b) makes no GitHub API calls (hermetic).
"""
import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-required-checks.sh"


def _run(tmp_path: Path, lock: dict, workflows: dict[str, str]):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "required-checks.lock").write_text(json.dumps(lock))
    for name, body in workflows.items():
        (tmp_path / ".github" / "workflows" / name).write_text(body)
    return subprocess.run(
        ["bash", str(SCRIPT), "--local-only"],
        cwd=tmp_path, capture_output=True, text=True,
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
