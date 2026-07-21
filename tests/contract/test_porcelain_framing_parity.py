"""v16-r26B B3: porcelain framing is one contract, restated in every relay that reads git status.

These scripts are standalone executables run as subprocesses, not an importable package, so the
parser cannot literally be shared. What can be shared is the guarantee: no relay derives a status
record from `str.splitlines()`, because git's own quoting does not save it.

Measured against real git before this suite existed: with a repo-local `core.quotePath=false`
(which `GIT_CONFIG_NOSYSTEM=1` does not reach — it is the inspected repo's own `.git/config`), git
quotes C0 controls in a pathname but emits NEL (U+0085), LS (U+2028) and PS (U+2029) raw. Python's
`splitlines()` splits on all three, so a single untracked directory named `evil<U+2028> M .claude`
produced a second, fabricated ` M .claude/litmus-passed.local"` record — which
`marker_path_allowed()` accepted, since it strips the stray quote the split leaves behind.

A new relay, or an edited copy, fails here rather than in the field.
"""
import runpy
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
# Every production entrypoint that turns `git status` output into records.
FRAMING_RELAYS = (
    "hermes-busdriver-deliver",
    "hermes-busdriver-delivery-status",
    "hermes-busdriver-status",
    "hermes-busdriver-relay-brief",
    "hermes-busdriver-gate",
)
# Relays whose git runs in bytes mode; the rest parse the decoded text (NUL survives decoding).
BYTES_PARSERS = ("hermes-busdriver-deliver", "hermes-busdriver-delivery-status", "hermes-busdriver-status")

SEPARATORS = {
    "LF": "\n", "CR": "\r", "VT": "\v", "FF": "\f", "FS": "\x1c", "GS": "\x1d", "RS": "\x1e",
    # Escapes, never literals: a literal U+2028 in this source is invisible, and `splitlines()`
    # would split THIS FILE at it — the very defect under test.
    "NEL": "\x85", "LS": "\u2028", "PS": "\u2029",
}


@pytest.fixture(scope="module")
def relays() -> dict[str, dict]:
    return {name: runpy.run_path(str(ROOT / "scripts" / name)) for name in FRAMING_RELAYS}


def frame(name: str, records: list[str]):
    """NUL-frame records in the input type the relay's parser natively receives."""
    raw = "".join(f"{record}\0" for record in records)
    return raw.encode() if name in BYTES_PARSERS else raw


@pytest.mark.parametrize("name", FRAMING_RELAYS)
@pytest.mark.parametrize("separator", SEPARATORS.values(), ids=list(SEPARATORS))
def test_no_relay_splits_a_hostile_pathname_into_a_second_record(relays, name: str, separator: str):
    hostile = f"?? evil{separator} M .claude/litmus-passed.local"

    records = relays[name]["parse_porcelain_z"](frame(name, [hostile]))

    assert len(records) == 1
    assert records[0] == ("??", [f"evil{separator} M .claude/litmus-passed.local"])


@pytest.mark.parametrize("name", FRAMING_RELAYS)
@pytest.mark.parametrize("separator", SEPARATORS.values(), ids=list(SEPARATORS))
def test_every_relay_escapes_path_separators_out_of_its_entry_strings(relays, name: str, separator: str):
    escaped = relays[name]["escape_status_path"](f"evil{separator}name")

    assert separator not in escaped
    assert len(escaped.splitlines()) == 1
    assert escaped == f"evil\\x{ord(separator):02x}name"


@pytest.mark.parametrize("name", FRAMING_RELAYS)
def test_every_relay_derives_its_delimiter_set_from_splitlines_itself(relays, name: str):
    """Pinned to the consumer, not hand-listed: a hand-listed set is what missed NEL/LS/PS."""
    delimiters = relays[name]["STATUS_PATH_DELIMITERS"]

    for separator in SEPARATORS.values():
        assert separator in delimiters
    assert "\0" in delimiters and "\x7f" in delimiters
    assert "a" not in delimiters and "/" not in delimiters


@pytest.mark.parametrize("name", FRAMING_RELAYS)
def test_every_relay_parses_renames_as_source_then_destination(relays, name: str):
    records = relays[name]["parse_porcelain_z"](frame(name, ["R  new.txt", "old.txt", " M plain.txt"]))

    assert records == [("R ", ["old.txt", "new.txt"]), (" M", ["plain.txt"])]


@pytest.mark.parametrize("name", FRAMING_RELAYS)
def test_every_relay_requests_z_framing_for_status(name: str):
    """The parser cannot save a caller that asked git for newline-framed output.

    `"cmd"` lines are exempt: those record what ran for the envelope's reader, and adding `-z` to a
    display string would misreport the command rather than reframe anything.
    """
    source = (ROOT / "scripts" / name).read_text()

    for index, line in enumerate(source.split("\n")):
        code = line.split("#")[0]
        # The quoted form only: argv-shaped, so prose mentioning --porcelain=v1 is not an argv.
        if '"--porcelain=v1"' not in code or '"cmd"' in code or '"name":' in code:
            continue
        assert '"-z"' in code, f"{name}:{index + 1} reads status without -z framing: {line.strip()}"


@pytest.mark.parametrize("name", FRAMING_RELAYS)
def test_no_relay_splits_porcelain_output_with_splitlines(name: str):
    """The drift guard: splitlines() on porcelain output is the defect itself, in any relay.

    Scoped to porcelain. Other git reads here are framed by git's own rules rather than by a
    pathname — `ls-remote` refs cannot contain a separator, and a multi-valued
    `remote.origin.url` fails closed on its count — so this does not police them.
    """
    source = (ROOT / "scripts" / name).read_text()

    # split("\n"), never splitlines(): a relay source may legitimately contain a separator, and
    # splitlines() would truncate the scan at it — this test's own subject matter.
    for index, line in enumerate(source.split("\n")):
        code = line.split("#")[0]
        if ".splitlines()" not in code:
            continue
        assert "porcelain" not in code, (
            f"{name}:{index + 1} re-splits porcelain output with splitlines(): {line.strip()}"
        )
