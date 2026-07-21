import argparse
import hashlib
import json
import runpy
import stat
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
# Production, and it stays production: every refusal, static and live-path assertion below invokes
# or inspects THIS file. LOOP is deliberately not aliased to the harness — a fixture double standing
# in for the entrypoint under test is how a suite ends up proving only that the double works.
LOOP = ROOT / "scripts" / "hermes-busdriver-pr-grind-loop"
# The offline doubles, source-separated and never installed (v16-r33 A). Only the fixture-driven
# control-flow tests reach for this; production has no flag that can reach it at all.
HARNESS = ROOT / "tests" / "fixtures" / "pr-grind-loop-test-harness"


def fixture(tmp_path: Path, name: str, status: str, *, head: str = "a" * 40, clean: bool | None = None, reason: str | None = None) -> Path:
    if clean is None:
        clean = status == "clean"
    blockers = []
    if reason == "head_changed":
        blockers = [f"head_changed_during_collection:{'f' * 12}->{head[:12]}"]
    data = {
        "schema": "hermes-busdriver-pr-grind-check/v0",
        "version": 1,
        "ok": True,
        "read_only": True,
        "repository": "owner/repo",
        "pr": 7,
        "url": "https://github.com/owner/repo/pull/7",
        "head": head,
        "head_repository": "owner/repo",
        "head_ref": "feature",
        "base_repository": "owner/repo",
        "base": "main",
        "base_sha": "b" * 40,
        "status": status,
        "clean": clean,
        "blockers": blockers,
        "checks": {"failed": 0, "pending": 1 if status == "wait" else 0, "mode": "all", "kept": 1, "failed_rows": [], "pending_rows": [], "source": "fixture", "relevance_unavailable": False},
        "actionable_comments": [{"id": 1, "user": "reviewer", "path": "src/app.py", "line": 1, "commit_id": head, "body_preview": "fix this", "source": "review_comment"}] if status == "needs_fix" else [],
        "decision": {"status": status, "pr_grind_clean": status == "clean", "merge_allowed": False, "needs_fix": status == "needs_fix", "wait": status == "wait", "blocked": status == "blocked", "reason": reason or status},
    }
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


def run_loop(tmp_path: Path, *fixtures: Path, extra: list[str] | None = None) -> tuple[subprocess.CompletedProcess[str], dict]:
    """Drive the loop's control flow over offline results — via the harness, never production.

    The harness runs production's own main(); what it substitutes is only where a round's result
    comes from. So these still test the real loop, and the one thing they cannot do is pretend
    production could have been handed the same file.
    """
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    cmd = [
        sys.executable,
        str(HARNESS),
        "--repo",
        str(repo),
        "--pr",
        "7",
        "--poll-interval",
        "0",
        "--max-wait-seconds",
        "5",
    ]
    for item in fixtures:
        cmd += ["--fixture-result-file", str(item)]
    if extra:
        cmd += extra
    cp = subprocess.run(cmd, text=True, capture_output=True, check=False)
    assert cp.stdout, cp.stderr
    return cp, json.loads(cp.stdout)


def patch_bounded_run(monkeypatch, ns: dict, fake_run) -> None:
    """Bind a subprocess.run-shaped test double to the bounded production seam.

    The double replaces the primitive, so it also replaces the primitive's CONTRACT — and the two
    halves it used to drop are the two this repo cares about.

    `limit` was a named sink: declared so the call would not TypeError, then never read. Production
    spells it `limit: int = MAX_CAPTURED_BYTES`, and a default is frozen at def time, so a double
    that lets it default to `None` is not a lenient double — it is a different contract, one under
    which a production caller that dropped the bound still passes. Defaulting to the module's own
    constant means a site omitting `limit` is exercised against exactly the number production would
    have used, and a site that WEAKENS it is exercised against the weakened one, where the overflow
    assertion below can see it.

    And `overflowed` was hardcoded `False`, so no test reaching this seam could ever observe the
    refusal — `_bounded_run`'s `RuntimeError("child_output_too_large")` and `git_raw`'s
    `git_output_too_large` were unreachable through the fake, and a double could hand back oversized
    bytes as though they had arrived, which is the one shape production cannot produce. Production
    bounds at the pipe and REFUSES over it rather than slicing (a slice cuts the `token:` prefix off
    a secret and emits the remainder as ordinary text), so the double refuses the same way.
    """
    globals_ = ns["run_check"].__globals__
    BoundedOutput = globals_["BoundedOutput"]

    def bounded(cmd, *, cwd=None, env=None, timeout=None, stdin_bytes=None, limit=None, text=True):
        # Production's default, not None: a caller that omits the bound must still be bound.
        effective_limit = globals_["MAX_CAPTURED_BYTES"] if limit is None else limit
        kwargs = {
            "cwd": str(cwd) if cwd else None,
            "env": env,
            "timeout": timeout,
            "text": text,
            "capture_output": True,
            "check": False,
        }
        if stdin_bytes is not None:
            kwargs["input"] = stdin_bytes.decode() if text else stdin_bytes
        try:
            cp = fake_run(cmd, **kwargs)
        except subprocess.TimeoutExpired as exc:
            empty = "" if text else b""
            stdout = exc.output if exc.output is not None else empty
            stderr = exc.stderr if exc.stderr is not None else empty
            return BoundedOutput(124, stdout, stderr, False, True)
        # Production counts what the child SAID and refuses BOTH streams if either exceeded the
        # bound. `>` not `>=`: exactly `limit` bytes is not an overflow.
        measured = max(
            len(cp.stdout) if cp.stdout is not None else 0,
            len(cp.stderr) if cp.stderr is not None else 0,
        )
        if measured > effective_limit:
            return BoundedOutput(cp.returncode, "" if text else b"", "" if text else b"", True, False)
        return BoundedOutput(cp.returncode, cp.stdout, cp.stderr, False, False)

    monkeypatch.setitem(globals_, "run_bounded", bounded)


def expected_identity_args() -> list[str]:
    return [
        "--expected-repository", "owner/repo",
        "--expected-head-repository", "owner/repo",
        "--expected-head-ref", "feature",
        "--expected-base-repository", "owner/repo",
        "--expected-base-ref", "main",
        "--expected-head-sha", "a" * 40,
        "--expected-base-sha", "b" * 40,
    ]


def expected_identity_namespace(**overrides):
    values = {
        "check_script": None,
        "repo": "/tmp/repo",
        "pr": "7",
        "expected_repository": "owner/repo",
        "expected_head_repository": "owner/repo",
        "expected_head_ref": "feature",
        "expected_base_repository": "owner/repo",
        "expected_base_ref": "main",
        "expected_head_sha": "a" * 40,
        "expected_base_sha": "b" * 40,
        "plugin_root": None,
        "check_timeout": 10,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_default_checker_executes_retained_bytes_not_swappable_private_path(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(LOOP))
    globals_ = ns["run_check"].__globals__
    checker_source = tmp_path / "trusted" / "hermes-busdriver-pr-grind-check"
    checker_source.parent.mkdir(parents=True)
    payload = json.loads(fixture(tmp_path, "clean-check.json", "clean").read_text())
    checker_source.write_text("import json\nprint(json.dumps(%r))\n" % payload)
    checker_source.chmod(0o500)
    attacker_ran = tmp_path / "loop-checker-attacker-ran"
    attacker = (
        "import json, pathlib\n"
        f"pathlib.Path({str(attacker_ran)!r}).write_text('pwned')\n"
        f"print(json.dumps({payload!r}))\n"
    )
    monkeypatch.setitem(globals_, "CHECK", checker_source)
    monkeypatch.setitem(globals_, "TRUSTED_CHECK_SHA256", hashlib.sha256(checker_source.read_bytes()).hexdigest())
    monkeypatch.setitem(globals_, "trusted_executable_path", lambda name: Path(sys.executable) if name == "python3" else pytest.fail(f"unexpected trusted executable {name}"))
    original_run_bounded = globals_["run_bounded"]

    def swap_checker_then_exec(cmd, *args, **kwargs):
        entry = next(Path(str(value)) for value in cmd if Path(str(value)).name == "hermes-busdriver-pr-grind-check")
        entry.unlink()
        entry.write_text(attacker)
        entry.chmod(0o500)
        return original_run_bounded(cmd, *args, **kwargs)

    monkeypatch.setitem(globals_, "run_bounded", swap_checker_then_exec)

    result, meta = ns["run_check"](expected_identity_namespace(repo=str(tmp_path)))

    assert meta["ok"] is True
    assert result and result["status"] == "clean"
    assert not attacker_ran.exists(), "pr-grind-loop executed attacker-replaced checker path"


def assert_no_finalization_authority(decision: dict) -> None:
    for key in [
        "finalization_allowed",
        "commit_allowed",
        "push_allowed",
        "pr_allowed",
        "merge_allowed",
        "deploy_allowed",
        "release_allowed",
        "publish_allowed",
    ]:
        assert decision[key] is False
    assert decision["fixing_allowed"] is False
    assert decision["fix_rounds_attempted"] == 0
    assert decision["marker_write_allowed"] is False


def test_clean_result_emits_read_only_envelope_without_merge_authority(tmp_path: Path):
    """Envelope shape for a fixture-driven clean run.

    r25 asserted `ok: True` / `status: "clean"` / `pr_grind_clean: True` here off a hand-authored
    file, which is the forgery v16-r26A item 7 closes: the assertions were the bug written down as
    a contract. The shape checks stay; the authority claims are now the demoted ones.
    """
    cp, data = run_loop(tmp_path, fixture(tmp_path, "clean.json", "clean"))

    assert data["schema"] == "hermes-busdriver-pr-grind-loop/v0"
    assert data["read_only"] is True
    assert data["decision"]["marker_write_allowed"] is False
    assert_no_finalization_authority(data["decision"])
    assert len(data["iterations"]) == 1
    assert data["iterations"][0]["status"] == "clean"

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["clean"] is False
    assert data["source"] == "fixture"
    assert data["authoritative"] is False
    assert data["decision"]["pr_grind_clean"] is False


def test_partial_clean_checker_payload_is_blocked(tmp_path: Path):
    result_file = tmp_path / "partial-clean.json"
    result_file.write_text(json.dumps({"status": "clean"}))

    cp, data = run_loop(tmp_path, result_file)

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["decision"]["reason"] == "checker_schema_invalid"
    assert data["policy_gaps"] == ["checker_schema_invalid"]
    assert_no_finalization_authority(data["decision"])


@pytest.mark.parametrize(("field", "value"), [
    ("pr", 8),
    ("url", "https://github.com/owner/repo/pull/8"),
    ("head", "c" * 40),
    ("head_repository", "attacker/repo"),
    ("head_ref", "other"),
    ("base_repository", "attacker/repo"),
    ("base", "release"),
    ("base_sha", "d" * 40),
])
def test_checker_identity_mismatch_is_blocked(tmp_path: Path, field: str, value: object):
    result_file = fixture(tmp_path, "identity-mismatch.json", "clean")
    payload = json.loads(result_file.read_text())
    payload[field] = value
    result_file.write_text(json.dumps(payload))

    cp, data = run_loop(tmp_path, result_file, extra=expected_identity_args())

    assert cp.returncode == 1
    assert data["status"] == "blocked"
    assert data["decision"]["reason"] == "checker_binding_mismatch"
    assert data["policy_gaps"] == [f"checker_binding_mismatch:{field}"]


@pytest.mark.parametrize("mutation", [
    lambda payload: payload.update(ok=False),
    lambda payload: payload.update(clean=False),
    lambda payload: payload.pop("decision"),
    lambda payload: payload.update(finalization_allowed=True),
    lambda payload: payload["decision"].update(merge_allowed=True),
])
def test_conflicting_or_authority_positive_clean_checker_payload_is_blocked(tmp_path: Path, mutation):
    result_file = fixture(tmp_path, "conflicting-clean.json", "clean")
    payload = json.loads(result_file.read_text())
    mutation(payload)
    result_file.write_text(json.dumps(payload))

    cp, data = run_loop(tmp_path, result_file)

    assert cp.returncode == 1
    assert data["status"] == "blocked"
    assert data["decision"]["reason"] == "checker_schema_invalid"
    assert data["policy_gaps"] == ["checker_schema_invalid"]


def test_wait_status_polls_until_clean_with_bounded_budget(tmp_path: Path):
    cp, data = run_loop(
        tmp_path,
        fixture(tmp_path, "wait.json", "wait"),
        fixture(tmp_path, "clean.json", "clean", head="d" * 40),
    )

    # The loop reached its clean branch — that is what this test is about. The top-level verdict
    # stays demoted because the evidence is a fixture (v16-r26A item 7); `iterations` carries the
    # control-flow proof.
    assert [item["status"] for item in data["iterations"]] == ["wait", "clean"]
    assert data["latest_head"] == "d" * 40
    assert cp.returncode == 1
    assert data["status"] == "blocked"
    assert data["source"] == "fixture"
    assert_no_finalization_authority(data["decision"])


def test_needs_fix_bails_without_attempting_fix_rounds(tmp_path: Path):
    cp, data = run_loop(tmp_path, fixture(tmp_path, "needs-fix.json", "needs_fix"))

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["status"] == "needs_fix"
    assert data["decision"]["reason"] == "actionable_feedback_present_read_only_no_fix"
    assert data["decision"]["fixing_allowed"] is False
    assert data["decision"]["fix_rounds_attempted"] == 0
    assert len(data["iterations"]) == 1
    assert_no_finalization_authority(data["decision"])


def test_head_changed_block_repolls_latest_head_before_deciding(tmp_path: Path):
    cp, data = run_loop(
        tmp_path,
        fixture(tmp_path, "head-changed.json", "blocked", reason="head_changed"),
        fixture(tmp_path, "clean.json", "clean", head="e" * 40),
    )

    # Same as the wait case: the re-poll reaching `clean` is the behaviour under test; the
    # fixture-sourced top level stays non-authoritative.
    assert [item["decision_reason"] for item in data["iterations"]] == ["head_changed", "clean"]
    assert data["latest_head"] == "e" * 40
    assert cp.returncode == 1
    assert data["status"] == "blocked"
    assert data["source"] == "fixture"


def test_wait_exhaustion_fails_closed(tmp_path: Path):
    cp, data = run_loop(
        tmp_path,
        fixture(tmp_path, "wait.json", "wait"),
        extra=["--max-wait-seconds", "0", "--max-polls", "3"],
    )

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["status"] == "wait"
    assert data["decision"]["reason"] == "max_wait_exhausted"
    assert len(data["iterations"]) == 1
    assert_no_finalization_authority(data["decision"])


def test_unrecognized_checker_status_is_policy_gap(tmp_path: Path):
    cp, data = run_loop(tmp_path, fixture(tmp_path, "mystery.json", "mystery"))

    assert cp.returncode == 1
    assert data["ok"] is False
    assert data["status"] == "blocked"
    assert data["decision"]["reason"] == "checker_schema_invalid"
    assert data["policy_gaps"] == ["checker_schema_invalid"]
    assert len(data["iterations"]) == 0
    assert_no_finalization_authority(data["decision"])


def test_nonzero_fix_round_request_is_rejected_before_loop(tmp_path: Path):
    """Production refuses fix rounds, and it refuses them before it needs any evidence at all."""
    cp = subprocess.run(
        [
            sys.executable,
            str(LOOP),
            "--repo",
            str(tmp_path),
            "--pr",
            "7",
            "--max-fix-rounds",
            "1",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode != 0
    data = json.loads(cp.stderr.strip())
    assert data == {"ok": False, "error": "fix_rounds_not_supported_in_read_only_loop"}


def test_expected_repository_mismatch_blocks_clean_fixture(tmp_path: Path):
    result_file = fixture(tmp_path, "wrong-repo.json", "clean")
    data = json.loads(result_file.read_text())
    data["repository"] = "attacker/other"
    result_file.write_text(json.dumps(data))

    cp, output = run_loop(tmp_path, result_file, extra=["--expected-repository", "owner/name"])

    assert cp.returncode == 1
    assert output["ok"] is False
    assert output["status"] == "blocked"
    assert output["decision"]["reason"] == "repository_binding_mismatch"
    assert output["policy_gaps"] == ["repository_binding_mismatch"]
    assert_no_finalization_authority(output["decision"])


def test_live_checker_rejects_content_tamper(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(LOOP))
    checker = tmp_path / "check-tampered"
    checker.write_text("tampered\n")
    ns["run_check"].__globals__["TRUSTED_CHECK_SHA256"] = hashlib.sha256(b"trusted\n").hexdigest()
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: pytest.fail("tampered checker must not execute"))
    args = argparse.Namespace(
        check_script=str(checker), repo=str(tmp_path), pr=7,
        plugin_root=None, check_timeout=10, expected_repository=None,
    )
    data, meta = ns["run_check"](args)
    assert data is None
    assert meta["error"] == "checker_integrity_failed"


def _installed_bundle(tmp_path: Path) -> tuple[Path, Path, bytes]:
    """A loop + checker in the shape production actually has: installed 0755 files.

    The old fixture built a 0700 `private-bundle` with a `trusted-bin/` of private git/gh/jq copies
    beside the checker, because `run_check` used to detect that bundle and hand it down. It does not
    any more — the checker derives git/gh/jq from its own frozen root-owned table — so `run_check`
    now always reads its source with `private=False`, which is what an installed 0755 file is.
    """
    scripts = tmp_path / "installed-bundle" / "scripts"
    scripts.mkdir(parents=True)
    loop_script = scripts / "hermes-busdriver-pr-grind-loop"
    source_check = scripts / "hermes-busdriver-pr-grind-check"
    loop_script.write_bytes(LOOP.read_bytes())
    loop_script.chmod(0o755)
    checker_bytes = (ROOT / "scripts" / "hermes-busdriver-pr-grind-check").read_bytes()
    source_check.write_bytes(checker_bytes)
    source_check.chmod(0o755)
    return loop_script, source_check, checker_bytes


def test_loop_executes_the_retained_checker_bytes_not_the_replaced_source(monkeypatch, tmp_path: Path):
    """The checker is a repo script with no root-owned home, so it IS still retained privately and
    that half is unchanged: replacing the source after authentication does not change what runs.

    What went is the `trusted-bin/` this parent used to stage beside it and the
    HERMES_BUSDRIVER_PRIVATE_RUNTIME flag that selected it. The loop now holds exactly one executable
    pin: the frozen root-owned Python used to launch those authenticated retained bytes.
    """
    loop_script, source_check, trusted_checker_bytes = _installed_bundle(tmp_path)
    ns = runpy.run_path(str(loop_script))
    globals_ = ns["run_check"].__globals__
    monkeypatch.setitem(globals_, "TRUSTED_CHECK_SHA256", hashlib.sha256(trusted_checker_bytes).hexdigest())
    captured: dict = {}

    def fake_run(cmd, **kwargs):
        retained = next(Path(str(value)) for value in cmd if Path(str(value)).name == "hermes-busdriver-pr-grind-check")
        # Replace the source mid-flight: what runs must be the bytes that were authenticated.
        source_check.write_text("raise SystemExit('mutable source executed')\n")
        captured.update({
            "checker": retained,
            "env": dict(kwargs["env"]),
            "bytes": kwargs.get("input", "").encode(),
            "mode": stat.S_IMODE(retained.stat().st_mode),
            "parent_mode": stat.S_IMODE(retained.parent.stat().st_mode),
        })
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    patch_bounded_run(monkeypatch, ns, fake_run)
    args = argparse.Namespace(
        check_script=None, repo=str(tmp_path), pr=7,
        plugin_root=None, check_timeout=10, expected_repository=None,
    )

    data, meta = ns["run_check"](args)

    assert data == {}
    assert meta["ok"] is True
    assert captured["checker"] != source_check
    assert captured["bytes"] == trusted_checker_bytes, "the replaced source was executed"
    assert captured["mode"] == 0o500
    assert captured["parent_mode"] == 0o700
    assert not captured["checker"].exists(), "the retained copy outlived its round"
    assert "HERMES_BUSDRIVER_PRIVATE_RUNTIME" not in captured["env"]
    assert not (loop_script.parents[1] / "trusted-bin").exists()
    assert globals_["TRUSTED_EXECUTABLE_SOURCES"] == {"python3": Path("/usr/bin/python3")}
    assert set(globals_["TRUSTED_EXECUTABLE_DIGESTS"]) == {"python3"}
    for dead in ("PRIVATE_TRUSTED_BIN",):
        assert dead not in globals_, f"the loop reacquired an executable pin: {dead}"


@pytest.mark.parametrize(
    "mutation",
    ("checker_missing", "checker_symlink", "checker_hardlink", "checker_digest"),
)
def test_loop_rejects_a_mutated_checker_source_before_dispatch(monkeypatch, tmp_path: Path, mutation: str):
    """The mutations that still exist, against the source the loop actually reads.

    `scripts_mode`, `bin_missing` and `tool_digest` went with the private bundle: there is no
    `trusted-bin/` left to be missing and no tool pin left to diverge. `checker_mode` went with
    them for a different reason — the source is the installed 0755 file, and `private=False`
    deliberately does not constrain its mode. Keeping any of the four would have meant asserting a
    rejection production has no reason to make, which is how a suite ends up green against a
    contract nobody holds.
    """
    loop_script, source_check, checker_bytes = _installed_bundle(tmp_path)

    if mutation == "checker_missing":
        source_check.unlink()
    elif mutation == "checker_symlink":
        target = tmp_path / "checker-target"
        target.write_bytes(checker_bytes)
        target.chmod(0o755)
        source_check.unlink()
        source_check.symlink_to(target)
    elif mutation == "checker_hardlink":
        (tmp_path / "checker-alias").hardlink_to(source_check)
    else:
        source_check.write_bytes(checker_bytes + b"# changed\n")

    ns = runpy.run_path(str(loop_script))
    globals_ = ns["run_check"].__globals__
    monkeypatch.setitem(globals_, "TRUSTED_CHECK_SHA256", hashlib.sha256(checker_bytes).hexdigest())
    patch_bounded_run(monkeypatch, ns, lambda *_args, **_kwargs: pytest.fail("a mutated checker must not dispatch"))
    args = argparse.Namespace(
        check_script=None, repo=str(tmp_path), pr=7,
        plugin_root=None, check_timeout=10, expected_repository=None,
    )

    data, meta = ns["run_check"](args)

    assert data is None
    assert meta["error"] == "checker_integrity_failed"


def test_checker_subprocess_scrubs_ambient_repo_and_git_overrides(monkeypatch, tmp_path: Path):
    ns = runpy.run_path(str(LOOP))
    captured = {}
    blocked = ["GH_REPO", "GH_HOST", "GIT_CONFIG_COUNT", "GIT_SSH_COMMAND", "GIT_ASKPASS", "SSH_ASKPASS", "BASH_ENV", "PYTHONPATH", "PYTHONHOME", "OPAQUE_SECRET"]
    for key in blocked:
        monkeypatch.setenv(key, "attacker-controlled")

    # **kwargs, not the call's exact keywords: this double stands in for subprocess.run, and what
    # it is here to observe is the env and the argv, not how many arguments run_bounded passes.
    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env")
        payload = {"schema": "hermes-busdriver-pr-grind-check/v0", "status": "clean", "clean": True}
        return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")

    patch_bounded_run(monkeypatch, ns, fake_run)
    checker = tmp_path / "check"
    checker.write_text("# trusted test checker\n")
    ns["run_check"].__globals__["TRUSTED_CHECK_SHA256"] = hashlib.sha256(checker.read_bytes()).hexdigest()
    args = argparse.Namespace(
        check_script=str(checker), repo=str(tmp_path), pr=7,
        plugin_root=None, check_timeout=10, expected_repository=None,
    )

    data, meta = ns["run_check"](args)

    assert data["status"] == "clean"
    assert meta["ok"] is True
    assert captured["env"] is not None
    assert all(captured["env"].get(key) is None for key in blocked)
    assert captured["cmd"][1] == "-I"


def test_live_loop_rejects_untrusted_check_script(tmp_path: Path):
    script = tmp_path / "untrusted-check.py"
    script.write_text("#!/usr/bin/env python3\nprint('{}')\n")
    script.chmod(0o755)

    cp = subprocess.run(
        [
            sys.executable,
            str(LOOP),
            "--repo",
            str(tmp_path),
            "--pr",
            "7",
            "--check-script",
            str(script),
            "--max-polls",
            "1",
            "--max-wait-seconds",
            "1",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode == 2
    assert json.loads(cp.stderr) == {"ok": False, "error": "check_script_untrusted"}


# --- v16-r25 B5: the loop is a production entrypoint, not just a delivery-status child ---


def test_loop_tail_redacts_before_bounding():
    """r24 bounded child output here but never redacted it; the loop is itself an entrypoint."""
    ns = runpy.run_path(str(LOOP))
    secret = "ghp_" + "n" * 36

    out = ns["tail"]("child failed: " + secret + " " + "x" * 9000)

    assert secret not in out
    assert len(out) <= 4000


@pytest.mark.parametrize("prefix_len", [0, 3990, 3999, 4000, 4200])
def test_loop_secrets_are_redacted_across_the_truncation_boundary(prefix_len: int):
    ns = runpy.run_path(str(LOOP))
    secret = "ghp_" + "m" * 36

    out = ns["tail"]("p" * prefix_len + " " + secret + " " + "s" * 50)

    assert "ghp_" not in out


def test_loop_tail_redacts_credential_env_values(monkeypatch):
    ns = runpy.run_path(str(LOOP))
    monkeypatch.setenv("GITHUB_TOKEN", "opaque-enterprise-credential-value")

    assert "opaque-enterprise-credential-value" not in ns["tail"]("boom: opaque-enterprise-credential-value")


def test_loop_tail_redacts_url_userinfo():
    ns = runpy.run_path(str(LOOP))

    out = ns["tail"]("fatal: could not read from https://" + "x-access-token:" + "ghs_aaaaaaaaaaaaaaaaaaaaaaaa@github.com/o/r.git")

    assert "ghs_aaaaaaaaaaaaaaaaaaaaaaaa" not in out
    assert "github.com/o/r.git" in out


# --- v16-r26A item 7: a fixture-built result can never be a top-level production clean ---


def test_fixture_result_file_never_claims_top_level_clean(tmp_path):
    """A hand-authored file must not become `status: clean` + `pr_grind_clean: true`.

    r25 left provenance surviving only in `iterations[0].source`, so the top level of the
    envelope — the part every reader looks at first — was byte-identical to a live clean run.
    """
    clean = fixture(tmp_path, "clean.json", "clean")

    cp, data = run_loop(tmp_path, clean)

    assert data["status"] != "clean", "fixture forged a top-level production clean"
    assert data["clean"] is False
    assert data["decision"]["pr_grind_clean"] is False
    assert data["decision"]["status"] != "clean"
    assert cp.returncode != 0


def test_fixture_result_file_declares_non_authoritative_provenance(tmp_path):
    clean = fixture(tmp_path, "clean.json", "clean")

    _cp, data = run_loop(tmp_path, clean)

    assert data["source"] == "fixture"
    assert data["authoritative"] is False
    assert "fixture_evidence_not_authoritative" in data["policy_gaps"]


def test_fixture_result_file_preserves_nested_diagnostic_data(tmp_path):
    """Demotion is about authority, not about hiding what the fixture said."""
    clean = fixture(tmp_path, "clean.json", "clean")

    _cp, data = run_loop(tmp_path, clean)

    assert data["iterations"][0]["source"] == "fixture"
    assert data["iterations"][0]["status"] == "clean"
    assert data["iterations"][0]["clean"] is True


# --- v16-r33 A: production parses no caller-supplied evidence, and binds every run to a PR ---


def test_production_refuses_a_caller_supplied_fixture_result_file(tmp_path):
    """The affordance is absent, not gated: production's parser has never heard of the flag.

    The harness above drives the same offline results through the same main(). What must not exist
    is an INSTALLED entrypoint that will read a caller's file — so this asserts on the production
    binary the operator actually runs, and it must refuse before emitting any envelope at all.
    """
    cp = subprocess.run(
        [
            sys.executable,
            str(LOOP),
            "--repo",
            str(tmp_path),
            "--pr",
            "7",
            "--fixture-result-file",
            str(fixture(tmp_path, "clean.json", "clean")),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode == 2
    assert "unrecognized arguments" in cp.stderr
    assert "--fixture-result-file" in cp.stderr
    assert cp.stdout == "", "a refused run must not emit an envelope"


def test_production_requires_identity_bindings_on_every_run(tmp_path):
    """r33 A: the fixture flag WAIVED these, so a fixture run was bound to no real PR at all.

    That waiver was the flag's second half, and the more dangerous one — it is what made a result
    file about some other PR unfalsifiable. It left production with the flag it belonged to.
    """
    cp = subprocess.run(
        [sys.executable, str(LOOP), "--repo", str(tmp_path), "--pr", "7", "--max-polls", "1"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert cp.returncode != 0
    assert json.loads(cp.stderr) == {"ok": False, "error": "expected_repository_required"}


def test_live_path_still_reaches_top_level_clean():
    """The demotion must key off provenance, not break the authoritative path.

    r33 A: provenance used to be read off the caller's own argv, which is why this could assert it
    by handing production a Namespace. It is a module global now, unset by anything production
    parses — so the live default is what a real run gets, and only the non-installed harness can
    flip it. Both halves are asserted here: the default, and that flipping it demotes.
    """
    ns = runpy.run_path(str(LOOP))

    assert ns["FIXTURE_MODE"] is False, "production must default to authoritative provenance"
    assert ns["fixture_sourced"]() is False

    ns["fixture_sourced"].__globals__["FIXTURE_MODE"] = True
    assert ns["fixture_sourced"]() is True
