"""The fixed root-owned source execution contract.

r26..r34 executed a *private copy*: read the pinned bytes, write them to a 0700 temp dir, exec the
copy. That never removed the substitutable name, it only moved it into a directory the adversary
still owns. macOS has no `fexecve` and refuses to exec `/dev/fd/N`, so the kernel re-resolves a
*pathname* at exec time; any pathname we can write is one a same-UID adversary can rename between
our last check and that re-resolution. r34 proved it with a two-rename ABA (rename ours aside, move
theirs in — `st_nlink` stays 1 and every descriptor-visible field still matches).

The contract under test replaces that with: exec a fixed root-owned system path in place, after
proving every component root-to-leaf is root-owned and not group/world writable. The validation's
job is not to win a race — it is to prove no race exists, because a same-UID, non-root adversary
has no write access anywhere on the path.

These tests pin the four properties the decision named, plus the rename/symlink/ancestor-writability
cases. They deliberately use already-root-owned harmless system binaries (`/usr/bin/jq`, `/bin/bash`)
and real user-writable paths as fixtures rather than weakening production validation with an
injectable source path: `trusted_executable_path()` takes a NAME and gets its path from a frozen
table, and that is the only production entry point.
"""
import ast
import copy
import os
import runpy
import stat
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SF_RESTRICTED = 0x00080000

# The scripts that carry the contract. Each is loaded once and exercised through the same
# assertions, because the codebase copies primitives across standalone scripts rather than
# importing them — a property that has repeatedly let one copy drift.
CONTRACT_SCRIPTS = (
    "hermes-busdriver-deliver",
    "hermes-busdriver-delivery-status",
    "hermes-busdriver-pr-grind-check",
)


@pytest.fixture(scope="module")
def namespaces() -> dict[str, dict]:
    return {name: runpy.run_path(str(ROOT / "scripts" / name)) for name in CONTRACT_SCRIPTS}


@pytest.fixture(params=CONTRACT_SCRIPTS)
def ns(request, namespaces) -> dict:
    return namespaces[request.param]


def _err(exc: BaseException) -> str:
    return str(exc)


# --------------------------------------------------------------------------------------------
# The frozen source table: fixed root-owned paths, no override surface.
# --------------------------------------------------------------------------------------------


def test_sources_are_the_fixed_root_owned_system_paths(ns):
    assert ns["TRUSTED_EXECUTABLE_SOURCES"]["git"] == Path("/usr/bin/git")
    assert ns["TRUSTED_EXECUTABLE_SOURCES"]["jq"] == Path("/usr/bin/jq")
    # Credential-bearing gh is bound to exactly one root-owned path. Homebrew is not it.
    assert ns["TRUSTED_EXECUTABLE_SOURCES"]["gh"] == Path("/usr/local/bin/gh")


def test_no_trusted_source_resolves_into_homebrew(ns):
    for name, path in ns["TRUSTED_EXECUTABLE_SOURCES"].items():
        assert not str(path).startswith("/opt/homebrew"), name


def test_trusted_dispatch_path_excludes_user_writable_homebrew(ns, monkeypatch):
    """The PATH a credential-bearing git/gh child searches must not contain a uid=501 directory.

    /usr/bin winning for names present in both is not a defence: any name /usr/bin lacks —
    git-credential-* being the obvious one — resolves into /opt/homebrew/bin, which is drwxrwxr-x.
    """
    for builder in ("safe_git_env", "safe_subprocess_env", "child_env"):
        if builder not in ns:
            continue
        try:
            env = ns[builder]()
        except TypeError:
            env = ns[builder](None)
        assert "/opt/homebrew" not in env.get("PATH", ""), builder


def test_unknown_name_is_refused_rather_than_resolved(ns):
    with pytest.raises((RuntimeError, SystemExit, ValueError)):
        ns["trusted_executable_path"]("unmanifested-executable")


# --------------------------------------------------------------------------------------------
# Property 1 — Homebrew and user-writable ancestry are rejected.
# --------------------------------------------------------------------------------------------


def test_homebrew_gh_is_rejected_for_user_writable_ancestry(ns):
    """/opt/homebrew/bin is uid=501 drwxrwxr-x — user *and* group writable, and a symlink farm."""
    homebrew_gh = Path("/opt/homebrew/bin/gh")
    if not homebrew_gh.exists():
        pytest.skip("homebrew gh absent on this host")
    with pytest.raises((RuntimeError, SystemExit)) as excinfo:
        ns["_validated_root_owned_source"](homebrew_gh, "gh")
    assert "ancestry_untrusted" in _err(excinfo.value) or "metadata_invalid" in _err(excinfo.value)


def test_user_writable_ancestor_is_rejected_even_with_a_root_owned_leaf(ns, tmp_path):
    """The leaf being perfect is not enough: a writable *ancestor* is a rename primitive."""
    nested = tmp_path / "bin"
    nested.mkdir()
    leaf = nested / "jq"
    leaf.write_bytes(b"#!/bin/sh\n")
    leaf.chmod(0o755)
    with pytest.raises((RuntimeError, SystemExit)) as excinfo:
        ns["_validated_root_owned_source"](leaf, "jq")
    assert "ancestry_untrusted" in _err(excinfo.value) or "metadata_invalid" in _err(excinfo.value)


def test_symlinked_component_is_rejected(ns, tmp_path):
    """No symlink surprises: a symlinked *directory* component must not be traversed."""
    real = tmp_path / "real"
    real.mkdir()
    (real / "jq").write_bytes(b"x")
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises((RuntimeError, SystemExit)):
        ns["_validated_root_owned_source"](link / "jq", "jq")


def test_symlinked_leaf_to_a_trusted_target_is_rejected(ns, tmp_path):
    """A symlink whose target is genuinely root-owned is still refused: the *name* is writable."""
    link = tmp_path / "jq"
    link.symlink_to("/usr/bin/jq")
    with pytest.raises((RuntimeError, SystemExit)):
        ns["_validated_root_owned_source"](link, "jq")


def test_symlink_leaf_is_refused_even_with_perfect_root_owned_ancestry(ns):
    """The symlink check on its own terms, with the ancestry check taken out of the picture.

    The tmp_path symlink tests above are refused for ancestry before the leaf is ever opened, so
    they prove nothing about O_NOFOLLOW. /usr/local/bin/code is the real shape this needs: a
    root-owned symlink inside a root-owned 0755 directory. Ancestry passes; the leaf must still be
    refused, and refused *as a symlink* rather than as a missing file.
    """
    probe = Path("/usr/local/bin/code")
    if not probe.is_symlink():
        pytest.skip("no root-owned symlink available in /usr/local/bin on this host")
    with pytest.raises((RuntimeError, SystemExit)) as excinfo:
        ns["_validated_root_owned_source"](probe, "jq")
    assert "symlink" in _err(excinfo.value), _err(excinfo.value)


# --------------------------------------------------------------------------------------------
# Property 2 — a validated root-owned path cannot be substituted by a same-UID attacker.
# --------------------------------------------------------------------------------------------


def test_root_owned_source_validates_and_is_returned_in_place(ns):
    """The positive case: /usr/bin/jq is accepted and returned AS ITSELF, not as a copy."""
    resolved = ns["_validated_root_owned_source"](Path("/usr/bin/jq"), "jq")
    assert resolved == Path("/usr/bin/jq")


def test_validated_path_is_not_a_private_copy(ns):
    """The whole point of the migration: no temp-dir copy is materialized or executed."""
    resolved = ns["trusted_executable_path"]("jq")
    assert resolved == Path("/usr/bin/jq")
    st = os.lstat(resolved)
    assert st.st_uid == 0, "a same-UID adversary must not own the exec source"
    assert not (st.st_mode & (stat.S_IWGRP | stat.S_IWOTH))


def test_same_uid_attacker_cannot_rename_over_the_validated_source():
    """The ABA that killed the private-copy design is *not available* against a root-owned dir.

    This is the load-bearing claim of the whole architecture, so it is asserted against the kernel
    rather than argued in a comment: the two-rename substitution r34 used needs write access to the
    directory, and /usr/bin denies it to us.
    """
    assert os.getuid() != 0, "this test is meaningless as root"
    with pytest.raises(PermissionError):
        os.rename("/usr/bin/jq", "/usr/bin/jq.aba-aside")
    with pytest.raises(PermissionError):
        open("/usr/bin/hermes-aba-probe", "wb").close()


def test_ancestry_of_every_production_source_is_root_owned_and_unwritable(ns):
    """Root-to-leaf, for real, on this host — the claim the contract rests on."""
    for name, path in ns["TRUSTED_EXECUTABLE_SOURCES"].items():
        components = [Path("/")] + [Path(*path.parts[: i + 1]) for i in range(1, len(path.parts) - 1)]
        for component in components:
            st = os.lstat(component)
            assert st.st_uid == 0, f"{name}: {component} is not root-owned"
            assert not (st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)), f"{name}: {component} is writable"
            assert not stat.S_ISLNK(st.st_mode), f"{name}: {component} is a symlink"


# --------------------------------------------------------------------------------------------
# Property 3 — missing /usr/local/bin/gh blocks BEFORE the credential env is built.
# --------------------------------------------------------------------------------------------


def test_missing_root_owned_gh_fails_closed_with_the_named_reason(ns):
    if Path("/usr/local/bin/gh").exists():
        pytest.skip("gh has been provisioned; the absent-path contract no longer applies")
    with pytest.raises((RuntimeError, SystemExit)) as excinfo:
        ns["trusted_executable_path"]("gh")
    assert "trusted_root_owned_gh_unavailable" in _err(excinfo.value)


@pytest.mark.parametrize("script", CONTRACT_SCRIPTS)
def test_gh_resolution_precedes_credential_construction(script):
    """Ordering, not just outcome: a token must never reach a child env we then refuse to use.

    This is asserted structurally rather than by monkeypatching the namespace, because
    `runpy.run_path` hands back a *copy* of the module globals — rebinding a name in that copy is
    invisible to the functions, so the obvious "make the credential builder explode" test would
    pass while proving nothing. The dispatch wrapper's source is the honest evidence: in every
    dispatch function that both resolves a trusted executable and injects a credential, the resolve
    must come first.

    v16-r34c: a CALL to a credential-building function counts as injecting one, and the builders are
    derived rather than listed. The predecessor only looked for the credential key spelled inside
    the same function, so it saw nothing once pr-grind-check's resolve and its
    `safe_github_helper_env()` moved into different functions — and `checked` fell to 0, which is
    the one thing this test's final assertion exists to catch. Following the call is also strictly
    more coverage than before: `run()` resolves and then builds a token-bearing env through
    `safe_subprocess_env()`, an ordering nothing checked when the key had to appear inline.
    """
    source = (ROOT / "scripts" / script).read_text()
    tree = ast.parse(source)
    credential_keys = {"GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN"}

    def _names_a_credential(node) -> bool:
        return any(
            isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in credential_keys
            for n in ast.walk(node)
        )

    # Derived, never typed: any function that names a credential key is a function that can put one
    # in a dict, so calling it is indistinguishable from injecting one here.
    builders = {
        func.name
        for func in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        if _names_a_credential(func)
    }
    assert builders or script == "hermes-busdriver-delivery-status", (
        f"{script}: no credential builder found — key spelling changed?"
    )

    checked = 0
    for func in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
        resolves = [
            n.lineno
            for n in ast.walk(func)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "trusted_executable_path"
        ]
        # Three spellings of "a credential enters the child env here": deliver names the keys
        # inline, delivery-status delegates to child_env(credentials=True), and pr-grind-check
        # calls a builder that names them. All are credential construction and all must be ordered
        # after the resolve.
        credentials = [
            n.lineno
            for n in ast.walk(func)
            if (
                isinstance(n, ast.Constant)
                and isinstance(n.value, str)
                and n.value in credential_keys
            )
            or (
                isinstance(n, ast.Call)
                and any(
                    k.arg == "credentials"
                    and isinstance(k.value, ast.Constant)
                    and k.value.value is True
                    for k in n.keywords
                )
            )
            or (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id in builders
                and n.func.id != func.name
            )
        ]
        if not resolves or not credentials:
            continue
        checked += 1
        assert max(resolves) < min(credentials), (
            f"{script}:{func.name} injects a credential at line {min(credentials)} "
            f"before/while resolving the trusted executable at line {max(resolves)}"
        )
    assert checked, f"{script}: no dispatch function both resolves and injects — seam moved?"


def test_missing_gh_refuses_before_any_credential_is_read(ns, monkeypatch):
    """Behavioural half: with tokens in the environment, resolution still refuses and reads none."""
    if Path("/usr/local/bin/gh").exists():
        pytest.skip("gh has been provisioned; the absent-path contract no longer applies")
    read: list[str] = []
    real_environ_get = os.environ.get

    def tracking_get(key, default=None):
        if key in {"GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN"}:
            read.append(key)
        return real_environ_get(key, default)

    for key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN"):
        monkeypatch.setenv(key, "sentinel-token-must-not-be-read")
    monkeypatch.setattr(os.environ, "get", tracking_get)
    with pytest.raises((RuntimeError, SystemExit)) as excinfo:
        ns["trusted_executable_path"]("gh")
    assert "trusted_root_owned_gh_unavailable" in _err(excinfo.value)
    assert read == [], f"credential env was read during a refusal: {read}"


# --------------------------------------------------------------------------------------------
# Property 4 — no caller/env/PATH override can select another executable.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "var",
    [
        "HERMES_BUSDRIVER_PRIVATE_RUNTIME",
        "PATH",
        "GH_PATH",
        "GIT_PATH",
        "HERMES_BUSDRIVER_GH",
        "HERMES_BUSDRIVER_GIT",
        "DEVELOPER_DIR",
    ],
)
def test_no_environment_variable_redirects_the_source(ns, monkeypatch, tmp_path, var):
    impostor = tmp_path / "bin"
    impostor.mkdir()
    for name in ("git", "gh", "jq"):
        target = impostor / name
        target.write_text("#!/bin/sh\necho impostor\n")
        target.chmod(0o755)
    monkeypatch.setenv(var, str(impostor) if var != "PATH" else f"{impostor}:/usr/bin:/bin")
    assert ns["trusted_executable_path"]("jq") == Path("/usr/bin/jq")


def test_private_runtime_env_no_longer_selects_a_writable_bin(ns, monkeypatch, tmp_path):
    """r34's `HERMES_BUSDRIVER_PRIVATE_RUNTIME=1` branch chose a user-writable dir by design."""
    monkeypatch.setenv("HERMES_BUSDRIVER_PRIVATE_RUNTIME", "1")
    assert ns["trusted_executable_path"]("jq") == Path("/usr/bin/jq")


def test_developer_dir_cannot_redirect_the_commandlinetools_shim(ns):
    """/usr/bin/git is the CLT multi-call shim; it re-dispatches through xcrun, which honours
    $DEVELOPER_DIR. A root-owned, SIP-restricted, digest-matching binary will happily exec
    attacker code from a user-writable directory. Verified out-of-band: a planted xcrun returned
    exit 42. The ancestry walk cannot see this, so the contract owns the child env instead.
    """
    denied = ns["ENV_DENIED_FOR_TRUSTED_DISPATCH"]
    assert "DEVELOPER_DIR" in denied


def test_child_env_never_carries_developer_dir(ns, monkeypatch, tmp_path):
    monkeypatch.setenv("DEVELOPER_DIR", str(tmp_path))
    for builder in ("safe_subprocess_env", "safe_git_env", "child_env"):
        if builder not in ns:
            continue
        try:
            env = ns[builder]()
        except TypeError:
            env = ns[builder](None)
        assert "DEVELOPER_DIR" not in env, builder


# --------------------------------------------------------------------------------------------
# Descriptor/path opening+closing identity revalidation.
# --------------------------------------------------------------------------------------------


def test_digest_mismatch_is_refused(ns, monkeypatch):
    monkeypatch.setitem(ns["TRUSTED_EXECUTABLE_DIGESTS"], "jq", "0" * 64)
    with pytest.raises((RuntimeError, SystemExit)) as excinfo:
        ns["_validated_root_owned_source"](Path("/usr/bin/jq"), "jq")
    assert "integrity_failed" in _err(excinfo.value)


def test_directory_in_place_of_an_executable_is_refused(ns, tmp_path):
    with pytest.raises((RuntimeError, SystemExit)):
        ns["_validated_root_owned_source"](tmp_path, "jq")


def test_shim_backed_source_waives_nlink_but_requires_sip(ns):
    """/usr/bin/git and /usr/bin/python3 are ONE inode: a 78-way-hardlinked CLT shim dispatching on
    argv[0]. `st_nlink == 1` is therefore not a property of a trusted system source here, and
    requiring it would fail-close git forever. It also buys nothing under root-owned, unwritable
    ancestry: an adversary who cannot write the directory cannot add a name to it. SF_RESTRICTED
    (SIP — denies even root) is required instead, which is strictly stronger.
    """
    git = os.lstat("/usr/bin/git")
    python3 = os.lstat("/usr/bin/python3")
    assert (git.st_dev, git.st_ino) == (python3.st_dev, python3.st_ino), "shim identity changed"
    assert git.st_nlink > 1
    assert git.st_flags & SF_RESTRICTED
    assert "git" in ns["SHIM_BACKED_SOURCES"]
    assert ns["_validated_root_owned_source"](Path("/usr/bin/git"), "git") == Path("/usr/bin/git")


def test_non_shim_source_still_requires_single_link(ns, tmp_path):
    assert "jq" not in ns["SHIM_BACKED_SOURCES"]
    assert "gh" not in ns["SHIM_BACKED_SOURCES"]


# --------------------------------------------------------------------------------------------
# v16-r34c — the contract is COPIED into every consumer, so the copies must be held together.
#
# CONTRACT_SCRIPTS above is a hand-kept list of the three scripts whose table carries gh+jq, and
# the gh/jq-specific properties genuinely only apply to those. But the contract itself now lives in
# eleven files, and "a property that has repeatedly let one copy drift" is this suite's own words
# for why that matters. A hand-kept list is the mechanism of that drift: the copies it omits are
# exactly the copies nobody checks. So the set below is DERIVED from the source tree, and a twelfth
# copy joins these assertions by existing.
# --------------------------------------------------------------------------------------------

# The primitives that must be byte-for-byte the same logic wherever they appear.
CONTRACT_PRIMITIVES = (
    "_require_trusted_directory",
    "_open_root_owned_ancestry",
    "_require_trusted_leaf",
    "_identity",
    "_read_trusted_source_bytes",
    "_validated_root_owned_source",
    "trusted_executable_path",
)

# The refusal MECHANISM legitimately differs per file, because each answers in its own envelope:
# these two raise through their own failure helper rather than returning an exception to raise.
# Their logic is still held to the same shape by the assertions below; only the spelling of "refuse"
# is theirs. Every other copy routes through `private_runtime_error` / a returned exception.
_ADAPTED_REFUSAL = {"run-pi-busdriver-draft", "busdriver-fs-broker.py"}
_PYTHON_ONLY_EQUIVALENT = {
    "hermes-busdriver-finalization-readiness",
    "hermes-busdriver-pr-grind-loop",
    "hermes-busdriver-relay-role",
    "hermes-busdriver-smoke",
}


def _tracked_script_paths() -> list[Path]:
    names = subprocess.run(
        ["git", "ls-files", "-z", "scripts"], cwd=ROOT, capture_output=True, check=True
    ).stdout.split(b"\0")
    return [ROOT / name.decode() for name in names if name]


def _contract_sources() -> list[Path]:
    """Derived, never typed: every tracked production file that carries the contract."""
    found = [
        path
        for path in _tracked_script_paths()
        if path.is_file() and "_validated_root_owned_source" in path.read_text()
    ]
    broker = ROOT / "adapters" / "pi" / "busdriver-fs-broker.py"
    if "_validated_root_owned_source" in broker.read_text():
        found.append(broker)
    return found


def _root_owned_execution_consumers() -> set[Path]:
    """All production consumers, including non-Python validators, derived from their mechanism."""
    consumers = set(_contract_sources())
    for path in _tracked_script_paths():
        if path.is_file() and "trusted_tool()" in path.read_text(errors="replace"):
            consumers.add(path)
    return consumers


def test_shell_entrypoint_is_a_root_owned_execution_consumer():
    shell = ROOT / "scripts" / "check-required-checks.sh"
    assert shell in _root_owned_execution_consumers()
    source = shell.read_text()
    assert "trusted_tool()" in source
    assert "/usr/bin/python3 -I -c" in source
    assert "trusted_tool /usr/bin/jq 49356fcef7adb7afdb76c9e258eef0e78df3673ba0fb4d479905432c117f579a jq" in source
    assert "trusted_tool /usr/local/bin/gh 02d2d4a85241c6a8c0b77ebb1ec76fc723caf7fb128e00915b306b968847cba1 gh" in source
    assert " repo view" not in source, "remote target must not be inferred from mutable local Git metadata"
    identity_guard = source.index('config error: remote validation requires both --owner and --repo')
    assert identity_guard < source.index("GH=$(trusted_tool")
    assert source.index("compgen -e") < source.index("/usr/bin/python3 -I -c")


def test_every_shell_apple_shim_prevalidator_builds_an_empty_environment_first():
    found = []
    for path in _tracked_script_paths():
        if not path.is_file():
            continue
        source = path.read_text(errors="replace")
        first = source.splitlines()[0] if source.splitlines() else ""
        if first not in {"#!/bin/bash", "#!/bin/bash -p", "#!/bin/sh"} or "/usr/bin/python3" not in source:
            continue
        found.append(path)
        assert "compgen -e" in source and 'unset "$environment_name"' in source, path
        credential_free = source.split("credential_free_exec() (", 1)[1].split("\n\n# GitHub network", 1)[0]
        assert 'unset "$environment_name"' in credential_free
        assert "credential_free_exec /usr/bin/python3 -I -c" in source
        for denied in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "DEVELOPER_DIR", "SDKROOT", "XCODE_DEVELOPER_DIR_PATH", "TOOLCHAINS", "XCRUN_CACHE_PATH"):
            # The Apple-shim prevalidator is empty-by-construction. Credential-bearing gh uses a
            # separate function and preserves only explicit token variables after validation.
            assert denied not in credential_free, path
    assert found == [ROOT / "scripts" / "check-required-checks.sh"]


def _normalized(func: ast.FunctionDef) -> str:
    """The function's LOGIC: docstrings and type annotations stripped.

    Both differ legitimately between copies — one file documents more than another, one spells an
    annotation as a string because it has no `from __future__ import annotations`. Neither changes
    what the code does, and a comparison that fails on them would be noise nobody keeps green.
    """
    clone = copy.deepcopy(func)
    for node in ast.walk(clone):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body = node.body[1:]
            node.returns = None
            for arg in node.args.args + node.args.kwonlyargs:
                arg.annotation = None
        elif isinstance(node, ast.AnnAssign):
            node.annotation = ast.Name(id="_", ctx=ast.Load())
    return ast.dump(clone)


def test_every_file_carrying_the_contract_is_discovered():
    """The derivation itself, guarded. If this ever finds only the three CONTRACT_SCRIPTS again,
    the migration has been reverted somewhere and the tests below would silently prove nothing."""
    found = {p.name for p in _contract_sources()}
    assert {
        "hermes-busdriver-deliver",
        "hermes-busdriver-delivery-status",
        "hermes-busdriver-pr-grind-check",
        "hermes-busdriver-gate",
        "hermes-busdriver-lock",
        "hermes-busdriver-litmus-status",
        "hermes-busdriver-status",
        "hermes-busdriver-relay-brief",
        "hermes-busdriver-agent-draft",
        "run-pi-busdriver-draft",
        # v16-r34c: this one was found by the sweep, not by the handoff list. It ran
        # `run_bounded(["git", *args])` — a bare name with no env at all, so the ambient PATH chose
        # the binary that inspected the worker's repository, and /opt/homebrew/bin is on it.
        "run-opencode-busdriver-draft",
        "busdriver-fs-broker.py",
        *_PYTHON_ONLY_EQUIVALENT,
    } <= found, f"a git/gh consumer lost the contract: {found}"


@pytest.mark.parametrize("primitive", CONTRACT_PRIMITIVES)
def test_the_copied_contract_primitives_agree_across_every_consumer(primitive):
    """One logic per primitive, across all eleven copies.

    This is the check the comment at the head of each copy promises. The primitives are duplicated
    because these are standalone executables with no shared import path — the same reason
    SENSITIVE_PATTERNS and MAX_CAPTURED_BYTES are restated — and duplication without a test is just
    eleven chances for one copy to quietly keep the old behaviour. r34b's whole blocker was a
    half-migrated tree; this is what makes the next half-migration fail loudly.
    """
    variants: dict[str, list[str]] = {}
    for path in _contract_sources():
        for func in ast.walk(ast.parse(path.read_text())):
            if isinstance(func, ast.FunctionDef) and func.name == primitive:
                variants.setdefault(_normalized(func), []).append(path.name)
    assert variants, f"{primitive}: no copy found — was it renamed?"
    # The adapted-refusal files raise through their own helper, so their bodies differ by
    # construction. They are held to their own single shared logic, not exempted from having one.
    core = {k: v for k, v in variants.items() if not set(v) <= (_ADAPTED_REFUSAL | _PYTHON_ONLY_EQUIVALENT)}
    assert len(core) == 1, (
        f"{primitive} has diverged across copies: "
        + " | ".join(f"[{i}] {', '.join(sorted(v))}" for i, v in enumerate(core.values()))
    )


def test_every_contract_copy_pins_the_same_platform_constants():
    """The three numbers the deviations rest on. A copy that disagrees about SIP, the denied
    environment, or the read bound is a copy with a different threat model."""
    seen: dict[str, list] = {"SF_RESTRICTED": [], "ENV_DENIED_FOR_TRUSTED_DISPATCH": [], "MAX_TRUSTED_EXECUTABLE_BYTES": [], "SHIM_BACKED_SOURCES": []}
    for path in _contract_sources():
        ns = runpy.run_path(str(path))
        for key in seen:
            assert key in ns, f"{path.name} carries the contract but not {key}"
            seen[key].append((path.name, ns[key]))
    assert {v for _, v in seen["SF_RESTRICTED"]} == {0x00080000}
    assert {frozenset(v) for _, v in seen["ENV_DENIED_FOR_TRUSTED_DISPATCH"]} == {
        frozenset({"DEVELOPER_DIR", "SDKROOT", "XCODE_DEVELOPER_DIR_PATH", "TOOLCHAINS", "XCRUN_CACHE_PATH"})
    }, "DEVELOPER_DIR redirects the /usr/bin/git shim through xcrun; every copy must deny it"
    assert {v for _, v in seen["MAX_TRUSTED_EXECUTABLE_BYTES"]} == {256 * 1024 * 1024}
    for path in _contract_sources():
        ns = runpy.run_path(str(path))
        expected = frozenset(set(ns["TRUSTED_EXECUTABLE_SOURCES"]) & {"git", "python3"})
        assert frozenset(ns["SHIM_BACKED_SOURCES"]) == expected, path.name


def test_no_contract_copy_reintroduces_a_private_copy_or_an_env_override():
    """The migration's negative space, asserted over the whole tree rather than per file.

    r34b's tree was incoherent precisely because two consumers had moved and six had not, and
    nothing failed. These are the names the old design used; production carrying any of them again
    means a consumer has been rewritten back to executing bytes it copied to a writable path, or to
    letting a variable choose the executable.
    """
    forbidden = {
        "PRIVATE_TRUSTED_BIN": "a directory of private git/gh/jq copies",
        "HERMES_BUSDRIVER_PRIVATE_RUNTIME": "the env flag that selected that directory",
        "BD_BROKER_GIT": "the variable that named the broker's git",
        "/opt/homebrew/bin/git": "user-writable (uid=501 drwxrwxr-x) ancestry",
        "/opt/homebrew/bin/gh": "user-writable (uid=501 drwxrwxr-x) ancestry",
    }
    offenders = []
    for path in sorted(ROOT.glob("scripts/**/*")) + [ROOT / "adapters" / "pi" / "busdriver-fs-broker.py"]:
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, ValueError, UnicodeDecodeError):
            continue
        # Strings and names in CODE only. The docstrings explaining why each of these is gone are
        # the reason a plain substring scan would find every one of them forever.
        for node in ast.walk(tree):
            literal = None
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                literal = node.value
            elif isinstance(node, ast.Name):
                literal = node.id
            if literal in forbidden:
                if isinstance(node, ast.Constant) and _is_docstring(tree, node):
                    continue
                offenders.append(f"{path.name}:{node.lineno} {literal} ({forbidden[literal]})")
    assert not offenders, "the private-copy design is back:\n  " + "\n  ".join(offenders)


def _is_docstring(tree: ast.AST, node: ast.Constant) -> bool:
    for parent in ast.walk(tree):
        if isinstance(parent, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(parent, "body", [])
            if body and isinstance(body[0], ast.Expr) and body[0].value is node:
                return True
    return False
