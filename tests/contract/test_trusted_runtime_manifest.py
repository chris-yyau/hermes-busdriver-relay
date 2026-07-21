"""The trusted runtime manifest is the closure over every embedded digest pin.

`refresh_contract` promises that every embedded consumer pin moves in one reviewed diff. r26 found
that promise unenforced: the test correlated a hand-picked subset, so `hermes-busdriver-status`
executed `scripts/lib/resolve-cli.sh` against a digest the manifest had never heard of, and four
more runtime pins were bound by nothing. A subset check cannot notice the pin nobody added.

So the binding is enumerated ONCE, in CONSUMER_PINS below, and the closure is checked from BOTH
ends:

  * every enumerated pin equals its manifest entry, and every manifest entry over repo-local bytes
    equals the file's current bytes (test_..._matches_embedded_runtime_pins);
  * every 64-hex digest literal in every tracked script is claimed by an enumerated pin
    (test_every_embedded_digest_literal_is_enumerated).

The second one is what makes this fail-closed and maintainable: adding a pin to a script without
adding its row here fails, naming the file and the literal. Nothing to keep in sync by comment.
"""
import hashlib
import json
import re
import runpy
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config" / "trusted-runtime-manifest.json"
# Both quote styles. A double-quote-only pattern made the far-end closure blind to just over half
# the pins in the tree — including every one in finalization-readiness and fifteen of eighteen in
# deliver — because the single-quoted spelling is what `repr(dict)` emits and the digest maps were
# pasted from it. That is the failure mode this check exists to catch, reachable through nothing but
# quote style, and self-perpetuating: the refresh workflow produces the invisible spelling.
HEX64_LITERAL = re.compile(r"""["']([a-f0-9]{64})["']""")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tracked_scripts() -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "scripts"], cwd=ROOT, capture_output=True, check=True
    ).stdout.split(b"\0")
    return [ROOT / name.decode() for name in listed if name and (ROOT / name.decode()).is_file()]


def tracked_executable_scripts() -> set[str]:
    listed = subprocess.run(
        ["git", "ls-files", "--stage", "scripts"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return {
        row.split(maxsplit=3)[3]
        for row in listed
        if row.split(maxsplit=1)[0] == "100755"
    }


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def test_manifest_entrypoints_equal_the_independent_git_executable_surface(manifest):
    """Every Git-shipped executable must be pinned, with no stale manifest-only entrypoint."""
    assert set(manifest["production_entrypoints"]) == tracked_executable_scripts()


@pytest.fixture(scope="module")
def namespaces() -> dict[str, dict]:
    """Every script that carries an embedded digest pin, loaded once."""
    names = [
        "hermes-busdriver-deliver",
        "hermes-busdriver-delivery-status",
        "hermes-busdriver-finalization-readiness",
        "hermes-busdriver-pr-grind-check",
        "hermes-busdriver-pr-grind-loop",
        "hermes-busdriver-agent-draft",
        "hermes-busdriver-litmus-status",
        "hermes-busdriver-lock",
        "hermes-busdriver-gate",
        "hermes-busdriver-status",
        "hermes-busdriver-relay-brief",
        "hermes-busdriver-relay-role",
        "hermes-busdriver-smoke",
    ]
    loaded = {name: runpy.run_path(str(ROOT / "scripts" / name)) for name in names}
    loaded["run-pi-busdriver-draft"] = runpy.run_path(str(ROOT / "scripts" / "pi" / "run-pi-busdriver-draft"))
    loaded["run-opencode-busdriver-draft"] = runpy.run_path(str(ROOT / "scripts" / "opencode" / "run-opencode-busdriver-draft"))
    return loaded


def executable_digest(manifest: dict, name: str) -> str:
    return manifest["executables"][name]["sha256"]


def consumer_pins(manifest: dict) -> list[tuple[str, str, object]]:
    """(script, constant, expected value from the manifest) — the whole binding, enumerated.

    A row per embedded pin. `expected` is always derived from the manifest, never restated, so the
    manifest stays the single place a digest is written down.
    """
    executables = {name: entry["sha256"] for name, entry in manifest["executables"].items()}
    scripts = manifest["scripts"]
    entrypoints = manifest["production_entrypoints"]
    return [
        # --- executable digest maps ---
        ("hermes-busdriver-deliver", "TRUSTED_EXECUTABLE_DIGESTS", {k: executables[k] for k in ("git", "git-real", "sandbox-exec", "gh", "jq", "bash", "python3")}),
        ("hermes-busdriver-delivery-status", "TRUSTED_EXECUTABLE_DIGESTS", {k: executables[k] for k in ("git", "git-real", "sandbox-exec", "gh", "jq", "python3")}),
        ("hermes-busdriver-pr-grind-check", "TRUSTED_EXECUTABLE_DIGESTS", {k: executables[k] for k in ("gh", "git", "jq", "bash", "python3")}),
        ("hermes-busdriver-agent-draft", "TRUSTED_EXECUTABLE_DIGESTS", {k: executables[k] for k in ("git", "gh", "pi", "opencode", "bash", "python3")}),
        # v16-r34c: the git-only consumers carry the same table shape as the git/gh/jq ones rather
        # than a lone TRUSTED_GIT_DIGEST/TRUSTED_GIT_SHA256 constant each, so one assertion covers
        # every copy and a new consumer cannot invent a third spelling.
        #
        ("hermes-busdriver-pr-grind-loop", "TRUSTED_EXECUTABLE_DIGESTS", {"python3": executables["python3"]}),
        ("hermes-busdriver-finalization-readiness", "TRUSTED_EXECUTABLE_DIGESTS", {"python3": executables["python3"]}),
        ("hermes-busdriver-relay-role", "TRUSTED_EXECUTABLE_DIGESTS", {"python3": executables["python3"]}),
        ("hermes-busdriver-smoke", "TRUSTED_EXECUTABLE_DIGESTS", {"python3": executables["python3"]}),
        ("hermes-busdriver-gate", "TRUSTED_EXECUTABLE_DIGESTS", {k: executables[k] for k in ("git", "git-real", "sandbox-exec", "bash")}),
        ("hermes-busdriver-lock", "TRUSTED_EXECUTABLE_DIGESTS", {k: executables[k] for k in ("git", "git-real", "sandbox-exec")}),
        ("hermes-busdriver-litmus-status", "TRUSTED_EXECUTABLE_DIGESTS", {k: executables[k] for k in ("git", "git-real", "sandbox-exec")}),
        ("hermes-busdriver-status", "TRUSTED_EXECUTABLE_DIGESTS", {k: executables[k] for k in ("git", "git-real", "sandbox-exec")}),
        ("hermes-busdriver-relay-brief", "TRUSTED_EXECUTABLE_DIGESTS", {k: executables[k] for k in ("git", "git-real", "sandbox-exec", "python3")}),
        ("run-pi-busdriver-draft", "TRUSTED_EXECUTABLE_DIGESTS", {"git": executables["git"]}),
        ("run-opencode-busdriver-draft", "TRUSTED_EXECUTABLE_DIGESTS", {"git": executables["git"]}),
        # --- single embedded executable pins ---
        ("run-opencode-busdriver-draft", "TRUSTED_OPENCODE_SHA256", executables["opencode"]),
        ("run-pi-busdriver-draft", "TRUSTED_NODE_SHA256", executables["node"]),
        ("run-pi-busdriver-draft", "TRUSTED_PI_TREE_SHA256", manifest["executables"]["pi-package-tree"]["sha256"]),
        # v16-r30 B: the adapter has no openat(2), so its filesystem containment runs as brokered
        # Python. Both halves of that runtime — the interpreter and the broker bytes — are executed
        # on the adapter's behalf, so both are in the closure like any other executed byte.
        ("run-pi-busdriver-draft", "TRUSTED_BROKER_PYTHON_SHA256", executables["python3"]),
        ("run-pi-busdriver-draft", "TRUSTED_FS_BROKER_SHA256", manifest["adapter_runtime"]["adapters/pi/busdriver-fs-broker.py"]),
        # v16-r31 A1: the adapter node loads is repo bytes on a user-writable path that used to go
        # straight onto node's `-e`. It defines every tool boundary in the run, so it is in the
        # closure like the broker beside it.
        ("run-pi-busdriver-draft", "TRUSTED_PI_TOOLS_SHA256", manifest["adapter_runtime"]["adapters/pi/busdriver-tools.ts"]),
        # v16-r31 A2: agent-draft executes both child wrappers, so both are executed bytes like any
        # other. Neither wrapper pins agent-draft, so this edge adds no cycle.
        ("hermes-busdriver-agent-draft", "TRUSTED_PI_WRAPPER_SHA256", entrypoints["scripts/pi/run-pi-busdriver-draft"]),
        ("hermes-busdriver-agent-draft", "TRUSTED_OPENCODE_WRAPPER_SHA256", entrypoints["scripts/opencode/run-opencode-busdriver-draft"]),
        # --- embedded plugin-script pins ---
        # `plugin_scripts` is the union across consumers, so each consumer binds the rows it runs
        # rather than the whole section: the checker runs these four, status runs the resolver.
        (
            "hermes-busdriver-pr-grind-check",
            "TRUSTED_PLUGIN_DIGESTS",
            {
                key: manifest["plugin_scripts"][key]
                for key in (
                    "scripts/ack-ledger.sh",
                    "scripts/augment-equiv-acks.sh",
                    "scripts/fetch-pr-state.sh",
                    "scripts/relevant-check-status.sh",
                )
            },
        ),
        # v16-r27 item 4: status executes these authenticated resolver bytes, so its pin is in the
        # closure like any other consumer. r26 left it bound by nothing.
        ("hermes-busdriver-status", "TRUSTED_RESOLVER_SHA256", manifest["plugin_scripts"]["scripts/lib/resolve-cli.sh"]),
        # --- embedded relay-helper pins ---
        ("hermes-busdriver-pr-grind-loop", "TRUSTED_CHECK_SHA256", scripts["hermes-busdriver-pr-grind-check"]),
        ("hermes-busdriver-deliver", "TRUSTED_PR_GRIND_CHECK_SHA256", scripts["hermes-busdriver-pr-grind-check"]),
        ("hermes-busdriver-deliver", "TRUSTED_PR_GRIND_LOOP_SHA256", scripts["hermes-busdriver-pr-grind-loop"]),
        ("hermes-busdriver-deliver", "TRUSTED_LOCK_SHA256", scripts["hermes-busdriver-lock"]),
        ("hermes-busdriver-agent-draft", "TRUSTED_LOCK_SHA256", scripts["hermes-busdriver-lock"]),
        ("hermes-busdriver-agent-draft", "TRUSTED_GATE_SHA256", scripts["hermes-busdriver-gate"]),
        ("hermes-busdriver-relay-brief", "TRUSTED_CONTRACT_STATUS_SHA256", entrypoints["scripts/hermes-busdriver-finalization-contract-status"]),
        ("hermes-busdriver-smoke", "TRUSTED_HELPER_DIGESTS", {
            "status": manifest["delivery_status_runtime"]["scripts/hermes-busdriver-status"],
            "runtime": manifest["delivery_status_runtime"]["scripts/hermes-busdriver-runtime-check"],
            "finalization_readiness": manifest["delivery_status_runtime"]["scripts/hermes-busdriver-finalization-readiness"],
            "gate": manifest["delivery_status_runtime"]["scripts/hermes-busdriver-gate"],
        }),
        ("hermes-busdriver-relay-role", "TRUSTED_STATUS_SHA256", manifest["delivery_status_runtime"]["scripts/hermes-busdriver-status"]),
        ("hermes-busdriver-deliver", "TRUSTED_DELIVERY_STATUS_RUNTIME_DIGESTS", manifest["delivery_status_runtime"]),
        ("hermes-busdriver-delivery-status", "TRUSTED_RELAY_HELPER_DIGESTS", None),  # subset; asserted below
        # Readiness executes four helpers directly. Delivery-status can in turn execute the five
        # helpers in its own TRUSTED_RELAY_HELPER_DIGESTS (status overlaps). Pin that exact
        # executable closure, not the broader metadata inventory; the old "all except readiness"
        # map included smoke even though readiness never executed it and created a smoke↔readiness
        # digest cycle as soon as smoke correctly pinned readiness.
        (
            "hermes-busdriver-finalization-readiness",
            "TRUSTED_READINESS_HELPER_DIGESTS",
            {
                key: manifest["delivery_status_runtime"][key]
                for key in (
                    "scripts/hermes-busdriver-agent-balance-plan",
                    "scripts/hermes-busdriver-delivery-status",
                    "scripts/hermes-busdriver-finalization-contract-status",
                    "scripts/hermes-busdriver-litmus-status",
                    "scripts/hermes-busdriver-lock",
                    "scripts/hermes-busdriver-pr-grind-check",
                    "scripts/hermes-busdriver-relay-role",
                    "scripts/hermes-busdriver-status",
                )
            },
        ),
    ]


def test_trusted_runtime_manifest_matches_embedded_runtime_pins(manifest, namespaces):
    assert manifest["schema"] == "hermes-busdriver-trusted-runtime/v1"
    assert manifest["refresh_contract"]

    deliver = namespaces["hermes-busdriver-deliver"]
    assert deliver["TRUSTED_BUSDRIVER_PLUGIN_COMMIT"] == manifest["busdriver"]["commit"]
    assert deliver["TRUSTED_BUSDRIVER_PLUGIN_VERSION"] == manifest["busdriver"]["version"]

    for script, constant, expected in consumer_pins(manifest):
        if expected is None:
            continue
        assert namespaces[script][constant] == expected, f"{script}:{constant} drifted from the manifest"

    # A pinned digest without a pinned path is a digest of nothing in particular.
    #
    # The ROOT-OWNED sources compare LITERALLY — no `.resolve()` on either side. It follows
    # symlinks, so it compared where the manifest's path POINTS rather than what it SAYS, which
    # silently passed the exact arrangement the contract exists to refuse: a manifest naming a
    # symlink in user-writable ancestry resolves to the real file and matches. For these the path
    # is the identity, so it is compared as written.
    for script, constant, name in [
        ("hermes-busdriver-deliver", "TRUSTED_GIT", "git"),
        ("hermes-busdriver-deliver", "TRUSTED_GH", "gh"),
        ("hermes-busdriver-deliver", "TRUSTED_JQ", "jq"),
    ]:
        assert str(namespaces[script][constant]) == str(Path(manifest["executables"][name]["path"])), f"{script}:{constant}"

    # The AGENT-lane anchors still resolve, and must: `pi` is an npm shim symlinking into
    # node_modules, so the manifest names the anchor an operator would recognise while the constant
    # holds what actually gets read. They are outside the root-owned contract by construction —
    # both live under $HOME, whose ancestry this UID can write — which is the same fact that keeps
    # agent dispatch policy_blocked. Resolving here asserts the pin, not a safety property.
    for script, constant, name in [
        ("hermes-busdriver-agent-draft", "TRUSTED_PI", "pi"),
        ("hermes-busdriver-agent-draft", "TRUSTED_OPENCODE", "opencode"),
        ("run-pi-busdriver-draft", "TRUSTED_NODE", "node"),
        # v16-r27 item 7: the Pi wrapper no longer PATH-resolves its anchor, so it has one to pin.
        ("run-pi-busdriver-draft", "TRUSTED_PI", "pi"),
        ("run-pi-busdriver-draft", "TRUSTED_BROKER_PYTHON", "python3"),
        ("run-opencode-busdriver-draft", "TRUSTED_OPENCODE", "opencode"),
    ]:
        assert str(namespaces[script][constant]) == str(Path(manifest["executables"][name]["path"]).resolve()), f"{script}:{constant}"

    # v16-r34c: every git/gh/jq consumer now names its sources in one frozen table, so the binding
    # is asserted over the table itself rather than over per-script alias constants. A consumer
    # missing from this map is a consumer whose source path nothing checks.
    for script, names in [
        ("hermes-busdriver-deliver", ("git", "git-real", "sandbox-exec", "gh", "jq", "bash", "python3")),
            ("hermes-busdriver-delivery-status", ("git", "git-real", "sandbox-exec", "gh", "jq", "python3")),
        ("hermes-busdriver-pr-grind-check", ("git", "gh", "jq", "bash", "python3")),
        ("hermes-busdriver-agent-draft", ("git", "gh", "bash", "python3")),
        ("hermes-busdriver-gate", ("git", "git-real", "sandbox-exec", "bash")),
        ("hermes-busdriver-lock", ("git", "git-real", "sandbox-exec")),
        ("hermes-busdriver-litmus-status", ("git", "git-real", "sandbox-exec")),
        ("hermes-busdriver-status", ("git", "git-real", "sandbox-exec")),
            ("hermes-busdriver-relay-brief", ("git", "git-real", "sandbox-exec", "python3")),
            ("hermes-busdriver-finalization-readiness", ("python3",)),
            ("hermes-busdriver-pr-grind-loop", ("python3",)),
            ("hermes-busdriver-relay-role", ("python3",)),
            ("hermes-busdriver-smoke", ("python3",)),
        ("run-pi-busdriver-draft", ("git",)),
        ("run-opencode-busdriver-draft", ("git",)),
    ]:
        assert namespaces[script]["TRUSTED_EXECUTABLE_SOURCES"] == {
            name: Path(manifest["executables"][name]["path"]) for name in names
        }, f"{script}:TRUSTED_EXECUTABLE_SOURCES"

    # The broker is not a `scripts/` entry point, so it is not in `namespaces`; it holds the same
    # table as plain strings because it never imports pathlib for this.
    broker = runpy.run_path(str(ROOT / "adapters" / "pi" / "busdriver-fs-broker.py"))
    broker_names = ("git", "git-real", "sandbox-exec")
    assert broker["TRUSTED_EXECUTABLE_SOURCES"] == {
        name: manifest["executables"][name]["path"] for name in broker_names
    }
    assert broker["TRUSTED_EXECUTABLE_DIGESTS"] == {
        name: manifest["executables"][name]["sha256"] for name in broker_names
    }
    # delivery-status retains the helpers it executes; that pin set is a subset of the closure.
    relay_helpers = namespaces["hermes-busdriver-delivery-status"]["TRUSTED_RELAY_HELPER_DIGESTS"]
    assert relay_helpers, "delivery-status pins no helper at all"
    for relative, digest in relay_helpers.items():
        assert manifest["delivery_status_runtime"][relative] == digest

    for name, digest in manifest["scripts"].items():
        assert sha256(ROOT / "scripts" / name) == digest, f"scripts/{name} bytes changed without a manifest refresh"

    # Repo-local bytes an adapter executes. Same rule as scripts/: manifested bytes are the bytes.
    assert manifest["adapter_runtime"], "no adapter runtime is manifested at all"
    for relative, digest in manifest["adapter_runtime"].items():
        assert sha256(ROOT / relative) == digest, f"{relative} bytes changed without a manifest refresh"

    expected_production_entrypoints = set(manifest["delivery_status_runtime"]) | {
        "scripts/check-required-checks.sh",
        "scripts/hermes-busdriver-deliver",
        "scripts/hermes-busdriver-relay-brief",
        "scripts/opencode/run-opencode-busdriver-draft",
        "scripts/pi/run-pi-busdriver-draft",
    }
    assert set(manifest["production_entrypoints"]) == expected_production_entrypoints
    for relative, digest in manifest["production_entrypoints"].items():
        assert sha256(ROOT / relative) == digest, f"{relative} bytes changed without a manifest refresh"


def test_every_embedded_digest_literal_is_enumerated(manifest, namespaces):
    """The closure, checked from the far end: no pin may exist that this file does not name.

    This is the assertion r26 was missing. It reads the scripts as TEXT rather than trusting the
    enumeration above to be complete — a new `TRUSTED_..._SHA256 = "..."` anywhere under scripts/
    fails here, by file and by literal, until it is both manifested and enumerated.
    """
    pinned: dict[str, set[str]] = {}
    for script, _constant, expected in consumer_pins(manifest):
        values = set()
        if isinstance(expected, dict):
            values = {value for value in expected.values() if isinstance(value, str)}
        elif isinstance(expected, str):
            values = {expected}
        pinned.setdefault(script, set()).update(values)
    # The one pin set the enumeration defers to the manifest subset check above.
    pinned.setdefault("hermes-busdriver-delivery-status", set()).update(
        namespaces["hermes-busdriver-delivery-status"]["TRUSTED_RELAY_HELPER_DIGESTS"].values()
    )

    unenumerated: dict[str, set[str]] = {}
    for path in tracked_scripts():
        literals = set(HEX64_LITERAL.findall(path.read_text(errors="replace")))
        if not literals:
            continue
        missing = literals - pinned.get(path.name, set())
        if missing:
            unenumerated[str(path.relative_to(ROOT))] = missing

    assert not unenumerated, (
        "embedded digest literals bound by nothing — add each to config/trusted-runtime-manifest.json "
        f"and to consumer_pins(): {json.dumps({k: sorted(v) for k, v in unenumerated.items()}, indent=2)}"
    )


def test_delivery_status_runtime_helper_closure_is_manifested(manifest, namespaces):
    delivery_status = namespaces["hermes-busdriver-delivery-status"]
    capability_helpers = {
        str(Path(entry["path"]).relative_to(ROOT))
        for entry in delivery_status["relay_capabilities"]().values()
        if Path(entry["path"]).name != "hermes-busdriver-deliver"
    }
    expected = capability_helpers | {"scripts/hermes-busdriver-lock"}

    assert set(manifest["delivery_status_runtime"]) == expected
    assert namespaces["hermes-busdriver-deliver"]["TRUSTED_DELIVERY_STATUS_RUNTIME_DIGESTS"] == manifest["delivery_status_runtime"]
    assert expected <= set(manifest["production_entrypoints"])
