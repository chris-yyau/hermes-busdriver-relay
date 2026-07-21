"""v16-r32 item 6: a writer that REPORTS success has to have PROVED it.

Every writer covered here hands bytes to `os.write` and then tells its caller it succeeded. Four
gaps sit between those two facts, and none of them is hypothetical:

  * `os.write` may accept FEWER bytes than it was given, so one call is a silent truncation;
  * it may accept ZERO, which a bare call turns into a lie and a slice-index loop into a hang;
  * the bytes may still be in the page cache when a child is launched to read them, so "written"
    and "durable" are not the same claim;
  * and the file can be replaced between the last write and the close — same name, same size,
    different content — so "we wrote the authenticated bytes" and "this file holds them" stay
    separate claims. Several of these files are then EXECUTED, which is what makes the second
    claim the only one worth having.

r32 item 8 (`test_complete_write_parity.py`) proved the LOOP terminates. This file proves the
RESULT — that the payload landed whole, reached the disk, and still identifies the destination the
caller authenticated. The enumeration at the bottom is what stops the next writer being added
without the primitive.
"""
from __future__ import annotations

import ast
import hashlib
import os
import runpy
import stat
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]

# Byte 0 is a known 'A' so the corruption injected below ('\xff') is always a real difference.
PAYLOAD = b"A" + bytes(range(256)) * 24


def load(module_path: str) -> dict:
    return runpy.run_path(str(ROOT / module_path))


# --- the primitive: one complete-write + fsync + close-verify per script -------------------------
#
# These scripts import nothing but the stdlib and never each other -- they are standalone
# executables, some launched `-I` -- so the primitive is duplicated per script BY DESIGN, and the
# only thing that can hold the copies to one contract is a test that names all of them.
#
# (module, function, integrity-failure token). Signature is uniformly (path, data, mode).
DIRECT_WRITERS = [
    ("scripts/hermes-busdriver-agent-draft", "write_private_runtime_file", "private_runtime_integrity_failed"),
    ("scripts/pi/run-pi-busdriver-draft", "write_private_runtime_file", "private_runtime_integrity_failed"),
    ("scripts/hermes-busdriver-relay-brief", "_write_exclusive", "retained_helper_replaced_after_write"),
    ("scripts/hermes-busdriver-pr-grind-loop", "_write_exclusive", "retained_helper_replaced_after_write"),
    ("scripts/hermes-busdriver-finalization-readiness", "_write_exclusive", "retained_helper_replaced_after_write"),
    ("scripts/hermes-busdriver-deliver", "write_private_authenticated", "private_copy_integrity_failed"),
    ("scripts/hermes-busdriver-pr-grind-check", "write_private_authenticated", "private_copy_integrity_failed"),
    ("scripts/hermes-busdriver-delivery-status", "write_private_authenticated", "private_copy_integrity_failed"),
    ("scripts/hermes-busdriver-gate", "write_private_authenticated", "private_copy_integrity_failed"),
    ("scripts/hermes-busdriver-lock", "write_private_authenticated", "private_copy_integrity_failed"),
    ("scripts/hermes-busdriver-litmus-status", "write_private_authenticated", "private_copy_integrity_failed"),
]

DIRECT_IDS = [f"{Path(m).name}:{f}" for m, f, _ in DIRECT_WRITERS]


@pytest.mark.parametrize("module_path,func_name,integrity_token", DIRECT_WRITERS, ids=DIRECT_IDS)
def test_a_short_write_still_lands_the_exact_payload(module_path, func_name, integrity_token, monkeypatch, tmp_path):
    """A one-byte-at-a-time kernel is legal. The complete-write guarantee is that the file is whole.

    This is what stops a `written != len(data): raise` "fix" from satisfying the zero-write test
    below while quietly breaking every large payload.
    """
    ns = load(module_path)
    real_write = os.write
    monkeypatch.setattr(os, "write", lambda fd, data: real_write(fd, bytes(memoryview(data)[:1])))

    target = tmp_path / "artifact"
    ns[func_name](target, PAYLOAD, 0o500)

    monkeypatch.setattr(os, "write", real_write)
    landed = target.read_bytes()
    assert landed == PAYLOAD, f"{func_name} lost bytes under a short-writing kernel"
    assert hashlib.sha256(landed).hexdigest() == hashlib.sha256(PAYLOAD).hexdigest()


@pytest.mark.parametrize("module_path,func_name,integrity_token", DIRECT_WRITERS, ids=DIRECT_IDS)
def test_a_zero_write_fails_closed_and_leaves_no_trusted_artifact(module_path, func_name, integrity_token, monkeypatch, tmp_path):
    """A kernel that accepts nothing must produce a refusal -- not a hang, not a truncated file.

    The `leaves nothing` half is the one with teeth: several of these paths write a file the very
    next step EXECUTES, so a half-written artifact left on disk after a failure is worse than the
    failure.
    """
    ns = load(module_path)
    calls: list[int] = []

    def refuses_everything(fd, data):
        calls.append(len(data))
        if len(calls) > 8:  # a spin is unbounded; eight identical refusals is already the bug
            raise AssertionError(f"{func_name} looped on a zero-return write instead of failing closed")
        return 0

    monkeypatch.setattr(os, "write", refuses_everything)
    target = tmp_path / "artifact"
    with pytest.raises((OSError, RuntimeError, SystemExit)) as exc:
        ns[func_name](target, PAYLOAD, 0o500)

    assert calls, "os.write was never reached; this test proves nothing"
    assert "short_write" in str(exc.value)
    assert not target.exists(), f"{func_name} left a truncated trusted artifact behind after failing"


@pytest.mark.parametrize("module_path,func_name,integrity_token", DIRECT_WRITERS, ids=DIRECT_IDS)
def test_a_replacement_after_the_final_write_is_caught(module_path, func_name, integrity_token, monkeypatch, tmp_path):
    """The bytes were authenticated in MEMORY. This proves the FILE is re-checked before success."""
    ns = load(module_path)
    real_write = os.write
    state = {"written": 0, "corrupted": False}

    def write_then_corrupt_once_complete(fd, data):
        count = real_write(fd, data)
        state["written"] += count
        if state["written"] >= len(PAYLOAD) and not state["corrupted"]:
            state["corrupted"] = True
            os.pwrite(fd, b"\xff", 0)  # same size, byte 0 now differs
        return count

    monkeypatch.setattr(os, "write", write_then_corrupt_once_complete)
    target = tmp_path / "artifact"
    with pytest.raises((OSError, RuntimeError, SystemExit)) as exc:
        ns[func_name](target, PAYLOAD, 0o500)

    monkeypatch.setattr(os, "write", real_write)
    assert state["corrupted"], "the corruption never fired; this test proves nothing"
    assert integrity_token in str(exc.value)
    assert not target.exists(), "an artifact that failed its own integrity check was left on disk"


@pytest.mark.parametrize("module_path,func_name,integrity_token", DIRECT_WRITERS, ids=DIRECT_IDS)
def test_a_replacement_after_fsync_is_caught(module_path, func_name, integrity_token, monkeypatch, tmp_path):
    """The same window, one step later: durable is not the same as unchanged."""
    ns = load(module_path)
    real_fsync = os.fsync
    fired: list[int] = []

    def fsync_then_corrupt(fd):
        real_fsync(fd)
        if stat.S_ISREG(os.fstat(fd).st_mode):
            os.pwrite(fd, b"\xff", 0)
            fired.append(fd)

    monkeypatch.setattr(os, "fsync", fsync_then_corrupt)
    target = tmp_path / "artifact"
    with pytest.raises((OSError, RuntimeError, SystemExit)) as exc:
        ns[func_name](target, PAYLOAD, 0o500)

    monkeypatch.setattr(os, "fsync", real_fsync)
    assert fired, "fsync never reached a regular file; this test proves nothing"
    assert integrity_token in str(exc.value)
    assert not target.exists(), "an artifact that failed its own integrity check was left on disk"


@pytest.mark.parametrize("module_path,func_name,integrity_token", DIRECT_WRITERS, ids=DIRECT_IDS)
def test_fsync_of_the_written_descriptor_precedes_success(module_path, func_name, integrity_token, monkeypatch, tmp_path):
    """Without a flush the child launched to read these bytes may not find them there yet."""
    ns = load(module_path)
    real_fsync = os.fsync
    synced_regular_file: list[bool] = []

    def record(fd):
        synced_regular_file.append(stat.S_ISREG(os.fstat(fd).st_mode))
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", record)
    ns[func_name](tmp_path / "artifact", PAYLOAD, 0o500)

    assert any(synced_regular_file), f"{func_name} reported success without fsync of the file it wrote"


@pytest.mark.parametrize("module_path,func_name,integrity_token", DIRECT_WRITERS, ids=DIRECT_IDS)
def test_a_successful_write_is_private_and_complete(module_path, func_name, integrity_token, tmp_path):
    """The no-follow / private-mode / single-link guarantees survive the hardening."""
    ns = load(module_path)
    target = tmp_path / "artifact"

    ns[func_name](target, PAYLOAD, 0o500)

    st = target.lstat()
    assert target.read_bytes() == PAYLOAD
    assert stat.S_IMODE(st.st_mode) == 0o500, "private mode was not applied to the inode written"
    assert st.st_nlink == 1, "a trusted artifact must not be reachable through a second name"
    assert st.st_uid == os.geteuid()


@pytest.mark.parametrize("module_path,func_name,integrity_token", DIRECT_WRITERS, ids=DIRECT_IDS)
def test_an_existing_name_is_never_reused(module_path, func_name, integrity_token, tmp_path):
    """O_EXCL: the primitive must refuse a name something else prepared for it."""
    ns = load(module_path)
    target = tmp_path / "artifact"
    target.write_bytes(b"squatted")

    with pytest.raises((OSError, RuntimeError, SystemExit)):
        ns[func_name](target, PAYLOAD, 0o500)

    assert target.read_bytes() == b"squatted", "the primitive wrote through a pre-existing name"


@pytest.mark.parametrize("module_path,func_name,integrity_token", DIRECT_WRITERS, ids=DIRECT_IDS)
def test_a_rename_away_from_the_name_is_caught_and_the_replacement_survives(
    module_path, func_name, integrity_token, monkeypatch, tmp_path,
):
    """The direction no descriptor can see -- and the cleanup that must not compound it.

    Every check these writers make reads the fd: type, owner, link count, size, mode, and a closing
    digest. That is the right instrument for "are OUR bytes intact" and the wrong one for "does the
    name still reach them", and the caller EXECUTES the name.

    It takes a sharper adversary than a rename-over to show the difference. `rename(attacker, target)`
    unlinks our inode and drops st_nlink to 0, which the metadata check already catches. Moving our
    file ASIDE first keeps st_nlink == 1 -- so every descriptor-visible field still describes our
    inode exactly, the digest still clears, and `target` is the attacker's file. Only re-resolving
    the name against the created inode can tell.

    The second assertion is the other half of the same clause: cleanup must leave that file alone.
    Unlinking whatever now holds the name deletes the attacker's plant rather than our residue --
    a second bug wearing the first one's cleanup.
    """
    ns = load(module_path)
    real_fsync = os.fsync
    target = tmp_path / "artifact.bin"
    attacker = tmp_path / "attacker.bin"
    attacker.write_bytes(b"attacker-payload")
    swapped: list[bool] = []

    def fsync_then_swap_the_name(fd: int) -> None:
        real_fsync(fd)
        if swapped:
            return
        swapped.append(True)
        os.rename(target, tmp_path / "moved-aside.bin")  # our inode keeps its one link
        os.rename(attacker, target)                      # the name now reaches attacker bytes

    monkeypatch.setattr(os, "fsync", fsync_then_swap_the_name)

    with pytest.raises((OSError, RuntimeError, SystemExit)) as exc:
        ns[func_name](target, PAYLOAD, 0o500)

    assert swapped, "the swap never happened; this test proves nothing"
    assert integrity_token in str(exc.value)
    assert target.read_bytes() == b"attacker-payload", "cleanup deleted the attacker's replacement"


# --- atomic-replacement writers: rename, then fsync the PARENT ----------------------------------
#
# A rename is only durable once the DIRECTORY entry is. Without the parent fsync, a crash can leave
# the parent still pointing at the temp name -- or at nothing -- with the file itself intact.


def _invoke_rename_writer(ns: dict, func_name: str, tmp_path: Path, payload: bytes) -> Path:
    if func_name == "write_private_file":  # opencode: (target_dir, target_name, payload, mode)
        ns[func_name](tmp_path / "private", "artifact.bin", payload, 0o600)
        return tmp_path / "private" / "artifact.bin"
    if func_name == "write_baseline_file":  # gate: (path, payload, mode=0o600)
        ns[func_name](tmp_path / "baseline.json", payload)
        return tmp_path / "baseline.json"
    if func_name == "copy_regular_file_nofollow":  # pi: (source, target_dir, target_name)
        source = tmp_path / "source.bin"
        source.write_bytes(payload)
        ns[func_name](source, tmp_path / "private", "artifact.bin")
        return tmp_path / "private" / "artifact.bin"
    if func_name == "write_artifact_bytes":  # deliver: (payload, dir_fd, tmp_name, name)
        dir_fd = os.open(tmp_path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            ns[func_name](payload, dir_fd, ".artifact.bin.tmp", "artifact.bin")
        finally:
            os.close(dir_fd)
        return tmp_path / "artifact.bin"
    raise AssertionError(f"no invoker for {func_name}")


RENAME_WRITERS = [
    ("scripts/opencode/run-opencode-busdriver-draft", "write_private_file"),
    ("scripts/hermes-busdriver-gate", "write_baseline_file"),
    ("scripts/pi/run-pi-busdriver-draft", "copy_regular_file_nofollow"),
    # The delivery result artifact. An INDEPENDENT writer, not a wrapper: the private-copy primitive
    # creates its final name with O_EXCL and never renames, and a result artifact must replace what
    # the previous run left. It is enumerated here because it restates the contract rather than
    # delegating it -- and because it spelled its write `handle.write`, which is invisible to an
    # `os.write`-shaped enumeration and so was covered by nothing at all.
    ("scripts/hermes-busdriver-deliver", "write_artifact_bytes"),
]

RENAME_IDS = [f"{Path(m).name}:{f}" for m, f in RENAME_WRITERS]


@pytest.mark.parametrize("module_path,func_name", RENAME_WRITERS, ids=RENAME_IDS)
def test_the_parent_directory_is_fsynced_after_the_atomic_rename(module_path, func_name, monkeypatch, tmp_path):
    ns = load(module_path)
    real_fsync, real_replace = os.fsync, os.replace
    events: list[str] = []

    def record_fsync(fd):
        try:
            kind = "fsync:dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "fsync:file"
        except OSError:
            kind = "fsync:file"
        events.append(kind)
        return real_fsync(fd)

    def record_replace(src, dst, **kwargs):
        result = real_replace(src, dst, **kwargs)
        events.append("replace")
        return result

    monkeypatch.setattr(os, "fsync", record_fsync)
    monkeypatch.setattr(os, "replace", record_replace)
    _invoke_rename_writer(ns, func_name, tmp_path, PAYLOAD)

    assert "replace" in events, f"{func_name} no longer renames; retarget this test"
    after_rename = events[len(events) - 1 - events[::-1].index("replace"):]
    assert "fsync:dir" in after_rename, (
        f"{func_name} renamed into place without fsyncing the parent directory -- the rename is "
        f"not durable. Order seen: {events}"
    )


@pytest.mark.parametrize("module_path,func_name", RENAME_WRITERS, ids=RENAME_IDS)
def test_the_renamed_destination_is_revalidated_before_success(module_path, func_name, monkeypatch, tmp_path):
    """A rename resolves the destination NAME a second time. Something else may own it by then."""
    ns = load(module_path)
    real_replace = os.replace
    fired: list[str] = []

    def replace_then_swap(src, dst, **kwargs):
        result = real_replace(src, dst, **kwargs)
        fired.append("swapped")
        # The destination now holds the authenticated bytes. Overwrite it, through the same name,
        # with a same-length impostor -- what a racing writer with access to the parent can do.
        fd = os.open(dst, os.O_WRONLY, dir_fd=kwargs.get("dst_dir_fd"))
        try:
            os.pwrite(fd, b"\xff", 0)
        finally:
            os.close(fd)
        return result

    monkeypatch.setattr(os, "replace", replace_then_swap)
    with pytest.raises((OSError, RuntimeError, SystemExit)):
        _invoke_rename_writer(ns, func_name, tmp_path, PAYLOAD)

    assert fired, "the rename never happened; this test proves nothing"


@pytest.mark.parametrize("module_path,func_name", RENAME_WRITERS, ids=RENAME_IDS)
def test_a_short_write_still_lands_the_exact_payload_through_a_rename(module_path, func_name, monkeypatch, tmp_path):
    ns = load(module_path)
    real_write = os.write
    monkeypatch.setattr(os, "write", lambda fd, data: real_write(fd, bytes(memoryview(data)[:1])))

    landed_at = _invoke_rename_writer(ns, func_name, tmp_path, PAYLOAD)

    monkeypatch.setattr(os, "write", real_write)
    assert landed_at.read_bytes() == PAYLOAD


@pytest.mark.parametrize("module_path,func_name", RENAME_WRITERS, ids=RENAME_IDS)
def test_a_zero_write_through_a_rename_publishes_nothing(module_path, func_name, monkeypatch, tmp_path):
    """The destination name must never appear at all -- a rename publishes atomically or not."""
    ns = load(module_path)
    calls: list[int] = []

    def refuses_everything(fd, data):
        calls.append(len(data))
        if len(calls) > 8:
            raise AssertionError(f"{func_name} looped on a zero-return write")
        return 0

    monkeypatch.setattr(os, "write", refuses_everything)
    with pytest.raises((OSError, RuntimeError, SystemExit)):
        _invoke_rename_writer(ns, func_name, tmp_path, PAYLOAD)

    assert calls, "os.write was never reached; this test proves nothing"
    published = [p for p in tmp_path.rglob("*") if p.is_file() and p.name != "source.bin"]
    assert published == [], f"{func_name} published a truncated artifact: {published}"


# --- the enumeration: no future writer may bypass the primitive ----------------------------------


def _production_sources() -> list[Path]:
    """Every production file worth parsing. Extension-less executables, so the suffix filter is a
    denylist of the things that are definitely not Python rather than an allowlist of `.py`."""
    candidates = sorted((ROOT / "scripts").rglob("*")) + sorted((ROOT / "adapters").rglob("*.py"))
    return [p for p in candidates if p.is_file() and p.suffix not in {".sh", ".md", ".json", ".ts"}]


def _enclosing_lookup(tree: ast.AST):
    """line -> innermost enclosing function name, or `<module>`."""
    scopes = [
        (node.lineno, node.end_lineno, node.name)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    def enclosing(line: int) -> str:
        best = None
        for start, end, name in scopes:
            if start <= line <= end and (best is None or start > best[0]):
                best = (start, end, name)
        return best[2] if best else "<module>"

    return enclosing


def _call_sites(attr_of: str, attrs: set[str]) -> set[tuple[str, str]]:
    """Every (module, enclosing function) that calls `<attr_of>.<attr>` across production source."""
    found: set[tuple[str, str]] = set()
    for path in _production_sources():
        try:
            tree = ast.parse(path.read_text(errors="replace"))
        except SyntaxError:
            continue
        enclosing = _enclosing_lookup(tree)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            func = node.func
            if func.attr not in attrs:
                continue
            if attr_of and not (isinstance(func.value, ast.Name) and func.value.id == attr_of):
                continue
            found.add((str(path.relative_to(ROOT)), enclosing(node.lineno)))
    return found


# Every function in production allowed to call `os.write`. A new writer that is not one of the
# primitives above has to be added HERE -- which is the point: the diff that adds it cannot be
# reviewed without someone deciding whether it proves what it wrote.
SANCTIONED_OS_WRITE_SITES = {
    # The primitives. One per script, each holding the full contract the tests above assert.
    ("scripts/hermes-busdriver-agent-draft", "write_private_runtime_file"),
    ("scripts/pi/run-pi-busdriver-draft", "write_private_runtime_file"),
    ("scripts/hermes-busdriver-relay-brief", "_write_exclusive"),
    ("scripts/hermes-busdriver-pr-grind-loop", "_write_exclusive"),
    ("scripts/hermes-busdriver-finalization-readiness", "_write_exclusive"),
    ("scripts/hermes-busdriver-deliver", "write_private_authenticated"),
    ("scripts/hermes-busdriver-pr-grind-check", "write_private_authenticated"),
    ("scripts/hermes-busdriver-delivery-status", "write_private_authenticated"),
    ("scripts/hermes-busdriver-gate", "write_private_authenticated"),
    ("scripts/hermes-busdriver-lock", "write_private_authenticated"),
    ("scripts/hermes-busdriver-litmus-status", "write_private_authenticated"),
    # Atomic-replacement writers: same loop, then rename + parent fsync + reopen-revalidate.
    ("scripts/opencode/run-opencode-busdriver-draft", "write_private_file"),
    ("scripts/hermes-busdriver-gate", "write_baseline_file"),
    ("scripts/pi/run-pi-busdriver-draft", "copy_regular_file_nofollow"),
    ("scripts/hermes-busdriver-deliver", "write_artifact_bytes"),
    # Not a file: the broker's own complete-write primitive, covered by test_pi_fs_broker.py.
    ("adapters/pi/busdriver-fs-broker.py", "write_all"),
}


def test_every_production_os_write_lives_in_a_sanctioned_primitive():
    """A grep the per-function tests above cannot do: they cannot cover a writer nobody wrote yet.

    Both bugs this file exists for arrived the same way -- someone copied a loop that looked fine
    into a new function. A new function is exactly what this notices.
    """
    found = _call_sites("os", {"write"})
    # feed_stdin writes to a subprocess PIPE, not a trusted artifact; it has no file to prove.
    found = {(m, f) for m, f in found if f != "feed_stdin"}

    unsanctioned = found - SANCTIONED_OS_WRITE_SITES
    assert unsanctioned == set(), (
        "os.write() outside a sanctioned complete-write primitive -- these bypass every guarantee "
        f"in this file:\n" + "\n".join(f"  {m}:{f}()" for m, f in sorted(unsanctioned))
    )

    departed = SANCTIONED_OS_WRITE_SITES - found
    assert departed == set(), (
        "sanctioned primitives that no longer call os.write -- retarget or drop them:\n"
        + "\n".join(f"  {m}:{f}()" for m, f in sorted(departed))
    )


# `Path.write_text()` / `Path.write_bytes()` are a single unchecked high-level write: no O_EXCL, no
# no-follow, no fsync, no close-verify.
#
# This is an ALLOWLIST, and the polarity is the whole point. The predecessor was a denylist filtered
# with `found & BANNED`, and an intersection with a hand-written set is a subset of that set: it can
# only ever re-report a site someone already enumerated, so the one thing it was written to do --
# notice the NEXT writer -- was the one thing it could not do. It had also gone stale unnoticed, its
# single entry (`agent-draft:build_guard_bin`) having migrated to the primitive long before, leaving
# the two sets disjoint and the assertion reduced to `set() == set()`.
#
# Subtraction inverts that: anything found and not listed FAILS, so a new high-level write anywhere
# under scripts/ or adapters/ has to be triaged into this list by a human in the diff that adds it.
HIGH_LEVEL_WRITE_ALLOWED_IN = {
    # Run-directory bookkeeping in the draft launchers' `main`: prompts, command echoes and stdout
    # captures. Nothing re-reads these as authenticated bytes and nothing executes them -- the
    # `git`/`gh` shims that ARE executed moved to `write_private_runtime_file`, which is what
    # emptied the old denylist. Production dispatch here is fixed `policy_blocked` besides.
    ("scripts/hermes-busdriver-agent-draft", "main"),
    ("scripts/opencode/run-opencode-busdriver-draft", "main"),
    ("scripts/pi/run-pi-busdriver-draft", "main"),
}


def test_no_trusted_artifact_is_written_by_an_unchecked_high_level_write():
    found = _call_sites("", {"write_text", "write_bytes"})

    offenders = found - HIGH_LEVEL_WRITE_ALLOWED_IN
    assert offenders == set(), (
        "Path.write_text()/write_bytes() writing bytes a later step may trust -- route these through "
        "the script's complete-write primitive, or triage them into HIGH_LEVEL_WRITE_ALLOWED_IN:\n"
        + "\n".join(f"  {m}:{f}()" for m, f in sorted(offenders))
    )

    departed = HIGH_LEVEL_WRITE_ALLOWED_IN - found
    assert departed == set(), (
        "allowlisted high-level writes that no longer exist -- drop them, or the list rots into the "
        "disjoint set that made this test vacuous:\n" + "\n".join(f"  {m}:{f}()" for m, f in sorted(departed))
    )


def _handle_write_sites() -> set[tuple[str, str]]:
    """Every (module, function) calling `<expr>.write(...)` on something that is not `os`.

    The OTHER spelling of a write, and the one `write_artifact_bytes` hid behind: a buffered file
    object's `.write` LOOKS like a complete write, is not one by contract, and is invisible to the
    receiver-keyed `os.write` scan above -- `_call_sites("os", {"write"})` requires the receiver to
    be the bare name `os`, so `handle.write(payload)` matched nothing and the function sat in no
    enumeration at all. That is not a hypothetical: it is how the delivery artifact writer came to
    make four unproven claims while every write test in this file passed.

    Streams are excluded, and only streams: `sys.stdout`/`sys.stderr` and a Popen's `.stdin` have no
    inode to reopen, no mode to check and no later step that trusts them as bytes on disk.
    """
    found: set[tuple[str, str]] = set()
    for path in _production_sources():
        try:
            tree = ast.parse(path.read_text(errors="replace"))
        except SyntaxError:
            continue
        enclosing = _enclosing_lookup(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "write":
                continue
            receiver = ast.unparse(node.func.value)
            if receiver == "os":
                continue  # SANCTIONED_OS_WRITE_SITES owns this spelling
            if receiver.startswith(("sys.stdout", "sys.stderr")) or receiver.endswith(".stdin"):
                continue  # a stream, not an artifact
            found.add((str(path.relative_to(ROOT)), enclosing(node.lineno)))
    return found


# Independent writers that publish through a buffered handle rather than the `os.write` loop, and
# are deliberately exempt from routing through a complete-write primitive.
#
# EMPTY as of v16-r34c, and that is the finding rather than a formality. The two entries were
# `lock::publish_lock` and `agent-draft::persist_final_report`, listed on the reasoning that neither
# is executed and neither is read back as authenticated bytes. Both were hardened instead, because
# the reasoning did not survive contact with what they publish: `publish_lock` is single-flight's
# whole record, and a crash between its byte fsync and its rename into an unsynced parent leaves a
# lock whose bytes are on disk and whose NAME is not -- which reads as "nobody holds it", and
# single-flight is precisely the invariant that cannot survive being taken twice.
# `persist_final_report` is a run's only durable evidence of which authority flags stayed false.
# Both now reuse their script's complete-write primitive, so the exemption describes nothing.
#
# The set stays as the named place to triage the next one; the `departed` assertion below is what
# stopped it from rotting into the disjoint set that makes this kind of test vacuous.
HANDLE_WRITE_ALLOWED_IN: set[tuple[str, str]] = set()


def test_no_trusted_artifact_is_written_by_an_unchecked_handle_write():
    found = _handle_write_sites()

    offenders = found - HANDLE_WRITE_ALLOWED_IN
    assert offenders == set(), (
        "handle.write() publishing bytes a later step may trust -- route these through the script's "
        "complete-write primitive, or triage them into HANDLE_WRITE_ALLOWED_IN:\n"
        + "\n".join(f"  {m}:{f}()" for m, f in sorted(offenders))
    )

    departed = HANDLE_WRITE_ALLOWED_IN - found
    assert departed == set(), (
        "allowlisted handle writes that no longer exist -- drop them:\n"
        + "\n".join(f"  {m}:{f}()" for m, f in sorted(departed))
    )
