import json
import subprocess
import sys
from pathlib import Path


RUNTIME = Path(__file__).resolve().parents[2] / "scripts" / "hermes-busdriver-runtime-check"


def make_fake_busdriver(root: Path) -> None:
    (root / "hooks" / "gate-scripts").mkdir(parents=True)
    (root / "package.json").write_text('{"name":"busdriver","version":"test"}\n')
    hooks = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/gate-scripts/pre-commit-gate.sh"'}],
                    "description": "[GATE] Block git commit until codex + design review pass",
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "Write|Edit|Bash",
                    "hooks": [{"type": "command", "command": 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/gate-scripts/check-design-document.sh"'}],
                    "description": "[STATE] Flag design docs for review gate",
                }
            ],
        }
    }
    (root / "hooks" / "hooks.json").write_text(json.dumps(hooks))


def run_runtime(root: Path, stdin: str | None = None) -> dict:
    proc = subprocess.run(
        [sys.executable, str(RUNTIME), "--plugin-root", str(root)],
        input=stdin,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def test_runtime_check_blocks_mutating_launcher_in_normal_shell(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    data = run_runtime(fake, stdin="")
    assert data["read_only"] is True
    assert data["runtime_equivalence"]["hook_manifest_available"] is True
    assert data["runtime_equivalence"]["gate_hooks_declared"] is True
    assert data["runtime_equivalence"]["inside_claude_code_hook_invocation"] is False
    assert data["runtime_equivalence"]["hermes_shell_is_claude_hook_runtime"] is False
    assert data["runtime_equivalence"]["claude_hooks_will_intercept_inner_shell_commands"] is False
    assert data["runtime_equivalence"]["mutating_launcher_allowed"] is False


def test_runtime_check_detects_claude_hook_shaped_stdin_but_still_does_not_allow_mutation(tmp_path):
    fake = tmp_path / "busdriver"
    make_fake_busdriver(fake)
    hook_stdin = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git commit"}})
    data = run_runtime(fake, stdin=hook_stdin)
    assert data["hook_input"]["looks_like_claude_hook_input"] is True
    assert data["runtime_equivalence"]["inside_claude_code_hook_invocation"] is True
    # The checker itself remains a read-only reporter; it never grants launcher authority.
    assert data["runtime_equivalence"]["mutating_launcher_allowed"] is False
