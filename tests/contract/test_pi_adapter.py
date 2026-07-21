from __future__ import annotations

import hashlib
import json
import os
import runpy
import shutil
import stat
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
AGENT_DRAFT = ROOT / "tests" / "fixtures" / "pi" / "agent-draft-test-harness"
PRODUCTION_AGENT_DRAFT = ROOT / "scripts" / "hermes-busdriver-agent-draft"
AGENT_SMOKE = ROOT / "tests" / "fixtures" / "pi" / "agent-smoke-test-harness"
PRODUCTION_AGENT_SMOKE = ROOT / "scripts" / "hermes-busdriver-agent-smoke"
PI_WRAPPER = ROOT / "tests" / "fixtures" / "pi" / "run-pi-test-harness"
PRODUCTION_PI_WRAPPER = ROOT / "scripts" / "pi" / "run-pi-busdriver-draft"
PI_SCHEMA = ROOT / "adapters" / "pi" / "pi-result.schema.json"
PI_TOOLS = ROOT / "adapters" / "pi" / "busdriver-tools.ts"
PI_FIXTURE = ROOT / "tests" / "fixtures" / "pi" / "src" / "app.txt"
TRUSTED_RUNTIME_MANIFEST = ROOT / "config" / "trusted-runtime-manifest.json"

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


def canonical_pi_package_tree_digest_v2(package_root: Path) -> tuple[str, int]:
    digest = hashlib.sha256(b"hermes-pi-package-tree-v2\0")
    count = 0
    for path in sorted(package_root.rglob("*"), key=lambda item: item.relative_to(package_root).as_posix()):
        relative = path.relative_to(package_root).as_posix().encode()
        if path.is_symlink():
            entry_type = b"symlink"
            content = os.readlink(path).encode()
        elif path.is_file():
            entry_type = b"regular"
            content = path.read_bytes()
        elif path.is_dir():
            continue
        else:
            raise AssertionError(f"unsupported Pi package entry: {path}")
        for field, width in ((relative, 4), (entry_type, 1), (content, 8)):
            digest.update(len(field).to_bytes(width, "big"))
            digest.update(field)
        count += 1
    return digest.hexdigest(), count


def copy_pi_package_tree(source: Path, destination: Path) -> None:
    def hardlink_or_copy(source_file: str, destination_file: str) -> str:
        source_path = Path(source_file)
        destination_path = Path(destination_file)
        if source_path.stat().st_dev == destination_path.parent.stat().st_dev:
            try:
                os.link(source_path, destination_path)
                return destination_file
            except OSError:
                pass
        return shutil.copy2(source_file, destination_file)

    shutil.copytree(source, destination, symlinks=True, copy_function=hardlink_or_copy)


@contextmanager
def pi_package_shadow(source: Path, destination: Path, *, copy_tree=copy_pi_package_tree):
    try:
        copy_tree(source, destination)
        yield destination
    finally:
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        elif destination.exists():
            shutil.rmtree(destination)


def test_pi_package_shadow_removes_partial_copy_when_copy_fails(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "entry.txt").write_text("fixture\n")
    destination = tmp_path / "shadow"

    def failing_copy(_source: Path, target: Path) -> None:
        target.mkdir()
        (target / "partial.txt").write_text("partial\n")
        raise RuntimeError("copy-stage-failure")

    with pytest.raises(RuntimeError, match="copy-stage-failure"):
        with pi_package_shadow(source, destination, copy_tree=failing_copy):
            pytest.fail("copy-stage failure unexpectedly yielded a shadow")

    assert not destination.exists()


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
        "seen = {key: os.environ.get(key) for key in ['GITHUB_TOKEN', 'AWS_SECRET_ACCESS_KEY', 'CUSTOM_SECRET_TOKEN', 'SSH_AUTH_SOCK', 'HERMES_GATE_BASELINE_HMAC_KEY']}\n"
        "(artifact_path.parent / 'seen-env.json').write_text(json.dumps(seen, sort_keys=True) + '\\n')\n"
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


def fake_pi_leaking(path: Path, secret: str) -> Path:
    """A worker that echoes a credential back through every channel the envelope quotes.

    The wrapper treats pi's stdout, stderr and result artifact as untrusted output, so each is a
    way a compromised or merely careless worker gets a credential printed into a Hermes envelope.
    """
    script = path / "fake-pi-leaking"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        f"secret = {secret!r}\n"
        "repo = Path(os.environ['BD_REPO_ROOT'])\n"
        "(repo / 'src').mkdir(parents=True, exist_ok=True)\n"
        "(repo / 'src' / 'pi_smoke.txt').write_text('pi adapter smoke ok\\n')\n"
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
        "  'changed_files': ['src/pi_smoke.txt'],\n"
        "  'files_changed': ['src/pi_smoke.txt'],\n"
        "  'tests_run': [],\n"
        "  'review_findings': [],\n"
        "  'blockers': [],\n"
        "  'blocked_actions': [],\n"
        "  'artifacts': [],\n"
        "  'event_log': [os.environ.get('PI_BD_EVENT_LOG', '')],\n"
        "  'summary': 'auth failed for ' + secret,\n"
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
        "print('pi stdout: using ' + secret)\n"
        "print('pi stderr: rejected ' + secret, file=sys.stderr)\n"
    )
    script.chmod(0o755)
    return script


def test_pi_wrapper_envelope_carries_no_secret_from_a_leaking_worker(tmp_path: Path):
    """v16-r30 C: stdout, stderr and the artifact are all untrusted text the envelope quotes.

    `tail` was a bare `text[-n:]`, so a credential in pi's output was printed verbatim. The
    artifact is the same class of input by another route — the wrapper parses whatever the worker
    wrote and echoes it — so redacting only the tails would leave the adjacent hole open.
    """
    secret = "ghp_" + "a" * 36
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("leak check\n")
    run_dir = tmp_path / "run"

    cp = sh([
        sys.executable, str(PI_WRAPPER), "--repo", str(repo), "--prompt-file", str(prompt),
        "--run-dir", str(run_dir), "--pi-bin", str(fake_pi_leaking(tmp_path, secret)),
        "--scope-include", "src/pi_smoke.txt",
    ], check=False)

    data = json.loads(cp.stdout)
    assert secret not in cp.stdout, "the credential reached the emitted envelope"
    assert "ghp_" not in json.dumps(data)
    assert "[REDACTED]" in data["stdout_tail"] and "[REDACTED]" in data["stderr_tail"]
    assert "[REDACTED]" in data["artifact"]["summary"]
    # The diagnostic must survive its redaction — scrubbing by emitting nothing is not the fix.
    assert data["artifact"]["summary"].startswith("auth failed for ")


def test_agent_draft_envelope_carries_no_secret_from_a_leaking_worker(tmp_path: Path):
    """v16-r30 C: the launcher quotes the worker's tails and artifact into its own envelope too.

    Same leak, one layer up: agent-draft re-reads the adapter's result file and prints its own
    `stdout_tail`/`stderr_tail`, so fixing only the wrapper would still surface the credential
    here — the launcher's envelope is the one an operator actually reads.
    """
    secret = "ghp_" + "b" * 36
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    plugin = fake_busdriver(tmp_path)

    cp = sh([
        sys.executable, str(AGENT_DRAFT), "--plugin-root", str(plugin), "--repo", str(repo),
        "--state-dir", str(tmp_path / "state"), "--agent", "pi",
        "--pi-bin", str(fake_pi_leaking(tmp_path, secret)),
        "--prompt", "write scoped pi smoke file", "--scope-include", "src/pi_smoke.txt",
    ], check=False)

    data = json.loads(cp.stdout)
    assert secret not in cp.stdout, "the credential reached the emitted envelope"
    assert "ghp_" not in json.dumps(data)
    assert "[REDACTED]" in data["pi_artifact"]["summary"]
    assert data["pi_artifact"]["summary"].startswith("auth failed for ")


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
        "parseScopeList",
        "scope_transport_invalid",
        "scope_pattern_rejected",
        "pathDenied",
        "path_excluded",
        "check_ignore",
        "common_secret_path_blocked",
        "gitignored_path_blocked",
        "GIT_IGNORE_RULE_PATH",
        "git_ignore_rule_path_blocked",
        "--no-ext-diff",
        "--no-textconv",
        "toLowerCase()",
        "(?:[\\\\s\\\\S]*/)?",
        "(?![\\\\s\\\\S])",
        "SCOPE_FORBIDDEN_CHARS",
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
    # All adapter filesystem effects are delegated to the descriptor-bound Python broker;
    # the TypeScript side must not retain a pathname check/use fallback.
    assert "lstatSync(abs)" not in text
    assert 'readFileSync(abs, "utf8")' not in text
    assert "mkdirSync(dirname(abs)" not in text
    assert "openSync(abs" not in text
    assert 'broker({ op: "read", root: "repo", rel })' in text
    assert 'broker({ op: "write", root: "repo", rel, content: params.content })' in text


def adapter_code() -> str:
    """The adapter with whole-line `//` comments dropped.

    The negative assertions below are about what this file DOES. Its comments deliberately name the
    constructs that were removed — that is what they are for — so a raw grep would read the
    explanation of a fix as the defect it describes.
    """
    return "\n".join(line for line in PI_TOOLS.read_text().splitlines() if not line.strip().startswith("//"))


def test_busdriver_tools_never_execute_git_directly():
    """v16-r31 A3: the adapter names a git VERB; it never runs git.

    `execFileSync("git", ...)` was PATH-resolved, so the ambient PATH chose the binary that
    inspected the repository, and argv-shaped, so every call site sat one string away from a
    mutating verb behind a hand-maintained env denylist. The only child process this file may start
    is the broker, which holds the wrapper-authenticated retained git and a fixed argv table.
    """
    text = adapter_code()

    assert 'execFileSync("git"' not in text
    assert "execFileSync(cmd, args" not in text, "bd_bash executed the caller's own argv"
    assert "sanitizedGitEnv" not in text, "a git env denylist survives only if git is still run here"
    assert "GIT_ENV_DENYLIST" not in text
    # Exactly one child process, and it is the broker.
    assert text.count("execFileSync(") == 1
    assert 'execFileSync(python, ["-I", script]' in text
    assert 'broker({ op: "git", root: "repo", verb: "check_ignore", rel })' in text
    assert 'broker({ op: "git", root: "repo", verb, rel: "" })' in text
    # The broker's env carries the roots and NOTHING else — never a credential, and since v16-r34c
    # never git's pathname either: BD_BROKER_GIT made the executable the broker ran a value that a
    # writer of this process's environment could choose, so the broker resolves it from its own
    # frozen root-owned table instead. Asserted as an exact list rather than a membership test,
    # because the property is that nothing ELSE is forwarded.
    assert '"BD_BROKER_ROOT_REPO", "BD_BROKER_ROOT_RUN"' in text
    assert "BD_BROKER_GIT" not in text, "the broker's git is back to being named by the environment"


def test_busdriver_tools_scope_transport_is_json_not_newline_split():
    """v16-r31 C6: `safe\\n**` must stay ONE pattern all the way to the matcher.

    A newline-joined list cannot express a pattern containing a newline, so the split re-admitted
    the very character scopeTokenRejected() exists to refuse — as a separate, unrejected `**`.
    """
    text = adapter_code()

    assert ".split(/\\r?\\n/)" not in text, "newline-delimited scope transport survives"
    assert "splitList" not in text
    assert "JSON.parse(value)" in text
    assert "Array.isArray(parsed)" in text
    assert 'typeof item !== "string"' in text
    assert "scopeTokenRejected(item)" in text


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


def test_private_pi_config_copies_auth_without_user_packages(tmp_path: Path):
    source = tmp_path / "source"
    private = tmp_path / "private"
    source.mkdir()
    (source / "auth.json").write_text('{"provider":"fake"}\n')
    (source / "settings.json").write_text('{"packages":["npm:pi-subagents"]}\n')
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))

    ns["copy_private_pi_config"](source, private)

    assert (private / "auth.json").read_text() == '{"provider":"fake"}\n'
    assert not (private / "settings.json").exists()
    assert (private / "auth.json").stat().st_mode & 0o777 == 0o600
    assert private.stat().st_mode & 0o777 == 0o700


def test_private_pi_config_rejects_symlink_auth(tmp_path: Path):
    source = tmp_path / "source"
    private = tmp_path / "private"
    source.mkdir()
    secret = tmp_path / "secret.json"
    secret.write_text('{"provider":"secret"}\n')
    (source / "auth.json").symlink_to(secret)
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))

    ns["copy_private_pi_config"](source, private)

    assert not (private / "auth.json").exists()


def test_production_pi_wrapper_blocks_before_launch_or_auth_copy(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo-production-blocked"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("must not launch\n")
    run_dir = tmp_path / "run"
    sentinel = tmp_path / "pi-ran"
    fake = tmp_path / "fake-pi"
    fake.write_text(f"#!/bin/sh\ntouch {sentinel}\n")
    fake.chmod(0o700)
    home = tmp_path / "home"
    auth = home / ".pi" / "agent" / "auth.json"
    auth.parent.mkdir(parents=True)
    auth.write_text('{"secret":"must-not-copy"}\n')
    monkeypatch.setenv("HOME", str(home))

    cp = sh([
        sys.executable, str(PRODUCTION_PI_WRAPPER), "--repo", str(repo),
        "--prompt-file", str(prompt), "--run-dir", str(run_dir), "--pi-bin", str(fake),
    ], check=False)
    data = json.loads(cp.stdout)

    assert cp.returncode == 2
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["error"] == "agent_containment_and_credential_broker_unavailable"
    assert not sentinel.exists()
    assert not (run_dir / "pi-home" / ".pi" / "agent" / "auth.json").exists()


def test_production_pi_wrapper_blocks_before_path_resolution(monkeypatch, capsys, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))

    def fail_which(_name):
        pytest.fail("PATH resolution ran before production policy blocker")

    monkeypatch.setattr(ns["shutil"], "which", fail_which)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(PRODUCTION_PI_WRAPPER),
            "--repo", str(tmp_path / "repo"),
            "--prompt-file", str(tmp_path / "prompt"),
            "--run-dir", str(tmp_path / "run"),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        ns["main"]()

    assert exc.value.code == 2
    assert json.loads(capsys.readouterr().out)["error"] == "agent_containment_and_credential_broker_unavailable"


def test_pi_package_tree_digest_v2_binds_symlink_type_and_target(tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))
    package = tmp_path / "package"
    package.mkdir()
    (package / "package.json").write_text('{"name":"synthetic"}\n')
    (package / "target-a").write_text("same bytes\n")
    (package / "target-b").write_text("same bytes\n")
    link = package / "entry"
    link.symlink_to("target-a")
    baseline, _ = ns["pi_package_tree_digest_v2"](package)

    link.unlink()
    link.symlink_to("target-b")
    target_mutant, _ = ns["pi_package_tree_digest_v2"](package)

    link.unlink()
    link.write_text("target-a")
    type_mutant, _ = ns["pi_package_tree_digest_v2"](package)

    assert target_mutant != baseline
    assert type_mutant != baseline


@pytest.mark.parametrize("target", ["/tmp/outside.js", "../../outside.js", "missing-inside.js"])
def test_pi_package_tree_refuses_symlink_targets_outside_the_authenticated_closure(tmp_path: Path, target: str):
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))
    package = tmp_path / "package"
    package.mkdir()
    (package / "package.json").write_text('{"name":"synthetic"}\n')
    (package / "entry").symlink_to(target)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)

    with pytest.raises(OSError, match="pi_package_symlink_target_untrusted"):
        ns["pi_package_tree_digest_v2"](package, private)


def test_pi_package_tree_retains_internal_relative_symlink(tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))
    package = tmp_path / "package"
    (package / "bin").mkdir(parents=True)
    (package / "package.json").write_text('{"name":"synthetic"}\n')
    (package / "target.js").write_text("reviewed\n")
    (package / "bin" / "entry").symlink_to("../target.js")
    private = tmp_path / "private"
    private.mkdir(mode=0o700)

    digest, count = ns["pi_package_tree_digest_v2"](package, private)
    private_digest, private_count = ns["verify_private_pi_package"](private)

    assert os.readlink(private / "bin" / "entry") == "../target.js"
    assert (private / "bin" / "entry").resolve() == private / "target.js"
    assert (private_digest, private_count) == (digest, count)


def synthetic_pi_package(root: Path, entry_source: str) -> Path:
    (root / "dist").mkdir(parents=True)
    (root / "package.json").write_text('{"name":"synthetic-pi"}\n')
    entry = root / "dist" / "cli.js"
    entry.write_text(entry_source)
    return entry


def test_trusted_pi_executable_launches_retained_bytes_not_the_swappable_anchor(monkeypatch, tmp_path: Path):
    # v16-r25 MEDIUM-6: the wrapper hashed the package tree under a user-writable
    # $HOME anchor and then handed the same pathname to node. A same-UID writer
    # could swap the entry in that window, so the executed bytes were never the
    # authenticated bytes. The launch target must now be a private copy that a
    # post-validation swap of the anchor cannot reach.
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))
    package = tmp_path / "pi-package"
    entry = synthetic_pi_package(package, "console.log('authenticated pi');\n")
    digest, _ = canonical_pi_package_tree_digest_v2(package)
    monkeypatch.setitem(ns["trusted_pi_executable"].__globals__, "TRUSTED_PI_TREE_SHA256", digest)

    private = ns["trusted_pi_executable"](str(entry))
    retained = private.read_bytes()
    entry.write_text("require('child_process').execSync('swapped-after-validation');\n")

    assert private != entry.resolve()
    assert package not in private.parents
    assert private.read_bytes() == retained == b"console.log('authenticated pi');\n"
    assert not private.is_symlink()
    assert private.stat().st_uid == os.getuid()
    assert private.stat().st_nlink == 1
    assert stat.S_IMODE(private.stat().st_mode) == 0o500
    assert stat.S_IMODE(private.parent.stat().st_mode) == 0o700


def test_trusted_pi_executable_rejects_anchor_swapped_before_validation(monkeypatch, capsys, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))
    package = tmp_path / "pi-package"
    entry = synthetic_pi_package(package, "console.log('authenticated pi');\n")
    digest, _ = canonical_pi_package_tree_digest_v2(package)
    monkeypatch.setitem(ns["trusted_pi_executable"].__globals__, "TRUSTED_PI_TREE_SHA256", digest)
    entry.write_text("require('child_process').execSync('swapped-before-validation');\n")

    with pytest.raises(SystemExit, match="2"):
        ns["trusted_pi_executable"](str(entry))

    assert json.loads(capsys.readouterr().out)["error"] == "pi_executable_integrity_failed"


def test_trusted_pi_executable_refuses_to_read_a_symlinked_package_entry(monkeypatch, tmp_path: Path):
    # O_NOFOLLOW is what makes the single read authoritative: an entry that turns
    # into a symlink between the directory walk and the read must fail closed
    # rather than silently authenticate whatever the link points at.
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))
    package = tmp_path / "pi-package"
    entry = synthetic_pi_package(package, "console.log('authenticated pi');\n")
    digest, _ = canonical_pi_package_tree_digest_v2(package)
    monkeypatch.setitem(ns["trusted_pi_executable"].__globals__, "TRUSTED_PI_TREE_SHA256", digest)
    real_is_symlink = Path.is_symlink

    def swap_to_symlink(self: Path) -> bool:
        seen = real_is_symlink(self)
        if self == entry and not seen:
            target = tmp_path / "attacker-payload.js"
            target.write_text("console.log('authenticated pi');\n")
            entry.unlink()
            entry.symlink_to(target)
        return seen

    monkeypatch.setattr(Path, "is_symlink", swap_to_symlink)

    with pytest.raises(SystemExit, match="2"):
        ns["trusted_pi_executable"](str(entry))


def test_trusted_node_executable_launches_retained_private_copy(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))
    source = tmp_path / "node"
    source.write_bytes(b"reviewed-node\n")
    source.chmod(0o755)
    globals_ = ns["trusted_node_executable"].__globals__
    monkeypatch.setitem(globals_, "TRUSTED_NODE", source)
    monkeypatch.setitem(globals_, "TRUSTED_NODE_SHA256", hashlib.sha256(source.read_bytes()).hexdigest())

    private = ns["trusted_node_executable"]()
    retained = private.read_bytes()
    source.write_bytes(b"swapped-after-authentication\n")

    assert private != source
    assert private.read_bytes() == retained == b"reviewed-node\n"
    assert not private.is_symlink()
    assert private.stat().st_uid == os.getuid()
    assert private.stat().st_nlink == 1
    assert stat.S_IMODE(private.stat().st_mode) == 0o500


def test_live_production_pi_tree_matches_independent_v2_digest_and_real_verifier():
    manifest = json.loads(TRUSTED_RUNTIME_MANIFEST.read_text())
    configured_executable = Path(manifest["executables"]["pi"]["path"])
    executable = configured_executable.resolve()
    package_root = executable.parent.parent
    digest, count = canonical_pi_package_tree_digest_v2(package_root)
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))

    assert count > 0
    assert digest == manifest["executables"]["pi-package-tree"]["sha256"]

    private = ns["trusted_pi_executable"](str(configured_executable))
    private_root = private.parents[1]

    assert private != executable
    assert package_root not in private.parents
    assert private.relative_to(private_root) == executable.relative_to(package_root)
    assert canonical_pi_package_tree_digest_v2(private_root) == (digest, count)


def test_real_pi_verifier_rejects_shadow_symlink_target_and_type_mutants(capsys, tmp_path: Path):
    manifest = json.loads(TRUSTED_RUNTIME_MANIFEST.read_text())
    production_executable = Path(manifest["executables"]["pi"]["path"]).resolve()
    production_package = production_executable.parent.parent
    shadow_package = tmp_path / "pi-package-shadow"

    with pi_package_shadow(production_package, shadow_package):
        shadow_executable = shadow_package / production_executable.relative_to(production_package)
        ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))
        production_pin = ns["TRUSTED_PI_TREE_SHA256"]

        assert production_pin == manifest["executables"]["pi-package-tree"]["sha256"]
        assert canonical_pi_package_tree_digest_v2(shadow_package) == canonical_pi_package_tree_digest_v2(production_package)

        private = ns["trusted_pi_executable"](str(shadow_executable))

        assert private != shadow_executable.resolve()
        assert shadow_package not in private.parents
        assert canonical_pi_package_tree_digest_v2(private.parents[1])[0] == production_pin

        symlink = next(path for path in sorted(shadow_package.rglob("*")) if path.is_symlink())
        original_target = os.readlink(symlink)
        symlink.unlink()
        symlink.symlink_to(original_target + "-target-mutant")
        with pytest.raises(SystemExit, match="2"):
            ns["trusted_pi_executable"](str(shadow_executable))
        assert json.loads(capsys.readouterr().out)["error"] == "pi_executable_integrity_failed"

        symlink.unlink()
        symlink.write_text(original_target)
        with pytest.raises(SystemExit, match="2"):
            ns["trusted_pi_executable"](str(shadow_executable))
        assert json.loads(capsys.readouterr().out)["error"] == "pi_executable_integrity_failed"
        assert ns["TRUSTED_PI_TREE_SHA256"] == production_pin

    assert not shadow_package.exists()


def test_pi_child_receives_no_ambient_credentials(tmp_path: Path):
    repo = tmp_path / "repo-secret-env"
    repo.mkdir()
    init_repo(repo)
    prompt = tmp_path / "prompt-secret-env.md"
    prompt.write_text("write pi smoke\n")
    run_dir = tmp_path / "run-secret-env"
    fake = fake_pi(tmp_path)
    env = {
        **os.environ,
        "GITHUB_TOKEN": "github-sentinel",
        "AWS_SECRET_ACCESS_KEY": "cloud-sentinel",
        "CUSTOM_SECRET_TOKEN": "custom-sentinel",
        "SSH_AUTH_SOCK": "/tmp/ssh-agent-sentinel",
        "HERMES_GATE_BASELINE_HMAC_KEY": "hmac-sentinel",
    }

    cp = sh([
        sys.executable, str(PI_WRAPPER), "--repo", str(repo), "--prompt-file", str(prompt),
        "--run-dir", str(run_dir), "--pi-bin", str(fake), "--scope-include", "src/pi_smoke.txt",
    ], env=env)

    assert json.loads(cp.stdout)["ok"] is True
    assert json.loads((run_dir / "seen-env.json").read_text()) == {
        "AWS_SECRET_ACCESS_KEY": None,
        "CUSTOM_SECRET_TOKEN": None,
        "GITHUB_TOKEN": None,
        "HERMES_GATE_BASELINE_HMAC_KEY": None,
        "SSH_AUTH_SOCK": None,
    }


def test_agent_smoke_pi_defaults_respect_environment():
    text = PRODUCTION_AGENT_SMOKE.read_text()
    assert 'default=os.environ.get("PI_BIN", "pi")' in text
    assert 'default=os.environ.get("PI_BD_MODEL", "openai-codex/gpt-5.4-mini")' in text


def test_agent_draft_pi_forwards_scope_exclude_to_wrapper():
    agent_text = PRODUCTION_AGENT_DRAFT.read_text()
    wrapper_text = PRODUCTION_PI_WRAPPER.read_text()

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
    assert data["pi_returncode"] != 0
    assert "missing-pi-bin" in data["stderr_tail"]
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


# --- v16-r27 item 7: PI_BIN is a pathname the wrapper trusts, so it may not come from PATH ---


@pytest.mark.parametrize("value", ["pi-evil", "./pi", "../pi", "bin/pi", "  pi"])
def test_relative_pi_bin_is_rejected_rather_than_resolved_through_path(value: str, monkeypatch, tmp_path: Path):
    """r26 flagged the asymmetry: OpenCode rejects a relative override, Pi ran `shutil.which`.

    A PATH lookup lets whatever ambient PATH the parent happens to carry choose the executable
    whose bytes then define the trusted tree digest — while private auth material is mounted. The
    tree digest and the production blocker make it unreachable today, which is exactly when a
    latent one is cheap to close.

    The PATH lookup must not merely FAIL, it must not HAPPEN: a `which` that resolves is the whole
    hazard, so the double here returns a real, digest-valid package the wrapper would accept.
    """
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))
    planted = _pi_package(tmp_path / "planted")
    which_calls: list[str] = []
    monkeypatch.setitem(ns["trusted_pi_executable"].__globals__, "shutil", _RecordingShutil(which_calls, str(planted)))

    with pytest.raises(SystemExit):
        ns["trusted_pi_executable"](value)

    assert which_calls == [], f"{value!r} was resolved through PATH"


def _pi_package(root: Path) -> Path:
    """A minimally well-formed Pi package the wrapper would otherwise accept."""
    dist = root / "dist"
    dist.mkdir(parents=True)
    (root / "package.json").write_text('{"name":"pi","version":"0.0.0"}\n')
    entry = dist / "index.js"
    entry.write_text("console.log('pi');\n")
    return entry


def test_bare_pi_name_uses_the_pinned_anchor_not_path(monkeypatch, tmp_path: Path):
    """The bare default name means "the pinned anchor", exactly as OpenCode's does."""
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))
    which_calls: list[str] = []
    monkeypatch.setitem(ns["trusted_pi_executable"].__globals__, "shutil", _RecordingShutil(which_calls))
    monkeypatch.setitem(ns["trusted_pi_executable"].__globals__, "TRUSTED_PI", tmp_path / "nonexistent" / "dist" / "index.js")

    with pytest.raises(SystemExit):
        ns["trusted_pi_executable"]("pi")

    assert which_calls == [], "the wrapper consulted PATH"


class _RecordingShutil:
    def __init__(self, calls: list[str], resolves_to: str | None = None) -> None:
        self._calls = calls
        self._resolves_to = resolves_to

    def which(self, value):  # noqa: D102 - test double
        self._calls.append(value)
        return self._resolves_to

    def rmtree(self, *args, **kwargs):  # noqa: D102 - test double
        return shutil.rmtree(*args, **kwargs)


def test_pinned_pi_anchor_is_bound_to_the_manifest():
    ns = runpy.run_path(str(PRODUCTION_PI_WRAPPER))
    manifest = json.loads(TRUSTED_RUNTIME_MANIFEST.read_text())

    assert str(ns["TRUSTED_PI"]) == str(Path(manifest["executables"]["pi"]["path"]).resolve())
