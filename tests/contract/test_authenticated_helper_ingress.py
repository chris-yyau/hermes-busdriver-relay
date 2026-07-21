"""v16-r34 item 3: a pinned-helper reader must not let the FILE choose what it costs.

Every reader here opens a pinned helper, reads it, and digests the result against a constant. The
digest is the whole authentication — and it runs last, after the bytes are already resident. So a
reader that loops `os.read(fd, 1MiB)` until EOF has already spent whatever the file asked for by the
time it discovers the file was never trusted. The bound has to precede the memory, not follow it.

The second half is the same argument the writers make in the other direction. These readers compared
identity at OPEN and never again, so everything between the open and the digest was unproven: the
file can grow, be truncated, gain a link, change mode, or be renamed away from under the name while
the read runs. `st_size` from the opening fstat is a number the reader must not trust either — it is
read from the same file the check exists to doubt.

These are contract tests over every copy of the reader, derived rather than typed, because the
copies are duplicated by design (standalone executables, no shared import path) and a subset is how
they drift apart.
"""
from __future__ import annotations

import hashlib
import os
import runpy
import stat
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]

# (module, reader function). Derived below and asserted against this floor, so a new copy of the
# reader is held to the contract rather than being silently skipped.
INGRESS_READERS = [
    ("scripts/hermes-busdriver-pr-grind-loop", "_read_authenticated"),
    ("scripts/hermes-busdriver-finalization-readiness", "_read_authenticated"),
    ("scripts/hermes-busdriver-relay-brief", "_read_authenticated"),
    ("scripts/hermes-busdriver-delivery-status", "_read_authenticated_helper"),
]

IDS = [f"{Path(m).name}:{f}" for m, f in INGRESS_READERS]


def load(module_path: str) -> dict:
    return runpy.run_path(str(ROOT / module_path))


def call(ns: dict, func_name: str, path: Path, digest: str):
    """Every copy takes (path, expected_digest); pr-grind-loop's also takes a `private` flag."""
    func = ns[func_name]
    if func_name == "_read_authenticated" and "private" in func.__code__.co_varnames:
        return func(path, digest, private=False)
    return func(path, digest)


def write_helper(path: Path, payload: bytes) -> str:
    path.write_bytes(payload)
    path.chmod(0o500)
    return hashlib.sha256(payload).hexdigest()


def test_the_enumeration_finds_every_copy_of_the_reader():
    """The guard on the guard: a derivation that found nothing would collect zero cases and pass."""
    defining = set()
    for path in sorted((ROOT / "scripts").rglob("*")):
        if not path.is_file() or path.suffix in {".sh", ".md", ".json", ".ts"}:
            continue
        text = path.read_text(errors="replace")
        for name in ("_read_authenticated", "_read_authenticated_helper"):
            if f"\ndef {name}(" in text:
                defining.add((str(path.relative_to(ROOT)), name))
    assert defining == set(INGRESS_READERS), (
        "pinned-helper readers this file does not hold to the contract:\n"
        + "\n".join(f"  {m}:{f}" for m, f in sorted(defining - set(INGRESS_READERS)))
    )


@pytest.mark.parametrize("module_path,func_name", INGRESS_READERS, ids=IDS)
def test_the_reader_declares_a_bound(module_path: str, func_name: str):
    ns = load(module_path)
    limit = ns.get("MAX_AUTHENTICATED_HELPER_BYTES")
    assert isinstance(limit, int), f"{module_path} declares no MAX_AUTHENTICATED_HELPER_BYTES"
    # Big enough for the largest helper this repo ships, small enough to still be a bound.
    assert 256 * 1024 <= limit <= 8 * 1024 * 1024


@pytest.mark.parametrize("module_path,func_name", INGRESS_READERS, ids=IDS)
def test_the_bound_is_identical_across_every_copy(module_path: str, func_name: str):
    """Restated, not shared — so a contract test is the only thing keeping the copies equal."""
    canonical = load(INGRESS_READERS[0][0])["MAX_AUTHENTICATED_HELPER_BYTES"]
    assert load(module_path)["MAX_AUTHENTICATED_HELPER_BYTES"] == canonical


@pytest.mark.parametrize("module_path,func_name", INGRESS_READERS, ids=IDS)
def test_an_untouched_helper_reads_back_whole(module_path: str, func_name: str, tmp_path: Path):
    """The bound must not cost the ordinary case."""
    ns = load(module_path)
    payload = b"#!/bin/sh\n" + bytes(range(256)) * 64
    helper = tmp_path / "helper"
    digest = write_helper(helper, payload)

    assert call(ns, func_name, helper, digest) == payload


@pytest.mark.parametrize("module_path,func_name", INGRESS_READERS, ids=IDS)
def test_a_helper_over_the_bound_is_refused_before_its_bytes_are_spent(
    module_path: str, func_name: str, tmp_path: Path, monkeypatch,
):
    """The point of the whole file: the refusal must precede the memory, not follow it.

    An oversized candidate is not merely rejected — it is rejected without this process ever having
    held it. `os.read` is counted rather than the result inspected, because "we allocated 500MB and
    then said no" is precisely the bug, and a test on the return value cannot tell the two apart.
    """
    ns = load(module_path)
    limit = ns["MAX_AUTHENTICATED_HELPER_BYTES"]
    helper = tmp_path / "helper"
    # Comfortably over, and written once: the file is the adversary's, so its size is its choice.
    payload = b"x" * (limit + (1 << 20))
    digest = write_helper(helper, payload)

    real_read = os.read
    handed: list[int] = []

    def counting_read(fd: int, n: int) -> bytes:
        chunk = real_read(fd, n)
        handed.append(len(chunk))
        return chunk

    monkeypatch.setattr(os, "read", counting_read)
    with pytest.raises(OSError):
        call(ns, func_name, helper, digest)
    monkeypatch.setattr(os, "read", real_read)

    assert sum(handed) <= limit + 4096, (
        f"{func_name} read {sum(handed)} bytes of a {len(payload)}-byte candidate before refusing "
        f"it — the bound is on the digest, not on the memory"
    )


@pytest.mark.parametrize("module_path,func_name", INGRESS_READERS, ids=IDS)
def test_a_helper_exactly_at_the_bound_is_still_readable(module_path: str, func_name: str, tmp_path: Path):
    """Off-by-one, asserted: the bound is a maximum, not a strict ceiling one byte below itself."""
    ns = load(module_path)
    limit = ns["MAX_AUTHENTICATED_HELPER_BYTES"]
    helper = tmp_path / "helper"
    payload = b"y" * limit
    digest = write_helper(helper, payload)

    assert call(ns, func_name, helper, digest) == payload


@pytest.mark.parametrize("module_path,func_name", INGRESS_READERS, ids=IDS)
def test_a_helper_replaced_at_its_name_during_the_read_fails_closed(
    module_path: str, func_name: str, tmp_path: Path, monkeypatch,
):
    """The direction the opening check cannot see, because it already ran.

    Identity was compared once, at open. Everything after it — including the read this function
    exists to perform — was covered by nothing. Moving our inode aside and renaming another file
    over the name leaves our fd, and every field on it, perfectly intact: only re-resolving the
    NAME notices, and the caller is about to use the name.
    """
    ns = load(module_path)
    helper = tmp_path / "helper"
    payload = b"#!/bin/sh\ntrusted\n"
    digest = write_helper(helper, payload)
    attacker = tmp_path / "attacker"
    write_helper(attacker, b"#!/bin/sh\nattacker\n")

    real_read = os.read
    swapped: list[bool] = []

    def read_then_swap(fd: int, n: int) -> bytes:
        chunk = real_read(fd, n)
        if not swapped:
            swapped.append(True)
            os.rename(helper, tmp_path / "moved-aside")  # our inode keeps its one link
            os.rename(attacker, helper)
        return chunk

    monkeypatch.setattr(os, "read", read_then_swap)
    with pytest.raises(OSError):
        call(ns, func_name, helper, digest)
    monkeypatch.setattr(os, "read", real_read)

    assert swapped, "the swap never happened; this test proves nothing"


@pytest.mark.parametrize("module_path,func_name", INGRESS_READERS, ids=IDS)
def test_a_helper_that_grows_during_the_read_fails_closed(
    module_path: str, func_name: str, tmp_path: Path, monkeypatch,
):
    """A size read at open is a number the file chose, and it can choose again mid-read."""
    ns = load(module_path)
    helper = tmp_path / "helper"
    payload = b"#!/bin/sh\ntrusted\n"
    digest = write_helper(helper, payload)

    real_read = os.read
    grown: list[bool] = []

    def read_then_grow(fd: int, n: int) -> bytes:
        chunk = real_read(fd, n)
        if not grown:
            grown.append(True)
            helper.chmod(0o700)
            with open(helper, "ab") as handle:
                handle.write(b"appended-after-the-open\n")
            helper.chmod(0o500)
        return chunk

    monkeypatch.setattr(os, "read", read_then_grow)
    with pytest.raises(OSError):
        call(ns, func_name, helper, digest)
    monkeypatch.setattr(os, "read", real_read)

    assert grown, "the growth never happened; this test proves nothing"


@pytest.mark.parametrize("module_path,func_name", INGRESS_READERS, ids=IDS)
def test_a_hard_linked_helper_is_refused(module_path: str, func_name: str, tmp_path: Path):
    """A second link is a second writer this reader never authorized."""
    ns = load(module_path)
    helper = tmp_path / "helper"
    payload = b"#!/bin/sh\ntrusted\n"
    digest = write_helper(helper, payload)
    os.link(helper, tmp_path / "second-link")

    with pytest.raises(OSError):
        call(ns, func_name, helper, digest)


@pytest.mark.parametrize("module_path,func_name", INGRESS_READERS, ids=IDS)
def test_a_symlinked_helper_is_refused(module_path: str, func_name: str, tmp_path: Path):
    ns = load(module_path)
    real = tmp_path / "real"
    digest = write_helper(real, b"#!/bin/sh\ntrusted\n")
    link = tmp_path / "helper"
    link.symlink_to(real)

    with pytest.raises(OSError):
        call(ns, func_name, link, digest)


@pytest.mark.parametrize("module_path,func_name", INGRESS_READERS, ids=IDS)
def test_a_helper_whose_bytes_do_not_match_the_pin_is_refused(module_path: str, func_name: str, tmp_path: Path):
    ns = load(module_path)
    helper = tmp_path / "helper"
    write_helper(helper, b"#!/bin/sh\nattacker\n")

    with pytest.raises(OSError):
        call(ns, func_name, helper, hashlib.sha256(b"#!/bin/sh\ntrusted\n").hexdigest())
