import json
import subprocess
import sys
from pathlib import Path


SMOKE = Path(__file__).resolve().parents[2] / "scripts" / "hermes-busdriver-agent-smoke"


def fake_busdriver(path: Path) -> Path:
    root = path / "busdriver"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [], "PostToolUse": [], "Stop": []}}))
    (root / "package.json").write_text(json.dumps({"version": "test"}))
    return root


def test_agent_smoke_custom_wrapper(tmp_path: Path):
    plugin = fake_busdriver(tmp_path)
    cmd = "python3 - <<'PY'\nfrom pathlib import Path\nPath('src/custom_smoke.txt').write_text('custom adapter smoke ok\\n')\nPY"
    cp = subprocess.run(
        [
            sys.executable,
            str(SMOKE),
            "--plugin-root",
            str(plugin),
            "--agent",
            "custom",
            "--agent-cmd",
            cmd,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert cp.returncode == 0, cp.stdout + cp.stderr
    data = json.loads(cp.stdout)
    assert data["ok"] is True
    assert data["summary"]["status"] == "needs_busdriver_review"
    assert data["summary"]["changed_files"] == ["src/custom_smoke.txt"]
    assert data["target_content"] == "custom adapter smoke ok\n"
