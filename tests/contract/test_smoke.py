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
    check = {"returncode": 0, "ok": True}

    smoke.mark_summary_parse_error(check, ValueError("bad json"))

    assert check["ok"] is False
    assert check["returncode"] == 1
    assert "bad json" in check["summary_parse_error"]
