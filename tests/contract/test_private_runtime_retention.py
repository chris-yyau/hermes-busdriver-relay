"""v16-r31 A1/A2/A3: repo anchors are authenticated once and their bytes are retained.

The defect these cover is one shape, repeated at five sites: digest a pathname, then put that same
pathname on a command line. Two reads of one mutable name — so a same-UID writer swaps the file in
between and the child runs bytes the digest never covered. The pin proves nothing about what ran;
it only proves what was read a moment earlier.

Retention closes the anchor read-to-copy race: read once under O_NOFOLLOW, digest those bytes, write
them into a private runtime, and re-prove the retained file. It does *not* make a pathname immutable
against another process running as the same UID; macOS re-resolves that name at exec time. The three
pathname launchers remain production-blocked until an OS isolation/descriptor launch boundary exists.

The swap tests below are deterministic, not timing races: the substitution is already in place, or
is injected exactly where the old code's window was.
"""
import hashlib
import json
import os
import runpy
import stat
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PI_WRAPPER = ROOT / "scripts" / "pi" / "run-pi-busdriver-draft"
AGENT_DRAFT = ROOT / "scripts" / "hermes-busdriver-agent-draft"
PI_TOOLS = ROOT / "adapters" / "pi" / "busdriver-tools.ts"
FS_BROKER = ROOT / "adapters" / "pi" / "busdriver-fs-broker.py"
MANIFEST = ROOT / "config" / "trusted-runtime-manifest.json"


@pytest.fixture(scope="module")
def wrapper() -> dict:
    return runpy.run_path(str(PI_WRAPPER))


@pytest.fixture()
def private_runtime(wrapper, tmp_path, monkeypatch):
    """Point the wrapper's private runtime at a tmp dir this test owns."""
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    monkeypatch.setitem(wrapper["privately_retain"].__globals__, "private_runtime_root", lambda: root)
    return root


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- retention: the bytes that ran are the bytes that were authenticated ---


def test_a_retained_file_holds_the_authenticated_bytes(wrapper, private_runtime, tmp_path):
    source = tmp_path / "payload.ts"
    source.write_bytes(b"reviewed-adapter\n")

    retained = wrapper["privately_retain"](source, sha(b"reviewed-adapter\n"), "pi_tools", mode=0o400)

    assert retained.read_bytes() == b"reviewed-adapter\n"
    assert retained != source, "the anchor itself was handed back; nothing was retained"
    assert private_runtime in retained.parents


def test_a_retained_file_is_private_unshared_and_ours(wrapper, private_runtime, tmp_path):
    source = tmp_path / "payload.py"
    source.write_bytes(b"broker\n")

    retained = wrapper["privately_retain"](source, sha(b"broker\n"), "fs_broker")
    st = retained.lstat()

    assert stat.S_ISREG(st.st_mode)
    assert st.st_uid == os.getuid()
    assert st.st_nlink == 1, "a hardlink is a second name that can rewrite what we are about to run"
    assert stat.S_IMODE(st.st_mode) == 0o500
    assert stat.S_IMODE(retained.parent.lstat().st_mode) == 0o700


def test_a_retained_data_file_is_readable_but_not_executable(wrapper, private_runtime, tmp_path):
    """node READS the adapter; nothing executes it. 0400, not 0500."""
    source = tmp_path / "tools.ts"
    source.write_bytes(b"export {};\n")

    retained = wrapper["privately_retain"](source, sha(b"export {};\n"), "pi_tools", mode=0o400)

    assert stat.S_IMODE(retained.lstat().st_mode) == 0o400


# --- tamper: a digest that does not match is a refusal, before anything runs ---


def test_tampered_bytes_fail_closed(wrapper, private_runtime, tmp_path):
    source = tmp_path / "payload.ts"
    source.write_bytes(b"tampered\n")

    with pytest.raises(SystemExit):
        wrapper["privately_retain"](source, sha(b"reviewed\n"), "pi_tools")


def test_a_missing_anchor_fails_closed(wrapper, private_runtime, tmp_path):
    with pytest.raises(SystemExit):
        wrapper["privately_retain"](tmp_path / "absent.ts", sha(b"x"), "pi_tools")


# --- link: the anchor is read no-follow, and never through a symlink ---


def test_a_symlinked_anchor_is_refused_rather_than_followed(wrapper, private_runtime, tmp_path):
    """O_NOFOLLOW on the anchor: authenticating whatever a link points at is authenticating the
    link's owner's choice, not ours."""
    real = tmp_path / "real.ts"
    real.write_bytes(b"reviewed\n")
    link = tmp_path / "link.ts"
    link.symlink_to(real)

    with pytest.raises(SystemExit):
        wrapper["privately_retain"](link, sha(b"reviewed\n"), "pi_tools")


def test_a_fifo_anchor_is_refused(wrapper, private_runtime, tmp_path):
    """O_NOFOLLOW does not reject a FIFO; the S_ISREG check on the descriptor does."""
    fifo = tmp_path / "payload.ts"
    os.mkfifo(fifo)

    with pytest.raises(SystemExit):
        wrapper["privately_retain"](fifo, sha(b"anything"), "pi_tools")


# --- swap: the window the retention exists to remove ---


def test_an_anchor_swapped_after_the_digest_cannot_reach_the_child(wrapper, private_runtime, tmp_path, monkeypatch):
    """The defect, injected exactly where it lived.

    The old code digested `source` and then named `source` on the launch argv. Here the attacker
    wins that window outright: the anchor is replaced the instant the digest is taken. Retention
    makes the win worthless — the bytes were already copied out of the attacker's reach, so what
    the child gets is what we authenticated, and the swapped anchor is never opened again.
    """
    source = tmp_path / "payload.ts"
    source.write_bytes(b"reviewed\n")
    swapped = []

    real_sha256 = hashlib.sha256

    def sha256_then_swap(data=b""):
        if data == b"reviewed\n" and not swapped:
            swapped.append(True)
            source.write_bytes(b"ATTACKER-PAYLOAD\n")
        return real_sha256(data)

    monkeypatch.setitem(wrapper["privately_retain"].__globals__, "hashlib", type("H", (), {"sha256": staticmethod(sha256_then_swap)}))
    retained = wrapper["privately_retain"](source, sha(b"reviewed\n"), "pi_tools")

    assert swapped, "the attack never ran; the test proves nothing"
    assert source.read_bytes() == b"ATTACKER-PAYLOAD\n", "the fixture did not actually swap the anchor"
    assert retained.read_bytes() == b"reviewed\n", "the attacker's bytes reached the retained runtime"


def test_candidate_wrapper_names_the_retained_adapter_not_the_repo_path():
    """The test-only wrapper retains its adapter; production never reaches this wrapper."""
    text = PI_WRAPPER.read_text()

    launch = text.split("def _run_in_directory", 1)[1]
    assert "str(trusted_tools)" in launch, "the launch still names an unretained path"
    assert "str(TOOLS)" not in launch, "the launch still names the repo-path adapter"


# --- the closure: every retained byte is pinned, and every pin is manifested ---


def test_every_repo_byte_the_pi_wrapper_executes_is_pinned(wrapper):
    """A retained file whose digest is not pinned is a copy, not an authentication."""
    manifest = json.loads(MANIFEST.read_text())
    adapter_runtime = manifest["adapter_runtime"]

    assert wrapper["TRUSTED_PI_TOOLS_SHA256"] == adapter_runtime["adapters/pi/busdriver-tools.ts"]
    assert wrapper["TRUSTED_FS_BROKER_SHA256"] == adapter_runtime["adapters/pi/busdriver-fs-broker.py"]
    assert wrapper["TRUSTED_PI_TOOLS_SHA256"] == sha(PI_TOOLS.read_bytes())
    assert wrapper["TRUSTED_FS_BROKER_SHA256"] == sha(FS_BROKER.read_bytes())


def test_the_agent_draft_blocks_without_a_wrapper_execution_edge():
    ns = runpy.run_path(str(AGENT_DRAFT))
    manifest = json.loads(MANIFEST.read_text())
    source = AGENT_DRAFT.read_text()

    assert ns["PI_PRODUCTION_BLOCKER"] == "agent_containment_and_credential_broker_unavailable"
    assert "run-pi-busdriver-draft" not in source
    assert manifest["adapter_runtime"]["scripts/pi/run-pi-busdriver-draft"] == sha(PI_WRAPPER.read_bytes())


def test_private_runtime_write_rejects_absolute_path_with_dir_fd(tmp_path: Path):
    ns = runpy.run_path(str(AGENT_DRAFT))
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    fd = os.open(runtime, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(OSError, match="private_runtime_absolute_path_with_dir_fd"):
            ns["write_private_runtime_file"](runtime / "tool", b"x", dir_fd=fd)
    finally:
        os.close(fd)
    assert not (runtime / "tool").exists()


def test_private_runtime_write_rejects_parent_traversal_with_dir_fd(tmp_path: Path):
    ns = runpy.run_path(str(AGENT_DRAFT))
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    fd = os.open(runtime, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(OSError, match="private_runtime_relative_path_invalid"):
            ns["write_private_runtime_file"]("../escaped", b"x", dir_fd=fd)
    finally:
        os.close(fd)
    assert not (tmp_path / "escaped").exists()


def test_private_runtime_closing_proof_rejects_a_new_hardlink(tmp_path: Path, monkeypatch):
    ns = runpy.run_path(str(AGENT_DRAFT))
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    target = runtime / "tool"
    alias = tmp_path / "alias"
    real_lstat = os.lstat
    linked = False

    def link_before_lstat(path, *, dir_fd=None):
        nonlocal linked
        if not linked:
            os.link(target, alias)
            linked = True
        return real_lstat(path, dir_fd=dir_fd)

    monkeypatch.setattr(ns["write_private_runtime_file"].__globals__["os"], "lstat", link_before_lstat)

    with pytest.raises(OSError, match="private_runtime_integrity_failed"):
        ns["write_private_runtime_file"](target, b"x")

    assert linked
    assert not target.exists()
    assert alias.read_bytes() == b"x"


def test_no_pinned_runtime_pins_itself():
    """A file whose own bytes contain its own digest cannot exist: writing the pin changes the
    digest the pin must equal. The graph has to stay a DAG."""
    for path in (PI_WRAPPER, AGENT_DRAFT, FS_BROKER, PI_TOOLS):
        assert sha(path.read_bytes()) not in path.read_text(), f"{path.name} pins its own digest"


# --- the interpreter: the one runtime edge every other pin runs on top of ---


def shebang(path: Path) -> bytes:
    return path.read_bytes().split(b"\n", 1)[0]


def test_every_production_script_pins_the_trusted_interpreter():
    """`#!/usr/bin/env python3` hands the choice of interpreter to PATH.

    Every byte this repo executes is authenticated against a pin — the wrapper, the adapter, the
    broker, each sibling helper — and then the kernel resolved the interpreter that runs all of it
    out of the caller's `PATH`. A writable directory earlier on PATH is arbitrary code as the
    operator, executing before any pin in this tree is consulted, so the whole retention design
    sits on an unauthenticated edge. The shebang names the same root-owned binary the manifest
    already pins for child spawns.

    Enumerated by the property that makes a shebang load-bearing — an executable bit on a file the
    kernel will hand to an interpreter — rather than by a path list that can go stale. So
    adapters/pi/busdriver-fs-broker.py is absent on its own merits: it is not executable, and the
    wrapper hands it to the digest-pinned interpreter explicitly. chmod +x it and this fires.
    tests/fixtures/ is excluded because a harness is not production and is never installed.
    """
    manifest = json.loads(MANIFEST.read_text())
    trusted = ("#!" + manifest["executables"]["python3"]["path"]).encode()

    scripts = [
        path for path in sorted(ROOT.rglob("*"))
        if path.is_file()
        and os.access(path, os.X_OK)
        and b"python" in shebang(path)
        and ".git" not in path.parts
        and "fixtures" not in path.parts
    ]

    assert scripts, "no production python entrypoint was found at all"
    accepted = {trusted, trusted + b" -I"}
    offenders = [str(path.relative_to(ROOT)) for path in scripts if shebang(path) not in accepted]
    assert offenders == [], f"these resolve their interpreter through PATH: {offenders}"


def test_the_trusted_interpreter_is_root_owned_and_not_caller_writable():
    """The pin is only worth what the pinned path's permissions are worth."""
    manifest = json.loads(MANIFEST.read_text())
    interpreter = Path(manifest["executables"]["python3"]["path"])
    st = interpreter.lstat()

    assert st.st_uid == 0, f"{interpreter} is not root-owned"
    assert not st.st_mode & stat.S_IWOTH, f"{interpreter} is world-writable"
