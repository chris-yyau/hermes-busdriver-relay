"""Portable CI contract: this file and its selected peers must be host-independent."""
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
SECURITY_WORKFLOW = ROOT / ".github" / "workflows" / "security.yml"
LOCK = ROOT / ".github" / "required-checks.lock"
CLAUDE_GUIDE = ROOT / ".claude" / "CLAUDE.md"


def portable_job() -> str:
    workflow = WORKFLOW.read_text()
    return workflow.split("  test:\n", 1)[1].split("\n  compliance:\n", 1)[0]


def portable_test_paths() -> list[str]:
    script = portable_job().split(
        "      - name: Run portable contract subset\n",
        1,
    )[1]
    return re.findall(
        r"tests/contract/test_[A-Za-z0-9_]+\.py",
        script,
    )


def test_portable_job_uses_an_explicit_host_independent_allowlist():
    job = portable_job()
    paths = portable_test_paths()

    assert "runs-on: ubuntu-latest" in job
    assert "python -B -I -m pytest -q -p no:cacheprovider" in job
    assert "pytest tests/contract -q" not in job
    assert "--ignore=tests/contract/" not in job
    assert paths == ["tests/contract/test_stack_portable_smoke.py"]
    assert "tests/contract/test_required_checks.py" not in paths
    assert len(paths) == len(set(paths))
    assert all((ROOT / path).is_file() for path in paths)


def test_portable_job_never_references_contracts_introduced_by_later_stack_slices():
    job = portable_job()
    assert "tests/contract/test_stack_portable_smoke.py" in job
    for introduced_later in (
        "tests/contract/test_required_checks_portable.py",
        "tests/contract/test_docs_inventory_closure.py",
        "tests/contract/test_finalization_unlock_contract_docs.py",
        "tests/contract/test_skill_references.py",
    ):
        assert introduced_later not in job


def test_portable_allowlist_contains_no_known_host_sealed_assumptions():
    # Build markers from fragments so this portable test does not contain the prohibited literals
    # that it checks in each workflow-selected source file.
    markers = (
        "/" + "Users/",
        "/" + "Library/",
        "SF_" + "RESTRICTED",
        "st_" + "flags",
        "/usr/bin/" + "sandbox-exec",
        "/usr/bin/" + "jq",
    )

    for relative in portable_test_paths():
        source = (ROOT / relative).read_text()
        found = [marker for marker in markers if marker in source]
        assert not found, f"{relative} has host-sealed assumptions: {found}"


def test_required_check_lock_names_portable_contract_and_no_self_hosted_lane():
    lock = json.loads(LOCK.read_text())
    rows = {
        (row["name"], row["source_app"], row["workflow"], row["job"])
        for row in lock["required"]
    }

    assert (
        "test", "github-actions", ".github/workflows/tests.yml", "test"
    ) in rows
    assert not any(row[0] == "Host runtime contract" for row in rows)
    assert not any(row["name"] == "Host runtime contract" for row in lock["advisory"])


def test_required_check_lock_pins_reporter_app_identity():
    lock = json.loads(LOCK.read_text())
    github_actions_rows = [row for row in lock["required"] if row["source_app"] == "github-actions"]

    assert github_actions_rows
    assert all(row.get("app_id") == 15368 for row in github_actions_rows)


def test_required_security_jobs_execute_on_every_pull_request():
    workflow = SECURITY_WORKFLOW.read_text()
    assert "  changes:\n" not in workflow
    for job in ("trivy", "semgrep", "checkov", "zizmor"):
        section = workflow.split(f"  {job}:\n", 1)[1].split("\n  ", 1)[0]
        assert "needs: [changes]" not in section
        assert "\n    if:" not in section


def test_claude_ci_guide_requires_actual_scanner_execution():
    guide = CLAUDE_GUIDE.read_text()
    assert "All four required scanner jobs run on every pull request" in guide
    assert "skipped scanner is not passing evidence" in guide
    assert "changes` job gates them" not in guide
    assert "skipped = passing" not in guide
