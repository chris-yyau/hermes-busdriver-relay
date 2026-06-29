import importlib.machinery
import importlib.util
from pathlib import Path


SMOKE = Path(__file__).resolve().parents[2] / "scripts" / "hermes-busdriver-smoke"


def load_smoke_module():
    loader = importlib.machinery.SourceFileLoader("hermes_busdriver_smoke", str(SMOKE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_summary_parse_error_marks_check_failed():
    smoke = load_smoke_module()

    for initial_returncode, expected_returncode in [(0, 1), (42, 42)]:
        check = {"returncode": initial_returncode, "ok": True}
        smoke.mark_summary_parse_error(check, ValueError("bad json"))

        assert check["ok"] is False
        assert check["returncode"] == expected_returncode
        assert "bad json" in check["summary_parse_error"]


def test_run_timeout_returns_structured_failure():
    smoke = load_smoke_module()

    result = smoke.run(["python3", "-c", "import time; time.sleep(2)"], timeout=1)

    assert result["ok"] is False
    assert result["returncode"] == 124
    assert "timed out" in result["stderr"]


def test_smoke_py_compile_covers_all_relay_scripts():
    smoke = load_smoke_module()
    scripts_dir = SMOKE.parent
    expected = sorted(scripts_dir.glob("hermes-busdriver-*"))

    assert sorted(smoke.PY_COMPILE_SCRIPTS) == expected


def test_finalization_readiness_summary_includes_guardrails_contract():
    smoke = load_smoke_module()

    summary = smoke.summarize_finalization_readiness({
        "readiness": {
            "status": "blocked",
            "ready": False,
            "commit_allowed": False,
            "merge_allowed": False,
        },
        "handoff_envelope": {"schema": "hermes-busdriver-handoff/v0"},
        "finalization_guardrails": {
            "schema": "hermes-busdriver-finalization-guardrails/v0",
            "read_only": True,
        },
    })

    assert summary["handoff_schema"] == "hermes-busdriver-handoff/v0"
    assert summary["finalization_guardrails"]["schema"] == "hermes-busdriver-finalization-guardrails/v0"
    assert summary["finalization_guardrails"]["read_only"] is True
