"""v16-r32 item 8: `os.write` is allowed to write less than it was given.

Three authenticated-copy loops spelled that contract as
`remaining = remaining[os.write(fd, remaining):]`, which is correct for every return value except
the one that matters: `0` slices nothing off, the loop condition is unchanged, and the process spins
forever inside a retention step holding an open descriptor and a lock. The launcher does not fail —
it stops, which is the one outcome a fail-closed design has no answer for.

The sibling loops already spell it `written = os.write(...); if written <= 0: raise` (agent-draft's
`write_private_runtime_file`, the broker's `write_all`, and six others). These tests hold every
authenticated-copy loop in production to that one contract, by name, so a new copy of the bad shape
has to walk past a failing test.
"""
import ast
import dis
import os
import runpy
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load(module_path: str) -> dict:
    return runpy.run_path(str(ROOT / module_path))


def _int_operands(func) -> set:
    """Every integer literal the function's bytecode loads, on any interpreter this suite runs on.

    Two encoding details, both of which had this reading the wrong thing:

    `LOAD_CONST` alone was version-dependent in the direction that matters. 3.14 moved small ints
    out to `LOAD_SMALL_INT`, so `if written <= 0:` — the exact shape these tests exist to require —
    stopped loading 0 as a const and every correct loop began failing. A version bump silently
    deciding a security contract is unsatisfiable is worth engineering out, so both opcodes are read
    and the question is asked of the operands rather than the encoding.

    And bools are excluded because `False == 0` and hashes alike, so a set membership test for 0 was
    satisfied by any function that merely mentioned `False` — which every one of these does. The
    check is meant to find a comparison against zero, not a boolean literal anywhere in the body.
    """
    return {
        instr.argval
        for instr in dis.get_instructions(func)
        if instr.opname in {"LOAD_CONST", "LOAD_SMALL_INT"}
        and isinstance(instr.argval, int)
        and not isinstance(instr.argval, bool)
    }


def _os_write_functions() -> list[tuple[str, str]]:
    """Derived, never typed: every production function that hands bytes to `os.write`.

    The predecessor was a hand-kept list of seven while fifteen functions ran the loop, and the
    eight it omitted were the eight nobody checked — the same failure `production_sources()` in
    test_bounded_subprocess_egress.py exists to prevent. "Every production loop", the docstring's
    claim, is a claim only a derivation can keep.
    """
    found: set[tuple[str, str]] = set()
    candidates = sorted((ROOT / "scripts").rglob("*")) + sorted((ROOT / "adapters").rglob("*.py"))
    for path in candidates:
        if not path.is_file() or path.suffix in {".sh", ".md", ".json", ".ts"}:
            continue
        try:
            tree = ast.parse(path.read_text(errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "write"
                    and isinstance(inner.func.value, ast.Name)
                    and inner.func.value.id == "os"
                ):
                    found.add((str(path.relative_to(ROOT)), node.name))
                    break
    # feed_stdin writes to a subprocess PIPE, not a retained artifact: no inode, nothing to prove.
    return sorted((m, f) for m, f in found if f != "feed_stdin")


# Every production loop that hands bytes to os.write — derived above, so "every" stays true as
# writers are added rather than being a claim someone has to remember to keep.
COMPLETE_WRITE_LOOPS = _os_write_functions()


def test_the_derivation_finds_every_copy_of_the_loop():
    """The guard on the guard: a derivation that silently found nothing would collect zero
    parametrized cases and pass, which is the shape of every vacuous enumeration this file exists to
    replace. The floor is the count when this was written; a new loop is fine, being SKIPPED is not.
    """
    assert len(COMPLETE_WRITE_LOOPS) >= 16, COMPLETE_WRITE_LOOPS
    for expected in (
        ("scripts/hermes-busdriver-deliver", "write_private_authenticated"),
        ("scripts/hermes-busdriver-deliver", "write_artifact_bytes"),
        ("scripts/hermes-busdriver-pr-grind-check", "write_private_authenticated"),
        ("adapters/pi/busdriver-fs-broker.py", "write_all"),
    ):
        assert expected in COMPLETE_WRITE_LOOPS, f"{expected} slipped out of the derivation"


@pytest.mark.parametrize("module_path,func_name", COMPLETE_WRITE_LOOPS)
def test_no_authenticated_copy_loop_can_spin_on_a_zero_write(module_path: str, func_name: str):
    """A source-level proof, because a runtime one would be a test that hangs forever if it failed.

    Reads the loop out of the function's own bytecode: a loop that consumes `os.write`'s result
    ONLY as a slice index can never terminate on 0, and no amount of calling it proves otherwise —
    the failure mode is non-termination, so the test for it must not be a call.
    """
    ns = load(module_path)
    func = ns.get(func_name)
    assert func is not None, f"{module_path} no longer defines {func_name}"
    names = {instr.argval for instr in dis.get_instructions(func)}
    assert "write" in names, f"{func_name} no longer calls os.write; retarget this test"

    operands = _int_operands(func)
    assert 0 in operands or 1 in operands, (
        f"{module_path}:{func_name} consumes os.write() without ever comparing it against zero — "
        "a zero-return write spins this loop forever"
    )


ZERO_WRITE_CALLABLE = [
    ("scripts/opencode/run-opencode-busdriver-draft", "write_private_file"),
    ("scripts/hermes-busdriver-gate", "write_baseline_file"),
]


@pytest.mark.parametrize("module_path,func_name", ZERO_WRITE_CALLABLE)
def test_a_zero_write_fails_closed_rather_than_spinning(module_path: str, func_name: str, monkeypatch, tmp_path: Path):
    """The behavioural half: a kernel that accepts nothing must produce a refusal, not a hang.

    `os.write` returning 0 is what a full filesystem or a stalled device does. pytest cannot time
    out a spin, so the counter below converts "would have hung" into a failed assertion — reaching
    the `pytest.raises` at all is the pass.
    """
    ns = load(module_path)
    calls: list[int] = []

    def refuses_everything(fd, data):
        calls.append(len(data))
        if len(calls) > 4:  # a spin is unbounded; four identical refusals is already the bug
            raise AssertionError(f"{func_name} looped on a zero-return write instead of failing closed")
        return 0

    monkeypatch.setattr(os, "write", refuses_everything)
    with pytest.raises((OSError, RuntimeError, SystemExit)):
        if func_name == "write_private_file":
            ns[func_name](tmp_path / "private", "payload.json", b"x" * 4096)
        else:
            ns[func_name](tmp_path / "baseline.json", b"x" * 4096)

    assert calls, "os.write was never reached; the test proves nothing"


@pytest.mark.parametrize("module_path,func_name", ZERO_WRITE_CALLABLE)
def test_a_short_write_still_lands_every_byte(module_path: str, func_name: str, monkeypatch, tmp_path: Path):
    """The other half: refusing 0 must not become refusing to loop at all.

    A one-byte-at-a-time kernel is legal, and the complete-write guarantee is that the payload still
    arrives whole. This is what stops a `written != len(data): raise` "fix" from passing the test
    above while quietly breaking every large retention.
    """
    ns = load(module_path)
    real_write = os.write
    payload = bytes(range(256)) * 16

    def one_byte_at_a_time(fd, data):
        return real_write(fd, bytes(data[:1]))

    monkeypatch.setattr(os, "write", one_byte_at_a_time)
    if func_name == "write_private_file":
        target = tmp_path / "private"
        ns[func_name](target, "payload.bin", payload)
        landed = (target / "payload.bin").read_bytes()
    else:
        target = tmp_path / "baseline.json"
        ns[func_name](target, payload)
        landed = target.read_bytes()
    monkeypatch.setattr(os, "write", real_write)

    assert landed == payload, "a short write did not land every byte of the retained payload"


def test_every_production_os_write_is_a_guarded_loop():
    """The enumeration itself: no production file may reintroduce either bad shape, anywhere.

    A grep, deliberately. The per-function tests above cannot cover a function nobody has written
    yet, and both bugs here arrived by someone copying a loop that looked fine.
    """
    offenders = []
    candidates = sorted((ROOT / "scripts").rglob("*")) + sorted((ROOT / "adapters").rglob("*.py"))
    for path in candidates:
        if not path.is_file() or path.suffix in {".sh", ".md", ".json", ".ts"}:
            continue
        for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            stripped = line.strip()
            if "os.write(" not in stripped or stripped.startswith("#"):
                continue
            where = f"{path.relative_to(ROOT)}:{number}"
            if "[os.write(" in stripped:
                offenders.append(f"{where}: slice-index loop spins forever on a zero write")
            elif not stripped.startswith("written = os.write("):
                offenders.append(f"{where}: bare os.write() drops bytes on a short write")

    assert offenders == [], "unguarded os.write():\n" + "\n".join(offenders)


# --- v16-r33 F: an authenticated copy proves the FILE holds what was authenticated ---


# All six scripts that restate `write_private_authenticated`, not the two that happened to be
# listed. They import nothing and never each other — the copies are duplicated BY DESIGN, so a test
# naming all of them is the only thing that can hold them to one contract. Naming a subset is how
# pr-grind-check drifted into implementing half of it while passing every test here.
PRIVATE_AUTHENTICATED_WRITERS = [
    "scripts/hermes-busdriver-deliver",
    "scripts/hermes-busdriver-pr-grind-check",
    "scripts/hermes-busdriver-delivery-status",
    "scripts/hermes-busdriver-gate",
    "scripts/hermes-busdriver-lock",
    "scripts/hermes-busdriver-litmus-status",
]


def test_every_script_restating_the_primitive_is_enumerated():
    """The guard on the guard, again: the list above must not fall behind the tree."""
    defining = sorted(
        str(path.relative_to(ROOT))
        for path in sorted((ROOT / "scripts").rglob("*"))
        if path.is_file()
        and path.suffix not in {".sh", ".md", ".json", ".ts"}
        and "\ndef write_private_authenticated(" in path.read_text(errors="replace")
    )
    assert defining == sorted(PRIVATE_AUTHENTICATED_WRITERS), (
        "scripts defining write_private_authenticated that this file does not hold to the contract:\n"
        + "\n".join(sorted(set(defining) - set(PRIVATE_AUTHENTICATED_WRITERS)))
    )


@pytest.mark.parametrize("module_path", PRIVATE_AUTHENTICATED_WRITERS)
def test_a_zero_write_in_an_authenticated_copy_fails_closed(module_path: str, monkeypatch, tmp_path: Path):
    """A kernel that accepts nothing must produce a refusal, not a spin and not a truncated file."""
    ns = load(module_path)
    monkeypatch.setitem(ns["write_private_authenticated"].__globals__, "os", _ZeroWriteOS(os))

    with pytest.raises(OSError) as exc:
        ns["write_private_authenticated"](tmp_path / "copy", b"authenticated", 0o500)

    assert "short_write" in str(exc.value)


@pytest.mark.parametrize("module_path", PRIVATE_AUTHENTICATED_WRITERS)
def test_an_authenticated_copy_replaced_after_the_write_fails_closed(module_path: str, monkeypatch, tmp_path: Path):
    """The window the closing re-digest exists for.

    The bytes were authenticated in memory. Between the write and the exec, the file can be replaced
    — same name, same size, different content — and every check that reads metadata still agrees.
    Re-reading the DESCRIPTOR is the only thing that can tell those apart, and this proves it does.
    """
    ns = load(module_path)
    real_fsync = os.fsync

    def fsync_then_replace(fd: int) -> None:
        real_fsync(fd)
        os.pwrite(fd, b"X" * len("authenticated"), 0)  # same size, every byte different

    monkeypatch.setattr(os, "fsync", fsync_then_replace)
    target = tmp_path / "copy"

    with pytest.raises(OSError) as exc:
        ns["write_private_authenticated"](target, b"authenticated", 0o500)

    assert "private_copy_integrity_failed" in str(exc.value)
    assert not target.exists(), "a copy that failed its own integrity check was left on disk"


@pytest.mark.parametrize("module_path", PRIVATE_AUTHENTICATED_WRITERS)
def test_an_authenticated_copy_renamed_away_from_its_name_fails_closed(module_path: str, monkeypatch, tmp_path: Path):
    """The half no descriptor can see: our inode is intact, but the NAME now reaches someone else's.

    The re-digest above proves OUR bytes survived. It says nothing about where `target` points by the
    time the caller EXECs it, and the caller execs the name. So this is the other direction, and it
    needs a sharper adversary than a rename-over: a plain `rename(attacker, target)` unlinks our
    inode and drops its `st_nlink` to 0, which the metadata check already catches. Moving our file
    ASIDE first keeps `st_nlink == 1`, so size, mode, owner, type, link count and the digest all
    still describe our inode exactly — every check a descriptor can make passes, and the name still
    belongs to the attacker. Only re-resolving the name against the created inode can tell.

    The second assertion is the same clause's other half: the cleanup must not delete the attacker's
    file. Unlinking whatever now holds the name is a second bug wearing the first one's cleanup.
    """
    ns = load(module_path)
    real_fsync = os.fsync
    target = tmp_path / "copy"
    attacker = tmp_path / "attacker"
    attacker.write_bytes(b"attacker-payload")
    moved_aside = tmp_path / "moved-aside"
    swapped: list[bool] = []

    def fsync_then_swap_the_name(fd: int) -> None:
        real_fsync(fd)
        if swapped:
            return
        swapped.append(True)
        os.rename(target, moved_aside)  # our inode keeps its one link, just under another name
        os.rename(attacker, target)     # the name the caller will exec now reaches attacker bytes

    monkeypatch.setattr(os, "fsync", fsync_then_swap_the_name)

    with pytest.raises(OSError) as exc:
        ns["write_private_authenticated"](target, b"authenticated", 0o500)

    assert swapped, "the swap never happened; the test proves nothing"
    assert "private_copy_integrity_failed" in str(exc.value)
    assert target.read_bytes() == b"attacker-payload", "cleanup deleted the attacker's replacement"


@pytest.mark.parametrize("module_path", PRIVATE_AUTHENTICATED_WRITERS)
def test_an_untouched_authenticated_copy_lands_complete_and_private(module_path: str, tmp_path: Path):
    ns = load(module_path)
    target = tmp_path / "copy"

    ns["write_private_authenticated"](target, b"authenticated", 0o500)

    assert target.read_bytes() == b"authenticated"
    assert target.stat().st_mode & 0o777 == 0o500


def test_the_finalization_readiness_retained_helper_revalidates_after_writing(monkeypatch, tmp_path: Path):
    ns = load("scripts/hermes-busdriver-finalization-readiness")
    real_fsync = os.fsync

    def fsync_then_replace(fd: int) -> None:
        real_fsync(fd)
        os.pwrite(fd, b"X" * len("helper-bytes"), 0)

    monkeypatch.setattr(os, "fsync", fsync_then_replace)
    target = tmp_path / "helper"

    with pytest.raises(OSError) as exc:
        ns["_write_exclusive"](target, b"helper-bytes", 0o500)

    assert "retained_helper_replaced_after_write" in str(exc.value)
    assert not target.exists()


def test_no_production_authenticated_copy_still_uses_write_bytes():
    """The enumeration: `Path.write_bytes()` cannot come back at the edges that then EXEC the file."""
    offenders = []
    for path in sorted((ROOT / "scripts").rglob("*")):
        if not path.is_file() or path.suffix in {".sh", ".md", ".json", ".ts"}:
            continue
        for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            if ".write_bytes(" in line and not line.lstrip().startswith("#") and "`Path.write_bytes()`" not in line:
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")

    assert offenders == [], "\n".join(offenders)


class _ZeroWriteOS:
    """`os` with a write that always accepts nothing. Everything else is the real module."""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    def write(self, fd, data):  # noqa: A003 - mirrors os.write
        return 0
