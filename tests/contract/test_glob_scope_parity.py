"""v16-r27 item 5: glob scope matching anchors at the true end of the pathname.

`$` in Python's `re` matches at the end of the string OR just before a trailing newline, so
`glob_to_regex("*.py")` accepted `evil.py\n` — a different file from `evil.py`, admitted to a
declared scope it was never in. Pathnames are bytes-with-a-NUL-terminator on POSIX: a trailing
`\n` or `\r` is an ordinary, creatable filename character, and `-z` framing now delivers such a
name to these matchers intact. Only `\\Z` anchors strictly.

The three relays carry their own copy of this helper (standalone executables, no shared import
path), so the guarantee is asserted for all of them here rather than in one of them.
"""
import runpy
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
GLOB_RELAYS = {
    "hermes-busdriver-gate": "scripts/hermes-busdriver-gate",
    "run-pi-busdriver-draft": "scripts/pi/run-pi-busdriver-draft",
    "run-opencode-busdriver-draft": "scripts/opencode/run-opencode-busdriver-draft",
}


@pytest.fixture(scope="module")
def relays() -> dict[str, dict]:
    return {name: runpy.run_path(str(ROOT / relative)) for name, relative in GLOB_RELAYS.items()}


@pytest.mark.parametrize("name", GLOB_RELAYS)
@pytest.mark.parametrize("suffix", ["\n", "\r", "\r\n", "\n\n", "\n.env"])
def test_trailing_newline_filename_is_not_the_pattern_it_trails(name: str, relays, suffix: str):
    ns = relays[name]

    assert not ns["scope_matches"](f"src/app.py{suffix}", "src/*.py")
    assert not ns["scope_matches"](f"src/app.py{suffix}", "src/app.py")
    assert not ns["scope_matches"](f"docs/readme.md{suffix}", "docs/*.md")
    assert not ns["scope_matches"](f"docs/readme.md{suffix}", "**/*.md")


@pytest.mark.parametrize("name", GLOB_RELAYS)
def test_ordinary_paths_still_match(name: str, relays):
    """The anchor must not cost the common case."""
    ns = relays[name]

    assert ns["scope_matches"]("src/app.py", "src/*.py")
    assert ns["scope_matches"]("src/app.py", "src/app.py")
    assert ns["scope_matches"]("docs/guide/readme.md", "docs/**")
    assert not ns["scope_matches"]("src/app.js", "src/*.py")


@pytest.mark.parametrize("name", GLOB_RELAYS)
def test_regex_is_terminally_anchored(name: str, relays):
    """Anchored with \\Z, not $ — the difference is exactly the trailing-newline case above."""
    ns = relays[name]

    assert ns["glob_to_regex"]("*.py").pattern.endswith(r"\Z")
    assert not ns["glob_to_regex"]("*.py").search("evil.py\n")


# --- v16-r28 item 1: control characters, line separators and backslash are refused outright ---

# Every character below is legal in a POSIX filename and is read inconsistently by the glob
# metacharacters: `[^/]` (from `*`) swallows a newline while `.` (from `**`) does not, so the same
# byte could sneak a path INTO an include and OUT of an exclude at once.
FORBIDDEN = {
    "LF": chr(10),
    "CR": chr(13),
    "VT": chr(11),
    "FF": chr(12),
    "NUL": chr(0),
    "TAB": chr(9),
    "ESC": chr(27),
    "DEL": chr(127),
    "C1-0x80": chr(128),
    "C1-NEL": chr(133),
    "C1-0x9f": chr(159),
    "U+2028": chr(8232),
    "U+2029": chr(8233),
    "backslash": chr(92),
}


@pytest.mark.parametrize("name", GLOB_RELAYS)
@pytest.mark.parametrize("label", sorted(FORBIDDEN))
def test_forbidden_character_anywhere_in_path_never_matches(name: str, label: str, relays):
    """Embedded, not just trailing: r27 anchored the tail, which said nothing about the middle."""
    ns = relays[name]
    ch = FORBIDDEN[label]

    assert not ns["scope_matches"](f"src/ev{ch}il.py", "src/*.py")
    assert not ns["scope_matches"](f"src/{ch}app.py", "src/**")
    assert not ns["scope_matches"](f"{ch}src/app.py", "**")
    assert not ns["scope_matches"](f"src/app.py{ch}", "src/*.py")


@pytest.mark.parametrize("name", GLOB_RELAYS)
@pytest.mark.parametrize("label", sorted(FORBIDDEN))
def test_forbidden_character_in_a_pattern_never_matches(name: str, label: str, relays):
    """Identical treatment: a pattern carrying one is a broken declaration, not a wildcard."""
    ns = relays[name]
    ch = FORBIDDEN[label]

    assert not ns["scope_matches"]("src/app.py", f"src/ev{ch}il.py")
    assert not ns["scope_matches"](f"src/ev{ch}il.py", f"src/ev{ch}il.py")


@pytest.mark.parametrize("name", GLOB_RELAYS)
@pytest.mark.parametrize("label", sorted(FORBIDDEN))
def test_exclude_cannot_be_bypassed_by_a_forbidden_character(name: str, label: str, relays):
    """The fail-OPEN half. `**` compiled to `.*`, which does not cross a newline, so an exclude of
    `**/secrets/**` did not match `secrets/x<LF>.key` — the deny list missing the one filename
    crafted to dodge it. Rejection must mean out-of-scope, never merely un-excluded.
    """
    ns = relays[name]
    ch = FORBIDDEN[label]
    hostile = f"secrets/ev{ch}il.key"

    assert not ns["scope_matches"](hostile, "**/secrets/**")
    assert not ns["scope_matches"](hostile, "**")

    if name == "hermes-busdriver-gate":
        assert not ns["path_in_scope"](hostile, ["**"], ["**/secrets/**"])
        assert not ns["path_in_scope"](hostile, [], [])
        assert not ns["path_in_scope"](hostile, ["**"], [])
    elif name == "run-opencode-busdriver-draft":
        assert ns["scope_violations"]([hostile], ["**"], ["**/secrets/**"]) == [hostile]
        assert ns["scope_violations"]([hostile], ["**"], []) == [hostile]
    else:
        assert ns["scope_errors_for_path"](hostile, ["**"], ["**/secrets/**"])
        assert ns["scope_errors_for_path"](hostile, [], [])


@pytest.mark.parametrize("name", GLOB_RELAYS)
def test_backslash_is_not_folded_into_a_separator(name: str, relays):
    """On POSIX `a\\b.py` is ONE file whose name contains a backslash. Folding it to `a/b.py`
    admitted it to a scope of `a/*.py` that the real file was never declared in.
    """
    ns = relays[name]
    hostile = "a" + chr(92) + "b.py"

    assert not ns["scope_matches"](hostile, "a/*.py")
    assert not ns["scope_matches"](hostile, "a/b.py")
    assert not ns["scope_matches"](hostile, "**")

    if name == "run-pi-busdriver-draft":
        assert ns["scope_errors_for_path"](hostile, ["a/*.py"], []) == [f"file_outside_scope:{hostile}"]


@pytest.mark.parametrize("name", GLOB_RELAYS)
def test_double_star_wildcard_is_newline_safe(name: str, relays):
    """`**` means any characters. Compiled as `.*` it quietly meant "any characters but a newline",
    which is what let an exclude be dodged. Checked on the compiled regex directly, because
    scope_matches() now refuses such a path before the wildcard is ever consulted.
    """
    ns = relays[name]

    assert ns["glob_to_regex"]("**").match("a" + chr(10) + "b")
    assert ns["glob_to_regex"]("**/secrets/**").match("x" + chr(10) + "y/secrets/z")
    assert ns["glob_to_regex"]("secrets/**").match("secrets/ev" + chr(10) + "il.key")


@pytest.mark.parametrize("name", GLOB_RELAYS)
def test_ordinary_paths_still_match_after_rejection(name: str, relays):
    """The refusal must not cost the common case."""
    ns = relays[name]

    assert ns["scope_matches"]("src/app.py", "src/*.py")
    assert ns["scope_matches"]("src/a/b/c.py", "src/**")
    assert ns["scope_matches"]("docs/readme.md", "**/*.md")
    assert ns["scope_matches"]("a-b_c.1/d~e.py", "**")
