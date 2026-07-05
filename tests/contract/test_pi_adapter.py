import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT_DRAFT = ROOT / "scripts" / "hermes-busdriver-agent-draft"
AGENT_SMOKE = ROOT / "scripts" / "hermes-busdriver-agent-smoke"
PI_WRAPPER = ROOT / "scripts" / "pi" / "run-pi-busdriver-draft"
PI_SCHEMA = ROOT / "adapters" / "pi" / "pi-result.schema.json"
PI_TOOLS = ROOT / "adapters" / "pi" / "busdriver-tools.ts"
PI_FIXTURE = ROOT / "tests" / "fixtures" / "pi" / "src" / "app.txt"

AUTHORITY_FALSE_FIELDS = [
    "finalization_allowed",
    "commit_allowed",
    "push_allowed",
    "pr_allowed",
    "merge_allowed",
    "marker_write_allowed",
    "deploy_allowed",
    "release_allowed",
    "publish_allowed",
]


def sh(cmd, cwd=None, check=True, env=None):
    cp = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False, env=env)
    if check and cp.returncode != 0:
        raise AssertionError(f"cmd failed rc={cp.returncode}\nCMD={cmd}\nSTDOUT={cp.stdout}\nSTDERR={cp.stderr}")
    return cp


def init_repo(path: Path) -> None:
    sh(["git", "init"], cwd=path)
    sh(["git", "config", "user.email", "test@example.com"], cwd=path)
    sh(["git", "config", "user.name", "Test User"], cwd=path)
    (path / "src").mkdir()
    (path / "src" / "app.txt").write_text("hello\n")
    (path / ".gitignore").write_text(".env\n")
    sh(["git", "add", "."], cwd=path)
    sh(["git", "commit", "-m", "init"], cwd=path)


def fake_busdriver(path: Path) -> Path:
    root = path / "busdriver"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [], "PostToolUse": [], "Stop": []}}))
    (root / "package.json").write_text(json.dumps({"version": "test"}))
    return root


def fake_pi(path: Path) -> Path:
    script = path / "fake-pi"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "repo = Path(os.environ['BD_REPO_ROOT'])\n"
        "target = os.environ.get('FAKE_PI_TARGET', 'src/pi_smoke.txt')\n"
        "content = os.environ.get('FAKE_PI_CONTENT', 'pi adapter smoke ok\\n')\n"
        "(repo / target).parent.mkdir(parents=True, exist_ok=True)\n"
        "(repo / target).write_text(content)\n"
        "artifact_path = Path(os.environ['PI_BD_ARTIFACT_PATH'])\n"
        "artifact_path.parent.mkdir(parents=True, exist_ok=True)\n"
        "artifact = {\n"
        "  'schema': 'pi-busdriver-result/v0',\n"
        "  'worker': 'pi',\n"
        "  'mode': 'mutating_draft',\n"
        "  'ok': True,\n"
        "  'status': 'needs_busdriver_review',\n"
        "  'repo': str(repo),\n"
        "  'branch': '',\n"
        "  'base_head': '',\n"
        "  'post_head': '',\n"
        "  'changed_files': [target],\n"
        "  'files_changed': [target],\n"
        "  'tests_run': [],\n"
        "  'review_findings': [],\n"
        "  'blockers': [],\n"
        "  'blocked_actions': [],\n"
        "  'artifacts': [],\n"
        "  'event_log': [os.environ.get('PI_BD_EVENT_LOG', '')],\n"
        "  'summary': 'fake pi draft',\n"
        "  'limitations': [],\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'authority': {\n"
        "    'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False,\n"
        "    'merge_allowed': False, 'marker_write_allowed': False, 'deploy_allowed': False,\n"
        "    'release_allowed': False, 'publish_allowed': False, 'finalization_allowed': False\n"
        "  },\n"
        "  'finalization_allowed': False, 'commit_allowed': False, 'push_allowed': False,\n"
        "  'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False,\n"
        "  'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False\n"
        "}\n"
        "artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + '\\n')\n"
        "Path(os.environ['PI_BD_EVENT_LOG']).write_text(json.dumps({'tool': 'fake-pi'}) + '\\n')\n"
        "print(json.dumps({'fake_pi': True, 'argv': sys.argv[1:], 'artifact': str(artifact_path)}))\n"
    )
    script.chmod(0o755)
    return script


def fake_pi_bad_authority(path: Path) -> Path:
    script = path / "fake-pi-bad-authority"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "artifact_path = Path(os.environ['PI_BD_ARTIFACT_PATH'])\n"
        "artifact_path.parent.mkdir(parents=True, exist_ok=True)\n"
        "artifact = {\n"
        "  'schema': 'pi-busdriver-result/v0',\n"
        "  'worker': 'pi',\n"
        "  'mode': 'mutating_draft',\n"
        "  'ok': True,\n"
        "  'status': 'needs_busdriver_review',\n"
        "  'repo': str(Path.cwd()),\n"
        "  'branch': '',\n"
        "  'base_head': '',\n"
        "  'post_head': '',\n"
        "  'changed_files': [],\n"
        "  'files_changed': [],\n"
        "  'tests_run': [],\n"
        "  'review_findings': [],\n"
        "  'blockers': [],\n"
        "  'blocked_actions': [],\n"
        "  'artifacts': [],\n"
        "  'event_log': [os.environ.get('PI_BD_EVENT_LOG', '')],\n"
        "  'summary': 'bad authority',\n"
        "  'limitations': [],\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'authority': {'commit_allowed': True, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False, 'finalization_allowed': False},\n"
        "  'finalization_allowed': False, 'commit_allowed': True, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False,\n"
        "  'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False\n"
        "}\n"
        "artifact_path.write_text(json.dumps(artifact) + '\\n')\n"
    )
    script.chmod(0o755)
    return script


def fake_pi_blocked(path: Path) -> Path:
    script = path / "fake-pi-blocked"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "artifact_path = Path(os.environ['PI_BD_ARTIFACT_PATH'])\n"
        "artifact_path.parent.mkdir(parents=True, exist_ok=True)\n"
        "artifact = {\n"
        "  'schema': 'pi-busdriver-result/v0',\n"
        "  'worker': 'pi',\n"
        "  'mode': 'mutating_draft',\n"
        "  'ok': False,\n"
        "  'status': 'blocked',\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'files_changed': [],\n"
        "  'authority': {'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False, 'finalization_allowed': False},\n"
        "  'finalization_allowed': False, 'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False,\n"
        "  'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False\n"
        "}\n"
        "artifact_path.write_text(json.dumps(artifact) + '\\n')\n"
    )
    script.chmod(0o755)
    return script


def fake_pi_extra_property(path: Path) -> Path:
    script = path / "fake-pi-extra-property"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "artifact_path = Path(os.environ['PI_BD_ARTIFACT_PATH'])\n"
        "artifact_path.parent.mkdir(parents=True, exist_ok=True)\n"
        "artifact = {\n"
        "  'schema': 'pi-busdriver-result/v0',\n"
        "  'worker': 'pi',\n"
        "  'mode': 'mutating_draft',\n"
        "  'ok': True,\n"
        "  'status': 'needs_busdriver_review',\n"
        "  'not_busdriver_native_claude_runtime': True,\n"
        "  'files_changed': [],\n"
        "  'authority': {'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False, 'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False, 'finalization_allowed': False},\n"
        "  'finalization_allowed': False, 'commit_allowed': False, 'push_allowed': False, 'pr_allowed': False, 'merge_allowed': False,\n"
        "  'marker_write_allowed': False, 'deploy_allowed': False, 'release_allowed': False, 'publish_allowed': False,\n"
        "  'unexpected_finalized_claim': True\n"
        "}\n"
        "artifact_path.write_text(json.dumps(artifact) + '\\n')\n"
    )
    script.chmod(0o755)
    return script


def fake_pi_no_artifact(path: Path) -> Path:
    script = path / "fake-pi-no-artifact"
    script.write_text("#!/usr/bin/env python3\nprint('no artifact written')\n")
    script.chmod(0o755)
    return script


def fake_pi_sleep(path: Path) -> Path:
    script = path / "fake-pi-sleep"
    script.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(5)\n")
    script.chmod(0o755)
    return script


def test_pi_result_schema_is_fail_closed_contract():
    schema = json.loads(PI_SCHEMA.read_text())

    assert schema["properties"]["schema"]["const"] == "pi-busdriver-result/v0"
    assert schema["properties"]["status"]["enum"] == ["needs_busdriver_review", "blocked"]
    assert "ok" in schema["required"]
    assert "authority" in schema["required"]
    assert "worker" in schema["required"]
    assert schema["properties"]["not_busdriver_native_claude_runtime"]["const"] is True
    for field in AUTHORITY_FALSE_FIELDS:
        assert field in schema["required"]
        assert field in schema["properties"]["authority"]["required"]
        assert schema["properties"][field]["const"] is False
        assert schema["properties"]["authority"]["properties"][field]["const"] is False
    assert schema["additionalProperties"] is False


def test_busdriver_tools_expose_hardened_pi_tool_boundary():
    text = PI_TOOLS.read_text()

    for needle in [
        "bd_status",
        "bd_read",
        "bd_write_draft",
        "bd_bash",
        "bd_artifact",
        "pi-busdriver-tool-result/v0",
        "argv-only",
        "before_hash",
        "after_hash",
        "operation_id",
        "marker_write_allowed",
        "finalization_allowed",
        "needs_busdriver_review",
        "bash -c",
        "symlink",
        "sanitizedGitEnv",
        "GIT_EXTERNAL_DIFF",
        "GIT_DIFF_OPTS",
        "GIT_ASKPASS",
        "GIT_SSH_COMMAND",
        "GIT_EXEC_PATH",
        "core.fsmonitor=false",
        "MAX_BD_FILE_BYTES",
        "write_size_limit",
        "O_NOFOLLOW",
        "openSync",
        ".netrc",
        ".aws\\/credentials",
        ".docker\\/config",
        "return { ...AUTHORITY_FLAGS }",
        "PI_BD_DENIED_WRITES",
        ".split(/\\r?\\n/)",
        "pathDenied",
        "path_excluded",
        "check-ignore",
        "common_secret_path_blocked",
        "gitignored_path_blocked",
        "GIT_IGNORE_RULE_PATH",
        "git_ignore_rule_path_blocked",
        "--no-ext-diff",
        "--no-textconv",
        "toLowerCase()",
        "(?:.*/)?",
        'glob[i] === "*"',
        'pattern += "[^/]*"',
        'glob[i] === "?"',
        'pattern += "[^/]"',
        "controlArgs",
        "finalizationForbidden",
        "markerForbidden",
        "blocked_actions || []).map",
    ]:
        assert needle in text
    assert "shell: true" not in text
    assert text.index("...extra") < text.index("...AUTHORITY_FLAGS")
    assert text.index("lstatSync(abs)") < text.index('readFileSync(abs, "utf8")')


def test_pi_fixture_is_consumed_by_contract_tests():
    assert PI_FIXTURE.read_text() == "initial app content\n"


def test_pi_fixture_drives_fake_pi_contract_output(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("write fixture content through fake pi\n")
    run_dir = tmp_path / "run"
    fake = fake_pi(tmp_path)
    fixture_content = PI_FIXTURE.read_text()

    cp = sh([
        sys.executable,
        str(PI_WRAPPER),
        "--repo",
        str(repo),
        "--prompt-file",
        str(prompt),
        "--run-dir",
        str(run_dir),
        "--pi-bin",
        str(fake),
        "--scope-include",
        "src/from_fixture.txt",
    ], env={**os.environ, "FAKE_PI_TARGET": "src/from_fixture.txt", "FAKE_PI_CONTENT": fixture_content})

    data = json.loads(cp.stdout)
    assert data["ok"] is True
    assert (repo / "src" / "from_fixture.txt").read_text() == fixture_content


def test_agent_smoke_pi_defaults_respect_environment():
    text = AGENT_SMOKE.read_text()
    assert 'default=os.environ.get("PI_BIN", "pi")' in text
    assert 'default=os.environ.get("PI_BD_MODEL", "openai-codex/gpt-5.4-mini")' in text


def test_agent_draft_pi_forwards_scope_exclude_to_wrapper():
    agent_text = AGENT_DRAFT.read_text()
    wrapper_text = PI_WRAPPER.read_text()

    assert 'cmd += ["--scope-exclude", p]' in agent_text
    assert '"--timeout",' in agent_text
    assert "pi_timeout = max(1, args.timeout - 30)" in agent_text
    assert 'ap.add_argument("--scope-exclude", action="append")' in wrapper_text
    assert "PI_BD_DENIED_WRITES" in wrapper_text
    assert "file_outside_scope" in wrapper_text
    assert "file_in_denied_scope" in wrapper_text
    assert "adapter_prompt_file" in wrapper_text
    assert 'cmd.append(f"@{adapter_prompt_file}")' in wrapper_text
    assert '"--no-approve"' in wrapper_text
    assert '"--system-prompt"' in wrapper_text
    assert '"--append-system-prompt"' in wrapper_text


def test_pi_wrapper_rejects_artifact_files_outside_declared_scope(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("write outside scope artifact\n")
    run_dir = tmp_path / "run"
    fake = fake_pi(tmp_path)

    cp = sh([
        sys.executable,
        str(PI_WRAPPER),
        "--repo",
        str(repo),
        "--prompt-file",
        str(prompt),
        "--run-dir",
        str(run_dir),
        "--pi-bin",
        str(fake),
        "--scope-include",
        "docs/**",
    ], env={**os.environ, "FAKE_PI_TARGET": "src/outside.txt"}, check=False)

    data = json.loads(cp.stdout)
    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert "file_outside_scope:src/outside.txt" in data["artifact_errors"]


def test_pi_wrapper_runs_fake_pi_and_validates_artifact(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("write pi smoke\n")
    run_dir = tmp_path / "run"
    fake = fake_pi(tmp_path)

    cp = sh([
        sys.executable,
        str(PI_WRAPPER),
        "--repo",
        str(repo),
        "--prompt-file",
        str(prompt),
        "--run-dir",
        str(run_dir),
        "--pi-bin",
        str(fake),
        "--scope-include",
        "src/pi_smoke.txt",
    ])

    data = json.loads(cp.stdout)
    command = json.loads((run_dir / "pi-command.json").read_text())
    artifact = json.loads((run_dir / "pi-result.json").read_text())
    assert data["ok"] is True
    assert any(str(arg).startswith("@") and str(run_dir / "pi-adapter-prompt.md") in str(arg) for arg in command)
    assert "write pi smoke" not in json.dumps(command)
    assert data["adapter_prompt_file"].endswith("pi-adapter-prompt.md")
    assert data["artifact"]["status"] == "needs_busdriver_review"
    assert artifact["status"] == "needs_busdriver_review"
    assert (repo / "src" / "pi_smoke.txt").read_text() == "pi adapter smoke ok\n"
    for field in AUTHORITY_FALSE_FIELDS:
        assert data[field] is False
        assert data["authority"][field] is False
        assert artifact[field] is False


def test_pi_wrapper_rejects_authority_positive_artifact(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("write unsafe pi artifact\n")
    run_dir = tmp_path / "run"
    fake = fake_pi_bad_authority(tmp_path)

    cp = sh([
        sys.executable,
        str(PI_WRAPPER),
        "--repo",
        str(repo),
        "--prompt-file",
        str(prompt),
        "--run-dir",
        str(run_dir),
        "--pi-bin",
        str(fake),
    ], check=False)

    data = json.loads(cp.stdout)
    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert "authority_field_not_false:commit_allowed" in data["artifact_errors"]
    assert "nested_authority_field_not_false:commit_allowed" in data["artifact_errors"]


def test_pi_wrapper_rejects_blocked_artifact_as_wrapper_failure(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("blocked pi artifact\n")
    run_dir = tmp_path / "run"
    fake = fake_pi_blocked(tmp_path)

    cp = sh([
        sys.executable,
        str(PI_WRAPPER),
        "--repo",
        str(repo),
        "--prompt-file",
        str(prompt),
        "--run-dir",
        str(run_dir),
        "--pi-bin",
        str(fake),
    ], check=False)

    data = json.loads(cp.stdout)
    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["artifact"]["status"] == "blocked"
    assert data["artifact_errors"] == []
    assert "artifact_status_blocked" in data["artifact_blockers"]


def test_pi_wrapper_rejects_schema_additional_properties(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("extra pi artifact property\n")
    run_dir = tmp_path / "run"
    fake = fake_pi_extra_property(tmp_path)

    cp = sh([
        sys.executable,
        str(PI_WRAPPER),
        "--repo",
        str(repo),
        "--prompt-file",
        str(prompt),
        "--run-dir",
        str(run_dir),
        "--pi-bin",
        str(fake),
    ], check=False)

    data = json.loads(cp.stdout)
    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert any("unexpected_finalized_claim" in err and "additionalProperty" in err for err in data["artifact_errors"])


def test_pi_wrapper_rejects_artifact_files_changed_outside_declared_scope(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("try excluded scoped artifact\n")
    run_dir = tmp_path / "run"
    fake = fake_pi(tmp_path)

    cp = sh([
        sys.executable,
        str(PI_WRAPPER),
        "--repo",
        str(repo),
        "--prompt-file",
        str(prompt),
        "--run-dir",
        str(run_dir),
        "--pi-bin",
        str(fake),
        "--scope-include",
        "**",
        "--scope-exclude",
        "src/blocked.txt",
    ], env={**os.environ, "FAKE_PI_TARGET": "src/blocked.txt"}, check=False)

    data = json.loads(cp.stdout)
    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert "file_in_denied_scope:src/blocked.txt" in data["artifact_errors"]


def test_pi_wrapper_rejects_artifact_files_changed_outside_single_segment_scope(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("try nested scoped artifact\n")
    run_dir = tmp_path / "run"
    fake = fake_pi(tmp_path)

    cp = sh([
        sys.executable,
        str(PI_WRAPPER),
        "--repo",
        str(repo),
        "--prompt-file",
        str(prompt),
        "--run-dir",
        str(run_dir),
        "--pi-bin",
        str(fake),
        "--scope-include",
        "src/*.txt",
    ], env={**os.environ, "FAKE_PI_TARGET": "src/nested/blocked.txt"}, check=False)

    data = json.loads(cp.stdout)
    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert "file_outside_scope:src/nested/blocked.txt" in data["artifact_errors"]


def test_pi_wrapper_clears_stale_artifact_before_run(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("no artifact\n")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "pi-result.json").write_text(json.dumps({"schema": "pi-busdriver-result/v0", "status": "needs_busdriver_review"}) + "\n")
    fake = fake_pi_no_artifact(tmp_path)

    cp = sh([
        sys.executable,
        str(PI_WRAPPER),
        "--repo",
        str(repo),
        "--prompt-file",
        str(prompt),
        "--run-dir",
        str(run_dir),
        "--pi-bin",
        str(fake),
    ], check=False)

    data = json.loads(cp.stdout)
    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["artifact"] is None
    assert data["artifact_errors"] == ["artifact_missing"]


def test_pi_wrapper_timeout_returns_structured_blocked(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("timeout\n")
    run_dir = tmp_path / "run"
    fake = fake_pi_sleep(tmp_path)

    cp = sh([
        sys.executable,
        str(PI_WRAPPER),
        "--repo",
        str(repo),
        "--prompt-file",
        str(prompt),
        "--run-dir",
        str(run_dir),
        "--pi-bin",
        str(fake),
        "--timeout",
        "1",
    ], check=False)

    data = json.loads(cp.stdout)
    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["pi_returncode"] == 124
    assert "pi_timeout" in data["stderr_tail"]
    assert data["artifact_errors"] == ["artifact_missing"]


def test_pi_wrapper_missing_pi_returns_structured_blocked(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("missing pi binary\n")
    run_dir = tmp_path / "run"

    cp = sh([
        sys.executable,
        str(PI_WRAPPER),
        "--repo",
        str(repo),
        "--prompt-file",
        str(prompt),
        "--run-dir",
        str(run_dir),
        "--pi-bin",
        str(tmp_path / "missing-pi-bin"),
    ], check=False)

    data = json.loads(cp.stdout)
    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["pi_returncode"] == 127
    assert "pi_launch_error:FileNotFoundError" in data["stderr_tail"]
    assert data["artifact_errors"] == ["artifact_missing"]
    for field in AUTHORITY_FALSE_FIELDS:
        assert data[field] is False
        assert data["authority"][field] is False


def test_agent_draft_pi_adapter_runs_through_gate_with_fake_pi(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake = fake_pi(tmp_path)

    cp = sh([
        sys.executable,
        str(AGENT_DRAFT),
        "--plugin-root",
        str(plugin),
        "--repo",
        str(repo),
        "--state-dir",
        str(state),
        "--agent",
        "pi",
        "--pi-bin",
        str(fake),
        "--prompt",
        "write scoped pi smoke file",
        "--scope-include",
        "src/pi_smoke.txt",
        "--verifier",
        "file=grep -qx 'pi adapter smoke ok' src/pi_smoke.txt",
    ])

    data = json.loads(cp.stdout)
    assert data["ok"] is True
    assert data["status"] == "needs_busdriver_review"
    assert data["agent"] == "pi"
    assert data["postflight"]["changed_files"] == ["src/pi_smoke.txt"]
    assert data["pi_artifact"]["status"] == "needs_busdriver_review"
    assert data["decision"]["commit_allowed"] is False
    assert sh(["git", "rev-list", "--count", "HEAD"], cwd=repo).stdout.strip() == "1"


def test_agent_draft_pi_adapter_accepts_relative_repo_path(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)
    state = tmp_path / "state"
    fake = fake_pi(tmp_path)

    cp = sh([
        sys.executable,
        str(AGENT_DRAFT),
        "--plugin-root",
        str(plugin),
        "--repo",
        repo.name,
        "--state-dir",
        str(state),
        "--agent",
        "pi",
        "--pi-bin",
        str(fake),
        "--prompt",
        "write scoped pi smoke file from relative repo path",
        "--scope-include",
        "src/pi_smoke.txt",
        "--verifier",
        "file=grep -qx 'pi adapter smoke ok' src/pi_smoke.txt",
    ], cwd=tmp_path)

    data = json.loads(cp.stdout)
    assert data["ok"] is True
    assert data["status"] == "needs_busdriver_review"
    assert data["pi_artifact"]["status"] == "needs_busdriver_review"
    assert (repo / "src" / "pi_smoke.txt").read_text() == "pi adapter smoke ok\n"


def test_agent_smoke_pi_adapter_accepts_fake_pi(tmp_path: Path):
    plugin = fake_busdriver(tmp_path)
    fake = fake_pi(tmp_path)

    cp = sh([
        sys.executable,
        str(AGENT_SMOKE),
        "--plugin-root",
        str(plugin),
        "--agent",
        "pi",
        "--pi-bin",
        str(fake),
    ])

    data = json.loads(cp.stdout)
    assert data["ok"] is True
    assert data["summary"]["agent"] == "pi"
    assert data["summary"]["status"] == "needs_busdriver_review"
    assert data["summary"]["changed_files"] == ["src/pi_smoke.txt"]
    assert data["target_content"] == "pi adapter smoke ok\n"
