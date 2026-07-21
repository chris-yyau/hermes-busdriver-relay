"""v16-r25 B5: bounded redaction is one contract, restated in every relay that emits output.

These scripts are standalone executables run as subprocesses, not an importable package, so the
redaction block cannot literally be shared. What can be shared is the guarantee: every relay that
prints subprocess output or a remote URL redacts the same things, the same way, before bounding.
r24 closed this in `deliver` alone and four siblings kept leaking, which is exactly the drift
these tests exist to catch — a new relay, or an edited copy, fails here rather than in the field.
"""
import json
import runpy
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
# Every production entrypoint that emits subprocess output or a remote URL into an envelope.
REDACTING_RELAYS = (
    "hermes-busdriver-deliver",
    "hermes-busdriver-delivery-status",
    "hermes-busdriver-pr-grind-check",
    "hermes-busdriver-pr-grind-loop",
    "hermes-busdriver-litmus-status",
    "hermes-busdriver-finalization-readiness",
    # v16-r28 item 2: the OpenCode wrapper emits opencode's stdout/stderr into its blocked
    # envelopes and writes both to the run dir, so it is a redacting relay like any other. It was
    # simply never listed — and had drifted to five patterns, no credential env values, and the
    # redact-then-bound order this suite exists to forbid. Listing it is the fix that stays fixed.
    "opencode/run-opencode-busdriver-draft",
    # v16-r30 C: the Pi wrapper and the agent-draft launcher emit a subprocess's stdout/stderr into
    # their envelopes through a `tail` that was a bare `text[-n:]` — no redaction at all, the very
    # leak this suite was built to catch. They are listed here for the same reason OpenCode was:
    # the contract is the membership, so an unlisted emitter is the bug.
    "pi/run-pi-busdriver-draft",
    "hermes-busdriver-agent-draft",
    # v16-r31 D8: the gate emits a verifier's stdout/stderr into its envelope — a verifier is an
    # arbitrary command line, so its output is exactly the untrusted text this suite governs — and
    # it was emitting a bare `cp.stdout[-4000:]`: no redaction at all, and bounded after the scan
    # rather than before it. Unlisted emitter, same bug, same fix as OpenCode and the two above.
    "hermes-busdriver-gate",
)
SECRET = "ghp_" + "a" * 36


def load(name: str) -> dict:
    return runpy.run_path(str(ROOT / "scripts" / name))


@pytest.fixture(scope="module")
def relays() -> dict[str, dict]:
    return {name: load(name) for name in REDACTING_RELAYS}


def patterns(ns: dict) -> list[tuple[str, str]]:
    return [(pattern.pattern, replacement) for pattern, replacement in ns["SENSITIVE_PATTERNS"]]


def test_every_relay_carries_the_same_pattern_list(relays):
    reference = patterns(relays["hermes-busdriver-deliver"])
    assert len(reference) >= 8
    for name, ns in relays.items():
        assert patterns(ns) == reference, f"{name} redaction patterns drifted from deliver"


def test_every_relay_redacts_the_same_credential_env_keys(relays):
    reference = relays["hermes-busdriver-deliver"]["CREDENTIAL_ENV_KEYS"]
    assert "GH_TOKEN" in reference and "GITHUB_TOKEN" in reference
    for name, ns in relays.items():
        assert ns["CREDENTIAL_ENV_KEYS"] == reference, f"{name} credential env keys drifted"


@pytest.mark.parametrize("name", REDACTING_RELAYS)
def test_every_relay_redacts_a_github_token(name: str, relays):
    assert SECRET not in relays[name]["redact_text"](f"HTTP 401: bad credentials {SECRET}")


@pytest.mark.parametrize("name", REDACTING_RELAYS)
def test_every_relay_redacts_url_userinfo_but_keeps_the_repo(name: str, relays):
    out = relays[name]["redact_text"]("fatal: https://" + "x-access-token:" + "ghs_bbbbbbbbbbbbbbbbbbbbbbbb@github.com/o/r.git")

    assert "ghs_bbbbbbbbbbbbbbbbbbbbbbbb" not in out
    assert "github.com/o/r.git" in out


@pytest.mark.parametrize("name", REDACTING_RELAYS)
def test_every_relay_redacts_its_own_credential_env_values(name: str, relays, monkeypatch):
    """An opaque enterprise token matches no shape pattern, but we know our own value."""
    monkeypatch.setenv("GH_TOKEN", "an-opaque-enterprise-credential-value")

    assert "an-opaque-enterprise-credential-value" not in relays[name]["redact_text"](
        "remote: rejected using an-opaque-enterprise-credential-value"
    )


@pytest.mark.parametrize("name", REDACTING_RELAYS)
def test_every_relay_ignores_short_env_values_as_credentials(name: str, relays, monkeypatch):
    """A 1-3 char token would redact every occurrence of that substring in all output."""
    monkeypatch.setenv("GH_TOKEN", "abc")

    assert relays[name]["redact_text"]("abc is a normal word here") == "abc is a normal word here"


@pytest.mark.parametrize("name", REDACTING_RELAYS)
@pytest.mark.parametrize("prefix_len", [0, 3990, 3999, 4000, 4200])
def test_every_relay_redacts_before_bounding(name: str, prefix_len: int, relays):
    """Redaction must precede the tail slice in every relay, at and across the 4000-byte cut."""
    ns = relays[name]
    tail = ns.get("tail") or ns["sanitized_tail"]

    out = tail("p" * prefix_len + " " + SECRET + " " + "s" * 50)

    assert "ghp_" not in out
    assert len(out) <= 4000


# --- v16-r26B B4: the redaction input is bounded BEFORE the regexes run ---


@pytest.mark.parametrize("name", REDACTING_RELAYS)
def test_every_relay_bounds_the_window_before_redacting(name: str, relays, monkeypatch):
    """r25 redacted the WHOLE input and bounded afterwards, so the bound never protected the regexes.

    A hostile subprocess returns as much stderr as it likes. Every SENSITIVE_PATTERN — including a
    URL-userinfo class with no length bound — then ran over all of it inside a helper that emits
    4000 bytes. The expensive step must never see more than the scan budget; past that the input is
    refused outright rather than sliced.
    """
    ns = relays[name]
    tail = ns.get("tail") or ns["sanitized_tail"]
    seen: list[int] = []
    real_redact = ns["redact_text"]

    def measuring_redact(text: str) -> str:
        seen.append(len(text))
        return real_redact(text)

    monkeypatch.setitem(ns["redact_text"].__globals__, "redact_text", measuring_redact)

    out = tail("A" * 5_000_000 + " tail-marker")

    assert not seen, "the 5MB input reached the regexes"
    assert out == ns["REDACTED_OVERSIZED"]


@pytest.mark.parametrize("name", REDACTING_RELAYS)
def test_every_relay_redacts_inside_the_scan_budget(name: str, relays, monkeypatch):
    """Under budget, nothing is dropped: the regexes run and the diagnostic tail survives."""
    ns = relays[name]
    tail = ns.get("tail") or ns["sanitized_tail"]
    seen: list[int] = []
    real_redact = ns["redact_text"]

    def measuring_redact(text: str) -> str:
        seen.append(len(text))
        return real_redact(text)

    monkeypatch.setitem(ns["redact_text"].__globals__, "redact_text", measuring_redact)

    out = tail("A" * 8_000 + " tail-marker")

    assert max(seen) <= 4000 + ns["redaction_overlap"]()
    assert len(out) <= 4000
    assert out.endswith("tail-marker")


@pytest.mark.parametrize("name", REDACTING_RELAYS)
def test_every_relay_refuses_a_hostile_url_over_budget(name: str, relays):
    """The userinfo class `([^/\\s:@]+(?::[^/\\s@]*)?)@` is unbounded; a 5MB URL is one candidate span."""
    ns = relays[name]
    tail = ns.get("tail") or ns["sanitized_tail"]

    out = tail("https://" + "x-access-token:" + "" + "z" * 5_000_000 + "@github.com/o/r.git")

    assert out == ns["REDACTED_OVERSIZED"]
    assert "zzzzzzzzzzzzzzzz" not in out


@pytest.mark.parametrize("name", REDACTING_RELAYS)
@pytest.mark.parametrize("offset", [0, 1, 40, 500, 3960, 3999, 4000, 4200, 8000])
def test_every_relay_keeps_a_boundary_spanning_secret_out_of_the_emitted_tail(name: str, relays, offset: int):
    """A secret that ends inside the emitted region must be matched whole, never bisected.

    `offset` walks the secret across the emitted boundary and past it, with the whole input still
    inside the scan budget so the regexes actually run.
    """
    ns = relays[name]
    tail = ns.get("tail") or ns["sanitized_tail"]

    # A space before the secret: `\bghp_` needs a word boundary, and real output has one.
    out = tail("N" * 100 + " " + SECRET + " " + "t" * offset)

    assert "ghp_" not in out
    assert SECRET[8:40] not in out, "a tail of the secret survived the cut"
    assert len(out) <= 4000


@pytest.mark.parametrize("name", REDACTING_RELAYS)
def test_every_relay_sizes_its_overlap_from_its_own_credential_values(name: str, relays, monkeypatch):
    """An opaque enterprise token matches no shape pattern, so only its length can size the window."""
    ns = relays[name]
    tail = ns.get("tail") or ns["sanitized_tail"]
    secret = "opaque-" + "q" * 3000
    monkeypatch.setenv("GH_TOKEN", secret)

    assert ns["redaction_overlap"]() > len(secret)
    out = tail("N" * 5_000_000 + secret + " trailing")
    assert "opaque-" not in out
    assert "qqqqqqqqqqqqqqqq" not in out


@pytest.mark.parametrize("name", REDACTING_RELAYS)
def test_every_relay_sizes_the_window_so_a_long_credential_is_never_split(name: str, relays, monkeypatch):
    """A configured credential must land in the window WHOLE, however long it is.

    Split is the one state in which part of it would be emitted, and the overlap is sized from the
    value's own length precisely so the cut can never land inside it.
    """
    ns = relays[name]
    tail = ns.get("tail") or ns["sanitized_tail"]
    secret = "u" * 200_000
    monkeypatch.setenv("GH_TOKEN", secret)

    assert ns["redaction_overlap"]() > len(secret)
    out = tail(secret + " visible-tail")

    assert "uuuuuuuuuuuuuuuu" not in out
    assert out.endswith("visible-tail")


# --- v16-r27 item 3: an oversized prefix-identified secret is refused, never tail-sliced ---


@pytest.mark.parametrize("name", REDACTING_RELAYS)
@pytest.mark.parametrize(
    "prefix",
    [
        "token: ",
        "--token ",
        '{"token":"',
        "Authorization: Bearer ",
        "password=",
        "api_key: ",
    ],
)
def test_every_relay_refuses_an_oversized_prefix_identified_secret(name: str, relays, prefix: str):
    """The r26 leak: the value classes are unbounded, so a long enough value outruns any window.

    Slicing to the last `limit + overlap` bytes removes the `token:`/`--token`/`"token":`/`Bearer`
    prefix that identifies the value as a secret. The remainder matches no shape pattern, and the
    emitted tail is raw credential. No window size fixes this — the prefix is arbitrarily far from
    the tail — so an over-budget input must be dropped for the fixed literal instead.
    """
    ns = relays[name]
    tail = ns.get("tail") or ns["sanitized_tail"]
    secret = "S" * 20_000

    out = tail("fatal: " + prefix + secret)

    assert out == ns["REDACTED_OVERSIZED"]
    assert "SSSSSSSSSSSSSSSS" not in out


@pytest.mark.parametrize("name", REDACTING_RELAYS)
def test_every_relay_refuses_mixed_collapsible_padding_around_a_secret(name: str, relays):
    """r26 Low: redaction that SHRINKS the window re-admits the fragment the pre-slice bisected.

    `password=<1000 chars>` runs collapse to 19 chars each, so a 12KB window fell under the 4000
    limit and the whole of it — including the token bisected by the pre-slice — was emitted. The
    input must exceed the budget for the r26 arithmetic to trigger; over budget is now refused
    before any of it can matter.
    """
    ns = relays[name]
    tail = ns.get("tail") or ns["sanitized_tail"]
    victim = "V" * 2_000
    padding = " ".join(f"password={'p' * 1000}" for _ in range(20))
    assert len("https://" + "x-access-token:" + "" + victim + "@github.com/o/r.git " + padding) > 4000 + ns["redaction_overlap"]()

    out = tail("https://" + "x-access-token:" + "" + victim + "@github.com/o/r.git " + padding)

    assert out == ns["REDACTED_OVERSIZED"]
    assert "VVVVVVVVVVVVVVVV" not in out


@pytest.mark.parametrize("name", REDACTING_RELAYS)
def test_every_relay_keeps_a_long_unbroken_diagnostic_tail(name: str, relays):
    """Bounding must not eat the diagnostics: stderr with no whitespace still tails to `limit`."""
    ns = relays[name]
    tail = ns.get("tail") or ns["sanitized_tail"]

    out = tail("r" * 3000 + "s" * 3000)

    assert out == "r" * 1000 + "s" * 3000


@pytest.mark.parametrize("name", REDACTING_RELAYS)
def test_every_relay_leaves_short_output_untouched(name: str, relays):
    """The bound must not cost the common case: nothing is dropped when nothing is truncated."""
    ns = relays[name]
    tail = ns.get("tail") or ns["sanitized_tail"]

    assert tail("fatal: could not read Username for 'https://github.com'") == (
        "fatal: could not read Username for 'https://github.com'"
    )


# --- v16-r34: a credential can arrive AS a dict key ----------------------------------------------


def _defines_redact_value(name: str) -> bool:
    return "\ndef redact_value(" in (ROOT / "scripts" / name).read_text(errors="replace")


# Derived, not typed: REDACTING_RELAYS is the emitter list, and only some emitters walk a structure.
REDACT_VALUE_RELAYS = tuple(name for name in REDACTING_RELAYS if _defines_redact_value(name))


def test_the_redact_value_enumeration_finds_every_structural_redactor():
    """A derivation that found nothing would collect zero cases below and pass silently."""
    assert len(REDACT_VALUE_RELAYS) >= 7, REDACT_VALUE_RELAYS
    assert "hermes-busdriver-deliver" in REDACT_VALUE_RELAYS


@pytest.mark.parametrize("name", REDACT_VALUE_RELAYS)
def test_every_relay_redacts_a_credential_that_arrives_as_a_dict_key(name: str, relays):
    """`redact_value` asked two questions of a key — does its NAME look sensitive, and is its VALUE
    a secret — and never the third: is the key ITSELF one.

    These dicts are assembled from children's JSON, env snapshots and command echoes, so a key is
    untrusted text like any other and `{"<token>": ...}` is a shape the emitter can be handed. Four
    relays already ran the key through `redact_text`; deliver, delivery-status and
    finalization-readiness did not, and emitted it verbatim from the one function whose entire job is
    to make an envelope safe to print.

    Only the leak is asserted, not the key-NAME heuristic: deliver/gate/agent-draft/pi/opencode
    redact a key called `token`, while delivery-status/finalization-readiness instead learn the
    capability's VALUE from the key via capability_scalars(). Those are two designs for the same
    problem and both are fine; emitting the credential itself is what none of them may do.
    """
    ns = relays[name]

    emitted = json.dumps(ns["redact_value"]({
        SECRET: "seen",
        "nested": [{f"Authorization: Bearer {SECRET}": 1}],
    }))

    assert SECRET not in emitted, f"{name} emitted a credential that arrived as a dict key"
