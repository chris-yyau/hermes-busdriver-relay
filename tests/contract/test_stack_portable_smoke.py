"""Host-independent smoke checks that remain valid at every stacked PR tip."""
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def python_sources() -> list[Path]:
    sources = set(ROOT.rglob("*.py"))
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix:
            continue
        with path.open("rb") as handle:
            shebang = handle.readline(256)
        if shebang.startswith(b"#!") and b"python" in shebang.lower():
            sources.add(path)
    return sorted(sources)


def test_every_python_source_parses_on_the_ci_interpreter():
    sources = python_sources()
    assert len(sources) >= 40
    failures = []
    for path in sources:
        try:
            ast.parse(path.read_text(), filename=str(path.relative_to(ROOT)))
        except (SyntaxError, UnicodeDecodeError) as exc:
            failures.append(f"{path.relative_to(ROOT)}: {exc}")
    assert not failures


def test_core_stack_surfaces_exist():
    tests = (ROOT / ".github/workflows/tests.yml").read_text()
    assert "pull_request:" in tests and "\n  test:" in tests and "\n  compliance:" in tests
    test_job = tests.split("\n  test:", 1)[1].split("\n  compliance:", 1)[0]
    assert "python -B -I -m pytest" in test_job
    command_text = "\n".join(line.split("#", 1)[0] for line in test_job.splitlines())
    paths = [word.rstrip("\\") for word in command_text.split() if word.startswith("tests/contract/")]
    assert paths == ["tests/contract/test_stack_portable_smoke.py"]

    expected = {
        ("test", "test", ".github/workflows/tests.yml"),
        ("zizmor", "Actions security", ".github/workflows/security.yml"),
        ("semgrep", "Code security", ".github/workflows/security.yml"),
        ("trivy", "Dependency CVEs", ".github/workflows/security.yml"),
        ("checkov", "IaC misconfig", ".github/workflows/security.yml"),
    }
    lock = json.loads((ROOT / ".github/required-checks.lock").read_text())
    required = lock["required"]
    assert {(row["job"], row["name"], row["workflow"]) for row in required} == expected
    assert all(row["source_app"] == "github-actions" and row["app_id"] == 15368 for row in required)

    security = (ROOT / ".github/workflows/security.yml").read_text()
    assert "pull_request:" in security
    for job, name, _ in expected - {("test", "test", ".github/workflows/tests.yml")}:
        assert f"\n  {job}:" in security and f"\n    name: {name}" in security

    for relative in ("scripts/hermes-busdriver-gate", "scripts/check-required-checks.sh"):
        path = ROOT / relative
        assert path.is_file() and path.stat().st_mode & 0o111 and path.read_bytes().startswith(b"#!")
    assert (ROOT / "tests/contract").is_dir()
