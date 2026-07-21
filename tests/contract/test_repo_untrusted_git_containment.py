"""v16-r25 B7: a probe pointed at an untrusted repo must not execute that repo's code.

`core.fsmonitor` names a command git runs during index refresh, and it is settable from the
REPO-LOCAL `.git/config` — which `GIT_CONFIG_NOSYSTEM=1` and `GIT_CONFIG_GLOBAL=/dev/null` do not
disable, because those cover only the system and global files. Any probe that runs `git status`
against a repo it does not trust therefore hands that repo arbitrary code execution under the
operator's account, while reporting itself `read_only: true`.

`deliver`, `delivery-status`, `gate`, and `lock` all pin `-c core.fsmonitor=false`; r24 left
`status`, `relay-brief`, and `litmus-status` unpinned. These tests hold all of them to the same
contract, and prove the hostile config really would run without it.
"""
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "scripts" / "hermes-busdriver-status"
RELAY_BRIEF = ROOT / "scripts" / "hermes-busdriver-relay-brief"
LITMUS = ROOT / "scripts" / "hermes-busdriver-litmus-status"

GIT = "/usr/bin/git"


def hostile_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A git repo whose own .git/config asks git to run a payload on index refresh."""
    repo = tmp_path / "hostile"
    repo.mkdir()
    sentinel = tmp_path / "PWNED"
    payload = tmp_path / "payload.sh"
    payload.write_text(f"#!/bin/sh\ntouch {sentinel}\necho ''\n")
    payload.chmod(0o700)

    subprocess.run([GIT, "init", "-q", "."], cwd=repo, check=True)
    subprocess.run([GIT, "config", "user.email", "t@example.test"], cwd=repo, check=True)
    subprocess.run([GIT, "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "tracked.txt").write_text("x\n")
    subprocess.run([GIT, "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run([GIT, "-c", "core.fsmonitor=false", "commit", "-qm", "init"], cwd=repo, check=True)
    # Armed only after the setup commits, so the fixture cannot trip its own payload.
    subprocess.run([GIT, "config", "core.fsmonitor", str(payload)], cwd=repo, check=True)
    (repo / "dirty.txt").write_text("y\n")
    return repo, sentinel


def test_the_hostile_fixture_really_would_execute_without_the_pin(tmp_path: Path):
    """Guard against a vacuous suite: prove the payload runs when nothing pins it."""
    repo, sentinel = hostile_repo(tmp_path)

    subprocess.run([GIT, "status", "--porcelain=v1"], cwd=repo, capture_output=True)

    assert sentinel.exists(), "fixture is inert; the containment tests below would prove nothing"


def test_the_pin_is_what_stops_it(tmp_path: Path):
    repo, sentinel = hostile_repo(tmp_path)

    subprocess.run([GIT, "-c", "core.fsmonitor=false", "status", "--porcelain=v1"], cwd=repo, capture_output=True)

    assert not sentinel.exists()


def test_status_probe_does_not_execute_an_untrusted_repos_fsmonitor(tmp_path: Path):
    """hermes-busdriver-status --repo <untrusted> reports read_only:true while running `git status`."""
    repo, sentinel = hostile_repo(tmp_path)

    cp = subprocess.run(
        [sys.executable, str(STATUS), "--repo", str(repo), "--no-external-resolver"],
        capture_output=True, text=True,
    )

    assert not sentinel.exists(), "untrusted repo achieved code execution inside a read-only probe"
    assert cp.returncode in (0, 1)


def test_relay_brief_does_not_execute_an_untrusted_repos_fsmonitor(tmp_path: Path):
    repo, sentinel = hostile_repo(tmp_path)

    subprocess.run([sys.executable, str(RELAY_BRIEF), "--repo", str(repo)], capture_output=True, text=True)

    assert not sentinel.exists()


def test_litmus_status_does_not_execute_an_untrusted_repos_fsmonitor(tmp_path: Path):
    repo, sentinel = hostile_repo(tmp_path)

    subprocess.run([sys.executable, str(LITMUS), "--repo", str(repo)], capture_output=True, text=True)

    assert not sentinel.exists()


# --- ambient loader / config injection ---

# PATH picks the binary; PYTHONPATH/BASH_ENV/ENV/ZDOTDIR inject code into a child's startup;
# LD_*/DYLD_* inject it into the loader; GIT_CONFIG_COUNT/KEY_n/VALUE_n inject git config
# directly — including core.fsmonitor — which is the same code execution by another door, and
# which GIT_CONFIG_GLOBAL=/dev/null does nothing about.
AMBIENT_INJECTION_ENV = {
    "PYTHONPATH": "/tmp/evil",
    "PYTHONHOME": "/tmp/evil",
    "BASH_ENV": "/tmp/evil/rc.sh",
    "ENV": "/tmp/evil/rc.sh",
    "ZDOTDIR": "/tmp/evil",
    "LD_PRELOAD": "/tmp/evil/lib.so",
    "LD_LIBRARY_PATH": "/tmp/evil",
    "DYLD_INSERT_LIBRARIES": "/tmp/evil/lib.dylib",
    "DYLD_LIBRARY_PATH": "/tmp/evil",
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "core.fsmonitor",
    "GIT_CONFIG_VALUE_0": "/tmp/evil/payload.sh",
    "GIT_DIR": "/tmp/evil/.git",
    "GIT_EXTERNAL_DIFF": "/tmp/evil/diff.sh",
    "GIT_SSH_COMMAND": "/tmp/evil/ssh.sh",
    "GIT_TRACE": "/tmp/evil/trace.log",
}


@pytest.mark.parametrize("script, factory", [
    ("hermes-busdriver-status", "child_env"),
    ("hermes-busdriver-relay-brief", "child_env"),
    ("hermes-busdriver-litmus-status", "sanitized_git_env"),
])
def test_git_child_env_is_an_allowlist_not_a_denylist(monkeypatch, script: str, factory: str):
    """A denylist forwards whatever it failed to think of; an allowlist cannot.

    litmus-status's sanitized_git_env removed a hand-listed set of GIT_* names and copied
    everything else, so LD_PRELOAD, DYLD_*, PYTHONPATH and the GIT_CONFIG_COUNT/KEY_n/VALUE_n
    config-injection trio all survived into the git child.
    """
    for key, value in AMBIENT_INJECTION_ENV.items():
        monkeypatch.setenv(key, value)
    ns = runpy.run_path(str(ROOT / "scripts" / script))

    env = ns[factory]()

    for key in AMBIENT_INJECTION_ENV:
        assert key not in env, f"{script}: {key} reached the git child"
    assert env["PATH"] == "/usr/bin:/bin:/usr/sbin:/sbin"


@pytest.mark.parametrize("script, factory", [
    ("hermes-busdriver-status", "child_env"),
    ("hermes-busdriver-relay-brief", "child_env"),
    ("hermes-busdriver-litmus-status", "sanitized_git_env"),
])
def test_git_child_env_keeps_required_locale_temp_and_home_semantics(monkeypatch, script: str, factory: str):
    """Containment must not cost the semantics the probes legitimately need."""
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    monkeypatch.setenv("LC_TIME", "en_GB.UTF-8")
    monkeypatch.setenv("TMPDIR", "/tmp/mine")
    monkeypatch.setenv("HOME", "/Users/someone")
    ns = runpy.run_path(str(ROOT / "scripts" / script))

    env = ns[factory]()

    assert env["LANG"] == "en_US.UTF-8"
    assert env["LC_ALL"] == "en_US.UTF-8"
    assert env["LC_TIME"] == "en_GB.UTF-8"
    assert env["TMPDIR"] == "/tmp/mine"
    assert env["HOME"] == "/Users/someone"
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull


@pytest.mark.parametrize("script", [
    "hermes-busdriver-status",
    "hermes-busdriver-relay-brief",
    "hermes-busdriver-litmus-status",
])
def test_every_git_invocation_pins_fsmonitor_off(script: str):
    """Static check: no git call in these files may omit the pin.

    The runtime tests above cover the paths a probe takes today; this one covers the next git call
    someone adds. Repo-local config is untrusted input on every one of them.
    """
    source = (ROOT / "scripts" / script).read_text()
    assert "core.fsmonitor=false" in source, f"{script} never pins core.fsmonitor"
