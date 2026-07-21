"""v16-r30 B: the Pi adapter's filesystem containment, tested where it actually lives.

The adapter prechecked parents by pathname and then acted on the same string, so a parent swapped
between the check and the use redirected the effect out of the repo — `O_NOFOLLOW` guards only the
leaf. Node has no `openat(2)`, so the fix is this broker: every component below the root is opened
relative to its parent's descriptor under `O_DIRECTORY|O_NOFOLLOW`.

Nothing here is a wall-clock race, because the guarantee is not "we usually win the race" — it is
"there is no window", and a timing test cannot show the absence of one. Two shapes prove it
deterministically instead: substitution tests, where the attacker's symlink is already in place
before the call, and one injection test that hands the attacker the exact window the old code lost
(test_a_parent_swapped_after_the_walk_cannot_redirect_the_effect) and shows the swap is inert.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import runpy
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BROKER = ROOT / "adapters" / "pi" / "busdriver-fs-broker.py"
PI_TOOLS = ROOT / "adapters" / "pi" / "busdriver-tools.ts"
MAX_FILE_BYTES = 256 * 1024


def call(request: dict, *, repo: Path = None, run: Path = None, env: dict = None) -> dict:
    environ = {"PATH": "/usr/bin:/bin"}
    if repo is not None:
        environ["BD_BROKER_ROOT_REPO"] = str(repo)
    if run is not None:
        environ["BD_BROKER_ROOT_RUN"] = str(run)
    environ.update(env or {})
    cp = subprocess.run(
        [sys.executable, "-I", str(BROKER)],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        env=environ,
        check=False,
    )
    assert cp.returncode == 0, f"broker crashed: {cp.stderr}"
    return json.loads(cp.stdout)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.txt").write_text("hello\n")
    return root


@pytest.fixture()
def outside(tmp_path: Path) -> Path:
    """The escape target: a directory the containment must never reach."""
    victim = tmp_path / "outside"
    victim.mkdir()
    (victim / "secret.txt").write_text("SENTINEL-UNTOUCHED\n")
    return victim


def swap_parent_to_symlink(repo: Path, outside: Path) -> None:
    """Exactly the attack: `src` is a directory at check time and a symlink at use time."""
    (repo / "src").rename(repo / "src-real")
    (repo / "src").symlink_to(outside)


# --- the happy paths the containment must not cost ---


def test_read_returns_a_file_beneath_the_root(repo: Path):
    assert call({"op": "read", "root": "repo", "rel": "src/app.txt"}, repo=repo) == {
        "ok": True, "content": "hello\n", "bytes": 6,
    }


def test_write_overwrites_and_reports_both_hashes(repo: Path):
    out = call({"op": "write", "root": "repo", "rel": "src/app.txt", "content": "next\n"}, repo=repo)

    assert out["ok"] is True and out["bytes"] == 5
    assert out["before_hash"] and out["after_hash"] and out["before_hash"] != out["after_hash"]
    assert (repo / "src" / "app.txt").read_text() == "next\n"


def test_write_creates_a_new_file_with_a_null_before_hash(repo: Path):
    out = call({"op": "write", "root": "repo", "rel": "src/new.txt", "content": "fresh\n"}, repo=repo)

    assert out["ok"] is True and out["before_hash"] is None and out["after_hash"]
    assert (repo / "src" / "new.txt").read_text() == "fresh\n"


def test_write_creates_missing_parents_beneath_the_root(repo: Path):
    out = call({"op": "write", "root": "repo", "rel": "a/b/c/deep.txt", "content": "deep\n"}, repo=repo)

    assert out["ok"] is True
    assert (repo / "a" / "b" / "c" / "deep.txt").read_text() == "deep\n"
    assert (repo / "a").stat().st_mode & 0o777 == 0o700


def test_created_parent_and_leaf_entries_are_directory_fsynced_before_success(repo: Path, monkeypatch):
    ns = runpy.run_path(str(BROKER))
    real_fsync = os.fsync
    events: list[str] = []

    def record_fsync(fd: int) -> None:
        events.append("dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file")
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", record_fsync)
    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    root = ns["open_root"]("repo")
    try:
        out = ns["op_write"](
            {"op": "write", "root": "repo", "rel": "a/b/c/deep.txt", "content": "deep\n"}, root
        )
    finally:
        ns["close_root"](root)

    assert out["ok"] is True
    assert events.count("dir") >= 4, (
        "each newly created a/b/c directory and the deep.txt directory entry need a parent fsync; "
        f"events={events}"
    )
    assert "file" in events


def test_write_then_read_round_trips(repo: Path):
    call({"op": "write", "root": "repo", "rel": "src/rt.txt", "content": "round\n"}, repo=repo)

    assert call({"op": "read", "root": "repo", "rel": "src/rt.txt"}, repo=repo)["content"] == "round\n"


def test_append_accumulates_event_log_lines(repo: Path, tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    for line in ('{"a":1}\n', '{"b":2}\n'):
        assert call({"op": "append", "root": "run", "rel": "pi-events.jsonl", "content": line}, run=run)["ok"]

    assert (run / "pi-events.jsonl").read_text() == '{"a":1}\n{"b":2}\n'


# --- parent substitution: read, overwrite, new file, parent creation ---


def test_read_refuses_a_parent_swapped_to_a_symlink(repo: Path, outside: Path):
    swap_parent_to_symlink(repo, outside)

    out = call({"op": "read", "root": "repo", "rel": "src/secret.txt"}, repo=repo)

    assert out == {"ok": False, "error": "symlink_escape_refused"}
    assert (outside / "secret.txt").read_text() == "SENTINEL-UNTOUCHED\n"


def test_overwrite_refuses_a_parent_swapped_to_a_symlink(repo: Path, outside: Path):
    swap_parent_to_symlink(repo, outside)

    out = call(
        {"op": "write", "root": "repo", "rel": "src/secret.txt", "content": "PWNED\n"}, repo=repo
    )

    assert out == {"ok": False, "error": "symlink_escape_refused"}
    assert (outside / "secret.txt").read_text() == "SENTINEL-UNTOUCHED\n", "the outside file was overwritten"


def test_new_file_creation_refuses_a_parent_swapped_to_a_symlink(repo: Path, outside: Path):
    swap_parent_to_symlink(repo, outside)

    out = call({"op": "write", "root": "repo", "rel": "src/planted.txt", "content": "PWNED\n"}, repo=repo)

    assert out == {"ok": False, "error": "symlink_escape_refused"}
    assert not (outside / "planted.txt").exists(), "a file was created outside the root"
    assert sorted(p.name for p in outside.iterdir()) == ["secret.txt"]


def test_parent_creation_refuses_a_parent_swapped_to_a_symlink(repo: Path, outside: Path):
    """`mkdir -p` must be contained too: creating the parent is as much an escape as writing it."""
    swap_parent_to_symlink(repo, outside)

    out = call({"op": "write", "root": "repo", "rel": "src/nested/deep/planted.txt", "content": "PWNED\n"}, repo=repo)

    assert out == {"ok": False, "error": "symlink_escape_refused"}
    assert not (outside / "nested").exists(), "a directory was created outside the root"
    assert sorted(p.name for p in outside.iterdir()) == ["secret.txt"]


def test_append_refuses_a_parent_swapped_to_a_symlink(repo: Path, tmp_path: Path, outside: Path):
    """The event log is the adjacent escape: same pathname pattern, same containment."""
    run = tmp_path / "run"
    (run / "logs").mkdir(parents=True)
    (run / "logs").rmdir()
    (run / "logs").symlink_to(outside)

    out = call({"op": "append", "root": "run", "rel": "logs/events.jsonl", "content": "PWNED\n"}, run=run)

    assert out == {"ok": False, "error": "symlink_escape_refused"}
    assert not (outside / "events.jsonl").exists()


def test_a_parent_swapped_after_the_walk_cannot_redirect_the_effect(repo: Path, outside: Path, monkeypatch):
    """The race itself, injected where the old check/use gap actually was.

    The substitution tests above would have passed against the old adapter too — its pathname
    precheck did catch a parent that was ALREADY a symlink. Its real hole was the window: it
    rechecked a name and then reopened that name, so a swap in between redirected the write. Here
    the attacker is handed that exact window and wins it, deterministically — the swap lands after
    the traversal has proved the parent. The descriptor makes the win worthless: the write still
    goes to the inode that was proven, and the attacker's directory is untouched.

    r32 scope note: this proves only that the DESCRIPTOR contains the effect, which is why it drives
    the primitives rather than op_write. That the effect is also refused — because the proven inode
    is no longer reachable through the live root path — is a separate claim, proved against the real
    op by test_a_write_whose_parent_was_detached_after_the_walk_fails_closed.
    """
    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    ns = runpy.run_path(str(BROKER))
    root = ns["open_root"]("repo")
    try:
        chain, name = ns["walk"](root, "src/out.txt", True)
        try:
            swap_parent_to_symlink(repo, outside)  # the attacker wins the race
            fd, created = ns["open_leaf_for_mutation"](chain.fd, name, False)
            assert created, "out.txt did not exist; the create-vs-open answer must come from the syscall"
            try:
                os.write(fd, b"draft\n")
            finally:
                os.close(fd)
        finally:
            chain.close()
    finally:
        ns["close_root"](root)

    assert (repo / "src-real" / "out.txt").read_text() == "draft\n", "the write did not land on the proven inode"
    assert not (outside / "out.txt").exists(), "the swapped parent redirected the write out of the root"
    assert sorted(p.name for p in outside.iterdir()) == ["secret.txt"]


def test_a_symlinked_leaf_is_refused_without_following_it(repo: Path, outside: Path):
    (repo / "src" / "link.txt").symlink_to(outside / "secret.txt")

    assert call({"op": "read", "root": "repo", "rel": "src/link.txt"}, repo=repo)["error"] == "symlink_escape_refused"
    assert call(
        {"op": "write", "root": "repo", "rel": "src/link.txt", "content": "PWNED\n"}, repo=repo
    )["error"] == "symlink_escape_refused"
    assert (outside / "secret.txt").read_text() == "SENTINEL-UNTOUCHED\n"


def test_dotdot_cannot_climb_out_of_the_root(repo: Path, outside: Path):
    """`..` is resolved by the kernel against the parent, so a descriptor walk must refuse it."""
    out = call({"op": "write", "root": "repo", "rel": "../outside/planted.txt", "content": "PWNED\n"}, repo=repo)

    assert out == {"ok": False, "error": "path_component_rejected"}
    assert not (outside / "planted.txt").exists()


def test_an_absolute_rel_is_confined_to_the_root(repo: Path, outside: Path):
    """A leading `/` must not make the walk start at the filesystem root."""
    out = call({"op": "read", "root": "repo", "rel": f"/{outside}/secret.txt"}, repo=repo)

    assert out["ok"] is False
    assert "SENTINEL" not in json.dumps(out)


# --- leaf identity: regular, owned, unshared, bounded ---


def test_write_refuses_a_hardlinked_target(repo: Path, outside: Path):
    """A hardlink is a second authorized name for these bytes; mutating through one is an escape."""
    os.link(outside / "secret.txt", repo / "src" / "alias.txt")

    out = call({"op": "write", "root": "repo", "rel": "src/alias.txt", "content": "PWNED\n"}, repo=repo)

    assert out == {"ok": False, "error": "hardlinked_target_refused"}
    assert (outside / "secret.txt").read_text() == "SENTINEL-UNTOUCHED\n"


def test_reads_and_writes_refuse_a_fifo(repo: Path):
    os.mkfifo(repo / "src" / "pipe", 0o600)

    assert call({"op": "read", "root": "repo", "rel": "src/pipe"}, repo=repo)["error"] == "not_a_regular_owned_file"
    assert call(
        {"op": "write", "root": "repo", "rel": "src/pipe", "content": "x"}, repo=repo
    )["error"] == "not_a_regular_owned_file"


def test_read_refuses_a_file_over_the_size_limit(repo: Path):
    (repo / "src" / "big.txt").write_bytes(b"x" * (MAX_FILE_BYTES + 1))

    assert call({"op": "read", "root": "repo", "rel": "src/big.txt"}, repo=repo)["error"] == "size_limit"


def test_write_refuses_content_over_the_size_limit(repo: Path):
    out = call({"op": "write", "root": "repo", "rel": "src/big.txt", "content": "x" * (MAX_FILE_BYTES + 1)}, repo=repo)

    assert out["error"] == "size_limit"
    assert not (repo / "src" / "big.txt").exists(), "an over-budget write still created the file"


def test_read_refuses_a_missing_file(repo: Path):
    assert call({"op": "read", "root": "repo", "rel": "src/absent.txt"}, repo=repo)["error"] == "not_found"


# --- protocol: bounded, schema-strict, credential-free, fail-closed ---


def test_the_root_is_named_by_label_so_a_caller_cannot_widen_its_containment(repo: Path, outside: Path):
    """The label indexes the environment; only the trusted wrapper sets it."""
    out = call({"op": "read", "root": str(outside), "rel": "secret.txt"}, repo=repo)

    assert out["ok"] is False
    assert "SENTINEL" not in json.dumps(out)


def test_an_unconfigured_root_label_fails_closed(repo: Path):
    assert call({"op": "read", "root": "run", "rel": "x.txt"}, repo=repo) == {
        "ok": False, "error": "broker_root_unconfigured",
    }


def test_a_non_canonical_root_is_refused(tmp_path: Path, repo: Path):
    """A symlinked root would be resolved again by the open — the very gap this broker closes."""
    link = tmp_path / "root-link"
    link.symlink_to(repo)

    assert call({"op": "read", "root": "repo", "rel": "src/app.txt"}, repo=link) == {
        "ok": False, "error": "broker_root_not_canonical",
    }


@pytest.mark.parametrize("request_body", [
    {"op": "exec", "root": "repo", "rel": "src/app.txt"},
    {"op": "read", "root": "repo"},
    {"op": "read", "root": "repo", "rel": "src/app.txt", "extra": "x"},
    {"op": "read", "root": "repo", "rel": 7},
])
def test_the_protocol_is_schema_strict(request_body: dict, repo: Path):
    assert call(request_body, repo=repo)["ok"] is False


def test_a_non_json_request_fails_closed(repo: Path):
    cp = subprocess.run(
        [sys.executable, "-I", str(BROKER)], input="not json", capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "BD_BROKER_ROOT_REPO": str(repo)}, check=False,
    )

    assert json.loads(cp.stdout) == {"ok": False, "error": "request_not_json"}


def test_an_oversized_request_is_refused_before_it_is_parsed(repo: Path):
    cp = subprocess.run(
        [sys.executable, "-I", str(BROKER)], input="{" + " " * (4 * 1024 * 1024 + 8),
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "BD_BROKER_ROOT_REPO": str(repo)}, check=False,
    )

    assert json.loads(cp.stdout) == {"ok": False, "error": "request_too_large"}


def test_refusals_never_carry_the_absolute_path(repo: Path, outside: Path):
    """The error token is fixed vocabulary: an errno string would carry the path we were aimed at."""
    swap_parent_to_symlink(repo, outside)

    out = call({"op": "read", "root": "repo", "rel": "src/secret.txt"}, repo=repo)

    assert str(outside) not in json.dumps(out) and str(repo) not in json.dumps(out)


def test_the_broker_runs_under_the_system_python_isolated_mode(repo: Path):
    """`-I` is how it is dispatched: no site-packages, no PYTHONPATH, no injected sitecustomize."""
    cp = subprocess.run(
        ["/usr/bin/python3", "-I", str(BROKER)],
        input=json.dumps({"op": "read", "root": "repo", "rel": "src/app.txt"}),
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "BD_BROKER_ROOT_REPO": str(repo), "PYTHONPATH": "/nonexistent"},
        check=False,
    )

    assert json.loads(cp.stdout)["content"] == "hello\n"


def test_system_python_broker_can_observe_git_without_waitid(repo: Path):
    """The production 3.9 interpreter lacks waitid; kqueue must preserve pre-reap PGID safety."""
    git_repo(repo)
    cp = subprocess.run(
        ["/usr/bin/python3", "-B", "-I", str(BROKER)],
        input=json.dumps({"op": "git", "root": "repo", "verb": "status", "rel": ""}),
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "BD_BROKER_ROOT_REPO": str(repo)},
        check=False,
    )

    assert cp.returncode == 0, cp.stderr
    assert json.loads(cp.stdout) == {"ok": True, "output": ""}


# --- v16-r30c: the anchor gets the same treatment as everything below it ---


def test_a_symlinked_intermediate_root_component_is_refused(tmp_path: Path):
    """The root is walked from `/`, so a symlink ANYWHERE in it fails closed — not just the leaf.

    `realpath(root) == root` followed by a fresh path-based `os.open(root)` passes this shape and
    then resolves the name a second time: the anchor the whole containment hangs from, re-derived
    from a string. Here `hop` is a symlink at open time and the walk refuses to follow it.
    """
    real = tmp_path / "real"
    (real / "repo" / "src").mkdir(parents=True)
    (real / "repo" / "src" / "app.txt").write_text("hello\n")
    (tmp_path / "hop").symlink_to(real)

    assert call({"op": "read", "root": "repo", "rel": "src/app.txt"}, repo=tmp_path / "hop" / "repo") == {
        "ok": False, "error": "broker_root_not_canonical",
    }


@pytest.mark.parametrize("root_value", [
    "relative/repo",  # not absolute: there is no descriptor to anchor it to.
    "/tmp/../etc",    # `..` is resolved by the kernel from the parent, not from the held fd.
    "/tmp/./x",       # `.` is not a component the walk will accept.
])
def test_a_non_canonical_root_path_is_refused_without_being_walked(repo: Path, root_value: str):
    assert call(
        {"op": "read", "root": "repo", "rel": "src/app.txt"},
        env={"BD_BROKER_ROOT_REPO": root_value},
    ) == {"ok": False, "error": "broker_root_not_canonical"}


def test_a_root_component_that_is_a_regular_file_is_refused(tmp_path: Path):
    (tmp_path / "notadir").write_text("x")

    assert call({"op": "read", "root": "repo", "rel": "src/app.txt"}, repo=tmp_path / "notadir" / "repo") == {
        "ok": False, "error": "broker_root_not_canonical",
    }


# --- v16-r30c: a short write is a silent truncation ---


def test_write_all_loops_until_every_byte_lands(tmp_path: Path, monkeypatch):
    """`os.write` is permitted to write less than it was given; one call would truncate quietly.

    Scoped to our own descriptor so the patch cannot disturb pytest's own writes.
    """
    ns = runpy.run_path(str(BROKER))
    target = tmp_path / "out.txt"
    fd = os.open(str(target), os.O_RDWR | os.O_CREAT, 0o600)
    real_write = os.write
    calls = []

    def one_byte_at_a_time(write_fd, data):
        if write_fd != fd:
            return real_write(write_fd, data)
        written = real_write(write_fd, bytes(data)[:1])
        calls.append(written)
        return written

    monkeypatch.setattr(os, "write", one_byte_at_a_time)
    try:
        ns["write_all"](fd, b"complete\n")
    finally:
        os.close(fd)

    assert target.read_bytes() == b"complete\n", "write_all lost bytes to a short write"
    assert len(calls) == 9, "write_all did not loop over the short writes"


def test_write_all_refuses_a_write_that_makes_no_progress(tmp_path: Path, monkeypatch):
    ns = runpy.run_path(str(BROKER))
    fd = os.open(str(tmp_path / "out.txt"), os.O_RDWR | os.O_CREAT, 0o600)
    real_write = os.write
    monkeypatch.setattr(os, "write", lambda w, d: 0 if w == fd else real_write(w, d))
    try:
        with pytest.raises(Exception) as exc:
            ns["write_all"](fd, b"x")
    finally:
        os.close(fd)

    assert str(exc.value) == "short_write"


def test_a_write_reports_the_exact_length_it_landed(repo: Path):
    body = "x" * 4096

    out = call({"op": "write", "root": "repo", "rel": "src/app.txt", "content": body}, repo=repo)

    assert out["bytes"] == len(body)
    assert (repo / "src" / "app.txt").read_text() == body
    assert out["after_hash"] == hashlib.sha256(body.encode()).hexdigest()


# --- v16-r30c: the audit must describe the inode we mutated, or no audit at all ---


@pytest.mark.parametrize("op", ["write", "append"])
@pytest.mark.parametrize("attack", ["replaced", "renamed_away"])
def test_a_leaf_swapped_after_the_effect_fails_closed(repo: Path, op: str, attack: str, monkeypatch):
    """The window between the bytes landing and the audit being produced, handed to the attacker.

    An fd outlives its own directory entry, so every fstat still passes after a rename — the write
    itself is safe (it went to the proven inode), but the RESPONSE would describe `src/app.txt`
    while that name now points somewhere else. Whoever reads the audit is told a file they can
    still open has the hash we report. It does not. So the entry is re-proved against the
    descriptor, and a swap fails closed rather than returning an audit for another inode.
    """
    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    ns = runpy.run_path(str(BROKER))
    real_fsync = os.fsync
    swapped = []

    def fsync_then_swap(fd):
        real_fsync(fd)
        if swapped:
            return
        swapped.append(True)
        if attack == "replaced":
            (repo / "src" / "decoy.txt").write_text("ATTACKER\n")
            os.replace(repo / "src" / "decoy.txt", repo / "src" / "app.txt")
        else:
            os.rename(repo / "src" / "app.txt", repo / "src" / "moved.txt")

    monkeypatch.setattr(os, "fsync", fsync_then_swap)
    handler = ns["op_write"] if op == "write" else ns["op_append"]
    root = ns["open_root"]("repo")
    try:
        with pytest.raises(Exception) as exc:
            handler({"op": op, "root": "repo", "rel": "src/app.txt", "content": "draft\n"}, root)
    finally:
        ns["close_root"](root)

    assert swapped, "the attack never ran; the test proves nothing"
    assert str(exc.value) == "identity_drift"
    if attack == "replaced":
        assert (repo / "src" / "app.txt").read_text() == "ATTACKER\n"


def test_a_leaf_replaced_before_the_effect_is_never_created_outside_the_root(repo: Path, outside: Path):
    """O_CREAT|O_EXCL only ever fires on a leaf an open proved absent, and only under the walked
    parent — so losing that race is a refusal, not a file somewhere else."""
    ns = runpy.run_path(str(BROKER))
    parent_fd = os.open(str(repo / "src"), os.O_RDONLY | os.O_DIRECTORY)
    try:
        (repo / "src" / "new.txt").write_text("winner\n")  # the racer wins between open and create
        fd, created = ns["open_leaf_for_mutation"](parent_fd, "new.txt", False)
        os.close(fd)
    finally:
        os.close(parent_fd)

    assert not created, "an existing leaf must not be reported as created"
    assert sorted(p.name for p in outside.iterdir()) == ["secret.txt"]


def test_the_before_hash_is_the_bytes_that_were_actually_overwritten(repo: Path):
    """`before_hash` is bound to the descriptor that gets truncated — not to a second lookup."""
    (repo / "src" / "app.txt").write_text("original\n")

    out = call({"op": "write", "root": "repo", "rel": "src/app.txt", "content": "replacement\n"}, repo=repo)

    assert out["before_hash"] == hashlib.sha256(b"original\n").hexdigest()
    assert out["after_hash"] == hashlib.sha256(b"replacement\n").hexdigest()


# --- v16-r31 B4: the final window — after the hash, not just before it ---


def op_write_direct(ns: dict, repo: Path, rel: str, content: str):
    """Drive op_write against a real root so a monkeypatch can reach its inner window."""
    root = ns["open_root"]("repo")
    try:
        return ns["op_write"]({"op": "write", "root": "repo", "rel": rel, "content": content}, root)
    finally:
        ns["close_root"](root)


def test_a_leaf_replaced_after_the_hash_fails_closed(repo: Path, monkeypatch):
    """`validate_mutated_leaf` before the hash proves nothing about the moment the hash ended.

    The old order was validate -> hash -> return, so the entire hash was an unguarded window: a
    rename landing in it leaves every earlier proof intact while `rel` now names another inode, and
    the response still says "I hashed src/app.txt". The success claim is about the CURRENT name, so
    the name has to still be the hashed inode when the claim is made — not when the check ran.
    """
    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    ns = runpy.run_path(str(BROKER))
    real_hash_fd = ns["hash_fd"]
    content = "replacement-of-a-distinct-length\n"
    swapped: list[bool] = []

    def hash_then_replace(fd, size):
        digest = real_hash_fd(fd, size)
        if size == len(content) and not swapped:  # the after_hash call, never the before_hash one
            swapped.append(True)
            (repo / "src" / "decoy.txt").write_text("ATTACKER\n")
            os.replace(repo / "src" / "decoy.txt", repo / "src" / "app.txt")
        return digest

    monkeypatch.setitem(ns["op_write"].__globals__, "hash_fd", hash_then_replace)
    with pytest.raises(Exception) as exc:
        op_write_direct(ns, repo, "src/app.txt", content)

    assert swapped, "the attack never ran; the test proves nothing"
    assert str(exc.value) == "identity_drift"


def test_a_leaf_rewritten_in_place_after_the_hash_fails_closed(repo: Path, monkeypatch):
    """A same-length in-place rewrite keeps dev/ino/nlink/size and the directory entry identical.

    Every predicate `validate_mutated_leaf` owns still passes, so the pre-hash check cannot see it
    and the entry binding cannot either — the inode really is the one we wrote, under the name we
    were asked for. What moved is the BYTES, and `after_hash` was taken before they moved: the
    response would hand a reviewer a hash for content the file no longer has. Only re-proving the
    descriptor's own metadata across the hash catches it.
    """
    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    ns = runpy.run_path(str(BROKER))
    real_hash_fd = ns["hash_fd"]
    content = "drafted\n"
    rewritten: list[bool] = []

    def hash_then_rewrite(fd, size):
        digest = real_hash_fd(fd, size)
        if size == len(content) and not rewritten:
            rewritten.append(True)
            victim = os.open(str(repo / "src" / "app.txt"), os.O_WRONLY)
            try:
                os.pwrite(victim, b"ATTACK!\n", 0)  # same length: only mtime/ctime move
            finally:
                os.close(victim)
        return digest

    monkeypatch.setitem(ns["op_write"].__globals__, "hash_fd", hash_then_rewrite)
    with pytest.raises(Exception) as exc:
        op_write_direct(ns, repo, "src/app.txt", content)

    assert rewritten, "the attack never ran; the test proves nothing"
    assert str(exc.value) == "identity_drift"
    assert (repo / "src" / "app.txt").read_bytes() == b"ATTACK!\n"


def test_a_clean_write_still_reports_the_hash_of_the_bytes_it_landed(repo: Path):
    """The final proof must not cost the happy path: an undisturbed write still audits."""
    out = call({"op": "write", "root": "repo", "rel": "src/app.txt", "content": "settled\n"}, repo=repo)

    assert out["ok"] is True
    assert out["after_hash"] == hashlib.sha256(b"settled\n").hexdigest()
    assert (repo / "src" / "app.txt").read_bytes() == b"settled\n"


# --- v16-r31 B5: an append bound that bounds the FILE, not just the request ---


def test_append_refuses_to_grow_the_target_past_the_total_bound(tmp_path: Path):
    """`len(content) <= MAX` bounds one request. Nothing bounded the file the requests build.

    The event log is appended to once per tool call, so a per-request bound is not a bound at all —
    it is a rate. The target must be refused on `opened_size + appended > MAX`.
    """
    run = tmp_path / "run"
    run.mkdir()
    (run / "pi-events.jsonl").write_bytes(b"x" * (MAX_FILE_BYTES - 4))

    out = call({"op": "append", "root": "run", "rel": "pi-events.jsonl", "content": "12345"}, run=run)

    assert out == {"ok": False, "error": "size_limit"}
    assert (run / "pi-events.jsonl").stat().st_size == MAX_FILE_BYTES - 4, "the refused append still landed"


def test_append_refuses_an_already_oversized_target(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "pi-events.jsonl").write_bytes(b"x" * (MAX_FILE_BYTES + 1))

    assert call({"op": "append", "root": "run", "rel": "pi-events.jsonl", "content": "y"}, run=run) == {
        "ok": False, "error": "size_limit",
    }


def test_append_fills_the_bound_exactly_and_then_refuses(tmp_path: Path):
    """Repeated appends converge on the bound rather than walking through it."""
    run = tmp_path / "run"
    run.mkdir()
    (run / "pi-events.jsonl").write_bytes(b"x" * (MAX_FILE_BYTES - 2))

    assert call({"op": "append", "root": "run", "rel": "pi-events.jsonl", "content": "ab"}, run=run)["ok"] is True
    assert (run / "pi-events.jsonl").stat().st_size == MAX_FILE_BYTES
    assert call({"op": "append", "root": "run", "rel": "pi-events.jsonl", "content": "c"}, run=run) == {
        "ok": False, "error": "size_limit",
    }
    assert (run / "pi-events.jsonl").stat().st_size == MAX_FILE_BYTES


# --- v16-r31 A3: git inspection is brokered, pinned, and fixed-argv ---


def git_test_env() -> dict[str, str]:
    return {"PATH": "/usr/bin:/bin:/opt/homebrew/bin", "HOME": "/nonexistent", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e.com",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e.com"}


def git_repo(path: Path, branch: str | None = None) -> Path:
    env = git_test_env()
    # A named branch is how the ABA tests below tell WHICH repository answered, without needing two
    # distinguishable commits: `branch --show-current` prints it back.
    init = ["git", "init", "-q"] + (["-b", branch] if branch else [])
    for cmd in (init, ["git", "add", "-A"], ["git", "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=path, env=env, check=True, capture_output=True)
    return path


@pytest.fixture()
def retained_git(tmp_path: Path) -> Path:
    """v16-r34c: there is no retained private git any more, and this fixture no longer pretends.

    It used to build "the shape the wrapper hands over" — authenticated bytes copied 0500 under a
    0700 dir — from /opt/homebrew/bin/git. Both halves of that are gone: the wrapper hands nothing
    over, and Homebrew's git is refused for user-writable ancestry. The tests that took this fixture
    are asking "which git does the broker run", and the answer is now a constant, so the fixture
    returns it. Kept as a fixture rather than deleted because the request-schema test below still
    needs a plausible path to be REJECTED as an override.
    """
    return Path("/usr/bin/git")


def git_call(request: dict, repo: Path, retained_git: Path, **kw) -> dict:
    """No BD_BROKER_GIT. The broker resolves its own git; the env cannot name it."""
    return call(request, repo=repo, **kw)


def test_check_ignore_answers_through_the_broker(repo: Path, retained_git: Path):
    (repo / ".gitignore").write_text(".env\n")
    git_repo(repo)

    assert git_call({"op": "git", "root": "repo", "verb": "check_ignore", "rel": ".env"}, repo, retained_git) == {
        "ok": True, "ignored": True,
    }
    assert git_call({"op": "git", "root": "repo", "verb": "check_ignore", "rel": "src/app.txt"}, repo, retained_git) == {
        "ok": True, "ignored": False,
    }


@pytest.mark.parametrize("verb", ["status", "branch", "head", "diff", "diff_name_only", "diff_stat", "log"])
def test_every_inspection_verb_returns_bounded_output(repo: Path, retained_git: Path, verb: str):
    git_repo(repo)

    out = git_call({"op": "git", "root": "repo", "verb": verb, "rel": ""}, repo, retained_git)

    assert out["ok"] is True and isinstance(out["output"], str)


def test_status_reports_a_draft_write(repo: Path, retained_git: Path):
    git_repo(repo)
    (repo / "src" / "app.txt").write_text("drafted\n")

    out = git_call({"op": "git", "root": "repo", "verb": "status", "rel": ""}, repo, retained_git)

    assert "src/app.txt" in out["output"]


def test_status_repo_config_cannot_hide_mode_only_drift(repo: Path, retained_git: Path):
    tool = repo / "src" / "app.txt"
    tool.chmod(0o644)
    git_repo(repo)
    subprocess.run(
        [str(retained_git), "config", "core.fileMode", "false"],
        cwd=repo, env=git_test_env(), capture_output=True, check=True,
    )
    tool.chmod(0o755)

    hidden = subprocess.run(
        [str(retained_git), "status", "--porcelain=v1"],
        cwd=repo, env=git_test_env(), capture_output=True, text=True, check=True,
    )
    control = subprocess.run(
        [str(retained_git), "-c", "core.fileMode=true", "status", "--porcelain=v1"],
        cwd=repo, env=git_test_env(), capture_output=True, text=True, check=True,
    )
    assert hidden.stdout == "", "hostile fixture did not hide mode drift"
    assert "src/app.txt" in control.stdout, "mode-only control did not expose drift"

    out = git_call({"op": "git", "root": "repo", "verb": "status", "rel": ""}, repo, retained_git)

    assert out["ok"] is True
    assert "src/app.txt" in out["output"]


@pytest.mark.parametrize("verb", ["commit", "push", "config", "gc", "", "check-ignore", "status;rm"])
def test_a_verb_outside_the_fixed_table_is_refused(repo: Path, retained_git: Path, verb: str):
    """The caller picks a LABEL from a fixed table; it never supplies argv. This is the whole
    difference between a git inspection broker and an arbitrary command runner."""
    assert git_call({"op": "git", "root": "repo", "verb": verb, "rel": ""}, repo, retained_git) == {
        "ok": False, "error": "git_verb_rejected",
    }


@pytest.mark.parametrize("request_body", [
    {"op": "git", "root": "repo", "verb": "status"},                      # rel is not optional
    {"op": "git", "root": "repo", "verb": "status", "rel": "", "x": 1},   # no unknown keys
    {"op": "git", "root": "repo", "verb": 7, "rel": ""},                  # strings only
    {"op": "git", "root": "repo", "verb": "status", "rel": 7},
    {"op": "git", "root": "repo", "verb": "status", "rel": "unused"},     # rel only where it is read
])
def test_the_git_protocol_is_schema_strict(request_body: dict, repo: Path, retained_git: Path):
    assert git_call(request_body, repo, retained_git)["ok"] is False


def test_a_caller_cannot_select_the_git_executable(repo: Path, retained_git: Path, tmp_path: Path):
    """`rel` is the only caller-supplied string, and it is a pathspec — never an executable."""
    impostor = tmp_path / "impostor"
    impostor.write_text("#!/bin/sh\necho PWNED\n")
    impostor.chmod(0o500)

    out = call({"op": "git", "root": "repo", "verb": "status", "rel": "", "git": str(impostor)}, repo=repo,
               env={"BD_BROKER_GIT": str(retained_git)})

    assert out == {"ok": False, "error": "request_schema_rejected"}


def test_the_broker_needs_no_git_configuration_at_all(repo: Path):
    """v16-r34c: replaces test_an_unconfigured_git_fails_closed.

    "Unconfigured" was a state because $BD_BROKER_GIT was how git got here. There is nothing to
    configure now — the source is a constant in this file — so a broker with an empty environment
    resolves git and works. `git_unconfigured` is gone with the variable that could be missing.
    """
    git_repo(repo)
    out = call({"op": "git", "root": "repo", "verb": "status", "rel": ""}, repo=repo)
    assert out.get("ok") is True, out


@pytest.mark.parametrize("planted", [
    "/tmp/evil-git",                      # somewhere the adversary owns outright
    "/opt/homebrew/bin/git",              # real git, user-writable ancestry (uid=501 drwxrwxr-x)
    "git",                                # a bare name, to be found on PATH
    "",                                   # and the empty string, to look "unconfigured"
])
def test_no_environment_variable_can_choose_the_git_the_broker_runs(repo: Path, planted: str):
    """v16-r34c: replaces test_a_git_that_is_not_a_privately_retained_file_is_refused.

    That test checked that an env-named git had the right SHAPE — regular, ours, unshared, in a
    private-looking directory. Every one of those predicates is satisfiable by any file this UID can
    create, and none of them is a statement about WHICH BYTES, because the digest deliberately lived
    in the wrapper. The variable was the vulnerability, and validating its value harder was never
    going to fix it: a same-UID adversary who can set one variable on this process chose the program
    that ran with a descriptor on the repository.

    So the property inverts. There is nothing to validate because there is nothing to supply: the
    variable is ignored, whatever it holds, and the frozen root-owned source runs regardless.
    """
    git_repo(repo)
    out = call({"op": "git", "root": "repo", "verb": "status", "rel": ""}, repo=repo,
               env={"BD_BROKER_GIT": planted})
    # Not merely "refused" — SERVED, from the real git, with the plant ignored entirely. A refusal
    # would also pass a test that read the variable and disliked it.
    assert out.get("ok") is True, out


def test_the_broker_git_is_the_frozen_root_owned_source(repo: Path):
    """The other half of the above: name what it DOES run, so "ignores the env" cannot be satisfied
    by ignoring git altogether."""
    ns = runpy.run_path(str(BROKER))
    os.environ["BD_BROKER_GIT"] = "/tmp/evil-git"
    try:
        resolved = ns["trusted_git"]()
    finally:
        del os.environ["BD_BROKER_GIT"]
    assert resolved == ns["TRUSTED_EXECUTABLE_SOURCES"]["git"] == "/usr/bin/git"
    st = os.lstat(resolved)
    assert not stat.S_ISLNK(st.st_mode)
    assert st.st_uid == 0, "a git this UID owns is a git this UID can replace"
    assert not (st.st_mode & (stat.S_IWGRP | stat.S_IWOTH))


def test_git_runs_with_no_credential_in_its_environment(repo: Path, retained_git: Path, monkeypatch):
    """The broker builds git's env from a fixed table; it never forwards its own."""
    git_repo(repo)
    ns = runpy.run_path(str(BROKER))

    env = ns["git_env"]()

    assert "GH_TOKEN" not in env and "GITHUB_TOKEN" not in env
    assert env["GIT_OPTIONAL_LOCKS"] == "0"
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["HOME"] == "/nonexistent"


def test_no_verb_template_carries_a_mutating_or_config_argument():
    """Read-only is a property of the table, so the table is what the test reads."""
    ns = runpy.run_path(str(BROKER))
    forbidden = {"commit", "push", "merge", "rebase", "reset", "tag", "checkout", "switch", "config",
                 "fetch", "pull", "clone", "gc", "clean", "apply", "am", "stash", "-c", "--exec-path",
                 "--upload-pack", "--receive-pack"}

    for verb, (_needs_rel, template) in ns["GIT_VERBS"].items():
        assert not forbidden & set(template), f"{verb} template is not read-only: {template}"


def test_git_output_over_the_bound_is_refused_rather_than_truncated(repo: Path, retained_git: Path, monkeypatch):
    """A diff is as big as the tree the adapter just wrote, and the response is JSON in a pipe."""
    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    monkeypatch.setenv("BD_BROKER_GIT", str(retained_git))
    ns = runpy.run_path(str(BROKER))
    monkeypatch.setitem(ns["run_git"].__globals__, "MAX_GIT_OUTPUT_BYTES", 16)
    git_repo(repo)
    (repo / "src" / "app.txt").write_text("x" * 4096 + "\n")
    root = ns["open_root"]("repo")
    try:
        with pytest.raises(Exception) as exc:
            ns["op_git"]({"op": "git", "root": "repo", "verb": "diff", "rel": ""}, root)
    finally:
        ns["close_root"](root)

    assert str(exc.value) == "git_output_too_large"


def test_git_never_writes_the_index_it_inspects(repo: Path, retained_git: Path):
    """GIT_OPTIONAL_LOCKS=0: `status` refreshes the index by default, which is a mutation of the
    repository this broker exists to keep read-only."""
    git_repo(repo)
    (repo / "src" / "app.txt").write_text("drafted-to-force-a-refresh\n")
    before = (repo / ".git" / "index").stat().st_mtime_ns

    git_call({"op": "git", "root": "repo", "verb": "status", "rel": ""}, repo, retained_git)

    assert (repo / ".git" / "index").stat().st_mtime_ns == before


@pytest.mark.parametrize("rel", ["../outside", "/etc/passwd", "a/../../b", "a//b", "src/", ""])
def test_check_ignore_refuses_a_pathspec_it_would_have_to_normalize(repo: Path, retained_git: Path, rel: str):
    """`/etc/passwd` is the one that matters: silently reading it as `etc/passwd` answers about a
    file nobody named. git resolves its own pathname, so the broker cannot rewrite it and stay
    honest — it refuses instead."""
    git_repo(repo)

    assert git_call({"op": "git", "root": "repo", "verb": "check_ignore", "rel": rel}, repo, retained_git)["ok"] is False


@pytest.mark.parametrize("rel", [":(glob)**", ":!src/app.txt", ":/", ":^src", ":(attr:x)y", ":(exclude).env"])
def test_check_ignore_refuses_pathspec_magic(repo: Path, retained_git: Path, rel: str):
    """Magic makes check-ignore answer a different question than the path asked — and that answer
    is the whole of the ignored-path protection. `GIT_LITERAL_PATHSPECS` cannot close this: the one
    command that takes a caller's pathspec is the one that rejects literal mode outright."""
    (repo / ".gitignore").write_text(".env\n")
    git_repo(repo)

    assert git_call({"op": "git", "root": "repo", "verb": "check_ignore", "rel": rel}, repo, retained_git) == {
        "ok": False, "error": "pathspec_magic_refused",
    }


def test_a_symlinked_root_is_refused_before_git_runs(tmp_path: Path, retained_git: Path):
    """The git op hangs off the same descriptor-bound anchor as every other op."""
    real = tmp_path / "real"
    real.mkdir()
    (real / "app.txt").write_text("hello\n")
    git_repo(real)
    (tmp_path / "hop").symlink_to(real)

    assert call({"op": "git", "root": "repo", "verb": "status", "rel": ""}, repo=tmp_path / "hop",
                env={"BD_BROKER_GIT": str(retained_git)}) == {"ok": False, "error": "broker_root_not_canonical"}


# --- v16-r32 A: repo-local git config is attacker-authored, so no verb may consult it ---


HOSTILE_GIT_CONFIG = {
    # `status` refreshes the index, and a repo-local fsmonitor hook is a COMMAND git runs to do it.
    "core.fsmonitor": ("status", "sentinel-fsmonitor"),
    # `log.showSignature=true` turns `log --oneline` into a verification, and gpg.program is the
    # program that verifies. Two repo-local keys, one exec.
    "gpg.program": ("log", "sentinel-gpg"),
    "gpg.ssh.program": ("log", "sentinel-gpg-ssh"),
    "diff.external": ("diff", "sentinel-ext-diff"),
    # `.gitattributes` selects arbitrary named diff/filter drivers. Unlike diff.external, the name
    # inside either key is attacker-chosen, so no finite set of `-c` pins can enumerate it.
    "diff.pwn.command": ("diff", "sentinel-diff-command"),
    "filter.pwn.clean": ("status", "sentinel-filter-clean"),
    "core.pager": ("log", "sentinel-pager"),
    "core.hooksPath": ("status", "sentinel-hooks"),
}

DYNAMIC_PROGRAM_GIT_CONFIG = {"diff.pwn.command", "filter.pwn.clean"}


def hostile_git_config(repo: Path, key: str, program: Path) -> None:
    """Write the hostile key straight into `.git/config` — exactly what a draft worker can do.

    Deliberately not `git config`: this is the untrusted repository authoring its own config, and
    the test must not depend on a git invocation to plant what git will later read.
    """
    value = str(program)
    section, _, name = key.rpartition(".")
    with (repo / ".git" / "config").open("a") as handle:
        handle.write(f'[{section}]\n\t{name} = "{value}"\n')
    if key in ("gpg.program", "gpg.ssh.program"):
        with (repo / ".git" / "config").open("a") as handle:
            handle.write("[log]\n\tshowSignature = true\n")
    if key == "core.hooksPath":
        hooks = repo / "hostile-hooks"
        hooks.mkdir(exist_ok=True)
        for hook in ("pre-command", "post-index-change", "reference-transaction"):
            target = hooks / hook
            target.write_text(f'#!/bin/sh\necho fired >> "{program.parent}/sentinel-hooks"\nexit 0\n')
            target.chmod(0o700)


@pytest.fixture()
def sentinel_program(tmp_path: Path):
    """A program that records the fact it ran. If any of these files exists, git executed it."""
    bin_dir = tmp_path / "hostile-bin"
    bin_dir.mkdir()
    program = bin_dir / "evil"
    program.write_text(
        '#!/bin/sh\n'
        'echo "fired $*" >> "$(dirname "$0")/sentinel-fired"\n'
        'exit 0\n'
    )
    program.chmod(0o700)
    return program


@pytest.mark.parametrize("key", sorted(HOSTILE_GIT_CONFIG))
def test_a_hostile_repo_local_config_key_never_executes_a_command(
    repo: Path, retained_git: Path, sentinel_program: Path, key: str,
):
    """The repository was just written to by an untrusted draft worker, so `.git/config` is input.

    Every one of these keys names a PROGRAM that git will run while answering a read-only question.
    A denylist over the environment cannot reach them — they live in repo-local config, which git
    reads no matter what the environment says. `-c` on the command line is the one lever that
    outranks repo-local config, so the broker hard-pins each of them inert on every verb.
    """
    verb, _ = HOSTILE_GIT_CONFIG[key]
    git_repo(repo)
    if key in DYNAMIC_PROGRAM_GIT_CONFIG:
        # Attributes must be trusted by the index before the hostile driver is planted.  An
        # untracked .gitattributes is not consistently consulted by every git version during
        # status, and would make this parameter vacuously green.
        attribute = "filter=pwn" if key.startswith("filter.") else "diff=pwn"
        (repo / ".gitattributes").write_text(f"* {attribute}\n")
        for cmd in (["git", "add", ".gitattributes"], ["git", "commit", "-qm", "attributes"]):
            subprocess.run(cmd, cwd=repo, env=git_test_env(), check=True, capture_output=True)
    hostile_git_config(repo, key, sentinel_program)
    (repo / "src" / "app.txt").write_text("drafted-to-force-work\n")

    out = git_call({"op": "git", "root": "repo", "verb": verb, "rel": ""}, repo, retained_git)

    if key in DYNAMIC_PROGRAM_GIT_CONFIG:
        assert out == {"ok": False, "error": "git_program_config_refused"}
    else:
        assert out["ok"] is True

    fired = sorted(p.name for p in sentinel_program.parent.iterdir() if p.name.startswith("sentinel"))
    assert fired == [], f"repo-local {key} executed a command during `{verb}`: {fired}"


def test_the_hostile_filter_fixture_fires_against_an_unpinned_git(
    repo: Path, retained_git: Path, sentinel_program: Path,
):
    """Control for the dynamic filter name: the same indexed attributes and config must really exec."""
    git_repo(repo)
    (repo / ".gitattributes").write_text("* filter=pwn\n")
    for cmd in (["git", "add", ".gitattributes"], ["git", "commit", "-qm", "attributes"]):
        subprocess.run(cmd, cwd=repo, env=git_test_env(), check=True, capture_output=True)
    hostile_git_config(repo, "filter.pwn.clean", sentinel_program)
    (repo / "src" / "app.txt").write_text("drafted-to-force-filter\n")
    ns = runpy.run_path(str(BROKER))

    subprocess.run(
        [str(retained_git), "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo / ".git", env=ns["git_env"](), capture_output=True, check=False,
    )

    assert (sentinel_program.parent / "sentinel-fired").exists(), (
        "the filter fixture never fires even unpinned; the hostile-config parameter is vacuous"
    )


def test_an_included_hostile_filter_is_refused_before_git_can_execute_it(
    repo: Path, retained_git: Path, sentinel_program: Path,
):
    """`--includes` is load-bearing: an indirect driver is the same program from another file."""
    git_repo(repo)
    (repo / ".gitattributes").write_text("* filter=pwn\n")
    for cmd in (["git", "add", ".gitattributes"], ["git", "commit", "-qm", "attributes"]):
        subprocess.run(cmd, cwd=repo, env=git_test_env(), check=True, capture_output=True)
    included = repo / ".git" / "hostile-filter.config"
    included.write_text(f'[filter "pwn"]\n\tclean = "{sentinel_program}"\n')
    with (repo / ".git" / "config").open("a") as handle:
        handle.write(f'[include]\n\tpath = "{included}"\n')
    (repo / "src" / "app.txt").write_text("drafted-to-force-included-filter\n")

    out = git_call({"op": "git", "root": "repo", "verb": "status", "rel": ""}, repo, retained_git)

    assert out == {"ok": False, "error": "git_program_config_refused"}
    assert not (sentinel_program.parent / "sentinel-fired").exists()


def test_a_worktree_config_hostile_filter_is_refused_before_git_can_execute_it(
    repo: Path, retained_git: Path, sentinel_program: Path,
):
    """`extensions.worktreeConfig` moves effective local keys out of `.git/config`.

    An audit that reads only the ordinary local file is incomplete: Git merges `config.worktree`
    into the same effective scope before `status` chooses a filter program.
    """
    git_repo(repo)
    (repo / ".gitattributes").write_text("* filter=pwn\n")
    for cmd in (["git", "add", ".gitattributes"], ["git", "commit", "-qm", "attributes"]):
        subprocess.run(cmd, cwd=repo, env=git_test_env(), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "extensions.worktreeConfig", "true"],
        cwd=repo, env=git_test_env(), check=True, capture_output=True,
    )
    (repo / ".git" / "config.worktree").write_text(
        f'[filter "pwn"]\n\tclean = "{sentinel_program}"\n'
    )
    (repo / "src" / "app.txt").write_text("drafted-to-force-worktree-filter\n")

    out = git_call({"op": "git", "root": "repo", "verb": "status", "rel": ""}, repo, retained_git)

    assert out == {"ok": False, "error": "git_program_config_refused"}
    assert not (sentinel_program.parent / "sentinel-fired").exists()


def test_git_observations_are_os_sandboxed_and_transport_closed():
    ns = runpy.run_path(str(BROKER))
    argv = ns["git_observation_argv"]("status")
    profile = ns["GIT_OBSERVATION_SANDBOX_PROFILE"]

    assert ns["TRUSTED_EXECUTABLE_SOURCES"] == {
        "git": "/usr/bin/git",
        "git-real": "/Library/Developer/CommandLineTools/usr/bin/git",
        "sandbox-exec": "/usr/bin/sandbox-exec",
    }
    assert argv[:3] == ["/usr/bin/sandbox-exec", "-p", profile]
    assert argv[3] == "/Library/Developer/CommandLineTools/usr/bin/git"
    assert "(deny network*)" in profile
    assert "(deny process-exec)" in profile
    assert '(allow process-exec (literal "/Library/Developer/CommandLineTools/usr/bin/git"))' in profile
    assert "--ignore-submodules=none" in argv
    assert "--ignore-submodules=all" not in argv
    assert "--untracked-files=all" in argv

    env = ns["git_env"]()
    assert env["GIT_NO_LAZY_FETCH"] == "1"
    assert env["GIT_ALLOW_PROTOCOL"] == ""

    pinned = {argv[index + 1].split("=", 1)[0] for index, item in enumerate(argv) if item == "-c"}
    assert {
        "protocol.allow", "protocol.file.allow", "protocol.ext.allow", "submodule.recurse",
        "fetch.recurseSubmodules", "status.showUntrackedFiles",
    } <= pinned


def test_a_sandbox_denial_cannot_be_returned_as_a_successful_broker_observation(tmp_path: Path):
    ns = runpy.run_path(str(BROKER))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "tracked.txt").write_text("x\n")
    git_repo(repo)
    (repo / ".gitattributes").write_text("tracked.txt filter=pwn\n")
    payload = tmp_path / "filter.sh"
    sentinel = tmp_path / "PWNED"
    payload.write_text(f"#!/bin/sh\ntouch '{sentinel}'\nprintf 'y\\n'\n")
    payload.chmod(0o700)
    subprocess.run(
        ["/usr/bin/git", "config", "filter.pwn.clean", str(payload)],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    os.utime(repo / "tracked.txt", None)
    anchor_fd = os.open(repo / ".git", os.O_RDONLY | os.O_DIRECTORY)
    try:
        returncode, stdout = ns["run_git"](ns["git_observation_argv"]("status"), anchor_fd)
    finally:
        os.close(anchor_fd)

    assert returncode == 126
    assert stdout == b""
    assert not sentinel.exists()


def test_the_hostile_config_fixture_would_fire_against_an_unpinned_git(repo: Path, retained_git: Path, tmp_path: Path):
    """The control. Without this, every test above could be passing because the fixture is inert.

    Runs the SAME verb template the broker uses, with the same environment, minus only the `-c`
    pins — and proves the sentinel does fire. That is what makes the assertions above evidence.
    """
    git_repo(repo)
    program = tmp_path / "control-bin" / "evil"
    program.parent.mkdir()
    program.write_text('#!/bin/sh\necho fired >> "$(dirname "$0")/sentinel-fired"\nexit 0\n')
    program.chmod(0o700)
    hostile_git_config(repo, "core.fsmonitor", program)
    (repo / "src" / "app.txt").write_text("drafted-to-force-a-refresh\n")
    ns = runpy.run_path(str(BROKER))

    # cwd is the anchor, matching run_git(): git_env()'s GIT_DIR="." is bound to the descriptor
    # this stands in, so the control runs the same binding the broker does — minus only the pins.
    subprocess.run(
        [str(retained_git), "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo / ".git", env=ns["git_env"](), capture_output=True, check=False,
    )

    assert (program.parent / "sentinel-fired").exists(), (
        "the fixture never fires even unpinned; the hostile-config tests would be vacuous"
    )


@pytest.mark.parametrize("verb", sorted(["status", "branch", "head", "diff", "diff_name_only", "diff_stat", "log"]))
def test_every_verb_carries_the_full_inert_config_pin_set(verb: str):
    """Read from the TABLE, not from one lucky invocation: a verb added later gets this for free."""
    ns = runpy.run_path(str(BROKER))
    argv = ns["git_argv"](verb)

    pinned = {argv[i + 1] for i, item in enumerate(argv) if item == "-c"}
    assert set(ns["INERT_GIT_CONFIG"]) <= pinned, f"{verb} is missing inert pins"
    assert "--no-pager" in argv


def test_the_inert_pin_set_names_every_program_valued_key():
    """The pin set is the contract; this is what stops it being quietly shortened."""
    ns = runpy.run_path(str(BROKER))
    pinned = {item.split("=", 1)[0] for item in ns["INERT_GIT_CONFIG"]}

    assert {
        "core.fsmonitor", "core.hooksPath", "log.showSignature", "gpg.program", "gpg.ssh.program",
        "gpg.x509.program", "diff.external", "core.pager", "core.sshCommand", "core.editor",
        "core.askPass", "credential.helper", "core.attributesFile",
    } <= pinned


# --- v16-r32 A: the repository metadata anchor is validated, never followed ---


@pytest.mark.parametrize("shape", ["symlink", "gitfile", "missing", "regular_file"])
def test_a_repo_controlled_git_anchor_indirection_is_refused(
    repo: Path, retained_git: Path, tmp_path: Path, outside: Path, shape: str,
):
    """`.git` decides which repository git answers about, and the draft worker can rewrite it.

    A symlinked `.git` points the whole inspection at a tree the containment never authorized; a
    gitfile (`gitdir: /elsewhere`) does the same in one line of text, and carries `.git/config` —
    every hostile key above — from outside the root. This closed contract refuses the indirection
    rather than following it: a linked worktree fails closed here until an authenticated gitdir
    broker exists, which is the documented cost.
    """
    git_repo(repo)
    real_git = repo / ".git"
    if shape == "symlink":
        elsewhere = tmp_path / "elsewhere.git"
        real_git.rename(elsewhere)
        real_git.symlink_to(elsewhere)
    elif shape == "gitfile":
        elsewhere = tmp_path / "elsewhere.git"
        real_git.rename(elsewhere)
        real_git.write_text(f"gitdir: {elsewhere}\n")
    elif shape == "missing":
        real_git.rename(tmp_path / "elsewhere.git")
    elif shape == "regular_file":
        real_git.rename(tmp_path / "elsewhere.git")
        real_git.write_text("not a gitdir at all\n")

    out = git_call({"op": "git", "root": "repo", "verb": "status", "rel": ""}, repo, retained_git)

    assert out == {"ok": False, "error": "git_repository_anchor_refused"}


def test_the_git_anchor_refusal_never_names_the_path(repo: Path, retained_git: Path, tmp_path: Path):
    elsewhere = tmp_path / "elsewhere.git"
    git_repo(repo)
    (repo / ".git").rename(elsewhere)
    (repo / ".git").symlink_to(elsewhere)

    out = git_call({"op": "git", "root": "repo", "verb": "status", "rel": ""}, repo, retained_git)

    assert str(tmp_path) not in json.dumps(out)


def test_git_discovery_cannot_climb_out_of_the_validated_root(tmp_path: Path, retained_git: Path):
    """Without a bound discovery, a root with no `.git` answers about whatever repo is ABOVE it —
    the containment's own checkout, in the layout this adapter actually runs in."""
    outer = tmp_path / "outer"
    (outer / "inner" / "src").mkdir(parents=True)
    (outer / "inner" / "src" / "app.txt").write_text("hello\n")
    git_repo(outer)

    out = call({"op": "git", "root": "repo", "verb": "status", "rel": ""}, repo=outer / "inner",
               env={"BD_BROKER_GIT": str(retained_git)})

    assert out == {"ok": False, "error": "git_repository_anchor_refused"}


# --- v16-r33 C: git consumes the validated descriptor, and cannot outlive its deadline ---


def fake_git(tmp_path: Path, body: str) -> Path:
    """A stand-in git in the shape trusted_git() requires: 0500, owned, single-linked, under 0700."""
    private = tmp_path / "fake-git-bin"
    private.mkdir(mode=0o700, exist_ok=True)
    target = private / "git"
    target.write_text("#!/bin/sh\n" + body)
    target.chmod(0o500)
    return target


def descendant_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def assert_descendant_dies(pid: int, timeout: float = 5.0) -> None:
    """No survivor — waited for rather than sampled.

    A descendant is reparented to init when its leader exits, so the broker cannot reap it and
    cannot block on it; all it can do is SIGKILL the group, and SIGKILL is delivered asynchronously.
    Sampling `kill(pid, 0)` the instant the refusal returns therefore races the kernel rather than
    testing anything. Polling to a deadline asserts the same fact — nothing survives — without
    asserting a scheduling order that was never promised.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not descendant_alive(pid):
            return
        time.sleep(0.05)
    os.kill(pid, signal.SIGKILL)  # do not leak a 300s sleep into the rest of the run
    raise AssertionError(f"descendant {pid} survived the group kill")


class GitDispatchSpy:
    """Records what run_git() actually hands git, at the Popen seam.

    A stand-in for the `subprocess` NAME in the broker's namespace rather than a patch of the real
    module: the broker resolves `subprocess.Popen` through its own globals, so shimming it there
    leaves the rest of this process — git_repo()'s own subprocess use included — alone.

    The cwd is recorded as an INODE. run_git() fchdir()s to the proven anchor descriptor before it
    spawns, so the identity of what git stands in IS the binding under test, and a pathname is the
    one thing a swap can make lie about it. `os.getcwd()` here would report whatever name the anchor
    currently answers to and prove nothing.
    """

    def __init__(self, after_spawn=None):
        self.dispatched = []
        self._after_spawn = after_spawn

    def __getattr__(self, name):
        return getattr(subprocess, name)  # DEVNULL, PIPE, TimeoutExpired, ...

    def Popen(self, argv, **kw):
        cwd = os.stat(".")
        self.dispatched.append({
            "argv": list(argv),
            "env": dict(kw.get("env") or {}),
            "cwd_id": (cwd.st_dev, cwd.st_ino),
        })
        proc = subprocess.Popen(argv, **kw)
        if self._after_spawn is not None:
            self._after_spawn(proc)
        return proc


def test_git_cannot_be_redirected_by_an_anchor_swapped_after_it_was_validated(
    repo: Path, retained_git: Path, tmp_path: Path, monkeypatch,
):
    """The ABA a pre/post pathname check cannot close, injected where the window actually is.

    A→B→A: the anchor NAME is the attacker's symlink for exactly the span git runs in, and is the
    proven directory again before op_git re-checks it. Both pathname checks therefore see A and
    pass, so nothing but the binding decides which repository answered — which is the only shape in
    which this proves anything. run_git() fchdir()s to the descriptor open_git_anchor() proved and
    pins `GIT_DIR=.`, so git resolves no name and answers about the victim. The old `GIT_DIR=.git`
    resolved that name itself, mid-swap, and answered about the attacker — which is not a claim
    made from reasoning: the control below runs the old binding against this same fixture.

    The anchor is renamed WITHIN the root, not out of it. check_anchor_parent() stats `..` from the
    anchor inode, so an anchor moved to another parent is refused before git ever runs — that is
    what made the first version of this test vacuous, and it is now its own test below.
    """
    attacker = tmp_path / "attacker"
    (attacker / "src").mkdir(parents=True)
    (attacker / "src" / "app.txt").write_text("attacker\n")
    git_repo(attacker, branch="ATTACKERBRANCH")
    git_repo(repo, branch="VICTIMBRANCH")

    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    monkeypatch.setenv("BD_BROKER_GIT", str(retained_git))
    ns = runpy.run_path(str(BROKER))
    globals_ = ns["op_git"].__globals__
    real_open_anchor = globals_["open_git_anchor"]
    real_program_config_audit = globals_["reject_program_git_config"]
    proven = {}

    def open_and_record(root_fd: int) -> int:
        fd = real_open_anchor(root_fd)
        st = os.fstat(fd)
        proven["anchor_id"] = (st.st_dev, st.st_ino)
        return fd

    def audit_then_swap(anchor_fd: int) -> None:
        # The new config audit is itself descriptor-bound Git. Let it finish, then place the swap in
        # the still-live window immediately before the caller-requested verb.
        real_program_config_audit(anchor_fd)
        (repo / ".git").rename(repo / ".git-real")          # ... and the attacker wins the window
        (repo / ".git").symlink_to(attacker / ".git")

    def restore_once_git_has_resolved_it(proc) -> None:
        """The second A, and the wait is what makes the first B mean something.

        Restoring the instant Popen returns would race git's own resolution of GIT_DIR: a restore
        that lands first puts the real anchor back under the name before git ever looks, and the
        test would then pass against a name-bound git too — vacuous in a new way. Waiting for the
        child means the swap covered the WHOLE dispatch window, so what git answered is what the
        binding chose rather than what the scheduler did.

        Waiting on the pipe is safe only because `branch --show-current` writes a dozen bytes: the
        broker's drain thread has not started yet, so a child that filled the pipe buffer would
        block here instead. This is why the verb is `branch` and not `diff`.
        """
        if not (repo / ".git").is_symlink():
            return  # the descriptor-bound config audit runs before this test installs the ABA swap
        proc.wait()
        (repo / ".git").unlink()
        (repo / ".git-real").rename(repo / ".git")

    spy = GitDispatchSpy(after_spawn=restore_once_git_has_resolved_it)
    monkeypatch.setitem(globals_, "open_git_anchor", open_and_record)
    monkeypatch.setitem(globals_, "reject_program_git_config", audit_then_swap)
    monkeypatch.setitem(globals_, "subprocess", spy)
    monkeypatch.setitem(globals_, "prepare_git_exit_watch", lambda _proc: None)
    monkeypatch.setitem(globals_, "git_leader_exited", lambda _proc: True)
    root = ns["open_root"]("repo")
    try:
        out = ns["op_git"]({"op": "git", "root": "repo", "verb": "branch", "rel": ""}, root)
    finally:
        ns["close_root"](root)

    # Dispatch-reached, asserted rather than assumed: both the config audit and requested verb must
    # run, and the latter is the dispatch whose binding the injected ABA swap challenges.
    assert len(spy.dispatched) == 2, "the config audit and requested git verb did not both run"
    handed = spy.dispatched[1]

    assert out == {"ok": True, "output": "VICTIMBRANCH\n"}, "git answered about the swapped-in repo"
    assert handed["cwd_id"] == proven["anchor_id"], "git did not stand in the proven anchor inode"
    assert handed["env"]["GIT_DIR"] == ".", "GIT_DIR is a name git resolves for itself, not the fd"
    assert handed["env"]["GIT_WORK_TREE"] == ".."
    assert ".git" not in handed["argv"]
    assert not any(str(repo) in item for item in handed["argv"]), "argv names a re-resolvable path"
    assert not any(str(repo) in value for value in handed["env"].values())


def test_the_aba_fixture_redirects_a_pathname_bound_git(repo: Path, retained_git: Path, tmp_path: Path):
    """The control. Without it, the ABA test above could be passing because the swap is inert.

    Runs the same verb against the same swapped tree with the OLD binding — a `GIT_DIR` git resolves
    by name from the root — and proves it answers about the attacker. That is what makes the test
    above evidence for the descriptor binding rather than for the fixture doing nothing.
    """
    attacker = tmp_path / "attacker"
    (attacker / "src").mkdir(parents=True)
    (attacker / "src" / "app.txt").write_text("attacker\n")
    git_repo(attacker, branch="ATTACKERBRANCH")
    git_repo(repo, branch="VICTIMBRANCH")
    ns = runpy.run_path(str(BROKER))
    (repo / ".git").rename(repo / ".git-real")
    (repo / ".git").symlink_to(attacker / ".git")

    env = ns["git_env"]()
    env["GIT_DIR"], env["GIT_WORK_TREE"] = ".git", "."   # the second resolution the fix removed
    out = subprocess.run([str(retained_git), "branch", "--show-current"], cwd=repo, env=env,
                         capture_output=True, text=True, check=False)

    assert out.stdout.strip() == "ATTACKERBRANCH", (
        "the swap never redirects even a name-bound git; the ABA test above would be vacuous"
    )


def test_an_anchor_moved_out_of_the_root_fails_closed_before_git_runs(
    repo: Path, retained_git: Path, tmp_path: Path, monkeypatch,
):
    """check_anchor_parent() stats `..` from the anchor INODE, so an anchor moved to another parent
    is refused before git runs: the work tree it would be handed is not the root that was proved.

    Explicit because it is the shape that made the first ABA test vacuous. A swap injected by moving
    the anchor out of the root never reaches the binding it means to test — it is refused two steps
    earlier — so the dispatch count, not the refusal, is the assertion that carries this.
    """
    git_repo(repo, branch="VICTIMBRANCH")
    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    monkeypatch.setenv("BD_BROKER_GIT", str(retained_git))
    ns = runpy.run_path(str(BROKER))
    globals_ = ns["op_git"].__globals__
    real_open_anchor = globals_["open_git_anchor"]

    def open_then_move_out(root_fd: int) -> int:
        fd = real_open_anchor(root_fd)
        (repo / ".git").rename(tmp_path / "stashed.git")
        return fd

    spy = GitDispatchSpy()
    monkeypatch.setitem(globals_, "open_git_anchor", open_then_move_out)
    monkeypatch.setitem(globals_, "subprocess", spy)
    root = ns["open_root"]("repo")
    try:
        with pytest.raises(ns["BrokerError"]) as exc:
            ns["op_git"]({"op": "git", "root": "repo", "verb": "branch", "rel": ""}, root)
    finally:
        ns["close_root"](root)

    assert str(exc.value) == "git_repository_anchor_refused"
    assert spy.dispatched == [], "git ran against an anchor whose parent was never proven"


def test_this_platform_will_not_hand_git_a_directory_through_dev_fd(repo: Path, retained_git: Path):
    """run_git()'s docstring rests on this, so it is checked rather than asserted in prose.

    `/dev/fd/<n>` is the direct way to say "this inode, no name" and is what run_git() would use on
    Linux. Here fdesc gives ENOTDIR for a directory descriptor — it even stats as one, which is the
    trap — so git cannot take an inode that way and the cwd is the only handle left. That is why the
    binding above is `fchdir` + `GIT_DIR=.` rather than the `/dev/fd/<n>` a reader would expect.
    """
    git_repo(repo)
    fd = os.open(repo / ".git", os.O_RDONLY | os.O_DIRECTORY)
    try:
        assert os.path.isdir(f"/dev/fd/{fd}"), "the trap is gone; recheck run_git()'s reasoning"
        with pytest.raises(NotADirectoryError):
            os.open(f"/dev/fd/{fd}", os.O_RDONLY | os.O_DIRECTORY)

        os.set_inheritable(fd, True)
        out = subprocess.run(
            [str(retained_git), "branch", "--show-current"], cwd="/", capture_output=True, text=True,
            env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_DIR": f"/dev/fd/{fd}"},
            pass_fds=(fd,), check=False,
        )
        assert out.returncode != 0, "git now takes a /dev/fd directory; run_git() could bind it there"
    finally:
        os.close(fd)


def test_a_git_that_leaves_a_descendant_holding_the_pipe_cannot_hang_the_broker(
    repo: Path, tmp_path: Path, monkeypatch,
):
    """`stdout.read()` returns when the WRITER closes, not when the deadline expires.

    git exits immediately here and leaves a `sleep` behind holding the inherited pipe. A read on the
    calling thread waits for EOF that no longer has anyone to send it, so the timeout on the wait
    below it is never reached and the broker hangs forever — with its whole containment held open.
    """
    marker = tmp_path / "descendant.pid"
    git = fake_git(tmp_path, f"sleep 300 &\necho $! > {marker}\nexit 0\n")
    git_repo(repo)
    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    ns = runpy.run_path(str(BROKER))
    # The fake Git is injected at the authenticated observation-argv seam. Production has no
    # environment-selected executable; this unit is only about run_git()'s process-group bound.
    monkeypatch.setitem(
        ns["op_git"].__globals__, "git_observation_argv",
        lambda verb: [str(git), *ns["git_argv"](verb)],
    )
    monkeypatch.setitem(ns["run_git"].__globals__, "GIT_TIMEOUT_SECONDS", 2)
    root = ns["open_root"]("repo")
    try:
        with pytest.raises(Exception) as exc:
            ns["op_git"]({"op": "git", "root": "repo", "verb": "status", "rel": ""}, root)
    finally:
        ns["close_root"](root)

    assert str(exc.value) == "git_timeout"
    assert_descendant_dies(int(marker.read_text().strip()))


def test_successful_git_that_leaves_quiet_descendant_is_cleaned_before_leader_reap(
    repo: Path, tmp_path: Path, monkeypatch,
):
    """A quiet descendant does not hold pipes open, so success still needs a pre-reap group cleanup.

    The leader exits 0 and all drains finish normally. If run_git() waits/reaps the leader before it
    signals the group, the PGID is only a recycled number and this descendant survives the successful
    observation. The config-audit invocation returns the expected no-match exit code without spawning
    the descendant so the canary is scoped to the requested git verb.
    """
    marker = tmp_path / "quiet-descendant.pid"
    git = fake_git(
        tmp_path,
        "case \"$*\" in *--get-regexp*) exit 1;; esac\n"
        f"sleep 300 </dev/null >/dev/null 2>/dev/null &\necho $! > {marker}\nexit 0\n",
    )
    git_repo(repo)
    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    ns = runpy.run_path(str(BROKER))
    monkeypatch.setitem(
        ns["op_git"].__globals__, "git_observation_argv",
        lambda verb: [str(git), *ns["git_argv"](verb)],
    )
    root = ns["open_root"]("repo")
    try:
        out = ns["op_git"]({"op": "git", "root": "repo", "verb": "status", "rel": ""}, root)
    finally:
        ns["close_root"](root)

    assert out == {"ok": True, "output": ""}
    assert_descendant_dies(int(marker.read_text().strip()))


def test_git_output_over_the_bound_kills_the_descendant_that_holds_the_pipe(
    repo: Path, tmp_path: Path, monkeypatch,
):
    """Overflow is a refusal, and a refusal that leaves the writer running has not refused anything.

    Killing only on timeout leaves the overflow path returning while the group it spawned still
    holds the pipe and still runs.
    """
    marker = tmp_path / "descendant.pid"
    git = fake_git(tmp_path, f"sleep 300 &\necho $! > {marker}\nprintf 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'\nexit 0\n")
    git_repo(repo)
    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    ns = runpy.run_path(str(BROKER))
    # The fake Git is injected at the authenticated observation-argv seam. Production has no
    # environment-selected executable; this unit is only about run_git()'s process-group bound.
    monkeypatch.setitem(
        ns["op_git"].__globals__, "git_observation_argv",
        lambda verb: [str(git), *ns["git_argv"](verb)],
    )
    monkeypatch.setitem(ns["run_git"].__globals__, "MAX_GIT_OUTPUT_BYTES", 8)
    monkeypatch.setitem(ns["run_git"].__globals__, "GIT_TIMEOUT_SECONDS", 3)
    root = ns["open_root"]("repo")
    try:
        with pytest.raises(Exception) as exc:
            ns["op_git"]({"op": "git", "root": "repo", "verb": "status", "rel": ""}, root)
    finally:
        ns["close_root"](root)

    assert str(exc.value) == "git_output_too_large"
    assert_descendant_dies(int(marker.read_text().strip()))


def test_run_git_baseexception_kills_and_reaps_owned_group_before_reraising(repo: Path, monkeypatch):
    """KeyboardInterrupt must not bypass the broker's owned Git process-group cleanup."""
    git_repo(repo)
    ns = runpy.run_path(str(BROKER))
    anchor_fd = os.open(repo / ".git", os.O_RDONLY | os.O_DIRECTORY)
    original_cwd = os.open(".", os.O_RDONLY)
    state = {"killed": False, "waits": 0}

    class FakePipe:
        def close(self):
            return None

    class FakeProc:
        pid = 4242
        stdout = FakePipe()
        stderr = FakePipe()
        returncode = None

        def wait(self, timeout=None):
            state["waits"] += 1
            if self.returncode is None:
                self.returncode = -signal.SIGKILL
            return self.returncode

    class FakeSubprocess:
        DEVNULL = subprocess.DEVNULL
        PIPE = subprocess.PIPE
        TimeoutExpired = subprocess.TimeoutExpired

        def Popen(self, *args, **kwargs):
            return FakeProc()

    def no_drain(_pipe, _kept, _seen):
        return None

    def kill(proc):
        state["killed"] = True
        proc.returncode = -signal.SIGKILL
        proc.wait(timeout=5)

    def interrupt_exit_watch(_proc):
        raise KeyboardInterrupt("interrupt_during_git_exit_watch")

    globals_ = ns["run_git"].__globals__
    monkeypatch.setitem(globals_, "subprocess", FakeSubprocess())
    monkeypatch.setitem(globals_, "drain_git", no_drain)
    monkeypatch.setitem(globals_, "kill_git_group", kill)
    monkeypatch.setitem(globals_, "prepare_git_exit_watch", lambda _proc: None)
    monkeypatch.setitem(globals_, "git_leader_exited", interrupt_exit_watch)
    try:
        with pytest.raises(KeyboardInterrupt):
            ns["run_git"](["git", "status"], anchor_fd)
    finally:
        os.fchdir(original_cwd)
        os.close(original_cwd)
        os.close(anchor_fd)

    assert state["killed"] is True
    assert state["waits"] >= 1


def test_run_git_kills_the_group_before_reaping_a_leader_whose_drains_outlive_it(repo: Path, monkeypatch):
    """A drain that outlives the leader still needs a group kill, but not after wait() reaped it.

    The process-group ID is the leader's PID. Once wait() has reaped that PID, a later killpg uses a
    number that is no longer owned by this subprocess handle. The safe sequence is: observe leader
    exit without reaping, kill the still-owned group if pipe drains are still live, then reap.
    """
    git_repo(repo)
    ns = runpy.run_path(str(BROKER))
    anchor_fd = os.open(repo / ".git", os.O_RDONLY | os.O_DIRECTORY)
    original_cwd = os.open(".", os.O_RDONLY)
    state = {"kill_returncodes": [], "waits": 0}

    class FakePipe:
        def close(self):
            return None

    class FakeProc:
        pid = 4242
        stdout = FakePipe()
        stderr = FakePipe()
        returncode = None

        def wait(self, timeout=None):
            state["waits"] += 1
            if self.returncode is None:
                self.returncode = 0
            return self.returncode

    class FakeSubprocess:
        DEVNULL = subprocess.DEVNULL
        PIPE = subprocess.PIPE
        TimeoutExpired = subprocess.TimeoutExpired

        def Popen(self, *args, **kwargs):
            return FakeProc()

    class LiveDrain:
        def __init__(self, *args, **kwargs):
            self.joins = 0

        def start(self):
            return None

        def join(self, timeout=None):
            self.joins += 1

        def is_alive(self):
            return True

    class FakeThreading:
        Thread = LiveDrain

    def no_drain(_pipe, _kept, _seen):
        return None

    def leader_exited_without_reaping(proc):
        return True

    def kill(proc):
        state["kill_returncodes"].append(proc.returncode)
        proc.returncode = -signal.SIGKILL
        proc.wait(timeout=5)

    globals_ = ns["run_git"].__globals__
    monkeypatch.setitem(globals_, "subprocess", FakeSubprocess())
    monkeypatch.setitem(globals_, "threading", FakeThreading())
    monkeypatch.setitem(globals_, "drain_git", no_drain)
    monkeypatch.setitem(globals_, "kill_git_group", kill)
    monkeypatch.setitem(globals_, "prepare_git_exit_watch", lambda _proc: None)
    if "git_leader_exited" in globals_:
        monkeypatch.setitem(globals_, "git_leader_exited", leader_exited_without_reaping)
    try:
        with pytest.raises(Exception) as exc:
            ns["run_git"](["git", "status"], anchor_fd)
    finally:
        os.fchdir(original_cwd)
        os.close(original_cwd)
        os.close(anchor_fd)

    assert str(exc.value) == "git_timeout"
    assert state["kill_returncodes"], "a live drain requires killing the owned process group"
    assert all(rc is None for rc in state["kill_returncodes"]), (
        "run_git killed by PGID only after wait() had reaped the leader PID"
    )
    assert state["waits"] >= 1, "the leader still has to be reaped after the group kill"


def test_git_exit_watch_is_registered_before_output_drain_threads_start(tmp_path: Path, monkeypatch):
    ns = runpy.run_path(str(BROKER))
    events: list[str] = []

    class FakePipe:
        def close(self):
            return None

    class FakeProc:
        pid = 12345
        stdout = FakePipe()
        stderr = FakePipe()
        returncode = None

    class FakeSubprocess:
        DEVNULL = subprocess.DEVNULL
        PIPE = subprocess.PIPE
        TimeoutExpired = subprocess.TimeoutExpired

        def Popen(self, *args, **kwargs):
            events.append("popen")
            return FakeProc()

    class FakeThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            events.append("thread")

        def join(self, timeout=None):
            return None

        def is_alive(self):
            return False

    class FakeThreading:
        Thread = FakeThread

    def prepare(proc):
        events.append("watch")
        setattr(proc, "_busdriver_exit_watch", ("waitid", None))

    def kill(proc):
        proc.returncode = 0

    globals_ = ns["run_git"].__globals__
    monkeypatch.setitem(globals_, "subprocess", FakeSubprocess())
    monkeypatch.setitem(globals_, "threading", FakeThreading())
    monkeypatch.setitem(globals_, "prepare_git_exit_watch", prepare)
    monkeypatch.setitem(globals_, "git_leader_exited", lambda _proc: True)
    monkeypatch.setitem(globals_, "kill_git_group", kill)

    original_cwd = os.open(".", os.O_RDONLY)
    anchor_fd = os.open(tmp_path, os.O_RDONLY)
    try:
        code, data = ns["run_git"](["git", "status"], anchor_fd)
    finally:
        os.fchdir(original_cwd)
        os.close(original_cwd)
        os.close(anchor_fd)

    assert code == 0
    assert data == b""
    assert events[:4] == ["popen", "watch", "thread", "thread"]


def test_a_git_that_never_exits_is_killed_at_the_deadline(repo: Path, tmp_path: Path, monkeypatch):
    marker = tmp_path / "descendant.pid"
    git = fake_git(tmp_path, f"sleep 300 &\necho $! > {marker}\nsleep 300\n")
    git_repo(repo)
    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    ns = runpy.run_path(str(BROKER))
    # The fake Git is injected at the authenticated observation-argv seam. Production has no
    # environment-selected executable; this unit is only about run_git()'s process-group bound.
    monkeypatch.setitem(
        ns["op_git"].__globals__, "git_observation_argv",
        lambda verb: [str(git), *ns["git_argv"](verb)],
    )
    monkeypatch.setitem(ns["run_git"].__globals__, "GIT_TIMEOUT_SECONDS", 2)
    root = ns["open_root"]("repo")
    try:
        with pytest.raises(Exception) as exc:
            ns["op_git"]({"op": "git", "root": "repo", "verb": "status", "rel": ""}, root)
    finally:
        ns["close_root"](root)

    assert str(exc.value) == "git_timeout"
    assert_descendant_dies(int(marker.read_text().strip()))


# --- v16-r33 D: an append proves its own final content, not just its final size ---


def test_append_fails_closed_when_the_file_is_overwritten_at_the_same_size(
    tmp_path: Path, monkeypatch,
):
    """The exact-total-size check passes an attacker who keeps the size and replaces the bytes.

    A writer that never took the lock cannot be stopped by it, so the most the broker can promise is
    that it PROVES what it left behind. Size is not that proof: an external overwrite landing on the
    same total is indistinguishable from a clean append, and the broker reports `ok` for a file
    whose contents it did not write and never saw.
    """
    run = tmp_path / "run"
    run.mkdir()
    log = run / "pi-events.jsonl"
    log.write_text("original\n")
    monkeypatch.setenv("BD_BROKER_ROOT_RUN", str(run))
    ns = runpy.run_path(str(BROKER))
    real_write_all = ns["op_append"].__globals__["write_all"]

    def write_then_replace(fd: int, data: bytes) -> None:
        real_write_all(fd, data)
        # Same total size, entirely different bytes — every metadata check still agrees.
        os.truncate(fd, 0)
        os.pwrite(fd, b"F" * (len("original\n") + len(data)), 0)

    monkeypatch.setitem(ns["op_append"].__globals__, "write_all", write_then_replace)
    root = ns["open_root"]("run")
    try:
        with pytest.raises(Exception) as exc:
            ns["op_append"]({"op": "append", "root": "run", "rel": "pi-events.jsonl", "content": "appended\n"}, root)
    finally:
        ns["close_root"](root)

    assert str(exc.value) == "identity_drift"


def test_append_binds_its_success_to_the_exact_bytes_it_appended(tmp_path: Path):
    """The other half: an untouched append still succeeds, and leaves preimage + content."""
    run = tmp_path / "run"
    run.mkdir()
    (run / "pi-events.jsonl").write_text("first\n")

    assert call({"op": "append", "root": "run", "rel": "pi-events.jsonl", "content": "second\n"}, run=run) == {
        "ok": True, "bytes": 7,
    }
    assert (run / "pi-events.jsonl").read_text() == "first\nsecond\n"


# --- v16-r32 B4: success is bound to the LIVE root path, not to a detached descriptor ---


def test_a_write_whose_parent_was_detached_after_the_walk_fails_closed(repo: Path, outside: Path, monkeypatch):
    """The descriptor survives the rename; the containment must not.

    `walk()` proved `src` and then closed every ancestor, so the only thing still held at write time
    was the leaf's parent — an inode an attacker detaches from the tree with one rename while our
    descriptor stays perfectly valid. The bytes then land in a tree that no longer hangs off the
    root the caller named, and the old code reported that as success.

    The write still never reaches `outside` — the descriptor guarantees that much, and this test
    keeps proving it. What is new is that a detached success is no longer reported as one.
    """
    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    ns = runpy.run_path(str(BROKER))

    with pytest.raises(Exception) as exc:
        op_write_with_swap(ns, repo, "src/out.txt", "draft\n", lambda: swap_parent_to_symlink(repo, outside))

    assert str(exc.value) == "ancestry_drift"
    assert not (outside / "out.txt").exists(), "the swapped parent redirected the write out of the root"
    assert sorted(p.name for p in outside.iterdir()) == ["secret.txt"]


def op_write_with_swap(ns: dict, repo: Path, rel: str, content: str, attack):
    """Run the real op_write, landing `attack` in the window after the walk has proved the parent."""
    original = ns["write_all"]
    fired = []

    def once(fd, data):
        original(fd, data)
        if not fired:
            fired.append(True)
            attack()

    ns["op_write"].__globals__["write_all"] = once
    root = ns["open_root"]("repo")
    try:
        return ns["op_write"]({"op": "write", "root": "repo", "rel": rel, "content": content}, root)
    finally:
        ns["close_root"](root)
        ns["op_write"].__globals__["write_all"] = original


@pytest.mark.parametrize("target", ["root", "intermediate"])
def test_a_renamed_root_or_intermediate_parent_fails_closed(repo: Path, tmp_path: Path, target: str):
    """Renaming the ROOT is the same attack one level up, and it must land the same way.

    After `mv repo repo-old`, every descriptor the broker holds still resolves — to a tree the live
    `BD_BROKER_ROOT_REPO` path no longer names. A success here is an audit for a file that, by the
    only name the caller ever supplied, does not exist.
    """
    (repo / "src" / "deep").mkdir()
    ns = runpy.run_path(str(BROKER))
    os.environ["BD_BROKER_ROOT_REPO"] = str(repo)
    try:
        def attack():
            if target == "root":
                repo.rename(tmp_path / "repo-old")
            else:
                (repo / "src").rename(repo / "src-old")

        with pytest.raises(Exception) as exc:
            op_write_with_swap(ns, repo, "src/deep/out.txt", "draft\n", attack)
    finally:
        os.environ.pop("BD_BROKER_ROOT_REPO", None)

    assert str(exc.value) == "ancestry_drift"


def test_an_undisturbed_write_through_a_deep_path_still_succeeds(repo: Path):
    """The ancestry proof must not cost the happy path, at any depth."""
    out = call({"op": "write", "root": "repo", "rel": "a/b/c/d/out.txt", "content": "deep\n"}, repo=repo)

    assert out["ok"] is True
    assert (repo / "a" / "b" / "c" / "d" / "out.txt").read_text() == "deep\n"


def test_the_broker_leaks_no_descriptor_across_a_long_walk(repo: Path, monkeypatch):
    """The chain is held open for the whole op, so it is the chain that must be closed."""
    monkeypatch.setenv("BD_BROKER_ROOT_REPO", str(repo))
    ns = runpy.run_path(str(BROKER))
    before = len(os.listdir("/dev/fd"))

    for _ in range(20):
        root = ns["open_root"]("repo")
        try:
            ns["op_write"]({"op": "write", "root": "repo", "rel": "a/b/c/out.txt", "content": "x\n"}, root)
        finally:
            ns["close_root"](root)

    assert len(os.listdir("/dev/fd")) <= before + 2, "descriptors leaked across repeated ops"


# --- v16-r32 B5: the append total bound is atomic against another cooperating broker ---


def test_an_uncooperative_append_lock_holder_is_bounded_and_refused(tmp_path: Path):
    """The critical section stays exclusive without letting a dead holder wedge the broker.

    Two brokers each read `size = MAX - 10`, each decide their 6 bytes fit, and each append: the
    file ends 2 bytes over a bound both of them honoured. Nothing about O_APPEND prevents it —
    O_APPEND makes each write land at the end atomically, which is exactly what lets both land.

    A non-cooperating same-UID process can also hold the advisory lock forever. The broker must keep
    the atomicity guarantee while returning a structured refusal before its caller's outer deadline.
    """
    import fcntl

    run = tmp_path / "run"
    run.mkdir()
    target = run / "pi-events.jsonl"
    target.write_bytes(b"x" * 16)
    holder = os.open(target, os.O_RDWR)
    try:
        fcntl.flock(holder, fcntl.LOCK_EX)
        proc = subprocess.Popen(
            [sys.executable, "-I", str(BROKER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            env={"PATH": "/usr/bin:/bin", "BD_BROKER_ROOT_RUN": str(run)},
        )
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(json.dumps({"op": "append", "root": "run", "rel": "pi-events.jsonl", "content": "y"}))
        proc.stdin.close()
        assert proc.wait(timeout=3) == 0, "an uncooperative lock holder wedged the broker"
        out = json.loads(proc.stdout.read())
        assert out == {"ok": False, "error": "append_lock_timeout"}
        assert target.stat().st_size == 16, "a timed-out broker still appended"
    finally:
        proc.stdout.close()
        os.close(holder)

    assert target.stat().st_size == 16


def test_typescript_broker_call_has_an_outer_deadline_longer_than_the_lock_budget():
    source = PI_TOOLS.read_text()
    broker_source = BROKER.read_text()
    call = source[source.index("raw = execFileSync("):source.index("const response = JSON.parse(raw)")]

    def numeric_constant(pattern: str, text: str) -> int:
        match = re.search(pattern, text, re.MULTILINE)
        assert match is not None
        return int(match.group(1).replace("_", ""))

    short_timeout = numeric_constant(r"const BROKER_TIMEOUT_MS = ([0-9_]+);", source)
    git_timeout = numeric_constant(r"const BROKER_GIT_TIMEOUT_MS = ([0-9_]+);", source)
    python_git_timeout = numeric_constant(r"^GIT_TIMEOUT_SECONDS = ([0-9]+)$", broker_source)
    python_reap_timeout = numeric_constant(r"^GIT_REAP_SECONDS = ([0-9]+)$", broker_source)

    assert "timeout:" in call, "the TypeScript caller can wait forever even if the broker regresses"
    assert 'request.op === "git" ? BROKER_GIT_TIMEOUT_MS : BROKER_TIMEOUT_MS' in call
    assert git_timeout > (python_git_timeout + python_reap_timeout) * 1000
    assert short_timeout < git_timeout, "non-git operations lost their bounded short deadline"


def test_concurrent_appends_never_grow_the_file_past_the_bound(tmp_path: Path):
    """The property the lock exists for, proved against the real thing: N brokers, one bound."""
    run = tmp_path / "run"
    run.mkdir()
    target = run / "pi-events.jsonl"
    start = MAX_FILE_BYTES - 40
    target.write_bytes(b"x" * start)
    request = json.dumps({"op": "append", "root": "run", "rel": "pi-events.jsonl", "content": "y" * 16})

    procs = [
        subprocess.Popen(
            [sys.executable, "-I", str(BROKER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            env={"PATH": "/usr/bin:/bin", "BD_BROKER_ROOT_RUN": str(run)},
        )
        for _ in range(8)
    ]
    outs = [json.loads(p.communicate(request, timeout=60)[0]) for p in procs]

    granted = sum(1 for out in outs if out.get("ok"))
    assert granted == 2, f"exactly two 16-byte appends fit in 40 bytes; {granted} were granted"
    assert target.stat().st_size == start + granted * 16 <= MAX_FILE_BYTES
    assert all(out["error"] == "size_limit" for out in outs if not out.get("ok"))


def test_an_external_append_during_the_effect_is_detected_and_fails_closed(tmp_path: Path, monkeypatch):
    """A non-cooperating writer takes no lock, so the lock cannot stop it — detection must.

    The final total is rechecked against the exact size the append was authorized for, so bytes
    that arrived from outside the protocol make the success unprovable rather than silent.
    """
    run = tmp_path / "run"
    run.mkdir()
    target = run / "pi-events.jsonl"
    target.write_bytes(b"x" * 16)
    monkeypatch.setenv("BD_BROKER_ROOT_RUN", str(run))
    ns = runpy.run_path(str(BROKER))
    original = ns["write_all"]

    def then_an_outsider_appends(fd, data):
        original(fd, data)
        with open(target, "ab") as handle:  # no flock: the non-cooperating writer
            handle.write(b"SMUGGLED")

    ns["op_append"].__globals__["write_all"] = then_an_outsider_appends
    root = ns["open_root"]("run")
    try:
        with pytest.raises(Exception) as exc:
            ns["op_append"]({"op": "append", "root": "run", "rel": "pi-events.jsonl", "content": "y"}, root)
    finally:
        ns["close_root"](root)
        ns["op_append"].__globals__["write_all"] = original

    assert str(exc.value) == "identity_drift"


def test_an_append_that_would_land_over_the_bound_under_the_lock_is_refused(tmp_path: Path, monkeypatch):
    """The size the bound is checked against must be read INSIDE the lock, not at open time."""
    run = tmp_path / "run"
    run.mkdir()
    target = run / "pi-events.jsonl"
    target.write_bytes(b"x" * 16)
    monkeypatch.setenv("BD_BROKER_ROOT_RUN", str(run))
    ns = runpy.run_path(str(BROKER))
    original = ns["lock_exclusive"]

    def grow_it_first(fd):
        with open(target, "ab") as handle:
            handle.write(b"z" * (MAX_FILE_BYTES - 16))
        original(fd)

    ns["op_append"].__globals__["lock_exclusive"] = grow_it_first
    root = ns["open_root"]("run")
    try:
        with pytest.raises(Exception) as exc:
            ns["op_append"]({"op": "append", "root": "run", "rel": "pi-events.jsonl", "content": "y"}, root)
    finally:
        ns["close_root"](root)
        ns["op_append"].__globals__["lock_exclusive"] = original

    assert str(exc.value) == "size_limit"
    assert target.stat().st_size == MAX_FILE_BYTES
