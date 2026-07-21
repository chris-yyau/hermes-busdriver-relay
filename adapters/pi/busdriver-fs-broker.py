#!/usr/bin/python3
"""Descriptor-bound filesystem broker for the Pi adapter.

The adapter used to precheck a path for symlinked parents and then act on the same path string:
`lstatSync`/`readFileSync`/`mkdirSync`/`openSync`. Between those two resolutions a parent can be
swapped for a symlink, and `O_NOFOLLOW` does not help — it constrains only the final component,
so `repo/src/out.txt` still lands wherever `src` now points. No amount of re-checking closes that:
every pathname check is a check of a name, and the name is resolved again by the call that acts.

Node has no `openat(2)` — no `dir_fd` on `fs.open`, no `*at` family, and `fs.Dir` exposes no
descriptor — so the traversal cannot be made race-free in the adapter's own runtime. This broker
is that traversal, in a runtime that has the syscall: every component below the root is opened
relative to its parent's DESCRIPTOR under `O_DIRECTORY|O_NOFOLLOW`, so a swapped component fails
closed instead of resolving somewhere else, and the directory validated is the directory used.

Protocol: one JSON request on stdin, one JSON response on stdout. Bounded, schema-strict,
credential-free, fail-closed, no arbitrary commands. The root is named by LABEL, never by path —
the caller cannot widen its own containment, because the label resolves against this process's
environment, which only the trusted wrapper sets.

The `git` op is here for the same reason and under the same rule. The adapter used to run
`execFileSync("git", ...)`: PATH-resolved, so the ambient PATH chose the binary, and argv-shaped,
so every caller was one string away from a mutating verb. Read-only git inspection is a filesystem
question about the repository root, and the root is this process's descriptor — so it belongs on
this side of the boundary, where the executable is the wrapper-authenticated retained copy and the
caller picks a LABEL out of a fixed table rather than supplying argv. That is a git inspection
broker; it is deliberately not a command runner.
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import select
import signal
import stat
import subprocess
import sys
import threading
import time

# The adapter's MAX_BD_FILE_BYTES. Restated, not imported: this process is the enforcement point,
# so a caller that forgets its own bound still cannot exceed this one.
MAX_FILE_BYTES = 256 * 1024
# Envelope + JSON escaping over a max-size body, with room to spare. stdin is read to this bound
# and no further: an unbounded read is a memory DoS in a process whose whole job is one small op.
MAX_REQUEST_BYTES = 4 * 1024 * 1024
ROOT_ENV_PREFIX = "BD_BROKER_ROOT_"
# No GIT_ENV. $BD_BROKER_GIT named the executable this process ran; see trusted_git().
TRUSTED_EXECUTABLE_DIGESTS = {
    # git's digest is the CommandLineTools multi-call shim's, byte-identical to python3's (one
    # inode). A supply-chain pin, not an identity check — the path is the identity.
    "git": "31ec19f3253cc0044133c892bf65183a9fdb0cca36dfe04074a46d7201417da5",
    "git-real": "7018952d11ea59620a34ea929ffdcb3252cb0ad4bdfabd61e531a141d6bc1701",
    "sandbox-exec": "2d0d4cb4c8eab07c7261195798388d93c640c7f8db1bece63372946e4b00e91a",
}
# Fixed root-owned system sources, executed in place. No `.resolve()`: it follows symlinks, and a
# symlinked name is what this contract refuses. See _validated_root_owned_source().
TRUSTED_EXECUTABLE_SOURCES = {
    "git": "/usr/bin/git",
    "git-real": "/Library/Developer/CommandLineTools/usr/bin/git",
    "sandbox-exec": "/usr/bin/sandbox-exec",
}
# A diff is as large as the tree the adapter just wrote, so it is bounded at the pipe rather than
# after the fact: `communicate()` buffers whatever git decided to emit before anyone can refuse it.
MAX_GIT_OUTPUT_BYTES = 1024 * 1024
GIT_TIMEOUT_SECONDS = 120
# Advisory append locks protect the atomic size-check/write section, but an unrelated same-UID
# process can hold one forever. This is an enforcement deadline, not a caller-tunable preference.
APPEND_LOCK_TIMEOUT_SECONDS = 1.0
APPEND_LOCK_POLL_SECONDS = 0.01
# What a SIGKILLed group gets to finish dying in. Not part of the deadline: the group is already
# unconditionally dead by here, and this only bounds the reap so a wedged one cannot hang the exit.
GIT_REAP_SECONDS = 5

# The repository metadata anchor. Named once: `open_git_anchor()` proves it and `git_env()` pins
# discovery to it, and those two must be talking about the same entry for either to mean anything.
GIT_ANCHOR = ".git"

# Every git setting that names a PROGRAM git will run while answering a read-only question, pinned
# inert on every verb.
#
# The environment cannot reach these. `git_env()` disables the system and global config files, but
# repo-local `.git/config` is read regardless — and repo-local config is authored by the untrusted
# draft worker whose tree this is. `-c` on the command line is the one lever that outranks it, so
# the pins go there. Empirically (see the contract test's control) a repo-local `core.fsmonitor` is
# a command git executes during `status`, which made this the live hole, not the theoretical one.
#
# Pinned as a set rather than per-verb so a verb added to GIT_VERBS later cannot be added without
# them — `git_argv()` is the only way to build an argv, and it always prepends these.
INERT_GIT_CONFIG = (
    "core.fsmonitor=false",       # a command git runs to refresh the index during `status`
    "core.hooksPath=/dev/null",   # no read-only verb fires a hook today; nothing guarantees that
    "log.showSignature=false",    # turns `log` into a verification, which runs gpg.program
    "gpg.program=false",          # ... and these are the programs it would run. `false` resolves
    "gpg.ssh.program=false",      #     against git_env()'s fixed PATH, so even a live exec is inert.
    "gpg.x509.program=false",
    "diff.external=",             # belt to `--no-ext-diff`'s braces: this one covers every verb
    "core.pager=cat",             # git only pages onto a TTY, and this is a pipe. Pinned anyway.
    "core.sshCommand=false",
    "core.editor=false",
    "core.askPass=",
    "credential.helper=",         # empty resets the helper LIST; this process holds no credential
    "core.attributesFile=/dev/null",  # selects textconv/filter drivers, which are programs
    "protocol.allow=never",       # no object observation is allowed to become a transport
    "protocol.file.allow=never",
    "protocol.ext.allow=never",
    "submodule.recurse=false",    # no recursive command; status still reports submodule dirtiness
    "fetch.recurseSubmodules=false",
    "status.showUntrackedFiles=all",
    "core.fileMode=true",          # repo config must not hide executable-bit integrity drift
)

# `-c` can outrank fixed config names, but attributes choose arbitrary driver names and a same-UID
# writer can change local config between an audit and the requested verb. The kernel boundary is
# therefore the final authority: authenticated Git may exec itself, but no shell, filter, signature
# program or remote helper; network is denied independently.
GIT_OBSERVATION_SANDBOX_PROFILE = (
    '(version 1) '
    '(allow default) '
    '(deny network*) '
    '(deny file-write*) '
    '(allow file-write* (literal "/dev/null")) '
    '(deny process-exec) '
    '(allow process-exec (literal "/Library/Developer/CommandLineTools/usr/bin/git"))'
)

# `.gitattributes` chooses filter and diff driver NAMES, so no finite tuple above can pin every
# attacker-selected program key inert. Audit every program-valued key in those dynamic namespaces
# before any working-tree verb runs, without refusing harmless settings such as `diff.renames`.
# Git normalizes section/variable case but preserves subsection case; the explicit folds keep the
# match independent of that implementation detail.
PROGRAM_GIT_CONFIG_PATTERN = (
    r"^([Ff][Ii][Ll][Tt][Ee][Rr]\..*\."
    r"([Cc][Ll][Ee][Aa][Nn]|[Ss][Mm][Uu][Dd][Gg][Ee]|[Pp][Rr][Oo][Cc][Ee][Ss][Ss])"
    r"|[Dd][Ii][Ff][Ff]\..*\."
    r"([Cc][Oo][Mm][Mm][Aa][Nn][Dd]|[Tt][Ee][Xx][Tt][Cc][Oo][Nn][Vv]))$"
)

# The whole git surface, enumerated: (needs_rel, argv). The caller sends a key from this table, so
# there is no argv to smuggle a verb through and no place a `-c` could be injected. Read-only is a
# property of the table itself, which is why the table is what the contract test reads.
#
# `--no-ext-diff --no-textconv` on every diff: both are repo-configurable hooks that run a command
# of the repository's choosing, and the repository is what an untrusted draft worker just wrote to.
GIT_VERBS = {
    "check_ignore": (True, ("check-ignore", "-q", "--")),
    "status": (False, ("status", "--ignore-submodules=none", "--porcelain=v1", "--untracked-files=all")),
    "branch": (False, ("branch", "--show-current")),
    "head": (False, ("rev-parse", "HEAD")),
    "diff": (False, ("diff", "--no-ext-diff", "--no-textconv")),
    "diff_name_only": (False, ("diff", "--no-ext-diff", "--no-textconv", "--name-only")),
    "diff_stat": (False, ("diff", "--no-ext-diff", "--no-textconv", "--stat")),
    "log": (False, ("log", "--oneline")),
}

_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | _CLOEXEC
# O_NONBLOCK so a FIFO swapped in cannot wedge this process on open. O_NOFOLLOW rejects a symlink
# leaf outright; the fstat below rejects everything else that is not a regular file.
_READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | _CLOEXEC
# Deliberately no O_TRUNC: the identity of the opened inode is checked BEFORE any truncation, so a
# hardlinked or non-regular target is refused while it is still intact rather than after we
# destroyed it. Deliberately no O_CREAT either — open_leaf_for_mutation() adds it with O_EXCL only
# after an open proved the leaf absent, which is what makes `before_hash: null` mean "no file".
# O_RDWR, not O_WRONLY: the before/after hashes are pread from this same descriptor.
_WRITE_FLAGS = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | _CLOEXEC


class BrokerError(Exception):
    """A fail-closed refusal. The message is a fixed token, never file contents."""


def fail(token: str) -> "BrokerError":
    return BrokerError(token)


def check_component(name: str) -> str:
    """A path component the broker will open. The adapter normalizes; this process does not care.

    `..` is the whole point: it is the one component that escapes a descriptor-bound walk, because
    the kernel resolves it against the parent directory rather than the fd we hold.
    """
    if not name or name in (".", "..") or "/" in name or "\0" in name:
        raise fail("path_component_rejected")
    return name


def resolve_root_fd(root: str) -> int:
    """Walk `/`→root component-by-component under `O_DIRECTORY|O_NOFOLLOW` and return the descriptor.

    A `realpath(root) == root` test followed by a fresh path-based `os.open(root)` is a check of a
    name and then a second resolution of that name — the exact check/use gap this broker exists to
    close, reintroduced at the one place the whole containment hangs from. So the descriptor
    validated is the descriptor returned. A swap of any component — final or intermediate — fails
    closed.

    This makes symlink-free canonicality a property we PROVE rather than one we test for: the
    wrapper resolves the root before naming it (`repo.resolve()`), so a component that turns out to
    be a symlink means the path was not canonical after all, and that is refused, not followed.
    Intermediate components are not owner-checked — `/`, `/private`, `/Volumes` are root-owned by
    design. Ownership is the root's own property, checked by the caller on the final descriptor.

    Called twice per operation, and that is the point: once to open, once to re-resolve the LIVE
    path at validation time. See Root.revalidate().
    """
    try:
        fd = os.open("/", _DIR_FLAGS)
    except OSError:
        raise fail("broker_root_unopenable")
    try:
        for part in [p for p in root.split("/") if p != ""]:
            if part in (".", "..") or "\0" in part:
                # `..` against a held descriptor is resolved by the kernel from the parent, not the
                # fd — the one component a descriptor-bound walk cannot contain.
                raise fail("broker_root_not_canonical")
            try:
                nxt = os.open(part, _DIR_FLAGS, dir_fd=fd)
            except OSError as exc:
                # ELOOP (Linux) / ENOTDIR (BSD) over a symlink component, and ENOTDIR over a
                # regular-file component, all say the same thing: this was not a canonical
                # directory path. Any other errno is an ordinary open failure.
                raise fail(
                    "broker_root_not_canonical"
                    if exc.errno in (errno.ELOOP, errno.ENOTDIR)
                    else "broker_root_unopenable"
                )
            os.close(fd)
            fd = nxt
    except BaseException:
        os.close(fd)
        raise
    return fd


class Root:
    """The labelled root: the descriptor the walk is bound to, AND the live path it must stay at.

    A descriptor is not a containment. `fd` survives `rename()` — so after `mv repo repo-old` every
    proof this broker holds still passes, while the path the caller actually named resolves
    somewhere else or nowhere at all. The old code reported that as success: an audit for a file
    that, by the only name the caller ever supplied, does not exist.

    So the root keeps its path and its identity, and revalidate() re-resolves the path from `/` to
    prove the two still agree. That is a different claim from "our descriptor is still valid", and
    it is the one a success is actually asserting.
    """

    __slots__ = ("path", "fd", "dev", "ino")

    def __init__(self, path: str, fd: int, st: os.stat_result):
        self.path, self.fd, self.dev, self.ino = path, fd, st.st_dev, st.st_ino

    def revalidate(self) -> None:
        # Every refusal resolve_root_fd() can raise is drift HERE, and only here: this same path
        # already resolved once, at open time. That it now does not — gone, replaced by a symlink,
        # unopenable — is not a fact about the request's shape, it is the tree moving underneath a
        # request that was already accepted. Reporting `broker_root_unopenable` for a root that was
        # perfectly openable a moment ago names the symptom and hides the attack.
        try:
            fd = resolve_root_fd(self.path)
        except BrokerError:
            raise fail("ancestry_drift")
        try:
            st = os.fstat(fd)
        finally:
            os.close(fd)
        if (st.st_dev, st.st_ino) != (self.dev, self.ino):
            raise fail("ancestry_drift")

    def close(self) -> None:
        try:
            os.close(self.fd)
        except OSError:
            pass


def open_root(label: str) -> Root:
    """Open the labelled root. The label indexes the environment; the caller never names a path."""
    if not isinstance(label, str) or not label.isalnum():
        raise fail("broker_root_label_rejected")
    root = os.environ.get(ROOT_ENV_PREFIX + label.upper())
    if not root:
        raise fail("broker_root_unconfigured")
    if not os.path.isabs(root):
        raise fail("broker_root_not_canonical")
    fd = resolve_root_fd(root)
    try:
        st = os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
            raise fail("broker_root_invalid")
    except BaseException:
        os.close(fd)
        raise
    return Root(root, fd, st)


def close_root(root: Root) -> None:
    root.close()


def component_refusal(parent_fd: int, name: str) -> str:
    """Label a refusal that has ALREADY happened. Diagnostic only; it can never re-authorize.

    `O_DIRECTORY|O_NOFOLLOW` over a symlink is ELOOP on Linux but ENOTDIR on the BSDs, so the errno
    alone cannot tell "a parent was swapped for a symlink" from "a parent is a regular file", and
    the substitution attempt is the one an operator most needs named. This lstat is not a check/use
    gap: the open already failed closed and nothing reopens the name afterwards — the worst a
    racing attacker can do here is change which accurate refusal we report.
    """
    try:
        st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError:
        return "path_component_unopenable"
    return "symlink_escape_refused" if stat.S_ISLNK(st.st_mode) else "path_component_not_a_directory"


def open_dir_component(parent_fd: int, name: str, create: bool) -> int:
    """Open one directory beneath parent_fd, refusing any symlink, and never following one.

    `create` makes a MISSING component, 0700, and reopens it no-follow — it never replaces an
    existing one. The reopen matters: mkdir+open is itself a check/use pair, so what we return is
    always a descriptor we proved by fstat, not one we assumed from a successful mkdir.
    """
    try:
        fd = os.open(name, _DIR_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise fail(component_refusal(parent_fd, name))
        if exc.errno != errno.ENOENT or not create:
            raise fail("path_component_unopenable")
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
            os.fsync(parent_fd)
        except FileExistsError:
            pass  # Lost a benign race with another writer; the reopen below still proves it.
        except OSError:
            raise fail("path_component_uncreatable")
        try:
            fd = os.open(name, _DIR_FLAGS, dir_fd=parent_fd)
        except OSError:
            raise fail("path_component_unopenable")
    try:
        st = os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
            raise fail("path_component_invalid")
    except BaseException:
        os.close(fd)
        raise
    return fd


class Walk:
    """Every directory from the root to the leaf's parent, held open, with the name that reached it.

    The old walk proved each component and then threw the proof away — it closed each ancestor as it
    descended, so the only thing still held at write time was the leaf's parent. That is an inode,
    and an inode is not a location: one `rename()` detaches it from the tree while our descriptor
    stays perfectly valid, and the bytes then land in a directory the root no longer reaches. Every
    check still passed, because every check was about the descriptor.

    So the chain is kept, and every link carries the name it was reached by. revalidate() re-resolves
    each name against its PARENT's descriptor and proves it still names the inode we opened. Chained
    from a root that re-resolves its own absolute path, that is what makes "the live root path still
    reaches this file" something proved rather than assumed at open time.
    """

    __slots__ = ("root", "links")

    def __init__(self, root: Root):
        self.root = root
        self.links: list = []  # [(parent_fd, name, dev, ino, fd)], below the root

    @property
    def fd(self) -> int:
        return self.links[-1][4] if self.links else self.root.fd

    def descend(self, name: str, create: bool) -> None:
        parent_fd = self.fd  # read BEFORE the append, or a link parents itself
        fd = open_dir_component(parent_fd, name, create)
        try:
            st = os.fstat(fd)
        except BaseException:
            os.close(fd)
            raise
        self.links.append((parent_fd, name, st.st_dev, st.st_ino, fd))

    def revalidate(self) -> None:
        self.root.revalidate()
        for parent_fd, name, dev, ino, _fd in self.links:
            try:
                entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except OSError:
                raise fail("ancestry_drift")
            if (entry.st_dev, entry.st_ino) != (dev, ino):
                raise fail("ancestry_drift")

    def close(self) -> None:
        """Never closes root.fd — the Root owns that, and outlives every walk beneath it."""
        while self.links:
            try:
                os.close(self.links.pop()[4])
            except OSError:
                pass


def walk(root: Root, rel: str, create: bool):
    """Descend to the leaf's parent, one descriptor-bound component at a time.

    Returns (Walk, leaf_name). The caller closes the Walk.
    """
    parts = [check_component(part) for part in rel.split("/") if part != ""]
    if not parts:
        raise fail("path_rejected")
    chain = Walk(root)
    try:
        for part in parts[:-1]:
            chain.descend(part, create)
    except BaseException:
        chain.close()
        raise
    return chain, parts[-1]


def fd_identity(st: os.stat_result) -> tuple:
    """Every field that must be unmoved across an operation for it to be one coherent file."""
    return (
        st.st_dev,
        st.st_ino,
        st.st_nlink,
        st.st_uid,
        st.st_mode,
        st.st_size,
        st.st_mtime_ns,
        st.st_ctime_ns,
    )


def check_regular(st: os.stat_result, *, mutation: bool) -> None:
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid():
        raise fail("not_a_regular_owned_file")
    # A hardlink is a second name for these bytes, so a mutation through this one is also a
    # mutation through a path the containment never authorized. Reads tolerate it; writes do not.
    if mutation and st.st_nlink != 1:
        raise fail("hardlinked_target_refused")


def read_fd(fd: int, max_bytes: int) -> bytes:
    chunks = []
    size = 0
    while size <= max_bytes:
        chunk = os.read(fd, 1 << 16)
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
    if size > max_bytes:
        raise fail("size_limit")
    return b"".join(chunks)


def read_leaf(parent_fd: int, name: str, max_bytes: int) -> bytes:
    try:
        fd = os.open(name, _READ_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise fail("symlink_escape_refused")
        if exc.errno == errno.ENOENT:
            raise fail("not_found")
        raise fail("unreadable")
    try:
        st = os.fstat(fd)
        check_regular(st, mutation=False)
        if st.st_size > max_bytes:
            raise fail("size_limit")
        data = read_fd(fd, max_bytes)
        # Same discipline as the gate's baseline read: the opening fstat proves what the file was,
        # only the closing one proves it did not move while we read it.
        if fd_identity(os.fstat(fd)) != fd_identity(st) or len(data) != st.st_size:
            raise fail("identity_drift")
        return data
    finally:
        os.close(fd)


def hash_fd_into(h, fd: int, size: int) -> None:
    """Feed `size` bytes of THIS descriptor into `h`, read positionally.

    `pread` so the hash never disturbs (or is disturbed by) the write offset, and so the bytes
    hashed are the inode's, not whatever the leaf name resolves to on a second lookup. Hashing by
    reopening the name is how an audit ends up describing a file nobody wrote.

    Open-ended rather than returning a digest, because op_append needs to keep hashing: its
    expected value is preimage + content, which is one hash over two sources.
    """
    offset = 0
    while offset < size:
        chunk = os.pread(fd, min(1 << 16, size - offset), offset)
        if not chunk:
            raise fail("identity_drift")  # shrank under us; the audit would be a lie.
        h.update(chunk)
        offset += len(chunk)


def hash_fd(fd: int, size: int) -> str:
    h = hashlib.sha256()
    hash_fd_into(h, fd, size)
    return h.hexdigest()


def write_all(fd: int, data: bytes) -> None:
    """`os.write` is allowed to write less than it was given. One call is a silent truncation."""
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise fail("short_write")
        view = view[written:]


def open_leaf_for_mutation(parent_fd: int, name: str, append: bool):
    """Open the leaf for mutation, creating it only if it is genuinely absent.

    Returns (fd, created). O_CREAT alone cannot tell an absent file from an empty one, and the
    adapter's `before_hash` is exactly that distinction — `null` means "there was no file", not
    "there was an empty file". So: open existing first, and fall back to O_CREAT|O_EXCL, which
    makes the answer a property of the syscall that won rather than of a second lookup.

    O_RDWR, not O_WRONLY: the before/after hashes are read through this same descriptor.
    Deliberately no O_TRUNC — the caller validates the inode BEFORE destroying its contents.
    """
    flags = _WRITE_FLAGS | (os.O_APPEND if append else 0)
    created = False
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise fail("symlink_escape_refused")
        if exc.errno != errno.ENOENT:
            raise fail("unwritable")
        try:
            fd = os.open(name, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent_fd)
        except OSError as exc2:
            # EEXIST: something raced us into this name between the two opens. Refuse rather than
            # retry — whatever now holds the name is not the absent leaf we were asked to create.
            raise fail("identity_drift" if exc2.errno == errno.EEXIST else "unwritable")
        try:
            os.fsync(parent_fd)
        except OSError:
            os.close(fd)
            raise fail("directory_sync_failed")
        created = True
    try:
        check_regular(os.fstat(fd), mutation=True)
    except BaseException:
        os.close(fd)
        raise
    return fd, created


def validate_mutated_leaf(fd: int, parent_fd: int, name: str, opened: os.stat_result, size: int):
    """Prove, after the effect, that it landed on the file we were asked to mutate.

    Two distinct claims, and the second is not implied by the first:
      - the DESCRIPTOR still refers to the same regular, single-linked, owned inode, now exactly
        `size` bytes — the write went where we proved it would; and
      - the directory ENTRY still names that inode — an fd survives its own unlink, so a rename or
        replacement leaves every fstat above perfectly happy while the name the caller asked about
        now points somewhere else entirely.
    A concurrent rename fails closed here rather than returning an audit for another inode.

    The link count is drift here, not `hardlinked_target_refused`: that refusal is open-time, and
    it means "this file already had another authorized name". After the open proved `nlink == 1`,
    a count that is no longer 1 means someone linked or UNLINKED it underneath us — 0 is what
    `os.replace` leaves behind — which is a different fact and deserves its own token.
    """
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid():
        raise fail("not_a_regular_owned_file")
    if (
        (st.st_dev, st.st_ino) != (opened.st_dev, opened.st_ino)
        or st.st_nlink != 1
        or st.st_size != size
    ):
        raise fail("identity_drift")
    try:
        entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError:
        raise fail("identity_drift")
    if (entry.st_dev, entry.st_ino) != (st.st_dev, st.st_ino):
        raise fail("identity_drift")
    return st


def op_read(request, root: Root):
    max_bytes = MAX_FILE_BYTES
    chain, name = walk(root, request["rel"], create=False)
    try:
        data = read_leaf(chain.fd, name, max_bytes)
        # The same claim a write makes: these bytes are what the caller's PATH names right now, not
        # what some detached inode happens to hold.
        chain.revalidate()
    finally:
        chain.close()
    try:
        content = data.decode("utf8")
    except UnicodeDecodeError:
        raise fail("not_utf8_text")
    return {"ok": True, "content": content, "bytes": len(data)}


def op_write(request, root: Root):
    content = request["content"].encode("utf8")
    if len(content) > MAX_FILE_BYTES:
        raise fail("size_limit")
    # create=True: parent creation stays beneath the held root descriptor, so a `mkdir -p` can no
    # more escape than a write can. Nothing is created outside the root, ever — not even the
    # empty file a create-then-validate ordering would leave behind.
    chain, name = walk(root, request["rel"], create=True)
    try:
        parent_fd = chain.fd
        # One descriptor for the whole operation: validate, hash, truncate, write, revalidate, hash.
        # Reopening the name for the before/after hashes would mean the audit describes whatever
        # that name resolved to at hash time — three lookups, three chances to be handed a
        # different inode, and an audit that cannot be trusted precisely when it matters.
        fd, created = open_leaf_for_mutation(parent_fd, name, append=False)
        try:
            opened = os.fstat(fd)
            if opened.st_size > MAX_FILE_BYTES:
                raise fail("size_limit")
            before_hash = None if created else hash_fd(fd, opened.st_size)
            os.ftruncate(fd, 0)  # After the identity check, never before: see _WRITE_FLAGS.
            write_all(fd, content)
            os.fsync(fd)
            hashed = validate_mutated_leaf(fd, parent_fd, name, opened, len(content))
            after_hash = hash_fd(fd, len(content))
            # The hash is the last thing that happens, so it was the last thing left unguarded: a
            # check that ran BEFORE it says nothing about the moment it ended. A rename landing in
            # that window leaves every earlier proof intact while `rel` names another inode, and an
            # in-place rewrite of the same length moves no field the entry binding looks at — the
            # response would hand a reviewer a hash for bytes the file no longer has. Re-proving
            # the entry AND the descriptor's own metadata across the hash is what makes the success
            # a claim about the current name and the bytes actually hashed.
            if fd_identity(validate_mutated_leaf(fd, parent_fd, name, opened, len(content))) != fd_identity(hashed):
                raise fail("identity_drift")
            # ... and the leaf's own proofs say nothing about the tree ABOVE it. Last, after the
            # hash, because it is the same window: everything up to here is a claim about one
            # inode, and this is the claim that the caller's path still reaches that inode.
            chain.revalidate()
        finally:
            os.close(fd)
    finally:
        chain.close()
    return {"ok": True, "before_hash": before_hash, "after_hash": after_hash, "bytes": len(content)}


def lock_exclusive(fd: int) -> None:
    """Serialize this descriptor's whole read-decide-write against every other cooperating broker.

    A structured refusal is observable; an unbounded wait is not. A non-cooperating same-UID
    process can hold the advisory lock indefinitely, so use LOCK_NB under a fixed monotonic deadline.
    """
    deadline = time.monotonic() + APPEND_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                raise fail("append_lock_unavailable")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise fail("append_lock_timeout")
            time.sleep(min(APPEND_LOCK_POLL_SECONDS, remaining))


def op_append(request, root: Root):
    content = request["content"].encode("utf8")
    if len(content) > MAX_FILE_BYTES:
        raise fail("size_limit")
    chain, name = walk(root, request["rel"], create=True)
    try:
        parent_fd = chain.fd
        fd, _created = open_leaf_for_mutation(parent_fd, name, append=True)
        try:
            # The bound is a decision made from a size, so the size and the write it authorizes
            # must be one critical section. Two brokers each read `MAX - 10`, each conclude their
            # 6 bytes fit, and each append: the file ends over a bound both of them honoured.
            # O_APPEND does not help — it makes each write land atomically at the end, which is
            # exactly what lets both land. The lock is what makes the check mean anything.
            lock_exclusive(fd)
            # Re-stat INSIDE the lock: the size read at open time is a size from before we had any
            # right to act on it.
            opened = os.fstat(fd)
            check_regular(opened, mutation=True)
            # `len(content) <= MAX_FILE_BYTES` bounds one REQUEST. The event log is appended to once
            # per tool call, so a per-request bound is a rate, not a bound — the file it builds was
            # bounded by nothing. This bounds the target: an already-oversized file and one that
            # this append would push over both fail closed, so repeated appends converge on the
            # limit instead of walking through it.
            total = opened.st_size + len(content)
            if total > MAX_FILE_BYTES:
                raise fail("size_limit")
            # The preimage, hashed inside the lock and BEFORE the append, is what makes the final
            # digest below an actual binding: preimage + content is a claim about bytes, and only
            # something that read the bytes that were there can make it.
            expected = hashlib.sha256()
            hash_fd_into(expected, fd, opened.st_size)
            expected.update(content)
            write_all(fd, content)
            os.fsync(fd)
            # The event log gets the same final proof as a write: O_APPEND puts the bytes at the
            # end of the inode we opened, so a log line cannot silently land in a renamed-away file.
            validate_mutated_leaf(fd, parent_fd, name, opened, total)
            chain.revalidate()
            # Size is not content, and this is where that stops being a pedantic distinction. A
            # writer that never took the lock cannot be stopped by it, so the most a cooperating
            # broker can promise is that it PROVES what it left behind — and an external overwrite
            # that keeps the total size satisfies every metadata check above while replacing every
            # byte. Re-digesting the descriptor last, after ancestry and identity have agreed, is
            # the only check that can tell those apart. It runs last because a digest of an inode
            # that failed those checks would be a true statement about the wrong file.
            if hash_fd(fd, total) != expected.hexdigest():
                raise fail("identity_drift")
        finally:
            os.close(fd)  # releases the flock with the last descriptor on the open file description
    finally:
        chain.close()
    return {"ok": True, "bytes": len(content)}


def git_env() -> dict:
    """git's whole environment, built from a table rather than filtered from ours.

    A denylist over `os.environ` is the wrong shape for this: it has to name every variable that
    could matter, so the one nobody thought of is inherited. Enumerating instead means a credential
    this process happens to hold — and it holds none by design — cannot reach git at all, and
    neither can a `GIT_*` we have not considered. The repository being inspected was just written
    to by an untrusted draft worker, so every hook, pager, and config source it could reach through
    is turned off here rather than trusted to be absent.
    """
    return {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": "/nonexistent",  # no ~/.gitconfig, no ~/.git-credentials
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        # `status` refreshes the index by default: a write, in the one process whose contract is
        # that it inspects the repository rather than touching it.
        "GIT_OPTIONAL_LOCKS": "0",
        # A partial clone must stay incomplete rather than turning an observation into transport.
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_ALLOW_PROTOCOL": "",
        "GIT_PAGER": "cat",
        "LC_ALL": "C",
        # Discovery, bound to the descriptor open_git_anchor() proved rather than to its name.
        # Without a pin git searches UPWARDS from its cwd for a `.git`, so a root with none quietly
        # answers about whatever repository is above it — this relay's own checkout, in the layout
        # the adapter runs in.
        #
        # `.` rather than `.git` is the ABA fix, and it is load-bearing: run_git() fchdir()s to the
        # proven ANCHOR descriptor, so `.` is that inode and git performs no lookup of its own to
        # get there. A name here would be a second resolution of an entry the draft worker can
        # rewrite between our proof and git's use of it.
        "GIT_DIR": ".",
        # The work tree is then the anchor's parent. `..` is resolved from the proven inode we are
        # standing in, not walked from the filesystem root; op_git proves it is the root it opened
        # both before and after the run.
        "GIT_WORK_TREE": "..",
    }
    # No GIT_LITERAL_PATHSPECS, and not by oversight: `check-ignore` refuses it outright ("pathspec
    # magic not supported by this command: 'literal'", exit 128), so the one verb that takes a
    # caller-supplied pathspec is the one it cannot protect. The magic signature is refused in
    # check_pathspec() instead — at the boundary, where it is a fixed character rather than a git
    # version's opinion.


# =============================================================================================
# Fixed root-owned source execution contract. Copy of the primitive in hermes-busdriver-deliver;
# these are standalone executables with no shared import path, so a contract test asserts the
# copies agree. Refusals are BrokerError here rather than SystemExit, because this process answers
# every failure with a fixed token on its protocol; the tokens are the contract's, unchanged.
#
# The full rationale lives in the deliver copy; the short version: executing a private copy
# relocated the substitutable name instead of removing it. macOS has no fexecve and will not exec
# /dev/fd/N, so the kernel re-resolves a *pathname* at exec time, and any pathname we can write is
# one a same-UID adversary can rename first. The source therefore has to live where the adversary
# cannot write at all: root-owned, non-group/world-writable, root to leaf.
#
# /usr/bin/git is the CommandLineTools shim — same inode as /usr/bin/python3, nlink 78 — so nlink==1
# is waived for it and SF_RESTRICTED (SIP; denies even root) required instead. That shim also
# honours $DEVELOPER_DIR through xcrun, which no ancestry walk can see, so git_env() owns the child
# environment: see ENV_DENIED_FOR_TRUSTED_DISPATCH.
# =============================================================================================

SF_RESTRICTED = 0x00080000  # macOS SIP: modification denied even to root.
_NON_OWNER_WRITABLE = stat.S_IWGRP | stat.S_IWOTH
SHIM_BACKED_SOURCES = frozenset({"git"})
ENV_DENIED_FOR_TRUSTED_DISPATCH = frozenset({
    "DEVELOPER_DIR", "SDKROOT", "XCODE_DEVELOPER_DIR_PATH", "TOOLCHAINS", "XCRUN_CACHE_PATH",
})
MAX_TRUSTED_EXECUTABLE_BYTES = 256 * 1024 * 1024


def _trusted_source_refusal(name: str, reason: str, detail: "str | None" = None) -> "BrokerError":
    if reason == "unavailable" and name == "gh":
        return fail("trusted_root_owned_gh_unavailable")
    return fail("trusted_root_owned_source_" + reason)


def _require_trusted_directory(st: os.stat_result, name: str, component: str) -> None:
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or (st.st_mode & _NON_OWNER_WRITABLE):
        raise _trusted_source_refusal(name, "ancestry_untrusted", component)


def _open_root_owned_ancestry(path: str, name: str) -> int:
    """Walk root-to-parent with O_NOFOLLOW directory descriptors; return the parent fd.

    The fd, not the path: the leaf must be opened relative to the directory just validated.
    Re-opening by full pathname would re-traverse every component and restore the TOCTOU.
    """
    try:
        dir_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    except OSError as exc:
        raise _trusted_source_refusal(name, "ancestry_untrusted", "/") from exc
    try:
        _require_trusted_directory(os.fstat(dir_fd), name, "/")
        for component in path.split("/")[1:-1]:
            try:
                nxt = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=dir_fd,
                )
            except OSError as exc:
                raise _trusted_source_refusal(name, "ancestry_untrusted", component) from exc
            os.close(dir_fd)
            dir_fd = nxt
            _require_trusted_directory(os.fstat(dir_fd), name, component)
    except BaseException:
        os.close(dir_fd)
        raise
    return dir_fd


def _require_trusted_leaf(st: os.stat_result, name: str) -> None:
    if not stat.S_ISREG(st.st_mode):
        raise _trusted_source_refusal(name, "metadata_invalid", "not_regular")
    if st.st_uid != 0 or (st.st_mode & _NON_OWNER_WRITABLE):
        raise _trusted_source_refusal(name, "metadata_invalid", "writable_or_unowned")
    if not (st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
        raise _trusted_source_refusal(name, "metadata_invalid", "not_executable")
    if name in SHIM_BACKED_SOURCES:
        if not (getattr(st, "st_flags", 0) & SF_RESTRICTED):
            raise _trusted_source_refusal(name, "metadata_invalid", "not_sip_restricted")
    elif st.st_nlink != 1:
        raise _trusted_source_refusal(name, "metadata_invalid", "multiply_linked")


def _identity(st: os.stat_result) -> tuple:
    return (
        st.st_dev, st.st_ino, st.st_uid, st.st_gid, st.st_mode,
        st.st_nlink, st.st_size, st.st_mtime_ns, st.st_ctime_ns,
    )


def _read_trusted_source_bytes(fd: int, name: str) -> bytes:
    chunks = []
    total = 0
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_TRUSTED_EXECUTABLE_BYTES:
            raise _trusted_source_refusal(name, "metadata_invalid", "oversized")
        chunks.append(chunk)
    return b"".join(chunks)


def _validated_root_owned_source(path: str, name: str) -> str:
    """Pure seam: production reaches this only via trusted_executable_path(), which supplies the
    path from a frozen table. Tests pass harmless already-root-owned system binaries."""
    expected = TRUSTED_EXECUTABLE_DIGESTS[name]
    if not os.path.isabs(path):
        raise _trusted_source_refusal(name, "metadata_invalid", "not_absolute")
    leaf = path.rsplit("/", 1)[1]
    parent_fd = _open_root_owned_ancestry(path, name)
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=parent_fd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise _trusted_source_refusal(name, "metadata_invalid", "symlink") from exc
            raise _trusted_source_refusal(name, "unavailable", type(exc).__name__) from exc
        try:
            opened = os.fstat(fd)
            _require_trusted_leaf(opened, name)
            data = _read_trusted_source_bytes(fd, name)
            if hashlib.sha256(data).hexdigest() != expected:
                raise _trusted_source_refusal(name, "integrity_failed")
            if _identity(os.fstat(fd)) != _identity(opened):
                raise _trusted_source_refusal(name, "identity_changed", "descriptor")
            final = os.lstat(leaf, dir_fd=parent_fd)
            if (final.st_dev, final.st_ino) != (opened.st_dev, opened.st_ino):
                raise _trusted_source_refusal(name, "identity_changed", "path")
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)
    return path


def trusted_executable_path(name: str) -> str:
    """The only production entry point. Takes a name; the path is not negotiable.

    Revalidated on every call rather than cached: the contract is "validated immediately before
    dispatch", and a cache is a promise about the past.
    """
    source = TRUSTED_EXECUTABLE_SOURCES.get(name)
    if source is None:
        raise _trusted_source_refusal(name, "unsupported")
    return _validated_root_owned_source(source, name)


def trusted_git() -> str:
    """The git this broker runs, from the frozen table — never from the environment.

    $BD_BROKER_GIT used to name it, and the checks below the lookup could not make that safe. They
    proved a SHAPE — regular, ours, unshared, in a private-looking directory — and never once
    proved WHICH BYTES, because the digest deliberately lived in the wrapper. Any file this UID can
    create satisfies every one of those predicates; a same-UID adversary who can set one variable
    on this process, or who can rename the retained copy the variable points at, chose the program
    that then ran with a descriptor on the repository. "The wrapper authenticated it" is a claim
    about a different process, and an environment variable is not a way to inherit a proof.

    So the source is fixed here, root-owned, and validated root-to-leaf immediately before it is
    handed to subprocess — the same contract every other relay uses, and one no variable can
    redirect.
    """
    return str(trusted_executable_path("git"))


def git_global_options() -> list:
    """Git options that must outrank repo-local config for every broker-owned subcommand."""
    argv = ["--no-pager"]
    for pin in INERT_GIT_CONFIG:
        argv += ["-c", pin]
    return argv


def git_argv(verb: str) -> list:
    """One verb's whole argv, minus the executable and the pathspec: pins first, template second.

    The pins live here rather than in each GIT_VERBS template because this is the only way to build
    an argv — so a verb added to the table later gets them whether or not anyone remembered, and the
    contract test can read the property off the builder instead of trusting seven copies of it.

    Order is load-bearing: `-c` and `--no-pager` are git's own options and must precede the
    subcommand, which is why they cannot simply be appended to the template.
    """
    _needs_rel, template = GIT_VERBS[verb]
    return git_global_options() + list(template)


def git_sandbox_argv(args: list) -> list:
    """Bind one Git observation to authenticated OS sandbox and Git bytes."""
    sandbox = trusted_executable_path("sandbox-exec")
    git_real = trusted_executable_path("git-real")
    return [sandbox, "-p", GIT_OBSERVATION_SANDBOX_PROFILE, git_real, *args]


def git_observation_argv(verb: str) -> list:
    return git_sandbox_argv(git_argv(verb))


def open_git_anchor(root_fd: int) -> int:
    """Open `.git` beneath the root descriptor, refusing every indirection rather than following it.

    `.git` decides which repository git answers about, and the untrusted draft worker that just
    wrote this tree can rewrite it. A symlinked `.git` points the whole inspection at a tree the
    containment never authorized. A gitfile — the one-line `gitdir: /elsewhere` git writes for a
    linked worktree — does the same thing in text, and brings `.git/config` with it: every
    program-valued key INERT_GIT_CONFIG pins, sourced from outside the root.

    So the anchor gets exactly what every other component gets: opened relative to a proven
    descriptor under `O_DIRECTORY|O_NOFOLLOW`. A symlink is ELOOP/ENOTDIR, a gitfile is ENOTDIR, an
    absent one is ENOENT — every indirection lands in the same refusal instead of being followed.

    The cost is stated rather than hidden: a linked worktree IS a gitfile, so it fails closed here
    until an authenticated gitdir broker exists. This is a closed contract for one adapter's repo
    root, not a general-purpose git.
    """
    try:
        fd = os.open(GIT_ANCHOR, _DIR_FLAGS, dir_fd=root_fd)
    except OSError:
        raise fail("git_repository_anchor_refused")
    try:
        st = os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
            raise fail("git_repository_anchor_refused")
    except BaseException:
        os.close(fd)
        raise
    return fd


def drain_git(pipe, kept: bytearray, seen: list) -> None:
    """Read this pipe to EOF on a thread of its own, keeping at most one byte past the bound.

    Concurrent with the wait, and that is the whole point. `stdout.read(n)` returns when the WRITER
    closes, not when a deadline expires — so a git that exits leaving a descendant holding the
    inherited pipe blocks a read on the calling thread forever, and the timeout guarding the wait
    below it is never reached. The bound is on what is KEPT; reading continues to EOF so a child
    writing into a pipe nobody drains cannot block instead.

    `os.read` rather than `pipe.read(n)`: the buffered reader waits for the full n bytes or EOF, so
    with a descendant holding the write end it blocks on output already delivered — and an overflow
    that is never SEEN is never refused, it just becomes a timeout. One syscall returns what is
    there, which is what a bound needs to be measured against.
    """
    try:
        fd = pipe.fileno()
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            seen[0] += len(chunk)
            room = MAX_GIT_OUTPUT_BYTES + 1 - len(kept)
            if room > 0:
                kept += chunk[:room]
            if seen[0] > MAX_GIT_OUTPUT_BYTES:
                break  # over the bound: the whole capture goes, so there is nothing left to read for
    except (OSError, ValueError):
        pass  # the write end went away under us; EOF by another name
    finally:
        try:
            pipe.close()
        except (OSError, ValueError):
            pass


def kill_git_group(proc) -> None:
    """SIGKILL the whole session this git leads, not just its leader.

    A descendant is what holds the pipe and what outlives the leader, so killing the leader alone
    refuses the OUTPUT while leaving the process that produced it running. The group is non-empty
    exactly when there is something to kill, and killpg on an empty one is ESRCH — harmless.

    Callers must invoke this before reaping the leader PID. The PGID is the leader PID; once wait()
    has reaped that numeric PID, the subprocess handle no longer owns the name it would pass to
    killpg.
    """
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        proc.wait(timeout=GIT_REAP_SECONDS)
    except (subprocess.TimeoutExpired, OSError):
        pass


def prepare_git_exit_watch(proc) -> None:
    """Register a non-reaping leader-exit watch before the child can escape observation.

    run_git may still need to kill descendants that hold inherited pipes after the leader exits.
    `proc.wait()`/`proc.poll()` would reap the PID first, so the later PGID signal would be addressed
    only by a recycled number. Prefer waitid(WNOWAIT); Apple's production Python 3.9 omits waitid,
    so Darwin uses EVFILT_PROC/NOTE_EXIT, which also reports exit without reaping the leader.
    """
    waitid = getattr(os, "waitid", None)
    required = ("P_PID", "WEXITED", "WNOHANG", "WNOWAIT")
    if waitid is not None and all(hasattr(os, name) for name in required):
        setattr(proc, "_busdriver_exit_watch", ("waitid", None))
        return
    kqueue_required = (
        "kqueue", "kevent", "KQ_FILTER_PROC", "KQ_NOTE_EXIT", "KQ_EV_ADD", "KQ_EV_ONESHOT",
    )
    if not all(hasattr(select, name) for name in kqueue_required):
        raise fail("git_process_exit_watch_unavailable")
    queue = None
    try:
        queue = select.kqueue()
        change = select.kevent(
            proc.pid,
            filter=select.KQ_FILTER_PROC,
            flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
            fflags=select.KQ_NOTE_EXIT,
        )
        queue.control([change], 0, 0)
    except (OSError, ValueError):
        if queue is not None:
            queue.close()
        raise fail("git_process_exit_watch_unavailable")
    setattr(proc, "_busdriver_exit_watch", ("kqueue", queue))


def close_git_exit_watch(proc) -> None:
    watch = getattr(proc, "_busdriver_exit_watch", None)
    setattr(proc, "_busdriver_exit_watch", None)
    if isinstance(watch, tuple) and len(watch) == 2 and watch[0] == "kqueue":
        try:
            watch[1].close()
        except (OSError, ValueError):
            pass


def git_leader_exited(proc) -> bool:
    """Observe leader exit through the prepared waitid or kqueue watch, without reaping it."""
    watch = getattr(proc, "_busdriver_exit_watch", None)
    if not isinstance(watch, tuple) or len(watch) != 2:
        raise fail("git_process_exit_watch_unavailable")
    if watch[0] == "waitid":
        waitid = getattr(os, "waitid", None)
        if waitid is None:
            raise fail("git_process_exit_watch_unavailable")
        try:
            return waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
        except ChildProcessError:
            return True
        except OSError:
            raise fail("git_process_exit_watch_unavailable")
    if watch[0] == "kqueue":
        try:
            return bool(watch[1].control(None, 1, 0))
        except (OSError, ValueError):
            raise fail("git_process_exit_watch_unavailable")
    raise fail("git_process_exit_watch_unavailable")


def check_anchor_parent(anchor_fd: int, root: Root) -> None:
    """Prove `..` of the anchor is the root that was opened — the work tree git is handed.

    `..` is resolved by the kernel from the inode this process is standing in, so it cannot be
    redirected by a symlink the way a pathname component can. It CAN be changed by moving the anchor
    itself into another parent, which is the one thing this catches: git would then answer about the
    proven repository against a tree the containment never authorized.
    """
    try:
        parent = os.stat("..", dir_fd=anchor_fd)
    except OSError:
        raise fail("git_repository_anchor_refused")
    if (parent.st_dev, parent.st_ino) != (root.dev, root.ino):
        raise fail("git_repository_anchor_refused")


def run_git(argv: list, anchor_fd: int) -> tuple:
    """Run git against the anchor DESCRIPTOR, with a real deadline and its output bounded at the pipe.

    Two bindings, and the first is why this takes the anchor rather than the root. `GIT_DIR=.git`
    made git resolve the anchor's NAME for itself — a second lookup of the same entry the broker had
    just proved through a descriptor, with the untrusted draft worker owning the tree in between.
    Re-proving the name afterwards detects that swap but cannot contain it: git has already run
    against whatever the name pointed at, which means it has already read that repository's
    `.git/config`, and INERT_GIT_CONFIG only covers the keys we thought of.

    So the cwd IS the proven anchor inode and `GIT_DIR=.` resolves to it — no name, no second
    lookup, nothing for a swap to act on. `/dev/fd/<fd>` would say this more directly and is what
    Linux would use, but this platform's fdesc gives ENOTDIR for a directory descriptor (proved by
    the contract test's control), so the cwd is the only handle git will take an inode through.
    `GIT_WORK_TREE=..` is then the anchor's parent, checked against the proven root by op_git.
    """
    os.fchdir(anchor_fd)
    try:
        proc = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            # Git may exit zero after a sandbox-denied filter and emit a partial, falsely clean
            # status on stdout. Capture stderr under the same bound, but never relay its
            # repository-controlled prose: any byte makes the observation fail closed below.
            stderr=subprocess.PIPE, env=git_env(), close_fds=True,
            # Its own session, so one killpg reaches every descendant it spawns.
            start_new_session=True,
        )
    except OSError:
        raise fail("git_unavailable")
    try:
        # Darwin's kqueue registration can lose a short-lived PID once drain-thread startup has
        # yielded. Register immediately after Popen, before starting any other work. The unavoidable
        # Popen-to-registration window remains fail-closed: a vanished PID refuses the observation.
        prepare_git_exit_watch(proc)
    except BaseException:
        try:
            if getattr(proc, "returncode", None) is None:
                kill_git_group(proc)
        finally:
            for pipe in (getattr(proc, "stdout", None), getattr(proc, "stderr", None)):
                if pipe is not None:
                    try:
                        pipe.close()
                    except (OSError, ValueError):
                        pass
            close_git_exit_watch(proc)
        raise
    kept, seen = bytearray(), [0]
    err_kept, err_seen = bytearray(), [0]
    drain = threading.Thread(target=drain_git, args=(proc.stdout, kept, seen), daemon=True)
    err_drain = threading.Thread(target=drain_git, args=(proc.stderr, err_kept, err_seen), daemon=True)
    drain.start()
    err_drain.start()
    deadline = time.monotonic() + GIT_TIMEOUT_SECONDS
    try:
        leader_exited = False
        while True:
            if seen[0] > MAX_GIT_OUTPUT_BYTES or err_seen[0] > MAX_GIT_OUTPUT_BYTES:
                kill_git_group(proc)
                drain.join(timeout=GIT_REAP_SECONDS)
                err_drain.join(timeout=GIT_REAP_SECONDS)
                raise fail("git_output_too_large")
            if git_leader_exited(proc):
                leader_exited = True
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                kill_git_group(proc)
                drain.join(timeout=GIT_REAP_SECONDS)
                err_drain.join(timeout=GIT_REAP_SECONDS)
                if seen[0] > MAX_GIT_OUTPUT_BYTES or err_seen[0] > MAX_GIT_OUTPUT_BYTES:
                    raise fail("git_output_too_large")
                raise fail("git_timeout")
            time.sleep(min(0.01, remaining))

        # The leader exited but has NOT been reaped. That keeps its PID owned while pipe drains prove
        # whether descendants still exist; if they do, killpg still targets this git's group.
        if not leader_exited:
            raise fail("git_process_exit_watch_unavailable")
        drain.join(timeout=max(0.0, deadline - time.monotonic()))
        err_drain.join(timeout=max(0.0, deadline - time.monotonic()))
        if drain.is_alive() or err_drain.is_alive():
            kill_git_group(proc)
            drain.join(timeout=GIT_REAP_SECONDS)
            err_drain.join(timeout=GIT_REAP_SECONDS)
            if seen[0] > MAX_GIT_OUTPUT_BYTES or err_seen[0] > MAX_GIT_OUTPUT_BYTES:
                raise fail("git_output_too_large")
            raise fail("git_timeout")
        if seen[0] > MAX_GIT_OUTPUT_BYTES or err_seen[0] > MAX_GIT_OUTPUT_BYTES:
            # Refusing the output while the group that authored it still runs is not a refusal.
            kill_git_group(proc)
            raise fail("git_output_too_large")
        # Even a successful, quiet leader can leave same-session descendants after closing stdio.
        # The exit watch kept the leader PID unreaped exactly so this group signal still targets
        # the process group this run owns before wait() releases the numeric PGID.
        kill_git_group(proc)
        if getattr(proc, "returncode", None) is None:
            raise fail("git_timeout")
        if err_seen[0]:
            return 126, b""
        return proc.returncode, bytes(kept)
    except BaseException:
        try:
            if getattr(proc, "returncode", None) is None:
                kill_git_group(proc)
        finally:
            for pipe in (getattr(proc, "stdout", None), getattr(proc, "stderr", None)):
                if pipe is not None:
                    try:
                        pipe.close()
                    except (OSError, ValueError):
                        pass
            for thread in (drain, err_drain):
                try:
                    thread.join(timeout=GIT_REAP_SECONDS)
                except BaseException:
                    pass
        raise
    finally:
        close_git_exit_watch(proc)


def reject_program_git_config(anchor_fd: int) -> None:
    """Fail closed if effective local/worktree config defines an attacker-selected program namespace.

    `--includes` makes indirect include/includeIf files part of the audit. Omitting a scope flag is
    deliberate: with system/global config disabled, this reads both ordinary local config and the
    effective `config.worktree` selected by `extensions.worktreeConfig`. `--name-only` prevents an
    attacker-authored command VALUE from crossing the subprocess boundary even as inert output.
    `--get-regexp` returns 0 for a match, 1 for no match, and another status for an audit failure.
    """
    argv = git_sandbox_argv([
        *git_global_options(),
        "config",
        "--includes",
        "--name-only",
        "--get-regexp",
        PROGRAM_GIT_CONFIG_PATTERN,
    ])
    code, data = run_git(argv, anchor_fd)
    if code == 0:
        raise fail("git_program_config_refused")
    if code != 1 or data:
        raise fail("git_config_audit_failed")


def check_pathspec(rel: str) -> str:
    """The one caller-supplied string git ever sees. It is a path, so prove it is only a path.

    Two things a pathspec is that a pathname is not:

      * MAGIC. A leading `:` opens a small language — `:(glob)**`, `:!x`, `:(attr:...)` — that
        makes check-ignore answer a different question than the caller's path asked, and that
        question is the whole of the ignored-path protection. Magic is only recognized at the
        start, so refusing a leading `:` closes all of it.
      * NORMALIZABLE. `walk()` can afford to drop a leading `/`, because whatever it rebuilds is
        still opened under the root descriptor. git resolves its own pathname, so quietly reading
        `/etc/passwd` as `etc/passwd` would answer about a file nobody named. One name, one
        reading: the components must already spell exactly what was sent.

    What is left is glob wildcards, which git applies to any pathspec. They can only ever ADD
    matches, and `check-ignore -q` returns "ignored" if ANY match is ignored — so a wildcard can
    make this protection refuse more, never less. That is the safe direction, and it is why the
    remaining surface is left alone rather than parsed.
    """
    if rel.startswith(":"):
        raise fail("pathspec_magic_refused")
    parts = [check_component(part) for part in rel.split("/") if part != ""]
    if not parts or "/".join(parts) != rel:
        raise fail("path_rejected")
    return rel


def op_git(request, root: Root):
    entry = GIT_VERBS.get(request["verb"])
    if entry is None:
        raise fail("git_verb_rejected")
    needs_rel, _template = entry
    rel = request["rel"]
    if needs_rel:
        argv = [*git_observation_argv(request["verb"]), check_pathspec(rel)]
    elif rel != "":
        # `rel` is not read by this verb, so a non-empty one is two sides disagreeing about the
        # request — and an unnoticed disagreement is how a containment quietly stops applying.
        raise fail("request_schema_rejected")
    else:
        argv = git_observation_argv(request["verb"])
    anchor_fd = open_git_anchor(root.fd)
    try:
        anchor = os.fstat(anchor_fd)
        # The work tree git is about to be given is `..` of this anchor, so prove it is the root we
        # opened BEFORE git reads a byte through it, rather than reporting on a tree that was never
        # authorized and noticing afterwards.
        check_anchor_parent(anchor_fd, root)
        reject_program_git_config(anchor_fd)
        code, data = run_git(argv, anchor_fd)
        # GIT_DIR was the descriptor above, so the repository git answered about needs no re-proving
        # — there was no name for a swap to act on. These two are the WORK TREE's, which `..` and
        # the root path still reach by name: a swap inside the window makes the answer unprovable
        # rather than quietly about another tree.
        check_anchor_parent(anchor_fd, root)
        try:
            current = os.stat(GIT_ANCHOR, dir_fd=root.fd, follow_symlinks=False)
        except OSError:
            raise fail("git_repository_anchor_refused")
        if (current.st_dev, current.st_ino) != (anchor.st_dev, anchor.st_ino):
            raise fail("git_repository_anchor_refused")
        root.revalidate()
    finally:
        os.close(anchor_fd)
    if request["verb"] == "check_ignore":
        # The exit code IS the answer here: 0 ignored, 1 not ignored, anything else a real failure.
        if code not in (0, 1):
            raise fail("git_failed")
        return {"ok": True, "ignored": code == 0}
    if code != 0:
        raise fail("git_failed")
    try:
        return {"ok": True, "output": data.decode("utf8")}
    except UnicodeDecodeError:
        raise fail("not_utf8_text")


OPS = {
    "read": (op_read, ("op", "root", "rel")),
    "write": (op_write, ("op", "root", "rel", "content")),
    "append": (op_append, ("op", "root", "rel", "content")),
    "git": (op_git, ("op", "root", "verb", "rel")),
}


def handle(raw: bytes):
    try:
        request = json.loads(raw.decode("utf8"))
    except (ValueError, UnicodeDecodeError):
        raise fail("request_not_json")
    if not isinstance(request, dict):
        raise fail("request_not_object")
    entry = OPS.get(request.get("op"))
    if entry is None:
        raise fail("op_rejected")
    handler, allowed = entry
    # Schema-strict both ways: an unknown key is a protocol the two sides disagree about, and an
    # unnoticed disagreement about a filesystem request is how containment quietly stops applying.
    if set(request) != set(allowed):
        raise fail("request_schema_rejected")
    for key in allowed:
        if not isinstance(request[key], str):
            raise fail("request_schema_rejected")
    root = open_root(request["root"])
    try:
        return handler(request, root)
    finally:
        close_root(root)


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        response = {"ok": False, "error": "request_too_large"}
    else:
        try:
            response = handle(raw)
        except BrokerError as exc:
            response = {"ok": False, "error": str(exc)}
        except OSError:
            # Never leak errno text: it carries the absolute path this process was pointed at.
            response = {"ok": False, "error": "broker_os_error"}
    sys.stdout.write(json.dumps(response))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
